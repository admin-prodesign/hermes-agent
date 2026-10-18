"""Argument dispatch for the nemo shell scripts.

Each subcommand is one step the shell already sequenced by hand. The shell
owns systemd restarts; this module owns the decisions those restarts wait on.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from scripts.deploy.nemo.cutover_steps import apply_cutover, config_candidates, default_unit_dirs
from scripts.deploy.nemo.freeze_diff import compare, constraint_text
from scripts.deploy.nemo.frontend import mark_preinstalled
from scripts.deploy.nemo.gate import poll_until_quiet
from scripts.deploy.nemo.health import http_healthy, poll_until_healthy
from scripts.deploy.nemo.health_targets import resolve_health_plan, socket_profile_homes
from scripts.deploy.nemo.layout import (
    DEFAULT_DASHBOARD_HEALTH, DEFAULT_GATEWAY_HEALTH, DEFAULT_HEALTH_INTERVAL_S,
    DEFAULT_HEALTH_TIMEOUT_S, DEFAULT_POLL_S, DEFAULT_PROFILES, DEFAULT_QUIET_S,
    audit_dir, pin_uv_cache, releases_dir, resolve_hermes_home, valid_sha,
)
from scripts.deploy.nemo.manifest import (
    AUTO_RELEASE_SUFFIX, read_manifest, record_build_manifest, release_dir_name, write_manifest,
)
from scripts.deploy.nemo.postcheck import run_postcheck
from scripts.deploy.nemo.preflight import changed_files, plan_for
from scripts.deploy.nemo.probe import run_probe
from scripts.deploy.nemo.rollback import apply_rollback
from scripts.deploy.nemo.source import SourceMissing, acquire_source
from scripts.deploy.nemo.units import is_user_unit
from scripts.deploy.nemo.verify_mcp import compile_plan, scripts_in_release
from scripts.deploy.nemo.verify_ws import static_problems


def _home(args: argparse.Namespace) -> Path:
    explicit = Path(args.hermes_home) if args.hermes_home else None
    return resolve_hermes_home(explicit)


def _profiles(args: argparse.Namespace) -> tuple[str, ...]:
    chosen = tuple(args.profiles or ())
    return chosen or DEFAULT_PROFILES


def _spawn(argv: list[str], timeout: float, env: dict[str, str] | None = None) -> int:
    try:
        completed = subprocess.run(list(argv), env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"timed out after {timeout:.0f}s: {' '.join(argv)}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"{argv[0]}: {exc}", file=sys.stderr)
        return 1
    return int(completed.returncode)


def cmd_probe(args: argparse.Namespace) -> int:
    return run_probe(args.mirror, args.sha, args.timeout, args.remote)


def cmd_acquire(args: argparse.Namespace) -> int:
    if not valid_sha(args.sha):
        print("error: sha must be 7-40 hex characters", file=sys.stderr)
        return 1
    try:
        result = acquire_source(
            sha=args.sha, dest=args.dest,
            mirror=args.mirror, tarball=args.tarball,
            timeout=args.timeout, remote=args.remote,
        )
    except SourceMissing as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(result.method)
    return 0


def cmd_pin_cache(args: argparse.Namespace) -> int:
    print(pin_uv_cache(args.path))
    return 0


def cmd_freeze_constraint(args: argparse.Namespace) -> int:
    text = args.input.read_text(encoding="utf-8-sig")
    args.output.write_text(constraint_text(text), encoding="utf-8")
    return 0


def cmd_freeze_compare(args: argparse.Namespace) -> int:
    report, missing = compare(
        args.old.read_text(encoding="utf-8-sig"), args.new.read_text(encoding="utf-8-sig"),
    )
    args.report.write_text(report, encoding="utf-8")
    if missing:
        print("missing nemo pins: " + ", ".join(missing), file=sys.stderr)
        return 1
    return 0


def cmd_mark_frontend(args: argparse.Namespace) -> int:
    print(mark_preinstalled(args.release))
    return 0


def cmd_manifest_set(args: argparse.Namespace) -> int:
    payload: dict[str, str] = {}
    for item in args.set:
        if "=" not in item:
            print(f"expected key=value, got {item}", file=sys.stderr)
            return 2
        key, value = item.split("=", 1)
        payload[key] = value
    write_manifest(args.path, payload)
    return 0


def cmd_manifest_get(args: argparse.Namespace) -> int:
    data = read_manifest(args.path)
    if args.key not in data:
        return 1
    print(data[args.key])
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    changed = None
    if not args.full and args.mirror and args.old:
        changed = changed_files(args.mirror, args.old, args.new)
    plan = plan_for(changed, full=bool(args.full))
    print(f"# {plan.reason}")
    for name in plan.verifies:
        print(f"VERIFY {name}")
    for test in plan.tests:
        print(f"TEST {test}")
    return 0


def cmd_verify_mcp(args: argparse.Namespace) -> int:
    scripts = scripts_in_release(_home(args), args.release, _profiles(args))
    for argv in compile_plan(args.python, scripts):
        code = _spawn(list(argv), timeout=120)
        if code != 0:
            return code
    return 0


def cmd_verify_ws(args: argparse.Namespace) -> int:
    problems = static_problems(args.release)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


def cmd_gate(args: argparse.Namespace) -> int:
    ok, snaps = poll_until_quiet(
        _home(args), _profiles(args),
        quiet_s=args.quiet, poll_s=args.poll, timeout_s=args.timeout,
    )
    for snap in snaps:
        payload = asdict(snap)
        payload["db"] = str(snap.db)
        print(json.dumps(payload, sort_keys=True))
    if not ok:
        print("gate: profiles are not quiet", file=sys.stderr)
        return 1
    return 0


def cmd_cutover(args: argparse.Namespace) -> int:
    home = _home(args)
    releases = releases_dir(home, args.releases)
    audit = audit_dir(home, args.build)
    dirs = [Path(item) for item in args.unit_dirs] or default_unit_dirs()
    result = apply_cutover(
        releases=releases, build=args.build, unit_dirs=dirs,
        configs=config_candidates(home), audit=audit,
    )
    write_manifest(audit / "manifest.json", result)
    manifest_path = audit / "manifest.json"
    existing = read_manifest(manifest_path)
    sha = args.sha or existing.get("sha") or ""
    if sha:
        record_build_manifest(manifest_path, sha=str(sha), release_name=args.build)
    if not result["units"]:
        print("warning: no systemd units embed the previous release path", file=sys.stderr)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def cmd_list_units(args: argparse.Namespace) -> int:
    data = read_manifest(args.manifest)
    for item in data.get("units") or []:
        kind = "user" if item.get("user") else "system"
        print(f"{kind}\t{item['path']}")
    return 0


def _systemctl_active(path: str, user: bool) -> bool:
    argv = ["systemctl", "is-active", "--quiet"]
    if user:
        argv.append("--user")
    argv.append(Path(path).name)
    try:
        completed = subprocess.run(
            argv, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def cmd_health(args: argparse.Namespace) -> int:
    home = _home(args) if args.hermes_home else None
    plan = resolve_health_plan(home)
    units: list[tuple[str, bool]] = list(plan.extra_units)
    if args.manifest:
        for item in read_manifest(args.manifest).get("units") or []:
            units.append((str(item["path"]), bool(item.get("user"))))
    for path in args.unit:
        units.append((path, is_user_unit(Path(path))))
    gateway_url = args.gateway_url or plan.gateway_url
    dashboard_url = args.dashboard_url or plan.dashboard_url
    urls = [] if args.no_default_urls else [gateway_url, dashboard_url]
    urls.extend(args.url)
    socket_profiles = tuple(args.socket_profiles or ()) or plan.socket_profiles
    resolved_home = home if home is not None else resolve_hermes_home(None)
    socket_homes = socket_profile_homes(resolved_home, socket_profiles) if socket_profiles else []
    ok, checks = poll_until_healthy(
        units, urls, timeout_s=args.timeout, interval_s=args.interval,
        check_unit=_systemctl_active, check_url=lambda url: http_healthy(url, timeout=5),
        clock_fn=time.monotonic, sleep_fn=time.sleep,
        socket_homes=socket_homes, socket_timeout=args.socket_timeout,
    )
    for item in checks:
        state = "ok" if item.ok else "fail"
        print(f"{state}\t{item.name}\t{item.detail}")
    return 0 if ok else 1


def _post_run(argv: tuple[str, ...], env: dict[str, str]) -> int:
    return _spawn(list(argv), timeout=180, env=env)


def cmd_postcheck(args: argparse.Namespace) -> int:
    results = run_postcheck(_home(args), _profiles(args), args.python, run=_post_run)
    print(json.dumps(results, indent=2))
    return 0 if all(item["ok"] for item in results) else 1


def cmd_rollback(args: argparse.Namespace) -> int:
    print(json.dumps(apply_rollback(read_manifest(args.manifest)), indent=2))
    return 0


def cmd_release_name(args: argparse.Namespace) -> int:
    try:
        print(release_dir_name(args.sha, args.suffix or AUTO_RELEASE_SUFFIX))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def cmd_publish_venv(args: argparse.Namespace) -> int:
    from scripts.deploy.nemo.venv_publish import publish_venv

    try:
        publish_venv(args.release, args.from_staging)
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def cmd_extras_spec(args: argparse.Namespace) -> int:
    from scripts.deploy.nemo.runtime_deps import extras_spec, parse_extras

    try:
        print(extras_spec(parse_extras(args.extra)))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def cmd_check_imports(args: argparse.Namespace) -> int:
    from scripts.deploy.nemo.runtime_deps import check_runtime_imports

    try:
        check_runtime_imports(args.python, cwd=args.cwd)
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _add_home(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--hermes-home", default=None)


def _add_profiles(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", action="append", dest="profiles", default=None)


def register(sub) -> None:
    probe = sub.add_parser("probe", help="fetch one SHA and report a hang")
    probe.add_argument("--mirror", required=True, type=Path)
    probe.add_argument("--sha", required=True)
    probe.add_argument("--timeout", type=float, default=20.0)
    probe.add_argument("--remote", default="origin")
    probe.set_defaults(func=cmd_probe)

    acquire = sub.add_parser("acquire", help="fill an empty staging directory")
    acquire.add_argument("--sha", required=True)
    acquire.add_argument("--dest", required=True, type=Path)
    acquire.add_argument("--mirror", type=Path, default=None)
    acquire.add_argument("--tarball", type=Path, default=None)
    acquire.add_argument("--timeout", type=float, default=90.0)
    acquire.add_argument("--remote", default="origin")
    acquire.set_defaults(func=cmd_acquire)

    pin = sub.add_parser("pin-cache", help="mkdir and print UV_CACHE_DIR")
    pin.add_argument("--path", type=Path, default=None)
    pin.set_defaults(func=cmd_pin_cache)

    constraint = sub.add_parser("freeze-constraint", help="drop editable lines from a freeze")
    constraint.add_argument("--input", required=True, type=Path)
    constraint.add_argument("--output", required=True, type=Path)
    constraint.set_defaults(func=cmd_freeze_constraint)

    diff = sub.add_parser("freeze-compare", help="fail when a nemo pin disappeared")
    diff.add_argument("--old", required=True, type=Path)
    diff.add_argument("--new", required=True, type=Path)
    diff.add_argument("--report", required=True, type=Path)
    diff.set_defaults(func=cmd_freeze_compare)

    mark = sub.add_parser("mark-frontend", help="record that npm ci already ran")
    mark.add_argument("--release", required=True, type=Path)
    mark.set_defaults(func=cmd_mark_frontend)

    setter = sub.add_parser("manifest-set", help="merge string fields into the audit manifest")
    setter.add_argument("--path", required=True, type=Path)
    setter.add_argument("--set", action="append", default=[])
    setter.set_defaults(func=cmd_manifest_set)

    getter = sub.add_parser("manifest-get", help="print one manifest field")
    getter.add_argument("--path", required=True, type=Path)
    getter.add_argument("--key", required=True)
    getter.set_defaults(func=cmd_manifest_get)

    plan = sub.add_parser("plan", help="verifies and tests for the old/new diff")
    plan.add_argument("--mirror", type=Path, default=None)
    plan.add_argument("--old", default=None)
    plan.add_argument("--new", required=True)
    plan.add_argument("--full", action="store_true")
    plan.set_defaults(func=cmd_plan)

    verify_mcp = sub.add_parser("verify-mcp", help="compile MCP scripts inside the release")
    _add_home(verify_mcp)
    _add_profiles(verify_mcp)
    verify_mcp.add_argument("--release", required=True, type=Path)
    verify_mcp.add_argument("--python", required=True)
    verify_mcp.set_defaults(func=cmd_verify_mcp)

    verify_ws = sub.add_parser("verify-ws", help="static dashboard preinstall checks")
    verify_ws.add_argument("--release", required=True, type=Path)
    verify_ws.set_defaults(func=cmd_verify_ws)

    gate = sub.add_parser("gate", help="wait until every profile is quiet")
    _add_home(gate)
    _add_profiles(gate)
    gate.add_argument("--quiet", type=float, default=DEFAULT_QUIET_S)
    gate.add_argument("--poll", type=float, default=DEFAULT_POLL_S)
    gate.add_argument("--timeout", type=float, default=600.0)
    gate.set_defaults(func=cmd_gate)

    cutover = sub.add_parser("cutover", help="swap current, then rewrite units and configs")
    _add_home(cutover)
    cutover.add_argument("--releases", type=Path, default=None)
    cutover.add_argument("--build", required=True)
    cutover.add_argument("--sha", default=None)
    cutover.add_argument("--unit-dir", action="append", dest="unit_dirs", default=[])
    cutover.set_defaults(func=cmd_cutover)

    units = sub.add_parser("list-units", help="print kind and path for manifest units")
    units.add_argument("--manifest", required=True, type=Path)
    units.set_defaults(func=cmd_list_units)

    health = sub.add_parser("health", help="poll systemd and the health endpoints")
    _add_home(health)
    health.add_argument("--manifest", type=Path, default=None)
    health.add_argument("--unit", action="append", default=[])
    health.add_argument("--url", action="append", default=[])
    health.add_argument("--socket-profile", action="append", dest="socket_profiles", default=[])
    health.add_argument("--gateway-url", default=None)
    health.add_argument("--dashboard-url", default=None)
    health.add_argument("--no-default-urls", action="store_true")
    health.add_argument("--timeout", type=float, default=DEFAULT_HEALTH_TIMEOUT_S)
    health.add_argument("--interval", type=float, default=DEFAULT_HEALTH_INTERVAL_S)
    health.add_argument("--socket-timeout", type=float, default=5.0)
    health.set_defaults(func=cmd_health)

    post = sub.add_parser("postcheck", help="run the cron jobs' safe checks now")
    _add_home(post)
    _add_profiles(post)
    post.add_argument("--python", required=True)
    post.set_defaults(func=cmd_postcheck)

    rollback = sub.add_parser("rollback", help="restore the previous release from a manifest")
    rollback.add_argument("--manifest", required=True, type=Path)
    rollback.set_defaults(func=cmd_rollback)

    name = sub.add_parser("release-name", help="hermes-agent-<sha10>-<suffix> directory name")
    name.add_argument("--sha", required=True)
    name.add_argument("--suffix", default=AUTO_RELEASE_SUFFIX)
    name.set_defaults(func=cmd_release_name)

    publish_venv = sub.add_parser(
        "publish-venv",
        help="rewrite staging venv paths onto the published release and check the interpreter",
    )
    publish_venv.add_argument("--release", required=True, type=Path)
    publish_venv.add_argument("--from-staging", required=True, type=Path)
    publish_venv.set_defaults(func=cmd_publish_venv)

    extras = sub.add_parser("extras-spec", help="normalize a comma-separated extras list")
    extras.add_argument("--extra", default=None)
    extras.set_defaults(func=cmd_extras_spec)

    imports = sub.add_parser(
        "check-imports",
        help="import the runtime modules from a release interpreter",
    )
    imports.add_argument("--python", required=True)
    imports.add_argument("--cwd", type=Path, default=None)
    imports.set_defaults(func=cmd_check_imports)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nemo-deploy")
    register(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

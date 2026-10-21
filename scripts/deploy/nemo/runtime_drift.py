"""Daily runtime drift check: live gateway releases vs upstream ``main``.

Compares each running gateway unit's release tree to the commit at ``origin/main``
in the deploy mirror. Read-only against release directories; never prints secrets.

Exit codes (systemd treats only 0 and 1 as success when ``SuccessExitStatus=1``):

  0 — clean: every running gateway matches upstream and the tree checks pass.
  1 — drift: SHA, archive, or post-build write mismatches (notification written).
  2 — check failed: could not resolve a release root, fetch ``main``, or run the
      comparison (systemd marks the unit failed).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from scripts.deploy.nemo.drift import DriftReport, compare_tree as drift_compare_tree, tree_blobs
from scripts.deploy.nemo.layout import (
    DEFAULT_PROFILES,
    gateway_unit_name,
    releases_dir,
    resolve_hermes_home,
)
from scripts.deploy.nemo.source import Run, fetch_sha, resolve_bare_mirror, run_cmd

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_CHECK_FAILED = 2

EXCLUDE_TOP = frozenset({
    ".venv", ".python", "node_modules", ".pytest-cache", ".pytest_cache", ".git",
    ".hermes-runtime-sha", ".web_ui_build.lock", ".mypy_cache", ".ruff_cache", "build", "dist",
})
EXCLUDE_ANY = frozenset({"__pycache__", "node_modules", ".pytest_cache"})

GitRun = Callable[[list[str], float], subprocess.CompletedProcess]


@dataclass(frozen=True)
class GatewayRuntime:
    unit: str
    pid: int
    exe: str
    root: Path | None
    env_sha: str | None
    file_sha: str | None


def release_root_from_interpreter(
    exe: Path,
    *,
    pythonpath: str | None = None,
    releases: Path | None = None,
) -> Path | None:
    """Resolve the release directory from a running interpreter or ``PYTHONPATH``.

    Supports ``releases/<name>/.venv/bin/python*``, ``releases/<name>/.python/bin/python3.*``,
    and legacy ``releases/<name>/.hermes/bin/*``. The ``releases/<name>`` path component is
    authoritative; no Python version is hardcoded.
    """
    seeds: list[Path] = []
    if pythonpath:
        for entry in pythonpath.split(":"):
            if entry:
                seeds.append(Path(entry))
    seeds.append(exe)
    seen: set[Path] = set()
    for seed in seeds:
        try:
            resolved = seed.resolve(strict=False)
        except OSError:
            resolved = seed
        for path in (resolved, *resolved.parents):
            if path in seen:
                continue
            seen.add(path)
            root = _release_root_at(path, releases)
            if root is not None:
                return root
    return None


def _release_root_at(path: Path, releases: Path | None) -> Path | None:
    if releases is None:
        return None
    try:
        releases_root = releases.resolve()
    except OSError:
        releases_root = releases
    for candidate in (path, *path.parents):
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved == releases_root:
            continue
        try:
            parent = resolved.parent.resolve()
        except OSError:
            parent = resolved.parent
        if parent != releases_root:
            continue
        return resolved
    return None


def _git(mirror: Path, *args: str, check: bool = True, capture: bool = True,
         timeout: float = 600.0, run: GitRun | None = None) -> subprocess.CompletedProcess:
    runner = run or run_cmd
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    argv = ["git", "--git-dir", str(mirror), *args]
    completed = runner(argv, timeout)
    if check and completed.returncode != 0:
        err = (completed.stderr or b"").decode("utf-8", "replace")[-300:]
        raise RuntimeError(f"git {args[0]} failed rc={completed.returncode}: {err}")
    return completed


def main_sha(mirror: Path, remote: str = "origin", *, run: GitRun | None = None) -> str | None:
    mirror = resolve_bare_mirror(mirror)
    for attempt in range(2):
        try:
            completed = _git(mirror, "rev-parse", f"{remote}/main", check=True, run=run)
        except RuntimeError:
            if attempt:
                return None
            try:
                _git(mirror, "fetch", "--no-tags", remote, "main", check=True, run=run)
            except RuntimeError:
                return None
            continue
        text = (completed.stdout or b"").decode("ascii", "replace").strip()
        return text or None
    return None


def fetch_main(mirror: Path, sha: str, *, remote: str = "origin", run: GitRun | None = None) -> None:
    for lock in mirror.glob("*.lock"):
        if time.time() - lock.stat().st_mtime > 3600:
            lock.unlink(missing_ok=True)
    runner = run or run_cmd
    status = fetch_sha(mirror, sha, 600.0, remote=remote, run=runner)
    if status != "ok":
        if _git(mirror, "cat-file", "-e", sha + "^{tree}", check=False, run=runner).returncode != 0:
            raise RuntimeError(f"git fetch {sha[:10]}: {status}")


def unit_runtime(unit: str, releases: Path) -> GatewayRuntime | None:
    pid_text = subprocess.run(
        ["systemctl", "--user", "show", unit, "-p", "MainPID", "--value"],
        capture_output=True, text=True, timeout=30, check=False,
    ).stdout.strip()
    if not pid_text or pid_text == "0":
        return None
    pid = int(pid_text)
    try:
        exe = Path(os.readlink(f"/proc/{pid}/exe"))
    except OSError:
        return None
    env: dict[str, str] = {}
    try:
        for kv in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
            key, _, value = kv.partition(b"=")
            if key in (b"HERMES_RUNTIME_SHA", b"PYTHONPATH"):
                env[key.decode()] = value.decode()
    except OSError:
        pass
    root = release_root_from_interpreter(exe, pythonpath=env.get("PYTHONPATH"), releases=releases)
    file_sha = None
    if root is not None and (root / ".hermes-runtime-sha").is_file():
        file_sha = (root / ".hermes-runtime-sha").read_text(encoding="utf-8").strip()
    return GatewayRuntime(
        unit=unit, pid=pid, exe=str(exe),
        root=root, env_sha=env.get("HERMES_RUNTIME_SHA"), file_sha=file_sha,
    )


def compare_tree(root: Path, mirror: Path, sha: str, *, run: GitRun | None = None) -> dict:
    """Compare tracked files only (same rules as ``scripts.deploy.nemo.drift``)."""
    mirror = resolve_bare_mirror(mirror)
    runner = run or run_cmd
    blobs = tree_blobs(mirror, sha, run=runner)
    report = DriftReport(sha=sha)
    drift_compare_tree(root, blobs, report, mirror=mirror, sha=sha, run=runner)
    if report.error:
        raise RuntimeError(report.error)
    return {
        "files_expected": len(blobs),
        "changed": sorted(report.modified),
        "missing": sorted(report.missing),
        "extra": sorted(report.extra),
    }


def writes_after_build(root: Path) -> dict:
    marker = root / ".hermes-runtime-sha"
    built = marker.stat().st_mtime + 120 if marker.is_file() else 0.0
    source_writes, venv_writes = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_root = os.path.relpath(dirpath, root)
        rel_root = "" if rel_root == "." else rel_root + "/"
        dirnames[:] = [name for name in dirnames if name not in ("__pycache__", "node_modules", ".pytest-cache")]
        for name in filenames:
            rel = rel_root + name
            if rel.endswith((".pyc", ".lock")) or rel.startswith("hermes_cli/web_dist/"):
                continue
            try:
                if os.lstat(os.path.join(dirpath, name)).st_mtime > built:
                    (venv_writes if rel.startswith((".venv/", ".python/")) else source_writes).append(rel)
            except OSError:
                pass
    build_time = (
        datetime.fromtimestamp(built - 120, timezone.utc).isoformat()
        if marker.is_file() else None
    )
    return {
        "build_time": build_time,
        "source_writes": sorted(source_writes),
        "venv_writes": len(venv_writes),
        "venv_write_sample": sorted(venv_writes)[:10],
    }


def gateway_units(profiles: Sequence[str], overrides: dict[str, str] | None = None) -> list[str]:
    return [gateway_unit_name(profile, overrides) for profile in profiles]


def run_check(
    *,
    home: Path,
    releases: Path,
    mirror: Path,
    remote: str,
    units: Sequence[str],
    repository_label: str,
    verbose: bool,
    no_notify: bool,
    run: GitRun | None = None,
) -> int:
    mirror = resolve_bare_mirror(mirror)
    notify_dir = home / "state" / "runtime_drift_notify"
    drift_problems: list[str] = []
    fatal_problems: list[str] = []
    report: dict = {"checked_at": datetime.now(timezone.utc).isoformat(), "gateways": []}

    main_commit = main_sha(mirror, remote, run=run)
    report["origin_main"] = main_commit
    if not main_commit:
        fatal_problems.append(f"cannot read {remote}/main from mirror {mirror}")

    if main_commit and mirror.is_dir():
        try:
            fetch_main(mirror, main_commit, remote=remote, run=run)
        except RuntimeError as exc:
            fatal_problems.append(f"cannot fetch main {main_commit[:10]}: {exc}")

    roots: dict[str, str | None] = {}
    for unit in units:
        info = unit_runtime(unit, releases)
        if info is None:
            fatal_problems.append(f"{unit}: not running")
            continue
        entry = {
            "unit": info.unit,
            "pid": info.pid,
            "exe": info.exe,
            "root": str(info.root) if info.root else None,
            "env_sha": info.env_sha,
            "file_sha": info.file_sha,
        }
        report["gateways"].append(entry)
        if info.root is None:
            fatal_problems.append(f"{unit}: cannot locate release root from {info.exe}")
            continue
        for key in ("env_sha", "file_sha"):
            value = entry[key]
            if main_commit and value and value != main_commit:
                drift_problems.append(f"{unit}: {key}={value} != origin main {main_commit}")
        roots[str(info.root)] = info.file_sha

    for root_s, sha in roots.items():
        root = Path(root_s)
        result: dict = {"root": root_s}
        if sha and main_commit:
            try:
                result.update(compare_tree(root, mirror, sha, run=run))
                for key in ("changed", "missing", "extra"):
                    items = result[key]
                    if items:
                        drift_problems.append(
                            f"{root.name}: {len(items)} {key} file(s) vs git archive {sha[:10]}: {items[:5]}")
            except RuntimeError as exc:
                fatal_problems.append(f"{root.name}: tree compare failed: {exc}")
        writes = writes_after_build(root)
        result.update(writes)
        if writes["source_writes"]:
            drift_problems.append(
                f"{root.name}: {len(writes['source_writes'])} source file(s) written after build: "
                f"{writes['source_writes'][:5]}")
        if writes["venv_writes"]:
            drift_problems.append(
                f"{root.name}: {writes['venv_writes']} .venv/.python file(s) written after build "
                "(deps differ from the repo spec)")
        report.setdefault("trees", []).append(result)

    report["drift_problems"] = drift_problems
    report["fatal_problems"] = fatal_problems
    problems = fatal_problems + drift_problems
    report["problems"] = problems

    if verbose or problems:
        payload = report if verbose else {"drift_problems": drift_problems, "fatal_problems": fatal_problems}
        print(json.dumps(payload, indent=2)[:20000])

    if drift_problems and not no_notify:
        notify_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        path = notify_dir / f"drift-{stamp}.json"
        message = (
            f"[Runtime drift] live Hermes runtime does not match {repository_label}:\n- "
            + "\n- ".join(drift_problems)
        )
        path.write_text(
            json.dumps({
                "kind": "hermes_runtime_drift",
                "must_act_now": False,
                "message": message,
                "report": report,
                "written_at": report["checked_at"],
            }, indent=2) + "\n",
            encoding="utf-8",
        )

    if fatal_problems:
        return EXIT_CHECK_FAILED
    if drift_problems:
        return EXIT_DRIFT
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hermes-home", default=None, help="Hermes home (default: HERMES_HOME)")
    parser.add_argument("--releases", default=None, help="releases directory (default: <home>/releases)")
    parser.add_argument("--mirror", required=True, help="bare git mirror (same as nemo autodeploy)")
    parser.add_argument("--remote", default="origin", help="remote name on the mirror")
    parser.add_argument("--profile", action="append", dest="profiles", default=None,
                        help="gateway profile (repeatable; default pdone + default)")
    parser.add_argument("--gateway-unit", action="append", dest="gateway_units", default=[],
                        help="PROFILE=UNIT override (repeatable)")
    parser.add_argument("--repository-label", default="hermes-agent main",
                        help="label used in drift notifications")
    parser.add_argument("--verbose", action="store_true", help="print the full report even when clean")
    parser.add_argument("--no-notify", action="store_true", help="do not write a notification file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    releases = releases_dir(home, Path(args.releases) if args.releases else None)
    mirror = resolve_bare_mirror(Path(args.mirror))
    profiles = tuple(args.profiles or ()) or DEFAULT_PROFILES
    overrides = {}
    for item in args.gateway_units:
        profile, sep, unit = item.partition("=")
        if not sep or not profile or not unit:
            raise SystemExit(f"expected PROFILE=UNIT, got {item!r}")
        overrides[profile] = unit
    units = gateway_units(profiles, overrides if overrides else None)
    return run_check(
        home=home,
        releases=releases,
        mirror=mirror,
        remote=args.remote,
        units=units,
        repository_label=args.repository_label,
        verbose=args.verbose,
        no_notify=args.no_notify,
    )


if __name__ == "__main__":
    raise SystemExit(main())

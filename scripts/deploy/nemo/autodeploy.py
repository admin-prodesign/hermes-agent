"""Deploy worker: drain the poller's queue and deploy the newest SHA on main.

Runs from ``releases/current`` as a oneshot systemd unit woken by a ``.path`` unit.
It builds with ``build.sh`` and swaps with ``cutover.sh``, so the quiet-window gate,
unit rewrite, health poll, and automatic rollback are the ones a hand deploy uses.
A deploy whose diff only touches docs or bundled skills swaps ``current`` without a
restart (see ``changes.py``). Exit 75 from ``cutover.sh`` means the profiles never
went quiet: nothing changed, and the next poll queues main again. A SHA that was
rejected or failed is refused, so the poller does not retry it until a newer
commit lands or someone runs ``retry``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from scripts.deploy.nemo.changes import RESTART, SKILLS, changed_paths, classify
from scripts.deploy.nemo.drift import DriftReport, compare_tree, main_lag, stray_units, tree_blobs
from scripts.deploy.nemo.hot import sync_profiles
from scripts.deploy.nemo.layout import (
    DEFAULT_EXTRA, DEFAULT_POLL_S, DEFAULT_PROFILES, DEFAULT_QUIET_S, releases_dir,
    resolve_hermes_home,
)
from scripts.deploy.nemo.manifest import live_sha, resolve_sha_in_mirror
from scripts.deploy.nemo.autodeploy_units import service_path_env
from scripts.deploy.nemo.preflight import deploy_preflight, is_environment_failure
from scripts.deploy.nemo.release_swap import current_target
from scripts.deploy.nemo.retention import keep_set, prune, running_build, set_running
from scripts.deploy.nemo.source import Run, run_cmd
from scripts.deploy.nemo.spool import (
    Queued, forgive, queue_dir, refuse, refused_entries, state_dir, take_latest,
)

HERE = Path(__file__).resolve().parent
GATE_BUSY = 75
REFUSED_RESULTS = frozenset({"failed", "rejected"})
MAIN_REF = "refs/nemo/deploy-main"
DRIFT_MAIN_REF = "refs/nemo/drift-main"
DEFAULT_GATE_TIMEOUT_S = 6 * 3600.0
SCRIPT_MARGIN_S = 2 * 3600.0
DEFAULT_MIN_FREE_GB = 2.0
DEFAULT_MAX_LAG_S = 2 * 3600.0

Script = Callable[[list[str]], int]


@dataclass
class Config:
    home: Path
    mirror: Path
    releases: Path
    profiles: tuple[str, ...] = DEFAULT_PROFILES
    remote: str = "origin"
    extra: str = DEFAULT_EXTRA
    quiet_s: float = DEFAULT_QUIET_S
    poll_s: float = DEFAULT_POLL_S
    gate_timeout_s: float = DEFAULT_GATE_TIMEOUT_S
    min_free_gb: float = DEFAULT_MIN_FREE_GB
    fetch_timeout_s: float = 120.0
    uv_cache: Path | None = None
    alert_script: Path | None = None


@dataclass
class Outcome:
    result: str  # idle | live | deployed | waiting | deferred | failed | rejected
    sha: str = ""
    build: str = ""
    mode: str = ""
    detail: str = ""
    at: float = field(default_factory=time.time)
    superseded: list[str] = field(default_factory=list)

    @property
    def alert(self) -> bool:
        return self.result in {"failed", "rejected", "waiting"}


@dataclass
class Hooks:
    """Process boundaries, injectable for tests."""

    git: Run = run_cmd
    script: Script | None = None
    sync: Callable[..., list[dict]] = sync_profiles
    disk_free: Callable[[Path], float] = lambda path: shutil.disk_usage(path).free / 1e9


def build_name(sha: str) -> str:
    return sha[:12]


def lock_path(home: Path) -> Path:
    return state_dir(home) / "deploy.lock"


@contextlib.contextmanager
def deploy_lock(path: Path, *, blocking: bool = True) -> Iterator[bool]:
    """Yields False when ``blocking`` is off and another process holds the lock."""
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _script_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("NEMO_PYTHON", sys.executable)
    env["PATH"] = service_path_env()
    return env


def run_script(argv: list[str], timeout: float) -> int:
    """Stream to the journal. ``timeout`` must cover the gate wait plus a build."""
    try:
        return subprocess.run(argv, env=_script_env(), stdin=subprocess.DEVNULL, timeout=timeout, check=False).returncode
    except subprocess.TimeoutExpired:
        print(f"timed out after {timeout:.0f}s: {argv[1]}", file=sys.stderr)
        return 1


def fetch_main(cfg: Config, git: Run) -> str | None:
    """``None`` when origin/main is in the mirror; else a transient reason worth retrying."""
    refspec = f"+refs/heads/main:{MAIN_REF}"
    try:
        fetched = git(["git", "--git-dir", str(cfg.mirror), "fetch", "--no-tags", cfg.remote, refspec],
                      cfg.fetch_timeout_s)
    except subprocess.TimeoutExpired:
        return "git fetch main timed out"
    if fetched.returncode != 0:
        return "git fetch main failed"
    return None


def on_main(cfg: Config, sha: str, git: Run) -> str | None:
    """``None`` when ``sha`` is reachable from the fetched main, else why it is not deployable."""
    check = git(["git", "--git-dir", str(cfg.mirror), "merge-base", "--is-ancestor", sha, MAIN_REF], 30.0)
    if check.returncode == 1:
        return f"{sha} is not on main"
    if check.returncode != 0:
        return f"{sha} is not in the mirror"
    return None


def is_ancestor(cfg: Config, older: str, newer: str, git: Run) -> bool:
    """A delayed request for a commit behind the live one must not roll nemo back."""
    check = git(["git", "--git-dir", str(cfg.mirror), "merge-base", "--is-ancestor", older, newer], 30.0)
    return check.returncode == 0


def deployed_sha(cfg: Config, build: str | None) -> str | None:
    return live_sha(cfg.home, build)


def release_ready(release: Path) -> bool:
    return (release / "pyproject.toml").is_file() and (release / ".venv" / "bin" / "python").exists()


def build_argv(cfg: Config, sha: str, build: str) -> list[str]:
    argv = ["bash", str(HERE / "build.sh"), "--hermes-home", str(cfg.home), "--releases", str(cfg.releases),
            "--sha", sha, "--build", build, "--mirror", str(cfg.mirror), "--remote", cfg.remote,
            "--extra", cfg.extra, "--fetch-timeout", str(int(cfg.fetch_timeout_s))]
    if cfg.uv_cache:
        argv += ["--uv-cache", str(cfg.uv_cache)]
    return argv


def cutover_argv(cfg: Config, sha: str, build: str, old_sha: str | None, mode: str) -> list[str]:
    argv = ["bash", str(HERE / "cutover.sh"), "--hermes-home", str(cfg.home), "--releases", str(cfg.releases),
            "--build", build, "--sha", sha, "--mirror", str(cfg.mirror)]
    if old_sha:
        argv += ["--old-sha", old_sha]
    for name in cfg.profiles:
        argv += ["--profile", name]
    if mode == RESTART:
        return argv + ["--skip-pytest", "--quiet", str(cfg.quiet_s), "--poll", str(cfg.poll_s),
                       "--gate-timeout", str(int(cfg.gate_timeout_s))]
    return argv + ["--skip-preflight", "--skip-selftest", "--skip-gate", "--skip-restart", "--skip-health",
                   "--skip-postcheck"]


def _prepare_release(cfg: Config, item: Queued, build: str, hooks: Hooks, *, live_known: bool) -> str | None:
    release = cfg.releases / build
    if release_ready(release):
        return None
    if release.exists():
        if not live_known:
            return f"{release} exists but is not a finished release (live SHA unknown; not pruning)"
        prune(
            cfg.releases,
            keep_set(cfg.home, cfg.releases, with_previous=True) | {build},
            allow=True,
        )
        if release.exists():
            return f"{release} exists but is not a finished release"
    free = hooks.disk_free(cfg.releases)
    if free < cfg.min_free_gb:
        return f"only {free:.1f} GB free under {cfg.releases}; need {cfg.min_free_gb:.1f} GB"
    if hooks.script(build_argv(cfg, item.sha, build)) != 0:
        return "build.sh failed"
    return None


def _cutover(cfg: Config, item: Queued, build: str, old_build: str | None, mode: str, hooks: Hooks) -> Outcome:
    code = hooks.script(cutover_argv(cfg, item.sha, build, deployed_sha(cfg, old_build), mode))
    if code == GATE_BUSY:
        return Outcome("waiting", item.sha, build, mode,
                       f"profiles stayed busy for {int(cfg.gate_timeout_s)}s; retrying")
    if code != 0:
        live = current_target(cfg.releases)
        if live and os.path.basename(live) == build:
            return Outcome("failed", item.sha, build, mode, "cutover failed after the swap; check the host")
        return Outcome("failed", item.sha, build, mode, f"cutover exited {code}; still on {old_build}")
    if mode == RESTART:
        set_running(cfg.releases, build)
        return Outcome("deployed", item.sha, build, mode, "restarted")
    if mode == SKILLS:
        synced = hooks.sync(cfg.releases / build, cfg.home, cfg.profiles)
        bad = [entry["profile"] for entry in synced if not entry["ok"]]
        if bad:
            return Outcome("failed", item.sha, build, mode, "skill sync failed for " + ", ".join(bad))
        return Outcome("deployed", item.sha, build, mode, "skills synced without restart")
    return Outcome("deployed", item.sha, build, mode, "no runtime change; no restart")


def _expanded_sha(cfg: Config, sha: str | None, git: Run) -> str | None:
    if not sha:
        return None
    return resolve_sha_in_mirror(cfg.mirror, sha, run=git) or sha


def deploy(cfg: Config, item: Queued, hooks: Hooks) -> Outcome:
    preflight = deploy_preflight(path=service_path_env())
    if preflight:
        return Outcome("failed", item.sha, detail=preflight)
    problem = fetch_main(cfg, hooks.git)
    if problem:
        return Outcome("deferred", item.sha, detail=problem)
    reason = on_main(cfg, item.sha, hooks.git)
    if reason:
        return Outcome("rejected", item.sha, detail=reason)
    old_build = current_target(cfg.releases)
    old_sha = _expanded_sha(cfg, deployed_sha(cfg, old_build), hooks.git)
    build = build_name(item.sha)
    if old_sha and (old_sha == item.sha.lower() or item.sha.lower().startswith(old_sha)):
        return Outcome("live", item.sha, build, detail="already live")
    if old_build and os.path.basename(old_build) == build:
        return Outcome("live", item.sha, build, detail="already live")
    if old_sha and is_ancestor(cfg, item.sha, old_sha, hooks.git):
        return Outcome("rejected", item.sha, detail=f"older than the live {old_sha[:12]}")
    if old_build and running_build(cfg.releases) is None:
        set_running(cfg.releases, os.path.basename(old_build))
    mode = classify(changed_paths(cfg.mirror, old_sha, item.sha, run=hooks.git)) if old_sha else RESTART
    if old_sha:
        prune(
            cfg.releases,
            keep_set(cfg.home, cfg.releases, with_previous=True) | {build},
            allow=True,
        )
    problem = _prepare_release(cfg, item, build, hooks, live_known=bool(old_sha))
    if problem:
        return Outcome("failed", item.sha, build, mode, problem)
    return _cutover(cfg, item, build, old_build, mode, hooks)


def _record(cfg: Config, outcome: Outcome) -> None:
    root = state_dir(cfg.home)
    root.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(outcome), sort_keys=True)
    tmp = root / "status.json.tmp"
    tmp.write_text(payload + "\n", encoding="utf-8")
    os.replace(tmp, root / "status.json")
    with open(root / "history.jsonl", "a", encoding="utf-8") as handle:
        handle.write(payload + "\n")


def send_alert(script: Path | None, subject: str, body: str) -> None:
    print(f"ALERT {subject}\n{body}", file=sys.stderr)
    if script is None:
        return
    try:
        subprocess.run([str(script), subject], input=body.encode("utf-8"), timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"alert script failed: {exc}", file=sys.stderr)


def _finish(cfg: Config, item: Queued, outcome: Outcome) -> None:
    if outcome.result == "deployed" and live_sha(cfg.home, current_target(cfg.releases)):
        removed = prune(cfg.releases, keep_set(cfg.home, cfg.releases, with_previous=True), allow=True)
        if removed:
            print("pruned " + ", ".join(removed))
    if outcome.result in REFUSED_RESULTS and not is_environment_failure(outcome.detail):
        refuse(cfg.home, item.sha, outcome.result, outcome.detail)
    _record(cfg, outcome)
    if outcome.alert:
        send_alert(cfg.alert_script, f"nemo deploy {outcome.result}: {outcome.sha[:12]}",
                   json.dumps(asdict(outcome), indent=2, sort_keys=True))


def run_once(cfg: Config, hooks: Hooks | None = None) -> Outcome:
    hooks = hooks or Hooks()
    hooks.script = hooks.script or (lambda argv: run_script(argv, cfg.gate_timeout_s + SCRIPT_MARGIN_S))
    with deploy_lock(lock_path(cfg.home)):
        item, older = take_latest(queue_dir(cfg.home))
        if item is None:
            return Outcome("idle")
        outcome = deploy(cfg, item, hooks)
        outcome.superseded = [entry.sha for entry in older]
        _finish(cfg, item, outcome)
    print(json.dumps(asdict(outcome), sort_keys=True))
    return outcome


def check_drift(cfg: Config, *, unit_dirs: list[Path], max_lag_s: float, git: Run = run_cmd,
                now: float | None = None) -> DriftReport:
    build = current_target(cfg.releases)
    sha = deployed_sha(cfg, build) or ""
    report = DriftReport(sha=sha or "unknown")
    if not build:
        report.error = "releases/current is missing"
        return report
    if not sha:
        report.error = "releases/current has no SHA (manifest or release directory name)"
        return report
    full_sha = resolve_sha_in_mirror(cfg.mirror, sha, run=git) or sha
    report.sha = full_sha
    try:
        compare_tree(cfg.releases / os.path.basename(build), tree_blobs(cfg.mirror, full_sha, run=git), report)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        report.error = str(exc)
    allowed = {os.path.basename(build)} | {running_build(cfg.releases) or ""}
    report.units = stray_units(unit_dirs, cfg.releases, allowed)
    if max_lag_s > 0 and not any(queue_dir(cfg.home).glob("*.json")):
        report.behind = main_lag(cfg.mirror, full_sha, time.time() if now is None else now, max_lag_s,
                                 remote=cfg.remote, run=git, ref=DRIFT_MAIN_REF)
    return report


def _config(args: argparse.Namespace) -> Config:
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    return Config(
        home=home, mirror=Path(args.mirror).expanduser(),
        releases=releases_dir(home, Path(args.releases) if args.releases else None),
        profiles=tuple(args.profiles or ()) or DEFAULT_PROFILES, remote=args.remote,
        extra=getattr(args, "extra", DEFAULT_EXTRA),
        quiet_s=getattr(args, "quiet", DEFAULT_QUIET_S), poll_s=getattr(args, "poll", DEFAULT_POLL_S),
        gate_timeout_s=getattr(args, "gate_timeout", DEFAULT_GATE_TIMEOUT_S),
        min_free_gb=getattr(args, "min_free_gb", DEFAULT_MIN_FREE_GB),
        uv_cache=Path(args.uv_cache) if getattr(args, "uv_cache", None) else None,
        alert_script=Path(args.alert_script) if args.alert_script else None,
    )


def cmd_run(args: argparse.Namespace) -> int:
    cfg = _config(args)
    worst = 0
    while True:
        outcome = run_once(cfg)
        if outcome.result in {"idle", "waiting", "deferred"}:
            return worst
        if outcome.result in REFUSED_RESULTS:
            worst = 1


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def cmd_status(args: argparse.Namespace) -> int:
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    root = state_dir(home)
    report = {
        "deploy": _read_json(root / "status.json"),
        "poll": _read_json(root / "poll.json"),
        "queued": sorted(path.name for path in queue_dir(home).glob("*.json")),
        "refused": refused_entries(home),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    dropped = forgive(home, args.sha)
    print("retrying " + ", ".join(dropped) if dropped else "nothing refused matched")
    return 0


def cmd_drift(args: argparse.Namespace) -> int:
    from scripts.deploy.nemo.cutover_steps import default_unit_dirs

    cfg = _config(args)
    dirs = [Path(item) for item in args.unit_dirs] or default_unit_dirs()
    report = check_drift(cfg, unit_dirs=dirs, max_lag_s=args.max_lag)
    if report.clean:
        print(report.summary())
        return 0
    send_alert(cfg.alert_script, f"nemo drift: {report.sha[:12]}", report.summary(limit=50))
    return 1


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--hermes-home", default=None)
    parser.add_argument("--releases", default=None)
    parser.add_argument("--mirror", required=True)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--profile", action="append", dest="profiles", default=None)
    parser.add_argument("--alert-script", default=None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nemo-autodeploy")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="deploy the newest queued SHA, then exit")
    _common(run)
    run.add_argument("--extra", default=DEFAULT_EXTRA)
    run.add_argument("--quiet", type=float, default=DEFAULT_QUIET_S)
    run.add_argument("--poll", type=float, default=DEFAULT_POLL_S)
    run.add_argument("--gate-timeout", type=float, default=DEFAULT_GATE_TIMEOUT_S)
    run.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    run.add_argument("--uv-cache", default=None)
    run.set_defaults(func=cmd_run)
    drift = sub.add_parser("drift", help="compare the live release with its deployed SHA")
    _common(drift)
    drift.add_argument("--unit-dir", action="append", dest="unit_dirs", default=[])
    drift.add_argument("--max-lag", type=float, default=DEFAULT_MAX_LAG_S)
    drift.set_defaults(func=cmd_drift)
    status = sub.add_parser("status", help="print the last deploy, the last poll, the queue, and refused SHAs")
    status.add_argument("--hermes-home", default=None)
    status.set_defaults(func=cmd_status)
    retry = sub.add_parser("retry", help="take a refused SHA (default: all) off the list; the next poll queues it")
    retry.add_argument("--hermes-home", default=None)
    retry.add_argument("sha", nargs="?", default=None)
    retry.set_defaults(func=cmd_retry)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

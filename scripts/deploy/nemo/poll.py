"""Pull trigger: compare main on GitHub with the live SHA and queue a deploy when they differ.

Runs from ``releases/current`` as a oneshot unit started by ``hermes-deploy-poll.timer``
about once a minute. It runs ``git ls-remote`` through the bare mirror's remote, so it
reads GitHub with whatever credential the mirror already fetches with, and it needs no
inbound connection. It never builds or restarts anything: a new SHA goes into
``deploy/queue`` and ``hermes-deploy.path`` starts the worker, which does the idle gate,
cutover, health check, and rollback.

The poll skips its turn while the worker holds ``deploy.lock``, so it never runs beside
an in-flight deploy (including a gate wait for a running turn).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from scripts.deploy.nemo.autodeploy import Config, deploy_lock, deployed_sha, lock_path
from scripts.deploy.nemo.manifest import main_matches_live
from scripts.deploy.nemo.layout import releases_dir, resolve_hermes_home
from scripts.deploy.nemo.release_swap import current_target
from scripts.deploy.nemo.source import Run, run_cmd
from scripts.deploy.nemo.spool import FULL_SHA_RE, enqueue, queue_dir, queued_shas, refused_shas, state_dir

MAIN = "refs/heads/main"
DEFAULT_LS_REMOTE_TIMEOUT_S = 45.0


@dataclass
class PollResult:
    action: str  # busy | live | refused | pending | queued | error
    main: str = ""
    live: str = ""
    detail: str = ""
    at: float = field(default_factory=time.time)

    @property
    def exit_code(self) -> int:
        return 1 if self.action == "error" else 0


class PollError(RuntimeError):
    """``git ls-remote`` did not return a usable SHA for main."""


def remote_main(mirror: Path, remote: str, timeout: float, *, git: Run = run_cmd) -> str:
    argv = ["git", "--git-dir", str(mirror), "ls-remote", "--exit-code", remote, MAIN]
    try:
        done = git(argv, timeout)
    except subprocess.TimeoutExpired as exc:
        raise PollError(f"git ls-remote timed out after {timeout:.0f}s") from exc
    if done.returncode != 0:
        err = (done.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        raise PollError(f"git ls-remote exited {done.returncode}" + (f": {err[-1]}" if err else ""))
    for line in (done.stdout or b"").decode("ascii", "replace").splitlines():
        sha, _, ref = line.partition("\t")
        if ref.strip() == MAIN and FULL_SHA_RE.fullmatch(sha.strip()):
            return sha.strip()
    raise PollError("git ls-remote returned no SHA for main")


def _decide(cfg: Config, git: Run, timeout: float) -> PollResult:
    live = deployed_sha(cfg, current_target(cfg.releases)) or ""
    try:
        main = remote_main(cfg.mirror, cfg.remote, timeout, git=git)
    except PollError as exc:
        return PollResult("error", live=live, detail=str(exc))
    if main_matches_live(main, live or None):
        return PollResult("live", main, live)
    if main in refused_shas(cfg.home):
        return PollResult("refused", main, live, "refused earlier; `autodeploy.py retry` to try again")
    queue = queue_dir(cfg.home)
    if main in queued_shas(queue):
        return PollResult("pending", main, live, "already queued")
    enqueue(queue, main, ref=MAIN)
    return PollResult("queued", main, live)


def _record(home: Path, result: PollResult) -> None:
    root = state_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / "poll.json.tmp"
    tmp.write_text(json.dumps(asdict(result), sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, root / "poll.json")


def poll_once(cfg: Config, *, git: Run = run_cmd, timeout: float = DEFAULT_LS_REMOTE_TIMEOUT_S) -> PollResult:
    with deploy_lock(lock_path(cfg.home), blocking=False) as held:
        result = _decide(cfg, git, timeout) if held else PollResult("busy", detail="a deploy holds deploy.lock")
    _record(cfg.home, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nemo-deploy-poll")
    parser.add_argument("--hermes-home", default=None)
    parser.add_argument("--releases", default=None)
    parser.add_argument("--mirror", required=True)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--timeout", type=float, default=DEFAULT_LS_REMOTE_TIMEOUT_S)
    args = parser.parse_args(argv)
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    cfg = Config(home=home, mirror=Path(args.mirror).expanduser(),
                 releases=releases_dir(home, Path(args.releases) if args.releases else None), remote=args.remote)
    result = poll_once(cfg, timeout=args.timeout)
    print(json.dumps(asdict(result), sort_keys=True), file=sys.stderr if result.exit_code else sys.stdout)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

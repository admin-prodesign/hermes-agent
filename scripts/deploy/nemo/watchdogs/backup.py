"""Last successful hermes-backup push must be newer than the configured age."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from scripts.deploy.nemo.watchdogs.common import (
    Finding,
    hermes_home,
    now,
    resolve_under_home,
    run_check,
    run_cmd,
)

NAME = "backup"
DEFAULT_MARKER = "backups/last-successful-push"
DEFAULT_MAX_AGE_H = 26.0
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_SUCCESS = re.compile(r"(success|pushed|ok)", re.I)
Clock = Callable[[], float]


def _max_age_s() -> float:
    raw = os.environ.get("NEMO_WATCH_BACKUP_MAX_AGE_H", str(DEFAULT_MAX_AGE_H))
    try:
        hours = float(raw)
    except ValueError:
        hours = DEFAULT_MAX_AGE_H
    return hours * 3600.0


def parse_timestamp(text: str, fallback: float | None = None) -> float | None:
    stripped = (text or "").strip()
    if not stripped:
        return fallback
    match = _ISO.search(stripped)
    if match:
        parsed = datetime.strptime(match.group(0), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        return parsed.timestamp()
    try:
        return float(stripped.split()[0])
    except ValueError:
        return fallback


def marker_success(path: Path) -> float | None:
    try:
        mtime = path.stat().st_mtime
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return parse_timestamp(text, fallback=mtime)


def log_success(path: Path) -> float | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        mtime = path.stat().st_mtime
    except OSError:
        return None
    latest: float | None = None
    for line in text.splitlines():
        if not _SUCCESS.search(line):
            continue
        stamp = parse_timestamp(line, fallback=None)
        if stamp is not None:
            latest = stamp
    return latest if latest is not None else (mtime if _SUCCESS.search(text) else None)


def git_success(repo: Path, runner=None) -> float | None:
    if not repo.exists():
        return None
    proc = (runner or run_cmd)(
        ["git", "-C", str(repo), "log", "-1", "--format=%ct"], timeout=15
    )
    if getattr(proc, "returncode", 1) != 0:
        return None
    return parse_timestamp(getattr(proc, "stdout", "") or "")


def last_success(
    home: Path,
    *,
    runner=None,
) -> tuple[float | None, str]:
    marker = os.environ.get("NEMO_WATCH_BACKUP_MARKER", DEFAULT_MARKER)
    log = os.environ.get("NEMO_WATCH_BACKUP_LOG", "")
    repo = os.environ.get("NEMO_WATCH_BACKUP_REPO", "")
    if repo:
        stamp = git_success(resolve_under_home(repo, home), runner)
        return stamp, "git"
    stamp = marker_success(resolve_under_home(marker, home))
    if stamp is not None:
        return stamp, "marker"
    if log:
        return log_success(resolve_under_home(log, home)), "log"
    return None, "marker"


def collect(
    *,
    home: Path | None = None,
    clock: Clock | None = None,
    runner=None,
) -> list[Finding]:
    root = home or hermes_home()
    stamp, source = last_success(root, runner=runner)
    age_limit = _max_age_s()
    current = (clock or now)()
    if stamp is None:
        return [
            Finding(
                "backup:missing",
                "warn",
                "no successful hermes-backup push recorded",
                {"source": source},
            )
        ]
    age = current - stamp
    if age <= age_limit:
        return []
    return [
        Finding(
            "backup:stale",
            "warn",
            "last successful hermes-backup push is too old",
            {"source": source, "age_hours": round(age / 3600.0, 1)},
        )
    ]


def main() -> int:
    return run_check(NAME, collect)


if __name__ == "__main__":
    raise SystemExit(main())

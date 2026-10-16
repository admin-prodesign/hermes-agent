"""Deploy queue: one JSON file per accepted request under ``<home>/deploy/queue``.

The listener only writes here. The worker takes the newest request and drops
the older ones, because only the newest merge to main needs to be live.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts.deploy.nemo.webhook import FULL_SHA_RE, DeployRequest

STALE_TMP_S = 60.0


@dataclass(frozen=True)
class Queued:
    sha: str
    ref: str
    repository: str
    run_id: str
    received_at: float
    peer: str
    attempts: int = 0


def state_dir(home: Path) -> Path:
    return home / "deploy"


def queue_dir(home: Path) -> Path:
    return state_dir(home) / "queue"


def _entry_name(item: Queued) -> str:
    return f"{int(item.received_at * 1e9):020d}-{item.sha}.json"


def put(queue: Path, item: Queued) -> Path:
    queue.mkdir(parents=True, exist_ok=True, mode=0o700)
    final = queue / _entry_name(item)
    tmp = queue / (final.name + ".tmp")
    tmp.write_text(json.dumps(asdict(item), sort_keys=True), encoding="utf-8")
    os.replace(tmp, final)
    return final


def enqueue(queue: Path, request: DeployRequest, *, peer: str, now: float | None = None) -> Path:
    when = time.time() if now is None else now
    item = Queued(request.sha, request.ref, request.repository, request.run_id, when, peer)
    return put(queue, item)


def _load(path: Path) -> Queued | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        item = Queued(**data)
    except (OSError, ValueError, TypeError):
        return None
    return item if FULL_SHA_RE.fullmatch(item.sha) else None


def _sweep_tmp(queue: Path, now: float) -> None:
    for path in queue.glob("*.tmp"):
        try:
            if now - path.stat().st_mtime > STALE_TMP_S:
                path.unlink()
        except OSError:
            continue


def take_latest(queue: Path, *, now: float | None = None) -> tuple[Queued | None, list[Queued]]:
    """Remove every entry. Return the newest valid one and the ones it supersedes."""
    if not queue.is_dir():
        return None, []
    _sweep_tmp(queue, time.time() if now is None else now)
    items: list[Queued] = []
    for path in sorted(queue.glob("*.json")):
        item = _load(path)
        path.unlink(missing_ok=True)
        if item is not None:
            items.append(item)
    if not items:
        return None, []
    items.sort(key=lambda entry: entry.received_at)
    return items[-1], items[:-1]


def requeue(queue: Path, item: Queued) -> Path | None:
    """Put ``item`` back unless a newer request arrived meanwhile."""
    if queue.is_dir() and any(queue.glob("*.json")):
        return None
    return put(queue, Queued(**{**asdict(item), "attempts": item.attempts + 1}))

"""Deploy state under ``<home>/deploy``: the request queue and the refused-SHA list.

The poller only writes to the queue. The worker takes the newest request and drops
the older ones, because only the newest commit on main needs to be live. A SHA the
worker rejected or failed to deploy goes on the refused list so the poller does not
retry it every minute; ``autodeploy.py retry`` takes it off again.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")
STALE_TMP_S = 60.0


@dataclass(frozen=True)
class Queued:
    sha: str
    ref: str
    received_at: float
    source: str = "poll"


def state_dir(home: Path) -> Path:
    return home / "deploy"


def queue_dir(home: Path) -> Path:
    return state_dir(home) / "queue"


def refused_path(home: Path) -> Path:
    return state_dir(home) / "refused.jsonl"


def _entry_name(item: Queued) -> str:
    return f"{int(item.received_at * 1e9):020d}-{item.sha}.json"


def put(queue: Path, item: Queued) -> Path:
    queue.mkdir(parents=True, exist_ok=True, mode=0o700)
    final = queue / _entry_name(item)
    tmp = queue / (final.name + ".tmp")
    tmp.write_text(json.dumps(asdict(item), sort_keys=True), encoding="utf-8")
    os.replace(tmp, final)
    return final


def enqueue(queue: Path, sha: str, *, ref: str, source: str = "poll", now: float | None = None) -> Path:
    return put(queue, Queued(sha, ref, time.time() if now is None else now, source))


def _load(path: Path) -> Queued | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        item = Queued(**data)
    except (OSError, ValueError, TypeError):
        return None
    return item if FULL_SHA_RE.fullmatch(item.sha) else None


def queued_shas(queue: Path) -> set[str]:
    if not queue.is_dir():
        return set()
    return {item.sha for item in map(_load, queue.glob("*.json")) if item is not None}


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


def refuse(home: Path, sha: str, result: str, detail: str, *, now: float | None = None) -> None:
    path = refused_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"sha": sha, "result": result, "detail": detail, "at": time.time() if now is None else now}
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def refused_entries(home: Path) -> list[dict]:
    path = refused_path(home)
    if not path.is_file():
        return []
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and FULL_SHA_RE.fullmatch(str(entry.get("sha", ""))):
            entries.append(entry)
    return entries


def refused_shas(home: Path) -> set[str]:
    return {entry["sha"] for entry in refused_entries(home)}


def forgive(home: Path, sha: str | None = None) -> list[str]:
    """Drop ``sha`` (or every SHA when ``None``) from the refused list. Returns what was dropped."""
    entries = refused_entries(home)
    keep = [entry for entry in entries if sha is not None and entry["sha"] != sha]
    dropped = sorted({entry["sha"] for entry in entries} - {entry["sha"] for entry in keep})
    if not dropped:
        return []
    path = refused_path(home)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(entry, sort_keys=True) + "\n" for entry in keep), encoding="utf-8")
    os.replace(tmp, path)
    return dropped

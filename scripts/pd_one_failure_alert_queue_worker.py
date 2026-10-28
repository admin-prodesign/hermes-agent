#!/usr/bin/env python3
"""Worker that drains queued PD One failure alerts through the notification router."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.deploy.nemo.layout import resolve_hermes_home
from scripts.pd_one_notification_router import flush_held, load_state, send_route

QUEUE_REL = Path("state") / "pd_one_failure_alert_queue" / "pending.jsonl"


def queue_path(home: Path) -> Path:
    return home / QUEUE_REL


def read_queue(home: Path) -> list[dict[str, Any]]:
    path = queue_path(home)
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def write_queue(home: Path, events: list[dict[str, Any]]) -> None:
    path = queue_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not events:
        if path.is_file():
            path.unlink()
        return
    text = "\n".join(json.dumps(item, separators=(",", ":"), ensure_ascii=False) for item in events) + "\n"
    path.write_text(text, encoding="utf-8")


def process_once(home: Path, *, dry_run: bool = False) -> dict[str, Any]:
    state = load_state(home)
    released = flush_held(home, state, dry_run=dry_run)
    pending = read_queue(home)
    sent = 0
    remaining: list[dict[str, Any]] = []
    for event in pending:
        result = send_route(home, "pd_one_failure_escalations", event, dry_run=dry_run)
        if result.get("status") == "failed":
            remaining.append(event)
        else:
            sent += 1
    write_queue(home, remaining)
    return {"sent": sent, "released": released, "remaining": len(remaining)}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="PD One failure alert queue worker")
    parser.add_argument("--hermes-home", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    summary = process_once(home, dry_run=args.dry_run)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

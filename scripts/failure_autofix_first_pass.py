#!/usr/bin/env python3
"""First-pass autofix for PD One failures; pages only after local repair attempts."""

from __future__ import annotations

import json
from typing import Any

from scripts.pd_one_notification_router import send_route


def _maybe_page(home, event: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    """Notify admins through the pd_one_failure_escalations route (Neo hold, then Mattermost)."""
    return send_route(home, "pd_one_failure_escalations", event, dry_run=dry_run)


def format_page_event(*, summary: str, detail: str = "", severity: str = "error", fingerprint: str = "") -> dict[str, Any]:
    event: dict[str, Any] = {
        "severity": severity,
        "summary": summary,
        "detail": detail,
        "source": "failure_autofix_first_pass",
    }
    if fingerprint:
        event["fingerprint"] = fingerprint
    return event


def main(argv: list[str] | None = None) -> int:
    import argparse
    from pathlib import Path

    from scripts.deploy.nemo.layout import resolve_hermes_home

    parser = argparse.ArgumentParser(description="PD One failure autofix first pass")
    parser.add_argument("--hermes-home", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--detail", default="")
    parser.add_argument("--severity", default="error")
    parser.add_argument("--fingerprint", default="")
    args = parser.parse_args(argv)
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    event = format_page_event(
        summary=args.summary,
        detail=args.detail,
        severity=args.severity,
        fingerprint=args.fingerprint,
    )
    result = _maybe_page(home, event, dry_run=args.dry_run)
    print(json.dumps(result))
    return 0 if result.get("status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

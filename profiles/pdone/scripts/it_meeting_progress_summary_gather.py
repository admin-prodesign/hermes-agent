#!/usr/bin/env python3
"""Pre-run packet for cron job 9606f49ec7ec.

Prints ``not_due`` or one compact JSON object. Hermes injects that stdout
into the agent prompt. The agent writes pending.json; this script does not.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.pd_one_ops.appsheet_record_ops import AppSheetClient
from tools.pd_one_ops.pd_one_safe_ops_mcp_part0 import APPSHEET_ENV_FILES

import it_meeting_progress_summary_packet as packet

logger = logging.getLogger(__name__)
TIMEZONE = packet.TIMEZONE
_SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "appsheet-copilot"
    / "references"
    / "prodesign-schema-map.json"
)
_OPS_TIMEOUT_SECONDS = 90


def post_audit_argv(channel_id: str, lookback_days: int) -> list[str]:
    return [
        "mattermost-channel-post-audit",
        "--channel-id",
        channel_id,
        "--lookback-days",
        str(lookback_days),
        "--max-pages",
        "4",
    ]


def member_search_argv(channel_id: str, query: str, since: str) -> list[str]:
    return [
        "mattermost-member-search",
        "--sender-id",
        packet.SENDER_ID,
        "--query",
        query,
        "--channel-id",
        channel_id,
        "--since",
        since,
        "--max-results",
        "6",
        "--max-channels",
        "3",
        "--max-fallback-posts",
        "0",
    ]


def doc_header_argv(doc_id: str) -> list[str]:
    return [
        "google-docs-metadata-inspect",
        "--doc-id",
        doc_id,
        "--limit",
        "3",
    ]


def _run_ops(argv: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "tools.pd_one_ops.pd_one_safe_ops", *argv],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_OPS_TIMEOUT_SECONDS,
    )
    raw = (completed.stdout or "").strip()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {
            "status": "error",
            "error": packet.redact(raw or completed.stderr, 200),
        }
    if completed.returncode != 0 and isinstance(payload, dict):
        payload.setdefault("status", "error")
        payload.setdefault(
            "error", packet.redact(completed.stderr, 200) or "ops command failed"
        )
    if not isinstance(payload, dict):
        return {"status": "error", "error": "ops command did not return an object"}
    return payload


class LiveSources:
    """Deployed AppSheet reads plus the existing safe-ops read commands."""

    def __init__(self) -> None:
        self._client: AppSheetClient | None = None

    def find(self, table: str, selector: str) -> list[Any]:
        if self._client is None:
            env = APPSHEET_ENV_FILES()["deployed"]
            kwargs: dict[str, str] = {}
            if _SCHEMA.is_file():
                kwargs["schema_map_file"] = str(_SCHEMA)
            self._client = AppSheetClient(str(env), **kwargs)
        return self._client.find(table, selector)

    def post_audit(self, channel_id: str, lookback_days: int) -> dict[str, Any]:
        return _run_ops(post_audit_argv(channel_id, lookback_days))

    def member_search(self, channel_id: str, query: str, since: str) -> dict[str, Any]:
        return _run_ops(member_search_argv(channel_id, query, since))

    def doc_header(self, doc_id: str) -> dict[str, Any]:
        return _run_ops(doc_header_argv(doc_id))


def main() -> int:
    now = datetime.now(TIMEZONE)
    try:
        print(packet.render_run(now, LiveSources()))
    except Exception:
        logger.exception("IT meeting summary gather failed")
        print(
            packet.render_packet(
                {
                    "schema": packet.PACKET_SCHEMA,
                    "gate": "error",
                    "errors": ["gather failed"],
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

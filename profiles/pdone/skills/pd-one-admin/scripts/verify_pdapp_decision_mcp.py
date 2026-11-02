#!/usr/bin/env python3
"""Dry-run a PDAPP decision through the real pdone_safe_ops MCP transport.

This verifier never requests live mode. It proves fresh MCP discovery, confirms
that caller-controlled identity/decision fields are absent from the schema, and
prints a bounded receipt from server-side Mattermost post verification.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SAFE_SCHEMA_KEYS = {
    "ticket_id",
    "decision_post_id",
    "dry_run",
    "confirm_live_write",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket-id", required=True)
    parser.add_argument("--decision-post-id", required=True)
    parser.add_argument(
        "--profile-root",
        default="/home/prodesign/.hermes/profiles/pdone",
    )
    parser.add_argument(
        "--python",
        default="/home/prodesign/.hermes/services/hermes-ops/venv/bin/python",
    )
    return parser


async def verify(args: argparse.Namespace) -> dict:
    server_path = Path(args.profile_root) / "tools" / "pd_one_safe_ops_mcp.py"
    server = StdioServerParameters(command=args.python, args=[str(server_path)])
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool = next(
                item for item in tools.tools
                if item.name == "pd_one_admin_approval_decide"
            )
            schema_keys = set((tool.inputSchema.get("properties") or {}).keys())
            unsafe_keys = schema_keys - SAFE_SCHEMA_KEYS
            if unsafe_keys:
                raise RuntimeError(
                    f"unexpected caller-authoritative schema fields: {sorted(unsafe_keys)}"
                )
            result = await session.call_tool(
                tool.name,
                {
                    "ticket_id": args.ticket_id,
                    "decision_post_id": args.decision_post_id,
                    "dry_run": True,
                },
            )
            text = result.content[0].text if result.content else "{}"
            payload = json.loads(text)
            return {
                "tool": tool.name,
                "schema_properties": sorted(schema_keys),
                "is_error": bool(result.isError),
                "status": payload.get("status"),
                "ticket_id": payload.get("ticket_id"),
                "ticket_status": payload.get("ticket_status"),
                "ticket_status_after": payload.get("ticket_status_after"),
                "verified_actor_user_id": payload.get("verified_actor_user_id"),
                "verified_binding": payload.get("verified_binding"),
                "derived_decision": payload.get("derived_decision"),
                "would_apply": payload.get("would_apply"),
                "blocked_reason": payload.get("blocked_reason") or payload.get("reason"),
                "dry_run_only": True,
            }


def main() -> int:
    args = build_parser().parse_args()
    receipt = asyncio.run(verify(args))
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not receipt["is_error"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Dedicated PD One worker-scheduling MCP server.

This server intentionally exposes only the monthly worker scheduling dispatcher.
Keeping long OR-Tools and Google Sheets writebacks on their own MCP server
prevents the general ``pdone_safe_ops`` server from being blocked or
circuit-broken by a legitimate long scheduling call.

Run this file with the release interpreter. A script's ``sys.path[0]`` is its
own directory, so the release root (the parent of ``tools/``) is inserted
before the package import. Do not copy this file into a profile tools
directory.
"""
from __future__ import annotations

import inspect
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional, Union

_LOG = logging.getLogger("pdone_worker_scheduling")

_SERVER_NAME = "pdone_worker_scheduling"
_INSTRUCTIONS = (
    "Dedicated long-timeout PD One monthly worker scheduling tools. "
    "Use this server instead of pdone_safe_ops for scheduling playbook actions."
)


def _ensure_release_root() -> None:
    """Make ``import tools`` work when this file is executed by path.

    The same placement as the safe-ops server: the release checkout root, not
    a profile tools directory.
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)


def _json_result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _release_worker_scheduling():
    """The release dispatcher. Looked up on each call so a patch is visible."""
    _ensure_release_root()
    from tools.pd_one_ops import pd_one_safe_ops_mcp as commands

    return commands.worker_scheduling


def worker_scheduling(
    action: str,
    payload: Optional[dict[str, Any]] = None,
    dry_run: bool = True,
    timeout_seconds: int = 420,
    output_dir: Optional[str] = None,
    confirm_live_write: Optional[Union[str, bool]] = None,
) -> str:
    """Run the monthly worker-scheduling playbook through one stable action dispatcher.

    Supported actions:
    - audit_rest_requests
    - correct_raw_request_dates
    - source_setup
    - setup_scheduling_rules
    - sync_source_rollover
    - preflight
    - solve_preview (starts a background solve job by default; poll with poll_solve_preview). Every solve requires payload.following_month_required_rest_days_count; the solver jointly proves primary-month quality plus full following-month hard feasibility, while following-month requested-rest preferences are ignored.
    - poll_solve_preview
    - write_generated_schedule_from_report
    - closeout_processed_requests
    - review_im_scheduling (read-only handoff to profile im-scheduling; never writes sheets)

    Decision rule: a normal bounded solve_preview MCP timeout is a tool/runtime
    failure, not an infeasible schedule. Do not rerun with a much shorter solver
    cap and report that short-run UNKNOWN as the result. Inspect receipts, fix or
    reload the MCP path, then rerun the normal bounded solve_preview. Live source
    writes require confirm_live_write='RUN LIVE WORKER SCHEDULING SOURCE WRITE'.
    Generated schedule writeback requires confirm_live_write=true after explicit, scoped approved-user authorization for the verified primary-month writeback.
    """
    try:
        impl = _release_worker_scheduling()
        return impl(
            action=action,
            payload=payload,
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
            output_dir=output_dir,
            confirm_live_write=confirm_live_write,
        )
    except Exception as exc:  # health: allow BLE001 -- MCP boundary: any dispatcher failure is returned as JSON and the traceback is logged
        _LOG.exception("worker scheduling dispatch failed")
        return _json_result({
            "status": "error",
            "error": "worker_scheduling_dispatch_failed",
            "detail": str(exc),
            "safety": {
                "shell_used": False,
                "server": _SERVER_NAME,
            },
        })


def build_server() -> Any:
    """Expose the one scheduling dispatcher on its own stdio server."""
    from mcp.server.mcpserver import MCPServer

    _ensure_release_root()
    server = MCPServer(_SERVER_NAME, instructions=_INSTRUCTIONS)
    description = inspect.getdoc(worker_scheduling) or "worker_scheduling"
    # mcp 2.0 rejects a parameter whose name starts with "_". This signature
    # has none. structured_output stays off so the JSON string is the text
    # result, matching the release dispatcher.
    server.add_tool(
        worker_scheduling,
        name="worker_scheduling",
        description=description,
        structured_output=False,
    )
    return server


def main() -> None:
    _ensure_release_root()
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()

"""MCP wrappers added after part0/part1 so those files do not grow."""
from __future__ import annotations

import json
import logging
from typing import Optional

from tools.pd_one_ops.launch import python_argv
from tools.pd_one_ops.pd_one_safe_ops_mcp_part0 import *
from tools.pd_one_ops.site_config import resolve_configured_path

__all__ = [
    "pd_one_appsheet_user_access",
    "pd_one_mattermost_channel_member_add",
    "pd_one_mattermost_thread_move",
    "pd_one_unc_docx_table",
]


def pd_one_appsheet_user_access(
    person_id: str,
    name_zh: str,
    email: str,
    notification_groups: list[str],
    authorizing_post_id: str,
    dry_run: bool = True,
    confirm_live_write: str = "",
) -> str:
    """Grant AppSheet login/settings for one HR employee with Andy Mattermost post authorization."""
    try:
        from tools.pd_one_ops.pd_one_appsheet_user_access_ops import execute_appsheet_user_access

        payload = execute_appsheet_user_access(
            person_id=person_id,
            name_zh=name_zh,
            email=email,
            notification_groups=notification_groups,
            authorizing_post_id=authorizing_post_id,
            dry_run=dry_run,
            confirm_live_write=confirm_live_write,
        )
        return _json_result(payload)
    except Exception as exc:
        logging.getLogger("pd_one_ops").exception("pd one command failed")
        return _json_result(
            {"status": "error", "error": "invalid_request", "detail": str(exc)},
        )


def pd_one_mattermost_channel_member_add(
    channel_id: str,
    username: str,
    requester_id: str,
    confirm: str = "",
) -> str:
    """Add an active Mattermost user to a channel (admin requester, membership readback)."""
    try:
        from tools.pd_one_ops.pd_one_mattermost_channel_member_ops import execute_channel_member_add

        payload = execute_channel_member_add(
            channel_id=channel_id,
            username=username,
            requester_id=requester_id,
            confirm=confirm,
        )
        return _json_result(payload)
    except Exception as exc:
        logging.getLogger("pd_one_ops").exception("pd one command failed")
        return _json_result(
            {"status": "error", "error": "invalid_request", "detail": str(exc)},
        )


def pd_one_mattermost_thread_move(
    post_id: str,
    channel_id: str,
    requester_id: str,
    confirm: str = "",
) -> str:
    """Move a Mattermost thread to another channel (admin or it_support_operator)."""
    try:
        from tools.pd_one_ops.pd_one_mattermost_thread_move_ops import execute_thread_move

        payload = execute_thread_move(
            post_id=post_id,
            channel_id=channel_id,
            requester_id=requester_id,
            confirm=confirm,
        )
        return _json_result(payload)
    except Exception as exc:
        logging.getLogger("pd_one_ops").exception("pd one command failed")
        return _json_result(
            {"status": "error", "error": "invalid_request", "detail": str(exc)},
        )


def pd_one_unc_docx_table(
    requester_user_id: str,
    action: str = "list",
    root: str = "",
    path: str = "",
    paths: Optional[list[str]] = None,
    table_name: str = "",
    cursor: str = "",
    limit: int = 100,
    include_skipped: bool = False,
) -> str:
    """List or extract named Word tables on allowlisted UNC shares using the requester's NTFS rights.

    Staff-wide and read-only. The exact Mattermost sender id is required. Access matches that
    employee's Windows/NTFS ACLs: a user without Finance Read cannot list, search, or read
    Finance paths. The sql-srv helper identity never bypasses staff ACLs. First allowlisted
    root is ``\\\\sql-srv\\SIP&SOP\\SIP\\_原檔_新版本`` (archive folder skipped unless
    include_skipped). More roots: ``pd_one.unc_docx_roots``.
    """
    try:
        cmd = python_argv(
            resolve_configured_path("~/.hermes/profiles/pdone/tools/pd_one_unc_docx_table.py"),
            "--requester-user-id",
            requester_user_id,
            "--action",
            action,
            "--root",
            root,
            "--path",
            path,
            "--table-name",
            table_name,
            "--cursor",
            cursor,
            "--limit",
            str(max(1, min(int(limit), 200))),
        )
    except FileNotFoundError as exc:
        return json.dumps(_missing_config_result(exc), ensure_ascii=False)
    for item in paths or []:
        if str(item).strip():
            cmd.extend(["--paths", str(item).strip()])
    if include_skipped:
        cmd.append("--include-skipped")
    return run_json(cmd, timeout=240)

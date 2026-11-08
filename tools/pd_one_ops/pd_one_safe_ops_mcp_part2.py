"""MCP wrappers added after part0/part1 so those files do not grow."""
from __future__ import annotations

import json
from typing import Optional

from tools.pd_one_ops.launch import python_argv
from tools.pd_one_ops.pd_one_safe_ops_mcp_part0 import *
from tools.pd_one_ops.site_config import resolve_configured_path

__all__ = ["pd_one_unc_docx_table"]


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

"""PD One AppSheet reads that cannot return HRS private columns.

``cmd_appsheet_table_probe`` and every other read in this module drop the HRS
denylist before the result is returned. Private columns are available only from
``pd_one_hr_private_lookup``, and only when the bound Mattermost session — not
a model argument — is an HR/admin DM or an all-HR channel.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from agent.secret_scope import UnscopedSecretError, get_secret
from gateway.session_context import bound_session_value
from tools.pd_one_hr_fields import (
    PRIVATE_HRS_TABLES,
    members_are_hr_only,
    private_projection,
    redact_private_hr_columns,
    remember_private_hr_values,
)
from tools.registry import registry, tool_error, tool_result


def _secret(name: str) -> str:
    try:
        return str(get_secret(name, "") or "")
    except UnscopedSecretError:
        return ""


def policy_cache_directory() -> str:
    """Policy-cache directory from config, then the existing PD One secret."""
    try:
        from hermes_cli.config import load_config_readonly

        cfg = load_config_readonly()
    except (OSError, ValueError, TypeError):
        cfg = {}
    if isinstance(cfg, dict):
        mattermost = cfg.get("mattermost")
        if isinstance(mattermost, dict) and mattermost.get("pd_one_policy_cache_users"):
            return str(mattermost["pd_one_policy_cache_users"])
        platforms = cfg.get("platforms")
        if isinstance(platforms, dict):
            mm = platforms.get("mattermost")
            extra = mm.get("extra") if isinstance(mm, dict) else None
            if isinstance(extra, dict) and extra.get("pd_one_policy_cache_users"):
                return str(extra["pd_one_policy_cache_users"])
    return _secret("PD_ONE_POLICY_CACHE_USERS")


def load_user_policy(user_id: str, cache_dir: str | None = None) -> dict[str, Any] | None:
    """Load one policy-cache file. User ids are path segments, never traversed."""
    user_id = str(user_id or "").strip()
    if not user_id or "/" in user_id or "\\" in user_id or user_id in {".", ".."}:
        return None
    root = str(cache_dir if cache_dir is not None else policy_cache_directory() or "").strip()
    if not root:
        return None
    path = Path(root).expanduser() / f"{user_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def fetch_appsheet_rows(table: str, query: str = "") -> list[dict[str, Any]]:
    """Row source for AppSheet reads. Deployments replace this function.

    The default returns nothing. Callers that already hold rows pass them into
    the cmd functions; those rows are still redacted.
    """
    del table, query
    return []


def _appsheet_read(table: str, query: str = "", *, rows: Any = None) -> dict[str, Any]:
    """Single exit for AppSheet reads. Private columns cannot skip this."""
    source = fetch_appsheet_rows(table, query) if rows is None else rows
    table_name = str(table or "")
    if table_name in PRIVATE_HRS_TABLES:
        remember_private_hr_values(source)
    return redact_private_hr_columns(table_name, source)


def cmd_appsheet_table_probe(table: str, query: str = "", *, rows: Any = None, **_ignored: Any) -> dict[str, Any]:
    """Probe an AppSheet table. HRS private columns are replaced by a count."""
    del _ignored
    return _appsheet_read(table, query, rows=rows)


def cmd_appsheet_row_get(table: str, query: str = "", *, row: dict | None = None, rows: Any = None, **_ignored: Any) -> dict[str, Any]:
    """Single-row AppSheet read. Same denylist as the table probe."""
    del _ignored
    source = [row] if isinstance(row, dict) else rows
    payload = _appsheet_read(table, query, rows=source)
    first = payload["rows"][0] if payload["rows"] else {}
    return {"table": payload["table"], "row": first, "rows": payload["rows"], "withheld_fields": payload["withheld_fields"]}


def _safe_channel_id(chat_id: str) -> str:
    text = str(chat_id or "").strip()
    if not text or "/" in text or "\\" in text or ".." in text:
        return ""
    return text


def _mattermost_get(path: str) -> Any:
    base = _secret("MATTERMOST_URL").rstrip("/")
    token = _secret("MATTERMOST_TOKEN")
    if not base or not token:
        return None
    url = f"{base}/api/v4/{path.lstrip('/')}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, urllib.error.URLError):
        return None


def resolve_channel_member_ids(chat_id: str) -> list[str]:
    """Human members of the session channel. Failure returns [] so the lookup refuses."""
    from tools.pd_one_hr_fields import human_member_ids

    safe_id = _safe_channel_id(chat_id)
    if not safe_id:
        return []
    me = _mattermost_get("users/me")
    bot_id = str(me.get("id") or "") if isinstance(me, dict) else ""
    members = _mattermost_get(f"channels/{safe_id}/members")
    return human_member_ids(members, bot_id)


def session_destination_allows_private_hr() -> bool:
    """HR/admin DM, or a channel whose human members are all HR or admin.

    Chat id, chat type, and user id come from the bound session context. Model
    arguments and ``os.environ`` are ignored so a tool call cannot retarget the
    lookup at an HR room while the turn is somewhere else.
    """
    platform = (bound_session_value("HERMES_SESSION_PLATFORM") or "").strip().lower()
    if platform != "mattermost":
        return False
    chat_type = (bound_session_value("HERMES_SESSION_CHAT_TYPE") or "").strip().lower()
    chat_id = (bound_session_value("HERMES_SESSION_CHAT_ID") or "").strip()
    user_id = (bound_session_value("HERMES_SESSION_USER_ID") or "").strip()
    if not chat_id or not chat_type:
        return False
    if chat_type in {"dm", "direct"}:
        member_ids = [user_id] if user_id else []
    else:
        member_ids = resolve_channel_member_ids(chat_id)
    policies = [load_user_policy(member_id) for member_id in member_ids]
    return members_are_hr_only(policies)


def pd_one_hr_private_lookup(table: str, query: str = "", **_ignored: Any) -> dict[str, Any]:
    """Return private HRS columns only for an HR-only destination."""
    del _ignored
    table = str(table or "")
    if table not in PRIVATE_HRS_TABLES:
        return {"ok": False, "error": "private HR lookup only applies to HRS tables"}
    if not session_destination_allows_private_hr():
        return {
            "ok": False,
            "error": (
                "refused: private HR fields are available only in a DM with an HR or admin user, "
                "or a channel whose members all have those roles"
            ),
        }
    rows = fetch_appsheet_rows(table, query)
    remember_private_hr_values(rows)
    projected = [private_projection(row) for row in rows if isinstance(row, dict)]
    return {"ok": True, "table": table, "rows": projected}


def merged_appsheet_table_probe(
    table: str = "",
    query: str = "",
    selector: str = "",
    env: str = "prototype",
    *,
    rows: Any = None,
    **_ignored: Any,
) -> Any:
    """Probe used by the MCP server.

    A selector runs the live CLI probe, then the denylist. Without one, the
    in-process read stays so a caller that already holds rows is still filtered.
    """
    del _ignored
    if str(selector or "").strip():
        from tools.pd_one_ops.pd_one_safe_ops_mcp import pd_one_appsheet_table_probe as live

        raw = live(str(table or ""), str(selector), str(env or "prototype"))
        return _decode_probe_payload(raw)
    return cmd_appsheet_table_probe(table, query, rows=rows)


def _decode_probe_payload(raw: Any) -> Any:
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error": raw}


def mcp_read_handlers() -> dict[str, Any]:
    """Every safe-ops MCP command, with the filtered AppSheet reads in front.

    The probe and row-get names stay the in-process filtered functions. A
    selector on the probe is the live CLI path. The MCP server applies the
    denylist again on the result.
    """
    from tools.pd_one_ops.mcp_tools import iter_mcp_tools

    handlers = dict(iter_mcp_tools())
    handlers["pd_one_appsheet_table_probe"] = merged_appsheet_table_probe
    handlers["pd_one_appsheet_row_get"] = cmd_appsheet_row_get
    return handlers


def main(argv: list[str] | None = None) -> int:
    """CLI entry. Skills and the MCP server invoke this file by path."""
    import sys

    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from tools.pd_one_ops.cli import main as cli_main

    return int(cli_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())


def _probe_handler(args: dict, **_kwargs: Any) -> str:
    table = str((args or {}).get("table") or "")
    query = str((args or {}).get("query") or "")
    return tool_result(cmd_appsheet_table_probe(table, query))


def _row_handler(args: dict, **_kwargs: Any) -> str:
    table = str((args or {}).get("table") or "")
    query = str((args or {}).get("query") or "")
    return tool_result(cmd_appsheet_row_get(table, query))


def _private_handler(args: dict, **_kwargs: Any) -> str:
    # Destination keys are not read. A model-supplied channel or role cannot widen access.
    table = str((args or {}).get("table") or "")
    query = str((args or {}).get("query") or "")
    payload = pd_one_hr_private_lookup(table, query)
    if not payload.get("ok"):
        return tool_error(str(payload.get("error") or "refused"))
    return tool_result({"table": payload["table"], "rows": payload["rows"]})


_TABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "table": {"type": "string", "description": "AppSheet table name."},
        "query": {"type": "string", "description": "Optional lookup key. Do not put private field values here."},
    },
    "required": ["table"],
}

registry.register(
    name="pd_one_appsheet_table_probe",
    toolset="pdone_safe_ops",
    schema={
        "name": "pd_one_appsheet_table_probe",
        "description": (
            "Read an AppSheet table for PD One. HRS_Data and HRS_Data_MasterNames "
            "omit private columns and return a withheld_fields count."
        ),
        "parameters": _TABLE_SCHEMA,
    },
    handler=_probe_handler,
    emoji="📋",
)

registry.register(
    name="pd_one_appsheet_row_get",
    toolset="pdone_safe_ops",
    schema={
        "name": "pd_one_appsheet_row_get",
        "description": "Read one AppSheet row for PD One. HRS private columns are omitted.",
        "parameters": _TABLE_SCHEMA,
    },
    handler=_row_handler,
    emoji="📋",
)

registry.register(
    name="pd_one_hr_private_lookup",
    toolset="pdone_safe_ops",
    schema={
        "name": "pd_one_hr_private_lookup",
        "description": (
            "Return withheld HRS private columns only when the current Mattermost "
            "destination is an HR or admin DM, or a channel whose members all have "
            "those roles. The destination is the bound session, not an argument."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "enum": sorted(PRIVATE_HRS_TABLES),
                },
                "query": {"type": "string", "description": "Lookup key such as an employee id placeholder."},
            },
            "required": ["table"],
        },
    },
    handler=_private_handler,
    emoji="🔒",
)

"""Second pass of the HRS denylist for CLI and MCP results.

Row-shaped HR payloads lose private columns here. Policy documents are left
intact: blanking a whole policy text would make policy lookup useless, and the
denylist is a column filter.
"""
from __future__ import annotations

import json
from typing import Any

from tools.pd_one_hr_fields import (
    PRIVATE_HRS_TABLES,
    column_is_private,
    redact_private_hr_columns,
)

_ROW_KEYS = ("rows", "Rows", "data")
_HR_EMPLOYEE_TOOLS = frozenset({
    "pd_one_appsheet_hr_employee_patch",
    "appsheet_record_ops",
})
_HR_EMPLOYEE_TABLES = frozenset({"HR_Employees", *PRIVATE_HRS_TABLES})


def _table_name(payload: Any, table: str) -> str:
    if table:
        return str(table)
    if isinstance(payload, dict) and payload.get("table"):
        return str(payload["table"])
    return ""


def _capability(payload: Any) -> str:
    if isinstance(payload, dict) and payload.get("capability"):
        return str(payload["capability"])
    return ""


def _twin_name(arguments: dict | None) -> str:
    if not isinstance(arguments, dict):
        return ""
    return str(arguments.get("name") or arguments.get("twin") or "").strip().lower()


def hr_path(payload: Any, *, table: str = "", tool_name: str = "", arguments: dict | None = None) -> bool:
    """True when this result is an HRS or HR-employee row payload."""
    table_name = _table_name(payload, table)
    if table_name in _HR_EMPLOYEE_TABLES:
        return True
    capability = _capability(payload)
    if "hr_employee" in capability or table_name == "HR_Employees":
        return True
    if tool_name in _HR_EMPLOYEE_TOOLS and table_name in _HR_EMPLOYEE_TABLES:
        return True
    if tool_name == "pd_one_appsheet_hr_employee_patch":
        return True
    if tool_name == "appsheet_record_ops" and table_name in _HR_EMPLOYEE_TABLES:
        return True
    return tool_name == "call_function_twin" and _twin_name(arguments) == "hr"


def _strip_private_keys(value: Any) -> tuple[Any, int]:
    """Drop private column names from nested dicts. Returns (value, removed)."""
    if isinstance(value, list):
        removed = 0
        cleaned = []
        for item in value:
            nxt, count = _strip_private_keys(item)
            removed += count
            cleaned.append(nxt)
        return cleaned, removed
    if not isinstance(value, dict):
        return value, 0
    removed = 0
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if column_is_private(key):
            removed += 1
            continue
        nxt, count = _strip_private_keys(item)
        removed += count
        cleaned[key] = nxt
    return cleaned, removed


def _apply_row_redaction(payload: dict, table_name: str) -> Any:
    list_key = next((key for key in _ROW_KEYS if isinstance(payload.get(key), list)), None)
    row = payload.get("row") if isinstance(payload.get("row"), dict) else None
    if list_key is None and row is None:
        stripped, removed = _strip_private_keys(payload)
        if not removed:
            return payload
        stripped["table"] = table_name or payload.get("table") or ""
        stripped["withheld_fields"] = removed
        return stripped
    cleaned = dict(payload)
    withheld = 0
    if list_key is not None:
        redacted = redact_private_hr_columns(table_name, payload[list_key])
        if redacted["withheld_fields"]:
            cleaned[list_key] = redacted["rows"]
            withheld = int(redacted["withheld_fields"])
    if row is not None:
        redacted_one = redact_private_hr_columns(table_name, [row])
        if redacted_one["withheld_fields"]:
            cleaned["row"] = redacted_one["rows"][0] if redacted_one["rows"] else {}
            withheld = max(withheld, int(redacted_one["withheld_fields"]))
    if not withheld:
        return payload
    cleaned["table"] = table_name
    cleaned["withheld_fields"] = withheld
    return cleaned


def guard_hr_payload(
    payload: Any,
    *,
    table: str = "",
    tool_name: str = "",
    arguments: dict | None = None,
) -> Any:
    """Redact HRS/HR row payloads. A clean payload is returned unchanged."""
    if isinstance(payload, str):
        return _guard_text(payload, table=table, tool_name=tool_name, arguments=arguments)
    if not hr_path(payload, table=table, tool_name=tool_name, arguments=arguments):
        return payload
    if isinstance(payload, list):
        table_name = _table_name(payload, table) or "HRS_Data"
        redacted = redact_private_hr_columns(table_name, payload)
        if not redacted["withheld_fields"]:
            return payload
        return redacted["rows"]
    if not isinstance(payload, dict):
        return payload
    table_name = _table_name(payload, table)
    if table_name in PRIVATE_HRS_TABLES:
        return _apply_row_redaction(payload, table_name)
    stripped, removed = _strip_private_keys(payload)
    if not removed:
        return payload
    stripped["withheld_fields"] = removed
    if table_name:
        stripped["table"] = table_name
    return stripped


def _guard_text(payload: str, **kwargs: Any) -> Any:
    stripped = payload.lstrip()
    if not stripped or stripped[0] not in "{[":
        return payload
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    cleaned = guard_hr_payload(decoded, **kwargs)
    if cleaned is decoded:
        return payload
    return json.dumps(cleaned, ensure_ascii=False)

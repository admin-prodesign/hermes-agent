"""Shared denylist for PD One HRS private columns and outbound markers.

Column checks use an explicit denylist plus a substring regex, because AppSheet
names are compounds (``SalaryBand``, ``職等代碼``). Outbound text uses the same
Chinese markers and whole-word English tokens so ordinary words such as
"company" are not treated as compensation fields.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

PRIVATE_HRS_TABLES = frozenset({"HRS_Data", "HRS_Data_MasterNames"})

# Exact HRS columns that must never leave the safe probe. Passport, entry/exit,
# and residence-permit names are matched by stem below so numbering variants
# (``護照號碼``, ``residence_permit_no``) stay covered.
EXPLICIT_PRIVATE_COLUMNS = frozenset({
    "職等代碼",
    "職級代碼",
    "身份類別名稱",
    "直間接別",
    "勞退舊制年資結清",
    "工作年資起算日",
    "退休年資起算日",
    "_rownumber",
    "rownumber",
})

_PRIVATE_STEMS = (
    "護照",
    "入出境",
    "出入境",
    "居留證",
    "passport",
    "residencepermit",
    "entryexit",
    "exitentry",
)

# User-specified column regex. ``薪資`` is redundant with ``薪`` and kept so the
# denylist matches the requested pattern literally.
PRIVATE_COLUMN_RE = re.compile(
    r"職等|職級|薪|薪資|級距|grade|level|rank|salary|comp|wage|passport",
    re.IGNORECASE,
)

_TEXT_MARKER_RE = re.compile(
    r"職等|職級|薪資|級距|薪|"
    r"身份類別名稱|直間接別|勞退舊制年資結清|工作年資起算日|退休年資起算日|"
    r"_RowNumber|護照|入出境|出入境|居留證|"
    r"\b(?:grade|level|rank|salary|comp|wage|passport)\b|"
    r"\bresidence[- ]permit\b|"
    r"\bentry[- /]?exit\b",
    re.IGNORECASE,
)

HR_POLICY_ROLES = frozenset({"hr", "admin"})

# Fixed replacement. It must not itself contain private-field markers, or a
# second pass would treat the notice as another leak.
HR_PRIVATE_WITHHELD_NOTICE = (
    "The record was confirmed. Private fields were withheld.\n"
    "已確認該筆紀錄。私人欄位已隱藏。"
)


def _compact(name: str) -> str:
    return re.sub(r"[\s_\-./]+", "", name.casefold())


def column_is_private(name: object) -> bool:
    """True when an HRS column is on the denylist or matches the private regex."""
    text = str(name or "").strip()
    if not text:
        return False
    folded = text.casefold()
    compact = _compact(text)
    if folded in EXPLICIT_PRIVATE_COLUMNS or compact in EXPLICIT_PRIVATE_COLUMNS:
        return True
    if any(stem in folded or stem in compact for stem in _PRIVATE_STEMS):
        return True
    return PRIVATE_COLUMN_RE.search(text) is not None


def coerce_rows(rows: Any) -> list[dict[str, Any]]:
    """Accept a row list or an AppSheet-shaped ``{"Rows": [...]}`` payload."""
    if isinstance(rows, dict):
        for key in ("rows", "Rows", "data"):
            nested = rows.get(key)
            if isinstance(nested, list):
                rows = nested
                break
        else:
            rows = [rows]
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def redact_private_hr_columns(table: str, rows: Any) -> dict[str, Any]:
    """Drop private columns on the two HRS tables. Other tables pass through.

    ``withheld_fields`` is the number of private cells removed, not their names
    or values.
    """
    source = coerce_rows(rows)
    if table not in PRIVATE_HRS_TABLES:
        return {"table": table, "rows": source, "withheld_fields": 0}
    withheld = 0
    cleaned: list[dict[str, Any]] = []
    for row in source:
        kept: dict[str, Any] = {}
        for key, value in row.items():
            if column_is_private(key):
                withheld += 1
                continue
            kept[key] = value
        cleaned.append(kept)
    return {"table": table, "rows": cleaned, "withheld_fields": withheld}


def private_projection(row: dict[str, Any]) -> dict[str, Any]:
    """Keep only private columns. Used by the HR-only lookup, never the probe."""
    return {key: value for key, value in row.items() if column_is_private(key)}


def private_hr_marker_count(text: str) -> int:
    if not text:
        return 0
    return len(_TEXT_MARKER_RE.findall(text))


def text_has_private_hr_markers(text: str) -> bool:
    return private_hr_marker_count(text) > 0


def filter_private_hr_text(text: str, *, hr_only: bool, chat_id: str = "") -> str:
    """Replace the entire message when private markers would reach a non-HR room.

    Partial trimming is intentionally not done: a grade sitting next to a safe
    name is still a leak. The log line carries a hit count, never the text.
    """
    if hr_only or not text:
        return text
    hits = private_hr_marker_count(text)
    if hits <= 0:
        return text
    logger.warning(
        "Mattermost: withheld private HR fields from outbound message chat_id=%s marker_hits=%d",
        chat_id,
        hits,
    )
    return HR_PRIVATE_WITHHELD_NOTICE


def policy_has_hr_or_admin(policy: Any) -> bool:
    """True when a policy-cache record carries the HR or admin role."""
    if not isinstance(policy, dict):
        return False
    if policy.get("found") is False or policy.get("active") is False:
        return False
    tokens: set[str] = set()
    for key in ("roles", "safeScopes"):
        value = policy.get(key)
        if isinstance(value, str):
            parts = value.split(",")
        elif isinstance(value, (list, tuple)):
            parts = value
        else:
            continue
        tokens.update(str(part).strip().lower() for part in parts if str(part).strip())
    return bool(tokens & HR_POLICY_ROLES)


def members_are_hr_only(policies: list[Any]) -> bool:
    """Every destination human must be HR or admin. An empty roster fails closed."""
    if not policies:
        return False
    return all(policy_has_hr_or_admin(policy) for policy in policies)


def human_member_ids(payload: Any, bot_user_id: str = "") -> list[str]:
    """Mattermost ``/members`` rows, minus the bot (it is in every channel it can post to)."""
    rows: list[Any]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        nested = payload.get("members") or payload.get("users") or []
        rows = nested if isinstance(nested, list) else []
    else:
        rows = []
    ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if isinstance(row, str):
            user_id = row.strip()
        elif isinstance(row, dict):
            user_id = str(row.get("user_id") or row.get("id") or "").strip()
        else:
            continue
        if not user_id or user_id == bot_user_id or user_id in seen:
            continue
        if "/" in user_id or "\\" in user_id or user_id in {".", ".."}:
            continue
        seen.add(user_id)
        ids.append(user_id)
    return ids

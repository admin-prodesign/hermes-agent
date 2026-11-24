"""PD One Mattermost policy summaries kept off the adapter facade."""

from __future__ import annotations

from typing import Any, Optional

_PD_ONE_DRIVE_WRITER_MARKERS = (
    "without andy/admin approval",
    "writer/owner grants",
    "drive-group-authorized",
    "in-place edits without",
)


def _pd_one_summarize_data_access(data_access: Any) -> dict[str, Any]:
    """Keep Drive-group writer grants visible instead of collapsing them to read_limited."""
    if not isinstance(data_access, dict):
        return {}
    denied, full, read_limited, planned = [], [], [], []
    other: dict[str, str] = {}
    for key, value in sorted(data_access.items()):
        text = str(value).strip()
        lower = text.lower()
        if lower == "deny":
            denied.append(key)
        elif "planned" in lower:
            planned.append(key)
        elif "full" in lower:
            full.append(key)
        elif key == "googleDocsGroupDerivedAccess" or any(
            marker in lower for marker in _PD_ONE_DRIVE_WRITER_MARKERS
        ):
            other[key] = text[:180]
        elif "read" in lower or "summar" in lower or "limited" in lower or "draft" in lower:
            read_limited.append(key)
        else:
            other[key] = text[:120]
    summary: dict[str, Any] = {}
    if full:
        summary["full"] = full
    if read_limited:
        summary["read_limited"] = read_limited
    if planned:
        summary["planned"] = planned
    if denied:
        summary["denied"] = denied
    if other:
        summary["other"] = other
    return summary


def _pd_one_drive_writer_in_place_edits(data_access: Any) -> Optional[dict[str, Any]]:
    if not isinstance(data_access, dict):
        return None
    text = str(data_access.get("googleDocsGroupDerivedAccess") or "").lower()
    if not any(marker in text for marker in _PD_ONE_DRIVE_WRITER_MARKERS):
        return None
    return {
        "withoutAdminTicket": True,
        "basis": "live Drive ACL + Google Group writer/owner on the exact file",
        "doNotCreatePdappTicket": True,
        "redLines": "deletes, sharing, Drive moves, unrelated files, credentials/config/gateway/policy",
    }

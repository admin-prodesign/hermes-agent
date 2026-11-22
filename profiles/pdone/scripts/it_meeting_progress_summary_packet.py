"""Compact evidence packet for the IT meeting progress-summary job.

The cron pre-run script prints either ``not_due`` or one JSON object. The model
writes the bilingual tables from that object. Raw AppSheet rows and room
history stay in this process.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from it_meeting_progress_summary_gate import meeting_date

logger = logging.getLogger(__name__)
TIMEZONE = ZoneInfo("Asia/Taipei")
PACKET_SCHEMA = "pd-one.it-meeting-progress-summary.packet.v1"
MAX_ROWS = 40
MAX_PACKET_CHARS = 14_000
MAX_TERMS = 6
IT_MANUAL_DOC_ID = "1GshCdEa6GFkb8OrrVBf0waoIqDoRGtzkd38rJBDAf5E"
DRIVE_FOLDER_ID = "1yJHYfJ9aku46Xx8GTfQ6rQZshGFyYEVe"
ROOMS = (
    ("IT", "jp47xmyu8prytmqrhimaw9hy7e"),
    ("IT Work", "itbmu3ycsjb3tfuscmw69b9iny"),
    ("AI Discussion and IT Requests", "imj7bt6w4tdk5rsbttiga44agc"),
)
SENDER_ID = "5nak6m7nmf8kudbrwbtccazbgc"
CASE_FIELDS = (
    "CaseID",
    "Created On",
    "Title",
    "Title_zh-tw",
    "Title_en",
    "Type",
    "Status",
    "Completion Date",
)
UPDATE_FIELDS = (
    "CaseUpdateID",
    "Timestamp",
    "CaseID",
    "Case Type",
    "Update Summary",
    "Update_Summary_zh-tw",
    "Update_Summary_en",
    "New Status",
)
LEFT_OUT = (
    "personnel",
    "performance",
    "payroll",
    "finance",
    "account-reset steps",
    "MAC addresses",
    "internal IPs",
    "Case Last Updated",
    "server paths",
    "tokens",
    "service-account addresses",
)

_MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_SECRET = re.compile(
    r"(?i)(access[_ -]?key|authorization|bearer|token|api[_ -]?key)\s*[:=]\s*\S+"
)
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_+.-]{2,23}|[\u4e00-\u9fff]{2,12}")
_DOC_ID = re.compile(r"\b1[A-Za-z0-9_-]{24,}\b")
_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "ticket",
        "status",
        "not",
        "started",
        "progress",
        "review",
        "completed",
        "canceled",
        "cancelled",
        "update",
        "case",
    }
)


def redact(value: str, limit: int = 180) -> str:
    """Drop MAC, IP, and credential-shaped text, and flatten table-breaking pipes."""
    text = _SECRET.sub("[redacted]", value)
    text = _MAC.sub("[redacted]", text)
    text = _IPV4.sub("[redacted]", text)
    text = text.replace("|", "/")
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _cell(row: dict[str, Any], key: str) -> str:
    raw = row.get(key)
    if isinstance(raw, dict):
        raw = raw.get("CaseID") or raw.get("id") or raw.get("Title") or ""
    if isinstance(raw, list):
        raw = " ".join(str(item) for item in raw[:4])
    if raw is None:
        return ""
    return str(raw)


def project_row(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, str]:
    projected: dict[str, str] = {}
    for key in fields:
        text = _cell(row, key).strip()
        if text:
            projected[key] = redact(text)
    return projected


def take_rows(
    rows: list[Any], fields: tuple[str, ...], cap: int = MAX_ROWS
) -> dict[str, Any]:
    projected = [
        project_row(row, fields) for row in rows[:cap] if isinstance(row, dict)
    ]
    return {
        "returned": len(projected),
        "truncated": len(rows) > cap,
        "rows": projected,
    }


def previous_meeting_start(meeting_day: date) -> datetime:
    """13:30 Asia/Taipei on the prior 2nd or 4th Tuesday."""
    cursor = meeting_day - timedelta(days=7)
    for _ in range(8):
        ordinal = ((cursor.day - 1) // 7) + 1
        if cursor.weekday() == 1 and ordinal in (2, 4):
            return datetime(
                cursor.year, cursor.month, cursor.day, 13, 30, tzinfo=TIMEZONE
            )
        cursor -= timedelta(days=7)
    raise RuntimeError(f"no prior meeting Tuesday before {meeting_day.isoformat()}")


class Window:
    def __init__(self, meeting_day: str, start: datetime, end: datetime) -> None:
        self.meeting_date = meeting_day
        self.start = start
        self.end = end

    def start_stamp(self) -> str:
        return self.start.astimezone(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

    def since_date(self) -> str:
        return self.start.astimezone(TIMEZONE).date().isoformat()

    def lookback_days(self) -> int:
        end_day = self.end.astimezone(TIMEZONE).date()
        days = (end_day - self.start.astimezone(TIMEZONE).date()).days + 1
        return max(1, min(days, 30))


def meeting_window(now: datetime) -> Window | None:
    token = meeting_date(now)
    if token is None:
        return None
    day = now.astimezone(TIMEZONE).date()
    return Window(token, previous_meeting_start(day), now.astimezone(TIMEZONE))


def selector_new_tickets(stamp: str) -> str:
    return (
        f'Filter(Case, AND([Type] = "IT Ticket", [Created On] >= DATETIME("{stamp}")))'
    )


def selector_open_tickets() -> str:
    return (
        'Filter(Case, AND([Type] = "IT Ticket", '
        'NOT(IN([Status], LIST("Completed", "Canceled", "Cancelled")))))'
    )


def selector_updates_created_on(stamp: str) -> str:
    return f'Filter(Case_Updates, [Created On] >= DATETIME("{stamp}"))'


def selector_updates_timestamp(stamp: str) -> str:
    return f'Filter(Case_Updates, [Timestamp] >= DATETIME("{stamp}"))'


def selector_cases_by_id(case_ids: list[str]) -> str:
    inner = ", ".join(f'"{item.replace(chr(34), "")}"' for item in case_ids)
    return f"Filter(Case, IN([CaseID], LIST({inner})))"


def search_terms(*groups: list[dict[str, str]]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for row in group:
            blob = " ".join(row.values())
            for token in _TOKEN.findall(blob):
                key = token.casefold()
                if key in _STOP or key in seen:
                    continue
                seen.add(key)
                found.append(token)
                if len(found) >= MAX_TERMS:
                    return found
    return found


def _safe_find(sources: Any, table: str, selector: str) -> tuple[list[Any], str | None]:
    try:
        rows = sources.find(table, selector)
    except Exception as exc:
        logger.exception("AppSheet probe failed for %s", table)
        return [], redact(str(exc), 200) or "probe failed"
    if not isinstance(rows, list):
        return [], "probe did not return a list"
    return rows, None


def _it_case_ids(rows: list[Any]) -> set[str]:
    return {
        _cell(row, "CaseID")
        for row in rows
        if isinstance(row, dict)
        and _cell(row, "Type") == "IT Ticket"
        and _cell(row, "CaseID")
    }


def _status_index(rows: list[Any]) -> dict[str, str]:
    index: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = _cell(row, "CaseID")
        status = _cell(row, "Status")
        if case_id and status:
            index[case_id] = redact(status, 40)
    return index


def _keep_it_updates(rows: list[Any], it_ids: set[str]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        case_type = _cell(row, "Case Type")
        case_id = _cell(row, "CaseID")
        if case_type == "IT Ticket" or case_id in it_ids:
            kept.append(row)
    return kept


def _parent_ids_to_check(rows: list[Any], known: set[str]) -> list[str]:
    missing: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _cell(row, "Case Type") == "IT Ticket":
            continue
        case_id = _cell(row, "CaseID")
        if case_id and case_id not in known and case_id not in missing:
            missing.append(case_id)
    return missing[:20]


def load_case_sections(sources: Any, window: Window) -> dict[str, Any]:
    stamp = window.start_stamp()
    new_rows, new_error = _safe_find(sources, "Case", selector_new_tickets(stamp))
    open_rows, open_error = _safe_find(sources, "Case", selector_open_tickets())
    created_rows, created_error = _safe_find(
        sources, "Case_Updates", selector_updates_created_on(stamp)
    )
    stamped_rows, stamped_error = _safe_find(
        sources, "Case_Updates", selector_updates_timestamp(stamp)
    )
    known = _it_case_ids(new_rows) | _it_case_ids(open_rows)
    extra_rows: list[Any] = []
    extra_error = None
    missing = _parent_ids_to_check(stamped_rows, known)
    if missing:
        extra_rows, extra_error = _safe_find(
            sources, "Case", selector_cases_by_id(missing)
        )
        known |= _it_case_ids(extra_rows)
    kept = _keep_it_updates(stamped_rows, known)
    statuses = _status_index(new_rows + open_rows + extra_rows)
    parent_status = {
        _cell(row, "CaseID"): statuses[_cell(row, "CaseID")]
        for row in kept
        if _cell(row, "CaseID") in statuses
    }
    new_section = take_rows(new_rows, CASE_FIELDS)
    new_section["error"] = new_error
    open_section = take_rows(open_rows, CASE_FIELDS)
    open_section["error"] = open_error
    updates = take_rows(kept, UPDATE_FIELDS)
    updates["error"] = stamped_error or extra_error
    updates["parent_status"] = parent_status
    return {
        "new_tickets": new_section,
        "open_it_tickets": open_section,
        "case_updates": {
            "created_on": {
                "returned": len(created_rows),
                "error": created_error,
                "note": (
                    "Created On on Case_Updates is not the activity column. "
                    "Zero or an error here is not Case Last Updated activity."
                ),
            },
            "timestamp_it_ticket": updates,
        },
    }


def _compact_audit(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"status": "error", "error": "audit missing"}
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    error = redact(str(payload.get("error") or ""), 200)
    return {
        "status": payload.get("status") or "ok",
        "active_in_window": payload.get("active_in_window"),
        "posts_in_window": payload.get("posts_in_window"),
        "lookback_days": window.get("lookback_days"),
        "counts_are_lookback_not_topics": True,
        "error": error or None,
    }


def _compact_search(payload: Any, terms: list[str]) -> dict[str, Any]:
    if payload is None:
        return {"status": "skipped", "terms": terms, "hit_cap": False, "hits": []}
    if not isinstance(payload, dict):
        return {
            "status": "error",
            "terms": terms,
            "hits": [],
            "error": "search missing",
        }
    hits = []
    for item in (payload.get("results") or [])[:6]:
        if not isinstance(item, dict):
            continue
        hits.append(
            {
                "at": item.get("createAt"),
                "thread": item.get("originalPostId") or item.get("postId"),
                "excerpt": redact(str(item.get("excerpt") or ""), 160),
            }
        )
    error = redact(str(payload.get("error") or ""), 200)
    return {
        "status": payload.get("status") or "ok",
        "terms": terms,
        "hit_cap": bool(payload.get("hitCapReached")),
        "hits": hits,
        "error": error or None,
    }


def load_channels(
    sources: Any, window: Window, terms: list[str]
) -> list[dict[str, Any]]:
    lookback = window.lookback_days()
    since = window.since_date()
    query = ", ".join(terms)
    rooms: list[dict[str, Any]] = []
    for name, channel_id in ROOMS:
        audit = sources.post_audit(channel_id, lookback)
        search = sources.member_search(channel_id, query, since) if query else None
        rooms.append(
            {
                "name": name,
                "channel_id": channel_id,
                "audit": _compact_audit(audit),
                "search": _compact_search(search, terms),
            }
        )
    return rooms


def extra_doc_ids(channels: list[dict[str, Any]]) -> list[str]:
    blocked = {IT_MANUAL_DOC_ID, DRIVE_FOLDER_ID}
    blocked.update(channel_id for _name, channel_id in ROOMS)
    blob = json.dumps(channels, ensure_ascii=False)
    found: list[str] = []
    for match in _DOC_ID.findall(blob):
        if match in blocked or match in found:
            continue
        found.append(match)
        if len(found) >= 2:
            break
    return found


def _clip_doc_entry(entry: Any) -> str:
    if isinstance(entry, str):
        return redact(entry, 180)
    if not isinstance(entry, dict):
        return ""
    parts = [
        str(entry[key])
        for key in ("date", "text", "summary", "heading", "content")
        if entry.get(key)
    ]
    if not parts:
        parts.append(json.dumps(entry, ensure_ascii=False)[:180])
    return redact(" ".join(parts), 180)


def compact_document(doc_id: str, role: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "role": role,
            "doc_id": doc_id,
            "status": "error",
            "error": "inspect missing",
        }
    headers = []
    for header in (payload.get("headers") or [])[:4]:
        if isinstance(header, dict):
            headers.append(
                {
                    "type": header.get("type"),
                    "text": redact(str(header.get("text") or ""), 240),
                }
            )
    changelog = [
        text
        for text in (
            _clip_doc_entry(entry)
            for entry in (payload.get("recentChangelogEntries") or [])[:3]
        )
        if text
    ]
    error = redact(str(payload.get("error") or payload.get("detail") or ""), 200)
    return {
        "role": role,
        "doc_id": doc_id,
        "status": payload.get("status") or "ok",
        "title": redact(str(payload.get("documentTitle") or ""), 120),
        "headers": headers,
        "changelog": changelog,
        "error": error or None,
    }


def load_documents(
    sources: Any, channels: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    docs = [
        compact_document(
            IT_MANUAL_DOC_ID, "it_manual", sources.doc_header(IT_MANUAL_DOC_ID)
        )
    ]
    for doc_id in extra_doc_ids(channels):
        docs.append(compact_document(doc_id, "excerpt_doc", sources.doc_header(doc_id)))
    return docs


def _section_errors(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for label in ("new_tickets", "open_it_tickets"):
        message = (packet.get(label) or {}).get("error")
        if message:
            errors.append(f"{label}: {message}")
    updates = (packet.get("case_updates") or {}).get("timestamp_it_ticket") or {}
    if updates.get("error"):
        errors.append(f"case_updates: {updates['error']}")
    return errors


def assemble(now: datetime, sources: Any) -> dict[str, Any]:
    window = meeting_window(now)
    if window is None:
        raise ValueError("assemble is only for a 2nd or 4th Tuesday")
    sections = load_case_sections(sources, window)
    terms = search_terms(
        sections["new_tickets"]["rows"],
        sections["case_updates"]["timestamp_it_ticket"]["rows"],
    )
    channels = load_channels(sources, window, terms)
    documents = load_documents(sources, channels)
    packet = {
        "schema": PACKET_SCHEMA,
        "gate": f"due:{window.meeting_date}",
        "meeting_date": window.meeting_date,
        "window": {
            "start": window.start.isoformat(timespec="minutes"),
            "end": window.end.isoformat(timespec="minutes"),
            "selector_clock": "Asia/Taipei",
        },
        "new_tickets": sections["new_tickets"],
        "case_updates": sections["case_updates"],
        "open_it_tickets": sections["open_it_tickets"],
        "channels": channels,
        "documents": documents,
        "left_out": list(LEFT_OUT),
        "errors": [],
    }
    packet["errors"] = _section_errors(packet)
    return packet


def _dumps(packet: dict[str, Any]) -> str:
    return json.dumps(packet, ensure_ascii=False, separators=(",", ":"))


def _shrink_hits(packet: dict[str, Any]) -> None:
    for room in packet.get("channels") or []:
        search = room.get("search") if isinstance(room, dict) else None
        if not isinstance(search, dict):
            continue
        hits = []
        for hit in (search.get("hits") or [])[:1]:
            if isinstance(hit, dict):
                hits.append(
                    {**hit, "excerpt": redact(str(hit.get("excerpt") or ""), 40)}
                )
        search["hits"] = hits


def _shrink_open(packet: dict[str, Any]) -> None:
    section = packet.get("open_it_tickets")
    if isinstance(section, dict) and len(section.get("rows") or []) > 10:
        section["rows"] = section["rows"][:10]
        section["truncated"] = True


def _shrink_docs(packet: dict[str, Any]) -> None:
    for doc in packet.get("documents") or []:
        if isinstance(doc, dict):
            doc["headers"] = []
            doc["changelog"] = (doc.get("changelog") or [])[:1]


def _shrink_drop_open(packet: dict[str, Any]) -> None:
    packet["open_it_tickets"] = {
        "returned": 0,
        "truncated": True,
        "rows": [],
        "error": "omitted to keep the packet small",
    }


_SHRINK_STEPS: tuple[Callable[[dict[str, Any]], None], ...] = (
    _shrink_hits,
    _shrink_open,
    _shrink_docs,
    _shrink_drop_open,
)


def render_packet(packet: dict[str, Any]) -> str:
    current = copy.deepcopy(packet)
    text = _dumps(current)
    for step in _SHRINK_STEPS:
        if len(text) <= MAX_PACKET_CHARS:
            return text
        step(current)
        current["shrunk"] = True
        text = _dumps(current)
    if len(text) <= MAX_PACKET_CHARS:
        return text
    current["errors"] = ["packet truncated"]
    current["channels"] = []
    current["documents"] = []
    return _dumps(current)


def render_run(now: datetime, sources: Any) -> str:
    """Stdout for one prepare fire. ``not_due`` does not touch ``sources``."""
    if meeting_date(now) is None:
        return "not_due"
    return render_packet(assemble(now, sources))

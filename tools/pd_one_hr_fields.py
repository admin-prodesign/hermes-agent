"""Shared denylist for PD One HRS private columns and outbound markers.

Column checks use an explicit denylist plus a substring regex, because AppSheet
names are compounds (``SalaryBand``, ``職等代碼``). Outbound text redacts a span
only when a private label sits within 20 characters of a value, or when the
reply repeats a private value seen in this session. Generic words such as
level, grade, rank, and comp are not markers.
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
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
# denylist matches the requested pattern literally. Outbound matching does not
# use this regex: level/grade/rank/comp and bare 級距 would flag ordinary text.
PRIVATE_COLUMN_RE = re.compile(
    r"職等|職級|薪|薪資|級距|grade|level|rank|salary|comp|wage|passport",
    re.IGNORECASE,
)

HR_POLICY_ROLES = frozenset({"hr", "admin"})

# Whole-message fallback only when a cached probe value is still present after
# span redaction. The normal path is an inline marker naming the category.
HR_PRIVATE_WITHHELD_NOTICE = (
    "The record was confirmed. Private fields were withheld.\n"
    "已確認該筆紀錄。私人欄位已隱藏。"
)

# A label and its value may be this many characters apart. The extra tail lets
# a value that starts inside the gap finish (a date or a currency amount).
_VALUE_GAP = 20
_VALUE_TAIL = 40
_MAX_CACHED_SESSIONS = 128
_MAX_CACHED_VALUES = 256

_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)"
    r"[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*(?![A-Za-z0-9])"
)
_DATE_RE = re.compile(
    r"(?<!\d)(?:\d{4}-\d{1,2}-\d{1,2}|\d{4}/\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2}/\d{4})(?!\d)"
)
_NUMBER_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\d)")
_CURRENCY_RE = re.compile(
    r"(?:(?:NT|US|HK)\$|USD|NTD|TWD|\$|￥|¥|€|£)\s*\d[\d,]*(?:\.\d+)?",
    re.IGNORECASE,
)
_COLON_VALUE_RE = re.compile(r"[:：][ \t]{0,4}[^\s,.;:，。；、]+")
_VALUE_RES = {
    "code": _CODE_RE,
    "number": _NUMBER_RE,
    "date": _DATE_RE,
    "currency": _CURRENCY_RE,
    "colon": _COLON_VALUE_RE,
}
_EXACT_KINDS = ("code", "number", "date", "currency", "colon")
_PAY_KINDS = ("number", "currency", "colon")
_TRAVEL_KINDS = ("number", "date", "colon")
_GRADE_KINDS = ("code", "colon")

# (label, value kinds, log pattern, notice category, after_only)
_OUTBOUND_RULES: tuple[tuple[re.Pattern[str], tuple[str, ...], str, str, bool], ...] = (
    (re.compile("職等代碼"), _EXACT_KINDS, "exact_job_grade_code", "職等代碼", False),
    (re.compile("職級代碼"), _EXACT_KINDS, "exact_job_rank_code", "職級代碼", False),
    (re.compile("身份類別名稱"), _EXACT_KINDS, "exact_identity_category", "身份類別名稱", False),
    (re.compile("直間接別"), _EXACT_KINDS, "exact_direct_indirect", "直間接別", False),
    (re.compile("勞退舊制年資結清"), _EXACT_KINDS, "exact_legacy_pension", "勞退舊制年資結清", False),
    (re.compile("工作年資起算日"), _EXACT_KINDS, "exact_work_seniority_start", "工作年資起算日", False),
    (re.compile("退休年資起算日"), _EXACT_KINDS, "exact_retirement_seniority_start", "退休年資起算日", False),
    (re.compile(r"_RowNumber\b", re.IGNORECASE), _EXACT_KINDS, "exact_row_number", "_RowNumber", False),
    (re.compile("職等(?!代碼)"), _GRADE_KINDS, "grade_code", "職等", True),
    (re.compile("職級(?!代碼)"), _GRADE_KINDS, "rank_code", "職級", True),
    (re.compile("月薪"), _PAY_KINDS, "compensation", "月薪", False),
    (re.compile("薪資"), _PAY_KINDS, "compensation", "薪資", False),
    (re.compile(r"(?<!月)薪(?!資)"), _PAY_KINDS, "compensation", "薪", False),
    (re.compile(r"\bsalary\b", re.IGNORECASE), _PAY_KINDS, "compensation", "salary", False),
    (re.compile(r"\bwage\b", re.IGNORECASE), _PAY_KINDS, "compensation", "wage", False),
    (re.compile("護照"), _TRAVEL_KINDS, "travel_document", "護照", False),
    (re.compile(r"\bpassport\b", re.IGNORECASE), _TRAVEL_KINDS, "travel_document", "passport", False),
    (re.compile("居留證"), _TRAVEL_KINDS, "travel_document", "居留證", False),
    (re.compile(r"\bresidence[- ]permit\b", re.IGNORECASE), _TRAVEL_KINDS, "travel_document", "residence permit", False),
    (re.compile("入出境"), _TRAVEL_KINDS, "travel_document", "入出境", False),
)

# Short category names for the inline marker. Neither side is a stored value.
_MARKER_NAMES = {
    "職等代碼": ("grade", "職等"),
    "職級代碼": ("rank", "職級"),
    "身份類別名稱": ("identity", "身份"),
    "直間接別": ("direct-indirect", "直間接"),
    "勞退舊制年資結清": ("pension", "勞退"),
    "工作年資起算日": ("seniority", "年資"),
    "退休年資起算日": ("retirement", "退休年資"),
    "_RowNumber": ("row", "列號"),
    "職等": ("grade", "職等"),
    "職級": ("rank", "職級"),
    "月薪": ("pay", "薪資"),
    "薪資": ("pay", "薪資"),
    "薪": ("pay", "薪資"),
    "salary": ("pay", "薪資"),
    "wage": ("pay", "薪資"),
    "護照": ("passport", "護照"),
    "passport": ("passport", "護照"),
    "居留證": ("residence", "居留證"),
    "residence permit": ("residence", "居留證"),
    "入出境": ("entry-exit", "入出境"),
    "私人欄位": ("field", "欄位"),
}
_MARKER_RE = re.compile(r"\[withheld: [a-z0-9-]+\](?: 〔已隱藏：[^〕]*〕)?")
_SEP_CELL_RE = re.compile(r":?-{3,}:?")
_STEM_CATEGORIES = (
    (("居留", "residencepermit", "residence"), "居留證"),
    (("入出境", "出入境", "entryexit", "exitentry"), "入出境"),
    (("護照", "passport"), "護照"),
)
_EXACT_COLUMN_LABELS = (
    "職等代碼",
    "職級代碼",
    "身份類別名稱",
    "直間接別",
    "勞退舊制年資結清",
    "工作年資起算日",
    "退休年資起算日",
)

_CACHE_LOCK = threading.Lock()
_PRIVATE_VALUE_CACHE: dict[str, dict[str, str]] = {}


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    pattern: str
    category: str


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


def _session_cache_key() -> str:
    from gateway.session_context import bound_session_value

    for name in ("HERMES_SESSION_ID", "HERMES_SESSION_KEY"):
        value = (bound_session_value(name) or "").strip()
        if value:
            return value
    return ""


def _cacheable(text: str) -> bool:
    if len(text) >= 4:
        return True
    return len(text) >= 2 and _CODE_RE.fullmatch(text) is not None


def _cache_text(value: object) -> str | None:
    if value is None or isinstance(value, bool) or isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    if not _cacheable(text):
        return None
    return text


def _stem_category(folded: str, compact: str) -> str:
    for stems, category in _STEM_CATEGORIES:
        if any(stem in folded or stem in compact for stem in stems):
            return category
    return ""


def _category_for_column(name: str) -> str:
    folded = name.casefold()
    compact = _compact(name)
    for label in _EXACT_COLUMN_LABELS:
        if folded == label.casefold() or compact == _compact(label):
            return label
    if folded in {"_rownumber", "rownumber"} or compact in {"_rownumber", "rownumber"}:
        return "_RowNumber"
    stemmed = _stem_category(folded, compact)
    if stemmed:
        return stemmed
    if re.search(r"薪|salary|wage|comp", name, re.IGNORECASE):
        return "薪資"
    if re.search(r"職等|職級|grade|level|rank", name, re.IGNORECASE):
        return "職等"
    return "私人欄位"


def _private_cells(rows: Any) -> list[tuple[str, str]]:
    cells: list[tuple[str, str]] = []
    for row in coerce_rows(rows):
        for key, value in row.items():
            if not column_is_private(key):
                continue
            text = _cache_text(value)
            if text is None:
                continue
            cells.append((text, _category_for_column(str(key))))
    return cells


def _evict_sessions_locked() -> None:
    while len(_PRIVATE_VALUE_CACHE) >= _MAX_CACHED_SESSIONS:
        _PRIVATE_VALUE_CACHE.pop(next(iter(_PRIVATE_VALUE_CACHE)))


def remember_private_hr_values(rows: Any) -> None:
    """Remember private HRS cell values for this session. Memory only, no disk.

    The probe strips these cells before the model sees them. A later reply that
    repeats one is redacted. Short trivial tokens are not stored.
    """
    session_id = _session_cache_key()
    incoming = _private_cells(rows)
    if not session_id or not incoming:
        return
    with _CACHE_LOCK:
        bucket = _PRIVATE_VALUE_CACHE.get(session_id)
        if bucket is None:
            _evict_sessions_locked()
            bucket = {}
        else:
            _PRIVATE_VALUE_CACHE.pop(session_id, None)
        _PRIVATE_VALUE_CACHE[session_id] = bucket
        for value, category in incoming:
            if value in bucket:
                continue
            if len(bucket) >= _MAX_CACHED_VALUES:
                return
            bucket[value] = category


def clear_private_hr_value_cache() -> None:
    """Drop the in-memory value cache. Tests isolate sessions with this."""
    with _CACHE_LOCK:
        _PRIVATE_VALUE_CACHE.clear()


def _inline_marker(category: str, *, ascii_only: bool = False) -> str:
    english, chinese = _MARKER_NAMES.get(category, ("field", "欄位"))
    if ascii_only:
        return f"[withheld: {english}]"
    return f"[withheld: {english}] 〔已隱藏：{chinese}〕"


def hr_private_withheld_notice(categories: list[str]) -> str:
    """Safety notice when a cached value survives redaction. Names categories, never values."""
    labels: list[str] = []
    for category in categories:
        _english, chinese = _MARKER_NAMES.get(category, ("field", "欄位"))
        if chinese not in labels:
            labels.append(chinese)
    listed = ", ".join(labels)
    english, chinese = HR_PRIVATE_WITHHELD_NOTICE.split("\n")
    # Insert the category before the closing punctuation of the fixed sentences.
    return f"{english[:-1]} ({listed}).\n{chinese[:-1]}（{listed}）。"


def _mask_existing_markers(text: str) -> str:
    """Blank markers already written so a second pass does not re-match them."""
    return _MARKER_RE.sub(lambda match: " " * len(match.group(0)), text)


def _clip_at_pipe(region: str, *, forward: bool) -> tuple[str, int]:
    """Keep a proximity search inside one table cell."""
    pipe = region.find("|") if forward else region.rfind("|")
    if pipe < 0:
        return region, 0
    if forward:
        return region[:pipe], 0
    return region[pipe + 1:], pipe + 1


def _iter_forward(text: str, label_end: int, value_re: re.Pattern[str]):
    region, _shift = _clip_at_pipe(text[label_end:label_end + _VALUE_GAP + _VALUE_TAIL], forward=True)
    for match in value_re.finditer(region):
        if match.start() <= _VALUE_GAP:
            yield label_end + match.start(), label_end + match.end()


def _iter_backward(text: str, label_start: int, value_re: re.Pattern[str]):
    begin = max(0, label_start - _VALUE_GAP - _VALUE_TAIL)
    region, shift = _clip_at_pipe(text[begin:label_start], forward=False)
    begin += shift
    for match in value_re.finditer(region):
        value_start = begin + match.start()
        value_end = begin + match.end()
        if label_start - value_end <= _VALUE_GAP:
            yield value_start, value_end


def _nearest_value(
    text: str,
    label_start: int,
    label_end: int,
    kinds: tuple[str, ...],
    *,
    after_only: bool,
) -> tuple[int, int] | None:
    best: tuple[tuple[int, int], int, int] | None = None
    for kind in kinds:
        candidates = list(_iter_forward(text, label_end, _VALUE_RES[kind]))
        if not after_only:
            candidates.extend(_iter_backward(text, label_start, _VALUE_RES[kind]))
        for value_start, value_end in candidates:
            if value_end <= label_start:
                gap = label_start - value_end
            elif value_start >= label_end:
                gap = value_start - label_end
            else:
                continue
            if gap > _VALUE_GAP:
                continue
            rank = (gap, -(value_end - value_start))
            if best is None or rank < best[0]:
                best = (rank, value_start, value_end)
    if best is None:
        return None
    return best[1], best[2]


def _rule_spans(text: str, rule: tuple) -> list[_Span]:
    label_re, kinds, pattern, category, after_only = rule
    spans: list[_Span] = []
    for match in label_re.finditer(text):
        value = _nearest_value(
            text, match.start(), match.end(), kinds, after_only=after_only,
        )
        if value is None:
            continue
        value_start, value_end = value
        spans.append(_Span(
            min(match.start(), value_start),
            max(match.end(), value_end),
            pattern,
            category,
        ))
    return spans


def _token_char(ch: str) -> bool:
    return bool(ch) and (ch.isalnum() or ch in "-_")


def _bounded(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start else ""
    after = text[end] if end < len(text) else ""
    return not _token_char(before) and not _token_char(after)


def _find_occurrences(text: str, value: str) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    start = 0
    while True:
        index = text.find(value, start)
        if index < 0:
            return found
        end = index + len(value)
        if _bounded(text, index, end):
            found.append((index, end))
        start = end


def _cached_spans(text: str) -> list[_Span]:
    session_id = _session_cache_key()
    if not session_id:
        return []
    with _CACHE_LOCK:
        bucket = dict(_PRIVATE_VALUE_CACHE.get(session_id) or {})
    spans: list[_Span] = []
    for value, category in bucket.items():
        for start, end in _find_occurrences(text, value):
            spans.append(_Span(start, end, "cached_private_value", category))
    return spans


def _merge_spans(spans: list[_Span]) -> list[_Span]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda span: (span.start, -span.end))
    merged: list[_Span] = [ordered[0]]
    for span in ordered[1:]:
        current = merged[-1]
        if span.start < current.end:
            merged[-1] = _Span(
                current.start,
                max(current.end, span.end),
                current.pattern,
                current.category,
            )
            continue
        merged.append(span)
    return merged


def collect_private_hr_spans(text: str) -> list[_Span]:
    if not text:
        return []
    masked = _mask_existing_markers(text)
    spans: list[_Span] = []
    for rule in _OUTBOUND_RULES:
        spans.extend(_rule_spans(masked, rule))
    spans.extend(_cached_spans(masked))
    return _merge_spans(spans)


def _redact_plain(text: str, *, ascii_only: bool = False) -> tuple[str, list[_Span]]:
    spans = collect_private_hr_spans(text)
    if not spans:
        return text, []
    parts: list[str] = []
    cursor = 0
    for span in spans:
        parts.append(text[cursor:span.start])
        parts.append(_inline_marker(span.category, ascii_only=ascii_only))
        cursor = span.end
    parts.append(text[cursor:])
    return "".join(parts), spans


def _split_newline(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def _fence_mark(line: str) -> str | None:
    body, _newline = _split_newline(line)
    stripped = body.lstrip(" ")
    if len(body) - len(stripped) > 3:
        return None
    if stripped.startswith("```"):
        return "```"
    if stripped.startswith("~~~"):
        return "~~~"
    return None


def _parse_row(line: str) -> tuple[str, str, list[str], str] | None:
    """Newline, pipe prefix, cells, pipe suffix. None when the line is not a row."""
    body, newline = _split_newline(line)
    if "|" not in body:
        return None
    indent = body[: len(body) - len(body.lstrip(" "))]
    rest = body[len(indent):]
    prefix = indent
    if rest.startswith("|"):
        prefix += "|"
        rest = rest[1:]
    suffix = ""
    if rest.endswith("|"):
        suffix = "|"
        rest = rest[:-1]
    cells = rest.split("|")
    if len(cells) < 2:
        return None
    return newline, prefix, cells, suffix


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(_SEP_CELL_RE.fullmatch(cell.strip()) for cell in cells)


def _table_starts(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    header = _parse_row(lines[index])
    separator = _parse_row(lines[index + 1])
    if header is None or separator is None or len(header[2]) != len(separator[2]):
        return False
    return _is_separator(separator[2])


def _header_hit(cell: str) -> tuple[str, str] | None:
    """A header label marks the column under it, even without a value on that line."""
    text = cell.strip()
    if not text:
        return None
    for label_re, _kinds, pattern, category, _after_only in _OUTBOUND_RULES:
        if label_re.search(text):
            return pattern, category
    if column_is_private(text):
        return "table_column", _category_for_column(text)
    return None


def _replace_cell_text(cell: str, marker: str) -> str:
    stripped = cell.strip()
    if not stripped:
        return cell
    start = len(cell) - len(cell.lstrip())
    end = len(cell.rstrip())
    return cell[:start] + marker + cell[end:]


def _redact_cells(
    cells: list[str],
    column_hits: list[tuple[str, str] | None] | None,
) -> tuple[list[str], list[tuple[str, str]]]:
    rendered: list[str] = []
    found: list[tuple[str, str]] = []
    for index, cell in enumerate(cells):
        hit = column_hits[index] if column_hits else None
        if hit is not None and cell.strip():
            marker = _inline_marker(hit[1])
            replaced = _replace_cell_text(cell, marker)
            rendered.append(replaced)
            if replaced != cell:
                found.append(hit)
            continue
        redacted, spans = _redact_plain(cell)
        rendered.append(redacted)
        found.extend((span.pattern, span.category) for span in spans)
    return rendered, found


def _join_row(parsed: tuple[str, str, list[str], str], cells: list[str]) -> str:
    newline, prefix, _cells, suffix = parsed
    return prefix + "|".join(cells) + suffix + newline


def _consume_fence(
    lines: list[str],
    index: int,
    fence: str,
    out: list[str],
    hits: list[tuple[str, str]],
) -> int:
    out.append(lines[index])
    index += 1
    while index < len(lines):
        if _fence_mark(lines[index]) == fence:
            out.append(lines[index])
            return index + 1
        body, newline = _split_newline(lines[index])
        redacted, spans = _redact_plain(body, ascii_only=True)
        out.append(redacted + newline)
        hits.extend((span.pattern, span.category) for span in spans)
        index += 1
    return index


def _consume_table(
    lines: list[str],
    index: int,
    out: list[str],
    hits: list[tuple[str, str]],
) -> int:
    header = _parse_row(lines[index])
    if header is None:
        return index
    column_hits = [_header_hit(cell) for cell in header[2]]
    rendered, found = _redact_cells(header[2], None)
    out.append(_join_row(header, rendered))
    hits.extend(found)
    out.append(lines[index + 1])
    width = len(header[2])
    index += 2
    while index < len(lines) and _fence_mark(lines[index]) is None:
        row = _parse_row(lines[index])
        if row is None or len(row[2]) != width or _is_separator(row[2]):
            break
        rendered, found = _redact_cells(row[2], column_hits)
        out.append(_join_row(row, rendered))
        hits.extend(found)
        index += 1
    return index


def _redact_document(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    hits: list[tuple[str, str]] = []
    index = 0
    while index < len(lines):
        fence = _fence_mark(lines[index])
        if fence is not None:
            index = _consume_fence(lines, index, fence, out, hits)
            continue
        if _table_starts(lines, index):
            index = _consume_table(lines, index, out, hits)
            continue
        end = index + 1
        while end < len(lines) and _fence_mark(lines[end]) is None and not _table_starts(lines, end):
            end += 1
        redacted, spans = _redact_plain("".join(lines[index:end]))
        out.append(redacted)
        hits.extend((span.pattern, span.category) for span in spans)
        index = end
    return "".join(out), hits


def private_hr_marker_count(text: str) -> int:
    if not text:
        return 0
    return len(collect_private_hr_spans(text))


def text_has_private_hr_markers(text: str) -> bool:
    return private_hr_marker_count(text) > 0


def filter_private_hr_text(text: str, *, hr_only: bool, chat_id: str = "") -> str:
    """Redact private spans before a non-HR room sees them.

    Table cells and fenced lines are redacted in place so the pipes, column
    count, and fences stay. The whole message is replaced only when a cached
    probe value is still present after that pass. The log records pattern
    names, never the message or the value.
    """
    if hr_only or not text:
        return text
    redacted, hits = _redact_document(text)
    leftover = _cached_spans(_mask_existing_markers(redacted))
    if not hits and not leftover:
        return text
    patterns = [pattern for pattern, _category in hits]
    categories = [category for _pattern, category in hits]
    if leftover:
        patterns.extend(span.pattern for span in leftover)
        categories.extend(span.category for span in leftover)
    logger.warning(
        "Mattermost: withheld private HR fields from outbound message chat_id=%s patterns=%s",
        chat_id,
        ",".join(dict.fromkeys(patterns)),
    )
    if leftover:
        return hr_private_withheld_notice(categories)
    return redacted


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

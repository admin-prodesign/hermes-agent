"""Mattermost-safe splitting for long bilingual posts.

When a reply exceeds the practical Mattermost post length, prefer:

1. Language-first: English block then Traditional Chinese (or the reverse,
   matching the already-drafted order), usually separated by a ``---`` rule.
2. Markdown-safe packing: never cut through a fenced code block or GFM table.
3. Last resort: reopen code fences or repeat table headers if one atomic
   region is itself over the limit.

This is used by ``MattermostAdapter.truncate_message``.
"""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple

INDICATOR_RESERVE = 12  # room for "\n(XX/XX)" on its own line
FENCE_CLOSE = "\n```"
TABLE_SEP_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}\s*(\|\s*:?-{3,}\s*)+\|?\s*$"
)
HR_RE = re.compile(r"(?m)^\s*-{3,}\s*$")
FENCE_LINE_RE = re.compile(r"^\s*```")

Block = Tuple[int, int, str]  # start, end, kind


def split_mattermost_message(content: str, max_length: int = 4000) -> List[str]:
    """Split ``content`` into Mattermost posts that stay within ``max_length``."""
    if content is None:
        return [""]
    if max_length < 1:
        max_length = 1
    if len(content) <= max_length:
        return [content]

    budget = max(1, max_length - INDICATOR_RESERVE)
    sections = _language_sections(content)
    chunks: List[str] = []
    if sections and (len(sections) > 1 or len(sections[0]) <= budget):
        for section in sections:
            chunks.extend(_pack_markdown(section, budget))
    else:
        chunks = _pack_markdown(content, budget)

    if not chunks:
        chunks = [content[:budget]] if content else [""]

    if len(chunks) == 1:
        if len(chunks[0]) <= max_length:
            return chunks
        chunks = _pack_markdown(chunks[0], budget)

    if len(chunks) > 1:
        total = len(chunks)
        # Keep the marker off fences and table rows so markdown stays valid.
        chunks = [f"{chunk}\n({i + 1}/{total})" for i, chunk in enumerate(chunks)]
    return chunks


def _language_sections(content: str) -> List[str] | None:
    """Return ordered language sections when a clean bilingual cut exists."""
    hr_parts = [part.strip("\n") for part in HR_RE.split(content)]
    hr_parts = [part for part in hr_parts if part.strip()]
    if len(hr_parts) == 2 and _distinct_language_pair(hr_parts[0], hr_parts[1]):
        return hr_parts

    blocks = _parse_blocks(content)
    if not blocks:
        return None

    labels: List[str] = []
    for start, end, kind in blocks:
        labels.append(_classify_text(content[start:end], kind))

    switch_at: int | None = None
    first_lang: str | None = None
    for index, label in enumerate(labels):
        if label in {"en", "zh"}:
            if first_lang is None:
                first_lang = label
                continue
            if label == first_lang:
                if switch_at is not None:
                    return None
                continue
            if switch_at is None:
                switch_at = index
                continue
            return None
        if label == "mixed":
            return None
        # neutrals (code/table/punctuation) may sit on either side
        continue

    if first_lang is None or switch_at is None:
        return None

    cut = blocks[switch_at][0]
    left = content[:cut].strip("\n")
    right = content[cut:].strip("\n")
    if not left.strip() or not right.strip():
        return None
    if not _distinct_language_pair(left, right):
        return None
    return [left, right]


def _distinct_language_pair(left: str, right: str) -> bool:
    left_lang = _classify_text(_prose_for_classify(left), "prose")
    right_lang = _classify_text(_prose_for_classify(right), "prose")
    return {left_lang, right_lang} == {"en", "zh"}


def _prose_for_classify(text: str) -> str:
    """Strip fenced code and GFM tables so samples do not flip language."""
    pieces: List[str] = []
    for start, end, kind in _parse_blocks(text):
        if kind in {"code", "table"}:
            continue
        pieces.append(text[start:end])
    return "\n".join(pieces) if pieces else text


def _classify_text(text: str, kind: str) -> str:
    if kind in {"code", "table"}:
        return "neutral"
    han = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    latin = sum(1 for char in text if char.isascii() and char.isalpha())
    if han == 0 and latin == 0:
        return "neutral"
    if han > 0 and latin == 0:
        return "zh"
    if latin > 0 and han == 0:
        return "en"
    if han >= latin * 2:
        return "zh"
    if latin >= han * 2:
        return "en"
    return "mixed"


def _parse_blocks(text: str) -> List[Block]:
    if not text:
        return []
    lines = text.splitlines(keepends=True)
    offsets: List[int] = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)

    blocks: List[Block] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if FENCE_LINE_RE.match(line):
            end_index = index + 1
            while end_index < len(lines) and not FENCE_LINE_RE.match(lines[end_index]):
                end_index += 1
            if end_index < len(lines):
                end_index += 1
            blocks.append(_span(offsets, lines, index, end_index, "code"))
            index = end_index
            continue
        if _is_table_start(lines, index):
            end_index = index + 2
            while end_index < len(lines) and _is_table_row(lines[end_index]):
                end_index += 1
            blocks.append(_span(offsets, lines, index, end_index, "table"))
            index = end_index
            continue
        end_index = index + 1
        while end_index < len(lines) and not _starts_special(lines, end_index):
            if lines[end_index].strip() == "" and end_index + 1 < len(lines):
                if _starts_special(lines, end_index + 1):
                    end_index += 1
                    break
            end_index += 1
        blocks.append(_span(offsets, lines, index, end_index, "prose"))
        index = end_index
    return blocks


def _span(
    offsets: Sequence[int],
    lines: Sequence[str],
    start_index: int,
    end_index: int,
    kind: str,
) -> Block:
    start = offsets[start_index]
    if end_index < len(lines):
        end = offsets[end_index]
    else:
        end = offsets[start_index] + sum(len(line) for line in lines[start_index:])
    return start, end, kind


def _starts_special(lines: Sequence[str], index: int) -> bool:
    line = lines[index]
    if FENCE_LINE_RE.match(line):
        return True
    return _is_table_start(lines, index)


def _is_table_start(lines: Sequence[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    header = lines[index]
    sep = lines[index + 1]
    return "|" in header and bool(TABLE_SEP_RE.match(sep.rstrip("\n")))


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if FENCE_LINE_RE.match(line):
        return False
    return "|" in line


def _pack_markdown(text: str, budget: int) -> List[str]:
    text = text.strip("\n")
    if not text:
        return []
    if len(text) <= budget:
        return [text]

    blocks = _parse_blocks(text)
    chunks: List[str] = []
    cursor = 0
    current_parts: List[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current_parts, current_len
        if current_parts:
            chunks.append("\n".join(part.strip("\n") for part in current_parts if part.strip("\n") or part).strip("\n"))
            current_parts = []
            current_len = 0

    for start, end, kind in blocks:
        piece = text[max(cursor, start):end]
        cursor = end
        if not piece:
            continue
        piece_stripped = piece.strip("\n")
        if not piece_stripped:
            continue
        if len(piece_stripped) > budget:
            flush()
            chunks.extend(_split_oversize(piece_stripped, kind, budget))
            continue
        extra = len(piece_stripped) if not current_parts else len(piece_stripped) + 1
        if current_parts and current_len + extra > budget:
            flush()
        current_parts.append(piece_stripped)
        current_len = len("\n".join(current_parts))

    flush()
    return [chunk for chunk in chunks if chunk]


def _split_oversize(text: str, kind: str, budget: int) -> List[str]:
    if kind == "code":
        return _split_code_block(text, budget)
    if kind == "table":
        return _split_table(text, budget)
    return _split_prose(text, budget)


def _split_code_block(text: str, budget: int) -> List[str]:
    lines = text.split("\n")
    open_fence = lines[0] if lines and FENCE_LINE_RE.match(lines[0]) else "```"
    body = list(lines[1:]) if lines and FENCE_LINE_RE.match(lines[0]) else list(lines)
    if body and FENCE_LINE_RE.match(body[-1]):
        body = body[:-1]

    chunks: List[str] = []
    current = [open_fence]
    for line in body:
        trial = "\n".join(current + [line]) + FENCE_CLOSE
        if len(trial) > budget and len(current) > 1:
            chunks.append("\n".join(current) + FENCE_CLOSE)
            current = [open_fence, line]
            if len("\n".join(current) + FENCE_CLOSE) > budget:
                chunks.extend(_hard_split("\n".join(current) + FENCE_CLOSE, budget))
                current = [open_fence]
        else:
            current.append(line)
    if len(current) > 1 or not chunks:
        final = "\n".join(current) + FENCE_CLOSE
        if len(final) > budget:
            chunks.extend(_hard_split(final, budget))
        else:
            chunks.append(final)
    return chunks


def _split_table(text: str, budget: int) -> List[str]:
    lines = text.split("\n")
    if len(lines) < 2 or not TABLE_SEP_RE.match(lines[1]):
        return _split_prose(text, budget)
    header, sep, rows = lines[0], lines[1], lines[2:]
    prefix = f"{header}\n{sep}"
    if len(prefix) > budget:
        return _hard_split(text, budget)

    chunks: List[str] = []
    current_rows: List[str] = []

    def render(selected: Sequence[str]) -> str:
        if not selected:
            return prefix
        return prefix + "\n" + "\n".join(selected)

    for row in rows:
        trial = render(current_rows + [row])
        if len(trial) > budget and current_rows:
            chunks.append(render(current_rows))
            current_rows = [row]
            if len(render(current_rows)) > budget:
                chunks.extend(_hard_split(render(current_rows), budget))
                current_rows = []
        else:
            current_rows.append(row)
    if current_rows or not chunks:
        rendered = render(current_rows)
        if len(rendered) > budget:
            chunks.extend(_hard_split(rendered, budget))
        else:
            chunks.append(rendered)
    return chunks


def _split_prose(text: str, budget: int) -> List[str]:
    remaining = text
    chunks: List[str] = []
    while remaining:
        if len(remaining) <= budget:
            chunks.append(remaining)
            break
        region = remaining[:budget]
        split_at = region.rfind("\n")
        if split_at < budget // 2:
            split_at = region.rfind(" ")
        if split_at < 1:
            split_at = budget
        candidate = remaining[:split_at]
        backtick_count = candidate.count("`") - candidate.count("\\`")
        if backtick_count % 2 == 1:
            last_bt = candidate.rfind("`")
            if last_bt > 0:
                safe = max(candidate.rfind(" ", 0, last_bt), candidate.rfind("\n", 0, last_bt))
                if safe > budget // 4:
                    split_at = safe
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    return [chunk for chunk in chunks if chunk]


def _hard_split(text: str, budget: int) -> List[str]:
    return [text[index:index + budget] for index in range(0, len(text), budget)] or [text]

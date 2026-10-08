"""Bounded memory-recall queries.

Gateway turns prepend channel context (and, on this fork, a PD One permission
bridge) to the user message before the model sees it. That wrapped text is the
wrong recall query: the bridge is authorization evidence Honcho does not need,
and a long thread blows past the embedder's token cap so semantic recall
returns nothing.

The recall query is the new user message first, then the most recent
channel/thread posts (nearest the new message first) that still fit in
``RECALL_QUERY_MAX_CHARS``. The bridge never appears. A plain message with no
channel context is unchanged until it exceeds the bound, in which case the
tail is kept — that is where a long message's actual ask lives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from agent.skill_commands import extract_user_instruction_from_skill_message

# ~1000 characters stays under a 1,500-token embedder cap even for CJK.
RECALL_QUERY_MAX_CHARS = 1000

# A partial post has to carry some of the neighboring turn, not a stray token.
_MIN_PARTIAL_POST_CHARS = 24

_NEW_MESSAGE_SPLIT = "\n\n[New message]\n"
_PD_ONE_BLOCK_RE = re.compile(
    r"\[PD One [^\]]*\][\s\S]*?(?=\n\n\[(?!PD One )|\Z)",
)
_HEADER_RE = re.compile(
    r"^\[(?:"
    r"Mattermost thread context|Slack thread context|Thread context|"
    r"Recent channel messages|Channel context|older thread context truncated"
    r")\b",
    re.IGNORECASE,
)
_POST_START_RE = re.compile(r"^\[[^\]\n]+\] ")


@dataclass(frozen=True)
class MemoryRecallInput:
    """Raw new-message text plus thread posts, separate from the model prompt.

    ``posts`` is chronological (oldest first). When the adapter set it — including
    an empty tuple — those strings are the only channel context recall may use.
    ``thread_context`` is the fallback blob (other platforms' ``channel_context``)
    and is parsed into posts after permission-bridge blocks are removed.
    """

    user_text: str
    posts: tuple[str, ...] | None = None
    thread_context: str = ""


def bound_text_tail(text: str, max_chars: int) -> str:
    """Return ``text`` unchanged when it fits; otherwise keep its tail.

    A cut that lands mid-token drops the leading partial token when a later
    space exists. CJK text has no spaces and keeps the raw tail.
    """
    if max_chars <= 0:
        return ""
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    tail = cleaned[-max_chars:]
    cut = len(cleaned) - max_chars
    if cut > 0 and not cleaned[cut - 1].isspace() and not tail[:1].isspace():
        space = tail.find(" ")
        if 0 <= space < len(tail) - 1:
            tail = tail[space + 1:]
    return tail.strip()


def _context_is_channel_backfill(context: str) -> bool:
    """True when ``context`` is gateway channel context, not an assembled recall query.

    Real wraps lead with a PD One block or a thread header. An already-built recall
    query leads with the user message, so a quoted ``[New message]`` inside a post
    must not be split again.
    """
    head = (context or "").lstrip()
    if not head:
        return False
    if head.startswith("[PD One "):
        return True
    return any(_HEADER_RE.match(line.strip()) for line in head.splitlines())


def looks_like_gateway_wrap(text: str) -> bool:
    """True when ``text`` is a gateway channel-context wrap, not a user sentence."""
    if not text:
        return False
    idx = text.rfind(_NEW_MESSAGE_SPLIT)
    if idx == -1:
        return text.startswith("[PD One ")
    return _context_is_channel_backfill(text[:idx])


def split_wrapped_gateway_text(text: str) -> tuple[str, str]:
    """Split on the last ``[New message]`` marker into ``(user_text, context)``."""
    idx = text.rfind(_NEW_MESSAGE_SPLIT)
    if idx == -1:
        return text, ""
    return text[idx + len(_NEW_MESSAGE_SPLIT):], text[:idx]


def strip_permission_blocks(text: str) -> str:
    """Drop PD One bridge / workflow blocks. Thread posts after them stay."""
    if not text or "[PD One " not in text:
        return text or ""
    return _PD_ONE_BLOCK_RE.sub("", text).strip()


def split_context_posts(context: str) -> list[str]:
    """Chronological posts from a channel-context blob, headers and bridge removed."""
    body = strip_permission_blocks(context or "").strip()
    if not body:
        return []
    lines = body.splitlines()
    if not any(_POST_START_RE.match(line) for line in lines):
        return [line.strip() for line in lines if line.strip() and not _HEADER_RE.match(line.strip())]

    posts: list[str] = []
    buf: list[str] = []

    def _flush() -> None:
        text = "\n".join(buf).strip()
        buf.clear()
        if text and not _HEADER_RE.match(text):
            posts.append(text)

    for line in lines:
        stripped = line.strip()
        if _HEADER_RE.match(stripped) or _POST_START_RE.match(line):
            _flush()
        if _HEADER_RE.match(stripped):
            continue
        buf.append(line)
    _flush()
    return posts


def _user_instruction(text: str) -> str:
    """Skill-scaffolding strip. ``""`` for a bare ``/skill`` or a non-string."""
    if not isinstance(text, str):
        return ""
    cleaned = extract_user_instruction_from_skill_message(text)
    return cleaned if isinstance(cleaned, str) else ""


def assemble_recall_query(user_text: str, posts: list[str], *, max_chars: int = RECALL_QUERY_MAX_CHARS) -> str:
    """New message first, then posts from newest to oldest, within ``max_chars``."""
    user = bound_text_tail(user_text, max_chars)
    if not user:
        return ""
    if len(user) >= max_chars:
        return user
    parts = [user]
    used = len(user)
    for post in reversed(posts):
        post = strip_permission_blocks(post).strip()
        if not post or _HEADER_RE.match(post) or post.startswith("[PD One "):
            continue
        room = max_chars - used - 1  # one newline separator
        if room < _MIN_PARTIAL_POST_CHARS and len(post) > room:
            break
        if len(post) > room:
            post = bound_text_tail(post, room)
            if len(post) < _MIN_PARTIAL_POST_CHARS:
                break
        parts.append(post)
        used += 1 + len(post)
        if used >= max_chars:
            break
    return "\n".join(parts)


def _posts_from_recall(memory_recall: MemoryRecallInput) -> list[str]:
    if memory_recall.posts is not None:
        return [post.strip() for post in memory_recall.posts if isinstance(post, str) and post.strip()]
    if memory_recall.thread_context:
        return split_context_posts(memory_recall.thread_context)
    return []


def prepare_memory_recall_query(
    query: str,
    memory_recall: MemoryRecallInput | None = None,
    *,
    max_chars: int = RECALL_QUERY_MAX_CHARS,
) -> str:
    """Recall text for prefetch / queue_prefetch.

    Structured ``memory_recall`` wins. Otherwise a gateway wrap is split on the
    last ``[New message]`` marker. A plain message is only tail-capped.
    """
    if memory_recall is not None:
        return assemble_recall_query(
            _user_instruction(memory_recall.user_text),
            _posts_from_recall(memory_recall),
            max_chars=max_chars,
        )
    if not isinstance(query, str) or not query:
        return ""
    if looks_like_gateway_wrap(query):
        user_raw, context = split_wrapped_gateway_text(query)
        if not context and query.startswith("[PD One "):
            # A bridge block with no new-message marker is authorization evidence, not a query.
            user_raw = strip_permission_blocks(user_raw)
        return assemble_recall_query(
            _user_instruction(user_raw), split_context_posts(context), max_chars=max_chars,
        )
    return bound_text_tail(_user_instruction(query), max_chars)


def recall_gate_text(query: str, memory_recall: MemoryRecallInput | None = None) -> str:
    """Text the trivial-prompt gate sees: the new user message, not the backfill."""
    if memory_recall is not None:
        return _user_instruction(memory_recall.user_text).strip()
    if isinstance(query, str) and looks_like_gateway_wrap(query):
        user_raw, _context = split_wrapped_gateway_text(query)
        return _user_instruction(user_raw).strip()
    if not isinstance(query, str):
        return ""
    return _user_instruction(query).strip()


def bound_embedding_query(query: str, *, max_chars: int = RECALL_QUERY_MAX_CHARS) -> str:
    """Tail-preserving cap for Honcho embedding queries (search / peer.context)."""
    if not isinstance(query, str):
        return ""
    if looks_like_gateway_wrap(query):
        return prepare_memory_recall_query(query, max_chars=max_chars)
    return bound_text_tail(query.strip(), max_chars)


def bound_dialectic_input(query: str, max_chars: int) -> str:
    """Dialectic input cap. Gateway wraps become a recall query; other text keeps its tail."""
    if not isinstance(query, str):
        return ""
    if looks_like_gateway_wrap(query):
        return prepare_memory_recall_query(query, max_chars=min(max_chars, RECALL_QUERY_MAX_CHARS))
    return bound_text_tail(query.strip(), max_chars)


def recall_input_for_event(event: object) -> MemoryRecallInput | None:
    """Build recall input from a gateway event after inbound text is prepared.

    No channel context and no adapter-supplied posts means the caller should
    fall back to the ordinary user text (CLI, DMs without backfill).
    """
    channel_context = getattr(event, "channel_context", None)
    posts = getattr(event, "recall_posts", None)
    if not channel_context and posts is None:
        return None
    user_text = getattr(event, "_memory_recall_user_text", None)
    if not isinstance(user_text, str):
        user_text = getattr(event, "text", None) or ""
    if posts is not None:
        return MemoryRecallInput(user_text=user_text, posts=tuple(posts))
    return MemoryRecallInput(user_text=user_text, thread_context=str(channel_context or ""))

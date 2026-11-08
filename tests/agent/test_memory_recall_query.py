"""Recall queries stay small and never include the permission bridge.

The model prompt and session history keep the wrapped gateway text. Memory
prefetch and queue_prefetch see the new message plus the newest thread posts
that fit in the recall bound.
"""

from types import SimpleNamespace

from agent.memory_manager import MemoryManager
from agent.memory_provider import MemoryProvider
from agent.memory_recall_query import (
    RECALL_QUERY_MAX_CHARS,
    MemoryRecallInput,
    prepare_memory_recall_query,
    recall_input_for_event,
)
from agent.skill_commands import extract_user_instruction_from_skill_message


_BRIDGE = (
    "[PD One Hermes permission bridge]\n"
    "Authorize by exact sender id only. Policy JSON (compact): "
    '{"found":true,"decision":"allow","roles":["employee"]}'
)
_WORKFLOW = (
    "[PD One outbound DM workflow]\n"
    "Active outbound DM workflow selected by deterministic router.\n"
    'Workflow JSON: {"id":"wf-1"}'
)
_POSTS = [
    "[user-old] please review ticket T18 and say whether it must be collected",
    "[user-mid] the form is missing a signature from the requester",
    "[user-new] do we still need to collect T18 or can it stay unclaimed",
]
_NEW = "T18-未領取具無須收回"
_THREAD = (
    "[Mattermost thread context: root=abc123]\n"
    + "\n".join(_POSTS)
)


def _wrapped(*, posts=None, include_workflow=True) -> str:
    thread = _THREAD if posts is None else "[Mattermost thread context: root=abc123]\n" + "\n".join(posts)
    parts = [_BRIDGE]
    if include_workflow:
        parts.append(_WORKFLOW)
    parts.append(thread)
    return "\n\n".join(parts) + f"\n\n[New message]\n{_NEW}"


class _RecordingProvider(MemoryProvider):
    _name = "recording"

    def __init__(self):
        self.prefetched = []
        self.queued = []
        self.synced = []

    @property
    def name(self) -> str:
        return self._name

    def initialize(self, session_id: str = "", **kwargs) -> None:
        pass

    def is_available(self) -> bool:
        return True

    def system_prompt_block(self) -> str:
        return ""

    def prefetch(self, query, *, session_id: str = "") -> str:
        self.prefetched.append(query)
        return ""

    def queue_prefetch(self, query, *, session_id: str = "") -> None:
        self.queued.append(query)

    def sync_turn(self, user_content, assistant_content, *, session_id: str = "", messages=None) -> None:
        self.synced.append(user_content)

    def get_tool_schemas(self):
        return []


def _manager():
    mgr = MemoryManager()
    provider = _RecordingProvider()
    mgr.add_provider(provider)
    return mgr, provider


def test_structured_recall_is_new_message_then_nearest_posts_without_bridge():
    query = prepare_memory_recall_query(
        _wrapped(),
        MemoryRecallInput(user_text=_NEW, posts=tuple(_POSTS)),
    )

    assert query.startswith(_NEW + "\n")
    assert "permission bridge" not in query
    assert "Workflow JSON" not in query
    assert "PD One" not in query
    # Nearest post (last in the thread) comes first; the oldest is last.
    assert query.index("[user-new]") < query.index("[user-mid]") < query.index("[user-old]")
    assert len(query) <= RECALL_QUERY_MAX_CHARS


def test_wrapped_text_fallback_parses_after_last_new_message_marker():
    older = "quoted\n\n[New message]\nthis is inside an older post, not the trigger"
    posts = _POSTS + [f"[user-quote] {older}"]
    wrapped = _wrapped(posts=posts)
    query = prepare_memory_recall_query(wrapped)

    assert query.startswith(_NEW)
    assert "permission bridge" not in query
    assert "this is inside an older post" not in query.split("\n", 1)[0]
    assert "[user-new]" in query
    assert len(query) <= RECALL_QUERY_MAX_CHARS


def test_bridge_only_context_recalls_the_new_message():
    event = SimpleNamespace(
        text=_NEW,
        channel_context=_BRIDGE,
        recall_posts=[],
        _memory_recall_user_text=_NEW,
    )
    query = prepare_memory_recall_query(_BRIDGE + f"\n\n[New message]\n{_NEW}", recall_input_for_event(event))

    assert query == _NEW
    assert "permission bridge" not in query


def test_thread_context_blob_without_explicit_posts_drops_the_bridge():
    event = SimpleNamespace(
        text=_NEW,
        channel_context=f"{_BRIDGE}\n\n{_THREAD}",
        recall_posts=None,
        _memory_recall_user_text=_NEW,
    )
    query = prepare_memory_recall_query("ignored", recall_input_for_event(event))

    assert query.startswith(_NEW + "\n[user-new]")
    assert "permission bridge" not in query
    assert "[Mattermost thread context" not in query


def test_long_plain_message_keeps_the_tail():
    body = "HEAD-ONLY " + ("middle " * 400) + "TAIL-ASK"
    query = prepare_memory_recall_query(body)

    assert query.endswith("TAIL-ASK")
    assert "HEAD-ONLY" not in query
    assert len(query) <= RECALL_QUERY_MAX_CHARS


def test_new_message_longer_than_the_bound_keeps_its_tail_and_drops_posts():
    message = ("甲" * (RECALL_QUERY_MAX_CHARS + 50)) + "結尾"
    query = prepare_memory_recall_query(
        "ignored",
        MemoryRecallInput(user_text=message, posts=tuple(_POSTS)),
    )

    assert query.endswith("結尾")
    assert "[user-new]" not in query
    assert len(query) <= RECALL_QUERY_MAX_CHARS


def test_assembled_query_stays_stable_when_a_post_quotes_the_marker():
    """Preparing twice must not split a quoted ``[New message]`` inside a thread post."""
    quoted = "[Ada] see the note\n\n[New message]\nthis was quoted, not the trigger"
    recall = MemoryRecallInput(user_text="[Ada] " + _NEW, posts=(_POSTS[-1], quoted))
    once = prepare_memory_recall_query("ignored", recall)
    twice = prepare_memory_recall_query(once)

    assert once.startswith("[Ada] " + _NEW)
    assert twice == once
    assert "permission bridge" not in once


def test_short_message_without_context_is_unchanged():
    text = "what did we decide about the deploy pipeline?"
    assert prepare_memory_recall_query(text) == text
    assert recall_input_for_event(SimpleNamespace(text=text, channel_context=None, recall_posts=None)) is None


def test_providers_receive_bounded_query_and_sync_keeps_the_wrap():
    wrapped = _wrapped()
    mgr, provider = _manager()
    recall = MemoryRecallInput(user_text=_NEW, posts=tuple(_POSTS))
    bounded = prepare_memory_recall_query(wrapped, recall)

    assert mgr.prefetch_all(bounded) == ""
    mgr.sync_all(wrapped, "reply kept in history")
    mgr.queue_prefetch_all(bounded)
    mgr.flush_pending(timeout=5)

    assert provider.prefetched == [bounded]
    assert provider.queued == [bounded]
    assert provider.synced == [wrapped]
    assert "permission bridge" not in provider.prefetched[0]
    assert len(provider.prefetched[0]) <= RECALL_QUERY_MAX_CHARS


def test_prefetch_of_wrapped_text_without_structured_input_still_drops_the_bridge():
    mgr, provider = _manager()
    mgr.prefetch_all(_wrapped())

    assert provider.prefetched
    assert provider.prefetched[0].startswith(_NEW)
    assert "permission bridge" not in provider.prefetched[0]
    assert "Workflow JSON" not in provider.prefetched[0]


def test_end_of_turn_sync_keeps_the_wrap_and_queues_the_recall_query():
    from run_agent import AIAgent

    wrapped = _wrapped()
    recall = MemoryRecallInput(user_text=_NEW, posts=tuple(_POSTS))
    agent = AIAgent.__new__(AIAgent)
    agent._memory_manager = MemoryManager()
    provider = _RecordingProvider()
    agent._memory_manager.add_provider(provider)
    agent.session_id = "sess"
    agent._turn_author = None
    agent._memory_recall = recall

    agent._sync_external_memory_for_turn(
        original_user_message=wrapped, final_response="noted", interrupted=False,
    )
    agent._memory_manager.flush_pending(timeout=5)

    assert provider.synced == [wrapped]
    assert provider.queued
    assert provider.queued[0].startswith(_NEW)
    assert "permission bridge" not in provider.queued[0]
    assert len(provider.queued[0]) <= RECALL_QUERY_MAX_CHARS


def test_skill_scaffolding_strip_still_runs_before_the_bound():
    bare = (
        '[IMPORTANT: The user has invoked the "skill-creator" skill, indicating they want '
        "you to follow its instructions. The full skill content is loaded below.]\n\n"
        "# Skill Creator\n\n"
        "Large skill body, no user instruction."
    )
    bundle = (
        '[IMPORTANT: The user has invoked the "backend-dev" skill bundle, '
        "loading 2 skills together. Treat every skill below as active guidance for this turn.]\n\n"
        "Bundle: backend-dev\n"
        "Skills loaded: test-driven-development, code-review\n\n"
        "User instruction: fix the failing retrieval test\n\n"
        '[Loaded as part of the "backend-dev" skill bundle.]\n\n'
        "Large bundled skill body that must not be searched or embedded."
    )
    assert extract_user_instruction_from_skill_message(bundle) == "fix the failing retrieval test"

    mgr, provider = _manager()
    assert mgr.prefetch_all(bare) == ""
    assert provider.prefetched == []
    mgr.queue_prefetch_all(bundle)
    mgr.flush_pending(timeout=5)
    assert provider.queued == ["fix the failing retrieval test"]
    mgr.sync_all(bare, "Done.")
    mgr.flush_pending(timeout=5)
    assert provider.synced == []

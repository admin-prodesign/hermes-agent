"""Honcho search and dialectic keep the tail of an oversized query.

A gateway wrap puts the new message at the end. Head-truncation dropped it
and could still embed the permission bridge. Both paths tail-preserve, and a
wrap is reduced to the recall query before it reaches the embedder or peer.chat.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from plugins.memory.honcho.session import HonchoSession, HonchoSessionManager
from plugins.memory.honcho.session_context import _bounded_embedding_query


_NEW = "T18-未領取具無須收回"


def _wrapped() -> str:
    bridge = (
        "[PD One Hermes permission bridge]\n"
        "Authorize by exact sender id only.\n"
        'Policy JSON (compact): {"found":true}'
    )
    posts = "\n".join(
        f"[user-{i}] earlier post {i} " + ("pad " * 30) for i in range(20)
    )
    thread = f"[Mattermost thread context: root=abc]\n{posts}"
    return f"{bridge}\n\n{thread}\n\n[New message]\n{_NEW}"


def test_embedding_query_drops_bridge_and_keeps_the_new_message():
    query = _bounded_embedding_query(_wrapped())

    assert query.startswith(_NEW)
    assert "permission bridge" not in query
    assert "Policy JSON" not in query
    assert len(query) <= 1000


def test_plain_embedding_query_keeps_the_tail():
    query = _bounded_embedding_query("HEAD " + ("x" * 2000) + " TAIL")

    assert query.endswith("TAIL")
    assert not query.startswith("HEAD")
    assert len(query) <= 1000


def test_search_context_sends_the_bounded_tail():
    session = HonchoSession(key="k", user_peer_id="u", assistant_peer_id="a", honcho_session_id="s")
    mgr = HonchoSessionManager()
    mgr._cache[session.key] = session
    honcho_client = MagicMock()
    honcho_client.search.return_value = []
    with patch.object(HonchoSessionManager, "honcho", new_callable=lambda: property(lambda _s: honcho_client)):
        mgr.search_context(session.key, "HEAD " + ("mid " * 500) + "UNIQUE_TAIL")

    sent = honcho_client.search.call_args.args[0]
    assert sent.endswith("UNIQUE_TAIL")
    assert not sent.startswith("HEAD")
    assert len(sent) <= 1000


def test_dialectic_keeps_the_tail_of_a_long_plain_question():
    from plugins.memory.honcho.client import HonchoClientConfig

    cfg = HonchoClientConfig(dialectic_max_input_chars=80)
    mgr = HonchoSessionManager(config=cfg)
    mgr._dialectic_max_input_chars = 80
    session = HonchoSession(key="test", user_peer_id="u", assistant_peer_id="a", honcho_session_id="s")
    mgr._cache["test"] = session
    mock_peer = MagicMock()
    mock_peer.chat.return_value = "answer"
    mgr._get_or_create_peer = MagicMock(return_value=mock_peer)

    mgr.dialectic_query("test", ("HEAD " * 40) + ("TAIL " * 40))

    actual = mock_peer.chat.call_args.args[0]
    assert len(actual) <= 80
    assert "TAIL" in actual
    assert "HEAD" not in actual


def test_dialectic_wrapped_gateway_text_drops_the_bridge():
    from plugins.memory.honcho.client import HonchoClientConfig

    cfg = HonchoClientConfig(dialectic_max_input_chars=10000)
    mgr = HonchoSessionManager(config=cfg)
    mgr._dialectic_max_input_chars = 10000
    session = HonchoSession(key="test", user_peer_id="u", assistant_peer_id="a", honcho_session_id="s")
    mgr._cache["test"] = session
    mock_peer = MagicMock()
    mock_peer.chat.return_value = "answer"
    mgr._get_or_create_peer = MagicMock(return_value=mock_peer)

    mgr.dialectic_query("test", _wrapped())

    actual = mock_peer.chat.call_args.args[0]
    assert actual.startswith(_NEW)
    assert "permission bridge" not in actual
    assert len(actual) <= 1000


def test_prefetch_search_query_is_bounded():
    session = HonchoSession(key="k", user_peer_id="u", assistant_peer_id="a", honcho_session_id="s")
    mgr = HonchoSessionManager()
    mgr._cache[session.key] = session
    calls = []

    class _Peer:
        def context(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(representation="rep", peer_card=["card"])

    mgr._get_or_create_peer = MagicMock(return_value=_Peer())
    mgr._authed_call = lambda _label, fn: fn()

    mgr.get_prefetch_context(session.key, _wrapped())

    searched = [call["search_query"] for call in calls if call.get("search_query")]
    assert searched
    assert searched[0].startswith(_NEW)
    assert "permission bridge" not in searched[0]
    assert len(searched[0]) <= 1000

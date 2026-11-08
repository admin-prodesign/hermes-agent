"""Inbound wrap still feeds the model the bridge; recall input stays separate."""

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.event import MessageEvent
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from agent.memory_recall_query import recall_input_for_event


def _runner() -> GatewayRunner:
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.MATTERMOST: PlatformConfig(enabled=True, token="fake")},
    )
    runner.adapters = {}
    runner._model = "openai/gpt-4.1-mini"
    runner._base_url = None
    return runner


@pytest.mark.asyncio
async def test_channel_wrap_keeps_the_bridge_and_records_the_raw_message():
    runner = _runner()
    source = SessionSource(
        platform=Platform.MATTERMOST,
        chat_id="ch",
        chat_type="dm",
        user_id="u1",
        user_name="Ada",
    )
    bridge = "[PD One Hermes permission bridge]\nAuthorize by exact sender id only."
    thread = "[Mattermost thread context: root=abc]\n[user-new] nearest post"
    event = MessageEvent(
        text="T18-未領取具無須收回",
        source=source,
        channel_context=f"{bridge}\n\n{thread}",
        recall_posts=["[user-new] nearest post"],
    )

    result = await runner._prepare_inbound_message_text(event=event, source=source, history=[])

    assert result.startswith(bridge)
    assert "\n\n[New message]\nT18-未領取具無須收回" in result
    assert event._memory_recall_user_text == "T18-未領取具無須收回"
    recall = recall_input_for_event(event)
    assert recall is not None
    assert recall.user_text == "T18-未領取具無須收回"
    assert recall.posts == ("[user-new] nearest post",)
    assert "permission bridge" not in "\n".join(recall.posts)

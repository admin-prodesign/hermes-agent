"""Adapter-split memory-recall posts survive native admission.

Contract: a Mattermost thread reply's ``recall_posts`` (thread posts without the permission
bridge) reach the turn after the input is committed and replayed from the admission ledger.
Dropping them would make recall fall back to splitting ``channel_context``, which carries
authorization evidence.
"""
import json

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import SendResult
from gateway.run import GatewayRunner
from gateway.session_authority import initialize_session_authority
from gateway.session_results import execution_result
from tests.waiting import async_wait_until

SENDER = 'user_123'
THREAD_POSTS = ['[alice] first thread post', '[bob] second thread post']


@pytest.mark.asyncio
async def test_mattermost_thread_recall_posts_reach_the_turn(tmp_path, monkeypatch):
    from plugins.platforms.mattermost.adapter import MattermostAdapter
    monkeypatch.setenv('MATTERMOST_ALLOWED_USERS', SENDER)
    runner = GatewayRunner(GatewayConfig(sessions_dir=tmp_path / 'sessions'))
    adapter = MattermostAdapter(PlatformConfig(enabled=True, token='test-token',
                                               extra={'url': 'https://mm.example.com'}))
    adapter._bot_user_id, adapter._bot_username = 'bot_user_id', 'hermes-bot'
    adapter.gateway_runner, runner.adapters = runner, {Platform.MATTERMOST: adapter}
    authority = await initialize_session_authority(runner, profile_id='default', instance_id='mm')
    runner._wire_adapter_handlers(adapter)
    sent, turns = [], []

    async def download_attachments(file_ids):
        return [], []

    async def fetch_thread_context(root_id, triggering_post_id, session_key=None):
        return '[Thread context]\n' + '\n'.join(THREAD_POSTS), [], list(THREAD_POSTS)

    async def send(chat_id, content, **_):
        sent.append(content)
        return SendResult(success=True, message_id='s')

    async def turn(event, *_args, **_kwargs):
        turns.append(event.recall_posts)
        execution_result.get()['result'] = {'final_response': 'ok', 'messages': []}
        return 'ok'

    monkeypatch.setattr(adapter, '_download_attachments', download_attachments)
    monkeypatch.setattr(adapter, '_fetch_thread_context', fetch_thread_context)
    monkeypatch.setattr(adapter, 'send', send)
    monkeypatch.setattr(runner, '_handle_message_with_agent', turn)
    post = {'id': 'reply1', 'root_id': 'root1', 'user_id': SENDER, 'channel_id': 'dm_chan',
            'message': 'what did we decide?', 'file_ids': []}
    try:
        await adapter._handle_ws_event({'event': 'posted', 'data': {
            'post': json.dumps(post), 'channel_type': 'D', 'sender_name': '@alice'}})
        await async_wait_until(lambda: len(sent) >= 1, timeout=20, what='reply to a thread post')
        assert turns == [THREAD_POSTS], turns
    finally:
        authority.db.close()

"""Route ``post_script`` runs after the response; it never enters the durable destination."""
import hashlib
import hmac
import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from gateway.config import PlatformConfig
from gateway.platforms.webhook import WebhookAdapter, _WebhookDeliveryIdentity
from tests.gateway.fixtures.webhook_route_authority import mount_authority


async def _admit(route: dict, delivery_id: str, payload: dict):
    config = PlatformConfig(enabled=True, extra={'secret': 'owned-secret', 'routes': {'fixture': route}})
    adapter = WebhookAdapter(config)
    app = web.Application()
    mount_authority(app, adapter)
    app.router.add_post('/webhooks/{route_name}', adapter._handle_webhook)
    client = TestClient(TestServer(app))
    await client.start_server()
    body = json.dumps(payload).encode()
    headers = {'X-GitHub-Delivery': delivery_id, 'X-Hub-Signature-256':
               'sha256=' + hmac.new(b'owned-secret', body, hashlib.sha256).hexdigest()}
    response = await client.post('/webhooks/fixture', data=body, headers=headers)
    assert response.status == 202, await response.text()
    calls = []
    adapter._route_processor.run_post_script = lambda script, envelope: calls.append((script, envelope))
    chat_id = _WebhookDeliveryIdentity.from_parts(None, 'fixture', delivery_id).session_chat_id
    return client, adapter, chat_id, calls


@pytest.mark.asyncio
async def test_log_route_runs_post_script_with_payload_and_response():
    client, adapter, chat_id, calls = await _admit(
        {'prompt': '{text}', 'deliver': 'log', 'post_script': 'notify.py'}, 'post-one', {'text': 'hello'})
    try:
        runner = adapter._message_handler.__self__
        row = runner.session_authority.db._read_one('SELECT payload_json FROM session_admissions')
        retained = json.loads(row['payload_json'])['native_text_v1']['webhook_delivery']
        assert retained == {'deliver': 'log', 'deliver_extra': {}}

        assert (await adapter.send(chat_id, 'completed answer')).success
        assert calls == [('notify.py', {'payload': {'text': 'hello'}, 'response': 'completed answer',
                                        'route': 'fixture', 'chat_id': chat_id})]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_route_without_post_script_runs_nothing():
    client, adapter, chat_id, calls = await _admit(
        {'prompt': '{text}', 'deliver': 'log'}, 'post-two', {'text': 'hello'})
    try:
        assert (await adapter.send(chat_id, 'completed answer')).success
        assert calls == []
    finally:
        await client.close()

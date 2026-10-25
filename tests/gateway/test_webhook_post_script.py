"""Route ``post_script`` runs once the agent's response is delivered.

Contract: a route with ``post_script`` is admitted (its process-only inputs are not part of the
retained destination) and, on ``log`` delivery, the script receives the payload/response
envelope on stdin.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from gateway.config import PlatformConfig
from gateway.platforms.webhook import WebhookAdapter, _WebhookDeliveryIdentity
from tests.gateway.fixtures.webhook_route_authority import mount_authority

RECORDER = """import json, os, pathlib, sys
pathlib.Path(os.environ['HERMES_HOME'], 'post_script.json').write_text(sys.stdin.read())
"""


@pytest.mark.asyncio
async def test_post_script_route_is_admitted_and_runs_after_log_delivery():
    home = Path(os.environ['HERMES_HOME'])
    (home / 'scripts').mkdir(parents=True, exist_ok=True)
    (home / 'scripts' / 'record.py').write_text(RECORDER)
    config = PlatformConfig(enabled=True, extra={'secret': 'owned-secret', 'routes': {
        'fixture': {'prompt': '{text}', 'deliver': 'log', 'post_script': 'record.py'}}})
    adapter = WebhookAdapter(config)
    app = web.Application()
    mount_authority(app, adapter)
    app.router.add_post('/webhooks/{route_name}', adapter._handle_webhook)
    async with TestClient(TestServer(app)) as client:
        body = json.dumps({'text': 'hello', 'ticket': 42}).encode()
        headers = {'X-GitHub-Delivery': 'post-script-one', 'X-Hub-Signature-256':
                   'sha256=' + hmac.new(b'owned-secret', body, hashlib.sha256).hexdigest()}
        response = await client.post('/webhooks/fixture', data=body, headers=headers)
        assert response.status == 202, await response.text()
        runner = adapter._message_handler.__self__
        row = runner.session_authority.db._read_one('SELECT payload_json FROM session_admissions')
        assert json.loads(row['payload_json'])['native_text_v1']['webhook_delivery'] == {
            'deliver': 'log', 'deliver_extra': {}}
        chat_id = _WebhookDeliveryIdentity.from_parts(None, 'fixture', 'post-script-one').session_chat_id
        assert (await adapter.send(chat_id, 'completed answer')).success
    envelope = json.loads((home / 'post_script.json').read_text())
    assert envelope == {'payload': {'text': 'hello', 'ticket': 42}, 'response': 'completed answer',
                        'route': 'fixture', 'chat_id': chat_id}

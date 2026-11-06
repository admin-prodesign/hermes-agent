"""Unit tests for mattermost-channel-create (mocked HTTP)."""
from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

import pytest

from tools.pd_one_ops.pd_one_safe_ops_part0 import MATTERMOST_CHANNEL_CREATE_CONFIRMATION
from tools.pd_one_ops.pd_one_safe_ops_part2 import cmd_mattermost_channel_create


@pytest.fixture
def captured_emit(monkeypatch):
    """Capture emit() JSON payloads instead of printing."""
    out: list[dict] = []

    def _capture(data):
        out.append(data)

    monkeypatch.setattr('tools.pd_one_ops.pd_one_safe_ops_part2.emit', _capture)
    return out


def test_channel_create_dry_run_no_writes(captured_emit):
    base = 'https://mm.example'
    headers = {'Authorization': 'Bearer test'}
    me = {'id': 'u_bot', 'username': 'bot'}

    def mm_req(method, b, h, path, **kwargs):
        assert b == base
        assert method != 'POST', 'dry_run must not POST'
        if path == '/api/v4/teams/name/acme':
            return {'id': 'team1', 'name': 'acme'}
        if path == '/api/v4/users/username/alice':
            return {'id': 'u_alice', 'username': 'alice', 'delete_at': 0}
        raise AssertionError(f'unexpected {method} {path}')

    with patch('tools.pd_one_ops.pd_one_safe_ops_part2.mattermost_context', return_value=(base, headers, me)), patch('tools.pd_one_ops.pd_one_safe_ops_part2.mm_request', side_effect=mm_req):
        cmd_mattermost_channel_create(Namespace(team_name='acme', channel_name='proj-channel', display_name='Project Alpha', purpose='coord', member_username=['alice'], action='dry_run', confirm_live_write=None))
    assert len(captured_emit) == 1
    payload = captured_emit[0]
    assert payload['status'] == 'ok'
    assert payload['action'] == 'dry_run'
    assert payload['safety']['shell_used'] is False
    assert payload['safety']['live_write'] is False
    plan = payload['create_plan']
    assert plan['create_body']['type'] == 'P'
    assert plan['member_add_plan'] == [{'user_id': 'u_alice', 'username': 'alice'}]


def test_channel_create_apply_refused_without_confirm(captured_emit):
    base = 'https://mm.example'
    headers = {'Authorization': 'Bearer test'}
    me = {'id': 'u_bot', 'username': 'bot'}

    def mm_req(method, b, h, path, **kwargs):
        if path == '/api/v4/teams/name/acme':
            return {'id': 'team1', 'name': 'acme'}
        if path == '/api/v4/users/username/alice':
            return {'id': 'u_alice', 'username': 'alice', 'delete_at': 0}
        raise AssertionError(f'unexpected {method} {path}')

    with patch('tools.pd_one_ops.pd_one_safe_ops_part2.mattermost_context', return_value=(base, headers, me)), patch('tools.pd_one_ops.pd_one_safe_ops_part2.mm_request', side_effect=mm_req):
        with pytest.raises(SystemExit) as exc:
            cmd_mattermost_channel_create(Namespace(team_name='acme', channel_name='proj-channel', display_name='Project Alpha', purpose='coord', member_username=['alice'], action='apply', confirm_live_write='wrong'))
    assert exc.value.code == 2
    assert captured_emit == []


def test_channel_create_apply_readback(captured_emit):
    base = 'https://mm.example'
    headers = {'Authorization': 'Bearer test'}
    me = {'id': 'u_bot', 'username': 'bot'}
    calls: list[tuple] = []

    def mm_req(method, b, h, path, **kwargs):
        calls.append((method, path))
        if path == '/api/v4/teams/name/acme':
            return {'id': 'team1', 'name': 'acme'}
        if path == '/api/v4/users/username/alice':
            return {'id': 'u_alice', 'username': 'alice', 'delete_at': 0}
        if method == 'POST' and path == '/api/v4/channels':
            return {'id': 'ch_new', 'name': 'proj-channel', 'display_name': 'Project Alpha', 'purpose': 'coord', 'type': 'P', 'team_id': 'team1'}
        if method == 'POST' and path == '/api/v4/channels/ch_new/members':
            return {}
        if method == 'GET' and path == '/api/v4/channels/ch_new':
            return {'id': 'ch_new', 'name': 'proj-channel', 'display_name': 'Project Alpha', 'purpose': 'coord', 'type': 'P', 'team_id': 'team1'}
        raise AssertionError(f'unexpected {method} {path}')

    def fake_fetch_members(b, h, cid):
        assert cid == 'ch_new'
        return [{'user_id': 'u_alice'}]

    def fake_users_by_id(b, h, ids):
        return {'u_alice': {'id': 'u_alice', 'username': 'alice'}}

    with patch('tools.pd_one_ops.pd_one_safe_ops_part2.mattermost_context', return_value=(base, headers, me)), patch('tools.pd_one_ops.pd_one_safe_ops_part2.mm_request', side_effect=mm_req), patch('tools.pd_one_ops.pd_one_safe_ops_part2.fetch_channel_members', side_effect=fake_fetch_members), patch('tools.pd_one_ops.pd_one_safe_ops_part2.mm_users_by_id', side_effect=fake_users_by_id):
        cmd_mattermost_channel_create(Namespace(team_name='acme', channel_name='proj-channel', display_name='Project Alpha', purpose='coord', member_username=['alice'], action='apply', confirm_live_write=MATTERMOST_CHANNEL_CREATE_CONFIRMATION))
    assert len(captured_emit) == 1
    payload = captured_emit[0]
    assert payload['apply_status'] == 'applied'
    assert payload['channel_readback']['id'] == 'ch_new'
    assert payload['channel_readback']['display_name'] == 'Project Alpha'
    assert payload['membership_readback']['added_usernames'] == ['alice']
    assert payload['membership_readback']['member_count_observed'] == 1
    assert any((c[0] == 'POST' and c[1] == '/api/v4/channels' for c in calls))

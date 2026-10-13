"""Mattermost replaces private HR text unless every destination human is HR or admin."""
import json
import logging
from pathlib import Path

import pytest
from unittest.mock import AsyncMock

from gateway.config import PlatformConfig
from tools.pd_one_hr_fields import HR_PRIVATE_WITHHELD_NOTICE, filter_private_hr_text

REPO = Path(__file__).resolve().parents[2]
LEAK = "Placeholder Person confirmed. 職等代碼: G0-PLACEHOLDER. passport: P-PLACEHOLDER."


def _write_policies(cache: Path) -> None:
    for user_id, roles in (
        ("user-hr-1", ["hr"]),
        ("user-admin-3", ["admin"]),
        ("user-staff-2", ["employee"]),
    ):
        (cache / f"{user_id}.json").write_text(
            json.dumps({"found": True, "active": True, "roles": roles}),
            encoding="utf-8",
        )


def _adapter(cache: Path):
    from plugins.platforms.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter(PlatformConfig(
        enabled=True,
        token="test-token",
        extra={
            "url": "https://mm.example.com",
            "pd_one_policy_cache_users": str(cache),
        },
    ))
    adapter._bot_user_id = "bot-placeholder"
    return adapter


def _members(*user_ids: str) -> list[dict]:
    return [{"user_id": user_id} for user_id in ("bot-placeholder", *user_ids)]


CASES = [
    ("channel-mixed", "O", _members("user-hr-1", "user-staff-2"), False),
    ("channel-hr", "O", _members("user-hr-1", "user-admin-3"), True),
    ("dm-hr", "D", _members("user-hr-1"), True),
    ("dm-staff", "D", _members("user-staff-2"), False),
]


def _install_get(adapter, channel_type: str, members: list[dict]):
    async def _get(path: str):
        if path.endswith("/members"):
            return members
        return {"id": path.split("/")[1], "type": channel_type}

    adapter._api_get = _get


@pytest.mark.asyncio
@pytest.mark.parametrize(("chat_id", "channel_type", "members", "hr_only"), CASES)
async def test_send_filters_private_markers_by_destination(tmp_path, caplog, chat_id, channel_type, members, hr_only):
    _write_policies(tmp_path)
    adapter = _adapter(tmp_path)
    _install_get(adapter, channel_type, members)
    adapter._api_post = AsyncMock(return_value={"id": "post-placeholder"})

    with caplog.at_level(logging.WARNING):
        result = await adapter.send(chat_id, LEAK)

    assert result.success is True
    posted = adapter._api_post.call_args[0][1]["message"]
    if hr_only:
        assert posted == LEAK
        assert "withheld private HR fields" not in caplog.text
    else:
        assert posted == HR_PRIVATE_WITHHELD_NOTICE
        assert "G0-PLACEHOLDER" not in posted
        assert "P-PLACEHOLDER" not in posted
        assert "withheld private HR fields" in caplog.text
        assert "G0-PLACEHOLDER" not in caplog.text
        assert "P-PLACEHOLDER" not in caplog.text
        assert LEAK not in caplog.text


@pytest.mark.asyncio
async def test_edit_message_mixed_channel_replaces_the_whole_message(tmp_path):
    _write_policies(tmp_path)
    adapter = _adapter(tmp_path)
    _install_get(adapter, "O", _members("user-hr-1", "user-staff-2"))
    adapter._api = AsyncMock(return_value={"id": "edit-placeholder"})

    result = await adapter.edit_message("channel-mixed", "post-1", LEAK)

    assert result.success is True
    payload = adapter._api.call_args[0][2]
    assert payload["message"] == HR_PRIVATE_WITHHELD_NOTICE
    assert "G0-PLACEHOLDER" not in payload["message"]


@pytest.mark.asyncio
async def test_edit_message_hr_dm_keeps_private_text(tmp_path):
    _write_policies(tmp_path)
    adapter = _adapter(tmp_path)
    _install_get(adapter, "D", _members("user-hr-1"))
    adapter._api = AsyncMock(return_value={"id": "edit-placeholder"})

    result = await adapter.edit_message("dm-hr", "post-1", LEAK)

    assert result.success is True
    assert adapter._api.call_args[0][2]["message"] == LEAK


@pytest.mark.asyncio
@pytest.mark.parametrize(("chat_id", "members", "hr_only"), [
    ("channel-mixed", ["user-hr-1", "user-staff-2"], False),
    ("channel-hr", ["user-hr-1", "user-admin-3"], True),
    ("dm-hr", ["user-hr-1"], True),
    ("dm-staff", ["user-staff-2"], False),
])
async def test_standalone_send_filters_private_markers(monkeypatch, tmp_path, chat_id, members, hr_only):
    from plugins.platforms.mattermost import adapter as mm

    _write_policies(tmp_path)
    state = {"posts": [], "members": ["bot-placeholder", *members]}

    class _Resp:
        def __init__(self, payload, status=200):
            self.status = status
            self._payload = payload

        async def json(self):
            return self._payload

        async def text(self):
            return ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    class _Session:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def get(self, url, **_kwargs):
            if url.endswith("/users/me"):
                return _Resp({"id": "bot-placeholder"})
            if url.endswith("/members"):
                return _Resp([{"user_id": user_id} for user_id in state["members"]])
            return _Resp({"id": chat_id, "type": "D" if chat_id.startswith("dm-") else "O"})

        def post(self, url, **kwargs):
            state["posts"].append(kwargs.get("json") or {})
            return _Resp({"id": "post-placeholder"}, status=201)

    monkeypatch.setattr("aiohttp.ClientSession", _Session)
    result = await mm._standalone_send(
        PlatformConfig(
            enabled=True,
            token="test-token",
            extra={
                "url": "https://mm.example.com",
                "pd_one_policy_cache_users": str(tmp_path),
            },
        ),
        chat_id,
        LEAK,
    )

    assert result["success"] is True
    posted = state["posts"][0]["message"]
    if hr_only:
        assert posted == LEAK
    else:
        assert posted == HR_PRIVATE_WITHHELD_NOTICE
        assert "G0-PLACEHOLDER" not in posted


@pytest.mark.asyncio
async def test_ordinary_company_text_is_not_treated_as_compensation(tmp_path):
    adapter = _adapter(tmp_path)
    adapter._api_post = AsyncMock(return_value={"id": "post-placeholder"})
    text = "company picnic on Friday"
    result = await adapter.send("channel-mixed", text)
    assert result.success is True
    assert adapter._api_post.call_args[0][1]["message"] == text


def test_onboarding_template_can_be_posted_to_a_mixed_channel():
    text = (REPO / "skills/mattermost-playbooks/references/employee-onboarding-thread-start.md").read_text(encoding="utf-8")
    assert "Output template" in text
    assert filter_private_hr_text(text, hr_only=False, chat_id="channel-mixed") == text

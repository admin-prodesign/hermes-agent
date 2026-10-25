"""Mattermost redacts private HR spans unless every destination human is HR or admin."""
import json
import logging
from pathlib import Path

import pytest
from unittest.mock import AsyncMock

from gateway.config import PlatformConfig
from gateway.session_context import clear_session_vars, set_session_vars
from tools.pd_one_hr_fields import (
    clear_private_hr_value_cache,
    filter_private_hr_text,
)

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


def _assert_span_redacted(posted: str) -> None:
    assert "Placeholder Person confirmed." in posted
    assert "G0-PLACEHOLDER" not in posted
    assert "P-PLACEHOLDER" not in posted
    assert "[withheld:" in posted
    assert "已隱藏" in posted
    assert "Private fields were withheld (" not in posted


@pytest.fixture(autouse=True)
def _reset_private_value_cache():
    clear_private_hr_value_cache()
    yield
    clear_private_hr_value_cache()
    clear_session_vars([])


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
        _assert_span_redacted(posted)
        assert "withheld private HR fields" in caplog.text
        assert "exact_job_grade_code" in caplog.text
        assert "travel_document" in caplog.text
        assert "G0-PLACEHOLDER" not in caplog.text
        assert "P-PLACEHOLDER" not in caplog.text
        assert LEAK not in caplog.text


@pytest.mark.asyncio
async def test_edit_message_mixed_channel_replaces_the_whole_message(tmp_path):
    _write_policies(tmp_path)
    adapter = _adapter(tmp_path)
    _install_get(adapter, "O", _members("user-hr-1", "user-staff-2"))
    adapter._api = AsyncMock(return_value={"id": "edit-placeholder"})

    result = await adapter.edit_message("channel-mixed", "post-1", LEAK, finalize=True)

    assert result.success is True
    payload = adapter._api.call_args[0][2]
    _assert_span_redacted(payload["message"])


@pytest.mark.asyncio
async def test_edit_message_hr_dm_keeps_private_text(tmp_path):
    _write_policies(tmp_path)
    adapter = _adapter(tmp_path)
    _install_get(adapter, "D", _members("user-hr-1"))
    adapter._api = AsyncMock(return_value={"id": "edit-placeholder"})

    result = await adapter.edit_message("dm-hr", "post-1", LEAK, finalize=True)

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
        _assert_span_redacted(posted)


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


@pytest.mark.asyncio
async def test_in_progress_edit_is_not_filtered(tmp_path):
    _write_policies(tmp_path)
    adapter = _adapter(tmp_path)
    _install_get(adapter, "O", _members("user-hr-1", "user-staff-2"))
    adapter._api = AsyncMock(return_value={"id": "edit-placeholder"})

    result = await adapter.edit_message("channel-mixed", "post-1", LEAK, finalize=False)

    assert result.success is True
    assert adapter._api.call_args[0][2]["message"] == LEAK


_PASS_PHRASES = (
    "Level 2: PD-#-P-### Purchasing Management",
    "Level 1 has only the quality manual",
    "peer rank 13/40",
    "legal level",
    "就業安定費級距",
    "本回覆不是薪資決定",
    "the level, the department, the reason",
)

_BLOCK_PHRASES = (
    ("護照到期日是 2027-01-01", "2027-01-01"),
    ("職等代碼: X3", "X3"),
    ("月薪 NT$45,000", "45,000"),
)


@pytest.mark.parametrize("text", _PASS_PHRASES)
def test_outbound_allows_ordinary_phrases(text):
    assert filter_private_hr_text(text, hr_only=False, chat_id="channel-mixed") == text


@pytest.mark.parametrize(("text", "secret"), _BLOCK_PHRASES)
def test_outbound_redacts_label_next_to_a_value(text, secret):
    filtered = filter_private_hr_text(text, hr_only=False, chat_id="channel-mixed")
    assert secret not in filtered
    assert "NT$" not in filtered
    assert "[withheld:" in filtered
    assert "已隱藏" in filtered
    assert filtered == filter_private_hr_text(filtered, hr_only=False, chat_id="channel-mixed")


def test_mixed_message_keeps_nonsensitive_text():
    text = (
        "Placeholder Person is in Purchasing. 職等代碼: X3. "
        "File the form with the department."
    )
    filtered = filter_private_hr_text(text, hr_only=False, chat_id="channel-mixed")
    assert "Placeholder Person is in Purchasing." in filtered
    assert "File the form with the department." in filtered
    assert "X3" not in filtered
    assert "職等代碼" not in filtered
    assert "[withheld: grade]" in filtered
    assert "〔已隱藏：職等〕" in filtered


def test_bilingual_reply_redacts_cached_value_in_both_blocks(caplog):
    from tools.pd_one_safe_ops import cmd_appsheet_table_probe

    token = "PV-CACHE-PLACEHOLDER"
    set_session_vars(
        platform="mattermost",
        chat_id="channel-mixed",
        chat_type="channel",
        session_id="sess-bilingual-cache",
    )
    payload = cmd_appsheet_table_probe(
        "HRS_Data",
        rows=[{"姓名": "Placeholder Person", "職等代碼": token}],
    )
    assert token not in json.dumps(payload, ensure_ascii=False)
    text = (
        f"English: Placeholder Person starts on Monday. Token {token} is internal.\n"
        f"中文：Placeholder Person 週一到職。代號 {token} 僅供內部。"
    )
    with caplog.at_level(logging.WARNING):
        filtered = filter_private_hr_text(text, hr_only=False, chat_id="channel-mixed")
    assert token not in filtered
    assert "cached_private_value" in caplog.text
    assert token not in caplog.text
    assert text not in caplog.text
    assert "English: Placeholder Person starts on Monday." in filtered
    assert "is internal." in filtered
    assert "中文：Placeholder Person 週一到職。" in filtered
    assert "僅供內部。" in filtered
    assert filtered.count("[withheld:") >= 2
    assert filtered.count("已隱藏") >= 2
    kept = filter_private_hr_text(text, hr_only=True, chat_id="dm-hr")
    assert token in kept


def test_grade_column_redacts_cells_and_keeps_the_table():
    text = (
        "Roster for the team.\n"
        "| name | grade | department |\n"
        "| --- | --- | --- |\n"
        "| Placeholder Person | X3 | Purchasing |\n"
        "| Placeholder Peer | G9 | Quality |\n"
    )
    filtered = filter_private_hr_text(text, hr_only=False, chat_id="channel-mixed")
    assert "Roster for the team." in filtered
    assert "| name | grade | department |" in filtered
    assert "| --- | --- | --- |" in filtered
    assert "Placeholder Person" in filtered
    assert "Placeholder Peer" in filtered
    assert "Purchasing" in filtered
    assert "Quality" in filtered
    assert "X3" not in filtered
    assert "G9" not in filtered
    assert filtered.count("|") == text.count("|")
    assert "[withheld: grade]" in filtered
    assert filtered == filter_private_hr_text(filtered, hr_only=False, chat_id="channel-mixed")


def test_passport_date_in_a_cell_keeps_the_table():
    text = (
        "Travel notes.\n"
        "| person | document |\n"
        "| --- | --- |\n"
        "| Placeholder Person | 護照到期日是 2027-01-01 |\n"
        "| Placeholder Peer | seat A |\n"
    )
    filtered = filter_private_hr_text(text, hr_only=False, chat_id="channel-mixed")
    assert "Travel notes." in filtered
    assert "| person | document |" in filtered
    assert "| --- | --- |" in filtered
    assert "Placeholder Person" in filtered
    assert "Placeholder Peer" in filtered
    assert "seat A" in filtered
    assert "2027-01-01" not in filtered
    assert "護照到期日" not in filtered
    assert filtered.count("|") == text.count("|")
    assert "[withheld: passport]" in filtered
    assert "〔已隱藏：護照〕" in filtered


def test_code_block_redacts_key_value_lines_in_place():
    text = (
        "Sample record.\n"
        "```\n"
        "name: Placeholder Person\n"
        "職等代碼: X3\n"
        "passport: 2027-01-01\n"
        "```\n"
        "End of sample.\n"
    )
    filtered = filter_private_hr_text(text, hr_only=False, chat_id="channel-mixed")
    assert "Sample record." in filtered
    assert "End of sample." in filtered
    assert "name: Placeholder Person" in filtered
    assert "X3" not in filtered
    assert "2027-01-01" not in filtered
    assert filtered.count("\n") == text.count("\n")
    interior = filtered.split("```")[1]
    assert "[withheld: grade]" in interior
    assert "[withheld: passport]" in interior
    assert "已隱藏" not in interior
    assert filtered == filter_private_hr_text(filtered, hr_only=False, chat_id="channel-mixed")


def test_cached_value_on_a_fence_line_falls_back_to_the_whole_message(caplog):
    from tools.pd_one_hr_fields import remember_private_hr_values

    token = "PV-CACHE-PLACEHOLDER"
    set_session_vars(
        platform="mattermost",
        chat_id="channel-mixed",
        chat_type="channel",
        session_id="sess-fence-cache",
    )
    remember_private_hr_values([{"職等代碼": token}])
    text = f"Intro about Purchasing.\n```{token}\nname: Placeholder Person\n```\n"
    with caplog.at_level(logging.WARNING):
        filtered = filter_private_hr_text(text, hr_only=False, chat_id="channel-mixed")
    assert token not in filtered
    assert token not in caplog.text
    assert "Intro about Purchasing." not in filtered
    assert "Private fields were withheld" in filtered
    assert "cached_private_value" in caplog.text


def test_code_block_without_a_private_span_stays():
    text = "```\nprint('ok')\n```\nPurchasing note. 職等代碼: X3. Done."
    filtered = filter_private_hr_text(text, hr_only=False, chat_id="channel-mixed")
    assert "print('ok')" in filtered
    assert "Purchasing note." in filtered
    assert "Done." in filtered
    assert "X3" not in filtered

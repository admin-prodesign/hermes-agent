"""Fail-closed Mattermost gate for private HR fields.

The requester may be allowed to read a row. The send destination is still the
only audience, and a failed membership or policy lookup replaces the whole body.
"""

import json
from urllib.parse import parse_qs

import pytest

from gateway.config import PlatformConfig
from plugins.platforms.mattermost import adapter as mm
from plugins.platforms.mattermost.adapter import MattermostAdapter

NOTICE = (
    "我已確認這筆資料。我不會在這個房間張貼私人人事欄位。若需要那些欄位，請用私訊詢問。\n"
    "\n---\n\n"
    "I confirmed the record. I will not post private HR fields in this room. "
    "Ask in a direct message if you need those fields."
)
ROOM_NAME = "新員工 New Employees"
BOT = "mm-bot-1"
OTHER_BOT = "mm-bot-2"
HR = "mm-hr-1"
ADMIN = "mm-admin-1"
MANAGER = "mm-manager-1"
STAFF = "mm-staff-1"
CHANNEL = "room-mixed-1"
DM = "dm-room-1"

MARKERS = (
    "職等: G4",
    "職級: L2",
    "身份類別: 月薪",
    "直間接: 直接",
    "勞退: 新制",
    "護照: P0000000",
    "居留證: R0000000",
    "年資起算: 2020-01-01",
    "Job Grade: G4",
    "grade code: G4",
    "job rank: L2",
    "rank code: L2",
    "identity category: monthly",
    "worker class: direct",
    "pension: new scheme",
    "文件passport: P0000000",
    "residence permit: R0000000",
    "seniority start: 2020-01-01",
)
SAFE_LINES = (
    "部門 department: 組裝",
    "職稱 job title: 技術員",
    "start date: 2024-03-01",
    "employment status: active",
    "employee number: E-100",
    "person name: Sample Person",
    "upgrade code: UX-1",
    "pensions review is not this field",
)


def _write_policy(cache_dir, user_id, roles):
    (cache_dir / f"{user_id}.json").write_text(
        json.dumps({
            "found": True,
            "active": True,
            "roles": list(roles),
            "mattermostUserId": user_id,
        }),
        encoding="utf-8",
    )


def _users():
    return {
        BOT: {"id": BOT, "is_bot": True, "username": "pd-bot"},
        OTHER_BOT: {"id": OTHER_BOT, "is_bot": True, "username": "webhook"},
        HR: {"id": HR, "is_bot": False, "username": "hr-lead-sample"},
        ADMIN: {"id": ADMIN, "is_bot": False, "username": "admin-sample"},
        MANAGER: {"id": MANAGER, "is_bot": False, "username": "hr-manager-sample"},
        STAFF: {"id": STAFF, "is_bot": False, "username": "staff-sample"},
    }


def _adapter(tmp_path, *, with_cache=True):
    extra = {"url": "https://mm.example.test"}
    cache_dir = tmp_path / "policy-users"
    if with_cache:
        cache_dir.mkdir()
        extra["pd_one_policy_cache_users"] = str(cache_dir)
    adapter = MattermostAdapter(PlatformConfig(enabled=True, token="test-token", extra=extra))
    adapter._bot_user_id = BOT
    return adapter, cache_dir


def _install_api(adapter, *, channel_type, members, users, chat_id, broken=None):
    """Stub Mattermost reads. ``broken`` forces a failed lookup without posting the model text."""
    state = {"posts": [], "gets": [], "channel_type": channel_type, "members": list(members), "users": users}

    async def fake_api(method, path, payload=None):
        state["gets"].append((method, path, payload))
        if broken == "members" and method == "GET" and "/members" in path:
            return {}
        if broken == "users" and method == "POST" and path == "users/ids":
            return {}
        if method == "GET" and path == f"channels/{chat_id}":
            return {
                "id": chat_id,
                "type": state["channel_type"],
                "display_name": ROOM_NAME,
                "name": "new-employees",
            }
        if method == "GET" and path.startswith(f"channels/{chat_id}/members"):
            query = parse_qs(path.split("?", 1)[1] if "?" in path else "")
            page = int(query.get("page", ["0"])[0])
            per_page = int(query.get("per_page", ["200"])[0])
            start = page * per_page
            return state["members"][start:start + per_page]
        if method == "POST" and path == "users/ids":
            found = [users[user_id] for user_id in payload if user_id in users]
            if len(found) != len(payload):
                return found
            return found
        if method == "POST" and path == "posts":
            state["posts"].append(dict(payload))
            return {"id": "post-1", "channel_id": payload.get("channel_id"), "message": payload.get("message")}
        if method == "PUT" and path.startswith("posts/"):
            state["posts"].append(dict(payload))
            return {"id": "post-1", "message": payload.get("message")}
        return {}

    adapter._api = fake_api
    return state


def _member(user_id):
    return {"user_id": user_id, "channel_id": CHANNEL}


@pytest.fixture
def room(tmp_path):
    adapter, cache_dir = _adapter(tmp_path)
    _write_policy(cache_dir, HR, ["hr_lead"])
    _write_policy(cache_dir, ADMIN, ["admin"])
    _write_policy(cache_dir, MANAGER, ["hr_manager_transition"])
    _write_policy(cache_dir, STAFF, ["employee"])
    return adapter, cache_dir


def _posted(state):
    assert len(state["posts"]) == 1
    return state["posts"][0]["message"]


@pytest.mark.asyncio
async def test_mixed_channel_with_private_marker_is_replaced(room):
    adapter, _cache = room
    state = _install_api(
        adapter, channel_type="O", chat_id=CHANNEL, users=_users(),
        members=[_member(BOT), _member(OTHER_BOT), _member(HR), _member(STAFF)],
    )
    original = "部門 department: 組裝\n職等: G4\nchannel_id: not-the-destination\n職稱 job title: 技術員"
    result = await adapter.send(CHANNEL, original)

    assert result.success is True
    assert _posted(state) == NOTICE
    assert "職等" not in _posted(state)
    assert "department" not in _posted(state)
    assert state["posts"][0]["channel_id"] == CHANNEL
    member_paths = [path for method, path, _payload in state["gets"] if method == "GET" and "/members" in path]
    assert member_paths
    assert all(CHANNEL in path and "not-the-destination" not in path for path in member_paths)


@pytest.mark.asyncio
@pytest.mark.parametrize("marker", MARKERS)
async def test_each_private_marker_is_replaced_in_a_mixed_room(room, marker):
    adapter, _cache = room
    state = _install_api(
        adapter, channel_type="P", chat_id=CHANNEL, users=_users(),
        members=[_member(HR), _member(STAFF), _member(BOT)],
    )
    result = await adapter.send(CHANNEL, f"sample field {marker}")
    assert result.success is True
    assert _posted(state) == NOTICE


@pytest.mark.asyncio
async def test_room_of_only_hr_or_admin_humans_keeps_original_text(room):
    adapter, _cache = room
    state = _install_api(
        adapter, channel_type="O", chat_id=CHANNEL, users=_users(),
        members=[_member(BOT), _member(OTHER_BOT), _member(HR), _member(ADMIN), _member(MANAGER)],
    )
    original = "職等: G4\n身份類別: 月薪\npassport: P0000000"
    result = await adapter.send(CHANNEL, original)

    assert result.success is True
    assert _posted(state) == original


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id", (HR, ADMIN, MANAGER))
async def test_direct_message_to_hr_or_admin_keeps_original_text(room, user_id):
    adapter, _cache = room
    state = _install_api(
        adapter, channel_type="D", chat_id=DM, users=_users(),
        members=[{"user_id": BOT}, {"user_id": user_id}],
    )
    original = "職級: L2"
    result = await adapter.send(DM, original)

    assert result.success is True
    assert _posted(state) == original


@pytest.mark.asyncio
async def test_direct_message_to_non_hr_member_is_replaced(room):
    adapter, _cache = room
    state = _install_api(
        adapter, channel_type="D", chat_id=DM, users=_users(),
        members=[{"user_id": BOT}, {"user_id": STAFF}],
    )
    result = await adapter.send(DM, "居留證: R0000000")

    assert result.success is True
    assert _posted(state) == NOTICE


@pytest.mark.asyncio
@pytest.mark.parametrize("line", SAFE_LINES)
async def test_department_and_job_title_without_private_marker_is_unchanged(room, line):
    adapter, _cache = room
    state = _install_api(
        adapter, channel_type="O", chat_id=CHANNEL, users=_users(),
        members=[_member(HR), _member(STAFF)],
    )
    result = await adapter.send(CHANNEL, line)

    assert result.success is True
    assert _posted(state) == line
    assert not any(method == "GET" and "/members" in path for method, path, _payload in state["gets"])


@pytest.mark.asyncio
async def test_edit_message_and_standalone_send_use_the_same_gate(room, tmp_path, monkeypatch):
    adapter, cache_dir = room
    calls = []
    original_gate = mm._withhold_private_hr_fields

    async def recording_gate(message, chat_id, **kwargs):
        calls.append((chat_id, message))
        return await original_gate(message, chat_id, **kwargs)

    monkeypatch.setattr(mm, "_withhold_private_hr_fields", recording_gate)
    state = _install_api(
        adapter, channel_type="O", chat_id=CHANNEL, users=_users(),
        members=[_member(BOT), _member(STAFF)],
    )
    edited = await adapter.edit_message(CHANNEL, "post-9", "勞退: 新制")
    assert edited.success is True
    assert state["posts"][-1]["message"] == NOTICE

    posted = {}

    class _Resp:
        def __init__(self, status, payload):
            self.status = status
            self._payload = payload

        async def text(self):
            return ""

        async def read(self):
            return b""

        async def json(self):
            return self._payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    class _Session:
        def __init__(self, *_args, **_kwargs):
            posted["session"] = self
            self.posts = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def request(self, method, url, **kwargs):
            path = url.split("/api/v4/", 1)[-1]
            body = _dispatch(method, path, kwargs.get("json"))
            return _Resp(200, body)

        def post(self, url, **kwargs):
            payload = kwargs.get("json") or {}
            self.posts.append(payload)
            return _Resp(201, {"id": "cron-post"})

    def _dispatch(method, path, payload):
        if method == "GET" and path == f"channels/{CHANNEL}":
            return {"id": CHANNEL, "type": "O", "display_name": ROOM_NAME}
        if method == "GET" and path.startswith(f"channels/{CHANNEL}/members"):
            return [{"user_id": BOT}, {"user_id": STAFF}]
        if method == "POST" and path == "users/ids":
            return [_users()[user_id] for user_id in payload]
        return {}

    monkeypatch.setattr("aiohttp.ClientSession", _Session)
    config = PlatformConfig(
        enabled=True, token="test-token",
        extra={"url": "https://mm.example.test", "pd_one_policy_cache_users": str(cache_dir)},
    )
    sent = await mm._standalone_send(config, CHANNEL, "護照: P0000000")

    assert sent["success"] is True
    assert posted["session"].posts[0]["message"] == NOTICE
    assert posted["session"].posts[0]["channel_id"] == CHANNEL
    assert [chat_id for chat_id, _message in calls] == [CHANNEL, CHANNEL]
    assert all("勞退" in message or "護照" in message for _chat_id, message in calls)


@pytest.mark.asyncio
async def test_failed_member_lookup_replaces_text(room, caplog):
    adapter, _cache = room
    state = _install_api(
        adapter, channel_type="O", chat_id=CHANNEL, users=_users(),
        members=[_member(HR), _member(ADMIN)], broken="members",
    )
    secret = "職等: G4-synthetic"
    with caplog.at_level("WARNING"):
        result = await adapter.send(CHANNEL, secret)

    assert result.success is True
    assert _posted(state) == NOTICE
    assert secret not in caplog.text
    assert "職等" not in caplog.text


@pytest.mark.asyncio
async def test_failed_user_lookup_replaces_text(room):
    adapter, _cache = room
    state = _install_api(
        adapter, channel_type="D", chat_id=DM, users=_users(),
        members=[{"user_id": BOT}, {"user_id": HR}], broken="users",
    )
    result = await adapter.send(DM, "rank code: L2")
    assert result.success is True
    assert _posted(state) == NOTICE


@pytest.mark.asyncio
async def test_unreadable_policy_replaces_text_even_for_an_hr_room(tmp_path):
    adapter, cache_dir = _adapter(tmp_path)
    (cache_dir / f"{HR}.json").mkdir()
    state = _install_api(
        adapter, channel_type="D", chat_id=DM, users=_users(),
        members=[{"user_id": BOT}, {"user_id": HR}],
    )
    result = await adapter.send(DM, "pension: new scheme")
    assert result.success is True
    assert _posted(state) == NOTICE


@pytest.mark.asyncio
async def test_missing_policy_cache_replaces_text(tmp_path):
    adapter, _cache = _adapter(tmp_path, with_cache=False)
    state = _install_api(
        adapter, channel_type="D", chat_id=DM, users=_users(),
        members=[{"user_id": BOT}, {"user_id": ADMIN}],
    )
    result = await adapter.send(DM, "worker class: direct")
    assert result.success is True
    assert _posted(state) == NOTICE


@pytest.mark.asyncio
async def test_later_member_page_can_make_a_room_mixed(room, monkeypatch):
    monkeypatch.setattr(mm, "_PRIVATE_HR_MEMBER_PAGE", 2)
    adapter, _cache = room
    state = _install_api(
        adapter, channel_type="O", chat_id=CHANNEL, users=_users(),
        members=[_member(BOT), _member(HR), _member(ADMIN), _member(STAFF)],
    )
    result = await adapter.send(CHANNEL, "年資起算: 2020-01-01")
    assert result.success is True
    assert _posted(state) == NOTICE
    member_gets = [path for method, path, _payload in state["gets"] if method == "GET" and "/members" in path]
    assert len(member_gets) >= 2

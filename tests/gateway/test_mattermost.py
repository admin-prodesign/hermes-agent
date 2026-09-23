"""Tests for Mattermost platform adapter."""
import json
import os
import time
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from gateway.config import Platform, PlatformConfig
from gateway.platforms.event import MessageType
from gateway.run import (
    _resolve_gateway_display_bool,
    _resolve_progress_thread_id,
)


class TestMattermostProgressThreadRouting:
    def test_top_level_mattermost_progress_uses_event_message_id(self):
        assert _resolve_progress_thread_id(
            Platform.MATTERMOST,
            source_thread_id=None,
            event_message_id="top_post_123",
        ) == "top_post_123"


class TestMattermostDisplayHygiene:

    def test_mattermost_platform_opt_in_can_enable_interim_assistant_messages(self):
        """Mattermost can still opt into commentary explicitly per platform."""
        user_config = {
            "display": {
                "interim_assistant_messages": False,
                "platforms": {
                    "mattermost": {"interim_assistant_messages": True},
                },
            }
        }

        assert _resolve_gateway_display_bool(
            user_config,
            "mattermost",
            "interim_assistant_messages",
            default=True,
            platform=Platform.MATTERMOST,
            require_platform_override_for={Platform.MATTERMOST},
        ) is True


    def test_global_thinking_progress_still_applies_to_other_platforms(self):
        """The Mattermost guard must not silently neuter Telegram/other chats."""
        user_config = {"display": {"thinking_progress": True}}

        assert _resolve_gateway_display_bool(
            user_config,
            "telegram",
            "thinking_progress",
            default=False,
            platform=Platform.TELEGRAM,
            require_platform_override_for={Platform.MATTERMOST},
        ) is True


# ---------------------------------------------------------------------------
# Platform & Config
# ---------------------------------------------------------------------------

class TestMattermostConfigLoading:


    def test_mattermost_home_channel(self, monkeypatch):
        monkeypatch.setenv("MATTERMOST_TOKEN", "mm-tok-abc123")
        monkeypatch.setenv("MATTERMOST_URL", "https://mm.example.com")
        monkeypatch.setenv("MATTERMOST_HOME_CHANNEL", "ch_abc123")
        monkeypatch.setenv("MATTERMOST_HOME_CHANNEL_NAME", "General")

        from gateway.config import GatewayConfig, _apply_env_overrides
        config = GatewayConfig()
        _apply_env_overrides(config)

        home = config.get_home_channel(Platform.MATTERMOST)
        assert home is not None
        assert home.chat_id == "ch_abc123"
        assert home.name == "General"


# ---------------------------------------------------------------------------
# Adapter format / truncate
# ---------------------------------------------------------------------------

def _make_adapter():
    """Create a MattermostAdapter with mocked config."""
    from plugins.platforms.mattermost.adapter import MattermostAdapter
    config = PlatformConfig(
        enabled=True,
        token="test-token",
        extra={"url": "https://mm.example.com"},
    )
    adapter = MattermostAdapter(config)
    return adapter


class TestMattermostFormatMessage:
    def setup_method(self):
        self.adapter = _make_adapter()

    def test_image_markdown_to_url(self):
        """![alt](url) should be converted to just the URL."""
        result = self.adapter.format_message("![cat](https://img.example.com/cat.png)")
        assert result == "https://img.example.com/cat.png"


    def test_regular_markdown_preserved(self):
        """Regular markdown (bold, italic, code) should be kept as-is."""
        content = "**bold** and *italic* and `code`"
        assert self.adapter.format_message(content) == content


class TestMattermostTruncateMessage:
    def setup_method(self):
        self.adapter = _make_adapter()


    def test_long_message_splits(self):
        msg = "a " * 2500  # 5000 chars
        chunks = self.adapter.truncate_message(msg, 4000)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 4000


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

class TestMattermostSend:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._session = MagicMock()

    @pytest.mark.asyncio
    async def test_send_calls_api_post(self):
        """send() should POST to /api/v4/posts with channel_id and message."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"id": "post123"})
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)

        result = await self.adapter.send("channel_1", "Hello!")

        assert result.success is True
        assert result.message_id == "post123"

        # Verify post was called with correct URL
        call_args = self.adapter._session.post.call_args
        assert "/api/v4/posts" in call_args[0][0]
        # Verify payload
        payload = call_args[1]["json"]
        assert payload["channel_id"] == "channel_1"
        assert payload["message"] == "Hello!"


    @pytest.mark.asyncio
    async def test_send_with_thread_reply(self):
        """When reply_mode is 'thread', reply_to should become root_id."""
        self.adapter._reply_mode = "thread"

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"id": "post456"})
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        # send() now calls _resolve_root_id → _api_get("posts/<id>") first
        # to make sure root_id points to a thread root, so we need to mock
        # the GET too.  Return an empty dict (no root_id) so the resolver
        # falls back to the original reply_to as the root.
        mock_get_resp = AsyncMock()
        mock_get_resp.status = 200
        mock_get_resp.json = AsyncMock(return_value={"id": "root_post", "root_id": ""})
        mock_get_resp.text = AsyncMock(return_value="")
        mock_get_resp.__aenter__ = AsyncMock(return_value=mock_get_resp)
        mock_get_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)
        self.adapter._session.get = MagicMock(return_value=mock_get_resp)

        result = await self.adapter.send("channel_1", "Reply!", reply_to="root_post")

        assert result.success is True
        payload = self.adapter._session.post.call_args[1]["json"]
        assert payload["root_id"] == "root_post"


    @pytest.mark.asyncio
    async def test_progress_send_with_invalid_thread_root_never_falls_back_flat(self):
        """Tool/status/progress bubbles must stay quiet when the thread is broken."""
        self.adapter._reply_mode = "thread"
        self.adapter._api_get = AsyncMock(return_value={"id": "bad_root", "root_id": ""})
        self.adapter._last_post_status = 400
        self.adapter._last_post_error = "api.context.invalid_param.app_error: invalid root_id"
        self.adapter._api_post = AsyncMock(return_value={})

        result = await self.adapter.send(
            "channel_1",
            "⚙️ terminal...",
            metadata={"thread_id": "bad_root"},
        )

        assert result.success is False
        assert self.adapter._api_post.call_count == 1
        payload = self.adapter._api_post.call_args_list[0][0][1]
        assert payload["root_id"] == "bad_root"

    @pytest.mark.asyncio
    async def test_notify_send_with_invalid_thread_root_falls_back_flat_with_warning(self):
        """Notify-worthy replies may fall back flat so the answer is not lost."""
        self.adapter._reply_mode = "thread"
        self.adapter._api_get = AsyncMock(return_value={"id": "bad_root", "root_id": ""})
        self.adapter._last_post_status = 400
        self.adapter._last_post_error = "api.context.invalid_param.app_error: invalid root_id"
        self.adapter._api_post = AsyncMock(side_effect=[{}, {"id": "flat_final"}])

        result = await self.adapter.send(
            "channel_1",
            "Final answer body",
            reply_to="bad_root",
            metadata={"notify": True},
        )

        assert result.success is True
        assert result.message_id == "flat_final"
        assert self.adapter._api_post.call_count == 2
        threaded_payload = self.adapter._api_post.call_args_list[0][0][1]
        flat_payload = self.adapter._api_post.call_args_list[1][0][1]
        assert threaded_payload["root_id"] == "bad_root"
        assert "root_id" not in flat_payload
        assert flat_payload["channel_id"] == "channel_1"
        assert "Mattermost thread delivery failed" in flat_payload["message"]
        assert "Final answer body" in flat_payload["message"]


    @pytest.mark.asyncio
    async def test_progress_send_with_broken_thread_and_no_recorded_error_stays_quiet(self):
        """Same rule when no post error was recorded: still no flat fallback."""
        self.adapter._reply_mode = "thread"
        self.adapter._api_get = AsyncMock(return_value={"id": "bad_root", "root_id": ""})
        self.adapter._api_post = AsyncMock(return_value={})

        result = await self.adapter.send(
            "channel_1",
            "⚙️ terminal...",
            metadata={"thread_id": "bad_root"},
        )

        assert result.success is False
        assert self.adapter._api_post.call_count == 1
        payload = self.adapter._api_post.call_args_list[0][0][1]
        assert payload["root_id"] == "bad_root"


# ---------------------------------------------------------------------------
# WebSocket event parsing
# ---------------------------------------------------------------------------

class TestMattermostWebSocketParsing:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        self.adapter._bot_username = "hermes-bot"
        # Mock handle_message to capture the MessageEvent without processing
        self.adapter.handle_message = AsyncMock()

    @pytest.mark.asyncio
    async def test_parse_posted_event(self):
        """'posted' events should extract message from double-encoded post JSON."""
        post_data = {
            "id": "post_abc",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@bot_user_id Hello from Matrix!",
        }
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),  # double-encoded JSON string
                "channel_type": "O",
                "sender_name": "@alice",
            },
        }

        await self.adapter._handle_ws_event(event)
        assert self.adapter.handle_message.called
        msg_event = self.adapter.handle_message.call_args[0][0]
        # @mention is stripped from the message text
        assert msg_event.text == "Hello from Matrix!"
        assert msg_event.message_id == "post_abc"


    @pytest.mark.asyncio
    async def test_ignore_system_posts(self):
        """Posts with a 'type' field (system messages) should be ignored."""
        post_data = {
            "id": "sys_post",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "user joined",
            "type": "system_join_channel",
        }
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "O",
            },
        }

        await self.adapter._handle_ws_event(event)
        assert not self.adapter.handle_message.called


    @pytest.mark.asyncio
    async def test_leading_space_slash_command_is_command(self):
        """Mattermost mobile suggests leading-space slash commands."""
        post_data = {
            "id": "post_cmd",
            "user_id": "user_123",
            "channel_id": "chan_dm",
            "message": " /new",
        }
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "D",
                "sender_name": "@bob",
            },
        }

        await self.adapter._handle_ws_event(event)
        assert self.adapter.handle_message.called
        msg_event = self.adapter.handle_message.call_args[0][0]
        assert msg_event.text == "/new"
        assert msg_event.message_type is MessageType.COMMAND
        assert msg_event.get_command() == "new"


# ---------------------------------------------------------------------------
# Mention behavior (require_mention + free_response_channels)
# ---------------------------------------------------------------------------

class TestMattermostMentionBehavior:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        self.adapter._bot_username = "hermes-bot"
        self.adapter.handle_message = AsyncMock()

    def _make_event(self, message, channel_type="O", channel_id="chan_456"):
        post_data = {
            "id": "post_mention",
            "user_id": "user_123",
            "channel_id": channel_id,
            "message": message,
        }
        return {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": channel_type,
                "sender_name": "@alice",
            },
        }

    @pytest.mark.asyncio
    async def test_require_mention_true_skips_without_mention(self):
        """Default: messages without @mention in channels are skipped."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MATTERMOST_REQUIRE_MENTION", None)
            os.environ.pop("MATTERMOST_FREE_RESPONSE_CHANNELS", None)
            await self.adapter._handle_ws_event(self._make_event("hello"))
            assert not self.adapter.handle_message.called


    @pytest.mark.asyncio
    async def test_free_response_channel_responds_without_mention(self):
        """Messages in free-response channels don't need @mention."""
        with patch.dict(os.environ, {"MATTERMOST_FREE_RESPONSE_CHANNELS": "chan_456,chan_789"}):
            os.environ.pop("MATTERMOST_REQUIRE_MENTION", None)
            await self.adapter._handle_ws_event(self._make_event("hello", channel_id="chan_456"))
            assert self.adapter.handle_message.called


# ---------------------------------------------------------------------------
# File upload (send_image)
# ---------------------------------------------------------------------------

class TestMattermostFileUpload:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._session = MagicMock()

    @pytest.mark.asyncio
    @patch("tools.url_safety.is_safe_url", return_value=True)
    async def test_send_image_downloads_and_uploads(self, _mock_safe):
        """send_image should download the URL, upload via /api/v4/files, then post."""
        # Mock the download (GET)
        mock_dl_resp = AsyncMock()
        mock_dl_resp.status = 200
        mock_dl_resp.read = AsyncMock(return_value=b"\x89PNG\x00fake-image-data")
        mock_dl_resp.content_type = "image/png"
        mock_dl_resp.__aenter__ = AsyncMock(return_value=mock_dl_resp)
        mock_dl_resp.__aexit__ = AsyncMock(return_value=False)

        # Mock the upload (POST to /files)
        mock_upload_resp = AsyncMock()
        mock_upload_resp.status = 200
        mock_upload_resp.json = AsyncMock(return_value={
            "file_infos": [{"id": "file_abc123"}]
        })
        mock_upload_resp.text = AsyncMock(return_value="")
        mock_upload_resp.__aenter__ = AsyncMock(return_value=mock_upload_resp)
        mock_upload_resp.__aexit__ = AsyncMock(return_value=False)

        # Mock the post (POST to /posts)
        mock_post_resp = AsyncMock()
        mock_post_resp.status = 200
        mock_post_resp.json = AsyncMock(return_value={"id": "post_with_file"})
        mock_post_resp.text = AsyncMock(return_value="")
        mock_post_resp.__aenter__ = AsyncMock(return_value=mock_post_resp)
        mock_post_resp.__aexit__ = AsyncMock(return_value=False)

        # Route calls: first GET (download), then POST (upload), then POST (create post)
        self.adapter._session.get = MagicMock(return_value=mock_dl_resp)
        post_call_count = 0
        original_post_returns = [mock_upload_resp, mock_post_resp]

        def post_side_effect(*args, **kwargs):
            nonlocal post_call_count
            resp = original_post_returns[min(post_call_count, len(original_post_returns) - 1)]
            post_call_count += 1
            return resp

        self.adapter._session.post = MagicMock(side_effect=post_side_effect)

        result = await self.adapter.send_image(
            "channel_1", "https://img.example.com/cat.png", caption="A cat"
        )

        assert result.success is True
        assert result.message_id == "post_with_file"


# ---------------------------------------------------------------------------
# Dedup cache
# ---------------------------------------------------------------------------

class TestMattermostDedup:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        # Mock handle_message to capture calls without processing
        self.adapter.handle_message = AsyncMock()


    def test_prune_seen_clears_expired(self):
        """Dedup cache should remove entries older than TTL on overflow."""
        now = time.time()
        dedup = self.adapter._dedup
        # Fill with enough expired entries to trigger pruning
        for i in range(dedup._max_size + 10):
            dedup._seen[f"old_{i}"] = now - 600  # 10 min ago (older than default TTL)

        # Add a fresh one
        dedup._seen["fresh"] = now

        # Trigger pruning by calling is_duplicate with a new entry (over max_size)
        dedup.is_duplicate("trigger_prune")

        # Old entries should be pruned, fresh one kept
        assert "fresh" in dedup._seen
        assert len(dedup._seen) < dedup._max_size + 10


# ---------------------------------------------------------------------------
# Requirements check
# ---------------------------------------------------------------------------

class TestMattermostRequirements:
    def test_check_requirements_with_token_and_url(self, monkeypatch):
        monkeypatch.setenv("MATTERMOST_TOKEN", "test-token")
        monkeypatch.setenv("MATTERMOST_URL", "https://mm.example.com")
        from plugins.platforms.mattermost.adapter import check_mattermost_requirements
        assert check_mattermost_requirements() is True


    def test_validate_config_accepts_platform_values(self, monkeypatch):
        monkeypatch.delenv("MATTERMOST_TOKEN", raising=False)
        monkeypatch.delenv("MATTERMOST_URL", raising=False)
        from plugins.platforms.mattermost.adapter import validate_mattermost_config

        config = PlatformConfig(
            enabled=True,
            token="cfg-token",
            extra={"url": "https://mm.example.com"},
        )
        assert validate_mattermost_config(config) is True


# ---------------------------------------------------------------------------
# Media type propagation (MIME types, not bare strings)
# ---------------------------------------------------------------------------

class TestMattermostMediaTypes:
    """Verify that media_types contains actual MIME types (e.g. 'image/png')
    rather than bare category strings ('image'), so downstream
    ``mtype.startswith("image/")`` checks in run.py work correctly."""

    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        self.adapter.handle_message = AsyncMock()

    def _make_event(self, file_ids):
        post_data = {
            "id": "post_media",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@bot_user_id file attached",
            "file_ids": file_ids,
        }
        return {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "O",
                "sender_name": "@alice",
            },
        }

    @pytest.mark.asyncio
    async def test_image_media_type_is_full_mime(self):
        """An image attachment should produce 'image/png', not 'image'."""
        file_info = {"name": "photo.png", "mime_type": "image/png"}
        self.adapter._api_get = AsyncMock(return_value=file_info)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"\x89PNG fake")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        self.adapter._session = MagicMock()
        self.adapter._session.get = MagicMock(return_value=mock_resp)

        with patch("gateway.platforms.base.cache_image_from_bytes", return_value="/tmp/photo.png"):
            await self.adapter._handle_ws_event(self._make_event(["file1"]))

        msg = self.adapter.handle_message.call_args[0][0]
        assert msg.media_types == ["image/png"]
        assert msg.media_types[0].startswith("image/")


@pytest.mark.asyncio
async def test_mattermost_top_level_channel_post_is_thread_root():
    adapter = _make_adapter()
    adapter._reply_mode = "thread"
    adapter._bot_user_id = "bot_user_id"
    adapter._bot_username = "hermes-bot"
    adapter.handle_message = AsyncMock()
    post_data = {
        "id": "top_post_123",
        "user_id": "user_123",
        "channel_id": "chan_456",
        "message": "@hermes-bot start work",
        "root_id": "",
    }
    event = {
        "event": "posted",
        "data": {
            "post": json.dumps(post_data),
            "channel_type": "O",
            "sender_name": "@alice",
        },
    }

    await adapter._handle_ws_event(event)

    msg_event = adapter.handle_message.call_args[0][0]
    assert msg_event.source.thread_id == "top_post_123"
    assert msg_event.source.message_id == "top_post_123"
    assert msg_event.message_id == "top_post_123"


# ---------------------------------------------------------------------------
# Multiplex secondary-profile scope
# ---------------------------------------------------------------------------
#
# __init__'s url/reply_mode, validate_mattermost_config's url,
# _standalone_send's url, and _handle_ws_event's require_mention/
# free_response_channels/allowed_channels, all previously read raw
# os.getenv unconditionally (only MATTERMOST_TOKEN was already scoped).
# _apply_yaml_config also wrote MATTERMOST_REQUIRE_MENTION/
# MATTERMOST_FREE_RESPONSE_CHANNELS/MATTERMOST_ALLOWED_CHANNELS into the
# process-global os.environ unconditionally. Under multiplex, os.environ
# holds the DEFAULT profile's YAML-to-env bridge output -- a secondary
# profile with its own (different or absent) Mattermost config would
# silently connect to the default profile's server, or have its
# mention-gating/channel-allowlist decisions driven by the default
# profile's settings. Mirrors the LINE/DingTalk/IRC fix for #98738.

@pytest.fixture
def multiplex_scope():
    """Install multiplex + a secondary-profile secret scope; restore after."""
    tokens = []

    def install(scope=None):
        from agent.secret_scope import set_multiplex_active, set_secret_scope

        set_multiplex_active(True)
        tokens.append(set_secret_scope(scope or {}))
        return tokens[-1]

    yield install

    from agent.secret_scope import reset_secret_scope, set_multiplex_active

    for token in reversed(tokens):
        reset_secret_scope(token)
    set_multiplex_active(False)


@pytest.fixture
def default_profile_env(monkeypatch):
    """The default profile's YAML-to-env bridge output in os.environ."""
    monkeypatch.setenv("MATTERMOST_URL", "https://default.example.com")
    monkeypatch.setenv("MATTERMOST_REPLY_MODE", "thread")
    monkeypatch.setenv("MATTERMOST_REQUIRE_MENTION", "false")
    monkeypatch.setenv("MATTERMOST_FREE_RESPONSE_CHANNELS", "chan_default")
    monkeypatch.setenv("MATTERMOST_ALLOWED_CHANNELS", "chan_default")


class TestMultiplexProfileScope:

    @pytest.mark.asyncio
    async def test_ws_event_gating_uses_scoped_settings_not_default(
        self, monkeypatch
    ):
        """A secondary profile's own require_mention/free_response_channels/
        allowed_channels (installed via the scope) must gate its messages --
        not the default profile's bridged settings."""
        from agent.secret_scope import (
            reset_secret_scope,
            set_multiplex_active,
            set_secret_scope,
        )
        from plugins.platforms.mattermost.adapter import MattermostAdapter

        monkeypatch.setenv("MATTERMOST_REQUIRE_MENTION", "true")
        monkeypatch.delenv("MATTERMOST_FREE_RESPONSE_CHANNELS", raising=False)

        adapter = _make_adapter()
        adapter._bot_user_id = "bot_user_id"
        adapter._bot_username = "hermes-bot"
        adapter.handle_message = AsyncMock()

        post_data = {
            "id": "post_scoped",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "hello with no mention",
        }
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "O",
                "sender_name": "@alice",
            },
        }

        set_multiplex_active(True)
        token = set_secret_scope({"MATTERMOST_REQUIRE_MENTION": "false"})
        try:
            await adapter._handle_ws_event(event)
        finally:
            reset_secret_scope(token)
            set_multiplex_active(False)

        # The profile's own scope disables require_mention -- the message
        # must be dispatched even without an @mention, despite the default
        # profile's env bridge saying require_mention=true.
        assert adapter.handle_message.called

    def test_apply_yaml_config_scoped_skips_env_write_and_seeds_extra(
        self, multiplex_scope
    ):
        from plugins.platforms.mattermost.adapter import _apply_yaml_config

        multiplex_scope()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MATTERMOST_REQUIRE_MENTION", None)
            seeded = _apply_yaml_config({}, {"require_mention": False, "allowed_channels": ["c1"]})
            assert seeded == {"require_mention": False, "allowed_channels": ["c1"]}
            # Under a secondary profile's scope the env bridge must be
            # skipped -- writing here would leak into every other profile's
            # os.environ.
            assert "MATTERMOST_REQUIRE_MENTION" not in os.environ



class TestMattermostProgressRouting:
    def test_root_post_progress_uses_triggering_post_as_thread_root(self):
        """Root-channel mentions have no source.thread_id, but progress must thread."""
        from gateway.run import _mattermost_progress_thread_route

        thread_id, reply_to = _mattermost_progress_thread_route(
            source_thread_id=None,
            event_message_id="root_post",
        )

        assert thread_id == "root_post"
        assert reply_to == "root_post"

    def test_reply_progress_preserves_existing_root_and_reply_anchor(self):
        from gateway.run import _mattermost_progress_thread_route

        thread_id, reply_to = _mattermost_progress_thread_route(
            source_thread_id="thread_root",
            event_message_id="reply_post",
        )

        assert thread_id == "thread_root"
        assert reply_to == "reply_post"


class TestMattermostAutoThreadRootHeading:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        self.adapter.config.extra["auto_thread_root_heading"] = True
        self.adapter.handle_message = AsyncMock()

    def _reply_event(self, message="Follow-up reply"):
        post_data = {
            "id": "reply_post",
            "root_id": "root_post",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": message,
        }
        return {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "O",
                "sender_name": "@alice",
            },
        }

    def test_detects_existing_markdown_heading(self):
        assert self.adapter._has_markdown_heading("### Proper title\n\nBody") is True
        assert self.adapter._has_markdown_heading("body without heading") is False
        assert self.adapter._has_markdown_heading("\n\n# Title") is True

    def test_detects_bilingual_heading_title(self):
        assert self.adapter._heading_title_is_bilingual("出貨延遲檢討 / Shipping Delay Review") is True
        assert self.adapter._heading_title_is_bilingual("Shipping Delay Review / 出貨延遲檢討") is True
        assert self.adapter._heading_title_is_bilingual("PD One 測試") is False
        assert self.adapter._heading_title_is_bilingual("Shipping Delay Review") is False

    @pytest.mark.asyncio
    async def test_existing_heading_utility_output_must_preserve_source_text(self):
        class _Message:
            content = "Rewritten Thread Title / 改寫後標題"

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        with patch("plugins.platforms.mattermost.adapter.async_call_llm", new=AsyncMock(return_value=_Response())) as llm:
            title = await self.adapter._generate_thread_root_heading_title(
                "## Existing Thread Title\n\nBody",
                "reply",
                existing_heading_title="Existing Thread Title",
            )

        assert title is None
        llm.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_title_generation_failure_skips_heading(self):
        with patch(
            "plugins.platforms.mattermost.adapter.async_call_llm",
            new=AsyncMock(side_effect=RuntimeError("title api down")),
        ):
            title = await self.adapter._generate_thread_root_heading_title(
                "Can someone look at this?",
                "I can help",
            )

        assert title is None

    @pytest.mark.asyncio
    async def test_empty_utility_response_skips_heading(self):
        class _Message:
            content = ""

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        with patch(
            "plugins.platforms.mattermost.adapter.async_call_llm",
            new=AsyncMock(return_value=_Response()),
        ):
            title = await self.adapter._generate_thread_root_heading_title(
                "Can someone look at this?",
                "I can help",
            )

        assert title is None

    @pytest.mark.asyncio
    async def test_existing_heading_accepts_utility_translation_that_preserves_source_text(self):
        class _Message:
            content = "Existing Thread Title / 既有討論標題"

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        with patch("plugins.platforms.mattermost.adapter.async_call_llm", new=AsyncMock(return_value=_Response())):
            title = await self.adapter._generate_thread_root_heading_title(
                "## Existing Thread Title\n\nBody",
                "reply",
                existing_heading_title="Existing Thread Title",
            )

        assert title == "Existing Thread Title / 既有討論標題"

    @pytest.mark.asyncio
    async def test_thread_reply_adds_heading_before_mention_gate(self):
        self.adapter._api_get = AsyncMock(return_value={
            "id": "root_post",
            "message": "Can someone look at this?",
            "delete_at": 0,
        })
        self.adapter._generate_thread_root_heading_title = AsyncMock(return_value="出貨延遲檢討 / Shipping Delay Review")
        self.adapter._api_put = AsyncMock(return_value={"id": "root_post"})

        await self.adapter._handle_ws_event(self._reply_event("I can help"))

        self.adapter._api_put.assert_awaited_once_with(
            "posts/root_post/patch",
            {"message": "##### 出貨延遲檢討 / Shipping Delay Review\n\nCan someone look at this?"},
        )
        # No @mention in the reply, so the normal agent path should still be skipped.
        assert getattr(self.adapter.handle_message, "call_count") == 0

    @pytest.mark.asyncio
    async def test_own_thread_reply_adds_heading_but_does_not_reenter_agent(self):
        self.adapter._api_get = AsyncMock(return_value={
            "id": "root_post",
            "message": "Untitled user question",
            "delete_at": 0,
        })
        self.adapter._generate_thread_root_heading_title = AsyncMock(return_value="使用者問題 / User Question")
        self.adapter._api_put = AsyncMock(return_value={"id": "root_post"})
        event = self._reply_event("PD One answer")
        post = json.loads(event["data"]["post"])
        post["id"] = "bot_reply_post"
        post["user_id"] = "bot_user_id"
        event["data"]["post"] = json.dumps(post)
        event["data"]["sender_name"] = "@pd_one_bot"

        await self.adapter._handle_ws_event(event)

        self.adapter._api_put.assert_awaited_once_with(
            "posts/root_post/patch",
            {"message": "##### 使用者問題 / User Question\n\nUntitled user question"},
        )
        assert getattr(self.adapter.handle_message, "call_count") == 0

    @pytest.mark.asyncio
    async def test_thread_reply_updates_existing_non_bilingual_heading(self):
        self.adapter._api_get = AsyncMock(return_value={
            "id": "root_post",
            "message": "## Existing Thread Title\n\nBody",
            "delete_at": 0,
        })
        self.adapter._generate_thread_root_heading_title = AsyncMock(return_value="Existing Thread Title / 既有討論標題")
        self.adapter._api_put = AsyncMock(return_value={"id": "root_post"})

        await self.adapter._handle_ws_event(self._reply_event("another reply"))

        self.adapter._generate_thread_root_heading_title.assert_awaited_once_with(
            "## Existing Thread Title\n\nBody",
            "another reply",
            existing_heading_title="Existing Thread Title",
        )
        self.adapter._api_put.assert_awaited_once_with(
            "posts/root_post/patch",
            {"message": "## Existing Thread Title / 既有討論標題\n\nBody"},
        )

    @pytest.mark.asyncio
    async def test_thread_reply_skips_root_that_already_has_bilingual_heading(self):
        self.adapter._api_get = AsyncMock(return_value={
            "id": "root_post",
            "message": "## 既有討論標題 / Existing Thread Title\n\nBody",
            "delete_at": 0,
        })
        self.adapter._generate_thread_root_heading_title = AsyncMock(return_value="Ignored Title")
        self.adapter._api_put = AsyncMock(return_value={"id": "root_post"})

        await self.adapter._handle_ws_event(self._reply_event("another reply"))

        self.adapter._generate_thread_root_heading_title.assert_not_awaited()
        self.adapter._api_put.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_thread_reply_skips_when_disabled(self):
        self.adapter.config.extra["auto_thread_root_heading"] = False
        self.adapter._api_get = AsyncMock(return_value={"message": "Root"})
        self.adapter._api_put = AsyncMock(return_value={"id": "root_post"})

        await self.adapter._handle_ws_event(self._reply_event("another reply"))

        self.adapter._api_get.assert_not_awaited()
        self.adapter._api_put.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_thread_reply_skips_configured_disabled_channel(self):
        self.adapter.config.extra["auto_thread_root_heading_disabled_channels"] = ["chan_456"]
        self.adapter._api_get = AsyncMock(return_value={"message": "Root"})
        self.adapter._api_put = AsyncMock(return_value={"id": "root_post"})

        await self.adapter._handle_ws_event(self._reply_event("another reply"))

        self.adapter._api_get.assert_not_awaited()
        self.adapter._api_put.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_thread_reply_skips_patch_when_title_generation_fails(self):
        self.adapter._api_get = AsyncMock(return_value={
            "id": "root_post",
            "message": "Can someone look at this?",
            "delete_at": 0,
        })
        self.adapter._generate_thread_root_heading_title = AsyncMock(return_value=None)
        self.adapter._api_put = AsyncMock(return_value={"id": "root_post"})

        await self.adapter._handle_ws_event(self._reply_event("I can help"))

        self.adapter._generate_thread_root_heading_title.assert_awaited_once()
        self.adapter._api_put.assert_not_awaited()


class TestMattermostMentionTranslation:
    @pytest.mark.asyncio
    async def test_appends_utility_translation_when_enabled(self):
        adapter = _make_adapter()
        adapter.config.extra["auto_translate_mentioned_channel_messages"] = True
        adapter._generate_mention_translation = AsyncMock(return_value="請檢查今天的排程。")
        adapter._api_put = AsyncMock(return_value={"id": "post123"})
        post = {"id": "post123", "message": "@pd-one please check today's schedule."}

        await adapter._maybe_append_mention_translation(
            post,
            has_mention=True,
            channel_type_raw="O",
        )

        adapter._api_put.assert_awaited_once()
        path, payload = adapter._api_put.await_args.args
        assert path == "posts/post123/patch"
        assert "**Translation / 翻譯 (utility-agent):**" in payload["message"]
        assert "請檢查今天的排程。" in payload["message"]
        assert post["message"] == payload["message"]

    @pytest.mark.asyncio
    async def test_skips_dm_and_existing_translation_marker(self):
        adapter = _make_adapter()
        adapter.config.extra["auto_translate_mentioned_channel_messages"] = True
        adapter._generate_mention_translation = AsyncMock(return_value="translation")
        adapter._api_put = AsyncMock(return_value={"id": "post123"})

        await adapter._maybe_append_mention_translation(
            {"id": "post123", "message": "@pd-one hello"},
            has_mention=True,
            channel_type_raw="D",
        )
        await adapter._maybe_append_mention_translation(
            {"id": "post124", "message": "@pd-one hello\n\n**Translation / 翻譯 (utility-agent):**\n你好"},
            has_mention=True,
            channel_type_raw="O",
        )

        adapter._generate_mention_translation.assert_not_awaited()
        adapter._api_put.assert_not_awaited()

    def test_mixed_chinese_heading_with_english_instructions_targets_chinese(self):
        adapter = _make_adapter()
        message = (
            "#### 2026/06/15 邱老師面談（商周） / 2026/06/15 Interview with Teacher Chiu (Business Weekly)\n\n"
            "@pd_one_bot Transcribe this meeting consisting of two recordings, and provide a bilingual meeting report."
        )

        assert adapter._mention_translation_target_language(message) == "Traditional Chinese"

    @pytest.mark.asyncio
    async def test_mention_translation_prompt_warns_not_to_keep_english_instructions(self):
        adapter = _make_adapter()

        class _Message:
            content = "#### 2026/06/15 邱老師面談（商周）\n\n@pd_one_bot 請轉錄這場由兩段錄音組成的會議。"

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        message = (
            "#### 2026/06/15 邱老師面談（商周） / 2026/06/15 Interview with Teacher Chiu (Business Weekly)\n\n"
            "@pd_one_bot Transcribe this meeting consisting of two recordings, and provide a bilingual meeting report."
        )
        with patch("plugins.platforms.mattermost.adapter.async_call_llm", new=AsyncMock(return_value=_Response())) as llm:
            translated = await adapter._generate_mention_translation(message)

        assert "請轉錄" in translated
        call = llm.await_args.kwargs
        prompt_text = "\n".join(m["content"] for m in call["messages"])
        assert "into Traditional Chinese" in prompt_text
        assert "do not leave English instructions in English just because the heading contains Chinese" in prompt_text

    def test_yaml_bridge_exports_mention_translation_env(self, monkeypatch):
        from plugins.platforms.mattermost.adapter import _apply_yaml_config

        monkeypatch.delenv("MATTERMOST_AUTO_TRANSLATE_MENTIONED_CHANNEL_MESSAGES", raising=False)
        _apply_yaml_config({}, {"auto_translate_mentioned_channel_messages": True})

        assert os.environ["MATTERMOST_AUTO_TRANSLATE_MENTIONED_CHANNEL_MESSAGES"] == "true"

    def test_yaml_bridge_exports_ignored_channels_env(self, monkeypatch):
        from plugins.platforms.mattermost.adapter import _apply_yaml_config

        monkeypatch.delenv("MATTERMOST_IGNORED_CHANNELS", raising=False)
        _apply_yaml_config({}, {"ignored_channels": ["chanA", "chanB"]})

        assert os.environ["MATTERMOST_IGNORED_CHANNELS"] == "chanA,chanB"

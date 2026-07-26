"""Tests for Mattermost platform adapter."""
import json
import os
import time
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import MessageType
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

    def test_threaded_mattermost_progress_prefers_existing_thread_root(self):
        assert _resolve_progress_thread_id(
            Platform.MATTERMOST,
            source_thread_id="root_post_123",
            event_message_id="reply_post_456",
        ) == "root_post_123"

    def test_telegram_progress_does_not_use_message_id_as_thread_id(self):
        assert _resolve_progress_thread_id(
            Platform.TELEGRAM,
            source_thread_id=None,
            event_message_id="12345",
        ) is None


class TestMattermostDisplayHygiene:
    def test_mattermost_requires_platform_opt_in_for_interim_assistant_messages(self):
        """Global interim commentary must not make Mattermost leak scratch notes."""
        user_config = {"display": {"interim_assistant_messages": True}}

        assert _resolve_gateway_display_bool(
            user_config,
            "mattermost",
            "interim_assistant_messages",
            default=True,
            platform=Platform.MATTERMOST,
            require_platform_override_for={Platform.MATTERMOST},
        ) is False

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

    def test_mattermost_requires_platform_opt_in_for_thinking_progress(self):
        """Global thinking_progress must not surface internal analysis in Mattermost."""
        user_config = {"display": {"thinking_progress": True}}

        assert _resolve_gateway_display_bool(
            user_config,
            "mattermost",
            "thinking_progress",
            default=False,
            platform=Platform.MATTERMOST,
            require_platform_override_for={Platform.MATTERMOST},
        ) is False

    def test_mattermost_requires_platform_opt_in_for_show_reasoning(self):
        """Global show_reasoning must not prepend scratch reasoning in Mattermost."""
        user_config = {"display": {"show_reasoning": True}}

        assert _resolve_gateway_display_bool(
            user_config,
            "mattermost",
            "show_reasoning",
            default=False,
            platform=Platform.MATTERMOST,
            require_platform_override_for={Platform.MATTERMOST},
        ) is False

    def test_mattermost_platform_opt_in_can_enable_show_reasoning(self):
        user_config = {
            "display": {
                "show_reasoning": False,
                "platforms": {"mattermost": {"show_reasoning": True}},
            }
        }

        assert _resolve_gateway_display_bool(
            user_config,
            "mattermost",
            "show_reasoning",
            default=False,
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
    def test_apply_env_overrides_mattermost(self, monkeypatch):
        monkeypatch.setenv("MATTERMOST_TOKEN", "mm-tok-abc123")
        monkeypatch.setenv("MATTERMOST_URL", "https://mm.example.com")

        from gateway.config import GatewayConfig, _apply_env_overrides
        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.MATTERMOST in config.platforms
        mc = config.platforms[Platform.MATTERMOST]
        assert mc.enabled is True
        assert mc.token == "mm-tok-abc123"
        assert mc.extra.get("url") == "https://mm.example.com"

    def test_explicit_top_level_mattermost_disable_wins_over_env_credentials(
        self, monkeypatch, tmp_path
    ):
        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        (hermes_home / "config.yaml").write_text(
            "mattermost:\n"
            "  enabled: false\n"
            "  require_mention: true\n"
        )
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))
        monkeypatch.setenv("MATTERMOST_TOKEN", "mm-tok-abc123")
        monkeypatch.setenv("MATTERMOST_URL", "https://mm.example.com")

        from gateway.config import load_gateway_config

        config = load_gateway_config()
        mattermost = config.platforms[Platform.MATTERMOST]

        assert mattermost.enabled is False
        assert mattermost.token == "mm-tok-abc123"
        assert mattermost.extra.get("url") == "https://mm.example.com"
        assert "_enabled_explicit" not in mattermost.extra

    def test_mattermost_not_loaded_without_token(self, monkeypatch):
        monkeypatch.delenv("MATTERMOST_TOKEN", raising=False)
        monkeypatch.delenv("MATTERMOST_URL", raising=False)

        from gateway.config import GatewayConfig, _apply_env_overrides
        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.MATTERMOST not in config.platforms

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

    def test_mattermost_url_warning_without_url(self, monkeypatch):
        """MATTERMOST_TOKEN set but MATTERMOST_URL missing should still load."""
        monkeypatch.setenv("MATTERMOST_TOKEN", "mm-tok-abc123")
        monkeypatch.delenv("MATTERMOST_URL", raising=False)

        from gateway.config import GatewayConfig, _apply_env_overrides
        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.MATTERMOST in config.platforms
        assert config.platforms[Platform.MATTERMOST].extra.get("url") == ""


# ---------------------------------------------------------------------------
# Adapter format / truncate
# ---------------------------------------------------------------------------

def _make_adapter():
    """Create a MattermostAdapter with mocked config."""
    from plugins.platforms.mattermost.adapter import MattermostAdapter
    config = PlatformConfig(
        enabled=True,
        token="test-token",
        extra={"url": "https://mm.example.com", "pd_one_policy_bridge": False},
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

    def test_image_markdown_strips_alt_text(self):
        result = self.adapter.format_message("Here: ![my image](https://x.com/a.jpg) done")
        assert "![" not in result
        assert "https://x.com/a.jpg" in result

    def test_regular_markdown_preserved(self):
        """Regular markdown (bold, italic, code) should be kept as-is."""
        content = "**bold** and *italic* and `code`"
        assert self.adapter.format_message(content) == content

    def test_regular_links_preserved(self):
        """Non-image links should be preserved."""
        content = "[click](https://example.com)"
        assert self.adapter.format_message(content) == content

    def test_plain_text_unchanged(self):
        content = "Hello, world!"
        assert self.adapter.format_message(content) == content

    def test_multiple_images(self):
        content = "![a](http://a.com/1.png) text ![b](http://b.com/2.png)"
        result = self.adapter.format_message(content)
        assert "![" not in result
        assert "http://a.com/1.png" in result
        assert "http://b.com/2.png" in result


class TestMattermostTruncateMessage:
    def setup_method(self):
        self.adapter = _make_adapter()

    def test_short_message_single_chunk(self):
        msg = "Hello, world!"
        chunks = self.adapter.truncate_message(msg, 4000)
        assert len(chunks) == 1
        assert chunks[0] == msg

    def test_long_message_splits(self):
        msg = "a " * 2500  # 5000 chars
        chunks = self.adapter.truncate_message(msg, 4000)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 4000

    def test_custom_max_length(self):
        msg = "Hello " * 20
        chunks = self.adapter.truncate_message(msg, max_length=50)
        assert all(len(c) <= 50 for c in chunks)

    def test_exactly_at_limit(self):
        msg = "x" * 4000
        chunks = self.adapter.truncate_message(msg, 4000)
        assert len(chunks) == 1


# ---------------------------------------------------------------------------
# Gateway progress/status routing
# ---------------------------------------------------------------------------

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
    async def test_send_disables_mentions(self):
        """Bot-authored posts should not trigger @all/@channel notifications."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"id": "post123"})
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)

        result = await self.adapter.send("channel_1", "LLM says: @all restart")

        assert result.success is True
        payload = self.adapter._session.post.call_args[1]["json"]
        assert payload["message"] == "LLM says: @all restart"
        assert payload["props"]["disable_mentions"] is True

    @pytest.mark.asyncio
    async def test_send_empty_content_succeeds(self):
        """Empty content should return success without calling the API."""
        result = await self.adapter.send("channel_1", "")
        assert result.success is True

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
    async def test_send_uses_metadata_thread_id_as_root_id(self):
        """Status/progress sends carry thread context in metadata, not reply_to."""
        self.adapter._reply_mode = "thread"

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"id": "status_post"})
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_get_resp = AsyncMock()
        mock_get_resp.status = 200
        mock_get_resp.json = AsyncMock(return_value={"id": "root_post", "root_id": ""})
        mock_get_resp.text = AsyncMock(return_value="")
        mock_get_resp.__aenter__ = AsyncMock(return_value=mock_get_resp)
        mock_get_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)
        self.adapter._session.get = MagicMock(return_value=mock_get_resp)

        result = await self.adapter.send(
            "channel_1",
            "⏳ Still working...",
            metadata={"thread_id": "root_post"},
        )

        assert result.success is True
        payload = self.adapter._session.post.call_args[1]["json"]
        assert payload["root_id"] == "root_post"

    @pytest.mark.asyncio
    async def test_send_local_file_uses_metadata_thread_id_as_root_id(self, tmp_path):
        """MEDIA/file attachments must preserve thread metadata like text sends."""
        self.adapter._reply_mode = "thread"
        file_path = tmp_path / "chart.png"
        file_path.write_bytes(b"png-bytes")

        self.adapter._upload_file = AsyncMock(return_value="file_123")

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"id": "file_post"})
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_get_resp = AsyncMock()
        mock_get_resp.status = 200
        mock_get_resp.json = AsyncMock(return_value={"id": "thread_root", "root_id": ""})
        mock_get_resp.text = AsyncMock(return_value="")
        mock_get_resp.__aenter__ = AsyncMock(return_value=mock_get_resp)
        mock_get_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)
        self.adapter._session.get = MagicMock(return_value=mock_get_resp)

        result = await self.adapter.send_image_file(
            "channel_1",
            str(file_path),
            metadata={"thread_id": "thread_root"},
        )

        assert result.success is True
        payload = self.adapter._session.post.call_args[1]["json"]
        assert payload["file_ids"] == ["file_123"]
        assert payload["root_id"] == "thread_root"

    @pytest.mark.asyncio
    async def test_send_multiple_images_uses_metadata_thread_id_as_root_id(self, tmp_path):
        """Batched Mattermost image uploads must stay in the originating thread."""
        self.adapter._reply_mode = "thread"
        image_path = tmp_path / "chart.png"
        image_path.write_bytes(b"png-bytes")

        self.adapter._upload_file = AsyncMock(return_value="image_file_123")

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"id": "image_post"})
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_get_resp = AsyncMock()
        mock_get_resp.status = 200
        mock_get_resp.json = AsyncMock(return_value={"id": "thread_root", "root_id": ""})
        mock_get_resp.text = AsyncMock(return_value="")
        mock_get_resp.__aenter__ = AsyncMock(return_value=mock_get_resp)
        mock_get_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)
        self.adapter._session.get = MagicMock(return_value=mock_get_resp)

        await self.adapter.send_multiple_images(
            "channel_1",
            [(f"file://{image_path}", "")],
            metadata={"thread_id": "thread_root"},
        )

        payload = self.adapter._session.post.call_args[1]["json"]
        assert payload["file_ids"] == ["image_file_123"]
        assert payload["root_id"] == "thread_root"

    @pytest.mark.asyncio
    async def test_send_without_thread_no_root_id(self):
        """When reply_mode is 'off', reply_to should NOT set root_id."""
        self.adapter._reply_mode = "off"

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"id": "post789"})
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)

        result = await self.adapter.send("channel_1", "Reply!", reply_to="root_post")

        assert result.success is True
        payload = self.adapter._session.post.call_args[1]["json"]
        assert "root_id" not in payload


    @pytest.mark.asyncio
    async def test_send_uses_metadata_thread_id_for_progress_messages(self):
        """Progress/status messages pass Mattermost thread context via metadata."""
        self.adapter._reply_mode = "thread"
        self.adapter._api_get = AsyncMock(return_value={"id": "root_post_123", "root_id": ""})
        self.adapter._api_post = AsyncMock(return_value={"id": "progress_post"})

        result = await self.adapter.send(
            "channel_1",
            "⚡ terminal...",
            metadata={"thread_id": "root_post_123"},
        )

        assert result.success is True
        payload = self.adapter._api_post.call_args_list[0][0][1]
        assert payload["root_id"] == "root_post_123"

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
    async def test_notify_send_with_server_error_does_not_fall_back_flat(self):
        """Notify fallback is only for broken thread roots, not generic API failures."""
        self.adapter._reply_mode = "thread"
        self.adapter._api_get = AsyncMock(return_value={"id": "root_post", "root_id": ""})
        self.adapter._last_post_status = 500
        self.adapter._last_post_error = "Internal Server Error"
        self.adapter._api_post = AsyncMock(return_value={})

        result = await self.adapter.send(
            "channel_1",
            "Final answer body",
            reply_to="root_post",
            metadata={"notify": True},
        )

        assert result.success is False
        assert self.adapter._api_post.call_count == 1
        payload = self.adapter._api_post.call_args_list[0][0][1]
        assert payload["root_id"] == "root_post"

    @pytest.mark.asyncio
    async def test_progress_send_with_invalid_thread_root_never_falls_back_flat(self):
        """Tool/status/progress bubbles must stay quiet when the thread is broken."""
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

    @pytest.mark.asyncio
    async def test_send_api_failure(self):
        """When API returns error, send should return failure."""
        mock_resp = AsyncMock()
        mock_resp.status = 500
        mock_resp.json = AsyncMock(return_value={})
        mock_resp.text = AsyncMock(return_value="Internal Server Error")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)

        result = await self.adapter.send("channel_1", "Hello!")

        assert result.success is False

    @pytest.mark.asyncio
    async def test_send_typing_includes_thread_parent_id_from_metadata(self):
        """Threaded Mattermost typing indicators should include parent_id."""
        self.adapter._bot_user_id = "bot_user"
        self.adapter._api_post = AsyncMock(return_value={"status": "OK"})

        await self.adapter.send_typing("channel_1", metadata={"thread_id": "root_post"})

        self.adapter._api_post.assert_awaited_once_with(
            "users/bot_user/typing",
            {"channel_id": "channel_1", "parent_id": "root_post"},
        )

    @pytest.mark.asyncio
    async def test_processing_reactions_success_lifecycle(self):
        """Mattermost processing lifecycle should swap 👀 for ✅ on success."""
        from gateway.platforms.base import MessageEvent, ProcessingOutcome

        self.adapter._bot_user_id = "bot_user"
        self.adapter._api_post = AsyncMock(return_value={"ok": True})
        self.adapter._api_delete = AsyncMock(return_value=True)
        event = MessageEvent(text="hello", message_id="post_1")

        await self.adapter.on_processing_start(event)
        await self.adapter.on_processing_complete(event, ProcessingOutcome.SUCCESS)

        self.adapter._api_post.assert_any_await(
            "reactions",
            {"user_id": "bot_user", "post_id": "post_1", "emoji_name": "eyes"},
        )
        self.adapter._api_delete.assert_awaited_once_with(
            "users/bot_user/posts/post_1/reactions/eyes"
        )
        self.adapter._api_post.assert_any_await(
            "reactions",
            {"user_id": "bot_user", "post_id": "post_1", "emoji_name": "white_check_mark"},
        )

    @pytest.mark.asyncio
    async def test_processing_reactions_failure_lifecycle(self):
        """Mattermost processing lifecycle should swap 👀 for ❌ on failure."""
        from gateway.platforms.base import MessageEvent, ProcessingOutcome

        self.adapter._bot_user_id = "bot_user"
        self.adapter._api_post = AsyncMock(return_value={"ok": True})
        self.adapter._api_delete = AsyncMock(return_value=True)
        event = MessageEvent(text="hello", message_id="post_1")

        await self.adapter.on_processing_complete(event, ProcessingOutcome.FAILURE)

        self.adapter._api_post.assert_awaited_once_with(
            "reactions",
            {"user_id": "bot_user", "post_id": "post_1", "emoji_name": "x"},
        )

    @pytest.mark.asyncio
    async def test_delete_message_calls_api_delete(self):
        """delete_message() should delete the Mattermost post by ID."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.delete = MagicMock(return_value=mock_resp)

        result = await self.adapter.delete_message("channel_1", "post_to_delete")

        assert result is True
        call_args = self.adapter._session.delete.call_args
        assert "/api/v4/posts/post_to_delete" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_delete_message_failure_returns_false(self):
        mock_resp = AsyncMock()
        mock_resp.status = 403
        mock_resp.text = AsyncMock(return_value="Forbidden")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.delete = MagicMock(return_value=mock_resp)

        assert await self.adapter.delete_message("channel_1", "post_to_delete") is False

    @pytest.mark.asyncio
    async def test_delete_message_uses_transient_session_when_primary_closed(self):
        """Progress cleanup should still delete if the long-lived connector closed."""
        self.adapter._session.closed = True

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        transient_session = MagicMock()
        transient_session.delete = MagicMock(return_value=mock_resp)

        session_cm = AsyncMock()
        session_cm.__aenter__ = AsyncMock(return_value=transient_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=session_cm) as client_session:
            result = await self.adapter.delete_message("channel_1", "post_to_delete")

        assert result is True
        client_session.assert_called_once()
        call_args = transient_session.delete.call_args
        assert "/api/v4/posts/post_to_delete" in call_args[0][0]


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
    async def test_ignored_channel_is_silently_skipped_before_mention_processing(self):
        self.adapter.config.extra["ignored_channels"] = ["chan_ignored"]
        self.adapter._maybe_append_mention_translation = AsyncMock()
        post_data = {
            "id": "post_ignored",
            "user_id": "user_123",
            "channel_id": "chan_ignored",
            "message": "@hermes-bot should be owned by another runtime",
        }
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "O",
                "sender_name": "@alice",
            },
        }

        await self.adapter._handle_ws_event(event)

        assert not self.adapter.handle_message.called
        self.adapter._maybe_append_mention_translation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ignore_own_messages(self):
        """Messages from the bot's own user_id should be ignored."""
        post_data = {
            "id": "post_self",
            "user_id": "bot_user_id",  # same as bot
            "channel_id": "chan_456",
            "message": "Bot echo",
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
    async def test_ignore_non_posted_events(self):
        """Non-'posted' events should be ignored."""
        event = {
            "event": "typing",
            "data": {"user_id": "user_123"},
        }

        await self.adapter._handle_ws_event(event)
        assert not self.adapter.handle_message.called

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
    async def test_channel_type_mapping(self):
        """channel_type 'D' should map to 'dm'."""
        post_data = {
            "id": "post_dm",
            "user_id": "user_123",
            "channel_id": "chan_dm",
            "message": "DM message",
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
        assert msg_event.source.chat_type == "dm"

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

    @pytest.mark.asyncio
    async def test_leading_space_normal_text_is_preserved(self):
        """Only command-shaped mobile messages should be normalized."""
        post_data = {
            "id": "post_text",
            "user_id": "user_123",
            "channel_id": "chan_dm",
            "message": " hello",
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
        assert msg_event.text == " hello"
        assert msg_event.message_type is MessageType.TEXT

    @pytest.mark.asyncio
    async def test_thread_id_from_root_id(self):
        """Post with root_id should have thread_id set."""
        post_data = {
            "id": "post_reply",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@bot_user_id Thread reply",
            "root_id": "root_post_123",
        }
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "O",
                "sender_name": "@alice",
            },
        }

        await self.adapter._handle_ws_event(event)
        assert self.adapter.handle_message.called
        msg_event = self.adapter.handle_message.call_args[0][0]
        assert msg_event.source.thread_id == "root_post_123"

    @pytest.mark.asyncio
    async def test_root_channel_post_uses_own_post_id_as_thread_id(self):
        """Top-level Mattermost posts should get isolated sessions per post/thread."""
        post_data = {
            "id": "root_post_456",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@bot_user_id Start a separate task",
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

        await self.adapter._handle_ws_event(event)
        assert self.adapter.handle_message.called
        msg_event = self.adapter.handle_message.call_args[0][0]
        assert msg_event.source.thread_id == "root_post_456"

    @pytest.mark.asyncio
    async def test_thread_reply_fetches_root_thread_context(self):
        """A mention in an existing thread should prepend earlier thread posts."""
        post_data = {
            "id": "post_reply",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@bot_user_id What did we decide?",
            "root_id": "root_post_123",
        }
        self.adapter._api_get = AsyncMock(return_value={
            "order": ["root_post_123", "older_reply", "post_reply"],
            "posts": {
                "root_post_123": {
                    "id": "root_post_123",
                    "user_id": "user_root",
                    "message": "Original question before Hermes was mentioned",
                    "create_at": 1000,
                },
                "older_reply": {
                    "id": "older_reply",
                    "user_id": "user_older",
                    "message": "Earlier answer in the Mattermost thread",
                    "file_ids": ["prior_file_1"],
                    "create_at": 2000,
                },
                "post_reply": post_data,
            },
        })
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "O",
                "sender_name": "@alice",
            },
        }

        await self.adapter._handle_ws_event(event)

        self.adapter._api_get.assert_any_await("posts/root_post_123/thread")
        self.adapter._api_get.assert_any_await("files/prior_file_1/info")
        msg_event = self.adapter.handle_message.call_args[0][0]
        assert msg_event.source.thread_id == "root_post_123"
        assert "Mattermost thread context" in msg_event.channel_context
        assert "Original question before Hermes was mentioned" in msg_event.channel_context
        assert "Earlier answer in the Mattermost thread" in msg_event.channel_context
        assert "prior_file_1" in msg_event.channel_context
        assert "What did we decide?" not in msg_event.channel_context

    @pytest.mark.asyncio
    async def test_thread_context_fetch_failure_does_not_drop_message(self):
        """Thread API failures should not prevent the triggering mention from running."""
        post_data = {
            "id": "post_reply",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@bot_user_id Continue",
            "root_id": "root_post_123",
        }
        self.adapter._api_get = AsyncMock(side_effect=RuntimeError("thread unavailable"))
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "O",
                "sender_name": "@alice",
            },
        }

        await self.adapter._handle_ws_event(event)

        assert self.adapter.handle_message.called
        msg_event = self.adapter.handle_message.call_args[0][0]
        assert msg_event.text == "Continue"
        assert msg_event.channel_context is None

    @pytest.mark.asyncio
    async def test_pd_one_policy_bridge_injects_hermes_policy_context(self, tmp_path):
        """PD One profile can inject Hermes sender policy cache into context."""
        cache = tmp_path / "users"
        cache.mkdir()
        (cache / "user_123.json").write_text(json.dumps({
            "schema": "pd-one.mattermost-policy-resolution.v1",
            "found": True,
            "active": True,
            "decision": "allow_dm",
            "turnHandling": "scoped_dm_allowed",
            "language": "zh-tw",
            "roles": ["facilities"],
            "safeScopes": ["facilities", "appsheet-readonly"],
            "tools": {"reads": "allowed", "writes": "confirm"},
            "approval": {"writes": False, "gatewayRestart": False},
            "dataAccess": {"credentials": "deny", "operationalDocs": "read-summarize-only"},
            "setupResponse": {"en": "setup needed"},
        }), encoding="utf-8")
        self.adapter.config.extra.update({
            "pd_one_policy_bridge": True,
            "pd_one_hermes_policy_root": "/hermes/profiles/pdone",
            "pd_one_policy_cache_users": str(cache),
        })
        post_data = {
            "id": "post_root",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@bot_user_id Can I update this?",
        }
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "O",
                "sender_name": "@alice",
            },
        }

        await self.adapter._handle_ws_event(event)

        msg_event = self.adapter.handle_message.call_args[0][0]
        assert "PD One Hermes permission bridge" in msg_event.channel_context
        assert '"requesterMattermostUserId":"user_123"' in msg_event.channel_context
        assert '"roles":["facilities"]' in msg_event.channel_context
        assert '"dataAccessSummary"' in msg_event.channel_context
        assert '"denied":["credentials"]' in msg_event.channel_context
        assert '"read_limited":["operationalDocs"]' in msg_event.channel_context
        assert "mattermost-channels.md" in msg_event.channel_context
        assert "require approved-user authorization" in msg_event.channel_context

    @pytest.mark.asyncio
    async def test_pd_one_policy_bridge_missing_cache_marks_lookup_failure(self, tmp_path):
        """Missing Hermes policy cache entries are explicit, not silent allows."""
        cache = tmp_path / "users"
        cache.mkdir()
        self.adapter.config.extra.update({
            "pd_one_policy_bridge": True,
            "pd_one_hermes_policy_root": "/hermes/profiles/pdone",
            "pd_one_policy_cache_users": str(cache),
        })
        post_data = {
            "id": "post_root",
            "user_id": "unknown_user",
            "channel_id": "chan_456",
            "message": "@bot_user_id Help me",
        }
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "O",
                "sender_name": "@unknown",
            },
        }

        await self.adapter._handle_ws_event(event)

        msg_event = self.adapter.handle_message.call_args[0][0]
        assert "PD One Hermes permission bridge" in msg_event.channel_context
        assert '"found":false' in msg_event.channel_context
        assert "stop scoped work" in msg_event.channel_context

    @pytest.mark.asyncio
    async def test_invalid_post_json_ignored(self):
        """Invalid JSON in data.post should be silently ignored."""
        event = {
            "event": "posted",
            "data": {
                "post": "not-valid-json{{{",
                "channel_type": "O",
            },
        }

        await self.adapter._handle_ws_event(event)
        assert not self.adapter.handle_message.called


class TestMattermostMissedMentionBackfill:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        self.adapter._bot_username = "pd_one_bot"
        self.adapter.handle_message = AsyncMock()
        self.adapter._backfill_watermark_ms = 1000
        self.adapter._backfill_overlap_seconds = 0
        self.adapter._backfill_seen_ttl_seconds = 3600
        self.adapter._backfill_unreplied_lookback_seconds = 21600

    @pytest.mark.asyncio
    async def test_backfill_replays_recent_mention_through_normal_parser(self):
        post = {
            "id": "missed_post",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@pd_one_bot Confirmed, apply it",
            "create_at": 2000,
        }

        async def fake_get(path):
            if path == "users/me/teams":
                return [{"id": "team_1"}]
            if path == "channels/chan_456":
                return {"id": "chan_456", "type": "O"}
            return {}

        async def fake_post(path, payload):
            assert path == "teams/team_1/posts/search"
            assert payload["terms"] == "@pd_one_bot"
            return {"order": ["missed_post"], "posts": {"missed_post": post}}

        self.adapter._api_get = AsyncMock(side_effect=fake_get)
        self.adapter._api_post = AsyncMock(side_effect=fake_post)

        replayed = await self.adapter._run_backfill_once()

        assert replayed == 1
        assert self.adapter._backfill_watermark_ms == 2000
        msg_event = self.adapter.handle_message.call_args[0][0]
        assert msg_event.message_id == "missed_post"
        assert msg_event.text == "Confirmed, apply it"
        assert msg_event.source.thread_id == "missed_post"

    @pytest.mark.asyncio
    async def test_backfill_skips_recent_mention_when_bot_already_replied_in_thread(self):
        post = {
            "id": "recent_replied_post",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@pd_one_bot how are reminders generated?",
            "root_id": "thread_root",
            "create_at": 2000,
        }
        bot_reply = {
            "id": "bot_reply_after",
            "user_id": "bot_user_id",
            "channel_id": "chan_456",
            "message": "Handled",
            "root_id": "thread_root",
            "create_at": 2500,
        }
        self.adapter._backfill_watermark_ms = 2000
        self.adapter._backfill_overlap_seconds = 600
        self.adapter._backfill_seen_post_ids = {}

        async def fake_get(path):
            if path == "users/me/teams":
                return [{"id": "team_1"}]
            if path == "posts/thread_root/thread":
                return {
                    "order": ["recent_replied_post", "bot_reply_after"],
                    "posts": {"recent_replied_post": post, "bot_reply_after": bot_reply},
                }
            return {}

        self.adapter._api_get = AsyncMock(side_effect=fake_get)
        self.adapter._api_post = AsyncMock(return_value={"order": ["recent_replied_post"], "posts": {"recent_replied_post": post}})

        replayed = await self.adapter._run_backfill_once()

        assert replayed == 0
        assert not self.adapter.handle_message.called
        assert "recent_replied_post" in self.adapter._backfill_seen_post_ids

    @pytest.mark.asyncio
    async def test_backfill_bot_replied_skip_uses_seen_cache_on_repeated_poll(self):
        post = {
            "id": "recent_replied_post",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@pd_one_bot how are reminders generated?",
            "root_id": "thread_root",
            "create_at": 2000,
        }
        bot_reply = {
            "id": "bot_reply_after",
            "user_id": "bot_user_id",
            "channel_id": "chan_456",
            "message": "Handled",
            "root_id": "thread_root",
            "create_at": 2500,
        }
        self.adapter._backfill_watermark_ms = 2000
        self.adapter._backfill_overlap_seconds = 600
        self.adapter._backfill_seen_post_ids = {}

        async def fake_get(path):
            if path == "users/me/teams":
                return [{"id": "team_1"}]
            if path == "posts/thread_root/thread":
                return {
                    "order": ["recent_replied_post", "bot_reply_after"],
                    "posts": {"recent_replied_post": post, "bot_reply_after": bot_reply},
                }
            return {}

        self.adapter._api_get = AsyncMock(side_effect=fake_get)
        self.adapter._api_post = AsyncMock(return_value={"order": ["recent_replied_post"], "posts": {"recent_replied_post": post}})

        assert await self.adapter._run_backfill_once() == 0
        assert await self.adapter._run_backfill_once() == 0
        thread_fetches = [call.args[0] for call in self.adapter._api_get.await_args_list if call.args[0] == "posts/thread_root/thread"]
        assert thread_fetches == ["posts/thread_root/thread"]
        assert not self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_backfill_preserves_thread_root_for_missed_reply(self):
        post = {
            "id": "missed_reply",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@pd_one_bot continue",
            "root_id": "thread_root",
            "create_at": 3000,
        }

        async def fake_get(path):
            if path == "users/me/teams":
                return [{"id": "team_1"}]
            if path == "channels/chan_456":
                return {"id": "chan_456", "type": "O"}
            if path == "posts/thread_root/thread":
                return {"order": ["thread_root", "missed_reply"], "posts": {"missed_reply": post}}
            return {}

        self.adapter._api_get = AsyncMock(side_effect=fake_get)
        self.adapter._api_post = AsyncMock(return_value={"order": ["missed_reply"], "posts": {"missed_reply": post}})

        await self.adapter._run_backfill_once()

        msg_event = self.adapter.handle_message.call_args[0][0]
        assert msg_event.message_id == "missed_reply"
        assert msg_event.source.thread_id == "thread_root"

    @pytest.mark.asyncio
    async def test_backfill_skips_posts_older_than_overlap_window(self):
        old_post = {
            "id": "old_post",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@pd_one_bot old",
            "create_at": 999,
        }
        self.adapter._api_get = AsyncMock(return_value=[{"id": "team_1"}])
        self.adapter._api_post = AsyncMock(return_value={"order": ["old_post"], "posts": {"old_post": old_post}})

        replayed = await self.adapter._run_backfill_once()

        assert replayed == 0
        assert not self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_backfill_replays_older_unreplied_mention_within_unreplied_lookback(self):
        old_unreplied_post = {
            "id": "old_unreplied_post",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@pd_one_bot still needs a reply",
            "create_at": 500,
        }

        async def fake_get(path):
            if path == "users/me/teams":
                return [{"id": "team_1"}]
            if path == "posts/old_unreplied_post/thread":
                return {"order": ["old_unreplied_post"], "posts": {"old_unreplied_post": old_unreplied_post}}
            if path == "channels/chan_456":
                return {"id": "chan_456", "type": "O"}
            return {}

        self.adapter._api_get = AsyncMock(side_effect=fake_get)
        self.adapter._api_post = AsyncMock(return_value={"order": ["old_unreplied_post"], "posts": {"old_unreplied_post": old_unreplied_post}})

        with patch("plugins.platforms.mattermost.adapter.time.time", return_value=7.0):
            replayed = await self.adapter._run_backfill_once()

        assert replayed == 1
        msg_event = self.adapter.handle_message.call_args[0][0]
        assert msg_event.message_id == "old_unreplied_post"

    @pytest.mark.asyncio
    async def test_backfill_skips_older_mention_when_bot_already_replied_in_thread(self):
        old_replied_post = {
            "id": "old_replied_post",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@pd_one_bot already handled",
            "create_at": 500,
        }
        bot_reply = {
            "id": "bot_reply",
            "user_id": "bot_user_id",
            "channel_id": "chan_456",
            "message": "Handled",
            "create_at": 750,
        }

        async def fake_get(path):
            if path == "users/me/teams":
                return [{"id": "team_1"}]
            if path == "posts/old_replied_post/thread":
                return {
                    "order": ["old_replied_post", "bot_reply"],
                    "posts": {"old_replied_post": old_replied_post, "bot_reply": bot_reply},
                }
            return {}

        self.adapter._api_get = AsyncMock(side_effect=fake_get)
        self.adapter._api_post = AsyncMock(return_value={"order": ["old_replied_post"], "posts": {"old_replied_post": old_replied_post}})

        with patch("plugins.platforms.mattermost.adapter.time.time", return_value=7.0):
            replayed = await self.adapter._run_backfill_once()

        assert replayed == 0
        assert not self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_backfill_long_overlap_catches_multi_minute_late_mentions(self):
        delayed_post = {
            "id": "delayed_post",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@pd_one_bot delayed by minutes",
            "create_at": 5000,
        }
        self.adapter._backfill_watermark_ms = 600_000
        self.adapter._backfill_overlap_seconds = 600

        async def fake_get(path):
            if path == "users/me/teams":
                return [{"id": "team_1"}]
            if path == "channels/chan_456":
                return {"id": "chan_456", "type": "O"}
            return {}

        self.adapter._api_get = AsyncMock(side_effect=fake_get)
        self.adapter._api_post = AsyncMock(return_value={"order": ["delayed_post"], "posts": {"delayed_post": delayed_post}})

        replayed = await self.adapter._run_backfill_once()

        assert replayed == 1
        msg_event = self.adapter.handle_message.call_args[0][0]
        assert msg_event.message_id == "delayed_post"

    @pytest.mark.asyncio
    async def test_backfill_seen_cache_prevents_replay_inside_long_overlap(self):
        post = {
            "id": "repeat_post",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@pd_one_bot only once",
            "create_at": 2000,
        }

        async def fake_get(path):
            if path == "users/me/teams":
                return [{"id": "team_1"}]
            if path == "channels/chan_456":
                return {"id": "chan_456", "type": "O"}
            return {}

        self.adapter._api_get = AsyncMock(side_effect=fake_get)
        self.adapter._api_post = AsyncMock(return_value={"order": ["repeat_post"], "posts": {"repeat_post": post}})

        assert await self.adapter._run_backfill_once() == 1
        assert await self.adapter._run_backfill_once() == 0
        assert self.adapter.handle_message.await_count == 1

    @pytest.mark.asyncio
    async def test_backfill_skips_expired_posts_before_thread_lookup(self):
        expired_post = {
            "id": "expired_post",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@pd_one_bot expired",
            "create_at": 500,
        }
        self.adapter._backfill_watermark_ms = 10_000
        self.adapter._backfill_overlap_seconds = 1
        self.adapter._backfill_unreplied_lookback_seconds = 1

        async def fake_get(path):
            if path == "users/me/teams":
                return [{"id": "team_1"}]
            raise AssertionError(f"expired post should not fetch thread/channel: {path}")

        self.adapter._api_get = AsyncMock(side_effect=fake_get)
        self.adapter._api_post = AsyncMock(return_value={"order": ["expired_post"], "posts": {"expired_post": expired_post}})

        with patch("plugins.platforms.mattermost.adapter.time.time", return_value=10.0):
            replayed = await self.adapter._run_backfill_once()

        assert replayed == 0
        assert not self.adapter.handle_message.called
        assert [call.args[0] for call in self.adapter._api_get.await_args_list] == ["users/me/teams"]


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
    async def test_require_mention_false_responds_to_all(self):
        """MATTERMOST_REQUIRE_MENTION=false: respond to all channel messages."""
        with patch.dict(os.environ, {"MATTERMOST_REQUIRE_MENTION": "false"}):
            await self.adapter._handle_ws_event(self._make_event("hello"))
            assert self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_config_require_mention_false_responds_to_all(self):
        """config.extra require_mention=false should respond without env vars."""
        self.adapter.config.extra["require_mention"] = False
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MATTERMOST_REQUIRE_MENTION", None)
            os.environ.pop("MATTERMOST_FREE_RESPONSE_CHANNELS", None)
            await self.adapter._handle_ws_event(self._make_event("hello"))
            assert self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_free_response_channel_responds_without_mention(self):
        """Messages in free-response channels don't need @mention."""
        with patch.dict(os.environ, {"MATTERMOST_FREE_RESPONSE_CHANNELS": "chan_456,chan_789"}):
            os.environ.pop("MATTERMOST_REQUIRE_MENTION", None)
            await self.adapter._handle_ws_event(self._make_event("hello", channel_id="chan_456"))
            assert self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_config_free_response_channel_responds_without_mention(self):
        """config.extra free_response_channels should bypass mention requirement."""
        self.adapter.config.extra["free_response_channels"] = ["chan_456", "chan_789"]
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MATTERMOST_REQUIRE_MENTION", None)
            os.environ.pop("MATTERMOST_FREE_RESPONSE_CHANNELS", None)
            await self.adapter._handle_ws_event(self._make_event("hello", channel_id="chan_456"))
            assert self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_non_free_channel_still_requires_mention(self):
        """Channels NOT in free-response list still require @mention."""
        with patch.dict(os.environ, {"MATTERMOST_FREE_RESPONSE_CHANNELS": "chan_789"}):
            os.environ.pop("MATTERMOST_REQUIRE_MENTION", None)
            await self.adapter._handle_ws_event(self._make_event("hello", channel_id="chan_456"))
            assert not self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_dm_always_responds(self):
        """DMs (channel_type=D) always respond regardless of mention settings."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MATTERMOST_REQUIRE_MENTION", None)
            await self.adapter._handle_ws_event(self._make_event("hello", channel_type="D"))
            assert self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_mention_stripped_from_text(self):
        """@mention is stripped from message text."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MATTERMOST_REQUIRE_MENTION", None)
            await self.adapter._handle_ws_event(
                self._make_event("@hermes-bot what is 2+2")
            )
            assert self.adapter.handle_message.called
            msg = self.adapter.handle_message.call_args[0][0]
            assert "@hermes-bot" not in msg.text
            assert "2+2" in msg.text


# ---------------------------------------------------------------------------
# File upload (send_image)
# ---------------------------------------------------------------------------

class TestMattermostFileUpload:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._session = MagicMock()

    def test_unicode_filename_is_not_percent_encoded(self):
        """Mattermost should receive the original UTF-8 attachment name."""
        from plugins.platforms.mattermost.adapter import _build_file_upload_form

        filename = "器管-20260709-01-宿舍規定違反懲處公告_中英.docx"
        form = _build_file_upload_form(
            "channel_1",
            b"fake-docx",
            filename,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        payload = form()
        file_disposition = payload._parts[1][0].headers["Content-Disposition"]

        assert f'filename="{filename}"' in file_disposition
        assert "%E5" not in file_disposition

    def test_upload_filename_replaces_header_control_characters(self):
        from plugins.platforms.mattermost.adapter import _build_file_upload_form

        form = _build_file_upload_form("channel_1", b"data", "report\r\nInjected.txt")
        file_disposition = form()._parts[1][0].headers["Content-Disposition"]

        assert "report__Injected.txt" in file_disposition
        assert "\r" not in file_disposition
        assert "\n" not in file_disposition

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
# Passive thread root heading automation
# ---------------------------------------------------------------------------

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

    def test_fallback_thread_root_heading_title_is_bilingual(self):
        assert self.adapter._fallback_thread_root_heading_title("請幫忙確認出貨延遲") == "請幫忙確認出貨延遲 / Thread Discussion"
        assert self.adapter._fallback_thread_root_heading_title("Shipping delay needs review") == "討論串 / Shipping delay needs review"

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

        assert title == "Existing Thread Title / 討論串"
        llm.assert_awaited_once()

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


# ---------------------------------------------------------------------------
# Dedup cache
# ---------------------------------------------------------------------------

class TestMattermostDedup:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        # Mock handle_message to capture calls without processing
        self.adapter.handle_message = AsyncMock()

    @pytest.mark.asyncio
    async def test_duplicate_post_ignored(self):
        """The same post_id within the TTL window should be ignored."""
        post_data = {
            "id": "post_dup",
            "user_id": "user_123",
            "channel_id": "chan_456",
            "message": "@bot_user_id Hello!",
        }
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(post_data),
                "channel_type": "O",
                "sender_name": "@alice",
            },
        }

        # First time: should process
        await self.adapter._handle_ws_event(event)
        assert self.adapter.handle_message.call_count == 1

        # Second time (same post_id): should be deduped
        await self.adapter._handle_ws_event(event)
        assert self.adapter.handle_message.call_count == 1  # still 1

    @pytest.mark.asyncio
    async def test_different_post_ids_both_processed(self):
        """Different post IDs should both be processed."""
        for i, pid in enumerate(["post_a", "post_b"]):
            post_data = {
                "id": pid,
                "user_id": "user_123",
                "channel_id": "chan_456",
                "message": f"@bot_user_id Message {i}",
            }
            event = {
                "event": "posted",
                "data": {
                    "post": json.dumps(post_data),
                    "channel_type": "O",
                    "sender_name": "@alice",
                },
            }
            await self.adapter._handle_ws_event(event)

        assert self.adapter.handle_message.call_count == 2

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

    def test_seen_cache_tracks_post_ids(self):
        """Posts are tracked in the dedup cache."""
        self.adapter._dedup._seen["test_post"] = time.time()
        assert "test_post" in self.adapter._dedup._seen


# ---------------------------------------------------------------------------
# Requirements check
# ---------------------------------------------------------------------------

class TestMattermostRequirements:
    def test_check_requirements_with_token_and_url(self, monkeypatch):
        monkeypatch.setenv("MATTERMOST_TOKEN", "test-token")
        monkeypatch.setenv("MATTERMOST_URL", "https://mm.example.com")
        from plugins.platforms.mattermost.adapter import check_mattermost_requirements
        assert check_mattermost_requirements() is True

    def test_check_requirements_without_token(self, monkeypatch):
        monkeypatch.delenv("MATTERMOST_TOKEN", raising=False)
        monkeypatch.delenv("MATTERMOST_URL", raising=False)
        from plugins.platforms.mattermost.adapter import check_mattermost_requirements
        assert check_mattermost_requirements() is True

    def test_check_requirements_without_url(self, monkeypatch):
        monkeypatch.setenv("MATTERMOST_TOKEN", "test-token")
        monkeypatch.delenv("MATTERMOST_URL", raising=False)
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

    def test_validate_config_rejects_missing_url(self, monkeypatch):
        monkeypatch.delenv("MATTERMOST_URL", raising=False)
        from plugins.platforms.mattermost.adapter import validate_mattermost_config

        config = PlatformConfig(enabled=True, token="cfg-token", extra={})
        assert validate_mattermost_config(config) is False


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
    async def test_audio_media_type_is_full_mime(self):
        """An audio attachment should produce 'audio/ogg', not 'audio'."""
        file_info = {"name": "voice.ogg", "mime_type": "audio/ogg"}
        self.adapter._api_get = AsyncMock(return_value=file_info)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"OGG fake")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        self.adapter._session = MagicMock()
        self.adapter._session.get = MagicMock(return_value=mock_resp)

        with patch("gateway.platforms.base.cache_audio_from_bytes", return_value="/tmp/voice.ogg"), \
             patch("gateway.platforms.base.cache_image_from_bytes"), \
             patch("gateway.platforms.base.cache_document_from_bytes"):
            await self.adapter._handle_ws_event(self._make_event(["file2"]))

        msg = self.adapter.handle_message.call_args[0][0]
        assert msg.media_types == ["audio/ogg"]
        assert msg.media_types[0].startswith("audio/")

    @pytest.mark.asyncio
    async def test_document_media_type_is_full_mime(self):
        """A document attachment should produce 'application/pdf', not 'document'."""
        file_info = {"name": "report.pdf", "mime_type": "application/pdf"}
        self.adapter._api_get = AsyncMock(return_value=file_info)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"PDF fake")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        self.adapter._session = MagicMock()
        self.adapter._session.get = MagicMock(return_value=mock_resp)

        with patch("gateway.platforms.base.cache_document_from_bytes", return_value="/tmp/report.pdf"), \
             patch("gateway.platforms.base.cache_image_from_bytes"):
            await self.adapter._handle_ws_event(self._make_event(["file3"]))

        msg = self.adapter.handle_message.call_args[0][0]
        assert msg.media_types == ["application/pdf"]
        assert not msg.media_types[0].startswith("image/")
        assert not msg.media_types[0].startswith("audio/")

    @pytest.mark.asyncio
    async def test_attachment_download_uses_large_file_timeout(self):
        """Slow valid Mattermost files should not be capped by the JSON API 30s timeout."""
        self.adapter.config.extra["file_download_timeout"] = 900
        self.adapter.config.extra["file_download_sock_read_timeout"] = 180
        file_info = {"name": "料桶.抽料機清潔.pptx", "mime_type": "application/octet-stream"}
        self.adapter._api_get = AsyncMock(return_value=file_info)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"PK\x03\x04 fake pptx")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        self.adapter._session = MagicMock()
        mock_get = MagicMock(return_value=mock_resp)
        self.adapter._session.get = mock_get

        with patch("gateway.platforms.base.cache_document_from_bytes", return_value="/tmp/cleaning.pptx"):
            await self.adapter._handle_ws_event(self._make_event(["slow_pptx"]))

        timeout = mock_get.call_args.kwargs["timeout"]
        assert timeout.total == 900
        assert timeout.sock_read == 180
        msg = self.adapter.handle_message.call_args[0][0]
        assert msg.media_urls == ["/tmp/cleaning.pptx"]
        assert msg.media_types == ["application/octet-stream"]



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


@pytest.mark.asyncio
async def test_mattermost_dm_post_does_not_seed_thread_root():
    adapter = _make_adapter()
    adapter._reply_mode = "thread"
    adapter._bot_user_id = "bot_user_id"
    adapter._bot_username = "hermes-bot"
    adapter.handle_message = AsyncMock()
    post_data = {
        "id": "dm_post_123",
        "user_id": "user_123",
        "channel_id": "dm_chan",
        "message": "hello",
        "root_id": "",
    }
    event = {
        "event": "posted",
        "data": {
            "post": json.dumps(post_data),
            "channel_type": "D",
            "sender_name": "@alice",
        },
    }

    await adapter._handle_ws_event(event)

    msg_event = adapter.handle_message.call_args[0][0]
    assert msg_event.source.thread_id is None
    assert msg_event.source.message_id == "dm_post_123"
class TestMattermostThreadRehydrationCache:
    """Thread rehydration should avoid re-sending already loaded context/files."""

    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"

    @pytest.mark.asyncio
    async def test_same_session_only_returns_unseen_thread_posts_and_files(self):
        thread = {
            "order": ["root", "old_reply", "new_reply", "trigger"],
            "posts": {
                "root": {
                    "id": "root",
                    "user_id": "user_root",
                    "message": "Root context",
                    "file_ids": ["root_file"],
                    "create_at": 1,
                },
                "old_reply": {
                    "id": "old_reply",
                    "user_id": "user_old",
                    "message": "Already loaded reply",
                    "file_ids": ["old_file"],
                    "create_at": 2,
                },
                "new_reply": {
                    "id": "new_reply",
                    "user_id": "user_new",
                    "message": "Fresh reply",
                    "file_ids": ["new_file"],
                    "create_at": 3,
                },
                "trigger": {
                    "id": "trigger",
                    "user_id": "user_trigger",
                    "message": "@bot_user_id latest request",
                    "file_ids": [],
                    "create_at": 4,
                },
            },
        }
        self.adapter._api_get = AsyncMock(return_value=thread)

        first_context, first_files = await self.adapter._fetch_thread_context(
            "root",
            "old_reply",
            session_key="agent:main:mattermost:channel:chan:root",
        )
        second_context, second_files = await self.adapter._fetch_thread_context(
            "root",
            "trigger",
            session_key="agent:main:mattermost:channel:chan:root",
        )

        assert "Root context" in first_context
        assert "Fresh reply" in first_context
        assert first_files == ["root_file", "new_file"]
        assert second_context is None
        assert second_files == []

    @pytest.mark.asyncio
    async def test_different_session_rehydrates_independently(self):
        thread = {
            "order": ["root", "trigger"],
            "posts": {
                "root": {
                    "id": "root",
                    "user_id": "user_root",
                    "message": "Root context",
                    "file_ids": ["root_file"],
                    "create_at": 1,
                },
                "trigger": {
                    "id": "trigger",
                    "user_id": "user_trigger",
                    "message": "@bot_user_id latest request",
                    "file_ids": [],
                    "create_at": 2,
                },
            },
        }
        self.adapter._api_get = AsyncMock(return_value=thread)

        first_context, first_files = await self.adapter._fetch_thread_context(
            "root",
            "trigger",
            session_key="session-a",
        )
        second_context, second_files = await self.adapter._fetch_thread_context(
            "root",
            "trigger",
            session_key="session-b",
        )

        assert "Root context" in first_context
        assert first_files == ["root_file"]
        assert "Root context" in second_context
        assert second_files == ["root_file"]


# ---------------------------------------------------------------------------
# Mention translation append
# ---------------------------------------------------------------------------

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

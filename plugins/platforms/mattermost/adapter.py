"""Mattermost gateway adapter.

Connects to a self-hosted (or cloud) Mattermost instance via its REST API
(v4) and WebSocket for real-time events.  No external Mattermost library
required — uses aiohttp which is already a Hermes dependency.

Environment variables:
    MATTERMOST_URL              Server URL (e.g. https://mm.example.com)
    MATTERMOST_TOKEN            Bot token or personal-access token
    MATTERMOST_ALLOWED_USERS    Comma-separated user IDs
    MATTERMOST_HOME_CHANNEL     Channel ID for cron/notification delivery
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent.auxiliary_client import async_call_llm

from gateway.config import Platform, PlatformConfig
from gateway.platforms.helpers import MessageDeduplicator
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
)

from agent.secret_scope import UnscopedSecretError as _UnscopedSecretError
from agent.secret_scope import get_secret as _scoped_get_secret


def _get_scoped_secret(name, default=None):
    """Scope-aware credential read with the default-profile startup fallback.

    Secondary profiles construct their adapters under a profile secret
    scope -- the scope is authoritative and a scoped miss returns ``default``
    (no cross-profile borrow from ``os.environ``, which may hold another
    profile's value). The DEFAULT profile's adapter constructs and sends
    *unscoped* under multiplexing, where a bare ``get_secret`` would raise
    ``UnscopedSecretError`` and crash this path; there ``os.environ`` is that
    profile's own value, so fall back to it. Same pattern as the Slack
    ``SLACK_APP_TOKEN`` read (#59739) and
    ``gateway/platforms/whatsapp_common.py::_get_wsecret``.
    """
    try:
        val = _scoped_get_secret(name, default)
    except _UnscopedSecretError:
        val = os.getenv(name)
    return val if val is not None else default


logger = logging.getLogger(__name__)

# Mattermost post size limit (server default is 16383, but 4000 is the
# practical limit for readable messages — matching OpenClaw's choice).
MAX_POST_LENGTH = 4000

# Channel type codes returned by the Mattermost API.
_CHANNEL_TYPE_MAP = {
    "D": "dm",
    "G": "group",
    "P": "group",   # private channel → treat as group
    "O": "channel",
}

_MATTERMOST_DISABLE_MENTIONS_PROPS = {"disable_mentions": True}

# Reconnect parameters (exponential backoff).
_RECONNECT_BASE_DELAY = 2.0
_RECONNECT_MAX_DELAY = 60.0
_RECONNECT_JITTER = 0.2


def _build_file_upload_form(
    channel_id: str,
    file_data: bytes,
    filename: str,
    content_type: Optional[str] = None,
):
    """Build Mattermost upload form without percent-encoding Unicode names.

    aiohttp's default ``quote_fields=True`` percent-encodes non-ASCII
    characters in the multipart ``filename`` parameter. Mattermost stores
    that encoded value literally, so a file such as ``報告.docx`` appears as
    ``%E5%A0%B1%E5%91%8A.docx``. Mattermost accepts UTF-8 filenames directly,
    matching browser and requests-based uploads. Strip header control
    characters before disabling aiohttp's field quoting.
    """
    import aiohttp

    safe_filename = re.sub(r"[\x00-\x1f\x7f]", "_", filename)
    form = aiohttp.FormData(quote_fields=False)
    form.add_field("channel_id", channel_id)
    file_kwargs: Dict[str, Any] = {"filename": safe_filename}
    if content_type:
        file_kwargs["content_type"] = content_type
    form.add_field("files", file_data, **file_kwargs)
    return form


def _with_mentions_disabled(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a post payload that prevents Mattermost from firing mentions."""
    props = payload.get("props")
    if isinstance(props, dict):
        payload["props"] = {**props, **_MATTERMOST_DISABLE_MENTIONS_PROPS}
    else:
        payload["props"] = dict(_MATTERMOST_DISABLE_MENTIONS_PROPS)
    return payload


def check_mattermost_requirements() -> bool:
    """Return True if the Mattermost adapter runtime dependency is available."""
    try:
        import aiohttp  # noqa: F401
        return True
    except ImportError:
        logger.warning("Mattermost: aiohttp not installed")
        return False


def validate_mattermost_config(config: PlatformConfig) -> bool:
    """Return True when Mattermost has enough config to connect."""
    extra = getattr(config, "extra", {}) or {}
    token = (getattr(config, "token", None) or _get_scoped_secret("MATTERMOST_TOKEN", "")).strip()
    url = (extra.get("url", "") or os.getenv("MATTERMOST_URL", "")).strip()
    if not token:
        logger.debug("Mattermost: MATTERMOST_TOKEN not set")
        return False
    if not url:
        logger.warning("Mattermost: MATTERMOST_URL not set")
        return False
    return True


class MattermostAdapter(BasePlatformAdapter):
    """Gateway adapter for Mattermost (self-hosted or cloud)."""

    splits_long_messages = True  # send() chunks via truncate_message(MAX_POST_LENGTH)

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.MATTERMOST)

        self._base_url: str = (
            config.extra.get("url", "")
            or os.getenv("MATTERMOST_URL", "")
        ).rstrip("/")
        self._token: str = config.token or _get_scoped_secret("MATTERMOST_TOKEN", "")

        self._bot_user_id: str = ""
        self._bot_username: str = ""

        # aiohttp session + websocket handle
        self._session: Any = None  # aiohttp.ClientSession
        self._ws: Any = None       # aiohttp.ClientWebSocketResponse
        self._ws_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._backfill_task: Optional[asyncio.Task] = None
        self._closing = False

        # Bounded REST catch-up for missed WebSocket ``posted`` events.  The
        # WebSocket remains the primary path; this poller only replays recent
        # posts whose IDs are not already in the dedup cache.  It is deliberately
        # small-window/low-rate so a reconnect gap cannot silently drop a bot
        # mention, but the gateway does not continuously trawl Mattermost history.
        self._backfill_enabled = self._config_bool(
            "backfill_missed_mentions", "MATTERMOST_BACKFILL_MISSED_MENTIONS", True
        )
        self._backfill_interval_seconds = self._config_float(
            "backfill_interval_seconds", "MATTERMOST_BACKFILL_INTERVAL_SECONDS", 30.0, minimum=5.0
        )
        self._backfill_overlap_seconds = self._config_float(
            "backfill_overlap_seconds", "MATTERMOST_BACKFILL_OVERLAP_SECONDS", 600.0, minimum=5.0
        )
        self._backfill_initial_lookback_seconds = self._config_float(
            "backfill_initial_lookback_seconds", "MATTERMOST_BACKFILL_INITIAL_LOOKBACK_SECONDS", 90.0, minimum=0.0
        )
        self._backfill_per_page = int(self._config_float(
            "backfill_per_page", "MATTERMOST_BACKFILL_PER_PAGE", 100.0, minimum=1.0
        ))
        self._backfill_seen_ttl_seconds = self._config_float(
            "backfill_seen_ttl_seconds", "MATTERMOST_BACKFILL_SEEN_TTL_SECONDS", 3600.0, minimum=60.0
        )
        self._backfill_unreplied_lookback_seconds = self._config_float(
            "backfill_unreplied_lookback_seconds", "MATTERMOST_BACKFILL_UNREPLIED_LOOKBACK_SECONDS", 21600.0, minimum=0.0
        )
        self._backfill_watermark_ms = 0
        self._backfill_seen_post_ids: Dict[str, float] = {}

        # Reply mode: "thread" to nest replies, "off" for flat messages.
        self._reply_mode: str = (
            config.extra.get("reply_mode", "")
            or os.getenv("MATTERMOST_REPLY_MODE", "off")
        ).lower()

        self._last_post_status: Optional[int] = None
        self._last_post_error: str = ""
        self._pd_one_quality_queue_path: str = str(
            config.extra.get("pd_one_quality_queue_path", "")
            or os.getenv("MATTERMOST_PD_ONE_QUALITY_QUEUE", "")
        ).strip()

        # Dedup cache (prevent reprocessing)
        self._dedup = MessageDeduplicator()

        # Thread rehydration cache keyed by Hermes session key.  Once a
        # Mattermost thread message/file has been injected for a live session,
        # do not inject/download it again for later turns in the same thread.
        self._thread_rehydration_cache: Dict[str, Dict[str, set[str]]] = {}

        # Best-effort guard so simultaneous replies do not all attempt to title
        # the same Mattermost root post. The root message itself remains the
        # source of truth, so a gateway restart safely rechecks headings.
        self._auto_heading_roots_inflight: set[str] = set()

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _config_bool(self, key: str, env_key: str, default: bool) -> bool:
        raw: Any = None
        if self.config.extra:
            raw = self.config.extra.get(key)
        if raw is None:
            raw = os.getenv(env_key)
        if raw is None:
            return default
        return str(raw).strip().lower() not in {"false", "0", "no", "off", ""}

    def _config_float(self, key: str, env_key: str, default: float, *, minimum: float = 0.0) -> float:
        raw: Any = None
        if self.config.extra:
            raw = self.config.extra.get(key)
        if raw is None:
            raw = os.getenv(env_key)
        try:
            value = float(raw) if raw is not None else float(default)
        except (TypeError, ValueError):
            value = float(default)
        return max(value, minimum)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def _api_get(self, path: str) -> Dict[str, Any]:
        """GET /api/v4/{path}."""
        import aiohttp
        if ".." in path:
            logger.error("MM API path traversal blocked: %s", path)
            return {}
        url = f"{self._base_url}/api/v4/{path.lstrip('/')}"
        try:
            async with self._session.get(url, headers=self._headers(), timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.error("MM API GET %s → %s: %s", path, resp.status, body[:200])
                    return {}
                return await resp.json()
        except aiohttp.ClientError as exc:
            logger.error("MM API GET %s network error: %s", path, exc)
            return {}

    async def _api_post(
        self, path: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """POST /api/v4/{path} with JSON body."""
        import aiohttp
        if ".." in path:
            logger.error("MM API path traversal blocked: %s", path)
            return {}
        url = f"{self._base_url}/api/v4/{path.lstrip('/')}"
        self._last_post_status = None
        self._last_post_error = ""
        try:
            async with self._session.post(
                url, headers=self._headers(), json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                self._last_post_status = resp.status
                if resp.status >= 400:
                    body = await resp.text()
                    self._last_post_error = body or ""
                    logger.error("MM API POST %s → %s: %s", path, resp.status, body[:200])
                    return {}
                return await resp.json()
        except aiohttp.ClientError as exc:
            self._last_post_error = str(exc)
            logger.error("MM API POST %s network error: %s", path, exc)
            return {}

    async def _thread_root_for_send(
        self,
        reply_to: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """Resolve the Mattermost root_id from reply_to or metadata."""
        if self._reply_mode != "thread":
            return None
        candidate = reply_to
        if not candidate and isinstance(metadata, dict):
            candidate = metadata.get("thread_id") or metadata.get("root_id")
        if not candidate:
            return None
        return await self._resolve_root_id(str(candidate))

    def _last_post_failure_is_broken_thread_root(self) -> bool:
        """Return True only for clear invalid/missing Mattermost thread roots."""
        if self._last_post_status not in {400, 404}:
            return False
        body = (self._last_post_error or "").lower()
        if not body:
            return False
        rootish = any(marker in body for marker in ("root_id", "rootid", "root id", "thread", "post"))
        broken = any(marker in body for marker in ("invalid", "not found", "does not exist", "missing"))
        return rootish and broken

    async def _post_preserving_thread(
        self,
        chat_id: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Post once, optionally falling back flat for final notify content."""
        data = await self._api_post("posts", payload)
        if data:
            self._enqueue_pd_one_quality_event(chat_id, payload, data, metadata)
        if data or "root_id" not in payload:
            return data
        if not (isinstance(metadata, dict) and metadata.get("notify")):
            return data
        if not self._last_post_failure_is_broken_thread_root():
            return data

        flat_payload = dict(payload)
        flat_payload.pop("root_id", None)
        original = str(flat_payload.get("message") or "")
        flat_payload["message"] = (
            "⚠️ Mattermost thread delivery failed; posting final reply in channel.\n\n"
            + original
        ).strip()
        logger.warning(
            "Mattermost: falling back to flat channel delivery for notify-worthy post in %s",
            chat_id,
        )
        data = await self._api_post("posts", flat_payload)
        if data:
            self._enqueue_pd_one_quality_event(chat_id, flat_payload, data, metadata)
        return data

    def _enqueue_pd_one_quality_event(
        self,
        chat_id: str,
        payload: Dict[str, Any],
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """Best-effort queue signal for PD One reply-quality review.

        The queue is a lightweight candidate signal only. It intentionally does
        not persist message text, tool traces, or private source data; the
        supervisor can fetch bounded Mattermost/review_log evidence later.
        """
        if not getattr(self, "_pd_one_quality_queue_path", None):
            return
        post_id = str(data.get("id") or "")
        if not post_id:
            return
        meta = metadata if isinstance(metadata, dict) else {}
        event = {
            "event_type": "pd_one.reply_posted",
            "platform": "mattermost",
            "post_id": post_id,
            "channel_id": str(data.get("channel_id") or chat_id or ""),
            "root_id": str(data.get("root_id") or payload.get("root_id") or ""),
            "create_at": data.get("create_at"),
            "reply_to": str(meta.get("reply_to") or meta.get("thread_id") or meta.get("root_id") or ""),
            "file_count": len(data.get("file_ids") or payload.get("file_ids") or []),
            "message_chars": len(str(payload.get("message") or "")),
            "queued_at_ms": int(time.time() * 1000),
        }
        try:
            path = Path(self._pd_one_quality_queue_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception as exc:
            logger.warning("Mattermost: failed to enqueue PD One quality event for %s: %s", post_id, exc)

    async def _api_put(
        self, path: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """PUT /api/v4/{path} with JSON body."""
        import aiohttp
        if ".." in path:
            logger.error("MM API path traversal blocked: %s", path)
            return {}
        url = f"{self._base_url}/api/v4/{path.lstrip('/')}"
        try:
            async with self._session.put(
                url, headers=self._headers(), json=payload
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.error("MM API PUT %s → %s: %s", path, resp.status, body[:200])
                    return {}
                return await resp.json()
        except aiohttp.ClientError as exc:
            logger.error("MM API PUT %s network error: %s", path, exc)
            return {}

    def _file_download_timeout(self):
        """Return a generous timeout for Mattermost attachment downloads.

        Mattermost can serve larger Office/CAD attachments slowly from the
        production host.  A 30s total timeout is fine for JSON API calls but it
        can silently drop valid thread attachments before the agent sees them.
        Keep a bounded total timeout, but allow enough wall clock time for
        multi-MB files over slow links.
        """
        import aiohttp

        raw_total = (
            self.config.extra.get("file_download_timeout")
            if self.config.extra and "file_download_timeout" in self.config.extra
            else os.getenv("MATTERMOST_FILE_DOWNLOAD_TIMEOUT", "600")
        )
        raw_sock_read = (
            self.config.extra.get("file_download_sock_read_timeout")
            if self.config.extra and "file_download_sock_read_timeout" in self.config.extra
            else os.getenv("MATTERMOST_FILE_DOWNLOAD_SOCK_READ_TIMEOUT", "120")
        )
        try:
            total = max(float(str(raw_total or "600")), 30.0)
        except (TypeError, ValueError):
            total = 600.0
        try:
            sock_read = max(float(str(raw_sock_read or "120")), 30.0)
        except (TypeError, ValueError):
            sock_read = 120.0
        return aiohttp.ClientTimeout(total=total, sock_read=sock_read)

    async def _download_file_bytes(self, file_id: str) -> Tuple[Optional[bytes], Optional[int], Optional[str]]:
        """Download a Mattermost file using the attachment-specific timeout."""
        if not self._session:
            return None, None, "Mattermost session is not connected"
        dl_url = f"{self._base_url}/api/v4/files/{file_id}"
        async with self._session.get(
            dl_url,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=self._file_download_timeout(),
        ) as resp:
            if resp.status >= 400:
                return None, resp.status, None
            return await resp.read(), resp.status, None

    async def _api_delete(self, path: str) -> bool:
        """DELETE /api/v4/{path}.

        Normal gateway traffic uses the long-lived Mattermost aiohttp session.
        Progress-bubble cleanup can run very late in a turn, including while a
        gateway replacement is closing that session.  If the primary connector
        is already closed, retry with a short-lived session so cleanup is not
        silently lost after the final response lands.
        """
        import aiohttp
        url = f"{self._base_url}/api/v4/{path.lstrip('/')}"

        last_delete_error: list[BaseException | None] = [None]

        async def _delete_with_session(session: Any, *, request_kwargs: Optional[Dict[str, Any]] = None) -> bool:
            try:
                last_delete_error[0] = None
                async with session.delete(
                    url,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=30),
                    **(request_kwargs or {}),
                ) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        logger.error("MM API DELETE %s → %s: %s", path, resp.status, body[:200])
                        return False
                    return True
            except (aiohttp.ClientError, RuntimeError) as exc:
                # RuntimeError covers aiohttp's "Session is closed" path; the
                # live logs also showed "Connector is closed" as ClientError.
                last_delete_error[0] = exc
                logger.error("MM API DELETE %s network error: %s", path, exc)
                return False

        session = self._session
        session_closed = session is None or getattr(session, "closed", False) is True
        if not session_closed:
            ok = await _delete_with_session(session)
            if ok:
                return True
            # If the underlying connector/session flipped closed during the
            # request, fall through to a transient retry below. Normal API
            # failures (403/404/etc.) should not be retried with a second
            # session because the token/permission outcome will be the same.
            session_closed = getattr(session, "closed", False) is True
            closed_error = "closed" in str(last_delete_error[0] or "").lower()
            if not session_closed and not closed_error:
                return False
            session_closed = True

        if not self._base_url or not self._token:
            logger.error("MM API DELETE %s unavailable: Mattermost URL/token not configured", path)
            return False

        try:
            from gateway.platforms.base import resolve_proxy_url, proxy_kwargs_for_aiohttp

            proxy = resolve_proxy_url(platform_env_var="MATTERMOST_PROXY")
            session_kwargs, request_kwargs = proxy_kwargs_for_aiohttp(proxy)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                **session_kwargs,
            ) as transient_session:
                logger.debug(
                    "MM API DELETE %s using transient session after primary session closed=%s",
                    path,
                    session_closed,
                )
                return await _delete_with_session(
                    transient_session,
                    request_kwargs=request_kwargs,
                )
        except (aiohttp.ClientError, RuntimeError) as exc:
            logger.error("MM API DELETE %s transient session error: %s", path, exc)
            return False

    async def _upload_file(
        self, channel_id: str, file_data: bytes, filename: str, content_type: str = "application/octet-stream"
    ) -> Optional[str]:
        """Upload a file and return its file ID, or None on failure."""
        import aiohttp

        url = f"{self._base_url}/api/v4/files"
        form = _build_file_upload_form(
            channel_id,
            file_data,
            filename,
            content_type,
        )
        headers = {"Authorization": f"Bearer {self._token}"}
        async with self._session.post(url, headers=headers, data=form, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            if resp.status >= 400:
                body = await resp.text()
                logger.error("MM file upload → %s: %s", resp.status, body[:200])
                return None
            data = await resp.json()
            infos = data.get("file_infos", [])
            return infos[0]["id"] if infos else None

    # ------------------------------------------------------------------
    # Required overrides
    # ------------------------------------------------------------------

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        """Connect to Mattermost and start the WebSocket listener."""
        import aiohttp

        if not self._base_url or not self._token:
            logger.error("Mattermost: URL or token not configured")
            return False

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        self._closing = False

        # Verify credentials and fetch bot identity.
        me = await self._api_get("users/me")
        if not me or "id" not in me:
            logger.error("Mattermost: failed to authenticate — check MATTERMOST_TOKEN and MATTERMOST_URL")
            await self._session.close()
            return False

        self._bot_user_id = me["id"]
        self._bot_username = me.get("username", "")
        logger.info(
            "Mattermost: authenticated as @%s (%s) on %s",
            self._bot_username,
            self._bot_user_id,
            self._base_url,
        )

        # Start WebSocket in background.
        self._ws_task = asyncio.create_task(self._ws_loop())
        if self._backfill_enabled:
            now_ms = int(time.time() * 1000)
            self._backfill_watermark_ms = max(0, now_ms - int(self._backfill_initial_lookback_seconds * 1000))
            self._backfill_task = asyncio.create_task(self._backfill_loop())
            logger.info(
                "Mattermost: missed-mention REST backfill enabled (interval=%.0fs overlap=%.0fs initial_lookback=%.0fs unreplied_lookback=%.0fs)",
                self._backfill_interval_seconds,
                self._backfill_overlap_seconds,
                self._backfill_initial_lookback_seconds,
                self._backfill_unreplied_lookback_seconds,
            )
        self._mark_connected()
        return True

    async def disconnect(self) -> None:
        """Disconnect from Mattermost."""
        self._closing = True

        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except (asyncio.CancelledError, Exception):
                pass

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()

        if self._backfill_task and not self._backfill_task.done():
            self._backfill_task.cancel()
            try:
                await self._backfill_task
            except (asyncio.CancelledError, Exception):
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._session and not self._session.closed:
            await self._session.close()

        logger.info("Mattermost: disconnected")


    async def _resolve_root_id(self, post_id: str) -> str:
        """Resolve a post_id to the thread root_id for Mattermost.

        Mattermost requires root_id to be the *root* post of a thread.
        If the post is a reply (has its own root_id), we must use that
        root_id instead.  Using a reply's own ID as root_id causes
        "Invalid RootId parameter" errors.
        """
        if not post_id:
            return post_id
        # Check if this post has a root_id (meaning it's a reply)
        data = await self._api_get(f"posts/{post_id}")
        if data and data.get("root_id"):
            return data["root_id"]
        return post_id

    def _format_thread_context_post(self, post: Dict[str, Any]) -> Optional[str]:
        """Format a Mattermost thread post for channel_context injection."""
        if not post or post.get("delete_at"):
            return None
        message = str(post.get("message") or "").strip()
        file_ids = post.get("file_ids") or []
        if not message and not file_ids:
            return None
        author = str(post.get("user_id") or "unknown").strip() or "unknown"
        parts = []
        if message:
            parts.append(message)
        if file_ids:
            parts.append(f"[attachments: {', '.join(map(str, file_ids))}]")
        return f"[{author}] " + " ".join(parts)

    async def _fetch_thread_context(
        self,
        root_id: Optional[str],
        triggering_post_id: Optional[str],
        session_key: Optional[str] = None,
    ) -> Tuple[Optional[str], List[str]]:
        """Fetch and format Mattermost thread history before the triggering post.

        Hermes already uses Mattermost root_id as thread_id for session keys.
        This fills the missing bootstrap case: a first @mention in an existing
        thread should show the root post and earlier replies even when Hermes
        was not mentioned at the root.
        """
        if not root_id:
            return None, []
        try:
            thread = await self._api_get(f"posts/{root_id}/thread")
        except Exception as exc:
            logger.warning("Mattermost: failed to fetch thread context for %s: %s", root_id, exc)
            return None, []

        posts_by_id = thread.get("posts") if isinstance(thread, dict) else None
        if not isinstance(posts_by_id, dict):
            return None, []
        order = thread.get("order") if isinstance(thread, dict) else None
        if not isinstance(order, list):
            order = sorted(
                posts_by_id,
                key=lambda pid: int(posts_by_id.get(pid, {}).get("create_at") or 0),
            )

        max_posts = int(self.config.extra.get("thread_context_max_posts", 40) or 40)
        max_chars = int(self.config.extra.get("thread_context_max_chars", 12000) or 12000)
        max_files = int(self.config.extra.get("thread_context_max_files", 20) or 20)

        cache_key = session_key or root_id
        loaded_posts: set[str] = set()
        loaded_files: set[str] = set()
        if cache_key:
            cached = self._thread_rehydration_cache.setdefault(
                cache_key,
                {"posts": set(), "files": set()},
            )
            loaded_posts = cached.setdefault("posts", set())
            loaded_files = cached.setdefault("files", set())

        candidates: List[Tuple[str, str]] = []
        candidate_file_ids: List[str] = []
        for post_id in order:
            post_id_str = str(post_id)
            if post_id_str == triggering_post_id:
                continue
            if post_id_str in loaded_posts:
                continue
            post = posts_by_id.get(post_id)
            if not isinstance(post, dict):
                continue
            for file_id in post.get("file_ids") or []:
                file_id_str = str(file_id)
                if file_id_str not in loaded_files and file_id_str not in candidate_file_ids:
                    candidate_file_ids.append(file_id_str)
            formatted = self._format_thread_context_post(post)
            if formatted:
                candidates.append((post_id_str, formatted))

        omitted = 0
        selected = candidates
        if len(selected) > max_posts:
            omitted = len(selected) - max_posts
            selected = selected[-max_posts:]
        thread_file_ids = candidate_file_ids[-max_files:] if max_files > 0 else []

        if cache_key:
            loaded_posts.update(post_id for post_id, _ in selected)
            if triggering_post_id:
                loaded_posts.add(str(triggering_post_id))
            loaded_files.update(thread_file_ids)

        if not selected:
            return None, thread_file_ids

        body = "\n".join(line for _, line in selected)
        if len(body) > max_chars:
            body = "[older thread context truncated]\n" + body[-max_chars:]
        header = f"[Mattermost thread context: root={root_id}"
        if omitted:
            header += f"; omitted_older_posts={omitted}"
        header += "]"
        return f"{header}\n{body}", thread_file_ids

    def _load_pd_one_user_policy(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load an OpenClaw/PD One effective Mattermost policy cache entry."""
        if not user_id:
            return None
        cache_dir = self.config.extra.get("pd_one_policy_cache_users") or os.getenv("PD_ONE_POLICY_CACHE_USERS")
        if not cache_dir:
            return None
        path = Path(str(cache_dir)).expanduser() / f"{user_id}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"found": False, "mattermostUserId": user_id, "policyPath": str(path)}
        except Exception as exc:
            logger.warning("Mattermost: failed to load PD One policy cache for %s: %s", user_id, exc)
            return {"found": False, "mattermostUserId": user_id, "policyPath": str(path), "error": "unreadable"}
        if isinstance(data, dict):
            data["policyPath"] = str(path)
            return data
        return None

    def _build_pd_one_policy_context(self, user_id: str, channel_id: str, chat_type: str) -> Optional[str]:
        """Build compact policy context from the Hermes PD One profile.

        The Hermes PD One profile policy files remain the source of truth; this
        injects enough per-turn context to force exact sender-id authorization
        and gives the agent deterministic paths to consult before acting.
        Legacy OpenClaw key/env names remain accepted as compatibility aliases.
        """
        enabled = self.config.extra.get("pd_one_policy_bridge") if "pd_one_policy_bridge" in self.config.extra else os.getenv("PD_ONE_POLICY_BRIDGE")
        if str(enabled).lower() not in {"1", "true", "yes", "on"}:
            return None
        workspace = str(
            self.config.extra.get("pd_one_hermes_policy_root")
            or self.config.extra.get("pd_one_policy_root")
            or self.config.extra.get("pd_one_openclaw_workspace")
            or os.getenv("PD_ONE_HERMES_POLICY_ROOT")
            or os.getenv("PD_ONE_POLICY_ROOT")
            or os.getenv("PD_ONE_OPENCLAW_WORKSPACE")
            or "/home/prodesign/.hermes/profiles/pdone"
        )
        policy = self._load_pd_one_user_policy(user_id) or {"found": False, "mattermostUserId": user_id}
        def _summarize_data_access(data_access: Any) -> Dict[str, Any]:
            if not isinstance(data_access, dict):
                return {}
            denied = []
            full = []
            read_limited = []
            planned = []
            other: Dict[str, str] = {}
            for key, value in sorted(data_access.items()):
                text = str(value).strip()
                lower = text.lower()
                if lower == "deny":
                    denied.append(key)
                elif "planned" in lower:
                    planned.append(key)
                elif "full" in lower:
                    full.append(key)
                elif "read" in lower or "summar" in lower or "limited" in lower or "draft" in lower:
                    read_limited.append(key)
                else:
                    other[key] = text[:120]
            summary: Dict[str, Any] = {}
            if full:
                summary["full"] = full
            if read_limited:
                summary["read_limited"] = read_limited
            if planned:
                summary["planned"] = planned
            if denied:
                summary["denied"] = denied
            if other:
                summary["other"] = other
            return summary

        def _compact_identity(identity: Any) -> Dict[str, Any]:
            if not isinstance(identity, dict):
                return {}
            result = {key: identity.get(key) for key in ("nameZh", "nameEn", "appsheetPersonId") if identity.get(key)}
            result["identityRule"] = "Exact Mattermost sender id only; no name/fuzzy fallback."
            return result

        mode_raw = self.config.extra.get("pd_one_policy_bridge_mode") or os.getenv("PD_ONE_POLICY_BRIDGE_MODE") or "compact"
        mode = str(mode_raw).strip().lower()
        if mode in {"full", "legacy"}:
            allowed_keys = [
                "schema",
                "generatedAtUtc",
                "found",
                "active",
                "decision",
                "turnHandling",
                "dmEnabled",
                "language",
                "roles",
                "safeScopes",
                "approval",
                "tools",
                "channels",
                "dataAccess",
                "identity",
                "setupResponse",
                "lookupFailureResponse",
                "employeeFacingNotes",
                "policyPath",
            ]
            compact = {key: policy.get(key) for key in allowed_keys if key in policy}
        else:
            compact = {
                key: policy.get(key)
                for key in (
                    "schema",
                    "generatedAtUtc",
                    "found",
                    "active",
                    "decision",
                    "turnHandling",
                    "dmEnabled",
                    "language",
                    "roles",
                    "safeScopes",
                    "approval",
                    "tools",
                    "policyPath",
                )
                if key in policy
            }
            needs_refusal_text = not policy.get("found") or not policy.get("active", True) or str(policy.get("decision", "")).startswith("deny")
            if needs_refusal_text:
                for key in ("setupResponse", "lookupFailureResponse"):
                    if key in policy:
                        compact[key] = policy.get(key)
            if "identity" in policy:
                compact["identity"] = _compact_identity(policy.get("identity"))
            data_access_summary = _summarize_data_access(policy.get("dataAccess"))
            if data_access_summary:
                compact["dataAccessSummary"] = data_access_summary
            if policy.get("channels"):
                compact["channelAccess"] = policy.get("channels")
        compact.update({"requesterMattermostUserId": user_id, "currentChannelId": channel_id, "currentChatType": chat_type})
        payload = json.dumps(compact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return (
            "[PD One Hermes permission bridge]\n"
            "Authorize by exact sender id only; never name/fuzzy/prior-session identity. "
            "If found=false, lookup failed, inactive, or not allowed, use setup/lookup-failure response and stop scoped work. "
            "Mattermost channel/group replies must be fully bilingual English + Traditional Chinese with 1:1 equivalent substance and detail. "
            "For multi-part answers, mirror every heading, paragraph, bullet, numbered item, condition, caveat, feedback/recommendation, source/provenance note, question, and promised action in the other language. "
            "Before sending, compare paired sections; never make one language a summary or omit a section. "
            "Writes/external sends/destructive/gateway/config/policy/source edits/broad history/permission expansion require approved-user authorization plus dry-run where practical. "
            "Requester-provided current-thread document writing/polishing/formatting/translation is a non-destructive drafting artifact; do not treat it as protected source-system/private-record access merely because the topic is HR/personnel/discipline.\n"
            f"Policy sources: {workspace}/policies/mattermost-channels.md; {workspace}/policies/mattermost-users.json; {workspace}/policies/mattermost-roles.json; {workspace}/policy-cache/mattermost/users/{user_id}.json\n"
            f"Policy JSON ({mode}): {payload}"
        )

    def _build_pd_one_outbound_dm_workflow_context(self, user_id: str, channel_id: str, chat_type: str, message_text: str, post: Dict[str, Any]) -> Optional[str]:
        """Build outbound-DM workflow context only after conservative routing.

        Open workflow rows are candidates only.  The deterministic router injects
        full context only on tracker-code or platform thread linkage; probable
        matches receive a small disambiguation packet, and unrelated DMs receive
        no workflow context.
        """
        if chat_type != "dm" or not user_id:
            return None
        raw_enabled = self.config.extra.get("pd_one_outbound_dm_workflows") if "pd_one_outbound_dm_workflows" in self.config.extra else os.getenv("PD_ONE_OUTBOUND_DM_WORKFLOWS", "auto")
        if str(raw_enabled).strip().lower() in {"0", "false", "no", "off", "disabled"}:
            return None
        try:
            from hermes_constants import get_hermes_home
            default_db = Path(get_hermes_home()) / "state" / "outbound_dm_workflows.sqlite"
        except Exception:
            default_db = Path.home() / ".hermes" / "profiles" / "pdone" / "state" / "outbound_dm_workflows.sqlite"
        db_path = Path(str(self.config.extra.get("pd_one_outbound_dm_workflows_db") or os.getenv("PD_ONE_OUTBOUND_DM_WORKFLOWS_DB") or default_db)).expanduser()
        if str(raw_enabled).strip().lower() == "auto" and not db_path.exists():
            return None
        try:
            from gateway.pd_one_outbound_dm_workflows import (
                WorkflowRegistry,
                build_disambiguation_context,
                build_injected_context,
                route_inbound_message,
            )
            registry = WorkflowRegistry(db_path)
            root_message_id = str(post.get("root_id") or "")
            decision = route_inbound_message(
                registry,
                sender_id=user_id,
                message_text=message_text,
                root_message_id=root_message_id,
            )
            if decision.action == "inject_workflow":
                return build_injected_context(registry, decision)
            if decision.action in {"ask_confirmation", "ask_user_to_choose"}:
                return build_disambiguation_context(decision)
        except Exception as exc:
            logger.warning("Mattermost: failed to route PD One outbound DM workflow for %s/%s: %s", channel_id, user_id, exc)
        return None

    @staticmethod
    def _combine_channel_context(*parts: Optional[str]) -> Optional[str]:
        present = [part for part in parts if part]
        return "\n\n".join(present) if present else None

    def _auto_thread_root_heading_enabled(self) -> bool:
        raw = None
        if self.config.extra:
            raw = self.config.extra.get("auto_thread_root_heading")
        if raw is None:
            raw = os.getenv("MATTERMOST_AUTO_THREAD_ROOT_HEADING", "false")
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def _auto_thread_root_heading_channel_disabled(self, channel_id: str) -> bool:
        """Return True when passive root-heading edits are disabled for a channel."""
        channel_id = str(channel_id or "").strip()
        if not channel_id:
            return False
        raw: Any = None
        if self.config.extra:
            raw = self.config.extra.get("auto_thread_root_heading_disabled_channels")
        if raw is None:
            raw = os.getenv("MATTERMOST_AUTO_THREAD_ROOT_HEADING_DISABLED_CHANNELS", "")
        if isinstance(raw, str):
            disabled = {part.strip() for part in re.split(r"[,\s]+", raw) if part.strip()}
        elif isinstance(raw, (list, tuple, set)):
            disabled = {str(part).strip() for part in raw if str(part).strip()}
        else:
            disabled = set()
        return channel_id in disabled

    @staticmethod
    def _first_markdown_heading(message: str) -> Optional[Dict[str, Any]]:
        """Return details for the first non-blank line if it is a Markdown heading."""
        text = str(message or "")
        position = 0
        for line in text.splitlines(keepends=True):
            line_without_break = line.rstrip("\r\n")
            stripped = line_without_break.strip()
            line_end = position + len(line)
            if not stripped:
                position = line_end
                continue
            match = re.match(r"^(?P<indent>\s*)(?P<marks>#{1,6})\s+(?P<title>\S.*?)(?P<trailing>\s*)$", line_without_break)
            if not match:
                return None
            title = match.group("title").strip()
            return {
                "start": position,
                "end": line_end,
                "indent": match.group("indent") or "",
                "marks": match.group("marks"),
                "title": title,
                "line_break": line[len(line_without_break):],
            }
        return None

    @classmethod
    def _has_markdown_heading(cls, message: str) -> bool:
        return cls._first_markdown_heading(message) is not None

    @staticmethod
    def _heading_title_is_bilingual(title: str) -> bool:
        text = str(title or "").strip()
        if not text:
            return False
        # Treat a slash-separated Chinese + English pair as the canonical bilingual heading.
        parts = [part.strip() for part in re.split(r"\s+/\s+", text, maxsplit=1)]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return False
        has_cjk = [bool(re.search(r"[\u3400-\u9fff]", part)) for part in parts]
        has_latin = [bool(re.search(r"[A-Za-z]", part)) for part in parts]
        return (has_cjk[0] and has_latin[1]) or (has_latin[0] and has_cjk[1])

    @staticmethod
    def _sanitize_root_heading_title(raw: str) -> str:
        title = " ".join(str(raw or "").strip().split())
        title = re.sub(r"^#+\s*", "", title).strip()
        title = title.strip('`*_"\' ')
        if title.lower().startswith("title:"):
            title = title[6:].strip()
        title = title.rstrip(".。:：")
        if len(title) > 120:
            title = title[:117].rstrip() + "..."
        return title

    @classmethod
    def _fallback_thread_root_heading_title(cls, root_message: str, reply_message: str = "") -> str:
        source = root_message or reply_message or ""
        candidate = ""
        for line in str(source).splitlines():
            candidate = line.strip()
            if candidate:
                break
        candidate = re.sub(r"^#+\s*", "", candidate).strip()
        candidate = re.sub(r"https?://\S+", "", candidate)
        candidate = re.sub(r"@[\w.-]+", "", candidate)
        candidate = re.sub(r"[`*_>\[\]()]", " ", candidate)
        candidate = " ".join(candidate.split()).strip(" -–—:：。.")
        if not candidate:
            return "一般討論 / General Discussion"
        if len(candidate) > 48:
            candidate = candidate[:45].rstrip() + "..."
        if re.search(r"[\u3400-\u9fff]", candidate):
            return cls._sanitize_root_heading_title(f"{candidate} / Thread Discussion")
        return cls._sanitize_root_heading_title(f"討論串 / {candidate}")

    @classmethod
    def _fallback_bilingual_heading_title(cls, heading_title: str) -> str:
        candidate = cls._sanitize_root_heading_title(heading_title)
        if not candidate:
            return "一般討論 / General Discussion"
        if re.search(r"[\u3400-\u9fff]", candidate):
            return cls._sanitize_root_heading_title(f"{candidate} / Thread Discussion")
        return cls._sanitize_root_heading_title(f"{candidate} / 討論串")

    @classmethod
    def _mention_translation_marker_present(cls, message: str) -> bool:
        return "**Translation / 翻譯 (utility-agent):**" in str(message or "")

    @staticmethod
    def _truncate_translation_text(text: str, max_chars: int = 1600) -> str:
        cleaned = str(text or "").strip()
        cleaned = re.sub(r"^```(?:\w+)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        if len(cleaned) > max_chars:
            cleaned = cleaned[: max_chars - 1].rstrip() + "…"
        return cleaned

    @staticmethod
    def _mention_translation_target_language(message: str) -> str:
        """Pick the missing translation side for mixed mentioned-channel posts.

        Mentioned Mattermost posts often have a short Chinese heading followed by
        English instructions to PD One. Treat that as English-dominant prose that
        needs Traditional Chinese, not as a Chinese/mixed message that needs the
        already-English instructions repeated.
        """
        text = str(message or "")
        cjk_chars = len(re.findall(r"[\u3400-\u9fff]", text))
        latin_words = len(re.findall(r"\b[A-Za-z][A-Za-z0-9'’_-]*\b", text))
        if cjk_chars == 0:
            return "Traditional Chinese"
        if latin_words == 0:
            return "English"
        # One Chinese character roughly carries more information than one Latin
        # word, but a short Chinese heading plus English instructions should still
        # target Traditional Chinese. Bias toward Chinese only when CJK clearly
        # dominates the prose.
        if latin_words >= max(4, cjk_chars // 2):
            return "Traditional Chinese"
        return "English"

    async def _generate_mention_translation(self, message: str) -> Optional[str]:
        """Use the auxiliary LLM slot as the utility agent for mention translations."""
        source = str(message or "").strip()
        if not source:
            return None
        target_language = self._mention_translation_target_language(source)
        system_prompt = (
            "You are a low-cost utility agent that translates Mattermost messages. "
            f"Translate the user's message faithfully and concisely into {target_language}. "
            "For mixed Chinese/English messages, translate the substantive prose that is "
            "not already in the target language; do not leave English instructions in "
            "English just because the heading contains Chinese, and do not leave Chinese "
            "instructions in Chinese just because there are English product names or IDs. "
            "If both languages are already present with equivalent meaning, return an "
            "empty string. Preserve names, @mentions, URLs, file names, numbers, and "
            "technical terms. Do not answer the message, do not add commentary, and do "
            "not wrap the result in quotes or Markdown fences."
        )
        user_prompt = (
            f"Translate this Mattermost message only into {target_language}. Return only "
            "the translation text, or an empty string if no translation is needed.\n\n"
            f"Message:\n{source[:3000]}"
        )
        try:
            response = await async_call_llm(
                task="mattermost_mention_translation",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=500,
                temperature=0.1,
                timeout=30.0,
            )
        except Exception as exc:
            logger.warning("Mattermost: mention translation generation failed: %s", exc)
            logger.debug("Mattermost mention translation traceback", exc_info=True)
            return None
        try:
            content = response.choices[0].message.content
        except Exception:
            content = ""
        return self._truncate_translation_text(content)

    async def _maybe_append_mention_translation(
        self,
        post: Dict[str, Any],
        *,
        has_mention: bool,
        channel_type_raw: str,
    ) -> None:
        """Best-effort: append a clearly labeled utility-agent translation to channel mentions."""
        if channel_type_raw == "D" or not has_mention:
            return
        enabled_raw = None
        if self.config.extra:
            enabled_raw = self.config.extra.get("auto_translate_mentioned_channel_messages")
        if enabled_raw is None:
            enabled_raw = os.getenv("MATTERMOST_AUTO_TRANSLATE_MENTIONED_CHANNEL_MESSAGES", "false")
        enabled = str(enabled_raw).lower() in {"true", "1", "yes", "on"}
        if not enabled:
            return

        post_id = str(post.get("id") or "").strip()
        message = str(post.get("message") or "")
        if not post_id or not message.strip() or self._mention_translation_marker_present(message):
            return

        translation = await self._generate_mention_translation(message)
        if not translation:
            return

        appended = (
            f"{message.rstrip()}\n\n---\n"
            f"**Translation / 翻譯 (utility-agent):**\n{translation}"
        )
        if len(appended) > MAX_POST_LENGTH:
            budget = MAX_POST_LENGTH - len(message.rstrip()) - len("\n\n---\n**Translation / 翻譯 (utility-agent):**\n")
            if budget < 80:
                logger.warning("Mattermost: skipped mention translation for %s because post is too long", post_id)
                return
            translation = self._truncate_translation_text(translation, budget)
            appended = (
                f"{message.rstrip()}\n\n---\n"
                f"**Translation / 翻譯 (utility-agent):**\n{translation}"
            )

        data = await self._api_put(f"posts/{post_id}/patch", {"message": appended})
        if data and data.get("id"):
            post["message"] = appended
            logger.info("Mattermost: appended utility-agent translation to mentioned post %s", post_id)
        else:
            logger.warning("Mattermost: failed to append mention translation for post %s", post_id)

    async def _generate_thread_root_heading_title(
        self,
        root_message: str,
        reply_message: str,
        existing_heading_title: str = "",
    ) -> Optional[str]:
        """Use the auxiliary LLM slot as the cheap/utility agent for root titles."""
        existing_heading_title = str(existing_heading_title or "").strip()
        if existing_heading_title:
            system_prompt = (
                "You are a low-cost utility agent that bilingualizes Mattermost headings. "
                "Return one concise bilingual heading title only. Preserve the provided "
                "source heading text exactly as written, then add a short equivalent "
                "translation on the other side of ` / `. Do not reorder or rewrite the "
                "source heading text. Use no Markdown heading marks, no quotes, no trailing "
                "punctuation, and no explanation."
            )
            user_prompt = (
                "Make this Mattermost heading bilingual by preserving the source heading "
                "text exactly and adding only the missing Traditional Chinese or English "
                "translation. Return exactly one line as: Source heading text / Translation.\n\n"
                f"Source heading text:\n{existing_heading_title[:300]}\n\n"
                f"Root message context:\n{(root_message or '')[:900]}\n\n"
                f"Latest reply that triggered titling:\n{(reply_message or '')[:500]}"
            )
        else:
            system_prompt = (
                "You are a low-cost utility agent that writes Mattermost thread titles. "
                "Return one concise bilingual title only, formatted exactly as "
                "繁體中文 / English. Put Traditional Chinese first because most users "
                "are Chinese speakers. Keep each side short and equivalent in meaning. "
                "Use no Markdown heading marks, no quotes, no trailing punctuation, "
                "and no explanation."
            )
            user_prompt = (
                "Create a useful bilingual Traditional Chinese + English title for this "
                "Mattermost thread. Return exactly one line in the format: 繁體中文 / English.\n\n"
                f"Root message:\n{(root_message or '')[:1200]}\n\n"
                f"Latest reply that triggered titling:\n{(reply_message or '')[:600]}"
            )
        try:
            response = await async_call_llm(
                task="mattermost_thread_title",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=80,
                temperature=0.2,
                timeout=20.0,
            )
        except Exception as exc:
            logger.warning("Mattermost: auto thread root heading generation failed: %s", exc)
            logger.debug("Mattermost auto-heading traceback", exc_info=True)
            fallback = (
                self._fallback_bilingual_heading_title(existing_heading_title)
                if existing_heading_title
                else self._fallback_thread_root_heading_title(root_message, reply_message)
            )
            logger.info("Mattermost: using fallback auto-heading title")
            return fallback
        try:
            content = response.choices[0].message.content
        except Exception:
            content = ""
        title = self._sanitize_root_heading_title(content)
        if existing_heading_title and title:
            source_heading = self._sanitize_root_heading_title(existing_heading_title)
            # Enforce the product requirement that an existing source heading is not
            # rewritten or reordered; the utility agent may only add the missing
            # translation on the other side of a slash.
            if title == source_heading or not (
                title.startswith(f"{source_heading} / ")
                or title.endswith(f" / {source_heading}")
            ):
                title = ""
        if title:
            return title
        fallback = (
            self._fallback_bilingual_heading_title(existing_heading_title)
            if existing_heading_title
            else self._fallback_thread_root_heading_title(root_message, reply_message)
        )
        logger.info("Mattermost: using fallback auto-heading title after empty/invalid utility response")
        return fallback

    async def _maybe_auto_heading_thread_root(self, post: Dict[str, Any], channel_type_raw: str) -> None:
        """Best-effort: when a Mattermost thread gets a reply, title its root post.

        Skips roots whose first Markdown heading is already bilingual. If the root
        already starts with a non-bilingual Markdown heading, keeps that source
        heading text unchanged and asks the utility agent to add a translation.
        Otherwise prepends a new level-5 bilingual heading while preserving the
        original root body. The edit is gated by config/env and runs before
        mention-gating so passive thread replies can improve titles without
        invoking the main agent.
        """
        if not self._auto_thread_root_heading_enabled():
            return
        if channel_type_raw == "D":
            return
        channel_id = str(post.get("channel_id") or "").strip()
        if self._auto_thread_root_heading_channel_disabled(channel_id):
            return
        root_id = str(post.get("root_id") or "").strip()
        if not root_id:
            return
        if root_id in self._auto_heading_roots_inflight:
            return

        self._auto_heading_roots_inflight.add(root_id)
        try:
            root_post = await self._api_get(f"posts/{root_id}")
            if not root_post or root_post.get("delete_at"):
                return
            root_message = str(root_post.get("message") or "")
            heading = self._first_markdown_heading(root_message)
            reply_message = str(post.get("message") or "")
            if heading:
                source_heading_title = str(heading.get("title") or "").strip()
                if self._heading_title_is_bilingual(source_heading_title):
                    return
                title = await self._generate_thread_root_heading_title(
                    root_message,
                    reply_message,
                    existing_heading_title=source_heading_title,
                )
                if not title:
                    return
                line_break = str(heading.get("line_break") or "\n")
                new_heading_line = f"{heading.get('indent', '')}{heading.get('marks', '#####')} {title}{line_break}"
                new_message = f"{root_message[:heading['start']]}{new_heading_line}{root_message[heading['end']:]}"
            else:
                title = await self._generate_thread_root_heading_title(
                    root_message,
                    reply_message,
                )
                if not title:
                    return
                new_message = f"##### {title}\n\n{root_message}" if root_message.strip() else f"##### {title}"
            data = await self._api_put(f"posts/{root_id}/patch", {"message": new_message})
            if data and data.get("id"):
                logger.info("Mattermost: auto-added heading to thread root %s", root_id)
            else:
                logger.warning("Mattermost: failed to patch auto-heading for thread root %s", root_id)
        finally:
            self._auto_heading_roots_inflight.discard(root_id)

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send a message (or multiple chunks) to a channel."""
        if not content:
            return SendResult(success=True)

        formatted = self.format_message(content)
        chunks = self.truncate_message(formatted, MAX_POST_LENGTH)

        last_id = None
        for chunk in chunks:
            payload: Dict[str, Any] = _with_mentions_disabled({
                "channel_id": chat_id,
                "message": chunk,
            })
            # Thread support: reply_to or metadata["thread_id"] is the root post ID.
            resolved_root = await self._thread_root_for_send(reply_to, metadata)
            if resolved_root:
                payload["root_id"] = resolved_root

            data = await self._post_preserving_thread(chat_id, payload, metadata)
            if not data or "id" not in data:
                return SendResult(success=False, error="Failed to create post")
            last_id = data["id"]

        return SendResult(success=True, message_id=last_id)

    async def _resolve_effective_thread_root(
        self,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Return the Mattermost root_id for a send, honoring metadata.

        Text sends already accept thread routing either through ``reply_to`` or
        synthetic-send metadata (``thread_id`` / ``root_id``). File/image sends
        must use the same routing; otherwise MEDIA attachments emitted after a
        threaded text reply become top-level channel posts.
        """
        effective_reply_to = reply_to
        if not effective_reply_to and metadata:
            effective_reply_to = metadata.get("thread_id") or metadata.get("root_id")
        if effective_reply_to and self._reply_mode == "thread":
            return await self._resolve_root_id(str(effective_reply_to))
        return None

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """Return channel name and type."""
        data = await self._api_get(f"channels/{chat_id}")
        if not data:
            return {"name": chat_id, "type": "channel"}

        ch_type = _CHANNEL_TYPE_MAP.get(data.get("type", "O"), "channel")
        display_name = data.get("display_name") or data.get("name") or chat_id
        return {"name": display_name, "type": ch_type}

    # ------------------------------------------------------------------
    # Optional overrides
    # ------------------------------------------------------------------

    def _reaction_enabled(self) -> bool:
        """Return whether Mattermost processing reactions are enabled."""
        raw = None
        if self.config.extra:
            raw = self.config.extra.get("processing_reactions")
        if raw is None:
            raw = os.getenv("MATTERMOST_PROCESSING_REACTIONS", "true")
        return str(raw).strip().lower() not in {"0", "false", "no", "off"}

    async def _add_reaction(self, post_id: Optional[str], emoji_name: str) -> bool:
        """Best-effort add a Mattermost reaction to a post."""
        if not post_id or not emoji_name or not self._bot_user_id:
            return False
        data = await self._api_post(
            "reactions",
            {
                "user_id": self._bot_user_id,
                "post_id": str(post_id),
                "emoji_name": emoji_name,
            },
        )
        return bool(data)

    async def _remove_reaction(self, post_id: Optional[str], emoji_name: str) -> bool:
        """Best-effort remove a Mattermost reaction from a post."""
        if not post_id or not emoji_name or not self._bot_user_id:
            return False
        return await self._api_delete(
            f"users/{self._bot_user_id}/posts/{post_id}/reactions/{emoji_name}"
        )

    async def on_processing_start(self, event: MessageEvent) -> None:
        """Mark an accepted user message as seen/processing."""
        if not self._reaction_enabled():
            return
        await self._add_reaction(getattr(event, "message_id", None), "eyes")

    async def on_processing_complete(self, event: MessageEvent, outcome: Any) -> None:
        """Replace the processing marker with success/failure state."""
        if not self._reaction_enabled():
            return
        post_id = getattr(event, "message_id", None)
        await self._remove_reaction(post_id, "eyes")
        outcome_value = getattr(outcome, "value", str(outcome)).lower()
        if outcome_value == "success":
            await self._add_reaction(post_id, "white_check_mark")
        elif outcome_value == "cancelled":
            await self._add_reaction(post_id, "warning")
        else:
            await self._add_reaction(post_id, "x")

    async def send_typing(
        self, chat_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a typing indicator, scoped to the Mattermost thread when known."""
        payload: Dict[str, Any] = {"channel_id": chat_id}
        if metadata:
            parent_id = metadata.get("parent_id") or metadata.get("thread_id") or metadata.get("root_id")
            if parent_id:
                payload["parent_id"] = str(parent_id)
        await self._api_post(
            f"users/{self._bot_user_id}/typing",
            payload,
        )

    async def edit_message(
        self, chat_id: str, message_id: str, content: str, *, finalize: bool = False
    ) -> SendResult:
        """Edit an existing post."""
        formatted = self.format_message(content)
        data = await self._api_put(
            f"posts/{message_id}/patch",
            _with_mentions_disabled({"message": formatted}),
        )
        if not data or "id" not in data:
            return SendResult(success=False, error="Failed to edit post")
        return SendResult(success=True, message_id=data["id"])

    async def delete_message(self, chat_id: str, message_id: str) -> bool:
        """Delete a previously sent Mattermost post.

        Mattermost post IDs are globally unique, so the channel ID is not
        needed by the REST endpoint.  The gateway only tracks IDs returned from
        sends it performed itself; Mattermost enforces token permissions server
        side if a caller ever passes an invalid/unauthorized post ID.
        """
        if not message_id:
            return False
        return await self._api_delete(f"posts/{message_id}")

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Download an image and upload it as a file attachment."""
        return await self._send_url_as_file(
            chat_id, image_url, caption, reply_to, "image", metadata=metadata
        )

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Upload a local image file."""
        return await self._send_local_file(
            chat_id, image_path, caption, reply_to, metadata=metadata
        )

    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Upload a local file as a document."""
        return await self._send_local_file(
            chat_id, file_path, caption, reply_to, file_name, metadata=metadata
        )

    async def send_voice(
        self,
        chat_id: str,
        audio_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Upload an audio file."""
        return await self._send_local_file(
            chat_id, audio_path, caption, reply_to, metadata=metadata
        )

    async def send_video(
        self,
        chat_id: str,
        video_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Upload a video file."""
        return await self._send_local_file(
            chat_id, video_path, caption, reply_to, metadata=metadata
        )

    def format_message(self, content: str) -> str:
        """Mattermost uses standard Markdown — mostly pass through.

        Strip image markdown into plain links (files are uploaded separately).
        """
        # Convert ![alt](url) to just the URL — Mattermost renders
        # image URLs as inline previews automatically.
        content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\2", content)
        return content

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    async def _send_url_as_file(
        self,
        chat_id: str,
        url: str,
        caption: Optional[str],
        reply_to: Optional[str],
        kind: str = "file",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Download a URL and upload it as a file attachment."""
        from tools.url_safety import is_safe_url
        if not is_safe_url(url):
            logger.warning("Mattermost: blocked unsafe URL (SSRF protection)")
            return await self.send(chat_id, f"{caption or ''}\n{url}".strip(), reply_to, metadata=metadata)

        import aiohttp

        file_data = None
        ct = "application/octet-stream"
        fname = url.rsplit("/", 1)[-1].split("?")[0] or f"{kind}.png"

        for attempt in range(3):
            try:
                async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status >= 500 or resp.status == 429:
                        if attempt < 2:
                            logger.debug("Mattermost download retry %d/2 for %s (status %d)",
                                         attempt + 1, url[:80], resp.status)
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue
                    if resp.status >= 400:
                        return await self.send(chat_id, f"{caption or ''}\n{url}".strip(), reply_to, metadata=metadata)
                    file_data = await resp.read()
                    ct = resp.content_type or "application/octet-stream"
                    break
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                logger.warning("Mattermost: failed to download %s after %d attempts: %s", url, attempt + 1, exc)
                return await self.send(chat_id, f"{caption or ''}\n{url}".strip(), reply_to, metadata=metadata)

        if file_data is None:
            logger.warning("Mattermost: download returned no data for %s", url)
            return await self.send(chat_id, f"{caption or ''}\n{url}".strip(), reply_to, metadata=metadata)

        file_id = await self._upload_file(chat_id, file_data, fname, ct)
        if not file_id:
            return await self.send(chat_id, f"{caption or ''}\n{url}".strip(), reply_to, metadata=metadata)

        payload: Dict[str, Any] = _with_mentions_disabled({
            "channel_id": chat_id,
            "message": caption or "",
            "file_ids": [file_id],
        })
        # Preserve PD One media threading via metadata thread/root ids while
        # keeping upstream mention-suppression payload construction.
        root_id = await self._resolve_effective_thread_root(reply_to, metadata)
        if root_id:
            payload["root_id"] = root_id

        data = await self._post_preserving_thread(chat_id, payload, metadata)
        if not data or "id" not in data:
            return SendResult(success=False, error="Failed to post with file")
        return SendResult(success=True, message_id=data["id"])

    async def _send_local_file(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str],
        reply_to: Optional[str],
        file_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Upload a local file and attach it to a post."""
        import mimetypes

        p = Path(file_path)
        if not p.exists():
            logger.warning(
                "Mattermost: local file not found, skipping: %s", file_path
            )
            return SendResult(success=True, message_id=None)

        fname = file_name or p.name
        ct = mimetypes.guess_type(fname)[0] or "application/octet-stream"
        file_data = p.read_bytes()

        file_id = await self._upload_file(chat_id, file_data, fname, ct)
        if not file_id:
            return SendResult(success=False, error="File upload failed")

        payload: Dict[str, Any] = _with_mentions_disabled({
            "channel_id": chat_id,
            "message": caption or "",
            "file_ids": [file_id],
        })
        root_id = await self._resolve_effective_thread_root(reply_to, metadata)
        if root_id:
            payload["root_id"] = root_id

        data = await self._post_preserving_thread(chat_id, payload, metadata)
        if not data or "id" not in data:
            return SendResult(success=False, error="Failed to post with file")
        return SendResult(success=True, message_id=data["id"])

    async def send_multiple_images(
        self,
        chat_id: str,
        images: List[Tuple[str, str]],
        metadata: Optional[Dict[str, Any]] = None,
        human_delay: float = 0.0,
    ) -> None:
        """Send a batch of images as a single Mattermost post with multiple attachments.

        Mattermost supports up to 5 ``file_ids`` per post. Each image is
        uploaded individually (Mattermost's file API is one-at-a-time),
        then a single post is created referencing all uploaded file_ids
        at once. Batches larger than 5 are chunked. Falls back to the
        base per-image loop on total failure.
        """
        if not images:
            return

        import mimetypes
        import aiohttp
        from urllib.parse import unquote as _unquote

        CHUNK = 5  # Mattermost post file_ids cap
        chunks = [images[i:i + CHUNK] for i in range(0, len(images), CHUNK)]

        for chunk_idx, chunk in enumerate(chunks):
            if human_delay > 0 and chunk_idx > 0:
                await asyncio.sleep(human_delay)

            file_ids: List[str] = []
            caption_parts: List[str] = []
            try:
                for image_url, alt_text in chunk:
                    if alt_text:
                        caption_parts.append(alt_text)

                    if image_url.startswith("file://"):
                        local_path = _unquote(image_url[7:])
                        p = Path(local_path)
                        if not p.exists():
                            logger.warning("Mattermost: skipping missing image %s", local_path)
                            continue
                        fname = p.name
                        ct = mimetypes.guess_type(fname)[0] or "image/png"
                        file_data = p.read_bytes()
                    else:
                        from tools.url_safety import is_safe_url
                        if not is_safe_url(image_url):
                            logger.warning("Mattermost: blocked unsafe image URL in batch")
                            continue
                        try:
                            async with self._session.get(
                                image_url, timeout=aiohttp.ClientTimeout(total=30)
                            ) as resp:
                                if resp.status >= 400:
                                    logger.warning(
                                        "Mattermost: failed to download image (HTTP %d): %s",
                                        resp.status, image_url[:80],
                                    )
                                    continue
                                file_data = await resp.read()
                                ct = resp.content_type or "image/png"
                        except Exception as dl_err:
                            logger.warning("Mattermost: download failed for %s: %s", image_url[:80], dl_err)
                            continue
                        fname = image_url.rsplit("/", 1)[-1].split("?")[0] or f"image_{len(file_ids)}.png"

                    fid = await self._upload_file(chat_id, file_data, fname, ct)
                    if fid:
                        file_ids.append(fid)

                if not file_ids:
                    continue

                payload: Dict[str, Any] = _with_mentions_disabled({
                    "channel_id": chat_id,
                    "message": "\n".join(caption_parts),
                    "file_ids": file_ids,
                })
                root_id = await self._resolve_effective_thread_root(metadata=metadata)
                if root_id:
                    payload["root_id"] = root_id
                logger.info(
                    "Mattermost: sending %d image(s) as single post (chunk %d/%d)",
                    len(file_ids), chunk_idx + 1, len(chunks),
                )
                data = await self._post_preserving_thread(chat_id, payload, metadata)
                if not data or "id" not in data:
                    logger.warning("Mattermost: multi-image post failed, falling back")
                    await super().send_multiple_images(chat_id, chunk, metadata, human_delay=human_delay)
            except Exception as e:
                logger.warning(
                    "Mattermost: multi-image send failed (chunk %d/%d), falling back: %s",
                    chunk_idx + 1, len(chunks), e, exc_info=True,
                )
                await super().send_multiple_images(chat_id, chunk, metadata, human_delay=human_delay)

    # ------------------------------------------------------------------
    # Missed WebSocket event REST backfill
    # ------------------------------------------------------------------

    async def _backfill_loop(self) -> None:
        """Periodically replay recent @bot posts that the WebSocket missed."""
        while not self._closing:
            try:
                await asyncio.sleep(self._backfill_interval_seconds)
                if self._closing:
                    return
                await self._run_backfill_once()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("Mattermost: missed-mention backfill failed: %s", exc, exc_info=True)

    async def _run_backfill_once(self) -> int:
        """Search recent Mattermost posts for @bot mentions and replay new ones.

        Returns the number of candidate posts handed to the normal posted-event
        parser.  The parser's existing self-message, channel, mention, policy,
        and dedup gates remain authoritative.
        """
        if not self._bot_username:
            return 0

        self._prune_backfill_seen()
        since_ms = max(0, self._backfill_watermark_ms - int(self._backfill_overlap_seconds * 1000))
        unreplied_since_ms = max(0, int(time.time() * 1000) - int(self._backfill_unreplied_lookback_seconds * 1000))
        terms = f"@{self._bot_username}"
        posts_by_id: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []

        teams = await self._api_get("users/me/teams")
        if not isinstance(teams, list):
            teams = []
        for team in teams:
            team_id = str(team.get("id") or "") if isinstance(team, dict) else ""
            if not team_id:
                continue
            result = await self._api_post(
                f"teams/{team_id}/posts/search",
                {
                    "terms": terms,
                    "is_or_search": False,
                    "include_deleted_channels": False,
                    "page": 0,
                    "per_page": self._backfill_per_page,
                },
            )
            if not result:
                continue
            for post_id in result.get("order") or []:
                post = (result.get("posts") or {}).get(post_id)
                if not isinstance(post, dict):
                    continue
                created_ms = int(post.get("create_at") or 0)
                if created_ms <= since_ms:
                    if created_ms <= unreplied_since_ms:
                        continue
                    if await self._thread_has_bot_reply_after(post):
                        continue
                if post_id in self._backfill_seen_post_ids:
                    continue
                # Idempotency must be based on source-of-truth thread state,
                # not only the in-memory seen cache.  The rolling watermark is
                # intentionally anchored to the newest mention found by search;
                # when no newer mentions arrive, the same recent mention can
                # remain inside the overlap indefinitely.  After the seen-cache
                # TTL expires, replaying without checking the thread would
                # duplicate a request that already has a bot reply.  Do this
                # expensive thread lookup only after cheap age/cache gates; the
                # search endpoint can return hundreds of historical mentions.
                if await self._thread_has_bot_reply_after(post):
                    self._backfill_seen_post_ids[post_id] = time.time()
                    continue
                if post_id in self._backfill_seen_post_ids:
                    continue
                if post_id not in posts_by_id:
                    order.append(post_id)
                posts_by_id[post_id] = post

        replayed = 0
        newest_ms = self._backfill_watermark_ms
        for post_id in sorted(order, key=lambda pid: int(posts_by_id[pid].get("create_at") or 0)):
            post = posts_by_id[post_id]
            newest_ms = max(newest_ms, int(post.get("create_at") or 0))
            self._backfill_seen_post_ids[post_id] = time.time()
            if post.get("delete_at") or post.get("type"):
                continue
            channel_type = await self._channel_type_for_post(post)
            await self._handle_ws_event({
                "event": "posted",
                "data": {
                    "post": json.dumps(post),
                    "channel_type": channel_type,
                    "sender_name": post.get("user_id", ""),
                },
            })
            replayed += 1

        if newest_ms > self._backfill_watermark_ms:
            self._backfill_watermark_ms = newest_ms
        if replayed:
            logger.info("Mattermost: replayed %d missed mention candidate(s) via REST backfill", replayed)
        return replayed

    async def _thread_has_bot_reply_after(self, post: Dict[str, Any]) -> bool:
        """Return True if the bot has already replied after this post in its thread."""
        root_id = str(post.get("root_id") or post.get("id") or "")
        if not root_id or not self._bot_user_id:
            return False
        try:
            thread = await self._api_get(f"posts/{root_id}/thread")
        except Exception:
            return False
        if not isinstance(thread, dict):
            return False
        created_ms = int(post.get("create_at") or 0)
        for thread_post in (thread.get("posts") or {}).values():
            if not isinstance(thread_post, dict):
                continue
            if thread_post.get("user_id") != self._bot_user_id:
                continue
            if thread_post.get("delete_at"):
                continue
            if int(thread_post.get("create_at") or 0) > created_ms:
                return True
        return False

    def _prune_backfill_seen(self) -> None:
        if not self._backfill_seen_post_ids:
            return
        cutoff = time.time() - self._backfill_seen_ttl_seconds
        self._backfill_seen_post_ids = {
            post_id: seen_at
            for post_id, seen_at in self._backfill_seen_post_ids.items()
            if seen_at >= cutoff
        }

    async def _channel_type_for_post(self, post: Dict[str, Any]) -> str:
        channel_id = str(post.get("channel_id") or "")
        if not channel_id:
            return "O"
        channel = await self._api_get(f"channels/{channel_id}")
        return str(channel.get("type") or "O") if isinstance(channel, dict) else "O"

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------

    async def _ws_loop(self) -> None:
        """Connect to the WebSocket and listen for events, reconnecting on failure."""
        delay = _RECONNECT_BASE_DELAY
        while not self._closing:
            try:
                await self._ws_connect_and_listen()
                # Clean disconnect — reset delay.
                delay = _RECONNECT_BASE_DELAY
            except asyncio.CancelledError:
                return
            except Exception as exc:
                if self._closing:
                    return
                # Detect permanent auth/permission failures that will never
                # succeed on retry — stop reconnecting instead of looping forever.
                import aiohttp
                err_str = str(exc).lower()
                if isinstance(exc, aiohttp.WSServerHandshakeError) and exc.status in {401, 403}:
                    logger.error("Mattermost WS auth failed (HTTP %d) — stopping reconnect", exc.status)
                    return
                if "401" in err_str or "403" in err_str or "unauthorized" in err_str:
                    logger.error("Mattermost WS permanent error: %s — stopping reconnect", exc)
                    return
                logger.warning("Mattermost WS error: %s — reconnecting in %.0fs", exc, delay)

            if self._closing:
                return

            # Exponential backoff with jitter.
            import random
            jitter = delay * _RECONNECT_JITTER * random.random()
            await asyncio.sleep(delay + jitter)
            delay = min(delay * 2, _RECONNECT_MAX_DELAY)

    async def _ws_connect_and_listen(self) -> None:
        """Single WebSocket session: connect, authenticate, process events."""
        # Build WS URL: https:// → wss://, http:// → ws://
        ws_url = re.sub(r"^http", "ws", self._base_url) + "/api/v4/websocket"
        logger.info("Mattermost: connecting to %s", ws_url)

        self._ws = await self._session.ws_connect(ws_url, heartbeat=30.0)

        # Authenticate via the WebSocket.
        auth_msg = {
            "seq": 1,
            "action": "authentication_challenge",
            "data": {"token": self._token},
        }
        await self._ws.send_json(auth_msg)
        logger.info("Mattermost: WebSocket connected and authenticated")

        async for raw_msg in self._ws:
            if self._closing:
                return

            if raw_msg.type in {
                raw_msg.type.TEXT,
                raw_msg.type.BINARY,
            }:
                try:
                    event = json.loads(raw_msg.data)
                except (json.JSONDecodeError, TypeError):
                    continue
                await self._handle_ws_event(event)
            elif raw_msg.type in {
                raw_msg.type.ERROR,
                raw_msg.type.CLOSE,
                raw_msg.type.CLOSING,
                raw_msg.type.CLOSED,
            }:
                logger.info("Mattermost: WebSocket closed (%s)", raw_msg.type)
                break

    async def _handle_ws_event(self, event: Dict[str, Any]) -> None:
        """Process a single WebSocket event."""
        event_type = event.get("event")
        if event_type != "posted":
            return

        data = event.get("data", {})
        raw_post_str = data.get("post")
        if not raw_post_str:
            return

        try:
            post = json.loads(raw_post_str)
        except (json.JSONDecodeError, TypeError):
            return

        # Ignore system posts.
        if post.get("type"):
            return

        post_id = post.get("id", "")

        # Dedup.
        if self._dedup.is_duplicate(post_id):
            return

        # Build message event.
        channel_id = post.get("channel_id", "")
        channel_type_raw = data.get("channel_type", "O")
        chat_type = _CHANNEL_TYPE_MAP.get(channel_type_raw, "channel")

        # Passive hygiene automation: on any non-DM thread reply, optionally
        # add a Markdown heading to the root post before normal mention-gating.
        # Run this before the self-message guard because the most common
        # qualifying reply may be PD One's own threaded answer to a user's
        # untitled root question.  This does not invoke the main agent or post
        # a public reply.
        await self._maybe_auto_heading_thread_root(post, channel_type_raw)

        # Ignore own messages for the main agent loop after passive hygiene.
        if post.get("user_id") == self._bot_user_id:
            return

        # For DMs, user_id is sufficient.  For channels, check for @mention.
        message_text = post.get("message", "")

        # Mention-gating for non-DM channels.
        # Config (config.yaml `mattermost.*` with env-var fallback):
        #   require_mention / MATTERMOST_REQUIRE_MENTION: Require @mention in channels (default: true)
        #   free_response_channels / MATTERMOST_FREE_RESPONSE_CHANNELS: Channel IDs where bot responds without mention
        #   allowed_channels / MATTERMOST_ALLOWED_CHANNELS: If set, bot ONLY responds in these channels (whitelist)
        #   ignored_channels / MATTERMOST_IGNORED_CHANNELS: If set, bot NEVER responds in these channels (blacklist)
        if channel_type_raw != "D":
            ignored_raw = self.config.extra.get("ignored_channels") if self.config.extra else None
            if ignored_raw is None:
                ignored_raw = os.getenv("MATTERMOST_IGNORED_CHANNELS", "")
            if isinstance(ignored_raw, list):
                ignored_channels = {str(c).strip() for c in ignored_raw if str(c).strip()}
            else:
                ignored_channels = {
                    c.strip() for c in str(ignored_raw).split(",") if c.strip()
                }
            if channel_id in ignored_channels:
                logger.debug(
                    "Mattermost: ignoring message in ignored channel: %s",
                    channel_id,
                )
                return

            # allowed_channels check (whitelist — must pass before other gating).
            # When set, messages from channels NOT in this list are silently
            # ignored, even if @mentioned.  DMs are already excluded above.
            allowed_raw = self.config.extra.get("allowed_channels") if self.config.extra else None
            if allowed_raw is None:
                allowed_raw = os.getenv("MATTERMOST_ALLOWED_CHANNELS", "")
            if isinstance(allowed_raw, list):
                allowed_channels = {str(c).strip() for c in allowed_raw if str(c).strip()}
            else:
                allowed_channels = {
                    c.strip() for c in str(allowed_raw).split(",") if c.strip()
                }
            if allowed_channels and channel_id not in allowed_channels:
                logger.debug(
                    "Mattermost: ignoring message in non-allowed channel: %s",
                    channel_id,
                )
                return

            require_mention_raw = None
            if self.config.extra:
                require_mention_raw = self.config.extra.get("require_mention")
            if require_mention_raw is None:
                require_mention_raw = os.getenv("MATTERMOST_REQUIRE_MENTION", "true")
            require_mention = str(require_mention_raw).lower() not in {"false", "0", "no"}

            free_channels_raw = None
            if self.config.extra:
                free_channels_raw = self.config.extra.get("free_response_channels")
            if free_channels_raw is None:
                free_channels_raw = os.getenv("MATTERMOST_FREE_RESPONSE_CHANNELS", "")
            if isinstance(free_channels_raw, list):
                free_channels = {str(ch).strip() for ch in free_channels_raw if str(ch).strip()}
            else:
                free_channels = {ch.strip() for ch in str(free_channels_raw).split(",") if ch.strip()}
            is_free_channel = channel_id in free_channels

            mention_patterns = [
                f"@{self._bot_username}",
                f"@{self._bot_user_id}",
            ]
            has_mention = any(
                pattern.lower() in message_text.lower()
                for pattern in mention_patterns
            )

            if has_mention:
                await self._maybe_append_mention_translation(
                    post,
                    has_mention=has_mention,
                    channel_type_raw=channel_type_raw,
                )

            if require_mention and not is_free_channel and not has_mention:
                logger.debug(
                    "Mattermost: skipping non-DM message without @mention (channel=%s)",
                    channel_id,
                )
                return

            # Strip @mention from the message text so the agent sees clean input.
            if has_mention:
                for pattern in mention_patterns:
                    message_text = re.sub(
                        re.escape(pattern), "", message_text, flags=re.IGNORECASE
                    ).strip()

        # Resolve sender info.
        sender_id = post.get("user_id", "")
        sender_name = data.get("sender_name", "").lstrip("@") or sender_id

        # Thread support: Mattermost replies carry root_id, while top-level
        # channel posts are themselves thread roots. Use the triggering post id
        # as the synthetic thread_id for non-DM root posts so each top-level
        # task gets its own Hermes session and progress/final replies stay in
        # that post's thread instead of sharing the whole channel root.
        thread_id = post.get("root_id") or (post_id if channel_type_raw != "D" else None)
        source = self.build_source(
            chat_id=channel_id,
            chat_type=chat_type,
            user_id=sender_id,
            user_name=sender_name,
            thread_id=thread_id,
            message_id=post_id,
        )
        from gateway.session import build_session_key
        session_key = build_session_key(source)
        thread_context: Optional[str] = None
        thread_file_ids: List[str] = []
        if thread_id:
            thread_context, thread_file_ids = await self._fetch_thread_context(
                thread_id,
                post_id,
                session_key=session_key,
            )

        # Determine message type.
        file_ids = [str(fid) for fid in (post.get("file_ids") or [])]
        for fid in thread_file_ids:
            if fid not in file_ids:
                file_ids.append(fid)
        msg_type = MessageType.TEXT
        if message_text[:1].isspace() and message_text.lstrip().startswith("/"):
            message_text = message_text.lstrip()
        if message_text.startswith("/"):
            msg_type = MessageType.COMMAND

        # Download file attachments immediately (URLs require auth headers
        # that downstream tools won't have).
        media_urls: List[str] = []
        media_types: List[str] = []
        for fid in file_ids:
            try:
                file_info = await self._api_get(f"files/{fid}/info")
                fname = file_info.get("name", f"file_{fid}")
                ext = Path(fname).suffix or ""
                mime = file_info.get("mime_type", "application/octet-stream")

                file_data, status, error = await self._download_file_bytes(fid)
                if file_data is not None:
                    from gateway.platforms.base import cache_image_from_bytes, cache_document_from_bytes
                    if mime.startswith("image/"):
                        local_path = cache_image_from_bytes(file_data, ext or ".png")
                        media_urls.append(local_path)
                        media_types.append(mime)
                    elif mime.startswith("audio/"):
                        from gateway.platforms.base import cache_audio_from_bytes
                        local_path = cache_audio_from_bytes(file_data, ext or ".ogg")
                        media_urls.append(local_path)
                        media_types.append(mime)
                    else:
                        local_path = cache_document_from_bytes(file_data, fname)
                        media_urls.append(local_path)
                        media_types.append(mime)
                elif status is not None:
                    logger.warning("Mattermost: failed to download file %s: HTTP %s", fid, status)
                else:
                    logger.warning("Mattermost: failed to download file %s: %s", fid, error or "unknown error")
            except Exception as exc:
                logger.warning("Mattermost: error downloading file %s: %s", fid, exc)

        # Set message type based on downloaded media types.
        if media_types and msg_type == MessageType.TEXT:
            if any(m.startswith("image/") for m in media_types):
                msg_type = MessageType.PHOTO
            elif any(m.startswith("audio/") for m in media_types):
                msg_type = MessageType.VOICE
            elif media_types:
                msg_type = MessageType.DOCUMENT

        # Per-channel ephemeral prompt
        from gateway.platforms.base import resolve_channel_prompt
        _channel_prompt = resolve_channel_prompt(
            self.config.extra, channel_id, None,
        )
        policy_context = self._build_pd_one_policy_context(sender_id, channel_id, chat_type)
        workflow_context = self._build_pd_one_outbound_dm_workflow_context(sender_id, channel_id, chat_type, message_text, post)
        channel_context = self._combine_channel_context(policy_context, workflow_context, thread_context)

        msg_event = MessageEvent(
            text=message_text,
            message_type=msg_type,
            source=source,
            raw_message=post,
            message_id=post_id,
            media_urls=media_urls if media_urls else None,
            media_types=media_types if media_types else None,
            channel_prompt=_channel_prompt,
            channel_context=channel_context,
        )

        await self.handle_message(msg_event)




# ---------------------------------------------------------------------------
# Plugin standalone-send (out-of-process cron delivery via Mattermost REST)
# ---------------------------------------------------------------------------


async def _standalone_send(
    pconfig,
    chat_id: str,
    message: str,
    *,
    thread_id: Optional[str] = None,
    media_files: Optional[list] = None,
    force_document: bool = False,
) -> Dict[str, Any]:
    """Send via the Mattermost v4 REST API without a live gateway adapter.

    Used by ``tools/send_message_tool._send_via_adapter`` when the gateway
    runner is not in this process (typical for cron jobs running out-of-process).
    Reads ``MATTERMOST_TOKEN`` from ``pconfig.token`` (set by the gateway
    config loader from env) and falls back to the ``MATTERMOST_TOKEN`` env
    var.  Server URL comes from ``pconfig.extra["url"]`` (set by the YAML
    bridge / env loader) or the ``MATTERMOST_URL`` env var.

    Thread replies (Mattermost CRT) are supported via the ``root_id`` field
    on the ``POST /posts`` payload — pass ``thread_id`` when threading is
    desired.  ``media_files`` are uploaded via ``POST /files``
    (multipart/form-data), then their returned ``file_id`` values are
    attached to the post.

    ``force_document`` is accepted for signature parity with other
    standalone senders but unused — Mattermost stores every uploaded file
    as a generic attachment regardless.
    """
    try:
        import aiohttp
    except ImportError:
        return {"error": "aiohttp not installed. Run: pip install aiohttp"}

    base_url = (
        (getattr(pconfig, "extra", {}) or {}).get("url")
        or os.getenv("MATTERMOST_URL", "")
    ).rstrip("/")
    token = (getattr(pconfig, "token", None) or _get_scoped_secret("MATTERMOST_TOKEN", "")).strip()
    if not base_url or not token:
        return {
            "error": (
                "Mattermost standalone send: MATTERMOST_URL and "
                "MATTERMOST_TOKEN must both be set"
            )
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    upload_headers = {"Authorization": f"Bearer {token}"}

    media_files = media_files or []

    try:
        # Resolve proxy + session kwargs once so a single ClientSession can
        # cover the optional file uploads + final post.
        from gateway.platforms.base import resolve_proxy_url, proxy_kwargs_for_aiohttp
        _proxy = resolve_proxy_url(platform_env_var="MATTERMOST_PROXY")
        _sess_kw, _req_kw = proxy_kwargs_for_aiohttp(_proxy)

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            **_sess_kw,
        ) as session:
            # 1. Upload media (if any) and collect file_ids.
            file_ids: List[str] = []
            for media in media_files:
                file_path = media.get("path") if isinstance(media, dict) else media
                if not file_path or not os.path.exists(file_path):
                    continue
                with open(file_path, "rb") as fh:
                    form = _build_file_upload_form(
                        chat_id,
                        fh.read(),
                        os.path.basename(file_path),
                    )
                async with session.post(
                    f"{base_url}/api/v4/files",
                    data=form,
                    headers=upload_headers,
                    **_req_kw,
                ) as upload_resp:
                    if upload_resp.status not in {200, 201}:
                        body = await upload_resp.text()
                        return {
                            "error": (
                                f"Mattermost file upload failed "
                                f"({upload_resp.status}): {body[:400]}"
                            )
                        }
                    upload_data = await upload_resp.json()
                    for info in upload_data.get("file_infos", []):
                        if info.get("id"):
                            file_ids.append(info["id"])

            # 2. Post the message (with thread root + attached file_ids).
            payload: Dict[str, Any] = {
                "channel_id": chat_id,
                "message": message,
            }
            if thread_id:
                payload["root_id"] = thread_id
            if file_ids:
                payload["file_ids"] = file_ids
            async with session.post(
                f"{base_url}/api/v4/posts",
                headers=headers,
                json=payload,
                **_req_kw,
            ) as resp:
                if resp.status not in {200, 201}:
                    body = await resp.text()
                    return {
                        "error": (
                            f"Mattermost API error ({resp.status}): "
                            f"{body[:400]}"
                        )
                    }
                data = await resp.json()
            return {
                "success": True,
                "platform": "mattermost",
                "chat_id": chat_id,
                "message_id": data.get("id"),
            }
    except aiohttp.ClientError as exc:
        return {"error": f"Mattermost send failed (network): {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Mattermost send failed: {exc}"}


# ---------------------------------------------------------------------------
# Interactive setup wizard
# ---------------------------------------------------------------------------


def interactive_setup() -> None:
    """Guide the user through Mattermost bot setup.

    Mirrors Discord/Teams' ``interactive_setup`` shape: lazy-imports CLI
    helpers so the plugin's import surface stays small, prompts for the
    server URL + bot token, captures an allowlist, and offers to set a
    home channel.  Replaces the central
    ``hermes_cli/setup.py::_setup_mattermost`` function this migration
    removes.
    """
    from hermes_cli.config import get_env_value, remove_env_value, save_env_value
    from hermes_cli.cli_output import (
        prompt,
        prompt_yes_no,
        print_header,
        print_info,
        print_success,
    )

    print_header("Mattermost")
    existing = get_env_value("MATTERMOST_TOKEN")
    if existing:
        print_info("Mattermost: already configured")
        if not prompt_yes_no("Reconfigure Mattermost?", False):
            return

    print_info("Works with any self-hosted Mattermost instance.")
    print_info("   1. In Mattermost: Integrations → Bot Accounts → Add Bot Account")
    print_info("   2. Copy the bot token")
    print()
    mm_url = prompt("Mattermost server URL (e.g. https://mm.example.com)")
    if mm_url:
        save_env_value("MATTERMOST_URL", mm_url.rstrip("/"))
    token = prompt("Bot token", password=True)
    if not token:
        return
    save_env_value("MATTERMOST_TOKEN", token)
    print_success("Mattermost token saved")

    print()
    print_info("🔒 Security: Restrict who can use your bot")
    print_info("   To find your user ID: click your avatar → Profile")
    print_info("   or use the API: GET /api/v4/users/me")
    print()
    allowed_users = prompt("Allowed user IDs (comma-separated, leave empty for open access)")
    if allowed_users:
        save_env_value("MATTERMOST_ALLOWED_USERS", allowed_users.replace(" ", ""))
        print_success("Mattermost allowlist configured")
    else:
        print_info("⚠️  No allowlist set - anyone who can message the bot can use it!")

    print()
    print_info("📬 Home Channel: where Hermes delivers cron job results and notifications.")
    print_info("   To get a channel ID: click channel name → View Info → copy the ID")
    print_info("   You can also set this later by typing /set-home in a Mattermost channel.")
    home_channel = prompt("Home channel ID (leave empty to set later with /set-home)").strip()
    if home_channel:
        save_env_value("MATTERMOST_HOME_CHANNEL", home_channel)
    else:
        if remove_env_value("MATTERMOST_HOME_CHANNEL"):
            print_info("Home channel cleared.")
    print_info("   Open config in your editor:  hermes config edit")


# ---------------------------------------------------------------------------
# YAML → env config bridge (apply_yaml_config_fn, #25443)
# ---------------------------------------------------------------------------


def _apply_yaml_config(yaml_cfg: dict, mattermost_cfg: dict) -> dict | None:
    """Translate ``config.yaml`` ``mattermost:`` keys into env vars.

    Implements the ``apply_yaml_config_fn`` contract (#24836 / #25443).
    Mirrors the legacy ``mattermost_cfg`` block that used to live in
    ``gateway/config.py::load_gateway_config()`` before this migration.

    Most MattermostAdapter runtime configuration is read from
    ``PlatformConfig.extra`` first, then environment variables.  This hook
    therefore seeds adapter-owned extras while preserving the historical
    YAML→env bridge for env-driven call sites.

    Env vars take precedence over YAML — every assignment is guarded
    by ``not os.getenv(...)`` so an explicit env var survives a config.yaml
    update.  Returns a dict of adapter-owned extras for the gateway config
    loader to merge into ``PlatformConfig.extra``.
    """
    seeded: dict[str, object] = {}
    if "require_mention" in mattermost_cfg and not os.getenv("MATTERMOST_REQUIRE_MENTION"):
        os.environ["MATTERMOST_REQUIRE_MENTION"] = str(mattermost_cfg["require_mention"]).lower()
    if (
        "auto_translate_mentioned_channel_messages" in mattermost_cfg
        and not os.getenv("MATTERMOST_AUTO_TRANSLATE_MENTIONED_CHANNEL_MESSAGES")
    ):
        os.environ["MATTERMOST_AUTO_TRANSLATE_MENTIONED_CHANNEL_MESSAGES"] = str(
            mattermost_cfg["auto_translate_mentioned_channel_messages"]
        ).lower()
    if "auto_translate_mentioned_channel_messages" in mattermost_cfg:
        seeded["auto_translate_mentioned_channel_messages"] = mattermost_cfg[
            "auto_translate_mentioned_channel_messages"
        ]
    if "auto_thread_root_heading" in mattermost_cfg:
        seeded["auto_thread_root_heading"] = mattermost_cfg["auto_thread_root_heading"]
    if "auto_thread_root_heading_disabled_channels" in mattermost_cfg:
        seeded["auto_thread_root_heading_disabled_channels"] = mattermost_cfg[
            "auto_thread_root_heading_disabled_channels"
        ]
    frc = mattermost_cfg.get("free_response_channels")
    if frc is not None and not os.getenv("MATTERMOST_FREE_RESPONSE_CHANNELS"):
        if isinstance(frc, list):
            frc = ",".join(str(v) for v in frc)
        os.environ["MATTERMOST_FREE_RESPONSE_CHANNELS"] = str(frc)
    # allowed_channels: if set, bot ONLY responds in these channels (whitelist)
    ac = mattermost_cfg.get("allowed_channels")
    if ac is not None and not os.getenv("MATTERMOST_ALLOWED_CHANNELS"):
        if isinstance(ac, list):
            ac = ",".join(str(v) for v in ac)
        os.environ["MATTERMOST_ALLOWED_CHANNELS"] = str(ac)
    # ignored_channels: if set, bot NEVER responds in these channels (blacklist)
    ic = mattermost_cfg.get("ignored_channels")
    if ic is not None and not os.getenv("MATTERMOST_IGNORED_CHANNELS"):
        if isinstance(ic, list):
            ic = ",".join(str(v) for v in ic)
        os.environ["MATTERMOST_IGNORED_CHANNELS"] = str(ic)
    return seeded or None


# ---------------------------------------------------------------------------
# is_connected probe
# ---------------------------------------------------------------------------


def _is_connected(config) -> bool:
    """Mattermost is considered connected when BOTH MATTERMOST_TOKEN and
    MATTERMOST_URL are set.

    Looks up via ``hermes_cli.gateway.get_env_value`` at call time (not via
    the plugin's own bound import) so tests that patch
    ``gateway_mod.get_env_value`` can suppress ambient env vars.  Matches
    what the legacy connected-platforms check did before this migration.
    """
    import hermes_cli.gateway as gateway_mod
    return bool(
        (gateway_mod.get_env_value("MATTERMOST_TOKEN") or "").strip()
        and (gateway_mod.get_env_value("MATTERMOST_URL") or "").strip()
    )


# ---------------------------------------------------------------------------
# Plugin registration entry point
# ---------------------------------------------------------------------------


def _build_adapter(config):
    """Factory wrapper that constructs MattermostAdapter from a PlatformConfig."""
    return MattermostAdapter(config)


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin system."""
    ctx.register_platform(
        name="mattermost",
        label="Mattermost",
        adapter_factory=_build_adapter,
        check_fn=check_mattermost_requirements,
        validate_config=validate_mattermost_config,
        is_connected=_is_connected,
        required_env=["MATTERMOST_URL", "MATTERMOST_TOKEN"],
        install_hint="pip install aiohttp",
        # Interactive setup wizard — replaces the central
        # hermes_cli/setup.py::_setup_mattermost function.
        setup_fn=interactive_setup,
        # YAML→env config bridge — owns the translation of
        # ``config.yaml`` ``mattermost:`` keys (require_mention,
        # free_response_channels, allowed_channels, ignored_channels) into ``MATTERMOST_*``
        # env vars that the adapter reads via ``os.getenv()``.  Replaces
        # the hardcoded block that used to live in ``gateway/config.py``.
        # Hook contract: #24836 / #25443.
        apply_yaml_config_fn=_apply_yaml_config,
        # Auth env vars for _is_user_authorized() integration.
        allowed_users_env="MATTERMOST_ALLOWED_USERS",
        allow_all_env="MATTERMOST_ALLOW_ALL_USERS",
        # Cron home-channel delivery.
        cron_deliver_env_var="MATTERMOST_HOME_CHANNEL",
        # Out-of-process cron delivery via Mattermost REST API.  Without
        # this hook, ``deliver=mattermost`` cron jobs fail with "No live
        # adapter" when cron runs separately from the gateway.  Mirrors
        # the Discord / Teams pattern.
        standalone_sender_fn=_standalone_send,
        # Mattermost practical post-length limit (server default is 16383
        # but 4000 is the readable threshold the adapter has used since
        # day one).
        max_message_length=MAX_POST_LENGTH,
        # Display
        emoji="💬",
        allow_update_command=True,
    )

"""Outbound Mattermost guard for PD One HRS private fields.

Live sends and the standalone cron/script sender both call into this module.
Membership comes from the Mattermost channel being posted to, never from text
the model wrote into the message.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.platforms._shared import get_scoped_secret as _get_scoped_secret
from tools.pd_one_hr_fields import (
    filter_private_hr_text,
    human_member_ids,
    members_are_hr_only,
    text_has_private_hr_markers,
)


def _cache_dir_from_config(config: Any) -> str:
    extra = getattr(config, "extra", None) or {}
    if isinstance(extra, dict) and extra.get("pd_one_policy_cache_users"):
        return str(extra["pd_one_policy_cache_users"])
    return str(_get_scoped_secret("PD_ONE_POLICY_CACHE_USERS", "") or "")


def _load_policy(cache_dir: str, user_id: str) -> dict | None:
    user_id = str(user_id or "").strip()
    if not cache_dir or not user_id or "/" in user_id or "\\" in user_id:
        return None
    path = Path(cache_dir).expanduser() / f"{user_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def _policies_for(cache_dir: str, user_ids: list[str]) -> list[dict | None]:
    return [_load_policy(cache_dir, user_id) for user_id in user_ids]


async def guard_adapter_outbound(adapter: Any, chat_id: str, text: str) -> str:
    """Filter a final ``send``. The adapter skips in-progress edits."""
    if not text_has_private_hr_markers(text):
        return text
    hr_only = await _adapter_destination_is_hr_only(adapter, chat_id)
    return filter_private_hr_text(text, hr_only=hr_only, chat_id=str(chat_id or ""))


async def _adapter_destination_is_hr_only(adapter: Any, chat_id: str) -> bool:
    members = await adapter._api_get(f"channels/{chat_id}/members")
    bot_id = str(getattr(adapter, "_bot_user_id", "") or "")
    user_ids = human_member_ids(members, bot_id)
    policies = []
    loader = getattr(adapter, "_load_pd_one_user_policy", None)
    for user_id in user_ids:
        policies.append(loader(user_id) if callable(loader) else None)
    if not user_ids:
        return False
    return members_are_hr_only(policies)


async def guard_standalone_outbound(
    pconfig: Any,
    chat_id: str,
    text: str,
    session: Any,
    base_url: str,
    headers: dict,
    request_kwargs: dict | None = None,
) -> str:
    """Filter ``_standalone_send`` (cron and script delivery)."""
    if not text_has_private_hr_markers(text):
        return text
    hr_only = await _standalone_destination_is_hr_only(
        pconfig, chat_id, session, base_url, headers, request_kwargs or {},
    )
    return filter_private_hr_text(text, hr_only=hr_only, chat_id=str(chat_id or ""))


async def _standalone_destination_is_hr_only(
    pconfig: Any,
    chat_id: str,
    session: Any,
    base_url: str,
    headers: dict,
    request_kwargs: dict,
) -> bool:
    origin = str(base_url or "").rstrip("/")
    me = await _read_json(session, f"{origin}/api/v4/users/me", headers, request_kwargs)
    if "/" in str(chat_id or "") or ".." in str(chat_id or ""):
        return False
    bot_id = str(me.get("id") or "") if isinstance(me, dict) else ""
    members = await _read_json(
        session, f"{origin}/api/v4/channels/{chat_id}/members", headers, request_kwargs,
    )
    user_ids = human_member_ids(members, bot_id)
    if not user_ids:
        return False
    cache_dir = _cache_dir_from_config(pconfig)
    return members_are_hr_only(_policies_for(cache_dir, user_ids))


async def _read_json(session: Any, url: str, headers: dict, request_kwargs: dict) -> Any:
    try:
        import aiohttp
    except ImportError:
        return None
    try:
        async with session.get(url, headers=headers, **request_kwargs) as response:
            if getattr(response, "status", 500) >= 400:
                return None
            return await response.json()
    except (aiohttp.ClientError, OSError, TypeError, ValueError, TimeoutError):
        return None


# Re-export used by tests that want the role helper next to the guard.
__all__ = [
    "guard_adapter_outbound",
    "guard_standalone_outbound",
]

#!/usr/bin/env python3
"""Add a Mattermost user to a channel (admin requester, readback required)."""
from __future__ import annotations

import re
from typing import Any, Callable

CHANNEL_ID_RE = re.compile(r"^[a-z0-9]{26}$")
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
CONFIRMATION = "ADD_CHANNEL_MEMBER"


def normalize_username(username: str) -> str:
    text = str(username or "").strip()
    if text.startswith("@"):
        text = text[1:]
    if not USERNAME_RE.fullmatch(text):
        raise ValueError(f"invalid username: {username!r}")
    return text


def normalize_channel_id(channel_id: str) -> str:
    text = str(channel_id or "").strip()
    if not CHANNEL_ID_RE.fullmatch(text):
        raise ValueError(f"invalid channel_id: {channel_id!r}")
    return text


def _load_requester_policy(requester_id: str) -> dict[str, Any]:
    from tools.pd_one_safe_ops import load_user_policy

    policy = load_user_policy(str(requester_id or "").strip())
    return policy if isinstance(policy, dict) else {}


def requester_is_admin(requester_id: str, *, policy: dict[str, Any] | None = None) -> bool:
    resolved = policy if policy is not None else _load_requester_policy(requester_id)
    if resolved.get("found") is not True or resolved.get("active") is not True:
        return False
    roles = {str(role).strip().lower() for role in (resolved.get("roles") or [])}
    return "admin" in roles


def _default_http(
    method: str,
    base: str,
    headers: dict[str, str],
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    allow_status: set[int] | None = None,
) -> tuple[int, dict[str, Any] | list[Any] | None]:
    import requests

    response = requests.request(
        method,
        f"{base}{path}",
        headers=headers,
        json=json_body,
        timeout=35,
    )
    allowed = allow_status or {200, 201, 204}
    if response.status_code not in allowed:
        raise RuntimeError(f"Mattermost {method} {path} failed status={response.status_code}")
    if not response.content:
        return response.status_code, {}
    try:
        body = response.json()
    except ValueError:
        return response.status_code, {}
    return response.status_code, body


def execute_channel_member_add(
    *,
    channel_id: str,
    username: str,
    requester_id: str,
    confirm: str = "",
    http_call: Callable[..., tuple[int, Any]] | None = None,
    mattermost_context: Callable[[], tuple[str, dict[str, str], dict[str, Any]]] | None = None,
    policy_loader: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    channel = normalize_channel_id(channel_id)
    uname = normalize_username(username)
    requester = str(requester_id or "").strip()
    if not requester:
        raise ValueError("requester_id is required")
    if str(confirm or "").strip() != CONFIRMATION:
        raise ValueError(f"confirm must be {CONFIRMATION!r}")
    load_policy = policy_loader or _load_requester_policy
    policy = load_policy(requester)
    if not requester_is_admin(requester, policy=policy):
        raise ValueError("requester_id must be an active admin (exact sender id, not display name)")
    if mattermost_context is None:
        from tools.pd_one_ops.pd_one_safe_ops_part1 import mattermost_context as _ctx

        ctx = _ctx
    else:
        ctx = mattermost_context
    base, headers, _me = ctx()
    call = http_call or _default_http
    _status, user = call("GET", base, headers, f"/api/v4/users/username/{uname}")
    if not isinstance(user, dict):
        raise RuntimeError(f"user lookup for {uname!r} returned unexpected payload")
    if int(user.get("delete_at") or 0):
        raise ValueError(f"user {uname!r} is not active")
    user_id = str(user.get("id") or "")
    member_status, member = call(
        "GET",
        base,
        headers,
        f"/api/v4/channels/{channel}/members/{user_id}",
        allow_status={200, 404},
    )
    if member_status == 200 and isinstance(member, dict):
        return {
            "status": "ok",
            "capability": "pd_one_mattermost_channel_member_add",
            "already_member": True,
            "channel_id": channel,
            "username": uname,
            "user_id": user_id,
            "requester_id": requester,
            "readback": member,
        }
    call(
        "POST",
        base,
        {**headers, "Content-Type": "application/json"},
        f"/api/v4/channels/{channel}/members",
        json_body={"user_id": user_id},
        allow_status={201, 200},
    )
    read_status, readback = call(
        "GET",
        base,
        headers,
        f"/api/v4/channels/{channel}/members/{user_id}",
        allow_status={200},
    )
    if read_status != 200 or not isinstance(readback, dict):
        raise RuntimeError("channel membership readback missing after add")
    return {
        "status": "ok",
        "capability": "pd_one_mattermost_channel_member_add",
        "already_member": False,
        "channel_id": channel,
        "username": uname,
        "user_id": user_id,
        "requester_id": requester,
        "readback": readback,
    }
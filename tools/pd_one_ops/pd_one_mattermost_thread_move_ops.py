#!/usr/bin/env python3
"""Move a Mattermost thread to another channel (admin or IT support operator)."""
from __future__ import annotations

import re
from typing import Any, Callable

ID26_RE = re.compile(r"^[a-z0-9]{26}$")
CONFIRMATION = "MOVE_THREAD"
ALLOWED_REQUESTER_ROLES = frozenset({"admin", "it_support_operator"})


def _load_requester_policy(requester_id: str) -> dict[str, Any]:
    from tools.pd_one_safe_ops import load_user_policy

    policy = load_user_policy(str(requester_id or "").strip())
    return policy if isinstance(policy, dict) else {}


def requester_may_move(requester_id: str, *, policy: dict[str, Any] | None = None) -> bool:
    resolved = policy if policy is not None else _load_requester_policy(requester_id)
    if resolved.get("found") is not True or resolved.get("active") is not True:
        return False
    roles = {str(role).strip().lower() for role in (resolved.get("roles") or [])}
    return bool(roles & ALLOWED_REQUESTER_ROLES)


def _default_http(
    method: str,
    base: str,
    headers: dict[str, str],
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any] | None]:
    import requests

    response = requests.request(
        method,
        f"{base}{path}",
        headers=headers,
        json=json_body,
        timeout=60,
    )
    body: dict[str, Any] | None
    if response.content:
        try:
            parsed = response.json()
            body = parsed if isinstance(parsed, dict) else {"payload": parsed}
        except ValueError:
            body = {"raw_text": (response.text or "")[:2000]}
    else:
        body = {}
    return response.status_code, body


def execute_thread_move(
    *,
    post_id: str,
    channel_id: str,
    requester_id: str,
    confirm: str = "",
    http_call: Callable[..., tuple[int, Any]] | None = None,
    mattermost_context: Callable[[], tuple[str, dict[str, str], dict[str, Any]]] | None = None,
    policy_loader: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    post = str(post_id or "").strip()
    channel = str(channel_id or "").strip()
    requester = str(requester_id or "").strip()
    if not ID26_RE.fullmatch(post):
        raise ValueError(f"invalid post_id: {post_id!r}")
    if not ID26_RE.fullmatch(channel):
        raise ValueError(f"invalid channel_id: {channel_id!r}")
    if not requester:
        raise ValueError("requester_id is required")
    if str(confirm or "").strip() != CONFIRMATION:
        raise ValueError(f"confirm must be {CONFIRMATION!r}")
    load_policy = policy_loader or _load_requester_policy
    if not requester_may_move(requester, policy=load_policy(requester)):
        raise ValueError(
            "requester_id must be an active admin or it_support_operator (exact sender id)",
        )
    if mattermost_context is None:
        from tools.pd_one_ops.pd_one_safe_ops_part1 import mattermost_context as _ctx

        ctx = _ctx
    else:
        ctx = mattermost_context
    base, headers, _me = ctx()
    call = http_call or _default_http
    status, body = call(
        "POST",
        base,
        {**headers, "Content-Type": "application/json"},
        f"/api/v4/posts/{post}/move",
        json_body={"channel_id": channel},
    )
    if status == 501:
        return {
            "status": "error",
            "error": "move_not_implemented",
            "capability": "pd_one_mattermost_thread_move",
            "post_id": post,
            "channel_id": channel,
            "requester_id": requester,
            "http_status": status,
            "detail": "server returned 501; thread was not copied",
            "response": body,
        }
    if status >= 400:
        raise RuntimeError(f"Mattermost move failed status={status}")
    return {
        "status": "ok",
        "capability": "pd_one_mattermost_thread_move",
        "post_id": post,
        "channel_id": channel,
        "requester_id": requester,
        "http_status": status,
        "response": body,
    }
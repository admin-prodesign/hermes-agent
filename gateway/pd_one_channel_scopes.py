"""PD One/OpenClaw-style channel scope helpers for Hermes gateway runs.

The PD One migration keeps a single Hermes profile, but OpenClaw used
channel-bound agents to constrain behavior.  These helpers resolve a
Mattermost channel to a compact scope object, build the per-turn system
prompt, and hard-limit the toolsets passed to AIAgent when a scope defines
an allowlist.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def _dedupe_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _mattermost_config(user_config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(user_config, dict):
        return {}
    mattermost = user_config.get("mattermost")
    if isinstance(mattermost, dict):
        return mattermost
    platforms = user_config.get("platforms")
    if isinstance(platforms, dict):
        mm = platforms.get("mattermost")
        if isinstance(mm, dict):
            extra = mm.get("extra")
            if isinstance(extra, dict):
                return extra
    return {}


def _mattermost_scope_map(user_config: dict[str, Any]) -> dict[str, Any]:
    """Return the configured PD One channel scope map, if any.

    The canonical location is ``mattermost.pd_one_channel_scopes``.  A copy may
    also live under ``platforms.mattermost.extra`` after gateway config bridging;
    accept both so tests and callers can use either loaded-config shape.
    """

    if not isinstance(user_config, dict):
        return {}
    mattermost = user_config.get("mattermost")
    if isinstance(mattermost, dict):
        scopes = mattermost.get("pd_one_channel_scopes")
        if isinstance(scopes, dict):
            return scopes
    platforms = user_config.get("platforms")
    if isinstance(platforms, dict):
        mm = platforms.get("mattermost")
        if isinstance(mm, dict):
            extra = mm.get("extra")
            if isinstance(extra, dict):
                scopes = extra.get("pd_one_channel_scopes")
                if isinstance(scopes, dict):
                    return scopes
    return {}


def _is_admin_prefix(text: str | None, prefix: str = "admin:") -> bool:
    return str(text or "").lstrip().lower().startswith(prefix.lower())


def _configured_admin_ids(user_config: dict[str, Any]) -> set[str]:
    mm = _mattermost_config(user_config)
    candidates: list[Any] = []
    prefix_cfg = mm.get("pd_one_admin_prefix") if isinstance(mm.get("pd_one_admin_prefix"), dict) else {}
    for key in ("allow_from", "allow_admin_from", "group_allow_admin_from"):
        value = prefix_cfg.get(key) if isinstance(prefix_cfg, dict) else None
        if value is None:
            value = mm.get(key)
        if isinstance(value, list):
            candidates.extend(value)
        elif value:
            candidates.extend(str(value).split(","))
    return set(_dedupe_strings(candidates))


def _policy_cache_has_admin_role(user_config: dict[str, Any], user_id: str | None) -> bool:
    if not user_id:
        return False
    mm = _mattermost_config(user_config)
    cache_dir = mm.get("pd_one_policy_cache_users")
    if not cache_dir:
        return False
    try:
        data = json.loads((Path(str(cache_dir)).expanduser() / f"{user_id}.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict) or data.get("active") is False or data.get("found") is False:
        return False
    roles = {str(role).strip().lower() for role in (data.get("roles") or [])}
    scopes = {str(scope).strip().lower() for scope in (data.get("safeScopes") or [])}
    return "admin" in roles or "admin" in scopes


def _admin_prefix_authorized(user_config: dict[str, Any], user_id: str | None) -> bool:
    if not user_id:
        return False
    ids = _configured_admin_ids(user_config)
    if user_id in ids or f"id:{user_id}" in ids or f"user:{user_id}" in ids:
        return True
    return _policy_cache_has_admin_role(user_config, user_id)


def _admin_scope_from(scopes: dict[str, Any], channel_scope: dict[str, Any] | None) -> dict[str, Any] | None:
    for raw_scope in scopes.values():
        if isinstance(raw_scope, dict) and str(raw_scope.get("agent_id") or "") == "admin":
            scope = dict(raw_scope)
            if channel_scope is not None:
                scope["original_channel_scope"] = dict(channel_scope)
            scope["admin_prefix_invoked"] = True
            return scope
    return None


def resolve_pd_one_channel_scope(
    user_config: dict[str, Any],
    platform_key: str | None,
    channel_id: str | None,
    *,
    user_id: str | None = None,
    text: str | None = None,
) -> dict[str, Any] | None:
    """Resolve a Mattermost channel id to a PD One scope dict.

    Unknown channels can opt into a safe fallback by configuring ``_default``.
    An authorized ``admin:`` prefix from an admin sender temporarily selects the
    admin scope while preserving the original channel scope as metadata.
    Without an explicit fallback, no scope is applied so existing non-PD-One
    Mattermost deployments are unaffected.
    """

    if platform_key != "mattermost" or not channel_id:
        return None
    scopes = _mattermost_scope_map(user_config)
    if not scopes:
        return None
    raw_scope = scopes.get(str(channel_id)) or scopes.get("_default")
    if not isinstance(raw_scope, dict):
        return None
    scope = dict(raw_scope)
    scope.setdefault("channel_id", str(channel_id))
    scope["sender_user_id"] = str(user_id or "")
    if _is_admin_prefix(text) and _admin_prefix_authorized(user_config, user_id):
        admin_scope = _admin_scope_from(scopes, scope)
        if admin_scope is not None:
            admin_scope.setdefault("channel_id", str(channel_id))
            admin_scope["admin_prefix_channel_id"] = str(channel_id)
            return admin_scope
    return scope


# Scoped-only extensions are an explicit code-reviewed capability ceiling.
# Channel YAML may select among them but cannot invent arbitrary toolsets that
# the platform baseline did not already authorize.
_PD_ONE_SCOPED_EXTENSION_TOOLSETS = frozenset({
    "pd_one_wiki",
    "pdone_safe_ops",
    "pdone_worker_scheduling",
    "freecad_spkane",
    "freecad_neka",
})


def scoped_toolsets(platform_toolsets: Iterable[Any], scope: dict[str, Any] | None) -> list[str]:
    """Narrow platform tools to the channel allowlist and reviewed extensions."""

    baseline = _dedupe_strings(platform_toolsets)
    if not isinstance(scope, dict):
        return baseline
    allowed = scope.get("allowed_toolsets")
    if not isinstance(allowed, list):
        return baseline
    ceiling = set(baseline) | set(_PD_ONE_SCOPED_EXTENSION_TOOLSETS)
    return [name for name in _dedupe_strings(allowed) if name in ceiling]


def scoped_skills(scope: dict[str, Any] | None) -> list[str]:
    """Return ordered skills configured for a PD One channel scope."""

    if not isinstance(scope, dict):
        return []
    skills = scope.get("skills")
    if isinstance(skills, str):
        skills = [skills]
    if not isinstance(skills, list):
        return []
    return _dedupe_strings(skills)


def build_scope_prompt(scope: dict[str, Any] | None, *, channel_id: str | None = None) -> str:
    """Build the ephemeral system prompt for a resolved PD One channel scope."""

    if not isinstance(scope, dict):
        return ""
    agent_id = str(scope.get("agent_id") or "unknown")
    name = str(scope.get("name") or agent_id)
    resolved_channel = str(channel_id or scope.get("channel_id") or "unknown")
    workspace = str(scope.get("workspace") or "")
    toolsets = _dedupe_strings(scope.get("allowed_toolsets") or [])
    skills = scoped_skills(scope)
    custom_prompt = str(scope.get("prompt") or "").strip()

    lines = [
        "[PD One channel scope]",
        f"agent_id: {agent_id}",
        f"name: {name}",
        f"channel_id: {resolved_channel}",
    ]
    if scope.get("admin_prefix_invoked"):
        original_value = scope.get("original_channel_scope")
        original = original_value if isinstance(original_value, dict) else {}
        original_agent = str(original.get("agent_id") or "unknown")
        lines.extend(
            [
                "admin_prefix_invoked: true",
                f"original_channel_agent_id: {original_agent}",
                "An authorized admin: prefix selected the admin scope for this turn; keep the source thread context, but use admin privileges subject to normal approval/safety rules.",
            ]
        )
    if workspace:
        lines.append(f"workspace: {workspace}")
    if toolsets:
        lines.append(f"allowed_toolsets: {', '.join(toolsets)}")
    if skills:
        lines.append(f"preferred_skills: {', '.join(skills)}")
    lines.extend(
        [
            "This is a hard channel boundary for PD One/OpenClaw parity.",
            "Only perform work within this channel scope and the exact sender-id policy context.",
            "If the request exceeds this channel scope, refuse briefly or ask for an admin-approved handoff instead of using broader tools.",
        ]
    )
    if "pd_one_wiki" in toolsets:
        lines.extend(
            [
                "Wiki candidate workflow: when an in-scope answer finds source-backed durable company knowledge, call emit_wiki_update_candidate before the final reply.",
                "Use the current Mattermost channel_id from this scope/policy context as source_channel_id; use opaque post/thread/message IDs only, never raw URLs.",
                "Emit candidates only for concise durable facts with evidence, not for private/sensitive data, raw transcripts, speculation, or routine chat.",
            ]
        )
    if custom_prompt:
        lines.extend(["Channel-specific instructions:", custom_prompt])
    return "\n".join(lines)


def scope_signature_fragment(scope: dict[str, Any] | None) -> str:
    """Stable signature fragment so cached agents cannot cross channel scopes."""

    if not isinstance(scope, dict):
        return ""
    relevant = {
        "agent_id": scope.get("agent_id"),
        "channel_id": scope.get("channel_id"),
        "sender_user_id": scope.get("sender_user_id"),
        "admin_prefix_invoked": bool(scope.get("admin_prefix_invoked")),
        "workspace": scope.get("workspace"),
        "allowed_toolsets": _dedupe_strings(scope.get("allowed_toolsets") or []),
        "skills": scoped_skills(scope),
        "prompt": scope.get("prompt"),
    }
    return json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

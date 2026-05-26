"""PD One/OpenClaw-style channel scope helpers for Hermes gateway runs.

The PD One migration keeps a single Hermes profile, but OpenClaw used
channel-bound agents to constrain behavior.  These helpers resolve a
Mattermost channel to a compact scope object, build the per-turn system
prompt, and hard-limit the toolsets passed to AIAgent when a scope defines
an allowlist.
"""

from __future__ import annotations

import json
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


def resolve_pd_one_channel_scope(
    user_config: dict[str, Any],
    platform_key: str | None,
    channel_id: str | None,
) -> dict[str, Any] | None:
    """Resolve a Mattermost channel id to a PD One scope dict.

    Unknown channels can opt into a safe fallback by configuring ``_default``.
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
    return scope


def scoped_toolsets(platform_toolsets: Iterable[Any], scope: dict[str, Any] | None) -> list[str]:
    """Return effective toolsets after applying a channel scope allowlist."""

    if not isinstance(scope, dict):
        return _dedupe_strings(platform_toolsets)
    allowed = scope.get("allowed_toolsets")
    if not isinstance(allowed, list):
        return _dedupe_strings(platform_toolsets)
    return _dedupe_strings(allowed)


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
        "workspace": scope.get("workspace"),
        "allowed_toolsets": _dedupe_strings(scope.get("allowed_toolsets") or []),
        "skills": scoped_skills(scope),
        "prompt": scope.get("prompt"),
    }
    return json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

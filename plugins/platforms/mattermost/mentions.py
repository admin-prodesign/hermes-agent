"""Mattermost @mention helpers: outbound mention suppression and inbound bot-mention patterns."""

from __future__ import annotations

from typing import Any, Iterable

_MATTERMOST_DISABLE_MENTIONS_PROPS = {"disable_mentions": True}


def with_mentions_disabled(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a post payload that prevents Mattermost from firing mentions."""
    props, disable = payload.get("props"), _MATTERMOST_DISABLE_MENTIONS_PROPS
    payload["props"] = {**props, **disable} if isinstance(props, dict) else dict(disable)
    return payload


def legacy_bot_usernames(raw: Any) -> tuple[str, ...]:
    """Parse ``extra.legacy_bot_usernames`` (list or comma-separated string) into bare usernames.

    A renamed bot keeps its user id, but people keep typing the old ``@name``; listing it
    here keeps those posts recognised as mentions of the bot.
    """
    items = raw if isinstance(raw, (list, tuple)) else str(raw or "").split(",")
    names = (str(item).strip().lstrip("@").strip() for item in items)
    return tuple(dict.fromkeys(name for name in names if name))


def bot_mention_patterns(username: str, user_id: str, legacy: Iterable[str] = ()) -> list[str]:
    """``@<name>`` tokens that address the bot: current username, user id, then legacy usernames."""
    return [f"@{name}" for name in dict.fromkeys((username, user_id, *legacy)) if name]

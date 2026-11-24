"""Mattermost send target syntax: ``<channel_id>[:<root_post_id>]``.

Cron ``deliver`` and ``send_message`` both go through ``resolve_send_target``.
Without a parser, ``channel:root`` is handed to the adapter as one chat id, so
``POST /api/v4/posts`` is called with an invalid ``channel_id`` and no
``root_id``. Mattermost ids are 26 lowercase alphanumerics; the optional
second segment is the thread root.
"""

import re

_MATTERMOST_ID = r"[a-z0-9]{26}"
_SEND_TARGET_RE = re.compile(rf"^\s*({_MATTERMOST_ID})(?::({_MATTERMOST_ID}))?\s*$")


def parse_send_target(ref: str):
    """``target_ref_syntax_fn``: ``(channel_id, root_id | None)``, or None when
    the ref is not a Mattermost id (a name still goes to the channel directory)."""
    match = _SEND_TARGET_RE.fullmatch(ref or "")
    if match is None:
        return None
    return match.group(1), match.group(2)

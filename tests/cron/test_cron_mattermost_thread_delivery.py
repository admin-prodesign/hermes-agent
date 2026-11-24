"""Cron ``deliver=mattermost:<channel>[:<root>]`` must post into that thread.

Production (nemo, pdone profile): job ``94e9d234db6d`` stored
``mattermost:<channel_id>:<root_post_id>``. The resolver kept the whole
``channel:root`` string as ``chat_id`` and set ``thread_id=None``, logged
"origin has thread_id=... but delivery target lost it", then the standalone
fallback POSTed ``/api/v4/posts`` with that invalid ``channel_id`` and
Mattermost returned 403 ``api.context.permissions.app_error``. Job
``32621af63418`` stored only the channel, equal to its origin chat, and the
origin root was dropped the same way, so the report went top-level.

Mattermost ids are 26 lowercase alphanumerics. The third segment is the
thread root (``root_id``). A channel-only target inherits ``origin.thread_id``
only when it names the origin channel.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gateway.config import Platform, PlatformConfig

from cron import scheduler_delivery as sd

# Ids from the two production jobs (channel, then root post).
CHANNEL = "phimoeks3fdgbma7wng9wqjcto"
THREAD = "44pywwezrpgzdek14ppdghus8r"
OTHER_CHANNEL = "8ybghf9ay3bomk14iym8mr5xga"
OTHER_THREAD = "kbtpseqk1td6zrhd3g65hf5rxy"


def _job(deliver, origin):
    return {
        "id": "94e9d234db6d",
        "name": "nightly brief",
        "deliver": deliver,
        "wrap_response": False,
        "origin": origin,
    }


def _origin(chat_id, thread_id):
    return {"platform": "mattermost", "chat_id": chat_id, "thread_id": thread_id}


def _resolved(job):
    targets = sd._resolve_delivery_targets(job)
    assert len(targets) == 1, targets
    return targets[0]


def test_explicit_channel_and_thread_split_into_chat_and_thread():
    """``mattermost:<channel>:<thread>`` is a channel plus a root post, not one chat id."""
    target = _resolved(_job(
        f"mattermost:{CHANNEL}:{THREAD}",
        _origin(CHANNEL, OTHER_THREAD),
    ))
    assert target["platform"] == "mattermost"
    assert target["chat_id"] == CHANNEL
    assert target["thread_id"] == THREAD


def test_channel_only_target_inherits_origin_thread_on_the_same_channel():
    """A chat-only target on the origin channel keeps the root the job was scheduled from."""
    target = _resolved(_job(f"mattermost:{CHANNEL}", _origin(CHANNEL, THREAD)))
    assert target["chat_id"] == CHANNEL
    assert target["thread_id"] == THREAD


def test_channel_only_target_does_not_inherit_a_different_channels_thread():
    """Fan-out to another channel is not the origin conversation — no thread adoption."""
    target = _resolved(_job(f"mattermost:{OTHER_CHANNEL}", _origin(CHANNEL, THREAD)))
    assert target["chat_id"] == OTHER_CHANNEL
    assert target["thread_id"] is None


def test_bare_channel_without_an_origin_thread_stays_top_level():
    """A channel id with no origin lane is still just that channel."""
    target = _resolved(_job(f"mattermost:{CHANNEL}", None))
    assert target["chat_id"] == CHANNEL
    assert target["thread_id"] is None


def test_non_id_target_is_left_intact():
    """Names that are not Mattermost ids (``@admin``) stay a single chat id."""
    target = _resolved(_job("mattermost:@admin", _origin(CHANNEL, THREAD)))
    assert target["chat_id"] == "@admin"
    assert target["thread_id"] is None


class _Resp:
    def __init__(self, payload):
        self.status = 201
        self._payload = payload

    async def text(self):
        return ""

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class _Session:
    posts: list

    def __init__(self, *_args, **_kwargs):
        self.posts = []
        _Session.posts.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return _Resp({"id": "posted"})


def _gateway_config():
    cfg = MagicMock()
    cfg.platforms = {
        Platform.MATTERMOST: PlatformConfig(
            enabled=True,
            token="mm-bot-token",
            extra={"url": "https://mm.example.test"},
        )
    }
    return cfg


def _posted_payload(job):
    """Drive the standalone fallback and return the JSON body of POST /api/v4/posts."""
    _Session.posts = []
    with patch("gateway.config.load_gateway_config", return_value=_gateway_config()), \
         patch("aiohttp.ClientSession", _Session):
        error = sd._deliver_result(job, "Nightly report.", adapters=None, loop=None)
    assert error is None, error
    bodies = [
        kwargs.get("json")
        for session in _Session.posts
        for url, kwargs in session.posts
        if str(url).endswith("/api/v4/posts") and isinstance(kwargs.get("json"), dict)
    ]
    assert bodies, [session.posts for session in _Session.posts]
    return bodies[0]


def test_standalone_fallback_posts_parsed_channel_and_root():
    """The fallback sender posts channel_id and root_id, not the raw channel:thread string."""
    payload = _posted_payload(_job(
        f"mattermost:{CHANNEL}:{THREAD}",
        _origin(CHANNEL, OTHER_THREAD),
    ))
    assert payload.get("channel_id") == CHANNEL
    assert payload.get("root_id") == THREAD
    assert ":" not in str(payload.get("channel_id"))


def test_standalone_fallback_posts_inherited_origin_root():
    """A same-channel chat-only target reaches Mattermost as that origin root_id."""
    payload = _posted_payload(_job(f"mattermost:{CHANNEL}", _origin(CHANNEL, THREAD)))
    assert payload.get("channel_id") == CHANNEL
    assert payload.get("root_id") == THREAD

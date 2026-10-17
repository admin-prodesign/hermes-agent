"""Edge-trigger, dedupe, recovery, and webhook contract for nemo watchdogs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.deploy.nemo.watchdogs.common import (
    DEFAULT_SENDER_HEADER,
    Finding,
    IncidentStore,
    emit_events,
    post_alert,
    redact,
    webhook_cfg,
)


@pytest.fixture
def watch_home(tmp_path: Path, monkeypatch) -> Path:
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("NEMO_WATCH_STATE_DIR", str(home / "watchdogs" / "state"))
    monkeypatch.setenv("NEMO_WATCH_WEBHOOK_ENV", str(home / "watchdogs" / "webhook.env"))
    return home


def _finding(key: str = "unit:system:demo.service", extra: str = "failed") -> Finding:
    return Finding(key, "warn", "systemd unit failed", {"unit": "demo.service", "note": extra})


def test_new_finding_fires_once_then_dedupes_by_fingerprint(watch_home: Path) -> None:
    store = IncidentStore("failures", watch_home / "watchdogs" / "state")
    posted: list[tuple] = []
    first = emit_events("failures", [_finding()], store=store, poster=lambda *a, **k: posted.append((a, k)))
    assert [event.state for event in first] == ["firing"]
    assert len(posted) == 1
    posted.clear()
    again = emit_events("failures", [_finding()], store=store, poster=lambda *a, **k: posted.append((a, k)))
    assert again == []
    assert posted == []


def test_fingerprint_change_refires_and_clear_sends_recovery(watch_home: Path) -> None:
    store = IncidentStore("failures", watch_home / "watchdogs" / "state")
    posted: list[str] = []

    def poster(_name, _sev, title, _items, **kwargs):
        posted.append(f"{kwargs.get('state')}:{title}")

    emit_events("failures", [_finding(extra="a")], store=store, poster=poster)
    emit_events("failures", [_finding(extra="b")], store=store, poster=poster)
    emit_events("failures", [], store=store, poster=poster)
    silent = emit_events("failures", [], store=store, poster=poster)
    assert posted[0].startswith("firing:")
    assert posted[1].startswith("firing:")
    assert posted[2].startswith("resolved:")
    assert silent == []
    assert len(posted) == 3


def test_independent_keys_do_not_share_dedupe(watch_home: Path) -> None:
    store = IncidentStore("failures", watch_home / "watchdogs" / "state")
    events = emit_events(
        "failures",
        [_finding("unit:system:a.service"), _finding("unit:system:b.service")],
        store=store,
        poster=lambda *a, **k: None,
    )
    assert {event.key for event in events} == {"unit:system:a.service", "unit:system:b.service"}


def test_redact_strips_tokens_and_password_pairs() -> None:
    text = redact("Authorization: Bearer sk-abcdefghijklmnop last_error=password=hunter2")
    assert "sk-abcdefghijklmnop" not in text
    assert "hunter2" not in text
    assert "<redacted>" in text


def test_webhook_posts_sender_key_header_not_body(watch_home: Path, monkeypatch) -> None:
    env = watch_home / "watchdogs" / "webhook.env"
    env.parent.mkdir(parents=True)
    env.write_text(
        "WEBHOOK_URL=https://example.invalid/hook\nWEBHOOK_SENDER_KEY=test-sender-key\n",
        encoding="utf-8",
    )
    env.chmod(0o600)
    monkeypatch.delenv("NEMO_WATCH_DRY_RUN", raising=False)
    captured: dict = {}

    class _Resp:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    def opener(request, timeout=15):
        captured["url"] = request.full_url
        captured["headers"] = {key.lower(): value for key, value in request.headers.items()}
        captured["body"] = json.loads(request.data.decode())
        return _Resp()

    status = post_alert(
        "failures",
        "warn",
        "demo token=crsr_should_not_leak_value",
        [{"secret": "password=super-secret"}],
        opener=opener,
    )
    assert status == 204
    assert captured["url"] == "https://example.invalid/hook"
    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers[DEFAULT_SENDER_HEADER.lower()] == "test-sender-key"
    raw = json.dumps(captured["body"])
    assert "test-sender-key" not in raw
    assert "super-secret" not in raw
    assert "crsr_should_not_leak_value" not in raw


def test_webhook_env_rejects_group_readable_mode(watch_home: Path) -> None:
    env = watch_home / "watchdogs" / "webhook.env"
    env.parent.mkdir(parents=True)
    env.write_text("WEBHOOK_URL=https://example.invalid/hook\nWEBHOOK_SENDER_KEY=k\n", encoding="utf-8")
    env.chmod(0o644)
    with pytest.raises(RuntimeError, match="mode 600"):
        webhook_cfg(env)

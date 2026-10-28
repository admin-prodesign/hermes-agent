"""Neo Watch supervisor push and PD One notification router behaviour."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import hermes_autonomous_supervisor as supervisor
from scripts.deploy.nemo import neo_watch_webhook as neo
from scripts.pd_one_notification_router import (
    TARGET_RE,
    flush_held,
    load_state,
    parse_target,
    send_route,
)


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def _routes(home: Path, body: dict) -> None:
    path = home / "config" / "notification-routes.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding="utf-8")


def test_target_re_accepts_webhook_and_mattermost() -> None:
    assert TARGET_RE.fullmatch("webhook:https://example.invalid/hook")
    assert TARGET_RE.fullmatch("mattermost:@admin")
    assert TARGET_RE.fullmatch("Mattermost:channel-id")
    assert not TARGET_RE.fullmatch("ftp:bad")


def test_parse_target_webhook() -> None:
    kind, rest = parse_target("webhook:neo")
    assert kind == "webhook"
    assert rest == "neo"


def test_hold_ack_suppresses_mattermost_release(home: Path, monkeypatch) -> None:
    _routes(
        home,
        {
            "schema_version": 1,
            "routes": {
                "pd_one_failure_escalations": {
                    "pre_targets": ["webhook:neo"],
                    "hold_minutes": 10,
                    "targets": ["mattermost:@admin"],
                }
            },
        },
    )
    posts: list[dict] = []
    mm: list[tuple] = []

    monkeypatch.setattr(neo, "post_json_webhook", lambda payload, **kw: posts.append(payload) or True)
    monkeypatch.setattr(
        "scripts.pd_one_notification_router.deliver_mattermost",
        lambda channel, message, dry_run=False: mm.append(message) or True,
    )

    event = {"summary": "disk full", "fingerprint": "abc123"}
    result = send_route(home, "pd_one_failure_escalations", event, dry_run=False)
    assert result["status"] == "held"
    assert len(posts) == 1
    assert mm == []

    correlation = result["correlation_key"]
    from scripts.pd_one_notification_router import cmd_ack

    assert cmd_ack(home, correlation) == 0

    t1 = datetime(2026, 1, 1, 12, 20, tzinfo=timezone.utc)
    state = load_state(home)
    released = flush_held(home, state, dry_run=False, now=t1)
    assert released == 0
    assert mm == []


def test_hold_expiry_releases_to_mattermost(home: Path, monkeypatch) -> None:
    _routes(
        home,
        {
            "schema_version": 1,
            "routes": {
                "pd_one_failure_escalations": {
                    "pre_targets": ["webhook:neo"],
                    "hold_minutes": 5,
                    "targets": ["mattermost:@admin"],
                }
            },
        },
    )
    monkeypatch.setattr(neo, "post_json_webhook", lambda *a, **k: True)
    mm: list[str] = []
    monkeypatch.setattr(
        "scripts.pd_one_notification_router.deliver_mattermost",
        lambda channel, message, dry_run=False: mm.append(message) or True,
    )

    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    send_route(
        home,
        "pd_one_failure_escalations",
        {"summary": "stuck job", "fingerprint": "fp1"},
        now=t0,
    )
    t_expired = t0 + timedelta(minutes=6)
    assert flush_held(home, dry_run=False, now=t_expired) == 1
    assert mm == ["stuck job"]


def test_supervisor_dedupes_fingerprint_push(home: Path) -> None:
    posts: list[dict] = []
    state = {
        "findings": [{"id": "x", "severity": "critical", "subject": "fire"}],
        "notified_fingerprint": "",
    }
    supervisor.save_json(supervisor.state_path(home), state)
    with patch.object(neo, "post_json_webhook", side_effect=lambda payload, **kw: posts.append(payload) or True):
        supervisor.persist_state(home, dict(state))
        supervisor.persist_state(home, supervisor.load_json(supervisor.state_path(home), {}))
    assert len(posts) == 1
    saved = supervisor.load_json(supervisor.state_path(home), {})
    assert saved.get("notified_fingerprint")


def test_supervisor_missing_url_env_noop(home: Path, monkeypatch) -> None:
    monkeypatch.setenv("NEO_WATCH_WEBHOOK_URL", "")
    monkeypatch.setenv("BRIEFING_REPAIR_WEBHOOK_URL", "")
    posts: list[dict] = []
    state = {"findings": [{"id": "x", "severity": "critical", "subject": "fire"}], "notified_fingerprint": ""}
    with patch.object(neo, "post_json_webhook", side_effect=lambda *a, **k: posts.append(a) or True):
        supervisor.persist_state(home, state)
    assert posts == []
    saved = supervisor.load_json(supervisor.state_path(home), {})
    assert not saved.get("notified_fingerprint")


def test_supervisor_deadman_single_escalation(home: Path, monkeypatch) -> None:
    _routes(
        home,
        {
            "schema_version": 1,
            "routes": {"pd_one_failure_escalations": {"targets": ["mattermost:@admin"]}},
        },
    )
    escalations: list[dict] = []
    monkeypatch.setattr(
        supervisor,
        "escalate_deadman",
        lambda _h, *, correlation, summary, dry_run: escalations.append({"correlation": correlation, "summary": summary}) or True,
    )
    monkeypatch.setattr(supervisor, "is_correlation_acked", lambda _h, _c: False)

    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    state = {"findings": [{"id": "x", "severity": "critical", "subject": "fire"}], "notified_fingerprint": ""}
    with patch.object(neo, "post_json_webhook", return_value=True):
        state = supervisor.maybe_notify_neo(home, state, now=t0, dry_run=False)
        supervisor.save_json(supervisor.state_path(home), state)
        push_state = supervisor.load_json(supervisor.neo_push_path(home), {})
        push_state.setdefault("deadman", {})["started_at"] = neo.iso_now(t0 - timedelta(minutes=50))
        supervisor.save_json(supervisor.neo_push_path(home), push_state)
        state = supervisor.load_json(supervisor.state_path(home), {})
        supervisor.maybe_notify_neo(home, state, now=t0 + timedelta(minutes=50), dry_run=False)
        supervisor.maybe_notify_neo(home, state, now=t0 + timedelta(minutes=55), dry_run=False)
    assert len(escalations) == 1


def test_webhook_auth_headers_bearer_and_hmac(monkeypatch) -> None:
    monkeypatch.setenv("BRIEFING_REPAIR_WEBHOOK_BEARER", "tok")
    monkeypatch.setenv("BRIEFING_REPAIR_WEBHOOK_HMAC_SECRET", "sek")
    body = b'{"a":1}'
    headers = neo.build_auth_headers(body)
    assert headers["Authorization"] == "Bearer tok"
    assert headers["X-Hermes-Signature"].startswith("sha256=")


def test_ssl_verify_context_never_passes_cert_dir_as_cafile(monkeypatch, tmp_path: Path) -> None:
    capath = tmp_path / "certs"
    capath.mkdir()
    cafile_args: list[str | None] = []
    real_create = neo.ssl.create_default_context

    def tracking_create(*args, **kwargs):
        if "cafile" in kwargs:
            cafile_args.append(kwargs["cafile"])
        return real_create(*args, **kwargs)

    monkeypatch.setattr(neo.ssl, "create_default_context", tracking_create)
    monkeypatch.setattr(
        neo.ssl,
        "get_default_verify_paths",
        lambda: type("VerifyPaths", (), {"cafile": None, "capath": str(capath)})(),
    )
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    neo._ssl_verify_context()
    assert cafile_args == [] or all(p is None or not Path(str(p)).is_dir() for p in cafile_args)


def test_router_dry_run_does_not_write_hold_state(home: Path, monkeypatch) -> None:
    _routes(
        home,
        {
            "schema_version": 1,
            "routes": {
                "pd_one_failure_escalations": {
                    "pre_targets": ["webhook:neo"],
                    "hold_minutes": 10,
                    "targets": ["mattermost:@admin"],
                }
            },
        },
    )
    monkeypatch.setattr(neo, "post_json_webhook", lambda *a, **k: True)
    state_path = home / "state" / "pd_one_notification_router" / "state.json"
    send_route(home, "pd_one_failure_escalations", {"summary": "x", "fingerprint": "fp-dry"}, dry_run=True)
    assert not state_path.is_file()


def test_supervisor_tick_dry_run_skips_neo_push_file(home: Path, monkeypatch) -> None:
    monkeypatch.setattr(neo, "post_json_webhook", lambda *a, **k: True)
    state = {
        "findings": [{"id": "x", "severity": "critical", "subject": "fire"}],
        "notified_fingerprint": "",
    }
    supervisor.save_json(supervisor.state_path(home), state)
    push_path = supervisor.neo_push_path(home)
    supervisor.cmd_tick(home, dry_run=True)
    assert not push_path.is_file()

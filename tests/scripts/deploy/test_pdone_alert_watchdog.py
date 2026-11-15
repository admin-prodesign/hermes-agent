"""neo-watch PD One alert watchdog: detection, dedupe, resolve, payload, permissions."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.deploy.nemo import pdone_alert_watchdog as watch

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def _secrets(path: Path, *, mode: int = 0o600, **pairs: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in pairs.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, mode)


def _supervisor(home: Path, findings: list[dict]) -> None:
    path = home / "state" / "hermes_autonomous_supervisor" / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"findings": findings}), encoding="utf-8")


def _cron(home: Path, rel: str, jobs: list[dict]) -> None:
    path = home / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jobs), encoding="utf-8")


def test_collect_supervisor_critical_and_input_needed(home: Path) -> None:
    _supervisor(
        home,
        [
            {"id": "a1", "severity": "warning", "subject": "needs INPUT NEEDED from owner"},
            {"id": "a2", "severity": "info", "subject": "fine"},
            {"severity": "critical", "subject": "disk full"},
        ],
    )
    live = watch.collect_live_incidents(home, systemctl_runner=lambda _a: subprocess.CompletedProcess([], 0, "", ""))
    keys = set(live)
    assert "finding:a1" in keys
    assert len(keys) == 2
    assert "finding:a2" not in keys


def test_collect_cron_dedupes_across_paths(home: Path) -> None:
    job = {"id": "job1", "name": "digest", "last_status": "error", "last_error": "boom"}
    _cron(home, "cron/jobs.json", [job])
    _cron(home, "profiles/pdone/cron/jobs.json", [dict(job)])
    live = watch.collect_live_incidents(home, systemctl_runner=lambda _a: subprocess.CompletedProcess([], 0, "", ""))
    assert list(live) == ["cron:job1"]


def test_collect_failed_units(home: Path) -> None:
    def runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
        assert any("hermes-" in part for part in argv)
        return subprocess.CompletedProcess(argv, 0, "hermes-gateway-pdone.service failed\n", "")

    live = watch.collect_live_incidents(home, systemctl_runner=runner)
    assert "unit:hermes-gateway-pdone" in live


def test_permission_refusal_on_world_readable_secrets(home: Path, monkeypatch) -> None:
    path = watch.secrets_path(home)
    _secrets(path, mode=0o644, NEO_WATCH_WEBHOOK_URL="https://example.invalid/hook", NEO_WATCH_WEBHOOK_KEY="sekret")
    monkeypatch.delenv("NEO_WATCH_DRY_RUN", raising=False)
    with pytest.raises(SystemExit, match="mode 600"):
        watch.main(["--hermes-home", str(home)])


def test_dry_run_skips_secrets_and_prints_payload(home: Path, capsys, monkeypatch) -> None:
    _supervisor(home, [{"id": "x", "severity": "critical", "subject": "fire"}])
    monkeypatch.setattr(
        watch,
        "_list_failed_hermes_units",
        lambda _runner=None: [],
    )
    code = watch.main(["--hermes-home", str(home), "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0
    assert "neo-watch.alert.v1" in out
    assert "firing" in out


def test_dedupe_and_six_hour_cooldown(home: Path, monkeypatch) -> None:
    _supervisor(home, [{"id": "x", "severity": "critical", "subject": "fire"}])
    posts: list[dict] = []
    monkeypatch.setattr(watch, "post_webhook", lambda payload, dry_run=False: posts.append(payload) or True)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    watch.run_watchdog(home, now=t0)
    watch.run_watchdog(home, now=t0 + timedelta(minutes=5))
    assert len(posts) == 1
    watch.run_watchdog(home, now=t0 + timedelta(hours=7))
    assert len(posts) == 2


def test_resolve_after_three_clean_runs(home: Path, monkeypatch) -> None:
    _supervisor(home, [{"id": "x", "severity": "critical", "subject": "fire"}])
    posts: list[dict] = []
    monkeypatch.setattr(watch, "post_webhook", lambda payload, dry_run=False: posts.append(payload) or True)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    watch.run_watchdog(home, now=t0)
    _supervisor(home, [])
    for i in range(1, 4):
        watch.run_watchdog(home, now=t0 + timedelta(minutes=5 * i))
    states = [p["state"] for p in posts]
    assert states == ["firing", "resolved"]


def test_payload_cap_and_redaction() -> None:
    assert "«redacted»" in watch.redact_string("token=supersecretvalue123456789")
    long_title = "x" * 5000
    items = [{"detail": "note", "n": i} for i in range(20)]
    payload, truncated = watch.build_payload(
        None,
        key="unit:test",
        title=long_title,
        severity="critical",
        state="firing",
        items=items,
        host="nemo",
    )
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    assert len(encoded) <= watch.MAX_PAYLOAD_BYTES
    assert truncated or payload.get("truncated_items")


def test_deadman_after_forty_five_minutes(home: Path, monkeypatch) -> None:
    _supervisor(home, [{"id": "x", "severity": "critical", "subject": "fire"}])
    monkeypatch.setattr(watch, "post_webhook", lambda *a, **k: True)
    fallbacks: list[str] = []
    monkeypatch.setenv("NEO_WATCH_FALLBACK_TARGET", "mattermost:@owner")
    monkeypatch.setattr(watch, "send_mattermost_fallback", lambda msg, dry_run=False: fallbacks.append(msg) or True)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    watch.run_watchdog(home, now=t0)
    watch.run_watchdog(home, now=t0 + timedelta(minutes=50))
    assert len(fallbacks) == 1


def test_ack_suppresses_deadman(home: Path, monkeypatch) -> None:
    _supervisor(home, [{"id": "x", "severity": "critical", "subject": "fire"}])
    monkeypatch.setattr(watch, "post_webhook", lambda *a, **k: True)
    fallbacks: list[str] = []
    monkeypatch.setenv("NEO_WATCH_FALLBACK_TARGET", "mattermost:@owner")
    monkeypatch.setattr(watch, "send_mattermost_fallback", lambda msg, dry_run=False: fallbacks.append(msg) or True)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    watch.run_watchdog(home, now=t0)
    assert watch.main(["--hermes-home", str(home), "ack", "finding:x", "--note", "on it"]) == 0
    watch.run_watchdog(home, now=t0 + timedelta(minutes=50))
    assert fallbacks == []


def test_webhook_failure_triggers_fallback(home: Path, monkeypatch) -> None:
    _supervisor(home, [{"id": "x", "severity": "critical", "subject": "fire"}])
    monkeypatch.setattr(watch, "post_webhook", lambda *a, **k: False)
    fallbacks: list[str] = []
    monkeypatch.setenv("NEO_WATCH_FALLBACK_TARGET", "mattermost:@owner")
    monkeypatch.setattr(watch, "send_mattermost_fallback", lambda msg, dry_run=False: fallbacks.append(msg) or True)
    watch.run_watchdog(home)
    assert len(fallbacks) == 1


def test_units_render_alert_watch_timer(tmp_path: Path) -> None:
    from scripts.deploy.nemo.autodeploy_units import UnitOptions, render

    home = tmp_path / "hermes"
    units = render(UnitOptions(home=home, releases=home / "releases", mirror=tmp_path / "mirror.git"))
    assert "hermes-pdone-alert-watch.service" in units
    assert "OnUnitActiveSec=5min" in units["hermes-pdone-alert-watch.timer"]
    assert "pdone_alert_watchdog" in units["hermes-pdone-alert-watch.service"]

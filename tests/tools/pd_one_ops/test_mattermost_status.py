"""PD One Mattermost status monitor: provider probes and env switches."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tools.pd_one_ops.mattermost_status import config as cfg
from tools.pd_one_ops.mattermost_status import monitor
from tools.pd_one_ops.mattermost_status import providers as prov


@pytest.fixture
def status_home(tmp_path, monkeypatch):
    home = tmp_path / "profile"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(cfg, "STATE_DIR", home / "state" / "pd-one-mattermost-status")
    monkeypatch.setattr(cfg, "LOG_DIR", home / "logs" / "pd-one-mattermost-status")
    monkeypatch.setattr(cfg, "PDONE_CONFIG", home / "config.yaml")
    monkeypatch.setattr(cfg, "CHANNEL_ID", "chan-test")
    monkeypatch.setattr(cfg, "EXPECTED_HERMES_HOME", home)
    monkeypatch.setattr(cfg, "PROVIDER_CHECK_ENABLED", True)
    monkeypatch.setattr(cfg, "CANARY_ENABLED", True)
    monkeypatch.setattr(cfg, "HERMES_CANARY_ENABLED", True)
    (home / "config.yaml").write_text(
        "model:\n  default: grok-4.20-0309-non-reasoning\n  provider: xai-oauth\n",
        encoding="utf-8",
    )
    return home


def test_no_codex_strings_in_package_sources():
    root = Path(__file__).resolve().parents[3] / "tools" / "pd_one_ops" / "mattermost_status"
    banned = ("openai-codex", "codex oauth", "refresh_codex", "chatgpt.com", "OpenAI Codex")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for needle in banned:
            assert needle not in text, f"{needle} found in {path.name}"


def test_provider_metadata_xai_success(status_home, monkeypatch):
    calls: list[str] = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        resp = MagicMock()
        resp.status = 200
        resp.read.return_value = json.dumps({"data": [{"id": "grok"}]}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda *a: None
        return resp

    monkeypatch.setattr(prov.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        prov,
        "load_provider_runtime_credentials",
        lambda **kw: (
            {
                "provider": "xai-oauth",
                "base_url": "https://api.x.ai/v1",
                "api_key": "token",
                "source": "hermes-auth-store",
            },
            None,
        ),
    )
    ok, msg, detail = prov.check_provider_metadata()
    assert ok is True
    assert "catalog OK" in msg
    assert detail["models_http_code"] == 200
    assert calls and calls[0].endswith("/v1/models")


def test_inference_canary_failure_backoff_skips_runner(status_home, monkeypatch):
    monkeypatch.setattr(cfg, "CANARY_INTERVAL_SECONDS", 60)
    monkeypatch.setattr(cfg, "CANARY_FAILURE_BACKOFF_SECONDS", 900)
    runner_calls = 0

    def runner():
        nonlocal runner_calls
        runner_calls += 1
        return False, {"error": "boom"}

    state = {
        "codex_canary": {
            "last_run_utc": "2030-01-01T00:00:00+00:00",
            "ok": False,
            "auth_home": str(status_home),
            "profile_auth_context_ok": True,
        }
    }
    now = time.time()

    def parse_ts(value):
        if not value:
            return None
        return now - 120

    ok, msg, detail = prov.cached_canary_runner(
        state,
        state_key="codex_canary",
        enabled=True,
        force_env="PD_ONE_STATUS_FORCE_CANARY",
        interval_seconds=cfg.CANARY_INTERVAL_SECONDS,
        failure_backoff_seconds=cfg.CANARY_FAILURE_BACKOFF_SECONDS,
        stale_grace_seconds=cfg.CANARY_STALE_GRACE_SECONDS,
        disabled_msg="disabled",
        stale_msg="stale",
        ok_prefix="ok",
        fail_msg="fail",
        runner=runner,
        parse_iso_ts=parse_ts,
        utc_now_iso=lambda: "2030-01-01T00:02:00+00:00",
        tpe_stamp=lambda: "tpe",
    )
    assert runner_calls == 0
    assert ok is False
    assert detail.get("cached") is True


def test_switches_off_skip_provider_network(status_home, monkeypatch):
    monkeypatch.setattr(cfg, "PROVIDER_CHECK_ENABLED", False)
    monkeypatch.setattr(cfg, "CANARY_ENABLED", False)
    monkeypatch.setattr(cfg, "HERMES_CANARY_ENABLED", False)

    def boom(*a, **k):
        raise AssertionError("network should not run")

    monkeypatch.setattr(prov.urllib.request, "urlopen", boom)
    monkeypatch.setattr(prov, "_run_inference_canary", boom)
    monkeypatch.setattr(prov, "run_hermes_path_canary", boom)
    monkeypatch.setattr(monitor, "run_cmd", lambda *a, **k: (True, "active"))
    monkeypatch.setattr(
        monitor,
        "http_json",
        lambda url, **kw: (True, 200, {"id": "u1", "username": "bot"}),
    )

    ok, bad, detail = monitor.check_health("https://mm.example", "tok", {})
    assert "Provider metadata check disabled" in " ".join(ok)
    assert detail["inference_canary"]["skipped"] == "disabled"
    assert detail["hermes_path_canary"]["skipped"] == "disabled"


def test_main_requires_channel_id(status_home, monkeypatch):
    monkeypatch.setattr(cfg, "CHANNEL_ID", "")
    monkeypatch.setenv("PD_ONE_STATUS_DRY_RUN", "1")
    assert monitor.main() == 2

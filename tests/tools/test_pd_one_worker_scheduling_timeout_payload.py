"""Blank timeout_seconds in worker_scheduling MCP payload must not break int() coercion."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tools.pd_one_ops import pd_one_safe_ops_mcp_part0 as mcp


@pytest.fixture
def stub_preflight(monkeypatch):
    captured: dict[str, int] = {}

    def fake_run(_cmd, _out_dir, timeout_seconds: int) -> str:
        captured["wrapper_timeout"] = timeout_seconds
        return json.dumps({"status": "ok", "mode": "preflight_stub"})

    monkeypatch.setattr(
        mcp,
        "_worker_scheduling_command",
        lambda **_kw: (["stub"], Path("/tmp/stub"), False),
    )
    monkeypatch.setattr(mcp, "_run_worker_scheduling_command", fake_run)
    return captured


def test_preflight_blank_payload_timeout_uses_clamped_default(stub_preflight):
    cases = [
        {},
        {"timeout_seconds": ""},
        {"timeout_seconds": "   "},
        {"timeout_seconds": None},
    ]
    for payload in cases:
        out = json.loads(mcp.worker_scheduling("preflight", payload=payload))
        assert out["status"] == "ok"
        assert stub_preflight["wrapper_timeout"] == 180


def test_preflight_explicit_timeout_still_respects_clamp(stub_preflight):
    out = json.loads(
        mcp.worker_scheduling("preflight", payload={"timeout_seconds": 90}),
    )
    assert out["status"] == "ok"
    assert stub_preflight["wrapper_timeout"] == 90

    out = json.loads(
        mcp.worker_scheduling("preflight", payload={"timeout_seconds": 999}),
    )
    assert out["status"] == "ok"
    assert stub_preflight["wrapper_timeout"] == 180


def test_run_worker_scheduling_missing_min_timeout_site_setting_defaults_to_30(
    tmp_path,
    monkeypatch,
):
    seen: dict[str, int | None] = {}

    py = tmp_path / "python"
    py.write_text("")
    script = tmp_path / "run.py"
    script.write_text("")

    class FakeProc:
        returncode = 0

        def wait(self, timeout=None):
            seen["wait_timeout"] = timeout

    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: FakeProc())
    monkeypatch.setattr(mcp, "SCHEDULER_PYTHON", lambda: py)
    monkeypatch.setattr(mcp, "SCHEDULER_SCRIPT", lambda: script)
    monkeypatch.setattr(mcp, "SCHEDULER_PROJECT", lambda: tmp_path)

    def fake_site_text(name: str) -> str:
        if name == "WORKER_SCHEDULING_MIN_TIMEOUT_SECONDS":
            return ""
        return ""

    monkeypatch.setattr(mcp, "site_text", fake_site_text)

    out_dir = tmp_path / "receipts"
    result = json.loads(
        mcp._run_worker_scheduling_command(["stub"], out_dir, timeout_seconds=10),
    )
    assert result["status"] == "ok"
    assert seen["wait_timeout"] == 30


def test_sync_source_rollover_blank_payload_timeout_uses_default(monkeypatch):
    seen: dict[str, int] = {}

    def fake_sync(**kwargs):
        seen["timeout_seconds"] = kwargs["timeout_seconds"]
        return mcp._json_result({"status": "ok", "stub": True})

    monkeypatch.setattr(mcp, "worker_scheduling_sync_source_rollover", fake_sync)
    out = json.loads(
        mcp.worker_scheduling(
            "sync_source_rollover",
            payload={"timeout_seconds": ""},
        ),
    )
    assert out["status"] == "ok"
    assert seen["timeout_seconds"] == 420

import json
from unittest.mock import Mock

import tools.worker_scheduling_execution_tool as mod


def _available(monkeypatch):
    monkeypatch.setattr(mod, "_available", lambda: True)


def test_live_action_magic_phrase_still_requires_human_gate(monkeypatch):
    _available(monkeypatch)
    monkeypatch.setattr(
        "tools.approval.request_tool_approval",
        lambda *a, **k: {"approved": False, "message": "approval required"},
    )
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")))
    out = json.loads(mod.worker_scheduling_execute(
        action="solve_and_write_live",
        confirm_live_write=mod.LIVE_CONFIRM_PHRASE,
    ))
    assert out["success"] is False
    assert out["error"] == "human_approval_required"


def test_worker_subprocess_env_is_secret_scrubbed(monkeypatch):
    _available(monkeypatch)
    monkeypatch.setattr(mod, "build_subprocess_env", lambda **k: {"PATH": "/bin"})
    seen = {}
    def fake_run(*args, **kwargs):
        seen.update(kwargs)
        return Mock(returncode=0, stdout="ok", stderr="")
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    out = json.loads(mod.worker_scheduling_execute(action="preflight"))
    assert out["success"] is True
    assert seen["env"] == {"PATH": "/bin", "PYTHONUNBUFFERED": "1"}

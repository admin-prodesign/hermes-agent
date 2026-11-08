"""Behaviour contracts for AppSheet definition inspect/apply safe-ops tools."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.pd_one_ops import pd_one_appsheet_definition_ops as ops
import tools.pd_one_safe_ops as safe_ops


class _FakeClient:
    def __init__(self, *, app_id: str, app_name: str, apps: dict[str, dict]) -> None:
        self.app_id = app_id
        self.app_name = app_name
        self._apps = apps
        self.saved: list[dict] = []

    def load_app(self, version: str = "") -> tuple[dict, dict]:
        key = version or "latest"
        app = self._apps[key]
        return {"Success": True}, app

    def save_app(self, app: dict) -> dict:
        self.saved.append(app)
        self._apps["latest"] = app
        return {"status_code": 200, "success": True, "error": None, "text_len": 1, "wrapper": {}}

    def promote_stable(self, version: str) -> dict:
        return {"ok": True, "status_code": 200, "response": {"version": version}}


def _sample_app(version: str = "v1") -> dict:
    return {
        "Version": version,
        "StableVersion": version,
        "IsValid": True,
        "IsRunnable": True,
        "IsDeployable": True,
        "AppData": {"DataSchemas": [{"Name": "Case"}], "TableSlices": []},
        "Presentation": {"Controls": [{"Name": "Case_Form"}]},
    }


def test_mcp_handlers_register_definition_tools():
    handlers = safe_ops.mcp_read_handlers()
    assert "pd_one_appsheet_definition_inspect" in handlers
    assert "pd_one_appsheet_definition_apply_approved" in handlers
    assert callable(handlers["pd_one_appsheet_definition_inspect"])
    assert callable(handlers["pd_one_appsheet_definition_apply_approved"])


def test_inspect_returns_read_only_payload():
    app = _sample_app("42")
    client = _FakeClient(app_id=ops.DEFAULT_APP_ID, app_name=ops.DEFAULT_APP_NAME, apps={"latest": app, "42": app})

    payload = ops.inspect_definition(client_factory=lambda: client)
    assert payload["status"] == "ok"
    assert payload["capability"] == "pd_one_appsheet_definition_inspect"
    assert payload["safety"]["read_only"] is True
    assert payload["latest"]["Version"] == "42"
    assert client.saved == []


def test_apply_dry_run_does_not_save(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    home = tmp_path / "profiles" / "pdone"
    home.mkdir(parents=True)
    cache = home / "cache" / "scratch"
    cache.mkdir(parents=True)
    proposed_path = cache / "proposed.json"
    proposed = _sample_app("next")
    proposed_path.write_text(json.dumps(proposed), encoding="utf-8")
    envelope_path = cache / "envelope.json"
    envelope_path.write_text(
        json.dumps(
            {
                "patch_id": "demo-patch",
                "app_id": ops.DEFAULT_APP_ID,
                "app_name": ops.DEFAULT_APP_NAME,
                "proposed_app_path": str(proposed_path),
                "proposed_app_sha256": ops.app_json_sha256(proposed),
                "change_summary": ["add demo view"],
            }
        ),
        encoding="utf-8",
    )
    before = _sample_app("before")
    client = _FakeClient(
        app_id=ops.DEFAULT_APP_ID,
        app_name=ops.DEFAULT_APP_NAME,
        apps={"latest": before},
    )
    payload = ops.apply_definition(
        patch_envelope_path=str(envelope_path),
        dry_run=True,
        client_factory=lambda: client,
    )
    assert payload["mode"] == "dry-run"
    assert payload["plan"]["would_change"] is True
    assert client.saved == []


def test_apply_live_requires_confirm_and_ticket(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    home = tmp_path / "profiles" / "pdone"
    cache = home / "cache" / "scratch"
    cache.mkdir(parents=True)
    proposed_path = cache / "proposed.json"
    proposed = _sample_app("next")
    proposed_path.write_text(json.dumps(proposed), encoding="utf-8")
    envelope_path = cache / "envelope.json"
    envelope_path.write_text(
        json.dumps(
            {
                "patch_id": "demo-patch",
                "app_id": ops.DEFAULT_APP_ID,
                "proposed_app_path": str(proposed_path),
            }
        ),
        encoding="utf-8",
    )
    client = _FakeClient(
        app_id=ops.DEFAULT_APP_ID,
        app_name=ops.DEFAULT_APP_NAME,
        apps={"latest": _sample_app("before")},
    )
    with pytest.raises(SystemExit):
        ops.apply_definition(
            patch_envelope_path=str(envelope_path),
            dry_run=False,
            ticket_id="PDAPP-20261029-ABCDEF01",
            confirm_live_write="wrong",
            client_factory=lambda: client,
        )


def test_apply_live_saves_and_readbacks_with_ticket(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    profile = tmp_path / "profiles" / "pdone"
    cache = profile / "cache" / "scratch"
    cache.mkdir(parents=True)
    monkeypatch.setattr(
        ops,
        "authorize_ticket",
        lambda ticket_id, *, patch_id, app_id: {
            "ticket_id": ticket_id,
            "status": "approved",
            "patch_id": patch_id,
            "app_id": app_id,
        },
    )
    proposed = _sample_app("next")
    proposed_path = cache / "proposed.json"
    proposed_path.write_text(json.dumps(proposed), encoding="utf-8")
    envelope_path = cache / "envelope.json"
    envelope_path.write_text(
        json.dumps(
            {
                "patch_id": "demo-patch",
                "app_id": ops.DEFAULT_APP_ID,
                "app_name": ops.DEFAULT_APP_NAME,
                "proposed_app_path": str(proposed_path),
                "proposed_app_sha256": ops.app_json_sha256(proposed),
            }
        ),
        encoding="utf-8",
    )
    before = _sample_app("before")
    client = _FakeClient(
        app_id=ops.DEFAULT_APP_ID,
        app_name=ops.DEFAULT_APP_NAME,
        apps={"latest": before},
    )
    payload = ops.apply_definition(
        patch_envelope_path=str(envelope_path),
        dry_run=False,
        ticket_id="PDAPP-20261029-ABCDEF01",
        confirm_live_write=ops.LIVE_CONFIRMATION,
        client_factory=lambda: client,
    )
    assert payload["status"] == "ok"
    assert payload["writes"] is True
    assert payload["execution"]["verified"] is True
    assert len(client.saved) == 1
    assert Path(payload["snapshot_before_path"]).is_file()

"""Failure-autofix pages must hit the Neo hold before Mattermost.

The gate's router argv is what production runs. Parent options after ``send``
make argparse exit 2, so these tests fail if that order comes back.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest


def _stub(name: str, **attrs: object) -> None:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


_stub(
    "failure_autofix_admission_gate",
    cheap_reject=lambda *args, **kwargs: None,
    decide=lambda *args, **kwargs: None,
    record_verdict=lambda *args, **kwargs: None,
    should_page_recurrence=lambda *args, **kwargs: False,
)
_stub("failure_autofix_allowlist", try_allowlist_repair=lambda *args, **kwargs: {})
_stub("failure_autofix_thin_llm", run_thin_llm=lambda *args, **kwargs: {})

from scripts import failure_autofix_first_pass as first_pass
from scripts import hermes_autonomous_supervisor as supervisor
from scripts.deploy.nemo import profile_scripts
from scripts.deploy.nemo.cli import main as deploy_main
from scripts.hermes_release_paths import resolve_release_root
from scripts.pd_one_notification_router import main as router_main

REPO = Path(__file__).resolve().parents[2]


def _routes(home: Path) -> Path:
    path = home / "config" / "notification-routes.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "routes": {
                    "pd_one_failure_escalations": {
                        "pre_targets": ["webhook:neo"],
                        "hold_minutes": 10,
                        "targets": ["mattermost:@admin"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _alert() -> dict:
    return {
        "source": "automation-self-heal-monitor",
        "event_type": "pd-one.incident",
        "run_id": "run-1",
        "severity": "error",
    }


def _run_router(argv: list[str], capsys) -> tuple[int, dict]:
    if argv[1:3] == ["-m", "scripts.pd_one_notification_router"]:
        sys.argv = argv[2:]
    else:
        sys.argv = argv[1:]
    try:
        code = router_main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    payload: dict = {}
    text = (captured.out or "").strip()
    if text:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"raw": text}
    return code, payload


def _flags_after_send(argv: list[str]) -> list[str]:
    """The pre-fix gate order: ``send`` then ``--config`` / ``--state-dir``."""
    send_at = argv.index("send")
    head = argv[:send_at]
    tail = argv[send_at:]
    moved: list[str] = []
    kept: list[str] = []
    index = 0
    while index < len(head):
        token = head[index]
        if token in {"--config", "--state-dir"}:
            moved.extend(head[index : index + 2])
            index += 2
            continue
        kept.append(token)
        index += 1
    return [*kept, *tail[:1], *moved, *tail[1:]]


@pytest.fixture
def neo_before_mattermost(monkeypatch):
    calls: list[str] = []

    def post(payload, **kwargs):
        calls.append("neo")
        calls.append(str(payload.get("summary") or ""))
        calls.append(str(payload.get("message") or ""))
        return True

    def mattermost(channel, message, dry_run=False):
        calls.append("mattermost")
        return True

    monkeypatch.setattr(
        "scripts.pd_one_notification_router.neo.post_json_webhook",
        post,
    )
    monkeypatch.setattr(
        "scripts.pd_one_notification_router.deliver_mattermost",
        mattermost,
    )
    return calls


def test_release_root_prefers_agent_dir_then_runtime_current(
    tmp_path: Path, monkeypatch
) -> None:
    for relative in (
        "agent/scripts",
        "runtime/current/scripts",
        "releases/current/scripts",
    ):
        directory = tmp_path / relative
        directory.mkdir(parents=True)
        (directory / "pd_one_notification_router.py").write_text(
            "# marker\n", encoding="utf-8"
        )
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_AGENT_DIR", str(tmp_path / "agent"))
    assert resolve_release_root() == tmp_path / "agent"
    monkeypatch.delenv("HERMES_AGENT_DIR")
    assert resolve_release_root() == tmp_path / "runtime" / "current"


def test_first_pass_router_argv_holds_and_calls_neo_before_mattermost(
    tmp_path: Path, monkeypatch, capsys, neo_before_mattermost
) -> None:
    routes = _routes(tmp_path)
    state = tmp_path / "state" / "notification-router"
    monkeypatch.setenv("HERMES_AGENT_DIR", str(REPO))
    argv, cwd = first_pass.router_send_argv(
        _alert(),
        "page body for neo",
        config=routes,
        state_dir=state,
    )
    assert cwd == str(REPO)
    assert argv[1:3] == ["-m", "scripts.pd_one_notification_router"]
    send_at = argv.index("send")
    assert argv.index("--config") < send_at
    assert argv.index("--state-dir") < send_at

    code, payload = _run_router(argv, capsys)
    assert code == 0, payload
    assert payload["status"] == "held"
    assert neo_before_mattermost[0] == "neo"
    assert "mattermost" not in neo_before_mattermost
    assert "needs decision" in neo_before_mattermost[1].lower()
    assert "page body" in neo_before_mattermost[2]


def test_first_pass_page_uses_argv_that_parses(
    tmp_path: Path, monkeypatch, capsys, neo_before_mattermost
) -> None:
    """The subprocess the gate actually starts, not a helper it might stop calling."""
    routes = _routes(tmp_path)
    state = tmp_path / "state" / "notification-router"
    monkeypatch.setenv("HERMES_AGENT_DIR", str(REPO))
    monkeypatch.setenv("PD_ONE_NOTIFICATION_ROUTES", str(routes))
    monkeypatch.setenv("PD_ONE_NOTIFICATION_STATE_DIR", str(state))
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["cwd"] = kwargs.get("cwd")
        code, payload = _run_router(argv, capsys)
        return types.SimpleNamespace(
            returncode=code, stdout=json.dumps(payload), stderr=""
        )

    monkeypatch.setattr(first_pass.subprocess, "run", fake_run)
    result = first_pass._maybe_page(_alert(), "page body for neo")
    argv = captured["argv"]
    send_at = argv.index("send")
    assert argv.index("--config") < send_at
    assert argv.index("--state-dir") < send_at
    assert captured["cwd"] == str(REPO)
    assert result["rc"] == 0
    assert "held" in result["stdout_tail"]
    assert neo_before_mattermost[0] == "neo"
    assert "mattermost" not in neo_before_mattermost


def test_config_after_send_is_rejected_by_the_router(
    tmp_path: Path, monkeypatch, capsys, neo_before_mattermost
) -> None:
    routes = _routes(tmp_path)
    monkeypatch.setenv("HERMES_AGENT_DIR", str(REPO))
    argv, _cwd = first_pass.router_send_argv(
        _alert(),
        "page body",
        config=routes,
        state_dir=tmp_path / "state",
    )
    bad = _flags_after_send(argv)
    assert bad.index("send") < bad.index("--config")
    assert bad.index("send") < bad.index("--state-dir")
    code, payload = _run_router(bad, capsys)
    assert code == 2
    assert payload.get("status") != "held"
    assert neo_before_mattermost == []


def test_router_argv_falls_open_to_the_profile_script(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.delenv("HERMES_AGENT_DIR", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    argv, cwd = first_pass.router_send_argv(
        _alert(),
        "page body",
        config=tmp_path / "config" / "notification-routes.json",
        state_dir=tmp_path / "state",
    )
    assert cwd is None
    assert argv[1] == str(first_pass.NOTIFICATION_ROUTER)
    send_at = argv.index("send")
    assert argv.index("--config") < send_at
    assert argv.index("--state-dir") < send_at
    assert "falling back" in capsys.readouterr().err


def test_supervisor_router_argv_holds_before_mattermost(
    tmp_path: Path, monkeypatch, capsys, neo_before_mattermost
) -> None:
    routes = _routes(tmp_path)
    monkeypatch.setattr("scripts.pd_one_notification_router.DEFAULT_CONFIG", routes)
    cmd = supervisor._router_cmd(
        tmp_path,
        "send",
        "--route",
        "pd_one_failure_escalations",
        "--json",
        json.dumps({"summary": "dead-man hold", "fingerprint": "fp-1"}),
    )
    assert cmd.index("--hermes-home") < cmd.index("send")
    code, payload = _run_router(cmd, capsys)
    assert code == 0, payload
    assert payload["status"] == "held"
    assert neo_before_mattermost[0] == "neo"
    assert "mattermost" not in neo_before_mattermost


def test_synced_profile_router_script_holds_and_rejects_flags_after_send(
    tmp_path: Path,
) -> None:
    home = tmp_path / "hermes"
    copied = profile_scripts.sync_profile_scripts(REPO, home)
    assert all(item["ok"] for item in copied)
    routes = _routes(home)
    script = home / "scripts" / "pd_one_notification_router.py"
    base = [
        sys.executable,
        str(script),
        "--config",
        str(routes),
        "--state-dir",
        str(home / "router-state"),
        "--dry-run",
        "send",
        "--route",
        "pd_one_failure_escalations",
        "--event-id",
        "evt-1",
        "--correlation-key",
        "failure-autofix:src",
        "--severity",
        "error",
        "--title",
        "Needs decision",
        "--body",
        "page body",
    ]
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    held = subprocess.run(
        base,
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert held.returncode == 0, held.stderr
    assert '"status": "held"' in held.stdout
    bad = _flags_after_send(base)
    rejected = subprocess.run(
        bad,
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert rejected.returncode == 2
    assert "unrecognized arguments" in rejected.stderr


def test_sync_leaves_the_profile_script_when_the_release_file_is_missing(
    tmp_path: Path, capsys
) -> None:
    home = tmp_path / "home"
    kept = home / "scripts" / "failure_autofix_first_pass.py"
    kept.parent.mkdir(parents=True)
    kept.write_text("print('keep')\n", encoding="utf-8")
    result = profile_scripts.sync_profile_scripts(tmp_path / "empty-release", home)
    assert kept.read_text(encoding="utf-8") == "print('keep')\n"
    assert any(
        item["script"] == "failure_autofix_first_pass.py" and not item["ok"]
        for item in result
    )
    assert "missing" in capsys.readouterr().err


@pytest.mark.platforms("linux", "macos")
def test_cutover_copies_failure_autofix_scripts_into_the_profile(
    tmp_path: Path,
) -> None:
    home = tmp_path / "hermes"
    releases = home / "releases"
    (releases / "old").mkdir(parents=True)
    new = releases / "new"
    os.symlink("old", releases / "current")
    for relative, _name in profile_scripts.COPY_SOURCES:
        src = REPO / relative
        dest = new / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(src, dest)
    python = new / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    python.chmod(0o755)
    unit_dir = tmp_path / "units"
    unit_dir.mkdir()
    (unit_dir / "hermes.service").write_text(
        f"ExecStart={releases / 'old'}/.venv/bin/python\n",
        encoding="utf-8",
    )
    assert (
        deploy_main(
            [
                "cutover",
                "--hermes-home",
                str(home),
                "--build",
                "new",
                "--unit-dir",
                str(unit_dir),
            ]
        )
        == 0
    )
    copied = (home / "scripts" / "pd_one_notification_router.py").read_text(
        encoding="utf-8"
    )
    assert "pre_targets" in copied
    assert (home / "scripts" / "neo_watch_webhook.py").is_file()
    assert (home / "scripts" / "failure_autofix_first_pass.py").is_file()

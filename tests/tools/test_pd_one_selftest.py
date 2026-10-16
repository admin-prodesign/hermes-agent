"""The PD One safe-ops deploy-gate self-test.

It must pass on a healthy profile against a read-only (0444) copy of the release, fail on
the two v0.22.0 failure shapes (a release script executed without an interpreter, an unset
``pd_one.external`` key reaching a launch), and never run a child, reach the network, or write
outside its scratch directory while it calls tools.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from tools.pd_one_ops import pd_one_safe_ops_mcp_part0 as mcp
from tools.pd_one_ops import site_config
from tools.pd_one_ops.selftest import _call_tool, placeholder_arguments
from tools.pd_one_ops.selftest_guard import Guard, WriteRefused

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def healthy_home(tmp_path):
    root = tmp_path / "hermes"
    profile = root / "profiles" / "pdone"
    ledger = profile / "legacy-openclaw" / "workspace" / "tools"
    ledger.mkdir(parents=True)
    (ledger / "admin_approval_tickets.py").write_text("class ApprovalLedger:\n    pass\n", encoding="utf-8")
    external = tmp_path / "external"
    (external / "site-packages").mkdir(parents=True)
    (external / "sqlsrv_readonly.py").write_text("def load_env():\n    return {}\n", encoding="utf-8")
    (root / "config.yaml").write_text("model:\n  provider: auto\n", encoding="utf-8")
    (profile / "config.yaml").write_text(
        "pd_one:\n  external:\n"
        f"    winrm_python: {sys.executable}\n"
        f"    sqlsrv_readonly: {external / 'sqlsrv_readonly.py'}\n"
        f"    winrm_site_packages: {external / 'site-packages'}\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def guard(tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    release = tmp_path / "release"
    release.mkdir()
    with Guard(scratch, release) as active:
        yield active


@pytest.mark.platforms("posix")
def test_selftest_passes_against_a_readonly_copy_of_the_release(healthy_home):
    proc = subprocess.run(
        [sys.executable, "-m", "tools.pd_one_ops.selftest", "--readonly-copy", "--json",
         "--hermes-home", str(healthy_home)],
        cwd=str(REPO), capture_output=True, text=True, timeout=600, check=False,
    )
    report = json.loads(proc.stdout)
    failures = [r for r in report["results"] if r["status"] == "fail"]
    assert proc.returncode == 0 and not failures, failures
    assert report["release"] != str(REPO)
    tool_names = {r["name"] for r in report["results"]}
    assert {"pd_one_sqlsrv_windows_acl_read", "pd_one_smb_unc_content_search", "build_server"} <= tool_names
    assert any(name.startswith("start pd_one_sqlsrv_windows_acl_read.py") for name in tool_names)


def _guarded(tmp_path: Path) -> Guard:
    (tmp_path / "scratch").mkdir(exist_ok=True)
    (tmp_path / "release").mkdir(exist_ok=True)
    return Guard(tmp_path / "scratch", tmp_path / "release")


def test_a_release_script_launched_without_an_interpreter_fails(tmp_path):
    script = tmp_path / "release" / "helper.py"
    script.parent.mkdir()
    script.write_text("print('hi')\n", encoding="utf-8")
    script.chmod(0o444)

    def tool(path: str = "x") -> str:
        return mcp.run_json([str(script), "--path", path])

    def interpreted(path: str = "x") -> str:
        return mcp.run_json([sys.executable, str(script), "--path", path])

    with _guarded(tmp_path) as guard:
        direct = _call_tool("tool", tool, guard, frozenset())
        through_interpreter = _call_tool("tool", interpreted, guard, frozenset())
    assert direct.status == "fail"
    assert any("directly" in problem for problem in direct.problems)
    assert through_interpreter.status == "pass" and through_interpreter.launches == 1


def test_an_unset_external_key_fails_unless_declared_absent(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text("pd_one: {}\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    site_config.config_sources()

    def tool() -> str:
        return mcp.run_json([site_config.external_path("gog"), "drive", "get"])

    with _guarded(tmp_path) as guard:
        failed = _call_tool("tool", tool, guard, frozenset())
        allowed = _call_tool("tool", tool, guard, frozenset({"gog"}))
    assert failed.status == "fail" and failed.launches == 0
    assert any("pd_one.external" in problem for problem in failed.problems)
    assert allowed.status == "pass"


def test_guard_plans_children_and_refuses_network_and_outside_writes(guard, tmp_path):
    marker = tmp_path / "scratch" / "child-ran"
    proc = subprocess.run([sys.executable, "-c", f"open({str(marker)!r}, 'w')"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0 and not marker.exists()
    assert guard.launches[-1].argv[0] == sys.executable
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("example.com", 443))
    with pytest.raises(WriteRefused):
        open(tmp_path / "outside.txt", "w")
    with pytest.raises(WriteRefused):
        (tmp_path / "release" / "new.json").write_text("{}")
    assert any("release tree" in problem for launch in guard.launches for problem in launch.problems)
    (tmp_path / "scratch" / "inside.txt").write_text("ok")
    assert not (tmp_path / "outside.txt").exists()


def test_placeholders_force_dry_run_and_never_confirm():
    def tool(spreadsheet_id: str, values: list[float], live: bool = True, dry_run: bool = False,
             confirm_live_write: str = "") -> None:
        return None

    assert placeholder_arguments(tool) == {"spreadsheet_id": "selftest", "values": [1.0], "live": False, "dry_run": True}


def test_writes_are_restored_after_the_guard(tmp_path):
    with Guard(tmp_path / "scratch", tmp_path / "release"):
        pass
    (tmp_path / "after.txt").write_text("ok")
    assert subprocess.run([sys.executable, "-c", "pass"], check=False, timeout=60).returncode == 0
    assert os.access(tmp_path / "after.txt", os.R_OK)

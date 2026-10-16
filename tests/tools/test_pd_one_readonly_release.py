"""PD One safe-ops from an immutable release (every file 0444) with config on the profile.

Regression for the v0.22.0 nemo deploy: ``resolve_configured_path`` relocates a profile
``tools/<name>.py`` to the release copy, and the MCP wrapper executed that copy directly
(``[Errno 13] Permission denied`` for ``pd_one_sqlsrv_windows_acl_read.py``). The safe-ops MCP
child also ran without the served profile's home, so ``pd_one.external.winrm_python`` from the
profile config.yaml was invisible and reached the OS as ``<unset pd_one.external.winrm_python>``.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.pd_one_ops import pd_one_safe_ops_mcp_part0 as mcp
from tools.pd_one_ops import site_config
from tools.pd_one_ops.launch import checked_argv, child_env, python_argv
from tools.pd_one_ops.selftest import readonly_copy
from tools.pd_one_ops.selftest_guard import launch_problems

REPO = Path(__file__).resolve().parents[2]
_PROFILE_ENV = ("HERMES_PROFILE_HOME", "PD_ONE_PROFILE_HOME", "HERMES_PROFILE", "HERMES_PROFILE_NAME")
_RELEASE_SCRIPTS = (
    "pd_one_sqlsrv_windows_acl_read.py",
    "pd_one_smb_unc_content_search.py",
    "pd_one_dangerous_command_audit.py",
    "google_group_owner_ops.py",
    "mattermost_policy_lookup.py",
)


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    copy = readonly_copy(REPO)
    yield copy
    for path in [copy, *copy.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    shutil.rmtree(copy, ignore_errors=True)


@pytest.fixture
def install_root(tmp_path, monkeypatch):
    """HERMES_HOME on the install root; pd_one config only in profiles/pdone/config.yaml."""
    for key in _PROFILE_ENV:
        monkeypatch.delenv(key, raising=False)
    root = tmp_path / "hermes"
    (root / "profiles" / "pdone").mkdir(parents=True)
    (root / "config.yaml").write_text("model:\n  provider: auto\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(root))
    return root


def _profile_config(root: Path, text: str) -> Path:
    path = root / "profiles" / "pdone" / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def captured(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append([os.fspath(item) for item in argv])
        return subprocess.CompletedProcess(argv, 0, '{"ok": true}', "")

    monkeypatch.setattr(mcp.subprocess, "run", fake_run)
    return calls


@pytest.fixture
def release_package(release, monkeypatch):
    """Relocated profile tools resolve inside the 0444 copy."""
    monkeypatch.setattr(site_config, "_PACKAGE", release / "tools" / "pd_one_ops")
    monkeypatch.setattr(site_config, "_TOOLS_DIR", release / "tools")
    return release / "tools" / "pd_one_ops"


def test_copy_has_no_exec_bits(release):
    modes = {path.stat().st_mode & 0o777 for path in release.rglob("*.py")}
    assert modes == {0o444}


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("name", _RELEASE_SCRIPTS)
def test_release_helpers_start_from_a_0444_tree(release, install_root, name):
    ledger = install_root / "profiles" / "pdone" / "legacy-openclaw" / "workspace" / "tools"
    ledger.mkdir(parents=True)
    (ledger / "admin_approval_tickets.py").write_text("class ApprovalLedger:\n    pass\n", encoding="utf-8")
    script = release / "tools" / "pd_one_ops" / name
    env = {**child_env(), "PYTHONPATH": os.pathsep.join([str(release), str(REPO)])}
    proc = subprocess.run(python_argv(script, "--help"), env=env, cwd=str(release),
                          capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr[-800:]
    with pytest.raises(PermissionError):
        subprocess.run([str(script), "--help"], env=env, capture_output=True, timeout=60, check=False)


def test_acl_read_wrapper_runs_the_release_copy_through_an_interpreter(install_root, release_package, captured):
    mcp.pd_one_sqlsrv_windows_acl_read("user-id-placeholder", r"\\file-server\share\doc.txt")
    argv = captured[-1]
    assert argv[0] == sys.executable
    assert argv[1] == str(release_package / "pd_one_sqlsrv_windows_acl_read.py")
    assert launch_problems(argv) == []


def test_smb_search_reads_winrm_python_from_the_profile_config(install_root, release_package, captured, tmp_path):
    interpreter = tmp_path / "winrm-python"
    interpreter.write_text("", encoding="utf-8")
    _profile_config(install_root, f"pd_one:\n  external:\n    winrm_python: {interpreter}\n")
    mcp.pd_one_smb_unc_content_search(r"\\file-server\share", ["term"], requester_user_id="user-id-placeholder")
    argv = captured[-1]
    assert argv[:2] == [str(interpreter), str(release_package / "pd_one_smb_unc_content_search.py")]
    assert not any(arg.startswith(site_config.UNSET_MARK) for arg in argv)


def test_profile_config_layers_over_the_install_root(install_root):
    profile_config = _profile_config(install_root, "pd_one:\n  owner_display_name: Profile Owner\n")
    (install_root / "config.yaml").write_text("pd_one:\n  owner_display_name: Root Owner\n  portal_public_hosts: a.example\n", encoding="utf-8")
    assert site_config.owner_display_name() == "Profile Owner"
    assert site_config.site_text("PDONE_PORTAL_PUBLIC_HOSTS") == "a.example"
    assert site_config.config_sources() == [install_root / "config.yaml", profile_config]


def test_missing_winrm_python_fails_naming_the_key_and_config(install_root, release_package, captured):
    profile_config = _profile_config(install_root, "pd_one:\n  owner_display_name: Owner\n")
    result = json.loads(mcp.pd_one_smb_unc_content_search(r"\\file-server\share", ["term"]))
    assert captured == []
    assert result["error"] == "missing_external_config" and result["key"] == "winrm_python"
    assert "pd_one.external.winrm_python" in result["detail"] and str(profile_config) in result["detail"]


def test_unset_external_path_never_reaches_a_launch(install_root, captured):
    _profile_config(install_root, "pd_one: {}\n")
    with pytest.raises(site_config.MissingExternalConfig, match="pd_one.external.gog"):
        checked_argv([site_config.external_path("gog"), "drive", "get"])
    result = json.loads(mcp.run_json([site_config.external_path("hermes_bin"), "--version"]))
    assert (result["error"], result["key"]) == ("missing_external_config", "hermes_bin")
    assert captured == []


def test_stdio_mcp_child_gets_the_served_profile_home(install_root):
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override
    from tools.mcp_tool_config import _build_safe_env

    profile = install_root / "profiles" / "pdone"
    token = set_hermes_home_override(profile)
    try:
        assert _build_safe_env(None)["HERMES_HOME"] == str(profile)
        assert _build_safe_env({"HERMES_HOME": str(install_root)})["HERMES_HOME"] == str(install_root)
    finally:
        reset_hermes_home_override(token)

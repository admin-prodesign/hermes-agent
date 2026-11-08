"""Dashboard terminal Node deps: skip a present install; fail closed when sealed.

A release installed mode 0555 cannot accept ``npm ci``. When ``node_modules``
is already in the release, launch must not install. When it is missing and the
directory is not writable, one warning is logged and later calls do not retry.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

import pytest

from hermes_cli import main_tui_launch
from hermes_cli.terminal_node_deps import (
    TerminalDepsUnavailable,
    directory_writable,
    ensure_dashboard_terminal_deps,
    publish_terminal_node_modules,
    reset_terminal_deps_state,
    terminal_deps_install_command,
    terminal_node_deps_present,
)


@pytest.fixture(autouse=True)
def _reset_latch():
    reset_terminal_deps_state()
    yield
    reset_terminal_deps_state()


def _receipt(root: Path) -> None:
    modules = root / "node_modules"
    modules.mkdir(parents=True)
    (modules / ".hermes-node-deps").write_text("receipt\n", encoding="utf-8")


def _workspace_links(root: Path) -> None:
    modules = root / "node_modules"
    modules.mkdir(parents=True)
    (modules / ".package-lock.json").write_text("{}\n", encoding="utf-8")
    for workspace, name in (("ui-tui", "hermes-tui"), ("web", "web")):
        manifest = root / workspace
        manifest.mkdir()
        (manifest / "package.json").write_text(
            f'{{"name": "{name}"}}\n', encoding="utf-8")
        installed = modules / name
        installed.mkdir()
        (installed / "package.json").write_text(
            f'{{"name": "{name}"}}\n', encoding="utf-8")


def test_receipt_skips_install_and_does_not_probe(tmp_path, monkeypatch):
    root = tmp_path / "release"
    root.mkdir()
    _receipt(root)

    def refuse_probe(_path):
        raise AssertionError("writability probed although deps are present")

    monkeypatch.setattr(
        "hermes_cli.terminal_node_deps.directory_writable", refuse_probe)
    calls = []
    assert ensure_dashboard_terminal_deps(root, install=lambda: calls.append(1)) is True
    assert ensure_dashboard_terminal_deps(root, install=lambda: calls.append(1)) is True
    assert calls == []


def test_workspace_links_count_as_present_without_a_receipt(tmp_path):
    root = tmp_path / "release"
    root.mkdir()
    _workspace_links(root)
    assert terminal_node_deps_present(root) is True
    calls = []
    assert ensure_dashboard_terminal_deps(root, install=lambda: calls.append(1)) is True
    assert calls == []


def test_unwritable_missing_deps_warns_once_and_does_not_retry(tmp_path, monkeypatch, caplog):
    root = tmp_path / "release"
    root.mkdir()
    outside = tmp_path / "outside-cache"
    outside.mkdir()
    probes = []

    def not_writable(path):
        probes.append(path)
        return False

    monkeypatch.setattr("hermes_cli.terminal_node_deps.directory_writable", not_writable)
    calls = []
    with caplog.at_level(logging.WARNING, logger="hermes_cli.terminal_node_deps"):
        assert ensure_dashboard_terminal_deps(root, install=lambda: calls.append(1)) is False
        assert ensure_dashboard_terminal_deps(root, install=lambda: calls.append(1)) is False
    warnings = [record for record in caplog.records if "Dashboard terminal disabled" in record.message]
    assert len(warnings) == 1
    assert warnings[0].exc_info is None
    assert calls == []
    assert probes == [root]
    assert not (root / "node_modules").exists()
    assert list(outside.iterdir()) == []


@pytest.mark.platforms("linux")
def test_readonly_directory_with_missing_deps_warns_once(tmp_path, caplog):
    release = tmp_path / "release"
    release.mkdir()
    outside = tmp_path / "outside-cache"
    outside.mkdir()
    release.chmod(0o555)
    try:
        if os.geteuid() == 0:  # pragma: no cover - root ignores mode bits
            pytest.skip("root bypasses directory permissions")
        assert directory_writable(release) is False
        calls = []
        with caplog.at_level(logging.WARNING, logger="hermes_cli.terminal_node_deps"):
            first = ensure_dashboard_terminal_deps(release, install=lambda: calls.append(1))
            second = ensure_dashboard_terminal_deps(release, install=lambda: calls.append(1))
        assert first is False
        assert second is False
        assert calls == []
        warnings = [record for record in caplog.records if "Dashboard terminal disabled" in record.message]
        assert len(warnings) == 1
        assert warnings[0].exc_info is None
        assert not (release / "node_modules").exists()
        assert list(outside.iterdir()) == []
    finally:
        release.chmod(0o755)


def test_permission_denied_install_warns_once_and_does_not_retry(tmp_path, monkeypatch, caplog):
    root = tmp_path / "release"
    root.mkdir()
    monkeypatch.setattr("hermes_cli.terminal_node_deps.directory_writable", lambda _path: True)
    calls = []

    def install():
        calls.append(1)
        raise subprocess.CalledProcessError(
            1, ["npm", "ci"],
            stderr="npm error EACCES: permission denied, mkdir '/work/release/node_modules'",
        )

    with caplog.at_level(logging.WARNING, logger="hermes_cli.terminal_node_deps"):
        assert ensure_dashboard_terminal_deps(root, install=install) is False
        assert ensure_dashboard_terminal_deps(root, install=install) is False
    assert calls == [1]
    warnings = [record for record in caplog.records if "Dashboard terminal disabled" in record.message]
    assert len(warnings) == 1
    assert warnings[0].exc_info is None


def test_unrelated_install_failure_is_not_swallowed(tmp_path, monkeypatch):
    root = tmp_path / "release"
    root.mkdir()
    monkeypatch.setattr("hermes_cli.terminal_node_deps.directory_writable", lambda _path: True)

    def install():
        raise subprocess.CalledProcessError(1, ["npm", "ci"], stderr="npm error code ERESOLVE")

    with pytest.raises(subprocess.CalledProcessError):
        ensure_dashboard_terminal_deps(root, install=install)


@pytest.mark.platforms("posix")
def test_publish_copies_node_modules_into_the_release_only(tmp_path):
    prepared = tmp_path / "prepared"
    modules = prepared / "node_modules"
    modules.mkdir(parents=True)
    (modules / ".hermes-node-deps").write_text("receipt\n", encoding="utf-8")
    link = modules / "hermes-tui"
    link.symlink_to("../ui-tui")
    release = tmp_path / "out" / "hermes-agent"
    release.mkdir(parents=True)
    outside = tmp_path / "outside-cache"
    outside.mkdir()

    destination = publish_terminal_node_modules(prepared, release)

    assert destination == release / "node_modules"
    assert (destination / ".hermes-node-deps").read_text(encoding="utf-8") == "receipt\n"
    assert (destination / "hermes-tui").is_symlink()
    assert os.readlink(destination / "hermes-tui") == "../ui-tui"
    assert not (tmp_path / "node_modules").exists()
    assert list(outside.iterdir()) == []


def test_install_command_reuses_terminal_workspaces():
    command = terminal_deps_install_command(Path("/work/source"))
    assert command[0] == "scripts/build/node-deps.mjs"
    assert "--source" in command
    assert "/work/source" in command
    assert "--reuse" in command
    assert command.count("--workspace") == 2
    assert "ui-tui" in command
    assert "web" in command


def _argv_hooks(monkeypatch, installed):
    monkeypatch.delenv("HERMES_TUI_DIR", raising=False)
    monkeypatch.setattr(main_tui_launch, "_find_bundled_tui", lambda: None)
    monkeypatch.setattr(main_tui_launch, "_tui_need_rebuild", lambda _root: True)
    monkeypatch.setattr(
        "hermes_cli.source_build.prepare_launch_dependencies",
        lambda *args, **kwargs: installed.append("install"),
    )
    monkeypatch.setattr("hermes_cli.source_build.source_build_env", lambda: {"PATH": "/usr/bin"})
    monkeypatch.setattr("hermes_cli.source_build.build_source_tui", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_tui_launch.shutil, "which", lambda name, path=None: "/usr/bin/node")


def test_launch_with_deps_present_does_not_install(tmp_path, monkeypatch):
    root = tmp_path / "release"
    tui = root / "ui-tui"
    tui.mkdir(parents=True)
    _receipt(root)
    installed = []
    _argv_hooks(monkeypatch, installed)

    argv, cwd = main_tui_launch._make_tui_argv(tui, tui_dev=False)

    assert installed == []
    assert cwd == tui
    assert argv[-1] == str(tui / "dist/entry.js")


def test_launch_on_unwritable_release_raises_once_without_install(tmp_path, monkeypatch, caplog):
    root = tmp_path / "release"
    tui = root / "ui-tui"
    tui.mkdir(parents=True)
    installed = []
    _argv_hooks(monkeypatch, installed)
    monkeypatch.setattr("hermes_cli.terminal_node_deps.directory_writable", lambda _path: False)

    with caplog.at_level(logging.WARNING, logger="hermes_cli.terminal_node_deps"):
        with pytest.raises(TerminalDepsUnavailable) as first:
            main_tui_launch._make_tui_argv(tui, tui_dev=False)
        with pytest.raises(TerminalDepsUnavailable):
            main_tui_launch._make_tui_argv(tui, tui_dev=False)

    assert "not writable" in first.value.user_message
    assert installed == []
    warnings = [record for record in caplog.records if "Dashboard terminal disabled" in record.message]
    assert len(warnings) == 1
    assert all(record.exc_info is None for record in warnings)

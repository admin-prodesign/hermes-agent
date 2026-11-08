"""Runtime drift: release resolution, exit codes, and systemd unit rendering."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.deploy.nemo.autodeploy_units import RUNTIME_DRIFT, RUNTIME_DRIFT_TIMER, UnitOptions, render
from scripts.deploy.nemo.runtime_drift import (
    EXIT_CHECK_FAILED,
    EXIT_DRIFT,
    EXIT_OK,
    GatewayRuntime,
    release_root_from_interpreter,
    run_check,
)


def _releases() -> Path:
    return Path("/home/USER/.hermes/releases")


@pytest.mark.parametrize(
    ("exe", "pythonpath"),
    [
        (_releases() / "hermes-agent-deadbeef01-auto" / ".venv" / "bin" / "python", None),
        (_releases() / "hermes-agent-deadbeef01-auto" / ".venv" / "bin" / "python3.14", None),
        (_releases() / "hermes-agent-deadbeef01-auto" / ".python" / "bin" / "python3.14", None),
        (_releases() / "hermes-agent-deadbeef01-auto" / ".hermes" / "bin" / "hermes", None),
        (
            _releases() / "hermes-agent-deadbeef01-auto" / ".venv" / "bin" / "python",
            str(_releases() / "hermes-agent-deadbeef01-auto"),
        ),
        (_releases() / "current" / ".venv" / "bin" / "python", None),
    ],
)
def test_release_root_from_interpreter_layouts(exe: Path, pythonpath: str | None) -> None:
    root = release_root_from_interpreter(exe, pythonpath=pythonpath, releases=_releases())
    parts = exe.parts
    name = parts[parts.index("releases") + 1]
    assert root == _releases() / name


def test_release_root_rejects_paths_outside_releases_tree() -> None:
    exe = Path("/opt/hermes-agent/.venv/bin/python3.12")
    assert release_root_from_interpreter(exe, releases=_releases()) is None


def test_release_root_wrong_releases_directory() -> None:
    exe = _releases() / "pkg" / ".venv" / "bin" / "python"
    other = Path("/home/USER/other/releases")
    assert release_root_from_interpreter(exe, releases=other) is None


def test_run_check_unresolvable_release_returns_check_failed(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    releases = home / "releases"
    mirror = tmp_path / "mirror.git"
    mirror.mkdir()
    def fake_run(argv: list[str], _timeout: float):
        import subprocess

        if "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 0, b"c" * 40, b"")
        if "fetch" in argv:
            return subprocess.CompletedProcess(argv, 0, b"", b"")
        return subprocess.CompletedProcess(argv, 1, b"", b"")

    with patch(
        "scripts.deploy.nemo.runtime_drift.unit_runtime",
        return_value=GatewayRuntime(
            unit="hermes-gateway.service",
            pid=99,
            exe="/opt/legacy/.venv/bin/python3.11",
            root=None,
            env_sha=None,
            file_sha=None,
        ),
    ):
        code = run_check(
            home=home,
            releases=releases,
            mirror=mirror,
            remote="origin",
            units=["hermes-gateway.service"],
            repository_label="example main",
            verbose=False,
            no_notify=True,
            run=fake_run,
        )
    assert code == EXIT_CHECK_FAILED


def test_run_check_drift_returns_drift_exit(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    releases = home / "releases"
    build = releases / "hermes-agent-abc1234567-auto"
    build.mkdir(parents=True)
    (build / ".hermes-runtime-sha").write_text("oldsha" + "0" * 32, encoding="utf-8")
    mirror = tmp_path / "mirror.git"
    mirror.mkdir()
    main = "a" * 40

    def fake_run(argv: list[str], _timeout: float):
        import subprocess

        if "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 0, main.encode(), b"")
        if "fetch" in argv:
            return subprocess.CompletedProcess(argv, 0, b"", b"")
        if "archive" in argv:
            return subprocess.CompletedProcess(argv, 0, b"", b"")
        return subprocess.CompletedProcess(argv, 1, b"", b"fail")

    with patch(
        "scripts.deploy.nemo.runtime_drift.unit_runtime",
        return_value=GatewayRuntime(
            unit="hermes-gateway.service",
            pid=1,
            exe=str(build / ".venv" / "bin" / "python"),
            root=build,
            env_sha="oldsha" + "0" * 32,
            file_sha="oldsha" + "0" * 32,
        ),
    ), patch("scripts.deploy.nemo.runtime_drift.compare_tree", return_value={
        "files_expected": 0, "changed": [], "missing": [], "extra": [],
    }), patch("scripts.deploy.nemo.runtime_drift.writes_after_build", return_value={
        "build_time": None, "source_writes": [], "venv_writes": 0, "venv_write_sample": [],
    }):
        code = run_check(
            home=home,
            releases=releases,
            mirror=mirror,
            remote="origin",
            units=["hermes-gateway.service"],
            repository_label="example main",
            verbose=False,
            no_notify=True,
            run=fake_run,
        )
    assert code == EXIT_DRIFT


def test_run_check_clean_returns_ok(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    releases = home / "releases"
    build = releases / "hermes-agent-abc1234567-auto"
    build.mkdir(parents=True)
    main = "b" * 40
    (build / ".hermes-runtime-sha").write_text(main, encoding="utf-8")
    mirror = tmp_path / "mirror.git"
    mirror.mkdir()

    def fake_run(argv: list[str], _timeout: float):
        import subprocess

        if "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 0, main.encode(), b"")
        if "fetch" in argv:
            return subprocess.CompletedProcess(argv, 0, b"", b"")
        return subprocess.CompletedProcess(argv, 1, b"", b"")

    with patch(
        "scripts.deploy.nemo.runtime_drift.unit_runtime",
        return_value=GatewayRuntime(
            unit="hermes-gateway.service",
            pid=1,
            exe=str(build / ".python" / "bin" / "python3.14"),
            root=build,
            env_sha=main,
            file_sha=main,
        ),
    ), patch("scripts.deploy.nemo.runtime_drift.compare_tree", return_value={
        "files_expected": 1, "changed": [], "missing": [], "extra": [],
    }), patch("scripts.deploy.nemo.runtime_drift.writes_after_build", return_value={
        "build_time": None, "source_writes": [], "venv_writes": 0, "venv_write_sample": [],
    }):
        code = run_check(
            home=home,
            releases=releases,
            mirror=mirror,
            remote="origin",
            units=["hermes-gateway.service"],
            repository_label="example main",
            verbose=False,
            no_notify=True,
            run=fake_run,
        )
    assert code == EXIT_OK


def test_autodeploy_render_includes_runtime_drift_units(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    mirror = tmp_path / "mirror.git"
    units = render(UnitOptions(home=home, releases=home / "releases", mirror=mirror))
    service = units[RUNTIME_DRIFT]
    timer = units[RUNTIME_DRIFT_TIMER]
    current = str(home / "releases" / "current")
    assert f"{current}/.venv/bin/python -m scripts.deploy.nemo.runtime_drift" in service
    assert f"--mirror {mirror}" in service
    assert "SuccessExitStatus=1" in service
    assert "Nice=10" in service
    assert "OnCalendar=*-*-* 07:50:00 Asia/Taipei" in timer
    assert "RandomizedDelaySec=60" in timer
    assert f"Unit={RUNTIME_DRIFT}" in timer

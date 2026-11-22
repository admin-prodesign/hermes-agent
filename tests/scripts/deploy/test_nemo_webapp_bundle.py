"""A nemo release that serves the desktop webapp must contain its bundle.

``build.sh`` compiles ``apps/desktop/dist-webapp`` and ``cutover.sh`` calls
``require-webapp`` before it swaps. These tests are the gate: webapp.enabled
and a missing ``index.html`` fail; the webapp being off does not.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from hermes_cli.webapp import webapp_dist_dir
from scripts.deploy.nemo.cli import main
from scripts.deploy.nemo.drift import _is_build_output
from scripts.deploy.nemo.webapp_bundle import WEBAPP_BUNDLE_INDEX, webapp_bundle_problem

ROOT = Path(__file__).resolve().parents[3]
CUTOVER = ROOT / "scripts" / "deploy" / "nemo" / "cutover.sh"
_ON = "webapp:\n  enabled: true\n"
_OFF = "webapp:\n  enabled: false\n"


def _home(tmp_path: Path, text: str | None) -> Path:
    home = tmp_path / "hermes"
    home.mkdir()
    if text is not None:
        (home / "config.yaml").write_text(text, encoding="utf-8")
    return home


def _profile(home: Path, name: str, text: str) -> None:
    path = home / "profiles" / name
    path.mkdir(parents=True)
    (path / "config.yaml").write_text(text, encoding="utf-8")


def _release(tmp_path: Path, *, bundle: bool) -> Path:
    release = tmp_path / "release"
    if bundle:
        index = release / WEBAPP_BUNDLE_INDEX
        index.parent.mkdir(parents=True)
        index.write_text("<!doctype html>\n", encoding="utf-8")
    else:
        release.mkdir()
    return release


def test_missing_bundle_fails_when_the_webapp_is_enabled(tmp_path: Path) -> None:
    home = _home(tmp_path, _ON)
    problem = webapp_bundle_problem(_release(tmp_path, bundle=False), home)
    assert problem is not None
    assert "webapp.enabled is set (default)" in problem
    assert str(WEBAPP_BUNDLE_INDEX) in problem


def test_built_bundle_passes_when_the_webapp_is_enabled(tmp_path: Path) -> None:
    home = _home(tmp_path, _ON)
    assert webapp_bundle_problem(_release(tmp_path, bundle=True), home) is None


def test_missing_bundle_passes_when_the_webapp_is_off(tmp_path: Path) -> None:
    home = _home(tmp_path, _OFF)
    assert webapp_bundle_problem(_release(tmp_path, bundle=False), home) is None


def test_missing_bundle_passes_when_the_webapp_is_unset(tmp_path: Path) -> None:
    home = _home(tmp_path, None)
    assert webapp_bundle_problem(_release(tmp_path, bundle=False), home) is None


def test_a_non_boolean_enabled_value_does_not_require_the_bundle(
    tmp_path: Path,
) -> None:
    """The gateway keeps the webapp off unless ``enabled`` is boolean true."""
    home = _home(tmp_path, "webapp:\n  enabled: 'true'\n")
    assert webapp_bundle_problem(_release(tmp_path, bundle=False), home) is None


def test_a_directory_at_index_html_is_not_a_bundle(tmp_path: Path) -> None:
    home = _home(tmp_path, _ON)
    release = _release(tmp_path, bundle=False)
    (release / WEBAPP_BUNDLE_INDEX).mkdir(parents=True)
    problem = webapp_bundle_problem(release, home)
    assert problem is not None and str(WEBAPP_BUNDLE_INDEX) in problem


def test_a_named_profile_with_the_webapp_on_requires_the_bundle(tmp_path: Path) -> None:
    home = _home(tmp_path, _OFF)
    _profile(home, "pdone", _ON)
    problem = webapp_bundle_problem(_release(tmp_path, bundle=False), home)
    assert problem is not None
    assert "webapp.enabled is set (pdone)" in problem


def test_every_enabled_profile_is_named(tmp_path: Path) -> None:
    home = _home(tmp_path, _ON)
    _profile(home, "pdone", _ON)
    problem = webapp_bundle_problem(_release(tmp_path, bundle=False), home)
    assert problem is not None
    assert "webapp.enabled is set (default, pdone)" in problem


def test_staging_and_invalid_profile_dirs_are_not_webapp_homes(tmp_path: Path) -> None:
    home = _home(tmp_path, _OFF)
    _profile(home, ".staging-pdone", _ON)
    _profile(home, "NotAProfile", _ON)
    assert webapp_bundle_problem(_release(tmp_path, bundle=False), home) is None


def test_gate_checks_the_bundle_the_gateway_serves(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("HERMES_WEBAPP_DIST", raising=False)
    assert webapp_dist_dir(tmp_path) == tmp_path / WEBAPP_BUNDLE_INDEX.parent


def test_webapp_bundle_files_are_not_runtime_drift() -> None:
    assert _is_build_output("apps/desktop/dist-webapp/index.html")
    assert _is_build_output("apps/desktop/dist-webapp/assets/app.js")
    assert not _is_build_output("apps/desktop/scripts/build-webapp.mjs")


def test_cli_require_webapp_exits_on_a_missing_bundle(tmp_path: Path, capsys) -> None:
    home = _home(tmp_path, _ON)
    release = _release(tmp_path, bundle=False)
    code = main(
        [
            "require-webapp",
            "--hermes-home",
            str(home),
            "--release",
            str(release),
        ]
    )
    assert code == 1
    assert str(WEBAPP_BUNDLE_INDEX) in capsys.readouterr().err


def test_cli_require_webapp_passes_when_the_bundle_is_present(
    tmp_path: Path,
    capsys,
) -> None:
    home = _home(tmp_path, _ON)
    release = _release(tmp_path, bundle=True)
    code = main(
        [
            "require-webapp",
            "--hermes-home",
            str(home),
            "--release",
            str(release),
        ]
    )
    assert code == 0
    assert capsys.readouterr().err == ""


def _bash() -> str:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required")
    return bash


def _fake_release(home: Path, *, bundle: bool) -> Path:
    release = home / "releases" / "build-a"
    python = release / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    python.chmod(stat.S_IRWXU)
    (release / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    if bundle:
        index = release / WEBAPP_BUNDLE_INDEX
        index.parent.mkdir(parents=True)
        index.write_text("<!doctype html>\n", encoding="utf-8")
    return release


def _run_cutover(home: Path, unit_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env["NEMO_PYTHON"] = sys.executable
    return subprocess.run(
        [
            _bash(),
            str(CUTOVER),
            "--hermes-home",
            str(home),
            "--build",
            "build-a",
            "--unit-dir",
            str(unit_dir),
            "--skip-preflight",
            "--skip-selftest",
            "--skip-gate",
            "--skip-restart",
            "--skip-health",
            "--skip-postcheck",
        ],
        check=False,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


@pytest.mark.platforms("linux", "macos")
@pytest.mark.parametrize("enabled", [True, False])
def test_cutover_refuses_a_missing_bundle_only_when_the_webapp_is_on(
    tmp_path: Path,
    enabled: bool,
) -> None:
    home = _home(tmp_path, _ON if enabled else _OFF)
    _fake_release(home, bundle=False)
    proc = _run_cutover(home, tmp_path / "units")
    assert proc.returncode != 0
    assert not (home / "releases" / "current").exists()
    if enabled:
        assert "webapp.enabled is set" in proc.stderr
        assert str(WEBAPP_BUNDLE_INDEX) in proc.stderr
        assert "no releases/current" not in proc.stderr
    else:
        assert "webapp.enabled is set" not in proc.stderr
        assert "no releases/current" in proc.stderr


@pytest.mark.platforms("linux", "macos")
def test_cutover_continues_when_the_enabled_webapp_bundle_is_present(
    tmp_path: Path,
) -> None:
    home = _home(tmp_path, _ON)
    _fake_release(home, bundle=True)
    proc = _run_cutover(home, tmp_path / "units")
    assert proc.returncode != 0
    assert "webapp.enabled is set" not in proc.stderr
    assert "no releases/current" in proc.stderr
    assert not (home / "releases" / "current").exists()

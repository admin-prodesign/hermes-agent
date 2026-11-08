"""``cutover.sh`` runs the PD One safe-ops selftest from the new release before it swaps anything.

The release here is a temp tree whose ``tools.pd_one_ops.selftest`` records its argv and exits
with a chosen code, so the test pins the gate wiring: the release interpreter, the release as
the working directory, the live home and profile, and no swap when the selftest fails.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.deploy.nemo.manifest import write_manifest

ROOT = Path(__file__).resolve().parents[3]
NEMO = ROOT / "scripts" / "deploy" / "nemo"

_SELFTEST = """\
import json, os, sys
from pathlib import Path
Path(os.environ["SELFTEST_RECORD"]).write_text(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}))
raise SystemExit(int(os.environ["SELFTEST_EXIT"]))
"""


def _release(releases: Path, build: str) -> Path:
    release = releases / build
    package = release / "tools" / "pd_one_ops"
    package.mkdir(parents=True)
    (release / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "selftest.py").write_text(_SELFTEST, encoding="utf-8")
    (release / ".venv" / "bin").mkdir(parents=True)
    (release / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    os.symlink(sys.executable, release / ".venv" / "bin" / "python")
    return release


@pytest.fixture
def live(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "hermes"
    releases = home / "releases"
    _release(releases, "old")
    os.symlink("old", releases / "current")
    write_manifest(home / "upgrade-audits" / "old" / "manifest.json", {"build": "old", "sha": "a" * 40})
    new = _release(releases, "new")
    write_manifest(home / "upgrade-audits" / "new" / "manifest.json", {"build": "new", "sha": "b" * 40, "release": str(new)})
    return home, releases


def _cutover(home: Path, record: Path, code: int) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "NEMO_PYTHON": sys.executable, "SELFTEST_RECORD": str(record), "SELFTEST_EXIT": str(code)}
    argv = ["bash", str(NEMO / "cutover.sh"), "--hermes-home", str(home), "--build", "new", "--sha", "b" * 40,
            "--unit-dir", str(home / "units"), "--skip-preflight", "--skip-gate", "--skip-restart",
            "--skip-health", "--skip-postcheck", "--selftest-allow-missing", "freecadcmd"]
    return subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120, check=False)


@pytest.mark.platforms("linux", "macos")
def test_failed_selftest_leaves_the_live_release(live, tmp_path):
    home, releases = live
    record = tmp_path / "record.json"
    proc = _cutover(home, record, 1)
    assert proc.returncode != 0 and "selftest failed" in proc.stderr
    assert os.readlink(releases / "current") == "old"
    seen = json.loads(record.read_text())
    assert seen["cwd"] == str(releases / "new")
    assert seen["argv"] == ["--hermes-home", str(home), "--profile", "pdone", "--allow-missing", "freecadcmd"]


@pytest.mark.platforms("linux", "macos")
def test_passing_selftest_lets_the_swap_run(live, tmp_path):
    home, releases = live
    proc = _cutover(home, tmp_path / "record.json", 0)
    assert proc.returncode == 0, proc.stderr
    assert os.readlink(releases / "current") == "new"

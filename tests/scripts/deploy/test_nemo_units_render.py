"""Cutover renders systemd units and drop-ins against the release and moves every release link.

The 2026-10-19 shape: base units run ``<release>/.hermes/bin/hermes`` of a release that
``current`` never pointed at, drop-ins pin ``ExecStart``, ``PATH``, ``VIRTUAL_ENV``,
``PYTHONPATH`` and ``HERMES_RUNTIME_SHA``, and a ``build.sh`` release has no ``.hermes/bin``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from scripts.deploy.nemo.cutover_steps import UnitProblems, apply_cutover
from scripts.deploy.nemo.drift import unit_drift
from scripts.deploy.nemo.rollback import apply_rollback

OLD_SHA = "a" * 40
NEW_SHA = "b" * 40


def _build_sh_release(releases: Path, name: str) -> Path:
    release = releases / name
    bin_dir = release / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    os.symlink(sys.executable, bin_dir / "python")
    hermes = bin_dir / "hermes"
    hermes.write_text("#!/bin/sh\n", encoding="utf-8")
    hermes.chmod(0o755)
    (release / "node_modules" / ".bin").mkdir(parents=True)
    return release


def _hand_release(releases: Path, name: str) -> Path:
    release = _build_sh_release(releases, name)
    wrapper = release / ".hermes" / "bin"
    wrapper.mkdir(parents=True)
    (wrapper / "hermes").write_text("#!/bin/sh\n", encoding="utf-8")
    (wrapper / "hermes").chmod(0o755)
    return release


def _layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    """``current`` -> ``old``, but the units run the hand-built ``hand``; ``new`` is from build.sh."""
    home = tmp_path / "hermes"
    releases = home / "releases"
    _hand_release(releases, "old")
    _hand_release(releases, "hand")
    _build_sh_release(releases, "new")
    os.symlink("old", releases / "current")
    (releases / "runtime").mkdir()
    os.symlink("../hand", releases / "runtime" / "current")
    (releases / ".running").write_text("hand\n", encoding="utf-8")
    unit_dir = tmp_path / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True)
    hand = releases / "hand"
    (unit_dir / "hermes-gateway.service").write_text(
        "[Service]\n"
        f"ExecStart={hand}/.hermes/bin/hermes gateway run\n"
        f"ExecStop={hand}/.hermes/bin/hermes gateway stop\n"
        f'Environment="PATH={hand}/.hermes/bin:{hand}/node_modules/.bin:/usr/bin"\n',
        encoding="utf-8",
    )
    drop_in = unit_dir / "hermes-gateway.service.d"
    drop_in.mkdir()
    (drop_in / "91-sqlite.conf").write_text(
        "[Service]\nExecStart=\n"
        f"ExecStart={hand}/.venv/bin/python -m hermes_cli.main gateway run\n"
        f"Environment=PATH={hand}/.venv/bin:/usr/bin VIRTUAL_ENV={hand}/.venv\n"
        f"Environment=PYTHONPATH={hand} HERMES_RUNTIME_SHA={OLD_SHA[:12]}\n",
        encoding="utf-8",
    )
    (unit_dir / "hermes-review.service").write_text(
        f"[Service]\nExecStart=/usr/bin/true\nEnvironment=HERMES_RUNTIME_SHA={OLD_SHA}\n",
        encoding="utf-8",
    )
    (unit_dir / "unrelated.service").write_text("[Service]\nExecStart=/usr/bin/true\n", encoding="utf-8")
    return home, releases, unit_dir


def _cut(home: Path, releases: Path, unit_dir: Path) -> dict:
    return apply_cutover(releases=releases, build="new", unit_dirs=[unit_dir], configs=[],
                         audit=home / "upgrade-audits" / "new", sha=NEW_SHA, running=True)


@pytest.mark.platforms("linux", "macos")
def test_cutover_renders_base_units_and_drop_ins_onto_the_new_release(tmp_path: Path) -> None:
    home, releases, unit_dir = _layout(tmp_path)
    new = (releases / "new").resolve()
    result = _cut(home, releases, unit_dir)

    base = (unit_dir / "hermes-gateway.service").read_text(encoding="utf-8")
    assert f"ExecStart={new}/.venv/bin/hermes gateway run" in base
    assert f"ExecStop={new}/.venv/bin/hermes gateway stop" in base
    assert f"PATH={new}/.venv/bin:{new}/node_modules/.bin:/usr/bin" in base
    drop_in = (unit_dir / "hermes-gateway.service.d" / "91-sqlite.conf").read_text(encoding="utf-8")
    assert f"ExecStart={new}/.venv/bin/python -m hermes_cli.main gateway run" in drop_in
    assert f"VIRTUAL_ENV={new}/.venv" in drop_in
    assert f"PYTHONPATH={new} HERMES_RUNTIME_SHA={NEW_SHA[:12]}" in drop_in
    assert "/hand" not in base + drop_in
    review = (unit_dir / "hermes-review.service").read_text(encoding="utf-8")
    assert f"HERMES_RUNTIME_SHA={NEW_SHA}" in review

    restarts = {(item["unit"], item["restart"]) for item in result["units"]}
    assert ("hermes-gateway.service", "restart") in restarts
    assert ("hermes-review.service", "try-restart") in restarts
    assert not any(item["unit"] == "unrelated.service" for item in result["units"])

    assert os.readlink(releases / "current") == "new"
    assert os.readlink(releases / "previous") == "old"
    assert os.readlink(releases / "runtime" / "current") == "../new"
    assert (releases / ".running").read_text(encoding="utf-8").strip() == "new"


@pytest.mark.platforms("linux", "macos")
def test_rollback_restores_units_drop_ins_and_every_link(tmp_path: Path) -> None:
    home, releases, unit_dir = _layout(tmp_path)
    files = sorted(path for path in unit_dir.rglob("*") if path.is_file())
    before = {path: path.read_text(encoding="utf-8") for path in files}
    result = _cut(home, releases, unit_dir)

    apply_rollback(result)

    assert {path: path.read_text(encoding="utf-8") for path in files} == before
    assert os.readlink(releases / "current") == "old"
    assert not (releases / "previous").is_symlink()
    assert os.readlink(releases / "runtime" / "current") == "../hand"
    assert (releases / ".running").read_text(encoding="utf-8") == "hand\n"


@pytest.mark.platforms("linux", "macos")
def test_cutover_refuses_a_unit_whose_rendered_command_the_release_lacks(tmp_path: Path) -> None:
    home, releases, unit_dir = _layout(tmp_path)
    (releases / "new" / ".venv" / "bin" / "hermes").unlink()
    before = {path: path.read_text(encoding="utf-8") for path in unit_dir.rglob("*") if path.is_file()}

    with pytest.raises(UnitProblems, match="hermes does not exist"):
        _cut(home, releases, unit_dir)

    assert {path: path.read_text(encoding="utf-8") for path in before} == before
    assert os.readlink(releases / "current") == "old"
    assert not (releases / "previous").exists()
    assert (releases / ".running").read_text(encoding="utf-8") == "hand\n"


@pytest.mark.platforms("linux", "macos")
def test_drift_reports_a_drop_in_left_on_another_release_or_sha(tmp_path: Path) -> None:
    home, releases, unit_dir = _layout(tmp_path)
    live = {"old": OLD_SHA}

    found = unit_drift([unit_dir], releases, live)

    assert any("91-sqlite.conf" in item and "hand" in item for item in found)
    assert any("hermes-gateway.service ->" in item for item in found)
    assert not any("unrelated.service" in item for item in found)

    _cut(home, releases, unit_dir)
    assert unit_drift([unit_dir], releases, {"new": NEW_SHA}) == []
    stale_sha = unit_drift([unit_dir], releases, {"new": "c" * 40})
    assert any("91-sqlite.conf" in item and "HERMES_RUNTIME_SHA" in item for item in stale_sha)

"""Previous-freeze ``-c`` cleaning for the nemo deploy build.

The previous release's freeze holds unrelated packages steady. It must not
keep exact versions this SHA already re-pins (overrides, pyproject ``==``,
or a different ``uv.lock`` version). That class of clash made
``hermes-agent[nemo]`` unsatisfiable on the 903c9b2 hand cutover.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.deploy.nemo.freeze_diff import (
    constraint_drops,
    constraint_text,
    exact_pin_names,
    lock_diff_names,
    override_names,
    override_text,
)

ROOT = Path(__file__).resolve().parents[3]

PYPROJECT = """
[project]
name = "hermes-agent"
dependencies = [
  "certifi==2026.10.19",
  "nemo-relay>=0.10,<0.11",
  "Pillow==13.0.0",
]

[project.optional-dependencies]
nemo = [
  "hermes-agent[mcp]",
  "requests==2.33.0",
]
mcp = [
  "mcp==2.3.0",
]
web = [
  "fastapi==0.133.1",
]
"""

OLD_FREEZE = """\
certifi==2026.5.20
pillow==12.3.0
mcp==2.0.0
fastapi==0.100.0
requests==2.32.0
nemo-relay==0.10.0
mcp-types==2.0.0
anyio==4.0.0
idna==3.10
unrelated==1.0.0
-e /opt/hermes
"""

LOCK = """
[[package]]
name = "mcp-types"
version = "2.3.0"

[[package]]
name = "anyio"
version = "4.0.0"

[[package]]
name = "nemo-relay"
version = "0.10.1"

[[package]]
name = "unrelated"
version = "1.0.0"

[[package]]
name = "pillow"
version = "13.0.0"
"""

OVERRIDES = "Pillow==13.0.0\n"


def test_override_names_drop_the_old_freeze_pin(tmp_path: Path) -> None:
    """PR #68: leftover pillow==12.3.0 in -c is a second hard pin."""
    lock = tmp_path / "uv.lock"
    lock.write_text(
        "[manifest]\n"
        "overrides = [\n"
        '    { name = "pillow", specifier = "==13.0.0" },\n'
        "]\n",
        encoding="utf-8",
    )
    drop = override_names(override_text(lock))
    constrained = constraint_text(OLD_FREEZE, drop=drop)
    assert "pillow==12.3.0" not in constrained
    assert "certifi==2026.5.20" in constrained
    assert "pillow==12.3.0" in constraint_text(OLD_FREEZE)


def test_exact_pyproject_pins_leave_the_constraint_file() -> None:
    """Pass 1 of the 903c9b2 hand bootstrap: drop exact == pins, keep ranges."""
    pins = exact_pin_names(PYPROJECT, extra="nemo")
    assert pins == {"certifi", "pillow", "mcp", "requests"}
    constrained = constraint_text(OLD_FREEZE, drop=pins)
    assert "certifi==2026.5.20" not in constrained
    assert "mcp==2.0.0" not in constrained
    assert "requests==2.32.0" not in constrained
    assert "pillow==12.3.0" not in constrained
    # web extra is not part of .[nemo]; range pins are not exact.
    assert "fastapi==0.100.0" in constrained
    assert "nemo-relay==0.10.0" in constrained
    assert "mcp-types==2.0.0" in constrained


def test_lock_version_diffs_leave_the_constraint_file() -> None:
    """Pass 2: drop freeze pins whose version is not in this SHA's uv.lock."""
    drop = lock_diff_names(OLD_FREEZE, LOCK)
    assert drop == {"mcp-types", "nemo-relay", "pillow"}
    constrained = constraint_text(OLD_FREEZE, drop=drop)
    assert "mcp-types==2.0.0" not in constrained
    assert "nemo-relay==0.10.0" not in constrained
    assert "anyio==4.0.0" in constrained
    # Absent from the lock: keep holding the previous freeze (not a new conflict).
    assert "idna==3.10" in constrained
    assert "unrelated==1.0.0" in constrained


def test_previous_freeze_drops_overrides_exact_pins_and_lock_diffs() -> None:
    """Both hand-bootstrap passes together still hold unrelated packages."""
    drop = constraint_drops(
        OLD_FREEZE,
        overrides_text=OVERRIDES,
        pyproject_text=PYPROJECT,
        extra="nemo",
        lock_text=LOCK,
    )
    constrained = constraint_text(OLD_FREEZE, drop=drop)
    assert "-e" not in constrained
    assert "pillow==12.3.0" not in constrained
    assert "certifi==2026.5.20" not in constrained
    assert "mcp==2.0.0" not in constrained
    assert "requests==2.32.0" not in constrained
    assert "mcp-types==2.0.0" not in constrained
    assert "nemo-relay==0.10.0" not in constrained
    assert "fastapi==0.100.0" in constrained
    assert "anyio==4.0.0" in constrained
    assert "idna==3.10" in constrained
    assert "unrelated==1.0.0" in constrained


def test_freeze_constraint_cli_applies_all_drop_rules(tmp_path: Path) -> None:
    freeze = tmp_path / "old-freeze.txt"
    freeze.write_text(OLD_FREEZE, encoding="utf-8")
    overrides = tmp_path / "overrides.txt"
    overrides.write_text(OVERRIDES, encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(PYPROJECT, encoding="utf-8")
    lock = tmp_path / "uv.lock"
    lock.write_text(LOCK, encoding="utf-8")
    output = tmp_path / "constraints.txt"
    proc = subprocess.run(
        [
            sys.executable, "-m", "scripts.deploy.nemo.cli", "freeze-constraint",
            "--input", str(freeze), "--output", str(output),
            "--drop-overrides", str(overrides),
            "--pyproject", str(pyproject),
            "--lock", str(lock),
            "--extra", "nemo",
        ],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    constrained = output.read_text(encoding="utf-8")
    assert "pillow==12.3.0" not in constrained
    assert "certifi==2026.5.20" not in constrained
    assert "mcp-types==2.0.0" not in constrained
    assert "unrelated==1.0.0" in constrained

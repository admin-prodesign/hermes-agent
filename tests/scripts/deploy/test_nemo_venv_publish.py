"""Staging-to-release venv relocate and ``hermes-agent-<sha10>-<suffix>`` naming.

Nothing here writes to the real Hermes home.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.deploy.nemo.autodeploy import Config, build_name, build_argv
from scripts.deploy.nemo.manifest import (
    AUTO_RELEASE_SUFFIX, release_dir_name, sha_from_release_name,
)
from scripts.deploy.nemo.venv_publish import (
    check_release_interpreter, publish_venv, relocate_venv,
)

ROOT = Path(__file__).resolve().parents[3]
SHA = "a10be5b8b195" + "c" * 28


def _staging_venv(root: Path) -> Path:
    """A venv whose interpreter link is an absolute path into ``.python`` (the uv layout)."""
    staging = root / "releases" / ".staging-a10be5b8b195.xxxx"
    pybin = staging / ".python" / "bin"
    pybin.mkdir(parents=True)
    os.symlink(sys.executable, pybin / "python3")
    subprocess.run(
        [str(pybin / "python3"), "-m", "venv", "--without-pip", str(staging / ".venv")],
        check=True, timeout=30,
    )
    script = staging / ".venv" / "bin" / "sample-tool"
    script.write_text(f"#!{staging / '.venv' / 'bin' / 'python'}\nimport sys\n", encoding="utf-8")
    script.chmod(0o755)
    site = staging / ".venv" / "lib" / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    (site / "_nemo.pth").write_text(str(staging) + "\n", encoding="utf-8")
    return staging


def test_release_dir_name_matches_hand_built_convention() -> None:
    assert release_dir_name(SHA) == "hermes-agent-a10be5b8b1-auto"
    assert release_dir_name(SHA, "manual") == "hermes-agent-a10be5b8b1-manual"
    assert release_dir_name(SHA.upper(), AUTO_RELEASE_SUFFIX) == "hermes-agent-a10be5b8b1-auto"
    assert build_name(SHA) == "hermes-agent-a10be5b8b1-auto"
    assert sha_from_release_name(build_name(SHA)) == "a10be5b8b1"


def test_release_dir_name_keeps_short_sha_and_rejects_junk() -> None:
    assert release_dir_name("abc1234") == "abc1234"
    with pytest.raises(ValueError, match="suffix"):
        release_dir_name(SHA, "../x")
    with pytest.raises(ValueError, match="hex"):
        release_dir_name("not-a-sha")


def test_sha_from_release_name_still_reads_bare_sha12_and_hand_built() -> None:
    assert sha_from_release_name("a10be5b8b195") == "a10be5b8b195"
    assert sha_from_release_name("hermes-agent-a10be5b8b1-manual") == "a10be5b8b1"
    assert sha_from_release_name("hermes-agent-deadbeef01") == "deadbeef01"


def test_build_argv_passes_the_convention_name(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    cfg = Config(home=home, mirror=tmp_path / "mirror.git", releases=home / "releases")
    name = build_name(SHA)
    argv = build_argv(cfg, SHA, name)
    assert argv[argv.index("--build") + 1] == "hermes-agent-a10be5b8b1-auto"
    assert argv[argv.index("--sha") + 1] == SHA
    assert argv[argv.index("--extra") + 1] == "nemo,mcp"


def test_release_name_cli_prints_the_convention() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.deploy.nemo.cli", "release-name", "--sha", SHA],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=20, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "hermes-agent-a10be5b8b1-auto"


@pytest.mark.platforms("linux", "macos")
def test_venv_works_after_the_staging_dir_is_moved(tmp_path: Path) -> None:
    staging = _staging_venv(tmp_path)
    python = staging / ".venv" / "bin" / "python"
    assert python.exists()
    subprocess.run([str(python), "-c", "import sys"], check=True, timeout=20)

    final = tmp_path / "releases" / build_name(SHA)
    shutil.move(staging, final)
    moved = final / ".venv" / "bin" / "python"
    assert moved.is_symlink()
    assert not moved.exists()
    with pytest.raises(RuntimeError, match="release interpreter missing"):
        check_release_interpreter(final)

    publish_venv(final, staging)
    subprocess.run([str(moved), "-c", "import sys"], check=True, timeout=20, cwd=str(final))
    cfg = (final / ".venv" / "pyvenv.cfg").read_text(encoding="utf-8-sig")
    assert str(staging) not in cfg
    assert str(final / ".python" / "bin") in cfg
    shebang = (final / ".venv" / "bin" / "sample-tool").read_text(encoding="utf-8-sig").splitlines()[0]
    assert str(final / ".venv" / "bin" / "python") in shebang
    assert str(staging) not in shebang
    assert (final / ".venv" / "lib" / "site-packages" / "_nemo.pth").read_text(encoding="utf-8-sig") == (
        str(final) + "\n"
    )
    target = os.readlink(final / ".venv" / "bin" / "python3")
    assert not os.path.isabs(target)
    assert Path(final / ".venv" / "bin" / target).resolve() == (final / ".python" / "bin" / "python3").resolve()


@pytest.mark.platforms("linux", "macos")
def test_publish_venv_cli_fails_clearly_when_the_interpreter_stays_broken(tmp_path: Path) -> None:
    staging = _staging_venv(tmp_path)
    final = tmp_path / "releases" / build_name(SHA)
    shutil.move(staging, final)
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.deploy.nemo.cli", "publish-venv",
         "--release", str(final), "--from-staging", str(tmp_path / "other-staging")],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=20, check=False,
    )
    assert proc.returncode != 0
    assert "release interpreter missing" in proc.stderr
    assert str(final / ".venv" / "bin" / "python") in proc.stderr


@pytest.mark.platforms("linux", "macos")
def test_relocate_is_a_noop_when_staging_and_release_are_the_same(tmp_path: Path) -> None:
    staging = _staging_venv(tmp_path)
    relocate_venv(staging, staging)
    check_release_interpreter(staging)

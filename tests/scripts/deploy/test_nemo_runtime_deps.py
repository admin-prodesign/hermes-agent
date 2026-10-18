"""Nemo auto-build extras and the published-venv import check.

A clean auto-build used to install only ``[nemo]``. The PD One selftest then
failed with ``No module named 'mcp'``. These tests pin the extras list and
the import probe that must fail the build before cutover.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.deploy.nemo.autodeploy import Config, build_argv
from scripts.deploy.nemo.freeze_diff import compare
from scripts.deploy.nemo.layout import DEFAULT_EXTRA, NEMO_PACKAGES
from scripts.deploy.nemo.runtime_deps import (
    DEFAULT_EXTRAS,
    RUNTIME_IMPORTS,
    RUNTIME_PACKAGES,
    check_release_imports,
    check_runtime_imports,
    extras_spec,
    import_statement,
    parse_extras,
)
from scripts.deploy.nemo.verify_mcp import compile_plan

ROOT = Path(__file__).resolve().parents[3]
SHA = "a10be5b8b195" + "c" * 28


def test_default_extras_install_nemo_and_mcp() -> None:
    assert parse_extras() == ("nemo", "mcp")
    assert extras_spec() == "nemo,mcp"
    assert DEFAULT_EXTRA == extras_spec()
    assert DEFAULT_EXTRAS == parse_extras()


def test_parse_extras_accepts_a_comma_list_and_rejects_junk() -> None:
    assert parse_extras("nemo,mcp") == ("nemo", "mcp")
    assert parse_extras(" nemo, mcp, mcp ") == ("nemo", "mcp")
    assert parse_extras("nemo") == ("nemo",)
    with pytest.raises(ValueError, match="invalid extra"):
        parse_extras("nemo;rm")
    with pytest.raises(ValueError, match="invalid extra"):
        parse_extras("../evil")
    with pytest.raises(ValueError, match="empty"):
        parse_extras(",")


def test_runtime_imports_include_the_selftest_mcp_module() -> None:
    assert "mcp" in RUNTIME_IMPORTS
    assert "httpx2" in RUNTIME_IMPORTS
    assert "yaml" in RUNTIME_IMPORTS
    assert "requests" in RUNTIME_IMPORTS
    assert import_statement().startswith("import ")
    assert "mcp" in import_statement()


def test_freeze_diff_fails_when_mcp_disappears() -> None:
    old = "requests==2.33.0\nmcp==2.0.0\nhttpx2==2.7.0\n"
    new = "requests==2.33.0\n"
    report, missing = compare(old, new)
    assert "mcp" in missing
    assert "httpx2" in missing
    assert "- mcp==2.0.0" in report
    assert set(NEMO_PACKAGES) <= set(RUNTIME_PACKAGES)
    assert "mcp" in RUNTIME_PACKAGES


def test_compile_plan_imports_mcp_before_compiling_scripts() -> None:
    script = Path("srv.py")
    plan = compile_plan("/opt/release/.venv/bin/python", [script])
    assert plan[0] == ("/opt/release/.venv/bin/python", "-c", import_statement())
    assert "mcp" in plan[0][2]
    assert plan[1] == ("/opt/release/.venv/bin/python", "-m", "py_compile", str(script))


def test_check_runtime_imports_fails_when_mcp_is_missing() -> None:
    with pytest.raises(RuntimeError, match="No module named") as caught:
        check_runtime_imports(sys.executable, modules=("nonesuch_nemo_mcp_module",))
    assert "release import check failed" in str(caught.value)
    assert "nonesuch_nemo_mcp_module" in str(caught.value)


def test_check_runtime_imports_fails_when_the_interpreter_cannot_start(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "no-such-python"
    with pytest.raises(RuntimeError, match="could not start"):
        check_runtime_imports(missing)


def test_check_release_imports_names_a_missing_interpreter(tmp_path: Path) -> None:
    release = tmp_path / "release"
    (release / ".venv" / "bin").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="release interpreter missing"):
        check_release_imports(release)


def test_check_runtime_imports_passes_on_the_test_interpreter() -> None:
    check_runtime_imports(sys.executable, cwd=ROOT)


@pytest.mark.platforms("linux", "macos")
def test_check_imports_cli_fails_clearly_when_a_module_is_missing(tmp_path: Path) -> None:
    fake = tmp_path / "python"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "sys.stderr.write(\"ModuleNotFoundError: No module named 'mcp'\\n\")\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.deploy.nemo.cli", "check-imports",
         "--python", str(fake)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=20, check=False,
    )
    assert proc.returncode != 0
    assert "No module named 'mcp'" in proc.stderr


def test_extras_spec_cli_normalizes_and_rejects() -> None:
    ok = subprocess.run(
        [sys.executable, "-m", "scripts.deploy.nemo.cli", "extras-spec",
         "--extra", "nemo, mcp"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=20, check=False,
    )
    assert ok.returncode == 0, ok.stderr
    assert ok.stdout.strip() == "nemo,mcp"
    default = subprocess.run(
        [sys.executable, "-m", "scripts.deploy.nemo.cli", "extras-spec"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=20, check=False,
    )
    assert default.returncode == 0, default.stderr
    assert default.stdout.strip() == "nemo,mcp"
    bad = subprocess.run(
        [sys.executable, "-m", "scripts.deploy.nemo.cli", "extras-spec",
         "--extra", "nemo;oops"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=20, check=False,
    )
    assert bad.returncode == 2
    assert "invalid extra" in bad.stderr


def test_build_argv_passes_the_mcp_extra(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    cfg = Config(home=home, mirror=tmp_path / "mirror.git", releases=home / "releases")
    argv = build_argv(cfg, SHA, "hermes-agent-a10be5b8b1-auto")
    assert argv[argv.index("--extra") + 1] == "nemo,mcp"


@pytest.mark.platforms("linux", "macos")
def test_build_rejects_an_unsafe_extras_list(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required")
    home = tmp_path / "hermes"
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env.setdefault("NEMO_PYTHON", sys.executable)
    proc = subprocess.run(
        [bash, str(ROOT / "scripts" / "deploy" / "nemo" / "build.sh"),
         "--hermes-home", str(home), "--sha", "abc1234", "--build", "build-a",
         "--tarball", str(tmp_path / "missing.tar"),
         "--extra", "nemo;oops"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20,
    )
    assert proc.returncode != 0
    assert "invalid extras" in proc.stderr
    assert not (home / "releases" / "build-a").exists()

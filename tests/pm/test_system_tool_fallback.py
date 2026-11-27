"""A pinned tool missing from the store is satisfied at startup by a working PATH copy."""

import importlib
import logging
from pathlib import Path

import pytest

import pm
from pm import paths, registry
from pm.lock import Lockfile
from pm.packages import BinaryPackage
from tests.pm._fixtures import make_tar, served as served  # noqa: PLC0414 -- the self-alias is load-bearing: it suppresses F811 for the pytest fixture parameter shadowing this import

pytestmark = pytest.mark.platforms("posix")


@pytest.fixture
def pinned_tool(tmp_path, monkeypatch, served):
    """A system_fallback tool installed in a real store, plus an empty user bin on PATH."""
    engine = importlib.import_module("pm.install")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("HERMES_RUNTIME_DIR", str(tmp_path / "store"))
    monkeypatch.setattr(paths, "repo_root", lambda: tmp_path / "repo")
    monkeypatch.setattr(paths, "lockfile_path", lambda: tmp_path / "lock.json")
    monkeypatch.setattr(registry, "_packages", {})
    docroot, url = served
    package = BinaryPackage()
    package.name = "fbtool"
    package.probe_version = False
    package.system_fallback = True
    package.binary_rel = {"posix": "bin/fbtool"}
    registry._packages["fbtool"] = package
    archive, digest = make_tar(docroot, "fbtool.tar.gz", {"bin/fbtool": "fixture tool"})
    lock = Lockfile(paths.lockfile_path())
    lock.set_pin("fbtool", "9.0", {"any": {"url": f"{url}/{archive}", "sha256": digest}})
    lock.save()
    engine.ensure("fbtool", explicit=True)
    bundled = pm.installed_package("fbtool").binary
    user_bin = tmp_path / "user-bin"
    user_bin.mkdir()
    monkeypatch.setenv("PATH", str(user_bin))
    return bundled, user_bin, tmp_path / "payload"


def _system_copy(user_bin: Path, *, exit_code: int = 0) -> None:
    tool = user_bin / "fbtool"
    tool.write_text(f"#!/bin/sh\necho 'fbtool version 6.1.1'\nexit {exit_code}\n")
    tool.chmod(0o755)


def _verdict(root: Path) -> str | None:
    from hermes_cli.venv_sync import check_runtime

    root.mkdir(exist_ok=True)
    return check_runtime(root)


def test_bundled_copy_present_is_in_sync(pinned_tool, caplog):
    _bundled, user_bin, root = pinned_tool
    _system_copy(user_bin)
    with caplog.at_level(logging.DEBUG, logger="pm.install"):
        assert _verdict(root) is None
    assert "using system binary" not in caplog.text


def test_missing_bundled_copy_is_satisfied_by_working_system_binary(pinned_tool, caplog):
    bundled, user_bin, root = pinned_tool
    bundled.unlink()
    _system_copy(user_bin)
    with caplog.at_level(logging.DEBUG, logger="pm.install"):
        assert _verdict(root) is None
    assert "fbtool: pinned build not installed; using system binary (fbtool version 6.1.1)" in caplog.text
    # Repair and `hermes update` still see the missing pin and provision it.
    assert pm.drift() == {"fbtool": "not installed or outdated"}


@pytest.mark.parametrize("system", ["absent", "broken"])
def test_missing_bundled_copy_without_working_system_binary_warns(pinned_tool, system):
    bundled, user_bin, root = pinned_tool
    bundled.unlink()
    if system == "broken":
        _system_copy(user_bin, exit_code=1)
    verdict = _verdict(root)
    assert verdict is not None
    assert verdict.startswith("install out of sync (fbtool: not installed or outdated)")

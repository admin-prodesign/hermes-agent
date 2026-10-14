"""PD One profile folder resolution.

The MCP server keeps HERMES_HOME on the Hermes install root. Capability
registries live under profiles/<name>. These tests use temp directories only.
"""
from pathlib import Path

import pytest

from tools.pd_one_ops import erp_work_manual_bootstrap as erp
from tools.pd_one_ops import google_docs_document_ops as docs
from tools.pd_one_ops.mattermost_policy_lookup import ROOT as policy_root
from tools.pd_one_ops.pd_one_safe_ops_part0 import ROOT as safe_root
from tools.pd_one_ops.site_config import external_path, profile_root

_PROFILE_ENV = (
    "HERMES_PROFILE_HOME",
    "PD_ONE_PROFILE_HOME",
    "HERMES_PROFILE",
    "HERMES_PROFILE_NAME",
)
_REGISTRY_NAME = "google_docs_document_ops_registry.json"
_GATE_PARTS = (
    "skills",
    "pd-one",
    "pd-one-admin",
    "scripts",
    "office_no_corruption_gate.py",
)


def _clear_profile_env(monkeypatch) -> None:
    for name in _PROFILE_ENV:
        monkeypatch.delenv(name, raising=False)


def _platform_install(monkeypatch) -> Path:
    """Temp stand-in for the default Hermes install root."""
    from hermes_constants import _get_platform_default_hermes_home

    home = _get_platform_default_hermes_home()
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    _clear_profile_env(monkeypatch)
    return home


def _use_home(monkeypatch, home: Path) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    _clear_profile_env(monkeypatch)
    return home


def _registry(root: Path) -> Path:
    return root / "capabilities" / _REGISTRY_NAME


def _write_registry(root: Path) -> Path:
    path = _registry(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    return path


def test_install_root_resolves_registry_under_profiles_pdone(monkeypatch, tmp_path):
    """HERMES_HOME at the install root reads profiles/pdone/capabilities."""
    homes = (
        _platform_install(monkeypatch),
        _use_home(monkeypatch, tmp_path / "custom-root"),
    )
    for home in homes:
        _use_home(monkeypatch, home)
        expected_root = home / "profiles" / "pdone"
        expected = _write_registry(expected_root)
        assert Path(docs.REGISTRY_PATH()) == expected
        assert expected.is_file()
        assert Path(erp.REGISTRY_PATH()) == expected
        assert Path(safe_root()) == expected_root
        assert Path(policy_root()) == expected_root
        assert Path(profile_root()) == expected_root
        gate = external_path("office_no_corruption_gate").path()
        assert gate == expected_root.joinpath(*_GATE_PARTS)


@pytest.mark.parametrize(
    "profile_home",
    ["platform", "custom"],
)
def test_profile_shaped_home_is_used_as_is(monkeypatch, tmp_path, profile_home):
    """A HERMES_HOME that is already a profile folder stays that folder."""
    if profile_home == "platform":
        profile = _platform_install(monkeypatch) / "profiles" / "pdone"
    else:
        profile = tmp_path / "custom-root" / "profiles" / "pdone"
    _use_home(monkeypatch, profile)
    expected = _write_registry(profile)
    assert Path(docs.REGISTRY_PATH()) == expected
    assert expected.is_file()
    assert Path(profile_root()) == profile


@pytest.mark.parametrize("env_name", ["HERMES_PROFILE_HOME", "PD_ONE_PROFILE_HOME"])
def test_profile_home_env_wins(monkeypatch, tmp_path, env_name):
    _platform_install(monkeypatch)
    pinned = tmp_path / "pinned-profile"
    pinned.mkdir()
    monkeypatch.setenv("HERMES_PROFILE", "worker")
    monkeypatch.setenv(env_name, str(pinned))
    expected = _write_registry(pinned)
    assert Path(docs.REGISTRY_PATH()) == expected
    assert expected.is_file()
    assert Path(profile_root()) == pinned
    assert Path(erp.REGISTRY_PATH()) == expected


def test_hermes_profile_home_wins_over_pd_one_profile_home(monkeypatch, tmp_path):
    _platform_install(monkeypatch)
    primary = tmp_path / "primary-profile"
    secondary = tmp_path / "secondary-profile"
    primary.mkdir()
    secondary.mkdir()
    monkeypatch.setenv("PD_ONE_PROFILE_HOME", str(secondary))
    monkeypatch.setenv("HERMES_PROFILE_HOME", str(primary))
    assert Path(docs.REGISTRY_PATH()) == _registry(primary)


def test_runtime_profile_name_wins_over_sticky_and_config(monkeypatch):
    home = _platform_install(monkeypatch)
    (home / "config.yaml").write_text("pd_one:\n  profile: site\n", encoding="utf-8")
    (home / "active_profile").write_text("sticky\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_PROFILE", "worker")
    assert Path(docs.REGISTRY_PATH()) == _registry(home / "profiles" / "worker")


def test_sticky_active_profile_wins_over_configured_name(monkeypatch):
    home = _platform_install(monkeypatch)
    (home / "config.yaml").write_text("pd_one:\n  profile: site\n", encoding="utf-8")
    (home / "active_profile").write_text("worker\n", encoding="utf-8")
    assert Path(docs.REGISTRY_PATH()) == _registry(home / "profiles" / "worker")


@pytest.mark.parametrize("key", ["profile", "profile_name"])
def test_configured_profile_name_selects_the_folder(monkeypatch, key):
    home = _platform_install(monkeypatch)
    (home / "config.yaml").write_text(f"pd_one:\n  {key}: site\n", encoding="utf-8")
    expected = _write_registry(home / "profiles" / "site")
    assert Path(docs.REGISTRY_PATH()) == expected
    assert expected.is_file()


@pytest.mark.parametrize("raw_name", ["../escape", "default", ""])
def test_unsafe_configured_profile_name_uses_pdone(monkeypatch, raw_name):
    home = _platform_install(monkeypatch)
    (home / "config.yaml").write_text(
        f'pd_one:\n  profile: "{raw_name}"\n',
        encoding="utf-8",
    )
    assert Path(profile_root()) == home / "profiles" / "pdone"

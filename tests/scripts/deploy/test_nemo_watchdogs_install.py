"""Installer dry-run, enable-state preservation, and unit rendering."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.deploy.nemo.watchdogs import install
from scripts.deploy.nemo.watchdogs.install import ENABLED, Options, render

ROOT = Path(__file__).resolve().parents[3]
WATCHDOGS = ROOT / "scripts" / "deploy" / "nemo" / "watchdogs"


def test_units_are_oneshot_timers_from_current(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    units = render(Options(home=home, releases=home / "releases"))
    assert set(units) >= {
        "hermes-watchdog-failures.service",
        "hermes-watchdog-failures.timer",
        "hermes-watchdog-gateway.service",
        "hermes-watchdog-gateway.timer",
        "hermes-watchdog-autodeploy.service",
        "hermes-watchdog-host.service",
        "hermes-watchdog-backup.timer",
    }
    service = units["hermes-watchdog-gateway.service"]
    current = str(home / "releases" / "current")
    assert "Type=oneshot" in service
    assert f"{current}/.venv/bin/python -m scripts.deploy.nemo.watchdogs.gateway" in service
    assert f"HERMES_HOME={home}" in service
    assert str(home / "watchdogs" / "webhook.env") in service
    timer = units["hermes-watchdog-gateway.timer"]
    assert "OnUnitActiveSec=2min" in timer
    assert "WantedBy=timers.target" in timer
    assert units["hermes-watchdog-failures.timer"].count("OnUnitActiveSec=5min") == 1
    assert "OnUnitActiveSec=1h" in units["hermes-watchdog-backup.timer"]
    joined = "".join(units.values())
    assert "REPLACE_WITH" not in joined
    assert "example.invalid" not in joined
    assert "WEBHOOK_SENDER_KEY" not in joined


def test_dry_run_prints_units_and_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    units_dir = install.unit_dir("user")
    units_dir.mkdir(parents=True)
    home = tmp_path / "hermes"
    code = install.main(["install", "--hermes-home", str(home), "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0
    assert "hermes-watchdog-failures.timer" in out
    assert "Type=oneshot" in out
    assert list(units_dir.iterdir()) == []


def test_install_preserves_disabled_timers_without_enable(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_systemctl(scope: str, *args: str) -> int:
        calls.append((scope, *args))
        if args and args[0] == "is-enabled":
            return 1
        if args and args[0] == "is-active":
            return 3
        return 0

    monkeypatch.setattr(install, "_systemctl", fake_systemctl)
    install._restore_unit_states("user", {ENABLED[0]: (False, False)})
    assert ("user", "disable", ENABLED[0]) in calls
    assert not any(call[1] == "enable" and "--now" in call for call in calls)


def test_install_enable_starts_timers(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "hermes"
    current = home / "releases" / "current" / ".venv" / "bin"
    current.mkdir(parents=True)
    (current / "python").write_text("", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls: list[tuple[str, ...]] = []

    def fake_systemctl(scope: str, *args: str) -> int:
        calls.append((scope, *args))
        if args and args[0] in {"is-enabled", "is-active"}:
            return 1
        return 0

    monkeypatch.setattr(install, "_systemctl", fake_systemctl)
    code = install.main(["install", "--hermes-home", str(home), "--enable"])
    assert code == 0
    enable_now = [call for call in calls if call[1:3] == ("enable", "--now")]
    assert enable_now
    assert "hermes-watchdog-gateway.timer" in enable_now[0]


def test_install_without_enable_does_not_enable_now(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "hermes"
    current = home / "releases" / "current" / ".venv" / "bin"
    current.mkdir(parents=True)
    (current / "python").write_text("", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls: list[tuple[str, ...]] = []

    def fake_systemctl(scope: str, *args: str) -> int:
        calls.append((scope, *args))
        if args and args[0] == "is-enabled":
            return 1
        if args and args[0] == "is-active":
            return 3
        return 0

    monkeypatch.setattr(install, "_systemctl", fake_systemctl)
    code = install.main(["install", "--hermes-home", str(home)])
    assert code == 0
    assert not any(call[1] == "enable" and "--now" in call for call in calls)
    written = list((Path.home() / ".config" / "systemd" / "user").glob("hermes-watchdog-*.timer"))
    assert written


@pytest.mark.platforms("linux", "macos")
def test_install_script_parses_and_dry_run_help() -> None:
    script = WATCHDOGS / "install_watchdogs.sh"
    subprocess.run(["bash", "-n", str(script)], check=True, timeout=20)
    help_out = subprocess.run(
        ["bash", str(script), "--help"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert "install" in help_out.stdout and "--enable" in help_out.stdout
    template = (WATCHDOGS / "webhook.env.template").read_text(encoding="utf-8-sig")
    assert "WEBHOOK_URL=" in template
    assert "WEBHOOK_SENDER_KEY=" in template
    assert "REPLACE_WITH_SENDER_KEY" in template
    assert "example.invalid" in template

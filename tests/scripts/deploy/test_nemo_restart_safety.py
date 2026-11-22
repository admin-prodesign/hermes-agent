"""What a nemo rollout and rollback may restart, how fast, and which runtime links move.

Regression for the first canary rollout of unit rendering: the rollout ran ``try-restart``
on a template unit (``name@.service``), and the rollback then ran ``restart`` on every
rewritten unit at once, starting stopped oneshots and starving the gateways' secret loads.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts.deploy.nemo import cli
from scripts.deploy.nemo.release_swap import runtime_links
from scripts.deploy.nemo.rollout import Restart, restart, rollback_restarts, systemctl, systemctl_timeout
from scripts.deploy.nemo.unit_state import concrete_restarts


def _capture(units: dict[str, dict]):
    """A ``systemctl`` output reader backed by ``{unit: {"active": bool, "type": str}}``."""
    calls: list[list[str]] = []

    def capture(args: list[str]) -> str | None:
        calls.append(args)
        if "show" in args:
            info = units.get(args[-1], {})
            return f"ActiveState={'active' if info.get('active') else 'inactive'}\nType={info.get('type', 'simple')}\n"
        if "list-units" in args:
            prefix = args[-1].split("*", 1)[0]
            return "".join(f"{name} loaded active running x\n" for name, info in units.items()
                           if info.get("active") and name.startswith(prefix))
        return None

    return capture, calls


@pytest.mark.platforms("linux", "macos")
def test_a_template_in_the_restart_set_becomes_its_active_instances_and_stopped_units_stay_stopped() -> None:
    capture, _ = _capture({
        "hermes-gateway-pdone.service": {"active": True},
        "alert@.service": {},
        "watch@a.service": {"active": True},
        "watch@b.service": {"active": True, "type": "oneshot"},
        "watch@.service": {},
        "kanban-bridge.service": {"type": "oneshot"},
        "dm-scan.service": {"active": True, "type": "oneshot"},
        "approval-executor.service": {},
    })
    items = [Restart("hermes-gateway-pdone.service", True), Restart("alert@.service", True, "try-restart"),
             Restart("watch@.service", True, "try-restart"), Restart("kanban-bridge.service", True),
             Restart("dm-scan.service", True), Restart("approval-executor.service", True)]

    kept, skipped = concrete_restarts(items, capture)

    assert kept == [Restart("hermes-gateway-pdone.service", True), Restart("watch@a.service", True, "try-restart")]
    assert not any("@." in item.unit for item in kept)
    assert [line.split(":")[0] for line in skipped] == [
        "alert@.service", "watch@b.service", "kanban-bridge.service", "dm-scan.service", "approval-executor.service"]


@pytest.mark.platforms("linux", "macos")
def test_rollback_restarts_only_what_the_rollout_restarted_with_its_own_verb() -> None:
    manifest = {
        "units": [{"path": "/u/kanban-bridge.service", "unit": "kanban-bridge.service", "user": True,
                   "restart": "restart"}],
        "restarted": [{"unit": "hermes-gateway.service", "user": True, "action": "restart"},
                      {"unit": "hermes-review.service", "user": True, "action": "try-restart"},
                      {"unit": "alert@.service", "user": True, "action": "try-restart"},
                      {"unit": "hermes-dashboard.service", "user": True}],
    }

    assert rollback_restarts(manifest) == [Restart("hermes-gateway.service", True, "restart"),
                                           Restart("hermes-review.service", True, "try-restart"),
                                           Restart("hermes-dashboard.service", True, "try-restart")]
    assert rollback_restarts({"units": manifest["units"], "restarted": None}) == []


@pytest.mark.platforms("linux", "macos")
def test_systemctl_restart_waits_at_least_the_unit_stop_timeout() -> None:
    """pdone TimeoutStopSec is 3m30s; a 60s client wait lost to a 105s drain."""
    assert systemctl_timeout(["--user", "restart", "hermes-gateway-pdone.service"]) >= 210
    assert systemctl_timeout(["--user", "try-restart", "hermes-gateway.service"]) >= 210
    assert systemctl_timeout(["--user", "stop", "hermes-gateway-pdone.service"]) >= 210
    assert systemctl_timeout(["--user", "start", "hermes-gateway-pdone.service"]) >= 210
    assert systemctl_timeout(["--user", "daemon-reload"]) < 210


@pytest.mark.platforms("linux", "macos")
def test_systemctl_passes_the_lifecycle_timeout_and_maps_a_client_timeout_to_failure(monkeypatch) -> None:
    seen: list[float] = []

    def fake_run(argv, **kwargs):
        seen.append(float(kwargs["timeout"]))
        assert argv[:1] == ["systemctl"]
        if argv[-1] == "hang.service":
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    args = ["--user", "restart", "hermes-gateway-pdone.service"]
    assert systemctl(args) == 0
    assert seen == [systemctl_timeout(args)]
    assert systemctl(["--user", "restart", "hang.service"]) == 1


@pytest.mark.platforms("linux", "macos")
def test_restarts_run_one_at_a_time_with_the_delay_and_wait_on_each_gateway() -> None:
    events: list[str] = []

    def run(args: list[str]) -> int:
        events.append(" ".join(args))
        return 0

    def settle(item: Restart, since: float) -> str | None:
        events.append(f"settle {item.unit}")
        return "pdone: gateway startup_failed" if item.unit == "hermes-gateway-pdone.service" else None

    items = [Restart("hermes-gateway.service", True), Restart("hermes-gateway-pdone.service", True),
             Restart("hermes-dashboard.service", True)]

    failures = restart(items, run, delay_s=4.0, sleep_fn=lambda s: events.append(f"sleep {s:g}"), settle=settle)

    assert events == ["--user restart hermes-gateway.service", "settle hermes-gateway.service", "sleep 4",
                      "--user restart hermes-gateway-pdone.service", "settle hermes-gateway-pdone.service",
                      "sleep 4", "--user restart hermes-dashboard.service", "settle hermes-dashboard.service"]
    assert failures == ["pdone: gateway startup_failed"]
    events.clear()
    restart(items, run, delay_s=0, settle=settle, stop_on_failure=True)
    assert "--user restart hermes-dashboard.service" not in events


@pytest.mark.platforms("linux", "macos")
def test_runtime_links_default_to_the_home_link_and_follow_config(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    releases = home / "releases"
    (releases / "old").mkdir(parents=True)
    (home / "runtime").mkdir()
    os.symlink("../releases/old", home / "runtime" / "current")

    assert runtime_links(home, releases, explicit=[], configured=[]) == ([home / "runtime" / "current"], [])

    links, warnings = runtime_links(home, releases, explicit=[],
                                    configured=["$HERMES_HOME/runtime/current", "runtime/missing"])
    assert links == [home / "runtime" / "current", home / "runtime" / "missing"]
    assert len(warnings) == 1 and "runtime/missing is not a symlink" in warnings[0]


@pytest.mark.platforms("linux", "macos")
def test_cutover_moves_the_hermes_home_runtime_link_and_rollback_restores_it(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    releases = home / "releases"
    for name in ("old", "new"):
        (releases / name).mkdir(parents=True)
    os.symlink("old", releases / "current")
    (home / "runtime").mkdir()
    os.symlink(str(releases / "old"), home / "runtime" / "current")
    (home / "pinned").mkdir()
    os.symlink("../releases/old", home / "pinned" / "current")
    (home / "config.yaml").write_text("deploy:\n  cutover:\n    runtime_links: [runtime/current, pinned/current]\n",
                                      encoding="utf-8")
    unit_dir = tmp_path / "units"
    unit_dir.mkdir()

    assert cli.main(["cutover", "--hermes-home", str(home), "--build", "new", "--unit-dir", str(unit_dir)]) == 0

    assert os.readlink(home / "runtime" / "current") == str((releases / "new").resolve())
    assert os.readlink(home / "pinned" / "current") == "../releases/new"
    manifest = home / "upgrade-audits" / "new" / "manifest.json"
    assert cli.main(["rollback", "--manifest", str(manifest)]) == 0
    assert os.readlink(home / "runtime" / "current") == str(releases / "old")
    assert os.readlink(home / "pinned" / "current") == "../releases/old"
    assert os.readlink(releases / "current") == "old"

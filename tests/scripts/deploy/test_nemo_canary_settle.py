"""Canary settle and verify for a gateway that comes back ``degraded``, after the old process's stop mark.

Regression for the second nemo canary: PD Neo passed, then pdone failed twice for false
reasons. Settle read the ``stopped`` the old gateway stamps (with its own PID) on its way
out as the new gateway failing, and verify refused ``degraded`` although every adapter
pdone serves was connected and its port bound (the parked platforms had no token).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.deploy.nemo.manifest import write_manifest
from scripts.deploy.nemo.rollout import Restart, gateway_settle
from scripts.deploy.nemo.verify import Expectation, check, expectations
from tests.scripts.deploy.test_nemo_rollout import REPO, _calls, _cutover, _deploy

PDONE_UNIT = "hermes-gateway-pdone.service"
OLD_PID, NEW_PID = 3200, 4000


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write(home: Path, gateway: str, pid: int, platforms: dict[str, str] | None = None,
           stamp: str | None = None, **extra) -> None:
    stamp = stamp or _now()
    home.mkdir(parents=True, exist_ok=True)
    (home / "gateway_state.json").write_text(json.dumps({
        "gateway_state": gateway, "pid": pid, "updated_at": stamp, **extra,
        "platforms": {name: {"state": state, "updated_at": stamp} for name, state in (platforms or {}).items()},
    }), encoding="utf-8")


class _Clock:
    """Fake monotonic clock; each sleep advances it and runs the next scripted step."""

    def __init__(self, steps=()) -> None:
        self.now = 0.0
        self.steps = list(steps)

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        if self.steps:
            self.steps.pop(0)()


def _settle(tmp_path: Path, clock: _Clock, main_pid: int | None = NEW_PID, timeout: float = 10.0):
    exp = Expectation("pdone", tmp_path, ("mattermost", "line"), (8646,))
    settle = gateway_settle({PDONE_UNIT: exp}, timeout_s=timeout, interval_s=1.0,
                            main_pid_fn=lambda item: main_pid, clock_fn=clock, sleep_fn=clock.sleep)
    return settle(Restart(PDONE_UNIT, True), datetime.now(UTC).timestamp() - 1)


# ---------------------------------------------------------------- settle


@pytest.mark.parametrize("new_state", ["running", "degraded"])
def test_the_old_pids_stopped_mark_is_waited_out_until_the_new_pid_serves(tmp_path: Path, new_state: str) -> None:
    _write(tmp_path, "stopped", OLD_PID)
    clock = _Clock([lambda: _write(tmp_path, "starting", NEW_PID),
                    lambda: _write(tmp_path, new_state, NEW_PID, {"mattermost": "connected"})])

    assert _settle(tmp_path, clock) is None
    assert clock.now == 2.0


def test_the_old_pids_running_mark_after_an_unexpected_signal_does_not_pass_settle(tmp_path: Path) -> None:
    _write(tmp_path, "running", OLD_PID)

    problem = _settle(tmp_path, _Clock(), timeout=3.0)

    assert problem is not None and "not serving" in problem
    assert f"from pid {OLD_PID}, not the unit's main pid {NEW_PID}" in problem


def test_a_stop_mark_written_before_the_restart_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "stopped", NEW_PID, stamp="2000-01-01T00:00:00+00:00")
    clock = _Clock([lambda: _write(tmp_path, "degraded", NEW_PID)])

    assert _settle(tmp_path, clock) is None


@pytest.mark.parametrize("state", ["stopped", "startup_failed"])
def test_the_new_pids_own_failure_ends_settle_early(tmp_path: Path, state: str) -> None:
    _write(tmp_path, "stopped", OLD_PID)
    clock = _Clock([lambda: _write(tmp_path, state, NEW_PID)])

    assert _settle(tmp_path, clock) == f"pdone: gateway {state} after restart {PDONE_UNIT}"
    assert clock.now == 1.0


def test_without_a_main_pid_a_stop_mark_is_waited_out_not_failed_on(tmp_path: Path) -> None:
    _write(tmp_path, "stopped", OLD_PID)
    clock = _Clock([lambda: _write(tmp_path, "running", NEW_PID)])

    assert _settle(tmp_path, clock, main_pid=None) is None
    _write(tmp_path, "stopped", OLD_PID)
    assert "not serving 3s" in _settle(tmp_path, _Clock(), main_pid=None, timeout=3.0)


# ---------------------------------------------------------------- verify


def _failed(exp: Expectation, *, bound: bool = True) -> list[str]:
    checks = check(exp, datetime.now(UTC).timestamp() - 1, connect=lambda host, port, timeout: bound)
    return [item.name for item in checks if not item.ok]


PDONE = Expectation("pdone", Path(), ("mattermost", "line"), (8646,))


def test_degraded_passes_when_every_expected_adapter_is_connected_and_port_bound(tmp_path: Path) -> None:
    exp = Expectation("pdone", tmp_path, PDONE.platforms, PDONE.ports)
    _write(tmp_path, "degraded", NEW_PID, {"mattermost": "connected", "line": "connected",
                                           "telegram": "fatal", "discord": "fatal"})

    assert _failed(exp) == []
    assert _failed(exp, bound=False) == ["pdone:port 8646"]


@pytest.mark.parametrize("line", ["absent", "disconnected", "fatal", "retrying"])
def test_degraded_fails_when_an_expected_adapter_is_missing_or_not_connected(tmp_path: Path, line: str) -> None:
    exp = Expectation("pdone", tmp_path, PDONE.platforms, PDONE.ports)
    platforms = {"mattermost": "connected"} | ({} if line == "absent" else {"line": line})
    _write(tmp_path, "degraded", NEW_PID, platforms)

    assert _failed(exp) == ["pdone:line"]


def test_degraded_still_fails_on_a_watchdog_exit_or_with_nothing_expected(tmp_path: Path) -> None:
    exp = Expectation("pdone", tmp_path, PDONE.platforms, PDONE.ports)
    _write(tmp_path, "degraded", NEW_PID, {"mattermost": "connected", "line": "connected"},
           exit_reason="event loop wedged")
    assert _failed(exp) == ["pdone:gateway"]

    _write(tmp_path, "degraded", NEW_PID, {"mattermost": "connected"})
    assert _failed(Expectation("pdone", tmp_path, (), ())) == ["pdone:gateway"]
    _write(tmp_path, "running", NEW_PID)
    assert _failed(Expectation("pdone", tmp_path, (), ())) == []


def test_expected_adapters_ports_and_host_come_from_each_profiles_config(tmp_path: Path) -> None:
    verify = {"default": {"platforms": ["webhook"], "ports": [8644], "host": "127.0.0.1"},
              "pdone": {"platforms": "mattermost, line", "ports": 8646}}

    found = expectations(tmp_path, ("pdone", "default"), verify_config=verify, platforms={}, ports={},
                         gate={"pdone": {"platforms": ["mattermost", "line", "telegram", "discord"]}})

    assert found == [Expectation("pdone", tmp_path / "profiles" / "pdone", ("mattermost", "line"), (8646,)),
                     Expectation("default", tmp_path, ("webhook",), (8644,), "127.0.0.1")]


# ---------------------------------------------------------------- canary rehearsal, both profiles


def _listening() -> socket.socket:
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    return server


def _verify_config(home: Path, default_port: int, pdone_port: int) -> None:
    (home / "config.yaml").write_text(
        "deploy:\n  verify:\n"
        f"    default: {{platforms: [webhook], ports: [{default_port}], host: 127.0.0.1}}\n"
        f"    pdone: {{platforms: [mattermost, line], ports: [{pdone_port}]}}\n", encoding="utf-8")


PDONE_DEGRADED = {"gateway": "degraded", "stale_stop": True,
                  "platforms": {"mattermost": "connected", "line": "connected",
                                "telegram": "fatal", "discord": "fatal"}}


@pytest.mark.platforms("linux")
def test_canary_rehearsal_rolls_out_both_profiles_past_the_stop_mark_and_degraded(tmp_path: Path) -> None:
    layout = _deploy(tmp_path)
    with _listening() as neo, _listening() as pdone:
        _verify_config(layout["home"], neo.getsockname()[1], pdone.getsockname()[1])
        proc = _cutover(layout, {"default": {"gateway": "running", "stale_stop": True,
                                             "platforms": {"webhook": "connected"}},
                                 "pdone": PDONE_DEGRADED}, "--canary")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok\tpdone:gateway\tdegraded" in proc.stdout
    for name in ("default:webhook", "pdone:mattermost", "pdone:line", "default:port", "pdone:port"):
        assert f"ok\t{name}" in proc.stdout
    assert "telegram" not in proc.stdout and "discord" not in proc.stdout
    assert os.readlink(layout["releases"] / "current") == "new"
    calls = _calls(layout)
    assert calls.index("--user restart hermes-gateway.service") < calls.index(f"--user restart {PDONE_UNIT}")


@pytest.mark.platforms("linux")
def test_canary_rehearsal_rolls_back_when_pdone_is_degraded_with_line_down(tmp_path: Path) -> None:
    layout = _deploy(tmp_path)
    line_down = {**PDONE_DEGRADED, "platforms": {**PDONE_DEGRADED["platforms"], "line": "fatal"}}
    with _listening() as neo, _listening() as pdone:
        _verify_config(layout["home"], neo.getsockname()[1], pdone.getsockname()[1])
        proc = _cutover(layout, {"default": "connected", "pdone": line_down}, "--canary",
                        old_state={"pdone": PDONE_DEGRADED})

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "fail\tpdone:line\tfatal" in proc.stdout
    assert "ROLLBACK FAILED" not in proc.stderr
    assert "rollback restarted: restart hermes-gateway.service, restart hermes-gateway-pdone.service" \
        in proc.stdout
    assert os.readlink(layout["releases"] / "current") == "old"


@pytest.mark.platforms("linux", "macos")
def test_rollout_dry_run_prints_both_stages_and_expectations_without_systemctl(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    _verify_config(home, 8644, 8646)
    manifest = home / "upgrade-audits" / "new" / "manifest.json"
    write_manifest(manifest, {"units": [
        {"path": f"/units/{PDONE_UNIT}", "unit": PDONE_UNIT, "user": True, "restart": "restart"},
        {"path": "/units/hermes-gateway.service", "unit": "hermes-gateway.service", "user": True,
         "restart": "restart"}]})
    before = manifest.read_text(encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "systemctl").write_text(f"#!/bin/sh\necho called >> {tmp_path / 'called'}\nexit 1\n",
                                        encoding="utf-8")
    (fake_bin / "systemctl").chmod(0o755)

    proc = subprocess.run(
        [sys.executable, "-m", "scripts.deploy.nemo.cli", "rollout", "--hermes-home", str(home),
         "--manifest", str(manifest), "--profile", "default", "--profile", "pdone", "--canary", "--dry-run"],
        cwd=REPO, env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        capture_output=True, text=True, timeout=120, check=False)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert "stage 1/2 (default): restart hermes-gateway.service" in lines
    assert "  default: expects webhook; 127.0.0.1:8644" in lines
    assert f"stage 2/2 (pdone): restart {PDONE_UNIT}" in lines
    assert "  pdone: expects mattermost, line; 127.0.0.1:8646" in lines
    assert not (tmp_path / "called").exists()
    assert manifest.read_text(encoding="utf-8") == before

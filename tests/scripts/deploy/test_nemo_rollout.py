"""Adapter gate before cutover, staged restart with verify after it, and rollback on failure.

The end-to-end tests run the real ``cutover.sh`` against a release made of this checkout,
with a fake ``systemctl`` on ``PATH`` that records calls and writes the gateway's
``gateway_state.json`` the way a started gateway would.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from scripts.deploy.nemo.extras import DIST, declared, missing
from scripts.deploy.nemo.manifest import write_manifest
from scripts.deploy.nemo.rollout import Restart, plan_stages, restarts_from, rollback_restarts
from scripts.deploy.nemo.verify import Expectation, check, tcp_open

REPO = Path(__file__).resolve().parents[3]
NEMO = REPO / "scripts" / "deploy" / "nemo"


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------- staging


@pytest.mark.platforms("linux", "macos")
def test_canary_restarts_the_top_level_gateway_alone_and_pdone_last() -> None:
    restarts = [Restart("hermes-gateway-pdone.service", True), Restart("hermes-dashboard.service", True),
                Restart("hermes-gateway.service", True)]

    stages = plan_stages(restarts, ("pdone", "default"), canary=True)

    assert [stage.profiles for stage in stages] == [("default",), ("pdone",)]
    assert [item.unit for item in stages[0].restarts] == ["hermes-gateway.service"]
    assert [item.unit for item in stages[1].restarts] == ["hermes-gateway-pdone.service",
                                                          "hermes-dashboard.service"]
    single = plan_stages(restarts, ("pdone", "default"), canary=False)
    assert len(single) == 1 and single[0].restarts == restarts


@pytest.mark.platforms("linux", "macos")
def test_a_unit_with_a_moved_path_restarts_even_when_another_file_only_changed_its_sha() -> None:
    units = [
        {"path": "/u/hermes-gateway.service.d/91.conf", "unit": "hermes-gateway.service", "user": True,
         "restart": "try-restart"},
        {"path": "/u/hermes-gateway.service", "unit": "hermes-gateway.service", "user": True,
         "restart": "restart"},
        {"path": "/u/hermes-review.service", "unit": "hermes-review.service", "user": True,
         "restart": "try-restart"},
    ]

    assert restarts_from(units) == [Restart("hermes-gateway.service", True, "restart"),
                                    Restart("hermes-review.service", True, "try-restart")]




# ---------------------------------------------------------------- verify


def _state(home: Path, platforms: dict[str, str], stamp: str | None = None) -> None:
    stamp = stamp or _now()
    home.mkdir(parents=True, exist_ok=True)
    (home / "gateway_state.json").write_text(json.dumps({
        "gateway_state": "running", "updated_at": stamp,
        "platforms": {name: {"state": state, "updated_at": stamp} for name, state in platforms.items()},
    }), encoding="utf-8")


@pytest.mark.platforms("linux", "macos")
def test_verify_needs_fresh_connected_adapters_and_a_bound_port(tmp_path: Path) -> None:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        exp = Expectation("pdone", tmp_path, ("mattermost", "line"), (port,))
        since = time.time()

        _state(tmp_path, {"mattermost": "connected", "line": "connected"})
        assert all(item.ok for item in check(exp, since, connect=tcp_open))

        _state(tmp_path, {"mattermost": "connected", "line": "fatal"})
        failed = [item.name for item in check(exp, since, connect=tcp_open) if not item.ok]
        assert failed == ["pdone:line"]

        _state(tmp_path, {"mattermost": "connected", "line": "connected"}, "2000-01-01T00:00:00+00:00")
        stale = [item.name for item in check(exp, since, connect=tcp_open) if not item.ok]
        assert stale == ["pdone:gateway", "pdone:mattermost", "pdone:line"]

    _state(tmp_path, {"mattermost": "connected", "line": "connected"})
    unbound = [item.name for item in check(exp, since, connect=tcp_open) if not item.ok]
    assert unbound == [f"pdone:port {port}"]


# ---------------------------------------------------------------- declared extras


@pytest.mark.platforms("linux", "macos")
def test_the_messaging_extra_declares_the_webhook_dependency() -> None:
    names = {req.name for req in declared(["messaging"])}
    assert "aiohttp" in names
    assert "aiohttp" not in {req.name for req in declared([])}
    absent = missing([Requirement("hermes-nemo-test-not-installed==1.0")])
    assert absent and "hermes-nemo-test-not-installed is not installed" in absent[0]


# ---------------------------------------------------------------- cutover.sh end to end

_FAKE_SYSTEMCTL = """#!{python}
import fnmatch, json, os, sys
from datetime import UTC, datetime
args = [arg for arg in sys.argv[1:] if arg != "--user"]
with open(os.environ["FAKE_SYSTEMCTL_LOG"], "a", encoding="utf-8") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")
state_path = os.environ["FAKE_SYSTEMD_STATE"]
with open(state_path, encoding="utf-8") as fh:
    units = json.load(fh)
verb, unit = args[0], args[-1]
if verb == "show":
    info = units.get(unit, {{}})
    print(f"Type={{info.get('type', 'simple')}}")
    print(f"ActiveState={{'active' if info.get('active') else 'inactive'}}")
elif verb == "list-units":
    for name, info in units.items():
        if info.get("active") and fnmatch.fnmatch(name, unit):
            print(f"{{name}} loaded active running fake")
elif verb in ("restart", "try-restart"):
    if "@." in unit:
        print(f"Failed to {{verb}} {{unit}}: Unit name {{unit}} is a unit template", file=sys.stderr)
        sys.exit(1)
    info = units.setdefault(unit, {{}})
    if verb == "try-restart" and not info.get("active"):
        sys.exit(0)
    info["active"] = True
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(units, fh)
    if unit.startswith("hermes-gateway"):
        profile = unit.removeprefix("hermes-gateway").removeprefix("-").removesuffix(".service")
        with open(os.path.join(os.environ["FAKE_UNIT_DIR"], unit), encoding="utf-8") as fh:
            release = "new" if "/new/" in fh.read() else "old"
        state = json.loads(os.environ["FAKE_STATES"]).get(release, {{}}).get(profile or "default", "connected")
        home = os.environ["FAKE_HERMES_HOME"]
        path = os.path.join(home, "profiles", profile) if profile else home
        now = datetime.now(UTC).isoformat()
        gateway = "startup_failed" if state == "startup_failed" else "running"
        with open(os.path.join(path, "gateway_state.json"), "w", encoding="utf-8") as fh:
            json.dump({{"gateway_state": gateway, "updated_at": now,
                       "platforms": {{"webhook": {{"state": state, "updated_at": now}}}}}}, fh)
"""

GATEWAYS = {"hermes-gateway.service": {"active": True}, "hermes-gateway-pdone.service": {"active": True}}


def _release(releases: Path, name: str) -> Path:
    """This checkout under a release name, with an interpreter that keeps the test venv."""
    release = releases / name
    bin_dir = release / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    for entry in REPO.iterdir():
        if not entry.name.startswith("."):
            os.symlink(entry, release / entry.name)
    python = bin_dir / "python"
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    python.chmod(0o755)
    return release


def _satisfied_extra() -> str:
    """An extra this interpreter fully installs, so the gate's requirement check can pass."""
    for extra in metadata.metadata(DIST).get_all("Provides-Extra") or []:
        if not missing(declared([extra])):
            return extra
    pytest.skip("no extra of hermes-agent is fully installed in this interpreter")


def _deploy(tmp_path: Path, extra_units: dict[str, dict] | None = None) -> dict:
    """Both gateways active; ``extra_units`` maps more unit files to their systemd state."""
    home = tmp_path / "hermes"
    releases = home / "releases"
    old = _release(releases, "old")
    _release(releases, "new")
    write_manifest(home / "upgrade-audits" / "new" / "manifest.json", {"extra": _satisfied_extra()})
    os.symlink("old", releases / "current")
    (home / "runtime").mkdir()
    os.symlink("../releases/old", home / "runtime" / "current")
    unit_dir = tmp_path / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True)
    for unit, profile_home in (("hermes-gateway.service", home),
                               ("hermes-gateway-pdone.service", home / "profiles" / "pdone")):
        profile_home.mkdir(parents=True, exist_ok=True)
        (unit_dir / unit).write_text(
            f"[Service]\nExecStart={old}/.venv/bin/python -m hermes_cli.main gateway run\n"
            f"Environment=HERMES_HOME={profile_home}\n", encoding="utf-8")
    for unit in extra_units or {}:
        (unit_dir / unit).write_text(f"[Service]\nExecStart={old}/.venv/bin/python -m tools.x\n", encoding="utf-8")
    systemd = tmp_path / "systemd.json"
    systemd.write_text(json.dumps({**GATEWAYS, **(extra_units or {})}), encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "systemctl"
    fake.write_text(_FAKE_SYSTEMCTL.format(python=sys.executable), encoding="utf-8")
    fake.chmod(0o755)
    return {"home": home, "releases": releases, "unit_dir": unit_dir, "bin": bin_dir,
            "log": tmp_path / "systemctl.log", "systemd": systemd}


def _cutover(layout: dict, new_state: str | dict, *extra: str,
             old_state: dict | None = None) -> subprocess.CompletedProcess[str]:
    """``new_state``/``old_state``: webhook state per profile once its gateway runs that release."""
    new = new_state if isinstance(new_state, dict) else {"default": new_state, "pdone": new_state}
    env = {**os.environ, "NEMO_PYTHON": sys.executable, "PATH": f"{layout['bin']}:{os.environ['PATH']}",
           "FAKE_SYSTEMCTL_LOG": str(layout["log"]), "FAKE_SYSTEMD_STATE": str(layout["systemd"]),
           "FAKE_UNIT_DIR": str(layout["unit_dir"]), "FAKE_HERMES_HOME": str(layout["home"]),
           "FAKE_STATES": json.dumps({"new": new, "old": old_state or {}})}
    env.pop("HERMES_HOME", None)
    argv = ["bash", str(NEMO / "cutover.sh"), "--hermes-home", str(layout["home"]), "--build", "new",
            "--sha", "b" * 40, "--unit-dir", str(layout["unit_dir"]), "--profile", "default",
            "--profile", "pdone", "--skip-preflight", "--skip-selftest", "--skip-gate", "--skip-health",
            "--skip-postcheck", "--health-timeout", "3", "--health-interval", "0.2", "--restart-delay", "0",
            *extra]
    return subprocess.run(argv, env=env, capture_output=True, text=True, timeout=300, check=False)


def _units(layout: dict) -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in layout["unit_dir"].rglob("*") if path.is_file()}


def _calls(layout: dict) -> list[str]:
    return layout["log"].read_text(encoding="utf-8").splitlines() if layout["log"].is_file() else []


@pytest.mark.platforms("linux")
def test_adapter_gate_refuses_a_release_missing_an_enabled_adapters_dependency(tmp_path: Path) -> None:
    layout = _deploy(tmp_path)
    (layout["home"] / ".env").write_text("WEBHOOK_ENABLED=true\n", encoding="utf-8")
    shadow = tmp_path / "shadow" / "aiohttp"
    shadow.mkdir(parents=True)
    (shadow / "__init__.py").write_text("raise ImportError('aiohttp is not in this release')\n", encoding="utf-8")
    drop_in = layout["unit_dir"] / "hermes-gateway.service.d"
    drop_in.mkdir()
    (drop_in / "90-env.conf").write_text(f"[Service]\nEnvironment=PYTHONPATH={shadow.parent}\n",
                                         encoding="utf-8")
    before = _units(layout)

    proc = _cutover(layout, "connected")

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "nothing was changed" in proc.stderr
    report = json.loads((layout["home"] / "upgrade-audits" / "new" / "adapters.json").read_text(encoding="utf-8"))
    assert [item["platform"] for item in report["default"]["failures"]] == ["webhook"]
    assert "aiohttp" in report["default"]["failures"][0]["detail"]
    assert _units(layout) == before
    assert os.readlink(layout["releases"] / "current") == "old"
    assert _calls(layout) == []


@pytest.mark.platforms("linux")
def test_canary_failure_rolls_back_before_pdone_restarts(tmp_path: Path) -> None:
    layout = _deploy(tmp_path)
    before = _units(layout)

    proc = _cutover(layout, "fatal", "--canary", "--expect", "default=webhook")

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "fail\tdefault:webhook" in proc.stdout
    assert _units(layout) == before
    assert os.readlink(layout["releases"] / "current") == "old"
    assert not (layout["releases"] / ".running").exists()
    restarts = [call for call in _calls(layout) if " restart " in f" {call} "]
    assert restarts == ["--user restart hermes-gateway.service"] * 2
    manifest = json.loads((layout["home"] / "upgrade-audits" / "new" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["restarted"] == [{"unit": "hermes-gateway.service", "user": True, "action": "restart"}]


@pytest.mark.platforms("linux")
def test_cutover_goes_live_when_adapters_connect_and_ports_bind(tmp_path: Path) -> None:
    layout = _deploy(tmp_path)
    new = (layout["releases"] / "new").resolve()
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        proc = _cutover(layout, "connected", "--canary", "--expect", "default=webhook",
                        "--expect-port", f"default={port}")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"ok\tdefault:port {port}" in proc.stdout
    assert all(str(new) in text for text in _units(layout).values())
    assert os.readlink(layout["releases"] / "current") == "new"
    assert (layout["releases"] / ".running").read_text(encoding="utf-8").strip() == "new"
    calls = _calls(layout)
    assert calls.index("--user daemon-reload") < calls.index("--user restart hermes-gateway.service") \
        < calls.index("--user restart hermes-gateway-pdone.service")


INCIDENT_UNITS = {
    "pd-one-systemd-failure-alert@.service": {},
    "pd-one-kanban-bridge.service": {"type": "oneshot"},
    "pd-one-dm-scan.service": {"type": "oneshot"},
    "hermes-approval-executor.service": {},
    "hermes-dashboard.service": {"active": True},
}
NEVER_STARTED = ("pd-one-systemd-failure-alert@.service", "pd-one-kanban-bridge.service",
                 "pd-one-dm-scan.service", "hermes-approval-executor.service")


def _restarts(layout: dict) -> list[str]:
    return [call for call in _calls(layout) if "restart" in call.split()[:2] or "try-restart" in call.split()[:2]]


@pytest.mark.platforms("linux")
def test_rollback_keeps_stopped_oneshots_and_templates_stopped_and_verifies_the_gateways(tmp_path: Path) -> None:
    layout = _deploy(tmp_path, INCIDENT_UNITS)
    before = _units(layout)

    proc = _cutover(layout, {"default": "connected", "pdone": "fatal"}, "--canary",
                    "--expect", "default=webhook", "--expect", "pdone=webhook")

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "fail\tpdone:webhook" in proc.stdout
    restarts = _restarts(layout)
    assert not [call for call in restarts if call.endswith(NEVER_STARTED)]
    rollout = ["--user restart hermes-gateway.service", "--user restart hermes-gateway-pdone.service",
               "--user restart hermes-dashboard.service"]
    assert restarts == rollout + rollout
    assert "rollback restarted: restart hermes-gateway.service, restart hermes-gateway-pdone.service" in proc.stdout
    assert "ROLLBACK FAILED" not in proc.stderr
    assert _units(layout) == before
    assert os.readlink(layout["releases"] / "current") == "old"
    assert os.readlink(layout["home"] / "runtime" / "current") == "../releases/old"
    systemd = json.loads(layout["systemd"].read_text(encoding="utf-8"))
    assert not any(systemd[name].get("active") for name in NEVER_STARTED)


@pytest.mark.platforms("linux")
def test_a_rollback_whose_gateway_does_not_come_back_fails_with_a_summary(tmp_path: Path) -> None:
    layout = _deploy(tmp_path)

    proc = _cutover(layout, {"default": "connected", "pdone": "fatal"}, "--expect", "default=webhook",
                    "--expect", "pdone=webhook", old_state={"pdone": "startup_failed"})

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "rollback FAILED to bring the previous release back cleanly" in proc.stderr
    assert "pdone: gateway startup_failed after restart hermes-gateway-pdone.service" in proc.stderr
    assert "verify: pdone:gateway (startup_failed)" in proc.stderr
    assert "ROLLBACK FAILED" in proc.stderr
    assert os.readlink(layout["releases"] / "current") == "old"

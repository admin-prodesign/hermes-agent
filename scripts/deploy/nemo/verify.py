"""After a restart: did each profile's gateway connect the adapters it should, and bind its ports?

Per profile, ``<profile home>/gateway_state.json`` (written by the gateway, see
``gateway/status.py``) must say ``running``, and every expected platform must be
``connected`` with an ``updated_at`` after the restart, so a file the old process
left behind cannot pass. Every expected port must accept a TCP connection.

``degraded`` (a configured platform was parked at startup, e.g. one with no token) passes
too, but only for a profile that expects at least one adapter or port, and only while no
``exit_reason`` is set (a watchdog stamps ``degraded`` with one before it kills a wedged
process). Its expected adapters and ports are still checked one by one, so ``degraded``
passes exactly when everything the profile is expected to serve is up. Adapters nobody
expects are never checked.

Expected platforms come from ``--expect PROFILE=PLATFORM``, else
``deploy.verify.<profile>.platforms`` in ``<home>/config.yaml``, else the adapters
the pre-cutover gate started for that profile. Ports come from ``--expect-port`` or
``deploy.verify.<profile>.ports`` only; with none, no port is checked. Ports are probed on
``deploy.verify.<profile>.host``, else ``--port-host`` (default ``127.0.0.1``)::

    deploy:
      verify:
        default: {platforms: [webhook], ports: [8644], host: 127.0.0.1}
        pdone: {platforms: [mattermost, line], ports: [8646]}
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from scripts.deploy.nemo.health import HealthCheck
from scripts.deploy.nemo.layout import TOP_LEVEL_PROFILE_ALIASES, profile_home

STATE_FILE = "gateway_state.json"
DEFAULT_PORT_HOST = "127.0.0.1"
SERVING_GATEWAY_STATES = frozenset({"running", "degraded"})
Connect = Callable[[str, int, float], bool]


@dataclass(frozen=True)
class Expectation:
    profile: str
    home: Path
    platforms: tuple[str, ...]
    ports: tuple[int, ...]
    host: str | None = None


def tcp_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _profile_block(verify: dict[str, Any], profile: str) -> dict[str, Any]:
    names = [profile]
    if profile in TOP_LEVEL_PROFILE_ALIASES:
        names += sorted(TOP_LEVEL_PROFILE_ALIASES - {profile, ""})
    for name in names:
        block = verify.get(name)
        if isinstance(block, dict):
            return block
    return {}


def _strings(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, (str, int)):
        value = str(value).split(",")
    return tuple(str(item).strip() for item in value if str(item).strip())


def expectations(
    home: Path, profiles: tuple[str, ...], *, verify_config: dict[str, Any],
    platforms: dict[str, list[str]], ports: dict[str, list[str]], gate: dict[str, Any],
) -> list[Expectation]:
    found: list[Expectation] = []
    for name in profiles:
        block = _profile_block(verify_config, name)
        gated = gate.get(name) or {}
        chosen = (_strings(platforms.get(name)) or _strings(block.get("platforms"))
                  or tuple(gated.get("platforms") or ()))
        port_values = _strings(ports.get(name)) or _strings(block.get("ports")) or ()
        where = Path(gated["home"]) if gated.get("home") else profile_home(home, name)
        host = str(block.get("host") or "").strip() or None
        found.append(Expectation(name, where, chosen, tuple(int(item) for item in port_values), host))
    return found


def written_after(stamp: Any, since: float) -> bool:
    try:
        return datetime.fromisoformat(str(stamp)).timestamp() >= since
    except (TypeError, ValueError):
        return False


def read_state(home: Path) -> dict[str, Any]:
    try:
        state = json.loads((home / STATE_FILE).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def state_pid(state: dict[str, Any]) -> int | None:
    try:
        return int(state.get("pid"))
    except (TypeError, ValueError):
        return None


def _gateway_check(exp: Expectation, state: dict[str, Any], since: float) -> HealthCheck:
    gateway = str(state.get("gateway_state") or "missing")
    name = f"{exp.profile}:gateway"
    if not written_after(state.get("updated_at"), since):
        return HealthCheck(name, False, f"{gateway} (not written since the restart)")
    if gateway == "running":
        return HealthCheck(name, True, gateway)
    if gateway != "degraded":
        return HealthCheck(name, False, gateway)
    if state.get("exit_reason"):
        return HealthCheck(name, False, f"degraded: {state['exit_reason']}"[:300])
    if not exp.platforms and not exp.ports:
        return HealthCheck(name, False, "degraded, and no adapter or port is expected of this profile")
    return HealthCheck(name, True, "degraded (accepted only with every expected adapter and port up)")


def check(exp: Expectation, since: float, *, connect: Connect, host: str = DEFAULT_PORT_HOST,
          timeout: float = 2.0) -> list[HealthCheck]:
    label = f"{exp.profile}:"
    state = read_state(exp.home)
    checks = [_gateway_check(exp, state, since)]
    platforms = state.get("platforms") if isinstance(state.get("platforms"), dict) else {}
    for name in exp.platforms:
        entry = platforms.get(name) if isinstance(platforms.get(name), dict) else {}
        status = str(entry.get("state") or "absent")
        ok = status == "connected" and written_after(entry.get("updated_at"), since)
        detail = status if not entry.get("error_message") else f"{status}: {entry['error_message']}"[:300]
        checks.append(HealthCheck(f"{label}{name}", ok, detail))
    for port in exp.ports:
        bound = connect(exp.host or host, port, timeout)
        checks.append(HealthCheck(f"{label}port {port}", bound, "listening" if bound else "nothing listening"))
    return checks


def poll_until_verified(
    exps: list[Expectation], since: float, *, timeout_s: float, interval_s: float,
    clock_fn: Callable[[], float], sleep_fn: Callable[[float], None], connect: Connect = tcp_open,
    host: str = DEFAULT_PORT_HOST,
) -> tuple[bool, list[HealthCheck]]:
    started = clock_fn()
    while True:
        latest = [item for exp in exps for item in check(exp, since, connect=connect, host=host)]
        if all(item.ok for item in latest):
            return True, latest
        if clock_fn() - started >= timeout_s:
            return False, latest
        sleep_fn(interval_s)

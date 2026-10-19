"""daemon-reload, then restart the rewritten units in stages, verifying each stage.

Only concrete units that are active and not oneshot are restarted (``unit_state.py``): a
template becomes its active instances, and a stopped unit or a oneshot is never started.
Without ``--canary`` there is one stage: every restartable unit, then every profile is
verified. With it, each profile's gateway unit is its own stage in canary order (the
top-level profile, PD Neo, first) and the other units (dashboard, approval and review
units) go with the last stage; a stage that fails verification stops the rollout so
later profiles never restart onto the new release. Units whose only change was
``HERMES_RUNTIME_SHA`` get ``try-restart``.

Restarts run one unit at a time with ``delay_s`` between them, and after a gateway the
next unit waits until that gateway's new process (the unit's ``MainPID``) wrote a fresh
``running`` or ``degraded`` state (or failed); the old process's ``stopped`` is ignored. So
two gateways never start together and load their secrets at once. Each unit is recorded in
the manifest with its verb before its restart, so a rollback restarts exactly those, with
the same verb.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from scripts.deploy.nemo.layout import canary_order, gateway_unit_name
from scripts.deploy.nemo.manifest import read_manifest, write_manifest
from scripts.deploy.nemo.units import RESTART, TRY_RESTART, is_template
from scripts.deploy.nemo.verify import SERVING_GATEWAY_STATES, Expectation, read_state, state_pid, written_after

Systemctl = Callable[[list[str]], int]
Settle = Callable[["Restart", float], "str | None"]
MainPid = Callable[["Restart"], "int | None"]
UnitActive = Callable[["Restart"], str | None]
_TERMINAL_UNIT_STATES = frozenset({"failed", "inactive", "dead"})
ProcessAlive = Callable[[int | None], bool]
SettleTimeout = Callable[["Restart"], float]


def _process_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@dataclass(frozen=True)
class Restart:
    unit: str
    user: bool
    action: str = RESTART


@dataclass
class Stage:
    profiles: tuple[str, ...]
    restarts: list[Restart] = field(default_factory=list)


def systemctl(args: list[str]) -> int:
    try:
        return subprocess.run(["systemctl", *args], timeout=60, stdin=subprocess.DEVNULL,
                              check=False).returncode
    except (OSError, subprocess.TimeoutExpired):
        return 1


def _scope(user: bool) -> list[str]:
    return ["--user"] if user else []


def restarts_from(units: list[dict]) -> list[Restart]:
    """One entry per unit in first-seen order; any file needing ``restart`` wins over ``try-restart``."""
    merged: dict[tuple[str, bool], str] = {}
    for item in units:
        unit = str(item.get("unit") or Path(str(item["path"])).name)
        key = (unit, bool(item.get("user")))
        action = str(item.get("restart") or RESTART)
        merged[key] = RESTART if RESTART in (merged.get(key), action) else action
    return [Restart(unit, user, action) for (unit, user), action in merged.items()]


def plan_stages(restarts: list[Restart], profiles: tuple[str, ...], *, canary: bool,
                overrides: dict[str, str] | None = None) -> list[Stage]:
    if not canary:
        return [Stage(profiles, list(restarts))]
    remaining = list(restarts)
    stages: list[Stage] = []
    for profile in canary_order(profiles):
        unit = gateway_unit_name(profile, overrides)
        mine = [item for item in remaining if item.unit == unit]
        remaining = [item for item in remaining if item.unit != unit]
        stages.append(Stage((profile,), mine))
    if not stages:
        return [Stage((), remaining)]
    stages[-1].restarts.extend(remaining)
    return stages


def daemon_reload(units: list[dict], run: Systemctl) -> list[str]:
    failures: list[str] = []
    for user in sorted({bool(item.get("user")) for item in units}):
        if run([*_scope(user), "daemon-reload"]) != 0:
            failures.append(f"daemon-reload{' --user' if user else ''} failed")
    return failures


def mark_restarted(manifest: Path, restarts: list[Restart]) -> None:
    done = list(read_manifest(manifest).get("restarted") or [])
    seen = {(item.get("unit"), bool(item.get("user"))) for item in done}
    for item in restarts:
        if (item.unit, item.user) not in seen:
            done.append({"unit": item.unit, "user": item.user, "action": item.action})
            seen.add((item.unit, item.user))
    write_manifest(manifest, {"restarted": done})


def restart(restarts: list[Restart], run: Systemctl, *, delay_s: float = 0.0,
            sleep_fn: Callable[[float], None] = time.sleep, settle: Settle | None = None,
            stop_on_failure: bool = False) -> list[str]:
    """One unit at a time, ``delay_s`` apart; ``settle`` waits on a restarted gateway."""
    failures: list[str] = []
    for index, item in enumerate(restarts):
        if index and delay_s > 0:
            sleep_fn(delay_s)
        since = time.time()
        problem = None
        if run([*_scope(item.user), item.action, item.unit]) != 0:
            problem = f"systemctl {item.action} {item.unit} failed"
        elif settle is not None:
            problem = settle(item, since)
        if problem:
            failures.append(problem)
            if stop_on_failure:
                break
    return failures


def settle_verdict(
    state: dict,
    since: float,
    main_pid: int | None,
    *,
    unit_active: str | None = "active",
    process_alive_fn: ProcessAlive = _process_alive,
) -> tuple[bool | None, str]:
    """``(True, _)`` serving, ``(False, why)`` failed, ``(None, why)`` keep waiting.

    Only a record written after the restart by the unit's current main process counts: on a
    restart the old process stamps ``stopped`` (``running`` after an unexpected signal) with
    its own PID after ``since``, before the new one writes anything. ``main_pid`` is systemd's
    ``MainPID`` (0: no main process yet), ``None`` when systemd could not say; then a
    ``stopped`` cannot be attributed and is waited out rather than failed on.

    A ``stopped`` mark whose PID matches ``MainPID`` is often transient while the new gateway
    is still starting (runtime heartbeats refresh ``pid`` before ``gateway_state`` advances).
    Fail on it only when the unit has reached a terminal state or the main process has exited;
    ``startup_failed`` always fails fast.
    """
    gateway = str(state.get("gateway_state") or "missing")
    if not written_after(state.get("updated_at"), since):
        return None, f"{gateway} (not written since the restart)"
    pid = state_pid(state)
    if main_pid is not None and pid != main_pid:
        return None, f"{gateway} from pid {pid}, not the unit's main pid {main_pid or 'none'}"
    if gateway in SERVING_GATEWAY_STATES:
        return True, gateway
    if gateway == "startup_failed":
        return False, gateway
    if gateway == "stopped" and main_pid is not None:
        if main_pid <= 0:
            return None, f"{gateway} (no main process yet)"
        active = (unit_active or "").strip()
        if not active or active in _TERMINAL_UNIT_STATES:
            return False, gateway
        if active == "active" and not process_alive_fn(main_pid):
            return False, gateway
        return None, f"{gateway} (transient while the unit is still starting)"
    return None, gateway


def gateway_settle(
    gateways: dict[str, Expectation],
    *,
    timeout_s: float | SettleTimeout,
    interval_s: float,
    main_pid_fn: MainPid = lambda item: None,
    unit_active_fn: UnitActive = lambda item: "active",
    process_alive_fn: ProcessAlive = _process_alive,
    clock_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Settle:
    """Wait after a gateway unit (keyed by unit name) until the new process reports
    ``running`` or ``degraded`` (see ``settle_verdict``).

    ``startup_failed`` and a terminal ``stopped`` (unit failed/inactive or main process gone)
    end the wait early as a failure. Adapters and ports are left to the stage verify.
    """

    def _timeout(item: Restart) -> float:
        return timeout_s(item) if callable(timeout_s) else timeout_s

    def settle(item: Restart, since: float) -> str | None:
        exp = gateways.get(item.unit)
        if exp is None:
            return None
        started = clock_fn()
        limit = _timeout(item)
        while True:
            # Query MainPID before reading gateway_state.json so side channels (tests, agents)
            # can publish the new process's first status once systemd names a main process.
            main = main_pid_fn(item)
            ok, detail = settle_verdict(
                read_state(exp.home),
                since,
                main,
                unit_active=unit_active_fn(item),
                process_alive_fn=process_alive_fn,
            )
            if ok:
                return None
            if ok is False:
                return f"{exp.profile}: gateway {detail} after {item.action} {item.unit}"
            if clock_fn() - started >= limit:
                return f"{exp.profile}: gateway not serving {limit:.0f}s after {item.action} " \
                       f"{item.unit} ({detail})"
            sleep_fn(interval_s)

    return settle


def rollback_restarts(manifest: dict) -> list[Restart]:
    """What a rollback restarts: the units the rollout restarted, each with the verb it used.

    The rollout only restarts units that were active and not oneshot, so nothing that was
    stopped before the cutover is started here. A record without a verb (an older manifest)
    gets ``try-restart``; a template is never restarted; no record means nothing restarted.
    """
    return [Restart(str(item["unit"]), bool(item.get("user")), str(item.get("action") or TRY_RESTART))
            for item in manifest.get("restarted") or [] if not is_template(str(item["unit"]))]

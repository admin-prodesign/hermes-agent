"""daemon-reload, then restart the rewritten units in stages, verifying each stage.

Without ``--canary`` there is one stage: every rewritten unit, then every profile is
verified. With it, each profile's gateway unit is its own stage in canary order (the
top-level profile, PD Neo, first) and the other units (dashboard, approval and review
units) go with the last stage; a stage that fails verification stops the rollout so
later profiles never restart onto the new release. Units whose only change was
``HERMES_RUNTIME_SHA`` get ``try-restart``: one that is not running (a oneshot) is not
started by a deploy. Each unit is recorded in the manifest as restarted before its
restart, so a rollback restarts exactly those.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from scripts.deploy.nemo.layout import canary_order, gateway_unit_name
from scripts.deploy.nemo.manifest import read_manifest, write_manifest
from scripts.deploy.nemo.units import RESTART

Systemctl = Callable[[list[str]], int]


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
    for item in restarts:
        record = {"unit": item.unit, "user": item.user}
        if record not in done:
            done.append(record)
    write_manifest(manifest, {"restarted": done})


def restart(restarts: list[Restart], run: Systemctl) -> list[str]:
    return [f"systemctl {item.action} {item.unit} failed" for item in restarts
            if run([*_scope(item.user), item.action, item.unit]) != 0]


def rollback_restarts(manifest: dict) -> list[Restart]:
    """What a rollback restarts: the units a rollout restarted, else every rewritten unit."""
    restarted = manifest.get("restarted")
    if restarted is not None:
        return [Restart(str(item["unit"]), bool(item.get("user")), RESTART) for item in restarted]
    return restarts_from(list(manifest.get("units") or []))

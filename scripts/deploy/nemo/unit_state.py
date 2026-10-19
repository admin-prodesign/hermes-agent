"""Which rewritten units a deploy may restart: concrete, active, and not oneshot.

A template unit (``name@.service``) has no process of its own; ``systemctl restart`` refuses
it, so it is replaced by its active instances (``name@x.service``). A unit that is not active
is never started by a deploy or a rollback, and neither is a oneshot: restarting one runs it
again (a kanban bridge, a scanner, an ``OnFailure=`` alert). Either picks up its rewritten
file the next time systemd starts it.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace
from typing import Callable

from scripts.deploy.nemo.rollout import Restart
from scripts.deploy.nemo.units import is_template

Capture = Callable[[list[str]], "str | None"]


@dataclass(frozen=True)
class UnitState:
    active: bool
    oneshot: bool


def systemctl_output(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(["systemctl", *args], timeout=30, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout if completed.returncode == 0 else None


def _scope(user: bool) -> list[str]:
    return ["--user"] if user else []


def unit_state(unit: str, user: bool, capture: Capture) -> UnitState:
    """``ActiveState`` and ``Type``; a unit systemd cannot describe counts as inactive."""
    text = capture([*_scope(user), "show", "-p", "ActiveState", "-p", "Type", unit]) or ""
    props = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    return UnitState(props.get("ActiveState") == "active", props.get("Type") == "oneshot")


def active_instances(template: str, user: bool, capture: Capture) -> list[str]:
    prefix = template.split("@", 1)[0] + "@"
    text = capture([*_scope(user), "list-units", "--plain", "--no-legend", "--no-pager", "--state=active",
                    template.replace("@.", "@*.", 1)]) or ""
    names = [line.split()[0] for line in text.splitlines() if line.split()]
    return [name for name in names if name.startswith(prefix) and not is_template(name)]


def concrete_restarts(items: list[Restart], capture: Capture) -> tuple[list[Restart], list[str]]:
    """``(restartable, skipped)``: a template becomes its active instances (same verb); inactive
    units and oneshots are dropped, each with its reason in ``skipped``."""
    kept: list[Restart] = []
    skipped: list[str] = []
    for item in items:
        names = [item.unit]
        if is_template(item.unit):
            names = active_instances(item.unit, item.user, capture)
            if not names:
                skipped.append(f"{item.unit}: template with no active instance")
                continue
        for name in names:
            state = unit_state(name, item.user, capture)
            if state.oneshot:
                skipped.append(f"{name}: oneshot, not started by a deploy")
            elif not state.active:
                skipped.append(f"{name}: not active, left stopped")
            else:
                kept.append(replace(item, unit=name))
    return kept, skipped

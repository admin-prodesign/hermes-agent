"""Autodeploy timer/path, refused list, last status, and drift unit."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from scripts.deploy.nemo.watchdogs.common import Finding, hermes_home, run_check, run_cmd

NAME = "autodeploy"
POLL_TIMER = "hermes-deploy-poll.timer"
WORKER_PATH = "hermes-deploy.path"
DRIFT = "hermes-deploy-drift.service"
Lifecycle = Callable[[str], tuple[bool | None, bool | None]]
Failed = Callable[[str], bool]


def _scope_args() -> list[str]:
    scope = os.environ.get("NEMO_WATCH_DEPLOY_SCOPE", "user")
    return ["--user"] if scope != "system" else []


def unit_lifecycle(unit: str, runner=None) -> tuple[bool | None, bool | None]:
    run = runner or run_cmd
    extra = _scope_args()
    enabled_proc = run(["systemctl", *extra, "is-enabled", unit], timeout=10)
    enabled_code = getattr(enabled_proc, "returncode", 1)
    if enabled_code == 0:
        enabled = True
    elif enabled_code == 1:
        enabled = False
    else:
        return None, None
    active_proc = run(["systemctl", *extra, "is-active", unit], timeout=10)
    active = getattr(active_proc, "returncode", 1) == 0
    return enabled, active


def unit_is_failed(unit: str, runner=None) -> bool:
    run = runner or run_cmd
    extra = _scope_args()
    proc = run(["systemctl", *extra, "is-failed", unit], timeout=10)
    return getattr(proc, "returncode", 1) == 0


def watch_units(
    *,
    lifecycle: Lifecycle | None = None,
    units: tuple[str, ...] = (POLL_TIMER, WORKER_PATH),
) -> list[Finding]:
    probe = lifecycle or unit_lifecycle
    findings: list[Finding] = []
    for unit in units:
        enabled, active = probe(unit)
        if enabled is True and active is True:
            continue
        state = "missing" if enabled is None else "disabled" if not enabled else "inactive"
        findings.append(
            Finding(
                f"deploy-unit:{unit}",
                "crit",
                "autodeploy unit is not enabled and active",
                {"unit": unit, "state": state},
            )
        )
    return findings


def refused_nonempty(home: Path) -> list[Finding]:
    path = home / "deploy" / "refused.jsonl"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return []
    count = sum(1 for line in text.splitlines() if line.strip())
    if count <= 0:
        return []
    return [
        Finding(
            "deploy:refused",
            "warn",
            "deploy refused list is not empty",
            {"count": count},
        )
    ]


def status_failed(home: Path) -> list[Finding]:
    path = home / "deploy" / "status.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict) or data.get("result") != "failed":
        return []
    return [
        Finding(
            "deploy:status",
            "crit",
            "last deploy result is failed",
            {"result": "failed"},
        )
    ]


def drift_failed(*, failed: Failed | None = None) -> list[Finding]:
    probe = failed or unit_is_failed
    if not probe(DRIFT):
        return []
    return [
        Finding(
            "deploy:drift",
            "crit",
            "hermes-deploy-drift.service failed",
            {"unit": DRIFT},
        )
    ]


def collect(
    *,
    home: Path | None = None,
    lifecycle: Lifecycle | None = None,
    failed: Failed | None = None,
) -> list[Finding]:
    root = home or hermes_home()
    return [
        *watch_units(lifecycle=lifecycle),
        *refused_nonempty(root),
        *status_failed(root),
        *drift_failed(failed=failed),
    ]


def main() -> int:
    return run_check(NAME, collect)


if __name__ == "__main__":
    raise SystemExit(main())

"""The ``rollout`` and ``restart`` subcommands: staged restart after a cutover, and the
restart plus verify after a rollback.

``rollout`` records how it verified (home, profiles, gateway units, expectations, timings)
in the manifest, so ``rollback.sh --manifest`` alone can restart the same units with the
same verbs, one at a time, and run the same verify (fresh ``running`` gateway, adapters
connected, ports bound). A rollback whose gateways do not come back exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from scripts.deploy.nemo.adapter_gate import ADAPTERS_FILE
from scripts.deploy.nemo.health_targets import load_deploy_section
from scripts.deploy.nemo.layout import (
    DEFAULT_HEALTH_INTERVAL_S, DEFAULT_HEALTH_TIMEOUT_S, DEFAULT_PROFILES, DEFAULT_RESTART_DELAY_S,
    gateway_unit_name, pairs, resolve_hermes_home,
)
from scripts.deploy.nemo.manifest import read_manifest, write_manifest
from scripts.deploy.nemo.rollout import (
    Restart, daemon_reload, gateway_settle, mark_restarted, plan_stages, restart, restarts_from,
    rollback_restarts, systemctl,
)
from scripts.deploy.nemo.unit_state import concrete_restarts, systemctl_output
from scripts.deploy.nemo.verify import DEFAULT_PORT_HOST, Expectation, expectations, poll_until_verified

ROLLOUT_KEY = "rollout"


@dataclass(frozen=True)
class Plan:
    profiles: tuple[str, ...]
    overrides: dict[str, str]
    exps: dict[str, Expectation]
    timeout: float
    interval: float
    port_host: str
    delay: float
    skip_verify: bool

    def gateways(self) -> dict[str, Expectation]:
        return {gateway_unit_name(name, self.overrides): exp for name, exp in self.exps.items()}

    def settle(self):
        return gateway_settle(self.gateways(), timeout_s=self.timeout, interval_s=self.interval)


def _restart_delay(explicit: float | None, home: Path) -> float:
    if explicit is not None:
        return max(0.0, explicit)
    try:
        return max(0.0, float(load_deploy_section(home, "cutover").get("restart_delay_s", DEFAULT_RESTART_DELAY_S)))
    except (TypeError, ValueError):
        return DEFAULT_RESTART_DELAY_S


def _plan(settings: dict, manifest: Path, delay: float | None) -> Plan:
    home = resolve_hermes_home(Path(settings["hermes_home"]) if settings.get("hermes_home") else None)
    profiles = tuple(settings.get("profiles") or ()) or DEFAULT_PROFILES
    overrides = {key: values[-1] for key, values in pairs(settings.get("gateway_units")).items()}
    gate_file = manifest.parent / ADAPTERS_FILE
    gate = json.loads(gate_file.read_text(encoding="utf-8-sig")) if gate_file.is_file() else {}
    exps = expectations(home, profiles, verify_config=load_deploy_section(home, "verify"),
                        platforms=pairs(settings.get("expect")), ports=pairs(settings.get("expect_port")),
                        gate=gate)
    return Plan(profiles, overrides, {exp.profile: exp for exp in exps},
                float(settings.get("timeout", DEFAULT_HEALTH_TIMEOUT_S)),
                float(settings.get("interval", DEFAULT_HEALTH_INTERVAL_S)),
                str(settings.get("port_host") or DEFAULT_PORT_HOST),
                _restart_delay(delay if delay is not None else settings.get("restart_delay"), home),
                bool(settings.get("skip_verify")))


def _print_checks(checks) -> None:
    for item in checks:
        print(f"{'ok' if item.ok else 'fail'}\t{item.name}\t{item.detail}")


def _verify(plan: Plan, profiles: tuple[str, ...], restarted: list[Restart], since: float):
    """Verify the profiles whose gateway was restarted; the rest are reported, not checked."""
    units = {item.unit for item in restarted}
    chosen = []
    for profile in profiles:
        if gateway_unit_name(profile, plan.overrides) in units:
            chosen.append(plan.exps[profile])
        else:
            print(f"{profile}: gateway unit was not restarted; not verified")
    ok, checks = poll_until_verified(
        chosen, since, timeout_s=plan.timeout, interval_s=plan.interval,
        clock_fn=time.monotonic, sleep_fn=time.sleep, host=plan.port_host,
    )
    _print_checks(checks)
    return ok, checks


def _run_stage(plan: Plan, manifest: Path, stage) -> bool:
    since = time.time()
    mark_restarted(manifest, stage.restarts)
    failures = restart(stage.restarts, systemctl, delay_s=plan.delay, settle=plan.settle(),
                       stop_on_failure=True)
    for failure in failures:
        print(failure, file=sys.stderr)
    if failures:
        return False
    if plan.skip_verify:
        return True
    return _verify(plan, stage.profiles, stage.restarts, since)[0]


def cmd_rollout(args: argparse.Namespace) -> int:
    manifest = read_manifest(args.manifest)
    units = list(manifest.get("units") or [])
    settings = {
        "hermes_home": str(resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)),
        "profiles": list(args.profiles or ()), "gateway_units": list(args.gateway_units),
        "expect": list(args.expect), "expect_port": list(args.expect_port), "port_host": args.port_host,
        "timeout": args.timeout, "interval": args.interval, "skip_verify": bool(args.skip_verify),
    }
    try:
        plan = _plan(settings, args.manifest, args.restart_delay)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_manifest(args.manifest, {ROLLOUT_KEY: {**settings, "restart_delay": plan.delay}})
    failures = daemon_reload(units, systemctl)
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    restarts, skipped = concrete_restarts(restarts_from(units), systemctl_output)
    for line in skipped:
        print(f"skip {line}")
    stages = plan_stages(restarts, plan.profiles, canary=args.canary, overrides=plan.overrides)
    for index, stage in enumerate(stages, 1):
        names = ", ".join(f"{item.action} {item.unit}" for item in stage.restarts) or "nothing"
        print(f"stage {index}/{len(stages)} ({', '.join(stage.profiles) or 'other units'}): {names}")
        if not _run_stage(plan, args.manifest, stage):
            print(f"stage {index} failed; later stages were not restarted", file=sys.stderr)
            return 1
    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    """After ``rollback``: restart what the rollout restarted, with its verbs, then verify."""
    manifest = read_manifest(args.manifest)
    units = list(manifest.get("units") or [])
    settings = dict(manifest.get(ROLLOUT_KEY) or {})
    if args.skip_verify:
        settings["skip_verify"] = True
    try:
        plan = _plan(settings, args.manifest, args.restart_delay)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    failures = daemon_reload(units, systemctl)
    restarts = rollback_restarts(manifest)
    if not restarts:
        print("rollback: the cutover restarted no unit; nothing to restart")
    since = time.time()
    failures += restart(restarts, systemctl, delay_s=plan.delay, settle=plan.settle())
    for failure in failures:
        print(failure, file=sys.stderr)
    failed_checks: list[str] = []
    if restarts and not plan.skip_verify:
        _, checks = _verify(plan, plan.profiles, restarts, since)
        failed_checks = [f"{item.name} ({item.detail})" for item in checks if not item.ok]
    if failures or failed_checks:
        print("rollback FAILED to bring the previous release back cleanly:", file=sys.stderr)
        for line in failures + [f"verify: {item}" for item in failed_checks]:
            print(f"  {line}", file=sys.stderr)
        return 1
    names = ", ".join(f"{item.action} {item.unit}" for item in restarts) or "nothing"
    print(f"rollback restarted: {names}")
    return 0

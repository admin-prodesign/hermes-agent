#!/usr/bin/env python3
"""Hermes autonomous supervisor state + Neo Watch push on alert fingerprint changes.

Critical and needs-input (non-repairable) findings POST to the Neo automation webhook
when ``notified_fingerprint`` advances. A 45-minute dead-man fires one Mattermost
escalation through ``pd_one_notification_router`` when Neo never acks.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.deploy.nemo import neo_watch_webhook as neo
from scripts.deploy.nemo.layout import resolve_hermes_home
from scripts.deploy.nemo.pdone_alert_watchdog import _finding_alertable, redact_value

LOG = logging.getLogger(__name__)

STATE_REL = Path("state") / "hermes_autonomous_supervisor" / "state.json"
NEO_PUSH_REL = Path("state") / "hermes_autonomous_supervisor" / "neo_push.json"
DEADMAN_SECONDS = 45 * 60
PROFILE = "pdone"
HOST_ENV = "NEO_WATCH_HOST"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def state_path(home: Path) -> Path:
    return home / STATE_REL


def neo_push_path(home: Path) -> Path:
    return home / NEO_PUSH_REL


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return dict(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        LOG.exception("corrupt state %s; resetting", path)
        return dict(default)
    return data if isinstance(data, dict) else dict(default)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def alertable_findings(findings: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in findings:
        if isinstance(raw, dict) and _finding_alertable(raw):
            out.append(raw)
    return out


def compute_fingerprint(findings: list[Any]) -> str:
    return neo.fingerprint_for_findings(list(findings), alertable_fn=_finding_alertable)


def _serialize_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw in findings:
        items.append(
            {
                "id": raw.get("id"),
                "severity": raw.get("severity"),
                "subject": raw.get("subject") or raw.get("title"),
            }
        )
    return redact_value(items)


def _router_cmd(home: Path, *args: str) -> list[str]:
    return [sys.executable, "-m", "scripts.pd_one_notification_router", *args, "--hermes-home", str(home)]


def escalate_deadman(home: Path, *, correlation: str, summary: str, dry_run: bool) -> bool:
    event = {
        "severity": "critical",
        "summary": summary,
        "correlation_key": correlation,
        "source": "hermes_autonomous_supervisor",
    }
    cmd = _router_cmd(
        home,
        "send",
        "--route",
        "pd_one_failure_escalations",
        "--json",
        json.dumps(event, separators=(",", ":")),
    )
    if dry_run:
        print(json.dumps({"deadman_escalation": event, "cmd": cmd}, indent=2))
        return True
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOG.error("dead-man escalation failed: %s", exc)
        return False
    if proc.returncode != 0:
        LOG.error(
            "dead-man escalation exit %s: %s",
            proc.returncode,
            (proc.stderr or proc.stdout or "").strip(),
        )
        return False
    return True


def is_correlation_acked(home: Path, correlation: str) -> bool:
    cmd = _router_cmd(home, "is-acked", "--correlation-key", correlation)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    try:
        body = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return False
    return bool(body.get("acked"))


def maybe_notify_neo(
    home: Path,
    state: dict[str, Any],
    *,
    host: str | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
    post_fn: Callable[..., bool] | None = None,
) -> dict[str, Any]:
    """Update ``notified_fingerprint`` and push Neo alerts when the fingerprint changes."""
    now = now or _utc_now()
    host = host or os.environ.get(HOST_ENV, socket.gethostname())
    findings = state.get("findings") if isinstance(state.get("findings"), list) else []
    alertable = alertable_findings(findings)
    fingerprint = compute_fingerprint(findings)
    state["fingerprint"] = fingerprint

    push_state = load_json(neo_push_path(home), {"pushed": {}, "deadman": {}})
    pushed: dict[str, Any] = push_state.setdefault("pushed", {})
    deadman: dict[str, Any] = push_state.setdefault("deadman", {})

    notified = str(state.get("notified_fingerprint") or "")
    correlation = neo.correlation_key(fingerprint)

    if fingerprint and fingerprint != notified:
        last_pushed = str(pushed.get("fingerprint") or "")
        if last_pushed != fingerprint:
            if neo.resolve_webhook_url() is None and not dry_run:
                neo.log_missing_webhook_once()
                save_json(neo_push_path(home), push_state)
                return state
            payload = neo.build_supervisor_alert_payload(
                fingerprint=fingerprint,
                findings=_serialize_findings(alertable),
                severity=neo.max_severity(alertable, alertable_fn=_finding_alertable),
                host=host,
                profile=PROFILE,
                first_seen=str(pushed.get("first_seen") or neo.iso_now(now)),
                last_seen=neo.iso_now(now),
            )
            poster = post_fn or neo.post_json_webhook
            ok = poster(payload, dry_run=dry_run)
            if ok:
                pushed["fingerprint"] = fingerprint
                pushed["first_seen"] = pushed.get("first_seen") or neo.iso_now(now)
                pushed["last_post_at"] = neo.iso_now(now)
                pushed["correlation_key"] = correlation
                state["notified_fingerprint"] = fingerprint
                deadman.pop("sent_at", None)
                deadman["correlation_key"] = correlation
                deadman["started_at"] = deadman.get("started_at") or neo.iso_now(now)
        else:
            state["notified_fingerprint"] = fingerprint

    if fingerprint and deadman.get("correlation_key") == correlation and not deadman.get("sent_at"):
        if is_correlation_acked(home, correlation):
            deadman["acked_at"] = neo.iso_now(now)
        else:
            started = deadman.get("started_at") or pushed.get("last_post_at")
            if started:
                try:
                    start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
                except ValueError:
                    start_dt = now
                if (now - start_dt).total_seconds() >= DEADMAN_SECONDS:
                    summary = f"Neo Watch dead-man: unacked {correlation}"
                    if escalate_deadman(home, correlation=correlation, summary=summary, dry_run=dry_run):
                        deadman["sent_at"] = neo.iso_now(now)

    if not fingerprint:
        state["notified_fingerprint"] = ""
        pushed.clear()
        deadman.clear()

    save_json(neo_push_path(home), push_state)
    return state


def persist_state(home: Path, state: dict[str, Any], **notify_kw: Any) -> None:
    state = maybe_notify_neo(home, state, **notify_kw)
    save_json(state_path(home), state)


def cmd_tick(home: Path, *, dry_run: bool) -> int:
    state = load_json(state_path(home), {"findings": [], "notified_fingerprint": ""})
    persist_state(home, state, dry_run=dry_run)
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Hermes autonomous supervisor Neo Watch hooks")
    parser.add_argument("--hermes-home", default=None, help="Hermes home (default: HERMES_HOME)")
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("tick", help="Re-read state and run Neo push / dead-man checks")
    args = parser.parse_args(argv)
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    if args.command == "tick" or args.command is None:
        return cmd_tick(home, dry_run=args.dry_run)
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

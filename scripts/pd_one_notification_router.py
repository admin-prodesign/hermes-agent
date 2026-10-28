#!/usr/bin/env python3
"""PD One notification router: Neo pre-target webhook, Mattermost hold, and ack."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.deploy.nemo import neo_watch_webhook as neo
from scripts.deploy.nemo.layout import resolve_hermes_home

LOG = logging.getLogger(__name__)

ROUTES_REL = Path("config") / "notification-routes.json"
STATE_REL = Path("state") / "pd_one_notification_router" / "state.json"
DEFAULT_HOLD_MINUTES = 10

TARGET_RE = re.compile(
    r"^(?P<kind>mattermost|webhook|email):(?P<rest>.+)$",
    re.IGNORECASE,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def routes_path(home: Path) -> Path:
    override = os.environ.get("PD_ONE_NOTIFICATION_ROUTES", "").strip()
    if override:
        return Path(override).expanduser()
    return home / ROUTES_REL


def router_state_path(home: Path) -> Path:
    return home / STATE_REL


def load_routes(home: Path) -> dict[str, Any]:
    path = routes_path(home)
    if not path.is_file():
        return {"schema_version": 1, "routes": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid notification routes {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"invalid notification routes {path}: expected object")
    return data


def load_state(home: Path) -> dict[str, Any]:
    path = router_state_path(home)
    if not path.is_file():
        return {"acked": [], "held_for_neo": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        LOG.exception("resetting corrupt router state %s", path)
        return {"acked": [], "held_for_neo": []}
    if not isinstance(data, dict):
        return {"acked": [], "held_for_neo": []}
    data.setdefault("acked", [])
    data.setdefault("held_for_neo", [])
    return data


def save_state(home: Path, state: dict[str, Any]) -> None:
    path = router_state_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = neo.iso_now()
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_target(raw: str) -> tuple[str, str]:
    text = raw.strip()
    match = TARGET_RE.fullmatch(text)
    if not match:
        raise ValueError(f"invalid target {raw!r}; expected mattermost:|webhook:|email:")
    return match.group("kind").lower(), match.group("rest").strip()


def route_def(routes_doc: dict[str, Any], name: str) -> dict[str, Any]:
    routes = routes_doc.get("routes")
    if not isinstance(routes, dict):
        raise SystemExit("notification-routes.json missing routes object")
    route = routes.get(name)
    if not isinstance(route, dict):
        raise SystemExit(f"unknown notification route {name!r}")
    return route


def hold_minutes(route: dict[str, Any]) -> int:
    raw = route.get("hold_minutes", DEFAULT_HOLD_MINUTES)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_HOLD_MINUTES
    return max(0, value)


def correlation_from_event(event: dict[str, Any]) -> str:
    explicit = str(event.get("correlation_key") or "").strip()
    if explicit:
        return explicit
    fp = str(event.get("fingerprint") or event.get("idempotency_key") or "").strip()
    if fp:
        return neo.correlation_key(fp)
    summary = str(event.get("summary") or event.get("message") or "event")
    digest = neo.fingerprint_for_findings([{"subject": summary}], alertable_fn=lambda _: True)
    return neo.correlation_key(digest)


def is_acked(state: dict[str, Any], correlation: str) -> bool:
    acked = state.get("acked")
    if not isinstance(acked, list):
        return False
    return correlation in acked


def deliver_mattermost(home: Path, target: str, message: str, *, dry_run: bool) -> bool:
    kind, rest = parse_target(f"mattermost:{target}" if ":" not in target else target)
    if kind != "mattermost":
        raise ValueError("expected mattermost target")
    to_ref = rest if rest.startswith("mattermost:") else f"mattermost:{rest}"
    if dry_run:
        print(json.dumps({"deliver": "mattermost", "to": to_ref, "message": message}, indent=2))
        return True
    hermes = os.environ.get("HERMES_BIN", "hermes").strip() or "hermes"
    cmd = [hermes, "--profile", "pdone", "send", "--to", to_ref, message]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOG.error("mattermost send failed: %s", exc)
        return False
    if proc.returncode != 0:
        LOG.error("mattermost send exit %s: %s", proc.returncode, (proc.stderr or proc.stdout or "").strip())
        return False
    return True


def deliver_webhook(target: str, event: dict[str, Any], *, dry_run: bool) -> bool:
    kind, rest = parse_target(f"webhook:{target}" if ":" not in target else target)
    if kind != "webhook":
        raise ValueError("expected webhook target")
    url = rest
    if url == "neo" or url == "default":
        url = None
    payload = dict(event)
    payload.setdefault("schema", neo.SCHEMA_SUPERVISOR)
    payload.setdefault("sent_at", neo.iso_now())
    return neo.post_json_webhook(payload, dry_run=dry_run, url=url)


def deliver_target(home: Path, target: str, event: dict[str, Any], *, dry_run: bool) -> bool:
    kind, rest = parse_target(target if ":" in target else f"mattermost:{target}")
    if kind == "webhook":
        return deliver_webhook(rest, event, dry_run=dry_run)
    if kind == "mattermost":
        message = str(event.get("summary") or event.get("message") or json.dumps(event, ensure_ascii=False))
        return deliver_mattermost(home, rest, message, dry_run=dry_run)
    if kind == "email":
        LOG.warning("email targets not implemented; skipping %s", target)
        return False
    return False


def flush_held(home: Path, state: dict[str, Any] | None = None, *, dry_run: bool, now: datetime | None = None) -> int:
    now = now or _utc_now()
    state = state if state is not None else load_state(home)
    routes_doc = load_routes(home)
    released = 0
    held = state.get("held_for_neo")
    if not isinstance(held, list):
        return 0
    keep: list[dict[str, Any]] = []
    for entry in held:
        if not isinstance(entry, dict):
            continue
        correlation = str(entry.get("correlation_key") or "")
        if is_acked(state, correlation):
            continue
        hold_until_raw = str(entry.get("hold_until") or "")
        try:
            hold_until = datetime.fromisoformat(hold_until_raw.replace("Z", "+00:00"))
        except ValueError:
            hold_until = now
        if now < hold_until:
            keep.append(entry)
            continue
        route_name = str(entry.get("route") or "")
        try:
            route = route_def(routes_doc, route_name)
        except SystemExit:
            keep.append(entry)
            continue
        targets = route.get("targets") or route.get("primary_targets")
        if not isinstance(targets, list) or not targets:
            keep.append(entry)
            continue
        event = entry.get("event") if isinstance(entry.get("event"), dict) else {}
        if deliver_target(home, str(targets[0]), event, dry_run=dry_run):
            released += 1
        else:
            keep.append(entry)
    state["held_for_neo"] = keep
    save_state(home, state)
    return released


def send_route(
    home: Path,
    route_name: str,
    event: dict[str, Any],
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or _utc_now()
    state = load_state(home)
    flush_held(home, state, dry_run=dry_run, now=now)
    state = load_state(home)

    routes_doc = load_routes(home)
    route = route_def(routes_doc, route_name)
    correlation = correlation_from_event(event)
    event = {**event, "correlation_key": correlation}

    if is_acked(state, correlation):
        return {"status": "suppressed", "reason": "acked", "correlation_key": correlation}

    pre_targets = route.get("pre_targets")
    if isinstance(pre_targets, list) and pre_targets:
        for target in pre_targets:
            if not isinstance(target, str):
                continue
            deliver_target(home, target, event, dry_run=dry_run)
        hold = hold_minutes(route)
        hold_until = now + timedelta(minutes=hold)
        held_entry = {
            "route": route_name,
            "correlation_key": correlation,
            "hold_until": neo.iso_now(hold_until),
            "event": event,
        }
        held = state.setdefault("held_for_neo", [])
        if isinstance(held, list):
            held = [item for item in held if not (isinstance(item, dict) and item.get("correlation_key") == correlation)]
            held.append(held_entry)
            state["held_for_neo"] = held
        save_state(home, state)
        return {"status": "held", "correlation_key": correlation, "hold_until": held_entry["hold_until"]}

    targets = route.get("targets") or route.get("primary_targets")
    if not isinstance(targets, list) or not targets:
        raise SystemExit(f"route {route_name!r} has no targets")
    ok = deliver_target(home, str(targets[0]), event, dry_run=dry_run)
    return {"status": "delivered" if ok else "failed", "correlation_key": correlation, "target": targets[0]}


def cmd_ack(home: Path, correlation: str) -> int:
    state = load_state(home)
    acked = state.setdefault("acked", [])
    if not isinstance(acked, list):
        acked = []
        state["acked"] = acked
    if correlation not in acked:
        acked.append(correlation)
    held = state.get("held_for_neo")
    if isinstance(held, list):
        state["held_for_neo"] = [
            item for item in held if not (isinstance(item, dict) and item.get("correlation_key") == correlation)
        ]
    save_state(home, state)
    print(json.dumps({"acked": True, "correlation_key": correlation}))
    return 0


def cmd_is_acked(home: Path, correlation: str) -> int:
    state = load_state(home)
    print(json.dumps({"acked": is_acked(state, correlation), "correlation_key": correlation}))
    return 0


def cmd_flush(home: Path, *, dry_run: bool) -> int:
    state = load_state(home)
    count = flush_held(home, state, dry_run=dry_run)
    print(json.dumps({"released": count}))
    return 0


def cmd_send(home: Path, route_name: str, event: dict[str, Any], *, dry_run: bool) -> int:
    result = send_route(home, route_name, event, dry_run=dry_run)
    print(json.dumps(result))
    return 0 if result.get("status") != "failed" else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="PD One notification router")
    parser.add_argument("--hermes-home", default=None)
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    send = sub.add_parser("send", help="Send through a named route")
    send.add_argument("--route", required=True)
    send.add_argument("--json", required=True, help="Event JSON object")

    ack = sub.add_parser("ack", help="Acknowledge a correlation key (suppress Mattermost release)")
    ack.add_argument("--correlation-key", required=True)

    is_acked = sub.add_parser("is-acked", help="Return whether a correlation key was acked")
    is_acked.add_argument("--correlation-key", required=True)

    sub.add_parser("flush", help="Release held Mattermost messages whose hold expired")

    args = parser.parse_args(argv)
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)

    if args.command == "send":
        try:
            event = json.loads(args.json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid --json: {exc}") from exc
        if not isinstance(event, dict):
            raise SystemExit("--json must be an object")
        return cmd_send(home, args.route, event, dry_run=args.dry_run)
    if args.command == "ack":
        return cmd_ack(home, args.correlation_key)
    if args.command == "is-acked":
        return cmd_is_acked(home, args.correlation_key)
    if args.command == "flush":
        return cmd_flush(home, dry_run=args.dry_run)
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

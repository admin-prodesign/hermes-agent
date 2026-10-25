"""PD One alert watchdog for nemo: neo-watch.alert.v1 webhook posts.

Runs on a timer (no LLM). Reads supervisor findings, cron failures, and failed
``hermes-*`` user units; dedupes and reminds on a 6h cadence; resolves after three
clean polls. Dead-man Mattermost DMs use ``NEO_WATCH_FALLBACK_TARGET`` when a
webhook post fails or an incident stays unacked for 45 minutes.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import logging
import os
import re
import socket
import ssl
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from scripts.deploy.nemo.layout import resolve_hermes_home

SCHEMA = "neo-watch.alert.v1"
WATCHDOG_NAME = "pdone-alert-watchdog"
PROFILE = "pdone"
MAX_PAYLOAD_BYTES = 4000
MAX_ITEMS = 10
REMIND_SECONDS = 6 * 3600
RESOLVE_CLEAN_RUNS = 3
DEADMAN_SECONDS = 45 * 60
FALLBACK_RATE_SECONDS = 10 * 60

DEFAULT_SECRETS_REL = Path("secrets") / "neo-watch-webhook.env"
DEFAULT_STATE_REL = Path("state") / "neo-watch-watchdogs"
SUPERVISOR_REL = Path("state") / "hermes_autonomous_supervisor" / "state.json"

_TOKEN_PATTERNS = (
    re.compile(r"(?i)\b(bearer\s+)[a-z0-9._\-+/=]{8,}"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*['\"]?([^\s'\",]{8,})"),
    re.compile(r"\b(sk-[a-zA-Z0-9]{10,})\b"),
    re.compile(r"\b(ghp_[a-zA-Z0-9]{20,})\b"),
    re.compile(r"\b(xox[baprs]-[a-zA-Z0-9\-]{10,})\b"),
)

LOG = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _utc_now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def secrets_path(home: Path) -> Path:
    override = os.environ.get("NEO_WATCH_SECRETS_FILE", "").strip()
    return Path(override).expanduser() if override else home / DEFAULT_SECRETS_REL


def state_dir(home: Path) -> Path:
    override = os.environ.get("NEO_WATCH_STATE_DIR", "").strip()
    return Path(override).expanduser() if override else home / DEFAULT_STATE_REL


def supervisor_state_path(home: Path) -> Path:
    override = os.environ.get("NEO_WATCH_SUPERVISOR_STATE", "").strip()
    return Path(override).expanduser() if override else home / SUPERVISOR_REL


def cron_job_paths(home: Path) -> list[Path]:
    explicit = os.environ.get("NEO_WATCH_CRON_JOBS", "").strip()
    if explicit:
        return [Path(item).expanduser() for item in explicit.split(os.pathsep) if item.strip()]
    return [
        home / "cron" / "jobs.json",
        home / "profiles" / PROFILE / "cron" / "jobs.json",
    ]


def _secrets_mode_ok(path: Path) -> bool:
    if not path.is_file():
        return False
    mode = path.stat().st_mode
    return not (mode & (stat.S_IRGRP | stat.S_IROTH | stat.S_IWGRP | stat.S_IWOTH))


def load_secrets(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SystemExit(f"secrets file missing: {path}")
    if not _secrets_mode_ok(path):
        raise SystemExit(f"secrets file must be mode 600 or tighter (no group/world access): {path}")
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        data[key.strip()] = value
    for key, value in data.items():
        if value and key not in os.environ:
            os.environ[key] = value
    return data


def redact_string(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern in _TOKEN_PATTERNS:
        out = pattern.sub("«redacted»", out)
    return out


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, dict):
        return {str(k): redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


@dataclass(frozen=True)
class LiveIncident:
    key: str
    title: str
    severity: str
    items: tuple[dict[str, Any], ...] = ()


def _finding_key(finding: dict[str, Any]) -> str:
    fid = str(finding.get("id") or "").strip()
    if fid:
        return f"finding:{fid}"
    subject = str(finding.get("subject") or finding.get("title") or "").strip()
    digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:16]
    return f"finding:{digest}"


def _finding_alertable(finding: dict[str, Any]) -> bool:
    severity = str(finding.get("severity") or "").strip().lower()
    subject = str(finding.get("subject") or finding.get("title") or "")
    if severity == "critical":
        return True
    return "INPUT NEEDED" in subject.upper()


def _as_record_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        items: list[dict[str, Any]] = []
        for key, item in value.items():
            if not isinstance(item, dict):
                continue
            record = dict(item)
            if not str(record.get("id") or "").strip():
                record["id"] = str(key)
            items.append(record)
        return items
    return []


def collect_supervisor_findings(path: Path) -> list[LiveIncident]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        LOG.exception("failed to read supervisor state %s", path)
        return []
    findings = payload.get("findings") if isinstance(payload, dict) else None
    raw_findings = _as_record_list(findings)
    incidents: list[LiveIncident] = []
    for raw in raw_findings:
        if not isinstance(raw, dict) or not _finding_alertable(raw):
            continue
        key = _finding_key(raw)
        subject = str(raw.get("subject") or raw.get("title") or key).strip()
        severity = str(raw.get("severity") or "warning").strip().lower() or "warning"
        items = (
            {
                "kind": "finding",
                "id": raw.get("id"),
                "severity": severity,
                "subject": subject,
            },
        )
        incidents.append(LiveIncident(key=key, title=subject, severity=severity, items=items))
    return incidents


def _cron_failed(job: dict[str, Any]) -> bool:
    if not job.get("enabled", True):
        return False
    state = str(job.get("state") or "").strip().lower()
    if state == "paused" or job.get("paused_at"):
        return False
    status = str(job.get("last_status") or "").strip().lower()
    return status in {"error", "failed", "delivery_failed"}


def collect_cron_failures(paths: list[Path]) -> list[LiveIncident]:
    incidents: list[LiveIncident] = []
    seen: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            LOG.exception("failed to read cron jobs %s", path)
            continue
        if isinstance(payload, dict):
            jobs = payload.get("jobs", payload)
        else:
            jobs = payload
        for job in _as_record_list(jobs):
            if not _cron_failed(job):
                continue
            job_id = str(job.get("id") or "").strip()
            if not job_id or job_id in seen:
                continue
            seen.add(job_id)
            name = str(job.get("name") or job_id).strip()
            err = str(job.get("last_error") or job.get("last_delivery_error") or job.get("last_status") or "error")
            key = f"cron:{job_id}"
            title = f"Cron job failed: {name}"
            items = (
                {
                    "kind": "cron",
                    "id": job_id,
                    "name": name,
                    "last_status": job.get("last_status"),
                    "error": err,
                    "path": str(path),
                },
            )
            incidents.append(LiveIncident(key=key, title=title, severity="critical", items=items))
    return incidents


def _list_failed_hermes_units(
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> list[str]:
    run = runner or (lambda argv: subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False))
    proc = run(
        [
            "systemctl",
            "--user",
            "list-units",
            "hermes-*.service",
            "--state=failed",
            "--no-legend",
            "--plain",
        ]
    )
    if proc.returncode != 0:
        LOG.warning("systemctl list-units failed: %s", (proc.stderr or proc.stdout or "").strip())
        return []
    names: list[str] = []
    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if not parts:
            continue
        unit = parts[0]
        if unit.endswith(".service") and unit.startswith("hermes-"):
            names.append(unit[: -len(".service")])
    return sorted(set(names))


def collect_failed_units(
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> list[LiveIncident]:
    incidents: list[LiveIncident] = []
    for unit in _list_failed_hermes_units(runner):
        key = f"unit:{unit}"
        title = f"systemd unit failed: {unit}"
        items = ({"kind": "unit", "unit": unit},)
        incidents.append(LiveIncident(key=key, title=title, severity="critical", items=items))
    return incidents


def collect_live_incidents(
    home: Path,
    *,
    systemctl_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, LiveIncident]:
    merged: dict[str, LiveIncident] = {}
    for group in (
        collect_supervisor_findings(supervisor_state_path(home)),
        collect_cron_failures(cron_job_paths(home)),
        collect_failed_units(systemctl_runner),
    ):
        for incident in group:
            merged[incident.key] = incident
    return merged


def _default_incident_record() -> dict[str, Any]:
    return {
        "first_seen": None,
        "first_alert": None,
        "last_alert": None,
        "count": 0,
        "active": False,
        "clean_runs": 0,
        "acked": False,
        "ack_note": "",
        "title": "",
        "severity": "warning",
        "last_fallback_at": None,
        "last_deadman_at": None,
    }


@contextmanager
def state_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"incidents": {}, "last_fallback_at": None, "updated_at": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        LOG.exception("corrupt watchdog state; resetting %s", path)
        return {"incidents": {}, "last_fallback_at": None, "updated_at": None}
    if not isinstance(data, dict):
        return {"incidents": {}, "last_fallback_at": None, "updated_at": None}
    incidents = data.get("incidents")
    if not isinstance(incidents, dict):
        incidents = {}
    return {
        "incidents": incidents,
        "last_fallback_at": data.get("last_fallback_at"),
        "updated_at": data.get("updated_at"),
    }


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _iso()
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_payload(
    incident: LiveIncident | None,
    *,
    key: str,
    title: str,
    severity: str,
    state: str,
    items: list[dict[str, Any]],
    host: str,
) -> tuple[dict[str, Any], bool]:
    truncated = len(items) > MAX_ITEMS
    clipped = items[:MAX_ITEMS]
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "host": host,
        "profile": PROFILE,
        "watchdog": WATCHDOG_NAME,
        "severity": severity,
        "state": state,
        "key": key,
        "title": title,
        "items": clipped,
        "truncated_items": truncated,
        "sent_at": _iso(),
    }
    body = redact_value(body)
    encoded = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) <= MAX_PAYLOAD_BYTES:
        return body, truncated
    # Shrink items until the payload fits.
    while clipped and len(json.dumps({**body, "items": clipped}, separators=(",", ":")).encode("utf-8")) > MAX_PAYLOAD_BYTES:
        clipped = clipped[:-1]
        body["items"] = clipped
        body["truncated_items"] = True
    if len(json.dumps(body, separators=(",", ":")).encode("utf-8")) > MAX_PAYLOAD_BYTES:
        body["items"] = []
        body["truncated_items"] = True
        body["title"] = redact_string(title[:200])
    return body, body.get("truncated_items", False)


def _ssl_context() -> ssl.SSLContext:
    paths = ssl.get_default_verify_paths()
    if paths.cafile and os.path.isfile(paths.cafile):
        return ssl.create_default_context(cafile=paths.cafile)
    if paths.capath and os.path.isdir(paths.capath):
        return ssl.create_default_context(capath=paths.capath)
    return ssl.create_default_context()


def post_webhook(payload: dict[str, Any], *, dry_run: bool) -> bool:
    if dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return True
    url = os.environ.get("NEO_WATCH_WEBHOOK_URL", "").strip()
    if not url:
        LOG.error("NEO_WATCH_WEBHOOK_URL is not set")
        return False
    header_name = os.environ.get("NEO_WATCH_WEBHOOK_KEY_HEADER", "Authorization").strip() or "Authorization"
    prefix = os.environ.get("NEO_WATCH_WEBHOOK_KEY_PREFIX", "Bearer ")
    token = os.environ.get("NEO_WATCH_WEBHOOK_KEY", "").strip()
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", header_name: f"{prefix}{token}" if token else prefix.rstrip()}
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30, context=_ssl_context()):
            return True
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        LOG.error("webhook post failed: %s", exc)
        return False


def _fallback_target() -> str:
    return os.environ.get("NEO_WATCH_FALLBACK_TARGET", "").strip()


def send_mattermost_fallback(message: str, *, dry_run: bool) -> bool:
    target = _fallback_target()
    if not target:
        LOG.warning("NEO_WATCH_FALLBACK_TARGET not configured; skipping Mattermost fallback")
        return False
    if dry_run:
        print(json.dumps({"fallback": "mattermost", "target": target, "message": message}, indent=2))
        return True
    hermes = os.environ.get("HERMES_BIN", "hermes").strip() or "hermes"
    cmd = [hermes, "--profile", PROFILE, "send", "--to", target, message]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOG.error("mattermost fallback command failed: %s", exc)
        return False
    if proc.returncode != 0:
        LOG.error("mattermost fallback exit %s: %s", proc.returncode, (proc.stderr or proc.stdout or "").strip())
        return False
    return True


def _remind_due(record: dict[str, Any], now: datetime) -> bool:
    last = _parse_iso(record.get("last_alert"))
    if last is None:
        return True
    return (now - last).total_seconds() >= REMIND_SECONDS


def _deadman_due(record: dict[str, Any], now: datetime) -> bool:
    if record.get("acked"):
        return False
    first = _parse_iso(record.get("first_alert"))
    if first is None:
        return False
    return (now - first).total_seconds() >= DEADMAN_SECONDS


def _fallback_rate_ok(state: dict[str, Any], now: datetime) -> bool:
    last = _parse_iso(state.get("last_fallback_at"))
    if last is None:
        return True
    return (now - last).total_seconds() >= FALLBACK_RATE_SECONDS


def _format_fallback_message(payload: dict[str, Any]) -> str:
    return f"[neo-watch] {payload.get('state')} {payload.get('key')}: {payload.get('title')}"


@dataclass
class RunResult:
    posted: int = 0
    resolved: int = 0
    fallbacks: int = 0


def run_watchdog(
    home: Path,
    *,
    dry_run: bool = False,
    systemctl_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    now: datetime | None = None,
) -> RunResult:
    now = now or _utc_now()
    host = os.environ.get("NEO_WATCH_HOST", socket.gethostname())
    live = collect_live_incidents(home, systemctl_runner=systemctl_runner)
    state_path = state_dir(home) / "state.json"
    lock_path = state_dir(home) / "state.json.lock"
    result = RunResult()

    with state_lock(lock_path):
        state = load_state(state_path)
        incidents: dict[str, dict[str, Any]] = state.setdefault("incidents", {})

        # Mark missing keys with clean-run streaks; resolve when streak hits threshold.
        for key, record in list(incidents.items()):
            if not record.get("active"):
                continue
            if key in live:
                record["clean_runs"] = 0
                continue
            record["clean_runs"] = int(record.get("clean_runs") or 0) + 1
            if record["clean_runs"] < RESOLVE_CLEAN_RUNS:
                continue
            record["active"] = False
            payload, _ = build_payload(
                None,
                key=key,
                title=str(record.get("title") or key),
                severity=str(record.get("severity") or "warning"),
                state="resolved",
                items=[],
                host=host,
            )
            ok = post_webhook(payload, dry_run=dry_run)
            if ok:
                result.resolved += 1
                result.posted += 1
            else:
                _maybe_fallback(state, record, payload, dry_run=dry_run, now=now, result=result)

        for key, incident in live.items():
            record = incidents.setdefault(key, _default_incident_record())
            record["title"] = incident.title
            record["severity"] = incident.severity
            if not record.get("first_seen"):
                record["first_seen"] = _iso(now)
            was_active = bool(record.get("active"))
            record["active"] = True
            record["clean_runs"] = 0

            should_fire = not was_active or _remind_due(record, now)
            if not should_fire:
                _maybe_deadman(state, record, incident, host, dry_run=dry_run, now=now, result=result)
                continue

            payload, _ = build_payload(
                incident,
                key=key,
                title=incident.title,
                severity=incident.severity,
                state="firing",
                items=list(incident.items),
                host=host,
            )
            ok = post_webhook(payload, dry_run=dry_run)
            if ok:
                result.posted += 1
                record["count"] = int(record.get("count") or 0) + 1
                if not record.get("first_alert"):
                    record["first_alert"] = _iso(now)
                record["last_alert"] = _iso(now)
            else:
                _maybe_fallback(state, record, payload, dry_run=dry_run, now=now, result=result)
            _maybe_deadman(state, record, incident, host, dry_run=dry_run, now=now, result=result)

        save_state(state_path, state)
    return result


def _maybe_deadman(
    state: dict[str, Any],
    record: dict[str, Any],
    incident: LiveIncident,
    host: str,
    *,
    dry_run: bool,
    now: datetime,
    result: RunResult,
) -> None:
    if not _deadman_due(record, now):
        return
    if record.get("last_deadman_at"):
        return
    payload, _ = build_payload(
        incident,
        key=incident.key,
        title=incident.title,
        severity=incident.severity,
        state="firing",
        items=list(incident.items),
        host=host,
    )
    if _maybe_fallback(state, record, payload, dry_run=dry_run, now=now, result=result):
        record["last_deadman_at"] = _iso(now)


def _maybe_fallback(
    state: dict[str, Any],
    record: dict[str, Any],
    payload: dict[str, Any],
    *,
    dry_run: bool,
    now: datetime,
    result: RunResult,
) -> bool:
    if not _fallback_rate_ok(state, now):
        return False
    message = _format_fallback_message(payload)
    if send_mattermost_fallback(message, dry_run=dry_run):
        state["last_fallback_at"] = _iso(now)
        record["last_fallback_at"] = _iso(now)
        result.fallbacks += 1
        return True
    return False


def cmd_ack(home: Path, key: str, note: str) -> int:
    state_path = state_dir(home) / "state.json"
    lock_path = state_dir(home) / "state.json.lock"
    with state_lock(lock_path):
        state = load_state(state_path)
        incidents: dict[str, dict[str, Any]] = state.setdefault("incidents", {})
        record = incidents.get(key)
        if record is None:
            print(f"unknown incident key: {key}", file=sys.stderr)
            return 1
        record["acked"] = True
        record["ack_note"] = note
        save_state(state_path, state)
    print(f"acked {key}")
    return 0


def _dry_run_enabled(flag: bool) -> bool:
    if flag:
        return True
    return os.environ.get("NEO_WATCH_DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="PD One neo-watch alert watchdog")
    parser.add_argument("--hermes-home", default=None, help="Hermes home (default: HERMES_HOME)")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads; do not post")
    sub = parser.add_subparsers(dest="command")

    ack = sub.add_parser("ack", help="Acknowledge an incident (dead-man suppress)")
    ack.add_argument("key", help="Incident key, e.g. cron:abc123")
    ack.add_argument("--note", default="", help="Optional ack note")

    args = parser.parse_args(argv)
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    dry_run = _dry_run_enabled(args.dry_run)

    if args.command == "ack":
        return cmd_ack(home, args.key, args.note)

    if not dry_run:
        load_secrets(secrets_path(home))

    result = run_watchdog(home, dry_run=dry_run)
    LOG.info("neo-watch done: posted=%s resolved=%s fallbacks=%s", result.posted, result.resolved, result.fallbacks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

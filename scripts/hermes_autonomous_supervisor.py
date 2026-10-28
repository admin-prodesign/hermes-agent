#!/usr/bin/env python3
"""Autonomous Hermes supervisor audit/safe-repair loop.

Scope:
- default/PD Neo profile plus PD One/pdone profile cron receipts;
- outcome contracts that catch semantic failures hidden by ok cron statuses;
- safe repair limited to registry self-registration and remediation-plan files.

This script is intentionally deterministic and aggregate-only. It must not read or
print private Yammer content, employee message bodies, raw attachment names, tokens,
or source-system data.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable

from scripts.deploy.nemo import neo_watch_webhook as neo
from scripts.deploy.nemo.layout import resolve_hermes_home
from scripts.deploy.nemo.pdone_alert_watchdog import _finding_alertable, redact_value

HERMES = Path('/home/prodesign/.hermes')
PDONE = HERMES / 'profiles/pdone'
DEFAULT_REGISTRY = HERMES / 'supervisor/automations.json'
PDONE_REGISTRY = PDONE / 'supervisor/automations.json'
REMEDIATION_DIR = HERMES / 'supervisor/remediation-plans'
SUPERVISOR_STATE = HERMES / 'state/hermes_autonomous_supervisor/state.json'
CRON_FAILURE_HOLDS = HERMES / 'state/hermes_autonomous_supervisor/cron_failure_holds.json'
GATEWAY_UNITS = {
    'pdone': 'hermes-gateway-pdone.service',
    'default': 'hermes-gateway.service',
}
# Supervisor tick is 30m. Hold first stale-receipt cluster until the next tick
# (or a recent owning-gateway restart) so drain/kill recoveries do not page Andy.
STALE_RECEIPT_CONFIRM_MIN = 30
GATEWAY_RESTART_HOLD_MIN = 45
STALE_CLUSTER_MIN_JOBS = 2
DEFAULT_CRON = HERMES / 'cron/jobs.json'
PDONE_CRON = PDONE / 'cron/jobs.json'
DEFAULT_CONFIG = HERMES / 'config.yaml'
PDONE_CONFIG = PDONE / 'config.yaml'
DEFAULT_SCRIPTS = HERMES / 'scripts'
PDONE_SCRIPTS = PDONE / 'scripts'
YAMMER_ROOT = Path('/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace/projects/yammer-migration')
YAMMER_PREFETCH = YAMMER_ROOT / 'archive/search/prefetch-status.json'
YAMMER_BATCH_WORKER = YAMMER_ROOT / 'archive/search/batch-worker-status.json'
YAMMER_BATCH_STATUS = YAMMER_ROOT / 'archive/search/batch-status.json'
YAMMER_SYNTH = YAMMER_ROOT / 'archive/search/wiki-synthesis/state.json'
YAMMER_SHARD_CACHE = YAMMER_ROOT / 'archive/search/shard-cache'
YAMMER_ARCHIVE_ACTIVE_JOB_IDS = {'3a33a3e609f4', '3dc75ca135d1', '58681c72baff'}
LOW_ROOT_FREE_GB_WARNING = 8.0
LOW_ROOT_FREE_GB_CRITICAL = 4.0
BRIDGE_RE = re.compile(r'(pd_neo_failure_to_hermes|pd_neo_cron_failure_alert|pd_one_failure_to_hermes|pd_one_cron_failure_alert|emit_pd_one_event|hermes_guarded_autorepair)', re.I)
HUMAN_ALERT_RE = re.compile(r'(discord|telegram|mattermost|send_message|notify|alert|warning|WARN|failure|failed|error)', re.I)
EXEMPT_SCRIPT_NAMES = {
    # Queue workers are the guarded-triage/fallback path itself; their source
    # naturally mentions alert/failure terms but they should not be wrapped by
    # another alert bridge.
    'pd_one_failure_alert_queue_worker.py',
    'pd_neo_failure_alert_queue_worker.py',
    'hermes_autonomous_supervisor_tick.sh',
    # Static approved one-shot reminder. Cron delivery state is the receipt and
    # adding an in-script failure bridge would create a second notification rail.
    'remind_remove_stephen_production_schedule_access.sh',
}

NEO_PUSH_REL = Path('state') / 'hermes_autonomous_supervisor' / 'neo_push.json'
DEADMAN_SECONDS = 45 * 60
NEO_PROFILE = 'pdone'
HOST_ENV = 'NEO_WATCH_HOST'

@dataclass
class Finding:
    severity: str
    scope: str
    automation: str
    message: str
    repairable: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            'severity': self.severity,
            'scope': self.scope,
            'automation': self.automation,
            'message': self.message,
            'repairable': self.repairable,
        }


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utcnow().isoformat()


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'__error__': f'{path}: {exc}'}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def load_jobs(path: Path) -> list[dict[str, Any]]:
    raw = load_json(path, {})
    if isinstance(raw, dict) and isinstance(raw.get('jobs'), list):
        return [j for j in raw['jobs'] if isinstance(j, dict)]
    if isinstance(raw, dict):
        return [j for j in raw.values() if isinstance(j, dict)]
    if isinstance(raw, list):
        return [j for j in raw if isinstance(j, dict)]
    return []


def schedule_minutes(job: dict[str, Any]) -> int | None:
    sched = job.get('schedule') if isinstance(job.get('schedule'), dict) else {}
    if sched.get('kind') == 'interval':
        try:
            return int(sched.get('minutes') or 0)
        except Exception:
            return None
    return None


TRANSIENT_ERROR_RE = re.compile(
    r'('
    r'timeout awaiting response headers|'
    r'context deadline exceeded|'
    r'i/o timeout|'
    r'tls handshake timeout|'
    r'temporary failure|'
    r'temporarily unavailable|'
    r'connection reset by peer|'
    r'connection refused|'
    r'connection timed out|'
    r'network is unreachable|'
    r'could not resolve host|'
    r'temporary failure in name resolution|'
    r'failed to lookup address information|'
    r'server misbehaving|'
    r'http2: timeout|'
    r'HTTP 429|'
    r'HTTP 500|HTTP 502|HTTP 503|HTTP 504|'
    r'5\d\d Server Error|'
    r'URLError: <urlopen error|'
    r'TimeoutExpired|timed out after \d+ seconds|timed out after \d+s|'
    r'UNAVAILABLE|DEADLINE_EXCEEDED'
    r')',
    re.I,
)
IMMEDIATE_ESCALATION_RE = re.compile(
    r'('
    r'permission denied|'
    r'access denied|'
    r'unauthorized|'
    r'authentication failed|'
    r'invalid (api )?token|'
    r'missing (credential|token|api key)|'
    r'HTTP 401|HTTP 403|'
    r'schema (mismatch|error)|'
    r'header mismatch|'
    r'readback (failed|mismatch)|'
    r'integrity (error|fail)'
    r')',
    re.I,
)
SCRIPT_TIMEOUT_RE = re.compile(r'Script timed out after (\d+)s:\s+(.+)', re.I | re.S)
WRAPPER_GATE_TIMEOUT_RE = re.compile(r'GATE_TIMEOUT_SECONDS="\$\{[^:}]+:-(?P<seconds>\d+)\}"')
DIRECT_TIMEOUT_RE = re.compile(r'\btimeout\b[^\n]*(?P<seconds>\d+)s')

LEGACY_CRONTAB_RUNNER_JOB_ID = '31c67e36016b'
LEGACY_CRONTAB_RUNNER_SCRIPT = 'pd_one_legacy_crontab_hermes_runner.py'
LEGACY_CRONTAB_TIMEOUT_RE = re.compile(
    r'Script timed out after \d+s: .*pd_one_legacy_crontab_hermes_runner\.py',
    re.I,
)


def is_legacy_crontab_runner_timeout(job: dict[str, Any], text: str) -> bool:
    """Narrow safe-auto-handle case for the migrated legacy bridge itself.

    The bridge is a 1-minute scheduler shim; a single Hermes-level timeout usually
    means one due legacy job consumed the wrapper budget. The next bridge tick
    either recovers silently or the failure persists and should be escalated after
    a short hold. Do not replay child jobs from here because they may send messages
    or write business systems.
    """
    if not text or not LEGACY_CRONTAB_TIMEOUT_RE.search(text):
        return False
    return (
        str(job.get('id') or '') == LEGACY_CRONTAB_RUNNER_JOB_ID
        or str(job.get('script') or '').endswith(LEGACY_CRONTAB_RUNNER_SCRIPT)
        or str(job.get('name') or '').lower() == 'pd one migrated legacy crontab runner'
    )


def looks_transient_error(text: str) -> bool:
    return bool(text and TRANSIENT_ERROR_RE.search(text))


def looks_immediate_escalation_error(text: str) -> bool:
    return bool(text and IMMEDIATE_ESCALATION_RE.search(text))


def cron_failure_fingerprint(text: str) -> str:
    cleaned = re.sub(r'\d{4}-\d{2}-\d{2}T[\d:.+-]+', '<ts>', text or '')
    cleaned = re.sub(r'last_run_at=\S+', 'last_run_at=<ts>', cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip()[:240]


def cron_hold_key(scope: str, job: dict[str, Any]) -> str:
    return f'{scope}|{job.get("id") or job.get("name") or "unnamed"}'


def load_cron_failure_holds(path: Path = CRON_FAILURE_HOLDS) -> dict[str, Any]:
    raw = load_json(path, {})
    if not isinstance(raw, dict):
        return {}
    holds = raw.get('holds')
    return holds if isinstance(holds, dict) else {}


def save_cron_failure_holds(holds: dict[str, Any], path: Path = CRON_FAILURE_HOLDS) -> None:
    write_json(path, {'updated_at': iso_now(), 'holds': holds})


def should_suppress_cron_failure_alert(job: dict[str, Any], error_text: str, first_seen_age_min: float | None) -> tuple[bool, str, int]:
    """Return whether to withhold a human alert for a cron last_status!=ok.

    Hold first-blip and known-transient failures until they persist past the
    job's retry window. If the next ticks recover, Andy is never paged.
    Auth/permission/schema/integrity failures still escalate immediately.
    """
    if looks_immediate_escalation_error(error_text):
        return False, 'immediate_escalation', 0
    if is_legacy_crontab_runner_timeout(job, error_text):
        hold_min = 10
        reason = 'legacy_crontab_runner_single_timeout'
    elif looks_transient_error(error_text):
        hold_min = transient_suppression_minutes(job)
        reason = 'transient_api_or_network_error'
    else:
        hold_min = transient_suppression_minutes(job)
        reason = 'first_blip_self_heal'
    return first_seen_age_min is None or first_seen_age_min < hold_min, reason, hold_min


def should_suppress_transient_cron_failure(job: dict[str, Any], error_text: str, age_min: float | None) -> tuple[bool, str, int]:
    """Compatibility wrapper. age_min is minutes since this failure class was first seen."""
    return should_suppress_cron_failure_alert(job, error_text, age_min)


def parse_systemd_timestamp(value: str | None) -> datetime | None:
    if not value or value.strip().lower() in {'', 'n/a', '0'}:
        return None
    text = value.strip()
    for fmt in ('%a %Y-%m-%d %H:%M:%S %Z', '%a %Y-%m-%d %H:%M:%S %z'):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return parse_dt(text)


def read_gateway_info(scope: str, now: datetime | None = None) -> dict[str, Any]:
    """Read owning gateway ActiveState / age. Empty dict if unknown (do not fake a restart hold)."""
    unit = GATEWAY_UNITS.get(scope)
    if not unit:
        return {}
    try:
        proc = subprocess.run(
            ['systemctl', '--user', 'show', unit, '-p', 'ActiveState', '-p', 'ActiveEnterTimestamp', '--no-pager'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return {}
    state = ''
    entered = None
    for raw in (proc.stdout or '').splitlines():
        if raw.startswith('ActiveState='):
            state = raw.split('=', 1)[1].strip()
        elif raw.startswith('ActiveEnterTimestamp='):
            entered = parse_systemd_timestamp(raw.split('=', 1)[1])
    now = now or utcnow()
    age_min = (now - entered).total_seconds() / 60 if entered else None
    return {'state': state, 'age_min': age_min, 'unit': unit}


def should_hold_stale_receipts(first_seen_age_min: float | None, gateway_info: dict[str, Any] | None) -> tuple[bool, str]:
    """Hold clustered stale receipts through one supervisor tick or a recent gateway restart."""
    gw = gateway_info or {}
    state = str(gw.get('state') or '')
    age = gw.get('age_min')
    if state == 'active' and isinstance(age, (int, float)) and age < GATEWAY_RESTART_HOLD_MIN:
        return True, 'gateway_recent_restart'
    if first_seen_age_min is None or first_seen_age_min < STALE_RECEIPT_CONFIRM_MIN:
        return True, 'stale_receipt_confirm_next_tick'
    return False, 'persistent_stale_receipts'


def stale_cluster_hold_key(scope: str) -> str:
    return f'stale|{scope}'


def transient_suppression_minutes(job: dict[str, Any]) -> int:
    """How long a known transient failure must persist before supervisor emits it.

    Short-interval watchdogs/importers normally self-recover on the next tick. For
    cron expressions where we cannot infer interval cheaply, use a one-hour hold so
    first-blip Google/API/network incidents do not page Andy immediately.
    """
    minutes = schedule_minutes(job)
    if minutes:
        return max(20, min(120, minutes * 3))
    return 60


def resolve_script(scope: str, script: str | None, workdir: str | None = None) -> Path | None:
    if not script:
        return None
    p = Path(script)
    if p.is_absolute():
        return p
    bases = [DEFAULT_SCRIPTS]
    if scope == 'pdone':
        bases = [PDONE_SCRIPTS, DEFAULT_SCRIPTS]
    for base in bases:
        candidate = base / script
        if candidate.exists():
            return candidate
    if workdir:
        return Path(workdir) / script
    return bases[0] / script


def config_path_for_scope(scope: str) -> Path:
    return PDONE_CONFIG if scope == 'pdone' else DEFAULT_CONFIG


def cron_script_timeout_from_config(config_path: Path) -> int | None:
    try:
        text = config_path.read_text(encoding='utf-8')
    except Exception:
        return None
    in_cron = False
    for raw in text.splitlines():
        if re.match(r'^cron:\s*$', raw):
            in_cron = True
            continue
        if in_cron:
            if raw and not raw.startswith(' ') and not raw.startswith('#'):
                break
            m = re.match(r'^\s{2}script_timeout_seconds:\s*(\d+)\s*$', raw)
            if m:
                return int(m.group(1))
    return None


def set_cron_script_timeout(config_path: Path, seconds: int) -> bool:
    text = config_path.read_text(encoding='utf-8')
    lines = text.splitlines()
    out: list[str] = []
    in_cron = False
    changed = False
    inserted = False
    for raw in lines:
        if re.match(r'^cron:\s*$', raw):
            in_cron = True
            out.append(raw)
            continue
        if in_cron and raw and not raw.startswith(' ') and not raw.startswith('#'):
            if not inserted:
                out.append(f'  script_timeout_seconds: {seconds}')
                inserted = True
                changed = True
            in_cron = False
        if in_cron and re.match(r'^\s{2}script_timeout_seconds:\s*', raw):
            new = f'  script_timeout_seconds: {seconds}'
            out.append(new)
            inserted = True
            changed = changed or raw != new
            continue
        out.append(raw)
    if in_cron and not inserted:
        out.append(f'  script_timeout_seconds: {seconds}')
        changed = True
    if changed:
        config_path.write_text('\n'.join(out) + ('\n' if text.endswith('\n') else ''), encoding='utf-8')
    return changed


def desired_timeout_for_script(path: Path | None, observed_timeout: int) -> int | None:
    if not path or not path.exists() or path.suffix.lower() not in {'.py', '.sh', '.bash'}:
        return None
    try:
        text = path.read_text(errors='ignore')[:20000]
    except Exception:
        return None
    candidates = [observed_timeout + 60]
    for rx in (WRAPPER_GATE_TIMEOUT_RE, DIRECT_TIMEOUT_RE):
        for m in rx.finditer(text):
            try:
                candidates.append(int(m.group('seconds')) + 60)
            except Exception:
                pass
    desired = max(candidates)
    return max(180, min(1800, desired))


def maybe_repair_timeout_budget(scope: str, job: dict[str, Any], error_text: str, summary: dict[str, Any], apply: bool) -> tuple[bool, str]:
    m = SCRIPT_TIMEOUT_RE.search(error_text or '')
    if not m:
        return False, ''
    observed = int(m.group(1))
    path = resolve_script(scope, job.get('script'), job.get('workdir'))
    desired = desired_timeout_for_script(path, observed)
    if desired is None:
        return False, ''
    config_path = config_path_for_scope(scope)
    current = cron_script_timeout_from_config(config_path) or 120
    if current >= desired:
        return True, f'timeout budget already aligned: current={current}s desired>={desired}s path={path}'
    if apply:
        changed = set_cron_script_timeout(config_path, desired)
        repairs = summary.setdefault('timeout_budget_repairs', [])
        if isinstance(repairs, list):
            repairs.append({'scope': scope, 'job_id': job.get('id'), 'config': str(config_path), 'from_seconds': current, 'to_seconds': desired, 'changed': changed})
        return True, f'auto-repaired cron script timeout budget: {config_path} {current}s -> {desired}s for {path}'
    return True, f'timeout budget can be auto-repaired: {config_path} {current}s -> {desired}s for {path}'


def registry_entries(registry: Any) -> list[dict[str, Any]]:
    if isinstance(registry, dict) and isinstance(registry.get('automations'), list):
        return [a for a in registry['automations'] if isinstance(a, dict)]
    return []


def ensure_registry(path: Path) -> dict[str, Any]:
    raw = load_json(path, {})
    if isinstance(raw, dict) and isinstance(raw.get('automations'), list):
        return raw
    return {
        'schema': 'hermes.supervisor.automations.v1',
        'updated_at': iso_now(),
        'notes': 'Auto-created by hermes_autonomous_supervisor.py; conservative entries only.',
        'automations': [],
    }


def classify_job(job: dict[str, Any], script_text: str) -> tuple[str, str, bool]:
    blob = ' '.join(str(job.get(k) or '') for k in ('name', 'prompt', 'script', 'deliver')) + '\n' + script_text[:20000]
    touches_external = bool(re.search(r'(gog|google|drive|sheet|appsheet|mattermost|discord|telegram|line|openclaw message|send_message|curl\s+https?://)', blob, re.I))
    if touches_external:
        return 'approval-required', 'Auto-registered conservative default: job appears to touch external systems or people; repairs/replays need approval until a narrow safe repair is defined.', True
    return 'do-not-autorepair', 'Advisory/local job or unclear side effects; alert/remediation-plan only until a narrow safe repair is defined.', False


def self_register_cron(scope: str, cron_path: Path, registry_path: Path, findings: list[Finding], apply: bool) -> dict[str, int]:
    registry = ensure_registry(registry_path)
    entries = registry_entries(registry)
    by_job = {a.get('job_id'): a for a in entries if a.get('source') == 'hermes-cron' and a.get('job_id')}
    added = 0
    for job in load_jobs(cron_path):
        if not job.get('enabled', True):
            continue
        job_id = job.get('id') or job.get('job_id')
        if not job_id or job_id in by_job:
            continue
        script_path = resolve_script(scope, job.get('script'), job.get('workdir'))
        script_text = ''
        if script_path and script_path.exists() and script_path.suffix.lower() in {'.py', '.sh', '.bash'}:
            try:
                script_text = script_path.read_text(errors='ignore')
            except Exception:
                script_text = ''
        classification, reason, touches_external = classify_job(job, script_text)
        entry = {
            'id': f'{scope}-cron-{job_id}',
            'source': 'hermes-cron',
            'job_id': job_id,
            'name': job.get('name') or job_id,
            'criticality': 'medium' if touches_external else 'low',
            'touches_external_systems': touches_external,
            'alert_expectation': 'Auto-registered by autonomous supervisor; requires scheduler receipt checks and outcome contract if it owns a business pipeline.',
            'outcome_contract': {
                'status': 'missing',
                'reason': 'Autonomous supervisor could not infer a business outcome contract safely. Add success metric, blocker checks, state paths, safe repairs, and approval-gated repairs.'
            },
            'autorepair': {'classification': classification, 'reason': reason},
            'supervisor': {'auto_registered_at': iso_now(), 'scope': scope},
        }
        if apply:
            entries.append(entry)
            added += 1
        findings.append(Finding('warning', scope, str(job.get('name') or job_id), f'enabled cron job {job_id} was missing from {registry_path}; self-registered conservative entry' if apply else f'enabled cron job {job_id} missing from {registry_path}', repairable=True))
    if apply and added:
        registry['automations'] = entries
        registry['updated_at'] = iso_now()
        write_json(registry_path, registry)
    return {'added': added}


def audit_cron_receipts(scope: str, cron_path: Path, findings: list[Finding], summary: dict[str, Any], apply: bool = False, holds_path: Path = CRON_FAILURE_HOLDS, gateway_info: dict[str, Any] | None = None) -> None:
    jobs = [j for j in load_jobs(cron_path) if j.get('enabled', True)]
    summary[f'{scope}_enabled_cron_jobs'] = len(jobs)
    now = utcnow()
    transient_suppressed = 0
    holds = load_cron_failure_holds(holds_path)
    holds_changed = False
    stale_jobs: list[dict[str, Any]] = []
    for job in jobs:
        name = str(job.get('name') or job.get('id') or 'unnamed')
        status = job.get('last_status')
        last = parse_dt(job.get('last_run_at'))
        hold_key = cron_hold_key(scope, job)
        transient_status = False
        if status and status != 'ok':
            error_text = str(job.get('last_error') or '')
            timeout_repairable, timeout_note = maybe_repair_timeout_budget(scope, job, error_text, summary, apply)
            if timeout_repairable:
                findings.append(Finding('warning', scope, name, f'last_status={status}; last_run_at={job.get("last_run_at")}; {timeout_note}; original_error={error_text[-300:]}', repairable=True))
            else:
                fingerprint = cron_failure_fingerprint(error_text)
                rec = holds.get(hold_key) if isinstance(holds.get(hold_key), dict) else {}
                if rec.get('fingerprint') != fingerprint:
                    first_seen = last or now
                    rec = {
                        'fingerprint': fingerprint,
                        'first_seen_at': first_seen.isoformat(),
                    }
                    holds[hold_key] = rec
                    holds_changed = True
                first_seen = parse_dt(rec.get('first_seen_at')) or last or now
                age_min = (now - first_seen).total_seconds() / 60
                suppress, reason, hold_min = should_suppress_cron_failure_alert(job, error_text, age_min)
                if rec.get('reason') != reason:
                    rec['reason'] = reason
                    holds[hold_key] = rec
                    holds_changed = True
                if suppress:
                    # First-blip, later-fixed, or known transient. Keep it out of
                    # human notifications for a bounded retry window; escalate
                    # only if it remains failing past the hold.
                    transient_suppressed += 1
                    transient_status = True
                    key = f'{scope}_transient_cron_failure_reasons'
                    summary.setdefault(key, {})
                    if isinstance(summary[key], dict):
                        summary[key][reason] = int(summary[key].get(reason) or 0) + 1
                elif reason and reason != 'immediate_escalation':
                    findings.append(Finding('critical', scope, name, f'last_status={status}; last_run_at={job.get("last_run_at")}; transient failure persisted beyond {hold_min}m hold ({reason}); error={error_text[-300:]}'))
                else:
                    findings.append(Finding('critical', scope, name, f'last_status={status}; last_run_at={job.get("last_run_at")}; error={error_text[-300:]}'))
        elif hold_key in holds:
            del holds[hold_key]
            holds_changed = True
        if job.get('last_delivery_error'):
            findings.append(Finding('critical', scope, name, f'last_delivery_error={job.get("last_delivery_error")}'))
        minutes = schedule_minutes(job)
        if minutes and last and not transient_status:
            grace = max(20, minutes * 3)
            age_min = (now - last).total_seconds() / 60
            if age_min > grace:
                stale_jobs.append({
                    'id': str(job.get('id') or job.get('name') or name),
                    'name': name,
                    'age_min': age_min,
                    'minutes': minutes,
                    'grace': grace,
                })
        if job.get('script'):
            path = resolve_script(scope, job.get('script'), job.get('workdir'))
            if path and not path.exists():
                findings.append(Finding('critical', scope, name, f'script missing: {path}'))
            elif path and path.name in EXEMPT_SCRIPT_NAMES:
                continue
            elif path and path.suffix.lower() in {'.py', '.sh', '.bash'}:
                try:
                    text = path.read_text(errors='ignore')
                except Exception:
                    text = ''
                human_visible = str(job.get('deliver') or '') not in {'', 'local'} or bool(HUMAN_ALERT_RE.search(text))
                if human_visible and not BRIDGE_RE.search(text):
                    findings.append(Finding('warning', scope, name, f'human-visible automation lacks guarded-triage marker: {path}', repairable=True))
    cluster_key = stale_cluster_hold_key(scope)
    if not stale_jobs:
        if cluster_key in holds:
            del holds[cluster_key]
            holds_changed = True
    else:
        fingerprint = ','.join(sorted(j['id'] for j in stale_jobs))
        rec = holds.get(cluster_key) if isinstance(holds.get(cluster_key), dict) else {}
        old_fp = str(rec.get('fingerprint') or '')
        old_ids = set(part for part in old_fp.split(',') if part)
        new_ids = {j['id'] for j in stale_jobs}
        if rec.get('fingerprint') != fingerprint:
            if old_ids & new_ids:
                rec = {
                    'first_seen_at': rec.get('first_seen_at') or iso_now(),
                    'fingerprint': fingerprint,
                }
            else:
                rec = {'first_seen_at': iso_now(), 'fingerprint': fingerprint}
            holds[cluster_key] = rec
            holds_changed = True
        first_seen = parse_dt(rec.get('first_seen_at')) or now
        first_age = (now - first_seen).total_seconds() / 60
        info = gateway_info if gateway_info is not None else read_gateway_info(scope, now)
        hold, reason = should_hold_stale_receipts(first_age, info)
        if rec.get('reason') != reason:
            rec['reason'] = reason
            holds[cluster_key] = rec
            holds_changed = True
        if hold:
            summary[f'{scope}_stale_receipt_holds_suppressed'] = len(stale_jobs)
            key = f'{scope}_transient_cron_failure_reasons'
            summary.setdefault(key, {})
            if isinstance(summary[key], dict):
                summary[key][reason] = int(summary[key].get(reason) or 0) + 1
        elif len(stale_jobs) >= STALE_CLUSTER_MIN_JOBS:
            names = ', '.join(j['name'] for j in stale_jobs[:8])
            extra = '' if len(stale_jobs) <= 8 else f' and {len(stale_jobs) - 8} more'
            gw_note = ''
            if info.get('state') and info.get('state') != 'active':
                gw_note = f'; gateway {info.get("unit") or scope} state={info.get("state")}'
            findings.append(Finding(
                'warning',
                scope,
                f'{scope} scheduler/gateway stall',
                f'{len(stale_jobs)} enabled jobs have stale cron receipts after grace ({names}{extra}){gw_note}; treat as one profile scheduler/gateway stall, not {len(stale_jobs)} independent job failures',
            ))
        else:
            job = stale_jobs[0]
            findings.append(Finding(
                'warning',
                scope,
                job['name'],
                f'cron receipt stale: last_run_at {job["age_min"]:.1f} minutes ago; interval={job["minutes"]}m grace={job["grace"]}m',
            ))
    if transient_suppressed:
        summary[f'{scope}_transient_cron_failures_suppressed'] = transient_suppressed
    if holds_changed:
        save_cron_failure_holds(holds, holds_path)


def audit_root_disk(findings: list[Finding], summary: dict[str, Any]) -> None:
    du = shutil.disk_usage('/')
    free_gb = du.free / 1024 ** 3
    summary['root_free_gb'] = round(free_gb, 3)
    if free_gb < LOW_ROOT_FREE_GB_CRITICAL:
        findings.append(Finding('critical', 'system', 'root filesystem', f'root disk critically low: {free_gb:.2f} GB free', repairable=True))
    elif free_gb < LOW_ROOT_FREE_GB_WARNING:
        findings.append(Finding('warning', 'system', 'root filesystem', f'root disk low: {free_gb:.2f} GB free', repairable=True))


def audit_yammer(findings: list[Finding], summary: dict[str, Any]) -> None:
    # The archive extraction/progress pipeline is intentionally paused/retired at
    # times while downstream historical wiki review jobs may still run. Do not
    # report stale archive outcome state unless one of the archive acquisition or
    # progress jobs is currently enabled.
    active_archive_jobs = [
        j for j in load_jobs(DEFAULT_CRON)
        if str(j.get('id') or '') in YAMMER_ARCHIVE_ACTIVE_JOB_IDS and j.get('enabled', True)
    ]
    if not active_archive_jobs:
        summary['yammer_archive_monitoring'] = 'skipped_inactive'
        return
    if not YAMMER_ROOT.exists():
        return
    free_gb = shutil.disk_usage(YAMMER_ROOT).free / 1024 ** 3
    prefetch = load_json(YAMMER_PREFETCH, {})
    worker = load_json(YAMMER_BATCH_WORKER, {})
    batch = load_json(YAMMER_BATCH_STATUS, {})
    synth = load_json(YAMMER_SYNTH, {})
    zips = list(YAMMER_SHARD_CACHE.glob('shard-*.zip')) if YAMMER_SHARD_CACHE.exists() else []
    parts = list(YAMMER_SHARD_CACHE.glob('shard-*.zip.part')) if YAMMER_SHARD_CACHE.exists() else []
    summary.update({
        'yammer_free_gb': round(free_gb, 3),
        'yammer_prefetch_status': prefetch.get('status') if isinstance(prefetch, dict) else None,
        'yammer_prefetch_min_free_gb': prefetch.get('min_free_gb') if isinstance(prefetch, dict) else None,
        'yammer_prefetch_updated_at': prefetch.get('updated_at') if isinstance(prefetch, dict) else None,
        'yammer_worker_status': worker.get('status') if isinstance(worker, dict) else None,
        'yammer_processed_shard_total': batch.get('processed_shard_total') if isinstance(batch, dict) else None,
        'yammer_uploaded_shard_total': batch.get('uploaded_shard_total') if isinstance(batch, dict) else None,
        'yammer_synthesized_count': len(synth.get('synthesized_shards') or []) if isinstance(synth, dict) else None,
        'yammer_cache_complete_zips': len(zips),
        'yammer_cache_part_files': len(parts),
    })
    min_free = None
    if isinstance(prefetch, dict):
        try:
            min_free = float(prefetch.get('min_free_gb') or 0)
        except Exception:
            min_free = None
    if isinstance(prefetch, dict) and prefetch.get('status') == 'skipped_low_disk':
        if min_free and free_gb < min_free:
            findings.append(Finding('critical', 'default', 'Yammer archive prefetch', f'prefetch blocked by disk guard: free={free_gb:.2f} GB < min_free_gb={min_free:.2f}; wiki synthesis will stall', repairable=True))
        else:
            findings.append(Finding('warning', 'default', 'Yammer archive prefetch', f'prefetch last status skipped_low_disk but current free={free_gb:.2f} GB; next tick should clear or needs manual trigger', repairable=True))
    if isinstance(worker, dict) and worker.get('status') == 'skipped_low_disk':
        findings.append(Finding('critical', 'default', 'Yammer archive extraction', f'extractor skipped for low disk: free_kb={worker.get("free_kb")} threshold_kb={worker.get("threshold_kb")}', repairable=True))
    # Producer/consumer stall hint: extractor is --no-download, so zero cache and stale prefetch is actionable.
    prefetch_updated = parse_dt(prefetch.get('updated_at') if isinstance(prefetch, dict) else None)
    if prefetch_updated and (utcnow() - prefetch_updated) > timedelta(minutes=45) and not zips and not parts:
        findings.append(Finding('warning', 'default', 'Yammer archive prefetch', f'prefetch status stale for {(utcnow()-prefetch_updated).total_seconds()/60:.1f} minutes and shard cache is empty; --no-download extractor may starve', repairable=True))


def write_remediation_plans(findings: list[Finding], summary: dict[str, Any]) -> int:
    REMEDIATION_DIR.mkdir(parents=True, exist_ok=True)
    existing_signatures: set[str] = set()
    for old_path in REMEDIATION_DIR.glob('*.json'):
        old = load_json(old_path, {})
        if isinstance(old, dict) and isinstance(old.get('finding'), dict):
            fd = old['finding']
            existing_signatures.add(re.sub(r'\s+', ' ', f"{fd.get('severity')}|{fd.get('scope')}|{fd.get('automation')}|{fd.get('message')}").strip()[:500])
    count = 0
    stamp = utcnow().strftime('%Y%m%dT%H%M%SZ')
    for idx, f in enumerate(findings):
        if f.severity not in {'critical', 'warning'}:
            continue
        if not f.repairable and f.severity != 'critical':
            continue
        sig = finding_signature(f)
        if sig in existing_signatures:
            continue
        slug = re.sub(r'[^a-z0-9]+', '-', f'{f.scope}-{f.automation}'.lower()).strip('-')[:70] or 'finding'
        path = REMEDIATION_DIR / f'{stamp}-{idx:02d}-{slug}.json'
        if path.exists():
            continue
        data = {
            'created_at': iso_now(),
            'signature': sig,
            'finding': f.as_dict(),
            'summary_snapshot': summary,
            'autonomous_status': 'blocked' if not f.repairable else 'queued-safe-review',
            'approval_required': not f.repairable,
            'allowed_autonomous_actions': [
                'registry self-registration',
                'monitoring/guarded-triage plumbing',
                'syntax/read-only verification',
                'known env fallback + no-send identity readback when explicitly allowlisted in the supervisor repair contract',
                'backup commit for supervisor files',
            ],
            'forbidden_without_approval': [
                'gateway restart',
                'credential creation/rotation/movement/value changes',
                'source-system writes',
                'employee/external sends or replays',
                'broad deletion/cleanup',
            ],
        }
        write_json(path, data)
        existing_signatures.add(sig)
        count += 1
    return count


def run_safe_temp_cleanup_if_needed(findings: list[Finding], summary: dict[str, Any], apply: bool) -> int:
    """Only clean explicitly allowlisted regenerable temp/cache paths for disk blockers."""
    blocker = any(f.repairable and 'disk' in f.message.lower() and f.severity == 'critical' for f in findings)
    if not blocker or not apply:
        return 0
    commands = [
        ['find', '/tmp', '-xdev', '-mindepth', '1', '-mtime', '+1', '!', '-name', '.X11-unix', '!', '-name', '.ICE-unix', '-exec', 'rm', '-rf', '--', '{}', '+'],
        ['find', '/var/tmp/openclaw-compile-cache', '-xdev', '-mindepth', '1', '-mtime', '+1', '-exec', 'rm', '-rf', '--', '{}', '+'],
    ]
    ran = 0
    for cmd in commands:
        if cmd[1].startswith('/var/tmp') and not Path(cmd[1]).exists():
            continue
        subprocess.run(cmd, text=True, capture_output=True, timeout=180, check=False)
        ran += 1
    summary['safe_temp_cleanup_commands_ran'] = ran
    return ran


def finding_signature(f: Finding) -> str:
    msg = re.sub(r'\d{4}-\d{2}-\d{2}T[\d:.+-]+', '<ts>', f.message)
    msg = re.sub(r'last_run_at=\S+', 'last_run_at=<ts>', msg)
    msg = re.sub(r'last_run_at \d+(?:\.\d+)? minutes ago', 'last_run_at <age> minutes ago', msg)
    msg = re.sub(
        r'\d+ enabled jobs have stale cron receipts after grace \([^)]*\)(; gateway \S+ state=\S+)?; treat as one profile scheduler/gateway stall, not \d+ independent job failures',
        'N enabled jobs have stale cron receipts after grace (jobs); treat as one profile scheduler/gateway stall, not N independent job failures',
        msg,
    )
    return re.sub(r'\s+', ' ', f'{f.severity}|{f.scope}|{f.automation}|{msg}').strip()[:500]


def filter_repeated_findings(findings: list[Finding], cooldown_hours: float, state_path: Path = SUPERVISOR_STATE) -> list[Finding]:
    """Return findings that are new or past cooldown; persist last-seen state."""
    now = utcnow()
    state = load_json(state_path, {})
    if not isinstance(state, dict):
        state = {}
    seen = state.get('findings') if isinstance(state.get('findings'), dict) else {}
    current: dict[str, Any] = {}
    emit: list[Finding] = []
    cooldown = timedelta(hours=cooldown_hours)
    for f in findings:
        sig = finding_signature(f)
        old = seen.get(sig) if isinstance(seen.get(sig), dict) else {}
        first_seen = old.get('first_seen_at') or iso_now()
        last_emitted = parse_dt(old.get('last_emitted_at'))
        # Quiet mode (2026-10-24): emission decided below by findings-set fingerprint, not cooldown.
        should_emit = False
        emit.append(f)
        current[sig] = {
            'first_seen_at': first_seen,
            'last_seen_at': iso_now(),
            'last_emitted_at': iso_now() if should_emit else old.get('last_emitted_at'),
            'finding': f.as_dict(),
        }
    # Post only when the set of findings (signature includes severity/status/error) changed since last post.
    import hashlib
    notify = [f for f in emit if needs_input(f)] or emit
    fp = hashlib.sha256('\n'.join(sorted(finding_signature(f) for f in notify)).encode()).hexdigest()[:16] if notify else ''
    last_fp = state.get('notified_fingerprint', '')
    if fp == last_fp:
        emit = []
    else:
        for f in emit:
            current[finding_signature(f)]['last_emitted_at'] = iso_now()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(state_path, {'updated_at': iso_now(), 'findings': current, 'notified_fingerprint': fp,
                            'notified_fingerprint_changed_at': iso_now() if fp != last_fp else state.get('notified_fingerprint_changed_at')})
    return emit


def human_label(key: str) -> str:
    labels = {
        'root_free_gb': 'Root disk free',
        'default_enabled_cron_jobs': 'PD Neo/default cron jobs checked',
        'pdone_enabled_cron_jobs': 'PD One cron jobs checked',
        'self_registered_default': 'New PD Neo/default registry entries',
        'self_registered_pdone': 'New PD One registry entries',
        'remediation_plans_written': 'New remediation plans written',
        'safe_temp_cleanup_ran': 'Safe cleanup commands run',
        'yammer_free_gb': 'Yammer disk free',
        'yammer_prefetch_status': 'Yammer prefetch status',
        'yammer_prefetch_min_free_gb': 'Yammer prefetch disk guard',
        'yammer_prefetch_updated_at': 'Yammer prefetch last update',
        'yammer_worker_status': 'Yammer extractor status',
        'yammer_processed_shard_total': 'Yammer processed shards',
        'yammer_uploaded_shard_total': 'Yammer uploaded shards',
        'yammer_synthesized_count': 'Wiki synthesized pages/shards',
        'yammer_cache_complete_zips': 'Ready cached shard ZIPs',
        'yammer_cache_part_files': 'In-progress shard downloads',
    }
    return labels.get(key, key.replace('_', ' ').capitalize())


def human_value(key: str, value: Any) -> str:
    if value is None:
        return 'unknown'
    if key.endswith('_gb') or key in {'yammer_prefetch_min_free_gb'}:
        try:
            return f'{float(value):.2f} GB'
        except Exception:
            return str(value)
    return str(value)


def needs_input(f: Finding) -> bool:
    """Whether Andy/admin input is needed for this finding."""
    # The deterministic supervisor may only perform narrow safe repairs. Anything
    # not marked repairable is explicitly approval/input-gated.
    return not f.repairable


def notification_findings(findings: list[Finding]) -> list[Finding]:
    """Return only findings that require Andy/admin input.

    Repairable findings remain in supervisor state, remediation plans, and the
    incident ledger/digest.  They must not ride along in an external alert just
    because an unrelated blocked finding is actionable.
    """
    return [finding for finding in findings if needs_input(finding)]


def auto_repair_result(f: Finding, summary: dict[str, Any]) -> tuple[str, list[str]]:
    """Return a clear per-finding repair status and concrete attempted actions."""
    msg = f.message.lower()
    attempts: list[str] = []
    if f.repairable:
        if 'disk' in msg:
            ran = int(summary.get('safe_temp_cleanup_ran') or 0)
            if ran:
                return 'AUTO-REPAIR ATTEMPTED — allowlisted temp/cache cleanup ran; recheck next tick.', [f'Ran {ran} allowlisted cleanup command(s).']
            return 'NO INPUT NEEDED YET — disk-related finding is repairable, but cleanup did not run unless the blocker is critical.', ['Checked disk state and kept within safe cleanup policy.']
        if 'guarded-triage marker' in msg or 'missing from' in msg or 'self-registered' in msg:
            return 'NO INPUT NEEDED — safe supervisor/plumbing remediation queued or already handled.', ['Wrote/deduped remediation-plan or conservative registry entry for safe follow-up.']
        if 'timeout budget' in msg or 'script timed out' in msg:
            repairs = summary.get('timeout_budget_repairs') if isinstance(summary.get('timeout_budget_repairs'), list) else []
            if repairs:
                return 'AUTO-REPAIR APPLIED — cron timeout budget aligned; next scheduled/manual run should clear stale error metadata.', [f'Applied {len(repairs)} bounded timeout-budget config repair(s).']
            return 'NO INPUT NEEDED — timeout-budget mismatch is allowlisted for deterministic repair/readback.', ['Checked wrapper/script timeout budget and kept within bounded max cap.']
        if 'prefetch' in msg or 'extractor' in msg or 'yammer' in msg:
            return 'NO INPUT NEEDED YET — supervisor will keep retry/readback monitoring this pipeline.', ['Checked Yammer producer/consumer state, disk guard, cache, and progress counters.']
        return 'NO INPUT NEEDED YET — classified as repairable; safe remediation plan/readback path is active.', ['Wrote/deduped remediation plan for safe autonomous follow-up.']
    attempts.append('Captured original cron/outcome error and wrote or deduped a remediation plan.')
    attempts.append('Did not perform risky repair automatically because this class is not allowlisted.')
    return 'INPUT NEEDED — no safe autonomous repair is currently allowlisted for this error class.', attempts


def format_human_report(summary: dict[str, Any], display_findings: list[Finding], total_findings: int, suppressed_count: int, all_mode: bool) -> str:
    critical = sum(1 for f in display_findings if f.severity == 'critical')
    warnings = sum(1 for f in display_findings if f.severity == 'warning')
    input_needed = sum(1 for f in display_findings if needs_input(f))
    no_input = len(display_findings) - input_needed
    status = 'INPUT NEEDED' if input_needed else ('NO INPUT NEEDED — AUTO-REPAIR/MONITORING ACTIVE' if display_findings else 'HEALTHY')
    lines: list[str] = []
    lines.append(f'Hermes Autonomous Supervisor Report — {status}')
    lines.append('')
    lines.append('Decision for Andy:')
    if display_findings:
        if input_needed:
            lines.append(f'- INPUT NEEDED for {input_needed} item(s). These are blocked by safety/approval or missing an allowlisted repair.')
        if no_input:
            lines.append(f'- NO INPUT NEEDED for {no_input} item(s). Supervisor handled/queued safe remediation or will continue monitoring.')
    else:
        lines.append('- NO INPUT NEEDED. No new unsuppressed findings on this run.')
    lines.append('')
    lines.append('Executive summary:')
    if display_findings:
        lines.append(f'- Found {critical} critical and {warnings} warning item(s) in this notification.')
    else:
        lines.append('- No new unsuppressed findings on this run.')
    if suppressed_count and not all_mode:
        lines.append(f'- {suppressed_count} unchanged finding(s) are still tracked but suppressed by cooldown.')
    lines.append(f'- Checked {summary.get("default_enabled_cron_jobs", "?")} PD Neo/default cron jobs and {summary.get("pdone_enabled_cron_jobs", "?")} PD One cron jobs.')
    transient_suppressed = int(summary.get('default_transient_cron_failures_suppressed') or 0) + int(summary.get('pdone_transient_cron_failures_suppressed') or 0)
    if transient_suppressed:
        lines.append(f'- Suppressed {transient_suppressed} recent transient or first-failure finding(s); will report only if they persist past the retry window.')
    lines.append(f'- Root disk free: {human_value("root_free_gb", summary.get("root_free_gb"))}.')
    if summary.get('remediation_plans_written'):
        lines.append(f'- Wrote {summary.get("remediation_plans_written")} new remediation plan(s).')
    if summary.get('self_registered_default') or summary.get('self_registered_pdone'):
        lines.append(f'- Self-registered {summary.get("self_registered_default", 0)} PD Neo/default and {summary.get("self_registered_pdone", 0)} PD One automation contract(s).')
    if summary.get('safe_temp_cleanup_ran'):
        lines.append(f'- Ran {summary.get("safe_temp_cleanup_ran")} allowlisted temp/cache cleanup command(s).')
    if summary.get('timeout_budget_repairs'):
        lines.append(f'- Applied {len(summary.get("timeout_budget_repairs") or [])} safe cron timeout-budget repair(s).')

    lines.append('')
    lines.append('Findings, original errors, and auto-repair result:')
    if display_findings:
        for idx, f in enumerate(display_findings[:80], 1):
            result, attempts = auto_repair_result(f, summary)
            lines.append(f'{idx}. {f.severity.upper()} — {f.scope} / {f.automation}')
            lines.append(f'   - Original error/finding: {f.message}')
            lines.append(f'   - Supervisor result: {result}')
            for attempt in attempts:
                lines.append(f'   - What it tried/did: {attempt}')
        if len(display_findings) > 80:
            lines.append(f'- ...and {len(display_findings) - 80} more item(s).')
    else:
        lines.append('- None to report.')

    lines.append('')
    lines.append('Autonomous repair boundary:')
    lines.append('- Auto-allowed: registry self-registration, remediation-plan writes/deduping, read-only checks, syntax checks, allowlisted temp/cache cleanup for critical disk blockers, bounded timeout-budget alignment, transient provider retry/readback, and explicitly allowlisted known-env-fallback/no-send identity readback repairs.')
    lines.append('- Requires Andy/admin input: gateway restarts, credential/auth creation/rotation/movement/value changes, source-system writes, employee/external sends or replays, permission changes, broad deletion, or any cron-specific repair not yet allowlisted.')
    lines.append('')
    lines.append(f'Checked at: {summary.get("checked_at")}')
    return '\n'.join(lines)


def state_path(home: Path) -> Path:
    return home / 'state' / 'hermes_autonomous_supervisor' / 'state.json'


def save_json(path: Path, data: dict[str, Any], *, dry_run: bool = False) -> None:
    if dry_run:
        return
    write_json(path, data)


def neo_push_path(home: Path) -> Path:
    return home / NEO_PUSH_REL


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
                'id': raw.get('id'),
                'severity': raw.get('severity'),
                'subject': raw.get('subject') or raw.get('title'),
            }
        )
    return redact_value(items)


def _router_cmd(home: Path, *args: str) -> list[str]:
    return [sys.executable, '-m', 'scripts.pd_one_notification_router', *args, '--hermes-home', str(home)]


def escalate_deadman(home: Path, *, correlation: str, summary: str, dry_run: bool) -> bool:
    event = {
        'severity': 'critical',
        'summary': summary,
        'correlation_key': correlation,
        'source': 'hermes_autonomous_supervisor',
    }
    cmd = _router_cmd(
        home,
        'send',
        '--route',
        'pd_one_failure_escalations',
        '--json',
        json.dumps(event, separators=(',', ':')),
    )
    if dry_run:
        print(json.dumps({'deadman_escalation': event, 'cmd': cmd}, indent=2))
        return True
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def is_correlation_acked(home: Path, correlation: str) -> bool:
    cmd = _router_cmd(home, 'is-acked', '--correlation-key', correlation)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    try:
        body = json.loads(proc.stdout or '{}')
    except json.JSONDecodeError:
        return False
    return bool(body.get('acked'))


def _findings_list_for_neo(state: dict[str, Any]) -> list[dict[str, Any]]:
    raw = state.get('findings')
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        out: list[dict[str, Any]] = []
        for item in raw.values():
            if isinstance(item, dict) and isinstance(item.get('finding'), dict):
                out.append(item['finding'])
        return out
    return []


def maybe_notify_neo(
    home: Path,
    state: dict[str, Any],
    *,
    host: str | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
    post_fn: Callable[..., bool] | None = None,
) -> dict[str, Any]:
    now = now or utcnow()
    host = host or os.environ.get(HOST_ENV, socket.gethostname())
    findings_raw = _findings_list_for_neo(state)
    alertable = alertable_findings(findings_raw)
    fingerprint = compute_fingerprint(findings_raw)

    push_state = load_json(neo_push_path(home), {'pushed': {}, 'deadman': {}})
    if not isinstance(push_state, dict) or push_state.get('__error__'):
        push_state = {'pushed': {}, 'deadman': {}}
    pushed: dict[str, Any] = push_state.setdefault('pushed', {})
    deadman: dict[str, Any] = push_state.setdefault('deadman', {})

    notified = str(state.get('notified_fingerprint') or '')
    correlation = neo.correlation_key(fingerprint)

    if fingerprint and fingerprint != notified:
        last_pushed = str(pushed.get('fingerprint') or '')
        if last_pushed != fingerprint:
            if neo.resolve_webhook_url() is None and not dry_run:
                neo.log_missing_webhook_once()
                save_json(neo_push_path(home), push_state, dry_run=dry_run)
                return state
            payload = neo.build_supervisor_alert_payload(
                fingerprint=fingerprint,
                findings=_serialize_findings(alertable),
                severity=neo.max_severity(alertable, alertable_fn=_finding_alertable),
                host=host,
                profile=NEO_PROFILE,
                first_seen=str(pushed.get('first_seen') or neo.iso_now(now)),
                last_seen=neo.iso_now(now),
            )
            poster = post_fn or neo.post_json_webhook
            ok = poster(payload, dry_run=dry_run)
            if ok:
                pushed['fingerprint'] = fingerprint
                pushed['first_seen'] = pushed.get('first_seen') or neo.iso_now(now)
                pushed['last_post_at'] = neo.iso_now(now)
                pushed['correlation_key'] = correlation
                if not dry_run:
                    state['notified_fingerprint'] = fingerprint
                deadman.pop('sent_at', None)
                deadman['correlation_key'] = correlation
                deadman['started_at'] = deadman.get('started_at') or neo.iso_now(now)
        elif not dry_run:
            state['notified_fingerprint'] = fingerprint

    if fingerprint and deadman.get('correlation_key') == correlation and not deadman.get('sent_at'):
        if is_correlation_acked(home, correlation):
            deadman['acked_at'] = neo.iso_now(now)
        else:
            started = deadman.get('started_at') or pushed.get('last_post_at')
            if started:
                try:
                    start_dt = datetime.fromisoformat(str(started).replace('Z', '+00:00'))
                except ValueError:
                    start_dt = now
                if (now - start_dt).total_seconds() >= DEADMAN_SECONDS:
                    summary = f'Neo Watch dead-man: unacked {correlation}'
                    if escalate_deadman(home, correlation=correlation, summary=summary, dry_run=dry_run):
                        deadman['sent_at'] = neo.iso_now(now)

    if not fingerprint:
        if not dry_run:
            state['notified_fingerprint'] = ''
        pushed.clear()
        deadman.clear()

    save_json(neo_push_path(home), push_state, dry_run=dry_run)
    return state


def persist_state(home: Path, state: dict[str, Any], **notify_kw: Any) -> None:
    state = maybe_notify_neo(home, state, **notify_kw)
    save_json(state_path(home), state, dry_run=bool(notify_kw.get('dry_run')))


def cmd_tick(home: Path, *, dry_run: bool) -> int:
    state = load_json(state_path(home), {'findings': [], 'notified_fingerprint': ''})
    if not isinstance(state, dict) or state.get('__error__'):
        state = {'findings': [], 'notified_fingerprint': ''}
    persist_state(home, state, dry_run=dry_run)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    findings: list[Finding] = []
    summary: dict[str, Any] = {'checked_at': iso_now(), 'repair_mode': bool(args.repair)}
    audit_root_disk(findings, summary)
    audit_cron_receipts('default', DEFAULT_CRON, findings, summary, args.repair)
    audit_cron_receipts('pdone', PDONE_CRON, findings, summary, args.repair)
    reg_default = self_register_cron('default', DEFAULT_CRON, DEFAULT_REGISTRY, findings, args.repair)
    reg_pdone = self_register_cron('pdone', PDONE_CRON, PDONE_REGISTRY, findings, args.repair)
    summary['self_registered_default'] = reg_default['added']
    summary['self_registered_pdone'] = reg_pdone['added']
    audit_yammer(findings, summary)
    cleanup_ran = run_safe_temp_cleanup_if_needed(findings, summary, args.repair)
    plans = write_remediation_plans(findings, summary) if args.repair else 0
    summary['remediation_plans_written'] = plans
    summary['safe_temp_cleanup_ran'] = cleanup_ran

    out = {'ok': not findings, 'summary': summary, 'findings': [f.as_dict() for f in findings]}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    display_findings = findings if args.all else filter_repeated_findings(findings, args.cooldown_hours)
    if not args.all:
        display_findings = notification_findings(display_findings)
    if not display_findings and not args.all:
        return 0
    suppressed_count = max(0, len(findings) - len(display_findings))
    print(format_human_report(summary, display_findings, len(findings), suppressed_count, args.all))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    if argv and argv[0] == 'tick':
        tick_parser = argparse.ArgumentParser(description='Neo Watch supervisor push / dead-man')
        tick_parser.add_argument('command', choices=['tick'])
        tick_parser.add_argument('--hermes-home', default=None)
        tick_parser.add_argument('--dry-run', action='store_true')
        tick_args = tick_parser.parse_args(argv)
        home = resolve_hermes_home(Path(tick_args.hermes_home) if tick_args.hermes_home else None)
        return cmd_tick(home, dry_run=tick_args.dry_run)

    audit_parser = argparse.ArgumentParser(description='Autonomous Hermes supervisor audit/safe-repair')
    audit_parser.add_argument('--repair', action='store_true', help='Apply safe registry self-registration and remediation-plan writes')
    audit_parser.add_argument('--json', action='store_true')
    audit_parser.add_argument('--all', action='store_true')
    audit_parser.add_argument(
        '--cooldown-hours',
        type=float,
        default=6.0,
        help='Suppress repeated text alerts for unchanged findings for this many hours',
    )
    audit_parser.add_argument('--hermes-home', default=None)
    audit_args = audit_parser.parse_args(argv)
    return cmd_audit(audit_args)

if __name__ == '__main__':
    raise SystemExit(main())

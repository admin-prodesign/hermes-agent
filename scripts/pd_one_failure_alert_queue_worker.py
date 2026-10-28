#!/usr/bin/env python3
"""Drain queued PD One federation events and let Hermes triage them.

This is a fallback for periods when the loopback webhook adapter is not
listening yet. It stays silent when no events are queued so a no_agent cron job
can run frequently without chat noise.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from model_policy.runtime import lane
from failure_autofix_admission_gate import decide as admit_failure_autofix
from failure_autofix_admission_gate import record_verdict as record_failure_autofix_verdict
from scripts.failure_autofix_first_pass import run_first_pass

QUEUE = Path("/home/prodesign/.hermes/pd-one-failure-alerts/queue.jsonl")
QUEUE_DIR = QUEUE.parent / "queue.d"
PROCESSING_DIR = QUEUE.parent / "processing.d"
QUEUE_IO_LOCK = QUEUE.parent / "queue-io.lock"
FAILED_DIR = Path("/home/prodesign/.hermes/pd-one-failure-alerts/failed")
LOCK = Path("/tmp/pd-one-failure-alert-queue-worker.lock")
HERMES = "/home/prodesign/.local/bin/hermes"
WORKSPACE = Path("/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace")
NOTIFICATION_ROUTER = Path("/home/prodesign/.hermes/scripts/pd_one_notification_router.py")
HERMES_AGENT = Path(os.environ.get("HERMES_AGENT_DIR", "/home/prodesign/.hermes/runtime/current"))
NOTIFICATION_ROUTER_PYTHON = str(HERMES_AGENT / ".venv/bin/python")
NOTIFICATION_STATE_DIR = Path("/home/prodesign/.hermes/state/notification-router")


def _router_base_cmd() -> list[str]:
    return [NOTIFICATION_ROUTER_PYTHON, "-m", "scripts.pd_one_notification_router"]
ESCALATION_ROUTE = "pd_one_failure_escalations"
RECEIPT_ROUTE = "pd_one_admin_receipts"
CLAIM_PATH_KEY = "_queue_claim_path"
OUTCOME_LEDGER = Path("/home/prodesign/.hermes/state/pd-one-supervisor-outcomes.jsonl")
# This cron runs every 2 minutes. Keep the whole drain bounded so one slow
# triage agent cannot overlap many ticks or monopolize scheduler capacity.
MAX_ALERTS_PER_RUN = int(os.environ.get("PD_ONE_QUEUE_MAX_ALERTS_PER_RUN", "1"))
HERMES_TRIAGE_TIMEOUT_SECONDS = int(os.environ.get("PD_ONE_QUEUE_HERMES_TIMEOUT_SECONDS", "240"))
# Defer repeated slow Supervisor handoffs before sending Andy a separate
# "Supervisor handoff failed" notification. Hermes triage can legitimately take
# several minutes on PD One incidents; keep the worker locked/bounded, but do
# not alert Andy just because the old 90-second budget was too short.
SUPERVISOR_DEFER_ATTEMPTS = int(os.environ.get("PD_ONE_QUEUE_SUPERVISOR_DEFER_ATTEMPTS", "6"))
SUPERVISOR_DEFER_MAX_AGE_SECONDS = int(os.environ.get("PD_ONE_QUEUE_SUPERVISOR_DEFER_MAX_AGE_SECONDS", "3600"))
SUPERVISOR_RETRY_BASE_SECONDS = int(os.environ.get("PD_ONE_QUEUE_RETRY_BASE_SECONDS", "120"))
SUPERVISOR_RETRY_MAX_SECONDS = int(os.environ.get("PD_ONE_QUEUE_RETRY_MAX_SECONDS", "900"))
SUPERVISOR_DELIVERY_TIMEOUT_SECONDS = int(os.environ.get("PD_ONE_QUEUE_DELIVERY_TIMEOUT_SECONDS", "60"))
OUTCOME_PREFIX = "SUPERVISOR_OUTCOME_JSON:"
NOTIFY_OUTCOMES = {"fixed", "needs_input", "supervisor_failed", "triage_failed"}
OUTCOME_VALUES = {
    "fixed",
    "recovered_no_action",
    "no_action",
    "needs_input",
    "supervisor_failed",
    "triage_failed",
    "digest_only",
}

PROMPT_TEMPLATE = """PD One/OpenClaw federation event was queued for Hermes/PD Neo because direct webhook delivery was unavailable.

Event JSON:
```json
{alert_json}
```

Routing rules by event_type and normalized `automation_incident.kind`:
- `pd-one.failure` / `automation.cron_failure`: the automation wrapper/process failed. Perform bounded admin-only triage.
- `pd-one.incident` with `automation.condition_finding` or `automation.inner_item_failure`: the automation ran and reported a business/pipeline condition; classify, verify, and only run a repair if the registry contract explicitly allows it.
- `pd-one.runtime_health`: diagnose runtime health with bounded evidence. Restarts/kills remain approval-gated unless a narrower runbook pre-approves them.
- `pd-one.attachment_failure`: diagnose attachment/file path handling with bounded evidence. Recover/deliver artifacts only through existing approved PD One rails; do not publicly replay sends.
- `pd-one.knowledge_candidate`: classify with the PD One knowledge-promotion playbook. Recommend or make a minimal canonical docs/skill/wiki update when safe; do not auto-post employee-facing content.
- `pd-one.capability_gap`: summarize blocker and route to request_approval, scoped_specialist_request, admin ticket, or runbook update as appropriate.
- Unknown event types or incident kinds: fail closed, save/report as needs-review, and do not auto-act.

Safety rules:
1. Apply only low-risk, reversible, clearly-scoped fixes supported by evidence.
2. Do NOT restart any gateway, kill processes, perform destructive cleanup, change messaging tokens/gateway ownership, replay external sends, or make production-impacting writes without Andy's explicit approval.
3. Preserve existing PD One employee-facing policy, approval tickets, scoped specialist handoffs, review-log, and Mattermost bilingual/authorization behavior.
4. Verify any fix. If the issue is transient/no-op, say so. If human approval or credentials are needed, report the blocker and recommended next action.
5. Keep local-only final responses concise with: event type/source, action taken, verification, remaining blocker.

Supervisor operating model:
- All automation/cron errors must be triaged by Supervisor first, before Andy is notified.
- If you safely fix the issue, verify it and produce a concise "fixed; no action needed" notification.
- If it recovered/no-oped without a material fix, record that as `recovered_no_action` or `no_action` and do not request immediate human attention.
- If you cannot safely fix it, stop at the approval/credential/permission/restart/destructive/external-send gate and produce an actionable decision-request notification.
- If your own triage cannot complete, fail closed; the queue worker will route one deduplicated Supervisor-handoff-failed notification through the named PD One escalation route.

When a human notification is needed, write compact Mattermost-friendly Markdown using one of these shapes:

✅ **PD One auto-fixed an issue**

**Status:** Fixed and verified  
**Event:** `<event_type>` from `<source>` on `<host>`  
**Impact:** What was degraded and whether anything remains at risk.

**What I changed**
- Concrete repair action.

**Verification**
- Real readback proving recovery.

**Andy action needed:** None.

or:

🚨 **PD One needs a decision**

**Status:** Blocked after safe auto-triage  
**Event:** `<event_type>` from `<source>` on `<host>`  
**Impact:** One plain-English sentence about what is degraded or at risk.

**What I checked**
- Concrete evidence/readback in human terms.
- Action already tried, if any.

**Why I stopped**
- The exact approval/safety gate.

**Decision needed**
- ✅ Approve: the narrow next action I can take safely if approved.
- ↩️ Alternative: monitor-only or deeper read-only option.

**Receipts**
- Short IDs/paths only; avoid long raw logs.

For `pd-one.runtime_health`, use a clear icon/title when useful: 🔥 CPU pressure, 💾 Disk pressure, 🟡 service degraded. Keep escalations under ~250 words, with bullets and bold labels.

Final output contract:
End your response with exactly one single-line JSON marker. It must be parseable JSON and must not be inside a code fence:
SUPERVISOR_OUTCOME_JSON: {"outcome":"fixed|recovered_no_action|no_action|needs_input|triage_failed|digest_only","notify":true|false,"impact":"low|visible|high","summary":"short summary","subject":"short notification title when notify=true","reason":"why this outcome was chosen","notification_markdown":"Mattermost-friendly body when notify=true"}

Use `notify=true` only for: `fixed` with a real verified repair, `needs_input`, or `triage_failed`. Classify fixed repairs as impact=low unless they restored a user-visible outcome or prevented material business interruption. Low-impact fixed receipts use the quiet admin-receipt route without an Andy mention; visible/high-impact fixed outcomes and blocked/failure outcomes use the escalation route. Use `notify=false` for routine recovered/no-action/digest-only findings.
"""


def acquire_lock() -> int | None:
    try:
        fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(fd, str(os.getpid()).encode())
        return fd
    except FileExistsError:
        # If stale for more than 30 minutes, replace it.
        try:
            if time.time() - LOCK.stat().st_mtime > 1800:
                LOCK.unlink()
                return acquire_lock()
        except FileNotFoundError:
            return acquire_lock()
        return None


def release_lock(fd: int | None) -> None:
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass
    try:
        LOCK.unlink()
    except FileNotFoundError:
        pass


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def _write_private(path: Path, text: str) -> None:
    _private_dir(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
    finally:
        os.chmod(path, 0o600)


def _redact_text(value: Any) -> str:
    text = str(value or "")
    text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)
    return re.sub(
        r"(?i)\b(password|passwd|token|api[_-]?key|secret|authorization)\b(\s*[:=]\s*)([^\s,;]+)",
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        text,
    )


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            parts = set(normalized.split("_"))
            sensitive_name = normalized in {"api_key", "apikey", "access_key", "private_key"}
            if sensitive_name or parts.intersection({"password", "passwd", "token", "secret", "authorization", "credential", "credentials"}):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_sensitive(item) for item in value)
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _event_key(alert: dict[str, Any]) -> str:
    stable = str(alert.get("idempotency_key") or alert.get("run_id") or "")
    if not stable:
        stable = json.dumps(alert, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def enqueue_alert(alert: dict[str, Any], *, replace: bool = False) -> Path:
    """Persist one event with an atomic no-clobber link or internal state replacement."""
    _private_dir(QUEUE.parent)
    _private_dir(QUEUE_DIR)
    clean = {k: v for k, v in alert.items() if k != CLAIM_PATH_KEY}
    clean.setdefault("_queued_at_ns", time.time_ns())
    target = QUEUE_DIR / f"{_event_key(clean)}.json"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.stem}-", suffix=".tmp", dir=str(QUEUE_DIR))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(clean, fh, ensure_ascii=False, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        if replace:
            os.replace(tmp, target)
        else:
            try:
                os.link(tmp, target)
            except FileExistsError:
                # Same idempotency key is already queued. Keep the existing
                # record, which may carry newer retry/delivery state.
                pass
        _fsync_dir(QUEUE_DIR)
    finally:
        tmp.unlink(missing_ok=True)
    return target


def _migrate_legacy_queue() -> None:
    """Migrate legacy JSONL without deleting the only recoverable backlog."""
    _private_dir(QUEUE.parent)
    with QUEUE_IO_LOCK.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if QUEUE.exists() and QUEUE.stat().st_size == 0:
            QUEUE.unlink(missing_ok=True)
        elif QUEUE.exists():
            legacy = QUEUE.with_name(f"queue.legacy-{os.getpid()}-{time.time_ns()}.jsonl")
            os.replace(QUEUE, legacy)
            os.chmod(legacy, 0o600)
            _fsync_dir(QUEUE.parent)

    # Recover archives left by a crash or persistence failure. Successfully
    # reprocessing earlier lines is harmless because producer enqueue is
    # idempotent and no-clobber.
    for legacy in sorted(QUEUE.parent.glob("queue.legacy-*.jsonl")):
        bad_lines: list[str] = []
        for line in legacy.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                bad_lines.append(line)
                continue
            if not isinstance(item, dict):
                bad_lines.append(line)
                continue
            enqueue_alert(item)
        if bad_lines:
            _write_private(FAILED_DIR / f"bad-lines-{time.time_ns()}.jsonl", "\n".join(bad_lines) + "\n")
        legacy.unlink(missing_ok=True)
        _fsync_dir(QUEUE.parent)


def _queue_order(item: dict[str, Any]) -> tuple[int, str]:
    claim = str(item.get(CLAIM_PATH_KEY) or "")
    try:
        queued_at = int(item.get("_queued_at_ns") or 0)
    except (TypeError, ValueError):
        try:
            queued_at = Path(claim).stat().st_mtime_ns
        except OSError:
            queued_at = 0
    return queued_at, claim


def drain_queue() -> list[dict]:
    """Claim queued events without deleting them until explicit acknowledgement."""
    _migrate_legacy_queue()
    _private_dir(QUEUE_DIR)
    _private_dir(PROCESSING_DIR)
    moved = False
    for queued in sorted(QUEUE_DIR.glob("*.json")):
        target = PROCESSING_DIR / queued.name
        try:
            if target.exists():
                # Same idempotency key is already in flight. Preserve its
                # retry/pending-outcome state instead of resetting it.
                queued.unlink()
                moved = True
                continue
            os.replace(queued, target)
            moved = True
        except FileNotFoundError:
            continue
    if moved:
        _fsync_dir(QUEUE_DIR)
        _fsync_dir(PROCESSING_DIR)
    alerts: list[dict[str, Any]] = []
    for claim in sorted(PROCESSING_DIR.glob("*.json")):
        try:
            item = json.loads(claim.read_text(encoding="utf-8"))
            if not isinstance(item, dict):
                raise ValueError("queue event must be a JSON object")
            item[CLAIM_PATH_KEY] = str(claim)
            retry_at = _parse_epoch(str(item.get("next_supervisor_attempt_at") or ""))
            if retry_at is not None and retry_at > time.time():
                continue
            alerts.append(item)
        except Exception as exc:
            _private_dir(FAILED_DIR)
            failed = FAILED_DIR / f"bad-event-{claim.name}"
            os.replace(claim, failed)
            os.chmod(failed, 0o600)
            _write_private(failed.with_suffix(failed.suffix + ".error.txt"), str(exc))
    alerts.sort(key=_queue_order)
    return alerts


def ack_alert(alert: dict[str, Any]) -> None:
    claim = str(alert.get(CLAIM_PATH_KEY) or "")
    if claim:
        path = Path(claim)
        path.unlink(missing_ok=True)
        if path.parent.exists():
            _fsync_dir(path.parent)


def update_claim(current: dict[str, Any], updated: dict[str, Any]) -> None:
    """Atomically replace one in-flight claim without a queue/ack crash window."""
    claim = Path(str(current.get(CLAIM_PATH_KEY) or ""))
    if not claim.name or claim.parent.resolve() != PROCESSING_DIR.resolve():
        raise ValueError("invalid processing claim path")
    clean = {k: v for k, v in updated.items() if k != CLAIM_PATH_KEY}
    _private_dir(PROCESSING_DIR)
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=PROCESSING_DIR,
            prefix=f".{claim.name}.",
            suffix=".tmp",
            delete=False,
        ) as fh:
            tmp = Path(fh.name)
            json.dump(clean, fh, ensure_ascii=False, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, claim)
        _fsync_dir(PROCESSING_DIR)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def requeue_alert(alert: dict[str, Any]) -> Path:
    return enqueue_alert(alert, replace=True)


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _parse_epoch(value: str) -> float | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _retryable_supervisor_error(error: str) -> bool:
    text = error or ""
    return bool(re.search(r"TimeoutExpired|timed out|timeout=|hermes chat failed", text, re.I))


def _defer_supervisor_error(alert: dict[str, Any], error: str) -> tuple[bool, dict[str, Any]]:
    """Requeue slow Supervisor triage instead of immediately emailing Andy.

    A queued PD One event is already under Supervisor-first ownership. Slow LLM
    triage should be retried/deferred a few times before becoming a human-visible
    Supervisor failure; otherwise direct fallback email races the agent run.
    """
    if not _retryable_supervisor_error(error):
        return False, alert
    now_iso = _utc_now_iso()
    first_seen = str(alert.get("supervisor_first_seen_at") or now_iso)
    first_seen_epoch = _parse_epoch(first_seen) or time.time()
    attempts = int(alert.get("supervisor_attempts") or 0) + 1
    if attempts >= SUPERVISOR_DEFER_ATTEMPTS:
        return False, alert
    if time.time() - first_seen_epoch > SUPERVISOR_DEFER_MAX_AGE_SECONDS:
        return False, alert
    deferred = dict(alert)
    deferred["supervisor_attempts"] = attempts
    deferred["supervisor_first_seen_at"] = first_seen
    deferred["last_supervisor_deferred_at"] = now_iso
    deferred["last_supervisor_error"] = error[-1200:]
    retry_delay = min(SUPERVISOR_RETRY_BASE_SECONDS * (2 ** (attempts - 1)), SUPERVISOR_RETRY_MAX_SECONDS)
    deferred["next_supervisor_attempt_at"] = dt.datetime.fromtimestamp(
        time.time() + retry_delay, tz=dt.timezone.utc
    ).isoformat(timespec="seconds")
    return True, deferred


def _compact_text(value: Any, *, limit: int = 3000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    head = text[: max(0, limit - 700)]
    tail = text[-600:]
    return f"{head}\n\n[...truncated {len(text) - len(head) - len(tail)} chars for Supervisor prompt budget...]\n\n{tail}"


def _alert_for_supervisor_prompt(alert: dict[str, Any]) -> dict[str, Any]:
    """Return a bounded, non-recursive view for the LLM triage prompt.

    Requeued alerts accumulate `last_supervisor_error` from prior Hermes CLI
    attempts. That error contains the full previous command, including the full
    prompt, so passing the raw alert back into Hermes recursively inflates the
    next prompt and makes timeouts more likely. Keep the saved alert intact on
    disk, but only send the Supervisor the event fields needed for judgment.
    """
    drop_keys = {
        "last_supervisor_error",
        "last_supervisor_deferred_at",
    }
    compact: dict[str, Any] = {}
    for key, value in alert.items():
        if key in drop_keys:
            continue
        if key == "detail":
            compact[key] = _compact_text(value, limit=3500)
        elif key == "what_was_tried" and isinstance(value, list):
            compact[key] = [_compact_text(item, limit=500) for item in value[:5]]
        else:
            compact[key] = value
    attempts = int(alert.get("supervisor_attempts") or 0)
    if attempts:
        compact["prior_supervisor_attempts"] = attempts
        compact["prior_supervisor_error_summary"] = _summarize_supervisor_error(str(alert.get("last_supervisor_error") or ""))
    return _redact_sensitive(compact)


def run_hermes(alert: dict) -> str:
    # PROMPT_TEMPLATE intentionally contains literal JSON examples. Avoid
    # str.format(), which treats those braces as replacement fields and raises
    # KeyError('"outcome"') before Supervisor triage can start.
    prompt_alert = _alert_for_supervisor_prompt(alert)
    prompt = PROMPT_TEMPLATE.replace("{alert_json}", json.dumps(prompt_alert, ensure_ascii=False, indent=2, sort_keys=True))
    proc = subprocess.run(
        [
            HERMES,
            "chat",
            "-Q",
            "--source",
            "tool",
            "--provider",
            lane("repair")["provider"],
            "--model",
            lane("repair")["model"],
            "-q",
            prompt,
            "--skills",
            "pd-one-admin",
            "--toolsets",
            "terminal,file,skills",
        ],
        cwd=str(WORKSPACE),
        text=True,
        capture_output=True,
        timeout=HERMES_TRIAGE_TIMEOUT_SECONDS,
        check=False,
    )
    out = (proc.stdout or "").strip()
    out_lines = [line for line in out.splitlines() if not line.startswith("session_id:")]
    out = "\n".join(out_lines).strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        raise RuntimeError(f"hermes chat failed rc={proc.returncode}\nSTDOUT:\n{out[-3000:]}\nSTDERR:\n{err[-3000:]}")
    return out or "Hermes completed the queued federation triage without producing text output."


def _alert_ref(alert: dict[str, Any]) -> str:
    return str(alert.get("run_id") or alert.get("idempotency_key") or alert.get("source") or "pd-one-event")


def _clean_triage_text(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        if not line.strip().startswith(OUTCOME_PREFIX):
            lines.append(line)
    return "\n".join(lines).strip()


def _is_supervisor_timeout(error: str) -> bool:
    return bool(re.search(r"TimeoutExpired|timed out after|timeout=|hermes chat failed", error or "", re.I))


def _extract_timeout_seconds(error: str) -> str:
    m = re.search(r"timed out after\s+([0-9.]+)\s+seconds", error or "", re.I)
    if m:
        return f"{m.group(1)} seconds"
    m = re.search(r"timeout=([0-9.]+)", error or "", re.I)
    if m:
        return f"{m.group(1)} seconds"
    return f"{HERMES_TRIAGE_TIMEOUT_SECONDS} seconds"


def _summarize_original_event(alert: dict[str, Any]) -> list[str]:
    """Return short, human-readable bullets for the underlying PD One event."""
    bullets: list[str] = []
    command = str(alert.get("command") or "").strip()
    if command:
        bullets.append(f"- Command: `{command[:220]}`")
    detail = str(alert.get("detail") or "")
    if detail:
        timeout_match = re.search(r"timed out after\s+[0-9.]+\s+seconds", detail, re.I)
        if timeout_match:
            bullets.append(f"- Original error: `{timeout_match.group(0)}`")
        elif "Connection refused" in detail:
            bullets.append("- Original error: loopback webhook delivery was unavailable, so the event was queued.")
        else:
            compact = " ".join(line.strip() for line in detail.splitlines() if line.strip())
            if compact:
                bullets.append(f"- Detail: {compact[:260]}")
    kind = (alert.get("automation_incident") or {}).get("kind")
    if kind:
        bullets.append(f"- Incident kind: `{kind}`")
    if not bullets:
        bullets.append("- No additional event detail was provided.")
    return bullets


def _summarize_supervisor_error(error: str) -> str:
    if _is_supervisor_timeout(error):
        return f"Hermes Supervisor triage did not return within {_extract_timeout_seconds(error)}."
    first_line = next((line.strip() for line in (error or "").splitlines() if line.strip()), "Unknown Supervisor error")
    return first_line[:320]


def parse_supervisor_outcome(triage_output: str, alert: dict[str, Any]) -> dict[str, Any]:
    """Parse the explicit Supervisor outcome marker; use narrow legacy fallbacks only."""
    for line in reversed((triage_output or "").splitlines()):
        stripped = line.strip()
        if not stripped.startswith(OUTCOME_PREFIX):
            continue
        raw = stripped[len(OUTCOME_PREFIX):].strip()
        try:
            outcome = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {
                "outcome": "triage_failed",
                "notify": True,
                "summary": "Supervisor returned an invalid outcome marker",
                "subject": "[PD Neo][Supervisor handoff failed] Invalid triage outcome",
                "reason": f"Invalid JSON after {OUTCOME_PREFIX}: {exc}",
                "notification_markdown": _supervisor_failed_markdown(alert, f"Invalid outcome marker: {exc}", triage_output),
            }
        value = str(outcome.get("outcome") or "").strip()
        if value not in OUTCOME_VALUES:
            value = "triage_failed"
        outcome["outcome"] = value
        # Required repair receipts/escalations are policy, not model choice.
        outcome["notify"] = value in NOTIFY_OUTCOMES
        outcome["impact"] = str(outcome.get("impact") or "low").lower()
        if outcome["impact"] not in {"low", "visible", "high"}:
            outcome["impact"] = "low"
        outcome.setdefault("summary", str(alert.get("summary") or _alert_ref(alert)))
        outcome.setdefault("reason", "Supervisor emitted structured outcome.")
        return outcome

    # Legacy/narrow fallback while old triage prompts age out: only explicit titles trigger email.
    clean = _clean_triage_text(triage_output)
    if "🚨 **PD One needs a decision**" in clean or "**Status:** Blocked after safe auto-triage" in clean:
        return {
            "outcome": "needs_input",
            "notify": True,
            "summary": str(alert.get("summary") or "PD One needs a decision"),
            "subject": "[PD Neo][Action needed] PD One supervisor needs input",
            "reason": "Supervisor output used the explicit decision-request escalation shape.",
            "notification_markdown": clean,
        }
    if "✅ **PD One auto-fixed an issue**" in clean or "**Status:** Fixed and verified" in clean:
        return {
            "outcome": "fixed",
            "notify": True,
            "impact": "low",
            "summary": str(alert.get("summary") or "PD One issue auto-fixed"),
            "subject": "[PD Neo][Auto-fixed] PD One issue recovered",
            "reason": "Supervisor output used the explicit auto-fixed notification shape.",
            "notification_markdown": clean,
        }
    return {
        "outcome": "triage_failed",
        "notify": True,
        "impact": "high",
        "summary": str(alert.get("summary") or "Supervisor triage returned no structured outcome"),
        "subject": "[PD Neo][Supervisor handoff failed] PD One triage was unstructured",
        "reason": "Supervisor output lacked the required structured outcome marker.",
        "notification_markdown": _supervisor_failed_markdown(
            alert,
            "Supervisor output lacked the required SUPERVISOR_OUTCOME_JSON marker.",
            triage_output,
        ),
    }


def _supervisor_failed_markdown(alert: dict[str, Any], error: str, triage_output: str = "", failed_path: str = "") -> str:
    alert = _redact_sensitive(alert)
    error = _redact_text(error)
    triage_output = _redact_text(triage_output)
    event_type = alert.get("event_type") or "unknown"
    source = alert.get("source") or "unknown"
    host = alert.get("host") or "unknown"
    lines = [
        "🚨 **PD One Supervisor handoff failed**",
        "",
        "**Status:** PD One could not complete Supervisor first-pass triage  ",
        f"**Event:** `{event_type}` from `{source}` on `{host}`  ",
        "**Impact:** The original automation event was preserved, but PD Neo/Supervisor did not complete judgment or repair.",
        "",
        "**What failed**",
        f"- {_summarize_supervisor_error(error)}",
        "",
        "**Original event summary**",
        *_summarize_original_event(alert),
        "",
        "**Retry status**",
        f"- Supervisor retry budget was exhausted after {SUPERVISOR_DEFER_ATTEMPTS} attempts or the max-age guard was reached.",
        "- The queue worker will continue processing future queued events; this failed event was saved for inspection.",
        "",
        "**Andy action needed**",
        "- No immediate production action is safe from this notification alone. Ask PD Neo to inspect the saved failed event if it repeats or if the original automation has not recovered.",
        "",
        "**Receipts**",
        f"- Event ref: `{_alert_ref(alert)}`",
    ]
    if failed_path:
        lines.append(f"- Saved failure: `{failed_path}`")
    if triage_output.strip():
        tail = triage_output.strip()[-1500:].replace("```", "`\u200b``")
        lines.extend(["", "**Triage output tail**", "```text", tail, "```"])
    return "\n".join(lines).strip() + "\n"


def supervisor_failed_outcome(alert: dict[str, Any], error: str, triage_output: str = "", failed_path: str = "") -> dict[str, Any]:
    return {
        "outcome": "supervisor_failed",
        "notify": True,
        "impact": "high",
        "summary": f"Supervisor handoff failed for {alert.get('source') or 'PD One event'}",
        "subject": "[PD Neo][Supervisor handoff failed] PD One event could not be triaged",
        "reason": _summarize_supervisor_error(error),
        "notification_markdown": _supervisor_failed_markdown(alert, error, triage_output, failed_path),
    }


def default_subject(outcome: dict[str, Any], alert: dict[str, Any]) -> str:
    if outcome.get("subject"):
        return str(outcome["subject"])[:180]
    source = str(alert.get("source") or "PD One")
    value = outcome.get("outcome")
    if value == "fixed":
        return f"[PD Neo][Auto-fixed] {source} recovered"[:180]
    if value == "needs_input":
        return f"[PD Neo][Action needed] {source} needs input"[:180]
    if value in {"supervisor_failed", "triage_failed"}:
        return "[PD Neo][Supervisor handoff failed] PD One event could not be triaged"
    return f"[PD Neo][Supervisor] {source} triage"[:180]


def record_outcome(alert: dict[str, Any], outcome: dict[str, Any], *, notification_result: dict[str, Any] | None = None) -> None:
    _private_dir(OUTCOME_LEDGER.parent)
    record = _redact_sensitive({
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "event_ref": _alert_ref(alert),
        "event_type": alert.get("event_type"),
        "source": alert.get("source"),
        "outcome": outcome.get("outcome"),
        "notify": bool(outcome.get("notify")),
        "impact": outcome.get("impact"),
        "summary": outcome.get("summary"),
        "reason": outcome.get("reason"),
        "notification_result": notification_result or {},
    })
    fd = os.open(OUTCOME_LEDGER, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    finally:
        os.chmod(OUTCOME_LEDGER, 0o600)


def _notification_correlation_key(alert: dict[str, Any]) -> str:
    text = " ".join(str(alert.get(k) or "") for k in ("source", "summary", "detail", "queue_reason")).lower()
    if "mattermost" in text and any(
        term in text
        for term in (
            "503",
            "name resolution",
            "dns",
            "connection refused",
            "unavailable",
            "connecttimeout",
            "timed out",
            "no route to host",
            "ehostunreach",
            "http 000",
        )
    ):
        return "dependency-outage:mattermost"
    if any(term in text for term in ("sheets.googleapis.com", "google oauth", "googleapis.com")) and any(term in text for term in ("name resolution", "dns", "connection")):
        return "dependency-outage:google-api"
    return str(alert.get("condition_key") or alert.get("source") or _alert_ref(alert))


def notification_route_for_outcome(outcome: dict[str, Any]) -> str:
    if outcome.get("outcome") == "fixed" and str(outcome.get("impact") or "low").lower() == "low":
        return RECEIPT_ROUTE
    return ESCALATION_ROUTE


def notification_route_has_pending(route: str) -> bool:
    path = NOTIFICATION_STATE_DIR / f"{route}.json"
    if not path.exists():
        return False
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        return bool(state.get("pending")) if isinstance(state, dict) else True
    except Exception:
        # Let the router surface malformed durable state instead of hiding it.
        return True


def deliver_route_notification(outcome: dict[str, Any], alert: dict[str, Any], *, log_path: str = "") -> dict[str, Any]:
    body = str(outcome.get("notification_markdown") or "").strip()
    if not body:
        body = _clean_triage_text(str(outcome.get("triage_output") or "")) or str(outcome.get("summary") or "PD One Supervisor notification")
    if log_path:
        body += f"\n\n- Saved failure: `{log_path}`"
    body = _redact_text(body)
    title = _redact_text(default_subject(outcome, alert))
    severity = "info" if outcome.get("outcome") == "fixed" else "error"
    route = notification_route_for_outcome(outcome)
    cmd = [
        *_router_base_cmd(),
        "send",
        "--config",
        str(Path(os.environ.get("PD_ONE_NOTIFICATION_ROUTES", "/home/prodesign/.hermes/config/notification-routes.json"))),
        "--state-dir",
        str(NOTIFICATION_STATE_DIR),
        "--route", route,
        "--event-id", _alert_ref(alert),
        "--correlation-key", _notification_correlation_key(alert),
        "--severity", severity,
        "--title", title,
        "--body", body,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=SUPERVISOR_DELIVERY_TIMEOUT_SECONDS, check=False)
    result_text = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
    try:
        payload = json.loads((proc.stdout or "{}").strip() or "{}")
    except json.JSONDecodeError:
        payload = {"raw": result_text[-2000:]}
    payload.update({"returncode": proc.returncode, "title": title, "route": route})
    if proc.returncode != 0:
        raise RuntimeError(f"notification router failed rc={proc.returncode}: {result_text[-1500:]}")
    return payload


def maybe_notify(outcome: dict[str, Any], alert: dict[str, Any], *, log_path: str = "") -> bool:
    if not outcome.get("notify"):
        record_outcome(alert, outcome)
        return True
    notification_result = deliver_route_notification(outcome, alert, log_path=log_path)
    record_outcome(alert, outcome, notification_result=notification_result)
    return True


def record_notification_failure(alert: dict[str, Any], outcome: dict[str, Any], exc: Exception) -> None:
    record_outcome(
        alert,
        outcome,
        notification_result={
            "status": "delivery_failed",
            "route": notification_route_for_outcome(outcome),
            "error": str(exc),
        },
    )


def main() -> int:
    fd = acquire_lock()
    if fd is None:
        return 0
    had_delivery_failure = False
    try:
        # Recheck the named route every worker tick. If the primary destination
        # recovered, the router emits one correlated recovery summary and
        # clears its durable outbox instead of replaying every child failure.
        if NOTIFICATION_ROUTER_PYTHON and Path(NOTIFICATION_ROUTER_PYTHON).is_file():
            for route in (ESCALATION_ROUTE, RECEIPT_ROUTE):
                if not notification_route_has_pending(route):
                    continue
                flush = subprocess.run(
                    [
                        *_router_base_cmd(),
                        "flush",
                        "--config",
                        str(Path(os.environ.get("PD_ONE_NOTIFICATION_ROUTES", "/home/prodesign/.hermes/config/notification-routes.json"))),
                        "--state-dir",
                        str(NOTIFICATION_STATE_DIR),
                        "--route",
                        route,
                    ],
                    text=True,
                    capture_output=True,
                    timeout=SUPERVISOR_DELIVERY_TIMEOUT_SECONDS,
                    check=False,
                )
                if flush.returncode != 0:
                    print(f"notification route flush failed ({route}): {(flush.stderr or flush.stdout)[-1000:]}", file=sys.stderr)
                    had_delivery_failure = True
        alerts = drain_queue()
        if not alerts:
            return 1 if had_delivery_failure else 0
        for alert in alerts[:MAX_ALERTS_PER_RUN]:
            failed_path = ""
            try:
                pending_outcome = alert.get("_pending_outcome")
                if isinstance(pending_outcome, dict):
                    outcome = pending_outcome
                else:
                    # Script-first first-pass (allowlist + thin xAI). No Hermes agent tools.
                    first = run_first_pass(alert)
                    if first.get("outcome") == "no_action" and not first.get("notify"):
                        ack_alert(alert)
                        continue
                    triage_output = str(
                        first.get("notification_markdown")
                        or first.get("offer")
                        or first.get("reason")
                        or ""
                    )
                    if first.get("model_used"):
                        import json as _json
                        triage_output = (
                            triage_output
                            + "\nSUPERVISOR_OUTCOME_JSON: "
                            + _json.dumps(
                                {
                                    "outcome": first.get("outcome"),
                                    "reason": first.get("reason") or "",
                                    "notify": bool(first.get("notify")),
                                },
                                ensure_ascii=False,
                            )
                        )
                    outcome = parse_supervisor_outcome(triage_output, alert)
                    if first.get("outcome"):
                        outcome["outcome"] = first.get("outcome")
                    if first.get("reason"):
                        outcome["reason"] = first.get("reason")
                    if first.get("notify"):
                        outcome["notify"] = True
                    if first.get("notification_markdown"):
                        outcome["notification_markdown"] = first["notification_markdown"]
                    outcome["triage_output"] = _clean_triage_text(triage_output)
                    if outcome.get("notify") and not outcome.get("notification_markdown"):
                        outcome["notification_markdown"] = outcome["triage_output"]
            except Exception as exc:
                error = str(exc)
                defer, deferred = _defer_supervisor_error(alert, error)
                if defer:
                    update_claim(alert, deferred)
                    continue
                _private_dir(FAILED_DIR)
                failed_file = FAILED_DIR / f"failed-{int(time.time())}.json"
                _write_private(
                    failed_file,
                    json.dumps(_redact_sensitive({"alert": alert, "error": error}), ensure_ascii=False, indent=2),
                )
                failed_path = str(failed_file)
                outcome = supervisor_failed_outcome(alert, error, failed_path=failed_path)
            try:
                maybe_notify(outcome, alert, log_path=failed_path)
                ack_alert(alert)
            except Exception as exc:  # noqa: BLE001 - surface notification rail failure to cron/supervisor
                had_delivery_failure = True
                print(
                    "PD One Supervisor notification delivery failed; preserved outcome locally.\n"
                    f"event_ref={_alert_ref(alert)} outcome={outcome.get('outcome')} error={exc}",
                    file=sys.stderr,
                )
                pending_alert = dict(alert)
                pending_alert["_pending_outcome"] = outcome
                try:
                    update_claim(alert, pending_alert)
                    record_notification_failure(alert, outcome, exc)
                except Exception as preserve_exc:
                    print(f"failed to persist notification retry state: {preserve_exc}", file=sys.stderr)
        # Overflow claims remain in PROCESSING_DIR and are picked up next tick.
        return 1 if had_delivery_failure else 0
    finally:
        release_lock(fd)


if __name__ == "__main__":
    raise SystemExit(main())

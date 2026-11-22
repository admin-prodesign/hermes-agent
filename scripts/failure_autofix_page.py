#!/usr/bin/env python3
"""Mattermost body for a failure-autofix needs-decision page.

The source event should pass ``findings``: a list of objects. Each object
uses ``kind``, ``unit`` or ``job_id``, ``error`` (the last error line), and
optionally ``action``, ``since``, and ``hit_count``. The same list may sit on
``automation_incident.findings``.

The self-heal monitor sends ``detail`` as the markdown report instead. Finding
bullets look like ``- **kind** `unit` — … last error: … Action: …`` and sit
under ``### Needs review / approval``. The parser accepts that bold and those
backticks, uses the ``last error:`` text (or the whole detail when it is
absent), and takes ``Action:`` as the action. The report header, ``Checked:``,
``Mode:``, ``Guardrails:``, and low-severity sections are ignored.
``hermes-deploy-drift.service`` still counts from a low-severity section.

``hermes-deploy-drift.service`` also stays on the page when the producer
parked it on ``suppressed_findings`` or ``downgraded_findings``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DRIFT_UNIT = "hermes-deploy-drift.service"
FINDING_CAP = 5
ERROR_LIMIT = 200
DETAIL_LIMIT = 500
SUMMARY_LIMIT = 200
_TAIPEI = ZoneInfo("Asia/Taipei")
_DEFAULT_STATE = Path(
    "/home/prodesign/.hermes/state/failure-autofix-admission/state.json"
)
_SECRET_NAME = (
    r"password|passwd|token|api[_-]?key|secret|authorization|"
    r"credential|access[_-]?key|private[_-]?key"
)
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")
_ASSIGN = re.compile(rf"(?i)\b({_SECRET_NAME})\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)")
_JSON_SECRET = re.compile(
    rf"(?i)([\"']?(?:{_SECRET_NAME})[\"']?\s*:\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)
_ENV = re.compile(
    r"(?i)\b(?:export\s+)?([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|"
    r"API_KEY|APIKEY|CREDENTIAL|AUTHORIZATION)[A-Z0-9_]*)\s*=\s*\S+"
)
_LINE = re.compile(
    r"^(?P<kind>[a-z][a-z0-9_]{2,})\s+"
    r"(?P<ident>.+?)\s+"
    r"[—–-]+\s+(?P<rest>.+)$"
)
_BULLET = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_BOLD_KIND = re.compile(r"^(?:\*\*|__)(?P<kind>[a-z][a-z0-9_]{2,})(?:\*\*|__)")
_TICK_IDENT = re.compile(r"^([a-z][a-z0-9_]{2,}\s+)`([^`]+)`")
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_META_LINE = re.compile(r"(?i)^(checked|mode|guardrails)\s*:")
_SKIP_HEADING = re.compile(
    r"(?i)\b(guardrail|low|info|informational|notice|healthy|resolved|"
    r"suppressed|downgraded|clean|passed|ok)\b"
)
_KEEP_HEADING = re.compile(
    r"(?i)(needs review|approval|action required|actionable|\berror\b|"
    r"\bcritical\b|\bfail)"
)
_LAST_ERROR = re.compile(r"(?i)\blast error:\s*")
_LEADING_MARK = re.compile(r"^[●•]\s*")
_UNIT_SUFFIXES = (".service", ".timer", ".socket", ".path")
_SAFE_UNIT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9@._:-]{0,120}$")
_GENERIC_OFFERS = (
    "signature is latched after a prior blocked repair",
    "do not re-burn llm",
    "approve a manual fix or clear the latch",
    "latched recurrence; approve manual action",
    "approve a bounded manual repair or extend the allowlist",
    "human decision required; do not auto-retry",
)
_SUPPRESSED_KEYS = ("suppressed_findings", "downgraded_findings", "paused_findings")
_NESTED_KEYS = ("automation_incident", "report")
_PROSE_KEYS = ("detail", "body", "message", "report")


@dataclass(frozen=True)
class Finding:
    kind: str
    unit: str
    job_id: str
    error: str
    action: str
    since: str
    hit_count: int | None


def redact(value: str) -> str:
    """Drop tokens, secret assignments, and env values before they hit a page."""
    text = "".join(ch for ch in str(value or "") if ch in "\n\t" or ord(ch) >= 32)
    text = _ENV.sub(r"\1=[REDACTED]", text)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    text = _ASSIGN.sub(r"\1\2[REDACTED]", text)
    text = _JSON_SECRET.sub(r"\1[REDACTED]", text)
    return text


def format_tpe(value: Any) -> str | None:
    """Format an epoch or ISO timestamp as ``YYYY-MM-DD HH:MM TPE``."""
    epoch = _epoch(value)
    if epoch is None:
        return None
    local = datetime.fromtimestamp(epoch, _TAIPEI)
    return local.strftime("%Y-%m-%d %H:%M TPE")


def latch_times_from_state(
    signature: str,
    state_path: Path | None = None,
) -> tuple[float | None, float | None]:
    """Return ``(last_verdict_at, unresolvable_until)`` for a latched signature."""
    if not str(signature or "").strip():
        return None, None
    path = state_path if state_path is not None else _state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, None
    signatures = data.get("signatures") if isinstance(data, dict) else None
    slot = signatures.get(signature) if isinstance(signatures, dict) else None
    if not isinstance(slot, dict):
        return None, None
    tried = _epoch(slot.get("last_verdict_at") or slot.get("last_llm_at"))
    until = _epoch(slot.get("unresolvable_until"))
    return tried, until


def collect_findings(alert: dict[str, Any]) -> list[Finding]:
    """Structured findings, plus drift rows the producer tried to park."""
    raw_items: list[Any] = []
    for container in _containers(alert):
        raw_items.extend(_finding_items(container.get("findings")))
        raw_items.extend(_finding_items(container.get("details")))
        for key in _SUPPRESSED_KEYS:
            for item in _finding_items(container.get(key)):
                if _item_is_drift(item):
                    raw_items.append(item)
    findings = _dedupe(_normalize_item(item) for item in raw_items)
    if findings:
        return findings
    return _dedupe(_findings_from_text(alert))


def concrete_decision(
    alert: dict[str, Any],
    *,
    reason: str,
    offer: str,
    signature: str,
) -> str:
    """One-line question derived from the finding, else a latch-clear question."""
    command = ""
    drift = ""
    for finding in collect_findings(alert):
        if _is_drift(finding):
            drift = drift or f"OK to inspect `{DRIFT_UNIT}`?"
            continue
        command = _reset_failed_decision(finding)
        if command:
            break
    if command:
        return command
    if drift:
        return drift
    if not _is_generic(offer):
        return _one_line(redact(offer), 240)
    if reason == "unresolvable_latched":
        shown = _one_line(redact(signature), 160)
        if shown:
            return f"OK to clear the latch for `{shown}`?"
        return "OK to clear the latch for this signature?"
    return "Approve a bounded manual repair or extend the allowlist."


def render_needs_decision_page(
    alert: dict[str, Any],
    *,
    reason: str,
    offer: str,
    signature: str = "",
    latch_tried_at: Any = None,
    latch_until: Any = None,
) -> tuple[str, str]:
    """Return ``(markdown, decision)``. Times are Asia/Taipei with a TPE label."""
    source = redact(str(alert.get("source") or "unknown"))
    decision = concrete_decision(alert, reason=reason, offer=offer, signature=signature)
    lines = [
        (
            "**Status:** Failure autofix needs a human decision "
            "(first-pass, no retry storm)"
        ),
        f"**Source:** `{source}`",
    ]
    findings = collect_findings(alert)
    if findings:
        lines.append("**Findings:**")
        lines.extend(_format_finding(item) for item in findings[:FINDING_CAP])
        extra = len(findings) - FINDING_CAP
        if extra > 0:
            lines.append(f"- +{extra} more")
    else:
        lines.extend(_summary_lines(alert))
    lines.append(f"**Decision:** {decision}")
    if reason == "unresolvable_latched":
        lines.append(f"**Latch:** {_latch_line(latch_tried_at, latch_until)}")
    return "\n".join(lines), decision


def _state_path() -> Path:
    env = os.environ.get("FAILURE_AUTOFIX_ADMISSION_STATE")
    if env:
        return Path(env)
    gate = sys.modules.get("failure_autofix_admission_gate")
    path = getattr(gate, "STATE_PATH", None) if gate is not None else None
    if isinstance(path, Path):
        return path
    return _DEFAULT_STATE


def _epoch(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            parsed = value.replace(tzinfo=UTC)
        else:
            parsed = value
        return parsed.timestamp()
    if isinstance(value, (int, float)):
        num = float(value)
        if num > 10_000_000_000:
            num /= 1000.0
        return num if num > 0 else None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.isdigit():
        return _epoch(int(text))
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def _containers(alert: dict[str, Any]) -> list[dict[str, Any]]:
    containers = [alert]
    for key in _NESTED_KEYS:
        nested = alert.get(key)
        if isinstance(nested, dict):
            containers.append(nested)
    return containers


def _finding_items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, (dict, str))]
    return []


def _item_is_drift(item: Any) -> bool:
    if isinstance(item, str):
        return DRIFT_UNIT in item
    if not isinstance(item, dict):
        return False
    for key in ("unit", "service", "job_id", "job", "id"):
        if str(item.get(key) or "").strip() == DRIFT_UNIT:
            return True
    return False


def _dedupe(items) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[str, str, str, str]] = set()
    for finding in items:
        if finding is None:
            continue
        ident = (finding.kind, finding.unit, finding.job_id, finding.error[:80])
        if ident in seen:
            continue
        seen.add(ident)
        findings.append(finding)
    return findings


def _normalize_item(item: Any) -> Finding | None:
    if isinstance(item, str):
        return _normalize_text(item)
    if isinstance(item, dict):
        return _normalize_dict(item)
    return None


def _normalize_dict(raw: dict[str, Any]) -> Finding | None:
    kind = str(raw.get("kind") or raw.get("type") or raw.get("class") or "").strip()
    unit = str(raw.get("unit") or raw.get("service") or "").strip()
    job_id = str(raw.get("job_id") or raw.get("job") or "").strip()
    if job_id == unit:
        job_id = ""
    error = str(raw.get("error") or raw.get("last_error") or raw.get("message") or "")
    action = str(raw.get("action") or raw.get("suggested_action") or "").strip()
    if not action:
        error, action = _split_action(error)
    since = str(
        raw.get("since")
        or raw.get("since_at")
        or raw.get("first_seen")
        or raw.get("failed_since")
        or ""
    ).strip()
    if not any((kind, unit, job_id, error, action)):
        return None
    return Finding(
        kind=kind or "finding",
        unit=unit,
        job_id=job_id,
        error=error.strip(),
        action=action,
        since=since,
        hit_count=_hit_count(raw),
    )


def _normalize_text(text: str) -> Finding | None:
    line = _unwrap_markdown(text)
    match = _LINE.match(line)
    if match is None:
        if DRIFT_UNIT in line:
            return Finding(
                kind="systemd_user_unit_failed",
                unit=DRIFT_UNIT,
                job_id="",
                error=line,
                action="",
                since="",
                hit_count=None,
            )
        return None
    ident = match.group("ident").strip()
    if not _ident_ok(match.group("kind"), ident):
        return None
    error, action = _error_and_action(match.group("rest"))
    unit, job_id = _split_ident(ident)
    return Finding(
        kind=match.group("kind"),
        unit=unit,
        job_id=job_id,
        error=error,
        action=action,
        since="",
        hit_count=None,
    )


def _unwrap_markdown(text: str) -> str:
    line = _BULLET.sub("", " ".join(text.split()))
    line = _BOLD_KIND.sub(r"\g<kind>", line, count=1)
    return _TICK_IDENT.sub(r"\1\2", line, count=1)


def _ident_ok(kind: str, ident: str) -> bool:
    if not ident or len(ident) > 160:
        return False
    if ident.endswith(_UNIT_SUFFIXES):
        return bool(_SAFE_UNIT.fullmatch(ident))
    if re.fullmatch(r"[0-9a-fA-F]{8,64}", ident):
        return True
    return "cron" in kind or "job" in kind


def _split_ident(ident: str) -> tuple[str, str]:
    if ident.endswith(_UNIT_SUFFIXES):
        return ident, ""
    return "", ident


def _split_action(text: str) -> tuple[str, str]:
    error, sep, action = text.partition("Action:")
    if not sep:
        return " ".join(text.split()), ""
    return " ".join(error.split()).rstrip("."), " ".join(action.split())


def _error_and_action(text: str) -> tuple[str, str]:
    """Prefer ``last error:``; otherwise keep the detail after the dash."""
    body, action = _split_action(text)
    body = _LEADING_MARK.sub("", body).strip()
    match = _LAST_ERROR.search(body)
    error = body[match.end() :].strip() if match else body
    return " ".join(error.split()).rstrip("."), action


def _hit_count(raw: dict[str, Any]) -> int | None:
    for key in ("hit_count", "hits", "hitCount"):
        if key not in raw:
            continue
        try:
            num = int(raw[key])
        except (TypeError, ValueError):
            return None
        return num if num >= 0 else None
    return None


def _findings_from_text(alert: dict[str, Any]) -> list[Finding | None]:
    found: list[Finding | None] = []
    for text in _prose_chunks(alert):
        parsed = _parse_json_blob(text)
        if isinstance(parsed, dict):
            found.extend(
                _normalize_item(item) for item in _finding_items(parsed.get("findings"))
            )
            continue
        if isinstance(parsed, list):
            found.extend(_normalize_item(item) for item in _finding_items(parsed))
            continue
        for line in _report_lines(text):
            found.append(_normalize_text(line))
    return found


def _heading_disposition(title: str) -> str:
    if _SKIP_HEADING.search(title):
        return "skip"
    if _KEEP_HEADING.search(title):
        return "keep"
    return "other"


def _report_lines(text: str) -> list[str]:
    """Finding bullets, skipping the report header and low-severity sections.

    Drift-check lines are kept from a skipped section so a paused autodeploy
    cannot hide ``hermes-deploy-drift.service``.
    """
    raw = [line.strip() for line in text.splitlines() if line.strip()]
    if not raw and text.strip():
        raw = [text.strip()]
    titles = [_HEADING.match(line).group(1) for line in raw if _HEADING.match(line)]
    only_keep = any(_heading_disposition(title) == "keep" for title in titles)
    section = "preamble"
    chosen: list[str] = []
    for line in raw:
        heading = _HEADING.match(line)
        if heading:
            section = _heading_disposition(heading.group(1))
            continue
        if _META_LINE.match(line):
            continue
        visible = section != "skip" and (not only_keep or section == "keep")
        if visible or DRIFT_UNIT in line:
            chosen.append(line)
    return chosen


def _prose_chunks(alert: dict[str, Any]) -> list[str]:
    chunks: list[str] = []
    for container in _containers(alert):
        for key in _PROSE_KEYS:
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                chunks.append(value)
    return chunks


def _parse_json_blob(text: str) -> Any:
    stripped = text.strip()
    if not stripped.startswith("{") and not stripped.startswith("["):
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _is_drift(finding: Finding) -> bool:
    return finding.unit == DRIFT_UNIT or finding.job_id == DRIFT_UNIT


def _safe_unit(unit: str) -> bool:
    return bool(_SAFE_UNIT.fullmatch(unit)) and unit.endswith(_UNIT_SUFFIXES)


def _reset_failed_decision(finding: Finding) -> str:
    unit = finding.unit
    if not _safe_unit(unit):
        return ""
    blob = f"{finding.kind} {finding.action} {finding.error}".lower()
    wants_reset = (
        finding.kind == "systemd_user_unit_failed"
        or "reset-failed" in blob
        or "reset/restart" in blob
    )
    if not wants_reset:
        return ""
    return f"OK to `systemctl --user reset-failed {unit}`?"


def _is_generic(offer: str) -> bool:
    text = " ".join(str(offer or "").lower().split())
    if not text:
        return True
    return any(snippet in text for snippet in _GENERIC_OFFERS)


def _one_line(text: str, limit: int) -> str:
    collapsed = " ".join(str(text or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1] + "…"


def _summary_lines(alert: dict[str, Any]) -> list[str]:
    summary = _one_line(
        redact(str(alert.get("summary") or alert.get("title") or "")),
        SUMMARY_LIMIT,
    )
    lines = [f"**Summary:** {summary}"] if summary else []
    detail = _fallback_detail(alert, summary)
    if detail:
        lines.append(f"**Detail:** {detail}")
    return lines


def _fallback_detail(alert: dict[str, Any], summary: str) -> str:
    parts: list[str] = []
    for text in _prose_chunks(alert):
        cleaned = _one_line(redact(text), DETAIL_LIMIT)
        if cleaned and cleaned != summary and cleaned not in parts:
            parts.append(cleaned)
    return _one_line(" ".join(parts), DETAIL_LIMIT)


def _format_finding(finding: Finding) -> str:
    kind = redact(finding.kind) or "finding"
    target = finding.unit or finding.job_id
    target_bit = f" `{redact(target)}`" if target else ""
    error = _one_line(redact(finding.error), ERROR_LIMIT)
    error_bit = f" — {error}" if error else ""
    extras: list[str] = []
    since = format_tpe(finding.since)
    if since:
        extras.append(f"since {since}")
    if finding.hit_count:
        noun = "hit" if finding.hit_count == 1 else "hits"
        extras.append(f"{finding.hit_count} {noun}")
    extra_bit = f" ({', '.join(extras)})" if extras else ""
    return f"- `{kind}`{target_bit}{error_bit}{extra_bit}"


def _latch_line(tried: Any, until: Any) -> str:
    tried_s = format_tpe(tried)
    until_s = format_tpe(until)
    if tried_s and until_s:
        return (
            f"Already tried once at {tried_s}; "
            f"not retrying automatically until {until_s}."
        )
    if tried_s:
        return f"Already tried once at {tried_s}; not retrying automatically."
    if until_s:
        return f"Not retrying automatically until {until_s}."
    return "Already tried once; not retrying automatically until the latch expires."

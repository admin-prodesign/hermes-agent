"""Failed units, failing cron jobs, PD One escalation files, Bitwarden 503s."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Callable, Iterable

from scripts.deploy.nemo.watchdogs.common import (
    Finding,
    hermes_home,
    resolve_under_home,
    run_check,
    run_cmd,
)

NAME = "failures"
DEFAULT_REPAIRER = "profiles/pdone/state/repairer-escalation.json"
DEFAULT_SUPERVISOR = "profiles/pdone/state/supervisor-escalation.json"
_BWS_RE = re.compile(r"\b(bws|bitwarden)\b", re.I)
_503_RE = re.compile(r"\b503\b|service unavailable", re.I)
_BAD_STATUS = frozenset(
    {"escalated", "escalate", "escalate_only", "critical", "page", "paging", "failed"}
)
_BAD_SEV = frozenset({"high", "critical", "crit"})
Runner = Callable[..., object]


def _ignore_units() -> set[str]:
    raw = os.environ.get("NEMO_WATCH_IGNORE_UNITS", "")
    return {part.strip() for part in raw.split(",") if part.strip()}


def _sysctl_env(user: bool) -> dict[str, str]:
    env = dict(os.environ)
    if user:
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return env


def failed_units(runner: Runner | None = None) -> list[Finding]:
    run = runner or run_cmd
    ignore = _ignore_units()
    findings: list[Finding] = []
    for user in (False, True):
        extra = ["--user"] if user else []
        proc = run(
            ["systemctl", *extra, "--failed", "--no-legend", "--plain", "--no-pager"],
            timeout=10,
            env=_sysctl_env(user),
        )
        stdout = getattr(proc, "stdout", "") or ""
        scope = "user" if user else "system"
        for line in stdout.splitlines():
            unit = line.split()[0] if line.strip() else ""
            if not unit or unit in ignore:
                continue
            findings.append(
                Finding(
                    f"unit:{scope}:{unit}",
                    "warn",
                    "systemd unit failed",
                    {"unit": unit, "scope": scope},
                )
            )
    return findings


def _jobs_from_file(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        jobs = data.get("jobs", [])
    elif isinstance(data, list):
        jobs = data
    else:
        return []
    return [job for job in jobs if isinstance(job, dict)]


def cron_job_files(home: Path) -> list[tuple[str, Path]]:
    found = [("default", home / "cron" / "jobs.json")]
    profiles = home / "profiles"
    if not profiles.is_dir():
        return found
    for child in sorted(profiles.iterdir()):
        if child.is_dir():
            found.append((child.name, child / "cron" / "jobs.json"))
    return found


def failing_cron_jobs(home: Path | None = None) -> list[Finding]:
    root = home or hermes_home()
    findings: list[Finding] = []
    for profile, path in cron_job_files(root):
        for job in _jobs_from_file(path):
            if not job.get("enabled", True):
                continue
            streak = int(job.get("failure_streak") or 0)
            if streak <= 0:
                continue
            job_id = str(job.get("id") or "unknown")
            findings.append(
                Finding(
                    f"cron:{profile}:{job_id}",
                    "warn",
                    "enabled cron job failing",
                    {"profile": profile, "job": job_id, "failure_streak": streak},
                )
            )
    return findings


def _record_escalated(data: dict) -> bool:
    if data.get("escalated") is True or data.get("escalate") is True:
        return True
    if data.get("notify_now") or data.get("notify_now_default"):
        return True
    status = str(data.get("status") or "").lower()
    if status in _BAD_STATUS:
        return True
    severity = str(data.get("severity") or data.get("impact") or "").lower()
    return severity in _BAD_SEV


def _escalation_records(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    if path.suffix == ".jsonl":
        rows: list[dict] = []
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _escalation_paths(home: Path) -> list[tuple[str, Path]]:
    repairer = os.environ.get("NEMO_WATCH_PDONE_REPAIRER_STATE", DEFAULT_REPAIRER)
    supervisor = os.environ.get("NEMO_WATCH_PDONE_SUPERVISOR_STATE", DEFAULT_SUPERVISOR)
    extra = os.environ.get("NEMO_WATCH_PDONE_ESCALATION_PATHS", "")
    named = [("repairer", repairer), ("supervisor", supervisor)]
    for item in extra.split(":"):
        if item.strip():
            named.append((Path(item).name, item.strip()))
    return [(label, resolve_under_home(raw, home)) for label, raw in named]


def pdone_escalations(home: Path | None = None) -> list[Finding]:
    root = home or hermes_home()
    findings: list[Finding] = []
    for label, path in _escalation_paths(root):
        targets = [path]
        if path.is_dir():
            targets = sorted(path.glob("*.json")) + sorted(path.glob("*.jsonl"))
        for target in targets:
            if not target.is_file():
                continue
            if any(_record_escalated(row) for row in _escalation_records(target)):
                findings.append(
                    Finding(
                        f"pdone:{label}",
                        "warn",
                        "PD One escalation state is active",
                        {"source": label, "kind": target.suffix.lstrip(".") or "file"},
                    )
                )
    return findings


def is_bws_503(line: str) -> bool:
    return bool(_BWS_RE.search(line) and _503_RE.search(line))


def bitwarden_503s(lines: Iterable[str], *, source: str) -> list[Finding]:
    count = sum(1 for line in lines if is_bws_503(line))
    if count <= 0:
        return []
    return [
        Finding(
            f"bws503:{source}",
            "warn",
            "Bitwarden Secrets Manager 503s",
            {"source": source, "count": count},
        )
    ]


def journal_lines(runner: Runner | None = None, minutes: int = 15) -> list[str]:
    run = runner or run_cmd
    since = f"{minutes} min ago"
    lines: list[str] = []
    for extra in ([], ["--user"]):
        proc = run(
            ["journalctl", *extra, "--since", since, "--no-pager", "-o", "cat"],
            timeout=15,
        )
        stdout = getattr(proc, "stdout", "") or ""
        lines.extend(stdout.splitlines())
    return lines


def recent_log_lines(home: Path, *, minutes: int = 15, clock: Callable[[], float] | None = None) -> list[str]:
    logs = home / "logs"
    if not logs.is_dir():
        return []
    cutoff = (clock or time.time)() - minutes * 60
    lines: list[str] = []
    for path in logs.rglob("*"):
        try:
            if not path.is_file() or path.stat().st_mtime < cutoff:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines.extend(text.splitlines()[-400:])
    return lines


def collect(
    *,
    home: Path | None = None,
    runner: Runner | None = None,
    journal: list[str] | None = None,
    logs: list[str] | None = None,
) -> list[Finding]:
    root = home or hermes_home()
    lookback = int(os.environ.get("NEMO_WATCH_BWS_LOOKBACK_MIN", "15"))
    journal_src = journal if journal is not None else journal_lines(runner, lookback)
    log_src = logs if logs is not None else recent_log_lines(root, minutes=lookback)
    return [
        *failed_units(runner),
        *failing_cron_jobs(root),
        *pdone_escalations(root),
        *bitwarden_503s(journal_src, source="journal"),
        *bitwarden_503s(log_src, source="logs"),
    ]


def main() -> int:
    return run_check(NAME, collect)


if __name__ == "__main__":
    raise SystemExit(main())

"""PD One Ops dashboard plugin backend.

Read-only MVP mounted at /api/plugins/pd-one-ops/.
It summarizes PD One profile operational assets without exposing secrets or
mutating source systems.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter()

PDONE_HOME = Path("/home/prodesign/.hermes/profiles/pdone")
SENSITIVE_PARTS = {
    ".env", "auth.json", "credentials", "tokens", "policy-cache",
    "sessions", "logs", "tmp", "work",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(PDONE_HOME))
    except Exception:
        return str(path)


def _schedule_display(job: dict[str, Any]) -> str:
    sched = job.get("schedule")
    if isinstance(sched, dict):
        return str(sched.get("display") or sched.get("expr") or job.get("schedule_display") or "")
    return str(job.get("schedule_display") or sched or "")


def _cron_jobs() -> list[dict[str, Any]]:
    raw = _read_json(PDONE_HOME / "cron" / "jobs.json", {"jobs": []})
    jobs = raw.get("jobs", []) if isinstance(raw, dict) else []
    out: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        out.append({
            "id": job.get("id"),
            "name": job.get("name") or job.get("id"),
            "enabled": bool(job.get("enabled")),
            "state": job.get("state"),
            "schedule": _schedule_display(job),
            "deliver": job.get("deliver"),
            "script": job.get("script"),
            "no_agent": bool(job.get("no_agent")),
            "last_status": job.get("last_status"),
            "last_run_at": job.get("last_run_at"),
            "next_run_at": job.get("next_run_at"),
            "last_delivery_error": job.get("last_delivery_error"),
            "paused_reason": job.get("paused_reason"),
            "skills": job.get("skills") or ([] if not job.get("skill") else [job.get("skill")]),
        })
    return out


def _supervisor_entries() -> list[dict[str, Any]]:
    raw = _read_json(PDONE_HOME / "supervisor" / "automations.json", {"automations": []})
    entries = raw.get("automations", []) if isinstance(raw, dict) else []
    out: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        autorepair = item.get("autorepair") if isinstance(item.get("autorepair"), dict) else {}
        sup = item.get("supervisor") if isinstance(item.get("supervisor"), dict) else {}
        out.append({
            "id": item.get("id"),
            "job_id": item.get("job_id"),
            "name": item.get("name") or item.get("id"),
            "source": item.get("source"),
            "criticality": item.get("criticality"),
            "touches_external_systems": bool(item.get("touches_external_systems")),
            "alert_expectation": item.get("alert_expectation"),
            "autorepair": autorepair.get("classification"),
            "wrapper_script": sup.get("wrapper_script"),
        })
    return out


def _skills() -> list[dict[str, Any]]:
    root = PDONE_HOME / "skills"
    out: list[dict[str, Any]] = []
    if not root.exists():
        return out
    for path in sorted(root.rglob("SKILL.md")):
        if set(path.parts) & SENSITIVE_PARTS:
            continue
        parent_rel = path.parent.relative_to(root)
        category = parent_rel.parts[0] if len(parent_rel.parts) > 1 else "uncategorized"
        description = ""
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:3000]
            for line in text.splitlines():
                if line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"')[:240]
                    break
        except Exception:
            pass
        out.append({
            "name": path.parent.name,
            "category": category,
            "path": _safe_rel(path),
            "description": description,
        })
    return out


def _policy_files() -> list[dict[str, Any]]:
    root = PDONE_HOME / "policies"
    out: list[dict[str, Any]] = []
    if not root.exists():
        return out
    for path in sorted(root.iterdir()):
        if path.is_file() and path.suffix in {".md", ".json", ".yaml", ".yml"}:
            out.append({"name": path.name, "path": _safe_rel(path), "size": path.stat().st_size})
    return out


def _scripts() -> list[dict[str, Any]]:
    root = PDONE_HOME / "scripts"
    out: list[dict[str, Any]] = []
    if not root.exists():
        return out
    for path in sorted(root.iterdir()):
        if path.is_file() and path.suffix in {".py", ".sh", ".bash"}:
            out.append({"name": path.name, "path": _safe_rel(path), "size": path.stat().st_size})
    return out


def _drift(cron_jobs: list[dict[str, Any]], sup_entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    cron_ids = {str(j.get("id")) for j in cron_jobs if j.get("id")}
    sup_job_ids = {str(s.get("job_id")) for s in sup_entries if s.get("job_id")}
    for job in cron_jobs:
        jid = str(job.get("id") or "")
        if jid and jid not in sup_job_ids and job.get("enabled"):
            issues.append({
                "severity": "medium",
                "kind": "cron-unregistered",
                "item": jid,
                "message": f"Enabled cron job lacks supervisor registry entry: {job.get('name')}",
            })
        if job.get("last_delivery_error"):
            issues.append({
                "severity": "high",
                "kind": "delivery-error",
                "item": jid,
                "message": f"Last delivery error: {job.get('last_delivery_error')}",
            })
        if job.get("enabled") and not job.get("script") and not job.get("skills"):
            issues.append({
                "severity": "low",
                "kind": "prompt-job-no-skill",
                "item": jid,
                "message": f"Enabled prompt job has no attached skill: {job.get('name')}",
            })
    for item in sup_entries:
        jid = str(item.get("job_id") or "")
        if jid and jid not in cron_ids:
            issues.append({
                "severity": "low",
                "kind": "supervisor-orphan",
                "item": jid,
                "message": f"Supervisor entry points to missing cron job: {item.get('name')}",
            })
    return issues[:200]


@router.get("/summary")
async def summary() -> dict[str, Any]:
    cron_jobs = _cron_jobs()
    sup_entries = _supervisor_entries()
    skills = _skills()
    policies = _policy_files()
    scripts = _scripts()
    drift = _drift(cron_jobs, sup_entries)
    counts = {
        "cron_total": len(cron_jobs),
        "cron_enabled": sum(1 for j in cron_jobs if j.get("enabled")),
        "cron_paused": sum(1 for j in cron_jobs if not j.get("enabled") or j.get("state") == "paused"),
        "cron_errors": sum(1 for j in cron_jobs if j.get("last_status") not in (None, "ok")),
        "supervisor_total": len(sup_entries),
        "supervisor_external": sum(1 for s in sup_entries if s.get("touches_external_systems")),
        "skills_total": len(skills),
        "policies_total": len(policies),
        "scripts_total": len(scripts),
        "drift_total": len(drift),
        "drift_high": sum(1 for d in drift if d.get("severity") == "high"),
    }
    category_counts = Counter(s.get("category") or "uncategorized" for s in skills)
    criticality_counts = Counter(s.get("criticality") or "unknown" for s in sup_entries)
    return {
        "ok": True,
        "generated_at": _now(),
        "profile_home": str(PDONE_HOME),
        "counts": counts,
        "skills_by_category": dict(category_counts.most_common()),
        "supervisor_by_criticality": dict(criticality_counts.most_common()),
        "cron_jobs": cron_jobs,
        "supervisor": sup_entries,
        "skills": skills[:300],
        "policies": policies,
        "scripts": scripts[:300],
        "drift": drift,
    }

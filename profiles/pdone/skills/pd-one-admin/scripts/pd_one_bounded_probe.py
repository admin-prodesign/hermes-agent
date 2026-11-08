#!/usr/bin/env python3
"""Bounded PD One/OpenClaw admin probes for Hermes/PD Neo.

This script intentionally uses small deterministic reads and never restarts
OpenClaw. It is designed for live chat/admin paths where broad diagnostics can
pressure the gateway.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path("/home/prodesign/.openclaw/workspace")
OPENCLAW = Path("/home/prodesign/.npm-global/bin/openclaw")
HERMES_BACKUP = Path("/home/prodesign/hermes-backup")

SECRET_KEYS = {"token", "api_key", "apikey", "secret", "password", "authorization"}
SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.I),
    re.compile(r"(gh[opsu]_[A-Za-z0-9_]{8})[A-Za-z0-9_]+"),
    re.compile(r"([A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.)[A-Za-z0-9_-]+"),
]


def redact_text(text: str) -> str:
    out = text
    for pat in SECRET_PATTERNS:
        out = pat.sub(r"\1…REDACTED", out)
    return out


def redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: ("REDACTED" if k.lower() in SECRET_KEYS else redact_json(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_json(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 20,
    stdout_limit: int | None = 12000,
) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or WORKSPACE),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        stdout = proc.stdout if stdout_limit is None else proc.stdout[-stdout_limit:]
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": redact_text(stdout),
            "stderr": redact_text(proc.stderr[-4000:]),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "timeout": timeout,
            "stdout": redact_text((exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else ""),
            "stderr": redact_text((exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else ""),
        }


def health() -> dict[str, Any]:
    result = run([str(OPENCLAW), "health", "--json"], timeout=30, stdout_limit=None)
    parsed: dict[str, Any] | None = None
    if result["ok"] and result["stdout"].strip():
        try:
            parsed = json.loads(result["stdout"])
        except json.JSONDecodeError:
            parsed = None
    if parsed is None:
        return {"probe": "health", "command_ok": result["ok"], "error": result["stderr"] or result["stdout"][:2000]}

    data = redact_json(parsed)
    channels = data.get("channels", {}) if isinstance(data, dict) else {}
    channel_summary = {}
    for name, ch in channels.items():
        if not isinstance(ch, dict):
            continue
        channel_summary[name] = {
            "enabled": ch.get("enabled"),
            "configured": ch.get("configured"),
            "running": ch.get("running"),
            "connected": ch.get("connected"),
            "lastError": ch.get("lastError"),
            "restartPending": ch.get("restartPending"),
        }
    plugins = data.get("plugins", {}) if isinstance(data, dict) else {}
    event_loop = data.get("eventLoop", {}) if isinstance(data, dict) else {}
    return {
        "probe": "health",
        "ok": data.get("ok"),
        "durationMs": data.get("durationMs"),
        "eventLoop": {
            "degraded": event_loop.get("degraded"),
            "reasons": event_loop.get("reasons"),
            "delayP99Ms": event_loop.get("delayP99Ms"),
            "delayMaxMs": event_loop.get("delayMaxMs"),
            "utilization": event_loop.get("utilization"),
            "cpuCoreRatio": event_loop.get("cpuCoreRatio"),
        },
        "plugins": {
            "loaded": plugins.get("loaded"),
            "errors": plugins.get("errors"),
        },
        "channels": channel_summary,
        "defaultAgentId": data.get("defaultAgentId"),
        "agentCount": len(data.get("agents", [])) if isinstance(data.get("agents"), list) else None,
    }


def triage() -> dict[str, Any]:
    commands = {
        "uptime": ["uptime"],
        "top_cpu": ["bash", "-lc", "ps -eo pid,ppid,comm,%cpu,%mem,etime,args --sort=-%cpu | head -12"],
        "top_mem": ["bash", "-lc", "ps -eo pid,ppid,comm,%cpu,%mem,rss,etime,args --sort=-%mem | head -12"],
        "disk": ["bash", "-lc", "df -h / /home /tmp 2>/dev/null"],
        "psi": ["bash", "-lc", "for f in /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io; do echo -- $f; cat $f; done"],
    }
    return {name: run(cmd, timeout=10) for name, cmd in commands.items()}


def logs(limit: int, max_bytes: int) -> dict[str, Any]:
    limit = max(1, min(limit, 300))
    max_bytes = max(1000, min(max_bytes, 200_000))
    return run(
        [str(OPENCLAW), "logs", "--limit", str(limit), "--plain", "--timeout", "10000", "--max-bytes", str(max_bytes)],
        timeout=20,
    )


def backup_status() -> dict[str, Any]:
    status: dict[str, Any] = {}
    if HERMES_BACKUP.exists():
        status["hermes_backup"] = run(["git", "status", "--short", "--branch"], cwd=HERMES_BACKUP, timeout=10)
    else:
        status["hermes_backup"] = {"ok": False, "error": f"missing {HERMES_BACKUP}"}
    status["hermes_source"] = run(["git", "status", "--short", "--branch"], cwd=Path(os.environ.get('HERMES_AGENT_DIR', '/home/prodesign/.hermes/runtime/current')), timeout=10)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded PD One/OpenClaw admin probe")
    parser.add_argument("--triage", action="store_true", help="include safe CPU/memory/disk/PSI triage")
    parser.add_argument("--logs", action="store_true", help="include a bounded OpenClaw log tail")
    parser.add_argument("--log-limit", type=int, default=120)
    parser.add_argument("--log-max-bytes", type=int, default=120000)
    parser.add_argument("--backup-status", action="store_true", help="include git status of Hermes backup/source repos")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text summary")
    args = parser.parse_args()

    report: dict[str, Any] = {"workspace": str(WORKSPACE), "health": health()}
    if args.triage:
        report["triage"] = triage()
    if args.logs:
        report["logs"] = logs(args.log_limit, args.log_max_bytes)
    if args.backup_status:
        report["backup_status"] = backup_status()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    h = report["health"]
    print("PD One bounded probe")
    print(f"- workspace: {report['workspace']}")
    print(f"- health ok: {h.get('ok')} durationMs={h.get('durationMs')}")
    ev = h.get("eventLoop") or {}
    print(f"- event loop degraded: {ev.get('degraded')} reasons={ev.get('reasons')}")
    print(f"- channels: {json.dumps(h.get('channels'), ensure_ascii=False)}")
    plugins = h.get("plugins") or {}
    print(f"- plugin errors: {plugins.get('errors')}")
    if args.triage:
        print("\nTriage excerpts:")
        for name, res in report["triage"].items():
            print(f"\n## {name} rc={res.get('returncode')}")
            print((res.get("stdout") or res.get("stderr") or "").strip()[:2500])
    if args.logs:
        res = report["logs"]
        print(f"\nLogs rc={res.get('returncode')} ok={res.get('ok')}")
        print((res.get("stdout") or res.get("stderr") or "").strip()[:4000])
    if args.backup_status:
        print("\nBackup/source status:")
        for name, res in report["backup_status"].items():
            print(f"\n## {name}")
            print((res.get("stdout") or res.get("stderr") or str(res)).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

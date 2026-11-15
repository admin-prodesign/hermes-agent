#!/usr/bin/env python3
"""First-pass auto-repair for pd-one / pd-neo failure-autofix.

Order (must not burn a model before script-first work):
1. Cheap admission reject (no_agent / below-severity / last-fix-still-green / latch)
2. Allowlist executor (zero model) + one verify
3. At most one thin direct-xAI call per signature cooldown (no Hermes tools)
4. Always silence the Hermes agent webhook path (__hermes_ignore__)

Queue workers call run_first_pass() and consume the structured result.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from failure_autofix_admission_gate import (
    cheap_reject,
    decide,
    record_verdict,
    should_page_recurrence,
)
from failure_autofix_allowlist import try_allowlist_repair
from failure_autofix_thin_llm import run_thin_llm

RECEIPT_PATH = Path(
    os.environ.get(
        "FAILURE_AUTOFIX_FIRST_PASS_RECEIPTS",
        "/home/prodesign/.hermes/state/failure-autofix-admission/first_pass.jsonl",
    )
)
NOTIFICATION_ROUTER = Path("/home/prodesign/.hermes/scripts/pd_one_notification_router.py")
HERMES_AGENT = Path(os.environ.get("HERMES_AGENT_DIR", "/home/prodesign/.hermes/runtime/current"))
NOTIFICATION_ROUTER_PYTHON = str(HERMES_AGENT / ".venv/bin/python")
ESCALATION_ROUTE = "pd_one_failure_escalations"


def _append_receipt(row: dict[str, Any]) -> None:
    try:
        RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _offer_markdown(alert: dict[str, Any], *, reason: str, offer: str) -> str:
    source = str(alert.get("source") or "unknown")
    summary = str(alert.get("summary") or alert.get("title") or "")[:200]
    lines = [
        "**Status:** Failure autofix needs a human decision (first-pass, no retry storm)",
        f"**Source:** `{source}`",
        f"**Summary:** {summary}",
        f"**Why automation stopped:** {reason}",
        f"**Concrete offer:** {offer or 'Approve a bounded manual repair or extend the allowlist.'}",
    ]
    return "\n".join(lines)


def _maybe_page(alert: dict[str, Any], markdown: str) -> dict[str, Any]:
    """Best-effort named-route page; never raises into the repair path."""
    if not Path(NOTIFICATION_ROUTER_PYTHON).is_file() and not Path(NOTIFICATION_ROUTER).is_file():
        return {"status": "skipped", "reason": "router_missing"}
    event = str(alert.get("event_type") or "")
    if event.startswith("pd-neo."):
        return {"status": "skipped", "reason": "pd_neo_surface"}
    source = str(alert.get("source") or "unknown")
    run_id = str(alert.get("run_id") or int(time.time()))
    event_id = f"failure-autofix-page:{source}:{run_id}"[:180]
    title = f"Failure autofix needs decision: {source}"[:120]
    python_bin = NOTIFICATION_ROUTER_PYTHON if Path(NOTIFICATION_ROUTER_PYTHON).is_file() else sys.executable
    try:
        proc = subprocess.run(
            [
                python_bin,
                "-m",
                "scripts.pd_one_notification_router",
                "send",
                "--config",
                str(Path(os.environ.get("PD_ONE_NOTIFICATION_ROUTES", "/home/prodesign/.hermes/config/notification-routes.json"))),
                "--state-dir",
                str(Path(os.environ.get("PD_ONE_NOTIFICATION_STATE_DIR", "/home/prodesign/.hermes/state/notification-router"))),
                "--route",
                ESCALATION_ROUTE,
                "--event-id",
                event_id,
                "--correlation-key",
                f"failure-autofix:{source}",
                "--severity",
                "error",
                "--title",
                title,
                "--body",
                markdown,
            ],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        return {
            "status": "ok" if proc.returncode == 0 else "failed",
            "rc": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-500:],
            "stderr_tail": (proc.stderr or "")[-500:],
        }
    except Exception as exc:
        return {"status": "failed", "error": type(exc).__name__}



def run_first_pass(
    alert: dict[str, Any],
    *,
    now: float | None = None,
    force: bool = False,
    thin_llm_fn=None,
    allowlist_fn=None,
) -> dict[str, Any]:
    """Execute script-first then optional thin LLM. Never invokes Hermes tools."""
    now = time.time() if now is None else now
    force = force or bool(alert.get("force_agent"))
    allowlist_fn = allowlist_fn or try_allowlist_repair
    thin_llm_fn = thin_llm_fn or run_thin_llm

    result: dict[str, Any] = {
        "path": "first_pass",
        "model_used": False,
        "hermes_agent": False,
        "ok": False,
        "outcome": "no_action",
        "reason": "",
        "offer": "",
        "notify": False,
        "admission": {},
        "allowlist": {},
        "thin_llm": {},
        "page": {},
    }

    # 1) Cheap reject that skips allowlist only for pure noise / below severity.
    # Latched signatures still get an allowlist attempt (zero model).
    if not force:
        failure_probe = cheap_reject(alert, now=now)
        if failure_probe and failure_probe.reason in {
            "no_agent_noise",
            "below_severity",
            "last_fix_still_green",
        }:
            result["admission"] = failure_probe.as_dict()
            result["reason"] = failure_probe.reason
            result["outcome"] = "no_action"
            _append_receipt({"ts": int(now), "source": alert.get("source"), **result})
            return result

    # 2) Allowlist first (zero model) — including when latched.
    allowlist = allowlist_fn(alert, force=force)
    result["allowlist"] = {
        "status": allowlist.get("status"),
        "target": allowlist.get("target"),
        "ok": allowlist.get("ok"),
        "offer": allowlist.get("offer") or "",
    }
    if allowlist.get("ok"):
        record_verdict(alert, "fixed", text=f"allowlist:{allowlist.get('target')}", now=now)
        result["ok"] = True
        result["outcome"] = "fixed"
        result["reason"] = f"allowlist repaired {allowlist.get('target')}"
        result["admission"] = {"invoke_agent": False, "reason": "allowlist_fixed"}
        _append_receipt({"ts": int(now), "source": alert.get("source"), **result})
        return result

    if allowlist.get("status") in {"repair_failed", "verify_failed"}:
        # Verify-once contract: stop, one concrete offer, no retry storm / no LLM burn.
        offer = str(allowlist.get("offer") or "")
        record_verdict(alert, "needs_input", text=offer, now=now)
        result["outcome"] = "needs_input"
        result["reason"] = str(allowlist.get("status"))
        result["offer"] = offer
        result["notify"] = True
        md = _offer_markdown(alert, reason=result["reason"], offer=offer)
        result["notification_markdown"] = md
        # Record latch first (above); page at most once per recurrence cooldown.
        if should_page_recurrence(alert, now=now):
            result["page"] = _maybe_page(alert, md)
        else:
            # First latch page: should_page_recurrence returns True after setting last_page_at.
            # If it returned False (race), still attach markdown for queue worker notify.
            result["page"] = {"status": "deferred_to_queue_or_cooldown"}
        result["admission"] = {"invoke_agent": False, "reason": "allowlist_verify_stop"}
        _append_receipt({"ts": int(now), "source": alert.get("source"), **result})
        return result

    # 3) Latched / cooldown / holds — no model; maybe page recurrence.
    pre = cheap_reject(alert, now=now)
    if pre and pre.reason == "unresolvable_latched" and not force:
        result["admission"] = pre.as_dict()
        result["outcome"] = "unresolvable"
        result["reason"] = "unresolvable_latched"
        result["offer"] = (
            "Signature is latched after a prior blocked repair. "
            "Do not re-burn LLM. Approve a manual fix or clear the latch."
        )
        if should_page_recurrence(alert, now=now):
            result["notify"] = True
            md = _offer_markdown(alert, reason=result["reason"], offer=result["offer"])
            result["page"] = _maybe_page(alert, md)
            result["notification_markdown"] = md
        _append_receipt({"ts": int(now), "source": alert.get("source"), **result})
        return result

    admission = decide(alert, now=now, force=force)
    result["admission"] = admission.as_dict()
    if not admission.invoke_agent:
        result["reason"] = admission.reason
        result["outcome"] = "no_action"
        if admission.reason == "unresolvable_latched" and should_page_recurrence(alert, now=now):
            result["notify"] = True
            result["offer"] = "Latched recurrence; approve manual action."
            md = _offer_markdown(alert, reason=admission.reason, offer=result["offer"])
            result["page"] = _maybe_page(alert, md)
            result["notification_markdown"] = md
        _append_receipt({"ts": int(now), "source": alert.get("source"), **result})
        return result

    # 4) Thin direct xAI — fail closed (no Hermes agent / utility-agent backup).
    thin = thin_llm_fn(alert, allowlist_result=allowlist)
    result["thin_llm"] = {
        "outcome": thin.get("outcome"),
        "reason": thin.get("reason"),
        "offer": thin.get("offer"),
        "ok": thin.get("ok"),
        "path": thin.get("path"),
        "latency_ms": thin.get("latency_ms"),
    }
    result["model_used"] = True
    result["outcome"] = str(thin.get("outcome") or "triage_failed")
    result["reason"] = str(thin.get("reason") or "")
    result["offer"] = str(thin.get("offer") or "")
    result["ok"] = bool(thin.get("ok"))
    result["notify"] = bool(thin.get("notify"))
    record_verdict(
        alert,
        result["outcome"],
        text=result["reason"] + "\n" + result["offer"],
        now=now,
    )
    if result["notify"]:
        md = _offer_markdown(
            alert,
            reason=result["reason"] or result["outcome"],
            offer=result["offer"],
        )
        result["notification_markdown"] = md
        result["page"] = _maybe_page(alert, md)
    _append_receipt({"ts": int(now), "source": alert.get("source"), **{k: result[k] for k in result if k != "thin_llm"}})
    return result


def run_first_pass_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Webhook route script contract: always silence Hermes agent after first-pass."""
    result = run_first_pass(payload)
    return {
        "__hermes_ignore__": True,
        "admission": result.get("admission") or {},
        "first_pass": {
            "outcome": result.get("outcome"),
            "reason": result.get("reason"),
            "offer": result.get("offer"),
            "model_used": result.get("model_used"),
            "hermes_agent": False,
            "allowlist": result.get("allowlist"),
            "notify": result.get("notify"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--webhook", action="store_true", help="Emit webhook_transform JSON")
    args = ap.parse_args(argv)
    if args.file:
        payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    else:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    if not isinstance(payload, dict):
        raise SystemExit("payload must be object")
    if args.force:
        payload = dict(payload)
        payload["force_agent"] = True
    # Webhook adapter feeds JSON on stdin with no --file (same contract as admission_gate).
    if args.webhook or (not sys.stdin.isatty() and not args.file):
        out = run_first_pass_webhook(payload)
        print(json.dumps(out, ensure_ascii=False))
        return 0
    result = run_first_pass(payload, force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") or result.get("outcome") == "no_action" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Needs-decision page: findings, latch times in TPE, and drift checks stay visible."""

from __future__ import annotations

import json
import sys
import types
from datetime import UTC, datetime
from pathlib import Path

from scripts.failure_autofix_page import (
    concrete_decision,
    latch_times_from_state,
    render_needs_decision_page,
)

SIGNATURE = (
    "automation-self-heal-monitor|automation.condition_finding|other|"
    "pd one automation self-heal monitor found cron/systemd issues"
)
TRIED = datetime(2026, 11, 16, 10, 4, tzinfo=UTC)  # 18:04 TPE
UNTIL = datetime(2026, 11, 17, 10, 4, tzinfo=UTC)  # 18:04 TPE the next day
DEPLOY = {
    "kind": "systemd_user_unit_failed",
    "unit": "hermes-deploy.service",
    "error": "Main process exited, status=1/FAILURE",
    "action": "needs review before reset/restart",
    "since": "2026-11-17T02:14:00+08:00",
    "hit_count": 4,
}
DRIFT = {
    "kind": "systemd_user_unit_failed",
    "unit": "hermes-deploy-drift.service",
    "error": "Main process exited, status=1/FAILURE",
    "action": "needs review before reset/restart",
    "suppress": True,
    "severity": "info",
    "downgrade": True,
}


def _page(alert: dict, **kwargs) -> str:
    text, _decision = render_needs_decision_page(alert, **kwargs)
    return text


def test_findings_replace_the_generic_summary_and_name_the_reset():
    alert = {
        "source": "automation-self-heal-monitor",
        "summary": "PD One automation self-heal monitor found cron/systemd issues",
        "findings": [DEPLOY],
    }
    page = _page(
        alert,
        reason="unresolvable_latched",
        offer="",
        signature=SIGNATURE,
        latch_tried_at=TRIED,
        latch_until=UNTIL,
    )
    assert "`systemd_user_unit_failed` `hermes-deploy.service`" in page
    assert "Main process exited, status=1/FAILURE" in page
    assert "since 2026-11-17 02:14 TPE, 4 hits" in page
    assert "OK to `systemctl --user reset-failed hermes-deploy.service`?" in page
    assert "Already tried once at 2026-11-16 18:04 TPE" in page
    assert "not retrying automatically until 2026-11-17 18:04 TPE" in page
    assert "found cron/systemd issues" not in page
    assert "Do not re-burn LLM" not in page
    assert "Why automation stopped" not in page


def test_summary_and_detail_when_the_event_has_no_findings():
    alert = {
        "source": "automation-self-heal-monitor",
        "summary": "PD One automation self-heal monitor found cron/systemd issues",
        "detail": "Watcher log had no structured rows.",
    }
    page, decision = render_needs_decision_page(
        alert,
        reason="verify_failed",
        offer="Allowlist repair ran but post-verify failed.",
        signature=SIGNATURE,
    )
    assert "**Summary:**" in page
    assert "found cron/systemd issues" in page
    assert "Watcher log had no structured rows." in page
    assert decision == "Allowlist repair ran but post-verify failed."
    assert "**Latch:**" not in page
    assert "**Findings:**" not in page


def test_prose_detail_line_becomes_a_finding_when_findings_is_absent():
    alert = {
        "source": "automation-self-heal-monitor",
        "summary": "PD One automation self-heal monitor found cron/systemd issues",
        "detail": (
            "systemd_user_unit_failed hermes-deploy.service — "
            "Main process exited, status=1/FAILURE. "
            "Action: needs review before reset/restart"
        ),
    }
    page, decision = render_needs_decision_page(
        alert, reason="unresolvable_latched", offer="", signature=SIGNATURE
    )
    assert "`hermes-deploy.service`" in page
    assert "status=1/FAILURE" in page
    assert decision == "OK to `systemctl --user reset-failed hermes-deploy.service`?"
    assert (
        "Already tried once; not retrying automatically until the latch expires."
        in page
    )


MONITOR_DETAIL = """\
## Automation Self-Heal Report
Checked: 2026-11-17 02:14 TPE
Mode: report
Guardrails: do not reset units from this header

### Needs review / approval
- **systemd_user_unit_failed** `hermes-deploy.service` — ● hermes-deploy.service loaded failed failed Hermes deploy worker (build, wait for idle profiles, cut over); last error: hermes-deploy.service: Main process exited, code=exited, status=1/FAILURE. Action: needs review before reset/restart
- **cron_job_failed** `nightly-sync` — 3 consecutive failures; last EXIT 1 at 2026-11-17T02:14:00+08:00; log /var/log/nightly-sync.log. Action: inspect the log

### Guardrails
- **systemd_user_unit_failed** `guarded.service` — last error: hidden by guardrails. Action: ignore

### Info
- **systemd_user_unit_failed** `quiet-probe.service` — last error: low severity noise. Action: ignore
- **systemd_user_unit_failed** `hermes-deploy-drift.service` — last error: drift while autodeploy is paused. Action: needs review before reset/restart
"""


def test_markdown_report_detail_uses_the_needs_review_line():
    alert = {
        "source": "automation-self-heal-monitor",
        "summary": "PD One automation self-heal monitor found cron/systemd issues",
        "detail": MONITOR_DETAIL,
    }
    page, decision = render_needs_decision_page(
        alert, reason="unresolvable_latched", offer="", signature=SIGNATURE
    )
    assert (
        "`systemd_user_unit_failed` `hermes-deploy.service` — "
        "hermes-deploy.service: Main process exited, code=exited, status=1/FAILURE"
        in page
    )
    assert "loaded failed failed" not in page
    assert (
        "`cron_job_failed` `nightly-sync` — "
        "3 consecutive failures; last EXIT 1 at 2026-11-17T02:14:00+08:00; "
        "log /var/log/nightly-sync.log" in page
    )
    assert decision == "OK to `systemctl --user reset-failed hermes-deploy.service`?"
    assert "hermes-deploy-drift.service" in page
    assert "Automation Self-Heal Report" not in page
    assert "do not reset units from this header" not in page
    assert "guarded.service" not in page
    assert "quiet-probe.service" not in page
    assert "low severity noise" not in page


def test_latched_page_without_findings_asks_to_clear_the_latch():
    alert = {"source": "automation-self-heal-monitor", "summary": "latched class"}
    page, decision = render_needs_decision_page(
        alert,
        reason="unresolvable_latched",
        offer="Signature is latched after a prior blocked repair. Do not re-burn LLM.",
        signature=SIGNATURE,
        latch_tried_at=TRIED.timestamp(),
        latch_until=UNTIL.timestamp(),
    )
    assert decision == f"OK to clear the latch for `{SIGNATURE}`?"
    assert decision in page
    assert "2026-11-16 18:04 TPE" in page
    assert "00:00" not in page


def test_extra_findings_are_counted_after_five():
    findings = [
        {
            "kind": "systemd_user_unit_failed",
            "unit": f"unit-{index}.service",
            "error": f"exit {index}",
        }
        for index in range(7)
    ]
    page = _page(
        {"source": "monitor", "findings": findings},
        reason="verify_failed",
        offer="",
        signature="",
    )
    assert "`unit-0.service`" in page
    assert "`unit-4.service`" in page
    assert "`unit-5.service`" not in page
    assert "- +2 more" in page


def test_drift_check_stays_on_the_page_while_autodeploy_is_paused():
    alert = {
        "source": "automation-self-heal-monitor",
        "summary": "PD One automation self-heal monitor found cron/systemd issues",
        "autodeploy_paused": True,
        "suppressed_findings": [DRIFT],
        "downgraded_findings": [DRIFT],
    }
    page, decision = render_needs_decision_page(
        alert, reason="unresolvable_latched", offer="", signature=SIGNATURE
    )
    assert "hermes-deploy-drift.service" in page
    assert "status=1/FAILURE" in page
    assert decision == "OK to inspect `hermes-deploy-drift.service`?"
    assert "info" not in page
    assert "downgrad" not in page


def test_deploy_and_drift_findings_both_show_and_the_decision_is_the_deploy_reset():
    alert = {
        "source": "automation-self-heal-monitor",
        "autodeploy_paused": True,
        "findings": [DRIFT, DEPLOY],
    }
    page, decision = render_needs_decision_page(
        alert, reason="needs_input", offer="", signature=""
    )
    assert "hermes-deploy-drift.service" in page
    assert "hermes-deploy.service" in page
    assert decision == "OK to `systemctl --user reset-failed hermes-deploy.service`?"


def test_pages_redact_tokens_env_values_and_keep_the_unit_error():
    secret = "supersecretvalue"
    bearer = "abc.def.ghi"
    api_key = "sk-live-secret"
    alert = {
        "source": "automation-self-heal-monitor",
        "summary": f"MATTERMOST_TOKEN={secret} failed",
        "detail": f'{{"api_key": "{api_key}"}}',
        "findings": [
            {
                "kind": "systemd_user_unit_failed",
                "unit": "hermes-deploy.service",
                "error": (
                    f"Main process exited, status=1/FAILURE TOKEN={secret} "
                    f'Bearer {bearer} "api_key": "{api_key}"'
                ),
            }
        ],
    }
    page, _decision = render_needs_decision_page(
        alert, reason="needs_input", offer="", signature=""
    )
    assert secret not in page
    assert bearer not in page
    assert api_key not in page
    assert "status=1/FAILURE" in page
    assert "[REDACTED]" in page


def test_error_line_is_truncated_near_two_hundred_characters():
    alert = {
        "source": "monitor",
        "findings": [
            {
                "kind": "systemd_user_unit_failed",
                "unit": "hermes-deploy.service",
                "error": "x" * 240,
            }
        ],
    }
    page = _page(alert, reason="needs_input", offer="", signature="")
    finding = next(line for line in page.splitlines() if line.startswith("- `"))
    shown = finding.split("— ", 1)[1]
    assert len(shown) == 200
    assert shown.endswith("…")


def test_nested_automation_incident_findings_are_used():
    alert = {
        "source": "automation-self-heal-monitor",
        "summary": "generic",
        "automation_incident": {
            "kind": "automation.condition_finding",
            "findings": [DEPLOY],
        },
    }
    decision = concrete_decision(alert, reason="needs_input", offer="", signature="")
    assert "hermes-deploy.service" in decision


def test_latch_times_come_from_the_admission_state(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "signatures": {
                    SIGNATURE: {
                        "last_verdict_at": TRIED.timestamp(),
                        "unresolvable_until": UNTIL.timestamp(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    tried, until = latch_times_from_state(SIGNATURE, path)
    assert tried == TRIED.timestamp()
    assert until == UNTIL.timestamp()
    assert latch_times_from_state("", path) == (None, None)
    assert latch_times_from_state(SIGNATURE, tmp_path / "missing.json") == (None, None)


def test_first_pass_latched_page_includes_the_finding(tmp_path: Path, monkeypatch):
    gate = types.ModuleType("failure_autofix_admission_gate")
    allow = types.ModuleType("failure_autofix_allowlist")
    thin = types.ModuleType("failure_autofix_thin_llm")

    class _Decision:
        reason = "unresolvable_latched"
        signature = SIGNATURE
        invoke_agent = False

        def as_dict(self):
            return {
                "reason": self.reason,
                "signature": self.signature,
                "invoke_agent": False,
            }

    gate.cheap_reject = lambda alert, now=None: _Decision()
    gate.decide = lambda alert, now=None, force=False: _Decision()
    gate.record_verdict = lambda *args, **kwargs: None
    gate.should_page_recurrence = lambda alert, now=None: True
    allow.try_allowlist_repair = lambda alert, force=False: {
        "status": "no_match",
        "ok": False,
        "offer": "",
    }
    thin.run_thin_llm = lambda alert, allowlist_result=None: {}
    monkeypatch.setitem(sys.modules, "failure_autofix_admission_gate", gate)
    monkeypatch.setitem(sys.modules, "failure_autofix_allowlist", allow)
    monkeypatch.setitem(sys.modules, "failure_autofix_thin_llm", thin)
    sys.modules.pop("scripts.failure_autofix_first_pass", None)

    state = tmp_path / "state.json"
    state.write_text(
        json.dumps(
            {
                "signatures": {
                    SIGNATURE: {
                        "last_verdict_at": TRIED.timestamp(),
                        "unresolvable_until": UNTIL.timestamp(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FAILURE_AUTOFIX_ADMISSION_STATE", str(state))

    from scripts import failure_autofix_first_pass as first_pass

    first_pass.RECEIPT_PATH = tmp_path / "first_pass.jsonl"
    first_pass.NOTIFICATION_ROUTER = tmp_path / "missing-router.py"
    first_pass.NOTIFICATION_ROUTER_PYTHON = str(tmp_path / "missing-python")
    result = first_pass.run_first_pass(
        {
            "source": "automation-self-heal-monitor",
            "summary": "PD One automation self-heal monitor found cron/systemd issues",
            "event_type": "pd-one.incident",
            "severity": "error",
            "findings": [DEPLOY],
        },
        now=TRIED.timestamp(),
        allowlist_fn=allow.try_allowlist_repair,
    )
    page = result["notification_markdown"]
    assert "hermes-deploy.service" in page
    assert result["offer"] == (
        "OK to `systemctl --user reset-failed hermes-deploy.service`?"
    )
    assert "2026-11-16 18:04 TPE" in page
    assert "Do not re-burn LLM" not in page

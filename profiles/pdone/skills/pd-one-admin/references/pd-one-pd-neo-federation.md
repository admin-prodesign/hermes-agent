# PD One ↔ PD Neo federation

Use this when asked how PD Neo/Hermes should federate with PD One/OpenClaw, or when adding cross-agent escalation, triage, approval, or knowledge-promotion flows.

For the first-pass implementation artifact map, supported event types, smoke-test commands, and backup/commit hygiene, also load `references/pd-one-pd-neo-federation-implementation-receipts.md`.

## Core rule
Prefer consolidating the existing rails over creating a new generic bidirectional queue. PD One already has separate mechanisms for failures, employee approvals, scoped specialist handoffs, review-log/missed-reply handling, and knowledge promotion. A new flat federation queue risks duplicate tickets, policy bypass, and extra model-driven load.

## Existing rails to preserve

### 0. Bidirectional envelope
Use `schema_version=pd-federation.v1` for both directions. PD One-originated events use `direction=pd-one-to-pd-neo`, `source_agent=pd-one`, `target_agent=pd-neo`; PD Neo-originated handoffs use `direction=pd-neo-to-pd-one`, `source_agent=pd-neo`, `target_agent=pd-one`. Default `privacy_scope` is `admin-only`; employee-facing relay must still go through PD One policy, approval, review-log, or scoped specialist rails.

Reverse handoff path:

- Hermes script: `/home/prodesign/.hermes/scripts/pd_neo_to_pd_one_event.py`
- OpenClaw-side handoff journal: `/home/prodesign/.openclaw/workspace/data/cross-agent/pd-neo-to-pd-one/queue.jsonl`
- Event types: `pd-neo.admin_recommendation`, `pd-neo.knowledge_promotion`, `pd-neo.capability_response`, `pd-neo.runtime_note`

This reverse journal is for admin review/audit and canonical updates. It must not auto-post to employees or bypass approval/action rails.

### 1. System failure / autofix rail
Canonical path:

- PD One/OpenClaw bridge script: `/home/prodesign/.openclaw/workspace/tools/pd_one_failure_to_hermes.py`
- Hermes fallback queue: `/home/prodesign/.hermes/pd-one-failure-alerts/queue.jsonl`
- Hermes queue worker: `/home/prodesign/.hermes/scripts/pd_one_failure_alert_queue_worker.py`
- Hermes cron: `012d548ed84d` (`PD One failure alert queue worker`, every 2 minutes, no-agent/local)
- Hermes webhook route: `pd-one-failure-autofix`
- Runbook: `/home/prodesign/.openclaw/workspace/docs/runbooks/pd-one-failure-alert-autofix.md`

Use for deterministic job failures, scanner/sync/export failures, attachment/file failures, runtime-health events, and low-risk admin-only triage. Keep the frequent processor deterministic and silent-on-empty; wake model/Hermes only when a real event exists.

### Failure-bridge gap audit pattern

When asked what PD One alerts/scripts still need PD Neo/Hermes federation, audit both active schedules and source wiring rather than relying on memory:

1. Inspect active PD One schedules: user crontab, `systemctl --user list-timers --all`, and relevant `.config/systemd/user/*.service` units.
2. Cross-check each scheduled script/wrapper for `pd_one_failure_to_hermes.py` usage and for direct `openclaw message send`, Mattermost/Discord posts, `send_alert`, `notify`, or failure-state logic.
3. Treat high-priority unwired candidates as: runtime health/slowness watchdogs, automation/systemd self-heal monitors, work-manual/document watchers, final-attempt operational briefings, attachment/review-log scanners, missed-reply replayers, and production schedule/project-list pollers.
4. Do not federate employee-facing reminders themselves. Federate only script/tool/runtime failures, attachment failures, capability gaps, or admin-only triage summaries; employee-visible relay still uses PD One review/approval/policy rails.
5. Prefer source-level wrapping at the existing alert/failure point when possible; otherwise let the deterministic automation self-heal monitor surface repeated cron/systemd failures as a bridge event.

If broadening this rail, extend the existing event envelope instead of adding a parallel queue. Candidate event types:

- `pd-one.failure`
- `pd-one.incident`
- `pd-one.attachment_failure`
- `pd-one.runtime_health`
- `pd-one.knowledge_candidate`
- `pd-one.capability_gap`

Keep backward compatibility for existing `pd-one.failure` payloads. Optional extra envelope fields can include: `request_type`, `privacy_scope`, `source_platform`, `source_channel_id`, `source_thread_id`, `source_post_id`, `employee_visible_summary`, `admin_context`, `what_pd_one_tried`, `desired_response_mode`, `approval_ticket_id`, and `review_log_row_id`.

Safety boundaries remain: no OpenClaw restart without Andy approval unless the approved unresponsive-gateway exception applies; no destructive cleanup; no token/gateway changes; no production writes; no external-send replay; bounded probes first; queue fallback if webhook is down.

### 2. Employee approval / action rail
Canonical path:

- `request_approval`
- admin approval ticket ledger
- `admin-prefix-escalation`
- Mattermost review-log/admin notification paths

Use for employee asks requiring restricted data, writes, new access/capability, admin action, cross-channel history, or sensitive context. Do not route these through the failure bridge unless they are actual system failures.

If PD Neo/Hermes triage is needed, add metadata to the existing approval ticket rather than creating another queue, for example:

```json
{
  "federation": {
    "needs_pd_neo": true,
    "reason": "system_fix_required | knowledge_promotion | admin_analysis",
    "privacy_scope": "admin-only",
    "source_post_id": "...",
    "review_log_row": "..."
  }
}
```

### 3. Scoped specialist handoff rail
Canonical path:

- `scoped_specialist_request` in `/home/prodesign/.openclaw/workspace/plugins/pd-one-employee-safety-gate/index.js`

This is already the safe read-only specialist handoff mechanism. Do not replace it with a generic PD Neo bridge. Only add PD Neo as a specialist endpoint if the tool enforces admin-only output, no raw private memory, no employee-facing relay without review, no writes, source-packet-only behavior, and review-log entry creation.

### 4. Knowledge-promotion rail
Canonical path:

- Hermes reference: `pd-one-admin/references/knowledge-promotion-playbook.md`
- OpenClaw runbook: `/home/prodesign/.openclaw/workspace/docs/runbooks/pd-one-knowledge-promotion.md`
- destination: skills, runbooks, wiki/source pages, glossary, policies, or agent rules depending on scope

Use for stable AppSheet behavior, terminology, source/data-location rules, employee-safe procedures, Mattermost response rules, and recurring pitfalls. Classify promotion candidates as employee-facing, manager/supervisor, admin-only, agent-only, or not promotable before writing them into PD One.

### 5. Review-log / missed-reply rail
Canonical references include:

- `pd-one-admin/references/mattermost-review-log-health-check.md`
- `pd-one-admin/references/mattermost-missed-message-catchup.md`
- Mattermost review-log DM scanner/timers
- n8n review-log digest/watchdog workflows where configured

Do not replace review-log/missed-message tooling with federation. Feed federation only when needed: repeated tool failure → failure bridge; capability gap → request approval/admin ticket; stable missing source knowledge → knowledge promotion; runtime failure causing missed reply → missed-reply catch-up then optional failure event for root-cause triage.

## Recommended implementation sequence

1. Documentation-only: add/patch OpenClaw runbooks and agent rules to describe the bidirectional rails. No runtime behavior change, gateway restart, new cron, or employee-facing change.
2. Extend the existing failure bridge into an event bridge by patching `pd_one_failure_to_hermes.py` and the Hermes queue worker. Keep old CLI flags and current `pd-one.failure` behavior working.
3. Add the PD Neo → PD One reverse handoff script as deterministic queue/journal writer only; do not add an auto-draining model cron or employee-facing relay in the first pass.
4. Connect one low-risk real PD One source first, preferably attachment/file failure, because it is admin-triage appropriate and already has runbooks.
5. Add approval-ticket federation metadata only after the event bridge is stable.
6. Repair/verify missed-reply replayer health before treating it as reliable federation input.

## Verification

- Python changes: `python3 -m py_compile` on modified bridge/worker scripts.
- JavaScript plugin changes: `node --check` or the relevant plugin tests.
- Shell wrappers: `bash -n`.
- Read back destination files/runbooks after writes.
- Commit/push narrow OpenClaw backup changes and Hermes backup changes when repos/remotes are configured.

## Pitfalls

- Do not create `/home/prodesign/.openclaw/federation/` as the primary failure/autofix queue unless the existing bridge cannot be extended.
- Do not let PD Neo auto-post employee-facing replies; relay through PD One Mattermost policy, review-log, approval-ticket, or admin-channel paths.
- Do not add a frequent model-driven federation cron. Keep polling deterministic and local; invoke AI only on actual events.
- Do not bypass `request_approval` for employee-originated restricted actions.
- Do not bypass `scoped_specialist_request` for read-only specialist handoffs.

# PD One ↔ PD Neo federation implementation receipts

Session-specific implementation map for the first safe bidirectional PD One/OpenClaw ↔ PD Neo/Hermes federation pass. Load this together with `references/pd-one-pd-neo-federation.md` when auditing, extending, or troubleshooting the live bridge.

## Implemented artifact map

OpenClaw / PD One side:

- Plan: `/home/prodesign/.openclaw/workspace/docs/plans/pd-one-pd-neo-bidirectional-federation-implementation-plan.md`
- Canonical runbook: `/home/prodesign/.openclaw/workspace/docs/runbooks/pd-one-pd-neo-federation.md`
- Bridge/event emitter: `/home/prodesign/.openclaw/workspace/tools/pd_one_failure_to_hermes.py`
- Agent/rule pointers:
  - `/home/prodesign/.openclaw/workspace/AGENTS.md`
  - `/home/prodesign/.openclaw/workspace/docs/agent-rules/core-operating-rules.md`
  - `/home/prodesign/.openclaw/workspace/docs/runbooks/pd-one-failure-alert-autofix.md`
  - `/home/prodesign/.openclaw/workspace/docs/runbooks/pd-one-knowledge-promotion.md`

Hermes / PD Neo side:

- Fallback queue worker: `/home/prodesign/.hermes/scripts/pd_one_failure_alert_queue_worker.py`
- Reverse handoff writer: `/home/prodesign/.hermes/scripts/pd_neo_to_pd_one_event.py`
- Reverse handoff journal default: `/home/prodesign/.openclaw/workspace/data/cross-agent/pd-neo-to-pd-one/queue.jsonl`

## Event envelope and direction rules

- Canonical schema version: `pd-federation.v1`.
- PD One-originated events use `direction=pd-one-to-pd-neo`, `source_agent=pd-one`, `target_agent=pd-neo`.
- PD Neo-originated events use `direction=pd-neo-to-pd-one`, `source_agent=pd-neo`, `target_agent=pd-one`.
- Default `privacy_scope` stays `admin-only`.
- Employee-visible relay must still pass through PD One approval, review-log, scoped-specialist, or Mattermost policy rails.

Implemented PD One-originated event types:

- `pd-one.failure`
- `pd-one.incident`
- `pd-one.attachment_failure`
- `pd-one.runtime_health`
- `pd-one.knowledge_candidate`
- `pd-one.capability_gap`

Implemented PD Neo-originated event types:

- `pd-neo.admin_recommendation`
- `pd-neo.knowledge_promotion`
- `pd-neo.capability_response`
- `pd-neo.runtime_note`

Useful envelope fields added/expected: `source_refs`, `approval_ticket_id`, `review_log_row_id`, `desired_response_mode`, `privacy_scope`, and idempotency key material. Keep legacy `pd-one.failure` payloads backward-compatible.

## Verification pattern used

Run syntax checks after bridge/worker changes:

```bash
python3 -m py_compile \
  /home/prodesign/.openclaw/workspace/tools/pd_one_failure_to_hermes.py \
  /home/prodesign/.hermes/scripts/pd_one_failure_alert_queue_worker.py \
  /home/prodesign/.hermes/scripts/pd_neo_to_pd_one_event.py
```

Smoke-test both directions with JSON dry-runs:

- Legacy PD One failure event still emits/queues correctly.
- PD One attachment-failure event emits the new federation envelope.
- PD Neo reverse handoff writes parseable JSONL with `direction == "pd-neo-to-pd-one"`.

For reverse handoff smoke tests, write to a temp JSONL path such as `/tmp/pd-neo-to-pd-one-smoke.jsonl`, parse/read back the row, verify direction/schema fields, then remove the temp file.

## Commit/backup hygiene

- Commit/push narrow OpenClaw backup changes and Hermes backup changes when remotes are configured.
- If unrelated unstaged local diffs exist, stage only the federation hunks/files needed for the durable backup; do not absorb unrelated local work into the federation commit.
- The first-pass commits were narrow backups, not a signal to restart OpenClaw or add new model-driven crons.

## First-pass safety decisions

- No OpenClaw gateway restart was needed.
- No new model-driven cron was added.
- No employee-facing auto-relay was created.
- Reverse communication was implemented as an admin-only journal first, so PD Neo can hand information back to PD One without bypassing PD One approval/review/specialist/knowledge-promotion rails.

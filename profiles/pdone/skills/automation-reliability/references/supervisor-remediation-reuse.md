# Supervisor remediation reuse notes

Use this reference when a supervisor audit discovers an actionable issue and you need to decide whether to write a new remediation plan.

## Exact-gap reuse rule

Search for an existing plan that matches both:
- the same automation/job, and
- the same gap class/state.

Treat these as different gap classes even if the automation name is the same:
- `cron last_status=error`
- `missing live cron`
- `stale live source`
- `stale waiting prompt`
- `delivery failure`
- `missing bridge`

If a matching plan already exists, report the existing path as the backlog receipt and do not create a duplicate plan.

## Bounded Sheets triage parsing

For `pd_one_review_log` triage:
1. Request a bounded wide range that includes current workflow columns.
2. Treat the live response range as authoritative if Sheets returns a narrower range than requested.
3. Save `gog ... --json` output to a temp file and parse with a robust JSON reader.
4. Build row decisions from stable ids/row numbers plus structured columns, not from prose alone.

## Classification guardrails

- `workflow_outcome_verified=no` stays open.
- Approval-gated or blocked replies are not closure evidence.
- `follow_up_needed` is metadata only; do not use it as the watcher source of truth.
- Use `review_status` plus structured verification/access fields first.

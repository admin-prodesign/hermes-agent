# PD One supervisor triage notes

This reference captures durable patterns observed while running the PD One Automation Supervisor Agent.

## Exact-gap remediation plan reuse

When audit evidence is unresolved, reuse an existing remediation plan only if both the automation and the gap class match.

Common gap classes seen in practice:
- `missing-live-cron`
- `cron-error`
- `stale-live-source`
- `missing bridge`
- `delivery failure`
- `degraded_noop`

Do not reuse a plan across different gap classes for the same automation. Example:
- a plan for `registered cron job not found in live cron jobs` does not cover `last real live dashboard success is stale`

## Bound-aware Google Sheets reads

For supervisor triage, use a bounded wide read, but trust the returned range verbatim if Google Sheets returns a smaller live extent than requested.

Example pattern:
- requested: `pd_one_review_log!A1:AZ1000`
- returned: `pd_one_review_log!A1:AY905`
- report the returned range as authoritative

This avoids inventing a missing trailing column and keeps row counts aligned to the live sheet.

## Read-only review_log triage

For first-pass triage:
- use `review_status` as the worklist source of truth
- ignore legacy `follow_up_needed` for selection
- classify open rows conservatively
- do not close rows without row-local or exact nearby completion evidence
- keep workflow rows open until `workflow_outcome_verified=yes` or equivalent receipt exists

## Reporting shape

When reporting a bounded scan, include:
- checked range
- non-closed row count
- category breakdown
- concise row ids only
- explicit note that no Sheet rows were changed

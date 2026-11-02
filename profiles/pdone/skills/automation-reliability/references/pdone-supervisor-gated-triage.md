# PD One supervisor gated-triage notes

This note captures a reusable pattern from a gated supervisor run where the deterministic packet already provided enough evidence to avoid redundant discovery.

## Gate-first workflow

- Treat the deterministic packet as the first evidence source.
- Do not repeat expensive discovery that the packet already answers unless verification is needed.
- If repair/apply scripts return no actions, still run the audit script and inspect the findings.
- When the audit still reports unresolved warnings/critical items, convert the gap into a durable remediation plan only if there is no exact existing plan for the same automation + gap class.

## Exact-gap remediation-plan dedup

Search for an existing plan by both automation name and gap class before writing a new one.

Examples of distinct gap classes:
- missing-live-cron
- stale-live-source
- stale prompt / waiting-prompt
- review_log reviewer-failed open rows

Do not reuse a plan for a different gap class on the same automation.

## Bounded review_log triage pattern

- Read the live tab with headers by name, not assumed letters.
- Use a wide bounded range for current counts; if the response returns a smaller authoritative range, trust the returned bound.
- Parse Sheets JSON with a robust parser after writing it to a temp file.
- Build the worklist from `review_status` non-closed rows, not `follow_up_needed`.
- For workflow rows, prefer structured fields such as `workflow_outcome_verified`, `project_update_history_verified`, and `answer_sources` over reply prose.
- A row is not closeable unless the row-local or exact nearby evidence proves completion.

## Compact triage categories used in this run

- `needs_admin_approval`: scope, access, or protected-source block; keep open pending admin decision.
- `needs_pd_one_corrective_reply`: no reply evidence or poor reply quality; verify the thread before any write.
- `automation_or_tooling_issue`: reviewer failure, auth/tooling failure, or stale closed/open inconsistency.
- `keep_open_pending_work`: workflow evidence missing or outcome not yet verified.
- `likely_closeable_after_verification`: only when direct completion evidence exists.

## Remediation-plan receipts

A durable remediation plan should include:
- the exact automation name and job id if present
- the exact gap class
- the audit timestamp and message
- actions already tried
- why autonomous repair is blocked
- the recommended admin action

## Verification before reporting

- Read back audit output and any newly written plans.
- Report counts and concise row IDs only.
- State explicitly that the Sheet was not changed when triage is read-only.

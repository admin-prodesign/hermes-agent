# Review-log response-quality reviewer failure pattern

Session-derived notes for PD One supervisor triage.

## Symptom
A `review_log` row remains `review_status=open` even though the row already contains later PD One bot-reply evidence in `answer_sources` / `reply_summary`, but `response_quality_status=error` and `response_quality_flags=reviewer_failed` prevent closure.

## Observed classification rule
- Do not classify these rows as `likely_closeable_after_verification` from reply evidence alone.
- If the row still says open because the quality reviewer failed or timed out, classify it as `automation_or_tooling_issue`.
- Keep approval-gated / scope-blocked rows separate even if they also have bot-reply evidence.

## Triage receipt to record in a remediation plan
- Include the row numbers and `review_log_id` values.
- Capture the exact status fields: `review_status`, `response_quality_status`, `response_quality_flags`.
- State whether the row already has later bot-reply evidence in the sheet.
- Recommend patching the collector/reviewer path so later same-thread replies reconcile cleanly without leaving open placeholders.

## Project List / Project Tracker collector exclusion
- Replies to a deterministic `專案追蹤更新 / Project List update` prompt are workflow data-collection events, not direct-answer interactions. Do not send the acknowledgement/restatement through semantic reply-quality review, and do not alert Andy on those rows.
- Verify a Project List prompt with structured `prompting_context=project_list_prompt`, the exact threaded root post, or — for unthreaded owner DMs — the other party's last preceding same-channel message. Owners often answer as a top-level DM. Do not match an older prompt if a later non-prompt other-party message exists.
- Terse declarative statuses are valid collector replies even when they contain no standard progress verb (for example, `CPK 尚未做，狀況與之前相同`). Keep actual questions/requests in normal quality review.
- Classify collector progress replies deterministically as `ok` with `workflow_continuation | project_list_followup | quality_review_excluded`. Missing Sheet write/readback is a Project List poller/workflow issue, not a reply-quality finding. The quality supervisor must skip `project_list_followup` and `quality_review_excluded` even if a stale sheet row still says `review`.
- When stale `reviewer_failed` rows are already open, dry-run a header-based targeted reconciliation by stable `review_log_id`, then set only the review/quality fields to closed/ok after approval and readback verification.

## Backlog hygiene
Before writing a new remediation plan, search existing plans for the same automation plus the same gap class (`reviewer_failed`, stale open placeholder, etc.). Reuse an exact-match plan when one already exists.

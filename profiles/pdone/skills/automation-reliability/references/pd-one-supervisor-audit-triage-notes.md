# PD One supervisor audit / triage notes

Session notes to preserve bounded supervisor learnings.

## Evidence-backed takeaways

- A bounded Google Sheets read may return a smaller live range than requested. Example pattern: asking for `pd_one_review_log!A1:AZ1000` can return `pd_one_review_log!A1:AY868`. Treat the returned range as the authoritative bound.
- First-pass `review_log` triage should rely on structured fields before reply prose:
  - `review_status`
  - `workflow_outcome_verified`
  - `response_quality_status`
  - `access_status`
  - `response_quality_flags`
  - `answer_sources`
  - `blocked_or_missing_sources`
- `review_status=open` plus reviewer/tool failures is usually an automation/tooling issue, not an employee follow-up.
- When an exact remediation plan already exists for the same automation and same gap class, reuse it instead of creating a duplicate plan.

## Compact triage reminder

- Keep the row open when workflow readback is missing or unverified.
- Treat approval-gated access requests as admin-approval items, not closure candidates.
- Do not close rows from “bot replied” prose alone unless the row-local structured receipt proves the expected outcome.

# Remediation-plan gap matching notes

Use this note when a supervisor audit finds a warning/critical item that might already have a durable backlog entry.

## Rule

Before writing a new remediation plan, search for an existing plan that matches both:
- the same automation, and
- the same gap class.

Do not key only on automation name. Different gaps for the same automation need different plans.

## Gap classes that should be matched exactly

- `missing-live-cron`
- `missing bridge`
- `stale-live-source`
- `delivery failure`
- `reviewer_failed` / response-quality reviewer failure
- stale Project List prompts

## When to reuse an existing plan

Reuse the existing plan path when the current evidence is materially the same as the earlier plan, for example:
- the same registered cron job is still absent from live cron jobs
- the same stale prompt is still unresolved
- the same live-source freshness regression is still the issue
- the same reviewer failure class is still leaving open rows unresolved

Report the existing plan path as the durable backlog receipt instead of creating a duplicate.

## When to create a new plan

Create a new plan only if the current evidence differs in a way that would change the recommended fix, such as:
- missing live cron vs stale success receipt
- missing bridge vs missing live cron
- stale source vs delivery failure
- workflow outcome missing vs reviewer_failed tool issue

## Review-log-specific note

Open review_log rows with `response_quality_status=error` and `reviewer_failed` should usually be treated as a tooling/automation backlog item when bot reply evidence is already present in the sheet. The remediation plan should point at the collector/reviewer path, not at employee follow-up, unless the row itself lacks reply evidence and a human has verified that the reply never existed.

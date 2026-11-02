# Remediation-plan deduping for supervisor findings

Use this when the supervisor audit produces a new critical/warning item and you need to decide whether to write a new remediation plan or reuse an existing one.

## Rule

Search for an exact match on both:
- the automation identity/name, and
- the gap/state class

Examples of gap/state classes:
- `cron last_status=error`
- `missing live cron`
- `stale-live-source`
- `missing bridge`
- `delivery failure`
- `queue corruption`
- `stale prompt`

If an exact-match plan already exists, do not create a duplicate. Report the existing plan path as the durable backlog receipt.

If the evidence is materially different for the same automation, a new plan is justified. Examples:
- `cron last_status=error` is not the same as `missing live cron`
- `stale-live-source` is not the same as `cached-success stale`

## Practical workflow

1. Search the remediation-plans directory for the automation name and exact gap/state terms.
2. Reuse an existing plan if it covers the same gap class.
3. If no exact match exists, write one narrow JSON plan.
4. Validate the new plan with `python3 -m json.tool`.
5. If backup sync is configured, run the profile backup sync and keep the commit/push scoped to the new plan plus any directly related durable files.

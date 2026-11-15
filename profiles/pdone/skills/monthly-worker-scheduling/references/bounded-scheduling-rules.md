# Bounded Scheduling Rules

Use this reference when adding or operating source-backed solver preferences that must remain narrower than arbitrary configuration.

## Design contract

- Keep the rules tab schema fixed and versionable; do not accept arbitrary columns, solver expressions, or caller-supplied payload overrides.
- Identify workers by stable `WorkerID`. Human-readable names, title, employment status, business unit, and run group are validation evidence—not the primary key.
- Validate enumerations, effective month, positive bounded weight, and date-list syntax before building solver inputs.
- Fail preflight unless the required role mapping is unique and maps to exactly one source worker. Missing, duplicate, stale, or mismatched mappings must block solve rather than silently disabling the rule.
- Preserve rules and their validation summary when filtering source records by run group so preflight and solve receipts show the same evidence.

## Safe typed tab setup

A setup action should be bound to one approved spreadsheet, tab name, schema, and seed payload. The action must:

1. Dry-run metadata first and report whether the tab exists.
2. Reject caller payload overrides.
3. Refuse duplicate tabs or non-empty conflicting content.
4. Create only the exact missing tab, then write the fixed values.
5. Read back metadata and the complete seeded range; success requires exact values and structural checks such as the frozen header.
6. Remain idempotent when the existing tab already matches exactly.

For the approved manager-day rule, the fixed tab is `排班規則 Scheduling Rules`, with columns:

`RuleID, Active, WorkerID, Name, JobTitle, EmploymentStatus, BusinessUnit, RunGroup, EffectiveFrom, WeekendBiasEnabled, PreferenceMode, RequestProtection, Weight, ExcludedDates, Notes`.

The initial reviewed row (2026-08) mapped `manager_day_weekend_bias_W12` to `W12` / `王柏凱`, mode `Prefer`, protection `Conservative`, weight `1500`. Andy 2026-08-25: each month, remap that single active row to whichever of `楊正義` or `王柏凱` is `幹部-日`. Do not add a night-shift copy. Keep mode/protection/weight.

## Soft-objective boundary

For a weekend-coverage preference:

- Enable it only in the intended run group.
- Compute weekend dates from the actual target year/month.
- Remove requested rest, hard rest, flex rest, protected leave, special work, mandatory work, and explicit rule exclusions before objective construction.
- Penalize missed eligible coverage as a soft term only. Never weaken hard labor/rest constraints or request-protection rules to satisfy the preference.
- Other run groups must remain behaviorally unchanged.

## Receipt design, including infeasible solves

Rule ingestion and solve feasibility are separate facts. Always expose the bounded rule and eligibility in `staffing_summary.weekend_coverage`, even when the solver returns `INFEASIBLE` or `UNKNOWN`:

- `run_group`, `solve_status`, and `coverage_computed`
- enabled worker count
- rule ID, worker ID/name, weight
- all weekend days
- eligible days
- exclusions grouped by reason
- staffed/missed eligible days only when a feasible solution exists; otherwise use null rather than pretending zero coverage

This lets operators prove that the rule was loaded without falsely claiming staffing outcomes from an infeasible model.

## Minimum regression coverage

- Exactly one active/effective role mapping succeeds.
- Missing or duplicate mapping fails preflight.
- Stable WorkerID/name/group/status mismatches fail.
- Preference is a no-op outside the target run group.
- Requested rest and explicit exclusions are removed from eligibility.
- Feasible output reports staffed/missed weekend coverage.
- Infeasible output still reports rule/eligibility with `coverage_computed=false`.
- Typed setup rejects payload overrides and conflicting existing content.
- Live setup tests require exact metadata and value readback.

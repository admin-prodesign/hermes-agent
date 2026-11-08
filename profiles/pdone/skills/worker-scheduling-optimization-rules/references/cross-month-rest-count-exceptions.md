# Cross-Month Rest-Count Exception Audit

Use this reference before recommending a global monthly rest-count increase or sending an exception list to HR.

## Purpose

Identify only active workers whose verified previous-month history forces both day 1 and day 2 to be rests under an anchored five-rests-per-14-days rule. These workers need a per-worker monthly rest-count exception; everyone else should retain the default unless another hard constraint independently proves otherwise.

## Exact boundary rule

For an anchored 14-day period ending on target-month day 2:

1. Count only the markers the solver parser treats as prior rests. In the current scheduler that is literal `V` or `申`; do not silently count `特`, `風`, `病`, `喪`, `訓`, blank, or other markers.
2. Let `r` be the count of prior-month rests in the historical portion of that period.
3. Required rests on target-month days 1-2 are `5 - r`, bounded by the two available days.
4. Audit the later anchored target-month periods separately. For a 31-day month with later periods day 3-16 and day 17-30, each needs five rests.

Classification:

- `r == 3`: both day 1 and day 2 must be rests. With five rests required in each later disjoint 14-day period, the target-month lower bound is `2 + 5 + 5 = 12`.
- `r >= 4`: the boundary alone does not force a 12-rest exception; the normal 11-rest count can still be boundary-compatible.
- `r < 3`: even resting both day 1 and day 2 cannot repair the historical 14-day period. Report a prior-period law/data violation instead of calling it a normal 12-rest exception.

This proves a rest-count exception is necessary under the boundary rule; it does not by itself prove the worker has no unrelated mandatory-work, leave, max-consecutive, or fixed-marker conflict.

## Roster-wide audit procedure

1. Resolve the exact active target-month roster from parsed source records, not every historical name visible on schedule tabs.
2. Exclude blank-class, generic/unmapped, inactive, footer, totals, and marker-only rows unless they are separately modeled exception groups.
3. Join each active worker by exact normalized name/stable ID to the correct previous-month destination row.
4. Read only the historical date cells needed by the anchored boundary period.
5. Count parser-recognized rest markers and record the exact dates.
6. Separately flag workers with fewer than three historical rests.
7. Check day 1 and day 2 for mandatory-work, protected-leave, or special-work conflicts.
8. Produce a review table with target group, WorkerID, employee ID, exact name, historical rest dates, current source rest count, and proposed exception.
9. Reconcile the result against solver probes, but prefer verified arithmetic and constructive witnesses over a misleading diagnostic summary.
10. Do not send to HR or write source overrides until the reviewer explicitly approves the list.

## Per-worker override requirement

Keep the global monthly default unchanged. A formula-owned `RequiredRestDaysCount` copied from one monthly control cell must not be manually overwritten row by row.

If the solver input already accepts a per-worker count but the source sheet exposes only a global value, add a bounded, month-effective, WorkerID-keyed override source. The effective value should be:

```text
per_worker_override if present and validated, otherwise monthly_default
```

For a temporary correction schema authorized specifically as `11 → 12`, fail closed rather than accepting a generic 1–31 replacement:

- bind each entry to the resolved solver year/month, not only to mutable per-row period fields;
- require stable `WorkerID` plus exact expected normalized name and schedule group;
- require the source value to be exactly `11` and the override to be exactly `12`;
- reject duplicate `(year, month, WorkerID)` keys, unsupported schema versions, missing identity fields, and group/name mismatches;
- never let this exception mechanism lower the source rest count;
- keep the override in a dedicated auditable config/rules source rather than editing formula-owned rows or encoding people directly in solver logic.

Emit a structured `applied_monthly_rest_overrides` receipt for every run group. Each entry should include period, WorkerID, name, source row, source count, effective count, reason, and config/rule source. Include the structured list in both the full generated report and the compact summary; warning text alone is not a sufficient machine-readable receipt.

Do not use AP:AT hard-rest dates as a substitute: forcing dates while retaining an exact total of 11 still leaves the model contradictory.

Regression coverage should include: matching period applies; another month stays at the default; duplicate keys fail; wrong name/group fails; non-`11 → 12` transitions fail; and applied overrides appear in the report. After implementation, run the normal bounded MCP preview and verify the spawned command/group selector. The accepted payload key is `solve_groups`; aliases such as `run_groups` may be ignored and accidentally launch all groups. If that happens, report it as a grouped sequential run—not as isolated group evidence—and do not start duplicate concurrent jobs.

## Generated-schedule verification

For every overridden worker, verify all of the following from the generated report before declaring success:

1. day 1 and day 2 tokens are counted rests;
2. the structured override receipt shows source `11` and effective `12`;
3. the solver row has exactly 12 counted rests;
4. the containing group is `FEASIBLE` or `OPTIMAL` under the normal cap;
5. `write_enabled=false` and no write report exists unless writeback was separately approved.

Do not equate `rest_v` with total counted rests. In solver summaries, requested rests may appear separately as `rest_requested` and render as `申`. For this policy, verify:

```text
total_counted_rests = rest_v + rest_requested
```

For example, `rest_v=9` and `rest_requested=3` is a valid 12-rest result. Report both components when explaining the receipt so HR/operations does not mistake nine literal `V` markers for only nine rests.

## Constructive witness and probe-status discipline

A rest-count probe must preserve and report each candidate's actual status. Never label an exhausted probe loop as `INFEASIBLE` unless every candidate was proven `INFEASIBLE`.

- `FEASIBLE` / `OPTIMAL`: accepted witness.
- `INFEASIBLE`: solver proof for that exact candidate.
- `UNKNOWN`: inconclusive; retry through the normal bounded path or validate a concrete calendar.
- `MODEL_INVALID` / other statuses: report separately as a model/runtime defect.

When operations supplies a concrete calendar, validate exact rest count, max consecutive work, all encoded 7-day periods, all encoded 14-day periods, flex/special-leave semantics, and prior-month marker classification. A valid constructive witness overrides a diagnostic sentence that merely conflated non-feasible statuses.

## HR review wording

State that the listed workers require a target-month rest-count exception because verified prior-month history forces both day 1 and day 2 to be rests under the five-in-14 rule. Explicitly state:

- the list is scoped to active parsed participants;
- the monthly default remains unchanged;
- the exception is per worker and per month;
- no source or schedule value was changed during the audit;
- unrelated scheduling conflicts may still require separate resolution.

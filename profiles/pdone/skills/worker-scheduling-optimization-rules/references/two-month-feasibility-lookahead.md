# Two-Month Feasibility Lookahead

Use this reference when a primary-month schedule must be chosen so that the immediately following month remains legally schedulable with a separately supplied exact rest count.

## Required semantics

A sequential procedure is not sufficient:

1. solve the primary month;
2. freeze that calendar;
3. solve the following month;
4. reject the primary result if the second solve fails.

That can falsely reject the month because a different, equally acceptable primary calendar may admit a feasible following month. The primary and following-month decisions must remain linked in the same authoritative CP-SAT feasibility model, or be represented by an exactly equivalent boundary-feasibility formulation.

The joint model must enforce:

- the primary month’s exact per-worker rest count, including validated period/WorkerID overrides;
- the following month’s separately supplied exact rest count;
- maximum consecutive work across the month boundary;
- every cycle-anchored 7-day and 14-day rest period crossing or contained in the two-month horizon;
- stable roster/group identity for every modeled worker.

The primary month retains submitted rest requests, protected inputs, staffing-quality objectives, rhythm preferences, and other approved objective terms. The following month is a feasibility guard:

- ignore employee requested-rest preferences;
- do not add staffing, rhythm, or request-preference objective terms unless a later policy explicitly requires them;
- preserve only the approved hard feasibility contract;
- never let its witness calendar become a write plan.

Only primary-month cells may produce generated-schedule writeback actions.

## Kickoff and input contract

Before any solve, collect two explicit exact rest-day counts:

1. the month being scheduled;
2. the immediately following month.

Fail closed when the following-month count is missing. Keep the primary count source-backed; do not infer either value from another year/month.

A useful receipt shape includes:

```json
{
  "lookahead_summary": {
    "enabled": true,
    "year": 2026,
    "month": 9,
    "required_rest_days_count": 12,
    "requested_rest_days_ignored": true,
    "primary_admits_following_month": true,
    "proof_status": "proven_feasible",
    "writeback_scope": "primary_month_only"
  }
}
```

For `UNKNOWN`, timeout, or model/runtime failure, use:

- `primary_admits_following_month: null`;
- `proof_status: indeterminate`.

Never translate `UNKNOWN` into following-month infeasibility.

## Modeling pattern

A single date-indexed horizon is often the narrowest safe extension of an existing monthly solver:

- primary indices cover day 1 through primary month-end;
- following indices continue through the full next calendar month;
- output serialization still emits primary-month tokens only;
- the private receipt may retain the following-month rest-day witness.

For maximum consecutive work, retain rich consecutive-count variables only where primary objectives need them. Across the boundary and throughout the objective-neutral lookahead month, the exact hard equivalent is a sliding window:

```text
sum(work[d : d + max_consecutive + 1]) <= max_consecutive
```

Every window of `max_consecutive + 1` days must contain a rest. This can materially reduce reified integer variables without weakening the hard rule.

## Search-performance pattern

A doubled horizon can introduce a large objective-neutral following-month symmetry. Use bounded staged search while preserving the normal overall cap:

1. clear the primary objective temporarily and seek a full grouped two-month feasibility witness;
2. add that witness as a hint;
3. restore and optimize the primary objective with the remaining time;
4. preserve the actual final status.

Bounded one-worker probes may be used only to generate optional hints. They alter group composition and can report `INFEASIBLE` even when the full group is feasible. Therefore:

- label their statuses non-authoritative;
- never use them as group feasibility proof;
- never recommend rest-count or policy changes from those probe statuses alone;
- accept feasibility only from the full grouped model or an exact equivalent proof.

### Hint decoding and authoritative validation

Treat serialized schedule tokens as presentation values, not as a generic blank/nonblank work flag. Decode hints with the solver's explicit token semantics. In the current Pro-Design solver, only `V` and `申` map to `work=0`; blank, `未`, `特`, and `喪` map to `work=1` for staffing and consecutive-work constraints. A blank/nonblank decoder can create a combined hint that appears infeasible even though every worker probe returned a valid calendar.

When every worker has a candidate hint, a short fixed-hint attempt inside the **full grouped model** is a useful validation stage:

1. fix only the grouped model's hinted work variables;
2. solve the complete hard model;
3. accept `FEASIBLE` or `OPTIMAL` as an authoritative grouped witness;
4. add the full witness, including auxiliary variables, as the optimization hint;
5. restore the primary objective and use the remaining overall budget.

A fixed-hint `INFEASIBLE` result proves only that the particular combined hint is incompatible. It does **not** prove that the group model is infeasible. Record it separately (for example, `fixed_complete_hint_status`), remove the fixed-hint requirement, and continue with an unfixed grouped feasibility search. If only some workers produced hints, skip the fixed-complete-hint stage and solve the grouped model with partial hints.

Budget seed probes, grouped feasibility validation, fallback grouped search, and objective optimization inside the normal per-group cap. Preserve both the feasibility-witness status and final optimization status so that an optimization timeout cannot erase a previously proven feasible two-month witness.

Do not run group solves concurrently: CP-SAT contention can turn a valid normal-cap run into a runtime-limited result. Use isolated `solve_groups=[...]` previews and verify the spawned `--solve-group` selector.

## Verification checklist

- [ ] Both monthly rest counts were supplied explicitly.
- [ ] Primary and following-month decisions remain boundary-linked.
- [ ] Following-month requested-rest preferences contribute no constraints or objective penalties.
- [ ] Exact rest totals hold independently for both months.
- [ ] Consecutive-work and anchored 7-/14-day rules cover the boundary.
- [ ] Full grouped status is `FEASIBLE` or `OPTIMAL`; `UNKNOWN` remains indeterminate.
- [ ] Every following-month witness worker has the exact supplied rest count.
- [ ] Receipt says `writeback_scope=primary_month_only`.
- [ ] Generated candidate actions contain no following-month cells.
- [ ] `write_enabled=false` during implementation QA.

## Regression cases

Add coverage for:

- missing following-month count fails closed;
- primary requests still affect primary tokens/objective;
- following-month requests are ignored;
- exact following-month count is enforced;
- day-1 boundary rest resets the primary streak;
- boundary work carries the streak correctly;
- cross-boundary 7-day and 14-day periods remain enforced;
- an alternative primary witness is found instead of freezing the first sequential calendar;
- display tokens decode to work variables using explicit solver semantics (`V`/`申` rest; blank/`未`/`特`/`喪` work in the current model);
- a complete fixed hint is accepted only after full grouped validation;
- an incompatible fixed-hint combination falls back to unfixed grouped search and is not reported as model infeasibility;
- non-authoritative one-worker probe statuses cannot determine the grouped result;
- `UNKNOWN` produces indeterminate proof fields;
- only primary-month actions are emitted.

# Post-Solve Staffing Quality Gates

Use this after any grouped monthly solve and before generated-schedule writeback.

## Why status alone is insufficient

`FEASIBLE` proves the hard constraints were satisfied. It does **not** prove that the returned incumbent is operationally acceptable. A bounded CP-SAT run can return a poor first incumbent when soft staffing objectives have not converged, especially in a joint primary/following-month model with many symmetry-breaking hints.

A successful write receipt proves delivery, not schedule quality. Quality must be accepted from the selected preview before writing.

## Required acceptance checks

For every solved group, inspect and record:

1. solver status, objective value, best bound, elapsed time, and whether optimization stopped at its cap;
2. worker count and exact primary-month rest totals;
3. following-month proof fields (`primary_admits_following_month`, proof status, and exact witness rest totals);
4. daily staffed-worker counts, target counts, minimum, maximum, spread, and below-target days;
5. adjacent-day staffing swings and any forced-low-day classification;
6. coverage/qualification misses and requested-rest effects.

Reject the preview if the daily profile is operationally implausible even when status is `FEASIBLE`. Do not write it and do not describe it as qualified.

## Roster-change invalidation

Any participant removal/addition or shift/group change invalidates earlier previews and write receipts as evidence for the new roster. Run fresh source preflight, verify the exact group population, solve only the affected group first, and re-run the quality gate. Confirm the removed worker is absent from the generated report, not merely absent from the destination write plan.

## Repair discipline

When investigating unstable staffing:

- Reproduce with an isolated, non-writing group solve at the normal bounded cap.
- Preserve `UNKNOWN` as indeterminate and `INFEASIBLE` only when proven.
- Do not respond to a poor incumbent by blindly increasing objective weights.
- If testing a hard staffing band, treat the tolerance as an explicit business rule. Verify it against clustered leave/request dates and cross-month feasibility.
- A stricter test that returns `UNKNOWN` is not evidence the band is impossible; a proven `INFEASIBLE` test is not permission to weaken labor constraints.
- Experimental solver patches must remain non-writing, receive syntax/regression checks plus an end-to-end preview, and be rolled back if qualification fails or is indeterminate.

## Writeback gate

Only write a preview when all are true:

- roster/source snapshot still matches the preview;
- hard constraints and exact rest counts pass;
- following-month feasibility is proven;
- staffing-quality metrics are reviewed and accepted;
- selected report path and group are explicit;
- approved live-write confirmation is current for that scope.

After writeback, verify values/formatting/readback, but do not confuse those delivery receipts with the pre-write quality gate.

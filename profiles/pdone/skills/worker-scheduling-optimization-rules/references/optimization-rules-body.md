## Core Principles

1. **Source policy; do not hard-code people.** Identify workers by stable `WorkerID` and keep effective role/rule rows in a dedicated configuration source.
2. **Separate constraints from preferences.** Legal limits, protected leave, hard rest, and required rest counts are hard constraints. Coverage and convenience normally begin as soft preferences.
3. **Keep raw requests raw.** Employee form submissions and `原資料` are not the place for management coverage policy.
4. **Resolve the live source from receipts.** A run tracker and live schedule source may be different workbooks. Use the typed scheduler preflight receipt to identify the active source spreadsheet and month.
5. **Make precedence explicit.** Every new objective must state what it may override and what it may never override.
6. **Compare behavior, not just score.** Run baseline and candidate previews against the same source snapshot and report business-facing deltas.
7. **Do not bundle unrelated repairs.** Report existing participant, destination, or request-history blockers separately.
8. No live schedule writeback during rule implementation QA. Writing a selected generated schedule is a later, explicitly confirmed operation.
9. Before a confirmed generated-schedule writeback, bind the selected preview to the final roster/AP:AT/source state through a fresh preflight/readback. A later roster, AP:AT, rollover, or source-control change invalidates older previews until re-solved.
10. A resumable writeback is not complete until every value batch, formatting batch, and final source readback succeeds. On tool timeout, preserve and resume the same output directory/state, selected groups, and batch caps; report actual completed/remaining batches and do not start another group or claim the monthly release complete until the current group has its final receipt.
11. **`FEASIBLE` is a hard-constraint status, not a staffing-quality approval.** Before accepting a preview, inspect the complete daily headcount series, target, minimum/maximum/spread, below-target days, adjacent-day swings, coverage misses, objective/bound, and cap exhaustion. Reject operationally implausible incumbents even if cross-month feasibility is proven. A 2-work/1-rest rhythm may score, but must not beat overall fluctuation. Count a denied rest request (`未`) as unstaffed: it is later assigned `特` unless it is truly impossible.
12. **Delivery receipts do not retroactively prove solution quality.** Value/format/readback receipts prove what was written. The selected preview must pass staffing-quality review before writeback; if a roster correction later exposes a bad schedule, re-preflight and re-solve the affected group rather than treating the earlier write receipt as qualification.
13. Keep solver repairs non-writing until qualified. If an experimental seed, objective, or hard-band change returns `UNKNOWN`, proves an unintended `INFEASIBLE`, or otherwise fails the business metrics, roll it back instead of leaving an unqualified default active.
14. **Qualify requested staffing intervals as explicit acceptance criteria.** Test the complete period/group-scoped band, then isolate upper- and lower-bound conflicts. A cap-only primary-month `INFEASIBLE` proof establishes that at least one primary-month day must exceed that cap; a two-month failure alone does not. Never combine independently generated per-worker primary calendars as a group staffing seed, and never accept a soft-bound result unless every realized daily count falls inside the requested interval.
15. **Search for the tightest feasible cap monotonically and preserve the best incumbent.** When a narrow band fails, test cap-only candidates upward under the normal runtime, preserve `UNKNOWN`, and use a proven infeasible cap to exclude every tighter cap. Save the first feasible report before attempting a higher floor. A realized floor may qualify the selected artifact even when it was not hard-enforced, but report that distinction explicitly and disable temporary bounds after preserving the receipt.
16. **Rebind identity-sensitive inputs after every roster refresh.** Source-row-derived WorkerIDs may shift after insertion, removal, or reordering. If a month-scoped override fails its expected-name/group guard, stop and reconcile the same person's current source row plus the historical basis for the exception; update only the scoped key if the identity and reason still match. Never weaken the guard or transfer the exception to whoever now occupies the old key. Also inspect any employee explicitly flagged for changed requests in the current parsed source and isolate the solve/write to that employee's actual current group.
17. **Do not turn incompatible worker probes into a grouped seed.** When a hard-cap run reports `primary_group_seed_status=UNKNOWN`, independent one-worker probes may each be feasible while using different primary calendars. Their fixed combination is not a group witness and may consume the authoritative search budget. Combine continuation probes only when they share one feasible grouped primary calendar; otherwise skip the fixed combination, preserve `UNKNOWN`, and leave more of the normal cap to the full joint model. Any seed-budget repair remains experimental until a fresh isolated run returns a complete terminal report; never write an `UNKNOWN` result.
18. **A soft preference is a candidate, not an automatic fallback.** The monthly staffing-bounds schema requires at least one hard minimum or maximum; use hard minimum `0` only as a schema-compatible no-op when testing a preferred minimum. Qualify the full realized series against the unrestricted incumbent, because a `FEASIBLE` soft result can still have a lower valley, unchanged peaks, or a wider spread. Reject non-improving candidates, distinguish parser rejection from solver status, revert experimental solver-budget edits, and restore temporary bounds before closeout.
19. **Verify objective wiring and diagnose synchronized early-month rests.** Do not assume a configured preference is active merely because it is parsed, validated, or printed in the report; trace it to an objective variable/expression and regression test. When a candidate concentrates discretionary rests on day 1 and creates the opposite peak on day 2, classify every rest by hard/requested/discretionary cause and inspect carryover before claiming it can move. If grouped seeding failed, independently generated worker calendars can synchronize on the same symmetry-equivalent rest pattern and form a feasible but poor incumbent. Treat a large objective/bound gap plus exhausted runtime as incomplete optimization, not as evidence that the imbalance is required. Prefer grouped staged/lexicographic smoothing over simply increasing one scalar weight, and report objective components, spread, and adjacent-day swings.
20. **Treat two-month seed budgets and incumbents as correctness-sensitive state.** All recursive primary, continuation, fixed-hint, and final optimization phases must share one measured outer runtime budget. A prior generated report may be a warm start only after period/group/full-roster validation; recursive worker probes may project strict subsets of that validated roster. Track hinted `(WorkerID, day-index)` keys and add each CP-SAT hint once—duplicate hints can produce `MODEL_INVALID`. Re-prove the exact following-month continuation after any primary change, remove one-run artifact paths from temporary config after qualification, and never write an older feasible artifact merely because later experiments failed. See `references/two-month-seed-budgeting-and-incumbent-safety.md`.

See `references/bounded-daily-staffing-qualification.md` for the reusable proof ladder, status semantics, group-level diagnostic boundaries, safe rollback, and the August 2026 worked example. See `references/bounded-cap-search-and-balanced-incumbents.md` for monotonic cap search, complete-group seeding, incumbent preservation, realized-band qualification, and compact staffing-distribution reporting. See `references/current-source-identity-drift-and-bounded-seed-unknown.md` for current-request group isolation, fail-closed override-key reconciliation, incompatible-probe `UNKNOWN` diagnostics, and soft-bound rollback. See `references/two-month-seed-budgeting-and-incumbent-safety.md` for shared recursive runtime accounting, incumbent validation/subsetting, duplicate-hint prevention, and writeback qualification.

## Source-Data Pattern

Prefer a dedicated bilingual rules tab such as `排班規則 Scheduling Rules`, with rows keyed by stable worker or coverage role. A general schema should support:

- `RuleID`
- `Enabled`
- `WorkerID` or a validated role selector
- `ScheduleGroup`
- `ManagementRole` / required skill
- `BiasType`
- `BiasMode`
- `Weight`
- target or minimum coverage
- leave/request protection flags
- `EffectiveFrom` / `EffectiveTo`
- `Notes`

Before using a row, validate that it is uniquely active for the target period, matches a worker in the intended scheduler group, and has valid dates/configuration. Zero or duplicate effective rows should be visible preflight failures, not silent no-ops.

Do not manually populate formula/spill-owned source ranges merely to expose a new rule. Join the dedicated rule source in the parser or surface it through controlled formulas after verifying ownership.

## Rule-Design Workflow

1. Write the business goal in observable terms: who needs to be present, on which dates, and why.
2. Identify the stable worker/role/skill source and its effective dates.
3. Classify each condition as hard constraint, protected input, soft preference, or tie-breaker.
4. Define eligibility and exclusions, especially leave, training, forced work/rest, and cross-month consecutive work.
5. Define precedence relative to staffing floors, employee requests, fairness, and rhythm objectives.
6. Add structured source rows and parser validation.
7. Add solver variables/objective terms only to the intended group.
8. Extend the generated report with coverage, misses, and reasons.
9. Add regression tests for positive, excluded, missing, duplicate, and cross-group cases.
10. Run baseline/candidate dry-runs from the same source snapshot.
11. Accept based on business metrics and hard-constraint safety, not objective value alone.
12. Record the selected preview and receipts in the monthly run tracker; obtain separate confirmation before any generated-schedule writeback.

## Weight Tuning

Weights are implementation details, not policy. Start with a bounded preview value located between lower-priority tie-breakers and the hard business outcome it must not defeat. Then inspect:

- coverage achieved;
- staffing-floor regressions;
- requested-rest denials;
- rest-day count and consecutive-work compliance;
- adjacent-day staffing swings;
- impact on workers outside the target rule.

If the result is wrong, first verify eligibility and precedence. Do not immediately increase weights to compensate for incorrect source mapping or exclusions.

## Safe Execution and Handoff

Use typed worker-scheduling MCP actions for normal preflight and solve previews. If a required add-tab or source-code patch is not available through a bounded specialist operation, route the exact implementation scope to the approved admin execution lane rather than bypassing safety with ad hoc shell access. Preserve the source thread, exact write targets, tests, and a prohibition on generated-schedule writeback unless separately approved.

Do not claim a rule is implemented until source readback, code/test receipts, and a relevant dry-run preview all agree.

### Isolated MCP repair verification

When validating a solver repair, run each schedule group independently through the typed MCP dispatcher. The supported payload field is `solve_groups`, and it must be a list, for example `{"solve_groups": ["manager_day"]}`. Do not use `group`, `solve_group`, or `run_group`: unknown payload keys may be ignored and accidentally start an all-group job. Before accepting the receipt, verify that the spawned command contains `--solve-group <expected-group>` and that the output directory has the expected group suffix.

Run one group to a terminal receipt before starting the next. Parallel group jobs create CP-SAT contention and Google read-quota pressure, while an all-group process can exceed its outer wrapper timeout or stop after the first failed group. If duplicate dry-run jobs were accidentally started, select one authoritative receipt, do not count duplicates as independent evidence, and wait for non-writing jobs/quota to settle before retrying. A `429`, wrapper timeout, or partial all-group receipt is a tool/runtime result—not solver infeasibility.

Inspect the active source and regression tests before patching. If the intended repair is already present, do not apply a duplicate edit; exercise the active runtime. For carryover repairs, require the day-1 reset witness, an exact-rest constructive witness, preserved cross-month 7/14-day protections, and isolated normal-cap previews for all four groups. A repair is demonstrated when the constructive regression passes and a formerly false blocker/status changes; remaining worker-local `INFEASIBLE` results must still be diagnosed rather than hidden by weakening rules or editing AP:AT.

## CP-SAT Infeasibility Diagnostics

When a monthly CP-SAT run is `INFEASIBLE`, distinguish solver proof, infeasibility-core extraction, and source-data diagnosis:

1. **Run assumption-core diagnostics single-threaded.** OR-Tools documents assumptions as incompatible with parallel search; use `cp_sat_num_search_workers=1` for the diagnostic solve. A parallel `INFEASIBLE` result may be valid while `SufficientAssumptionsForInfeasibility()` returns an empty or unusable core.
2. **Decode the API result as SAT literal indices.** In current Python OR-Tools, `sufficient_assumptions_for_infeasibility()` returns `Sequence[int]`; a negated literal is encoded as `-index - 1`. Accept integer results and literal-like `.Index()` wrappers, normalize negative literals safely, and prefer the lower-case API in new code because the uppercase form is deprecated.
3. **Treat the returned set as sufficient, not minimal.** Use it to localize investigation, not to claim a unique minimal conflict. Add a focused source/model proof for any proposed root cause.
4. **Validate carryover state and first-day reset semantics before model construction.** The first-day consecutive-work variable must equal `previous_consecutive_work_days + 1` only when day 1 is work, and must equal `0` when day 1 is rest. A source value above the configured maximum should be flagged as a prior-period data/law issue, but it does not by itself make the new month infeasible when day 1 is a legal reset rest. Never use `consec_day_1 = previous_consecutive_work_days + work_day_1`; that formula fails to reset on rest.
5. **Add decoder, carryover-reset, and model regressions.** Unit-test positive/negative integer literals and literal-like objects. Add constructive feasibility cases including `previous_consecutive_work_days=3`, rest on day 1, work on day 2, and an exact-11-rest 31-day witness. Integration-test genuinely contradictory hard inputs separately. Existing infeasibility-core tests must explicitly set `cp_sat_num_search_workers=1`.
6. **Challenge diagnostic probes with constructive witnesses.** A rest-count probe that says a worker becomes feasible only at 12 rests does not prove 11 is impossible if a concrete 11-rest calendar satisfies the named constraints. Validate the witness independently, then classify the discrepancy as a model/probe defect until the encoded recurrence and rolling windows are reconciled.
7. **Preserve every probe status.** An exhausted loop is not proof of infeasibility. Record each candidate count with `FEASIBLE`, `OPTIMAL`, `INFEASIBLE`, `UNKNOWN`, `MODEL_INVALID`, or the actual returned status. Never print “remained infeasible through N” when one or more candidates were merely `UNKNOWN`; retry the normal bounded path or validate a constructive witness. A short diagnostic cap must not silently become a policy recommendation.
8. **Audit cross-month exceptions roster-wide before changing the monthly default.** If the first anchored 14-day period contains exactly three counted prior-month rests, both target-month days 1 and 2 are required rests. When the next two disjoint 14-day periods each require five rests, that worker needs a 12-rest exception. Use exact active-roster joins and parser-recognized prior-rest markers; workers with fewer than three prior rests are historical violations, not ordinary exceptions. Keep the global default unchanged and use a validated month/WorkerID-keyed override.

See `references/cp-sat-infeasibility-diagnostics.md` for the API evidence and decoder shape, `references/cross-month-constructive-witness-analysis.md` for one-worker witness analysis, `references/cross-month-rest-count-exceptions.md` for the roster-wide boundary audit and per-worker override design, and `references/two-month-feasibility-lookahead.md` for joint primary/following-month modeling, proof semantics, explicit display-token-to-work hint decoding, authoritative grouped fixed-hint validation with safe fallback, symmetry control, and primary-only writeback.

### Constructive Witness Verifier

Before accepting a probe claim that a worker needs an extra rest day, run `scripts/validate_rest_witness.py` against any concrete calendar supplied by operations. It independently checks exact rest/work counts, day-1 carryover reset semantics, maximum consecutive work, and every 7-/14-day window wholly inside the target month. It deliberately reports cross-month windows as unevaluated unless exact prior-month calendar history is inspected separately; do not turn an internal-window pass into a full cross-month-law claim.

For a complete witness review, read the exact matched previous-month row, apply the parser's actual historical rest-marker classification, and evaluate the model's cycle-anchored cross-month periods. Report the counted dates and threshold for every failing period. If the witness fails an encoded cross-month rule, distinguish “solver search missed a valid schedule” from “the encoded policy disagrees with operations”; do not label the former until the witness passes every encoded hard constraint. See `references/cross-month-constructive-witness-analysis.md` for the reusable procedure and a worked W57 example.

Example:

```text
python scripts/validate_rest_witness.py \
  --days 31 \
  --rests 1,4,7,10,13,16,19,22,25,28,30 \
  --expected-rests 11 \
  --previous-consecutive 3 \
  --max-consecutive 3
```

Use the JSON receipt as a regression oracle. If the witness passes the named constraints but CP-SAT reports `INFEASIBLE`, investigate the encoded recurrence/window model before recommending policy or source-data changes.

# Solver runtime capping notes

Use this reference when comparing monthly worker scheduling solver caps after a successful dry-run/writeback.

## July 2026 manager-day low-staffing tuning

Andy manually adjusted the July 2026 `幹部-日` result to avoid days where only two managers were working. Preserve this as a durable solver preference:

- Keep the normal daily target at 3 managers (`min_workers_per_day_default = 3`).
- Penalize below-target staffing asymmetrically with `low_staffing_penalty_weight` so a 2-manager day is much worse than a 4-manager day, even though both are one away from target.
- The current default is `low_staffing_penalty_weight = 5000`, higher than fluctuation and request-denial weights.
- Verification receipt from the patched July preview: `/home/prodesign/.hermes/profiles/pdone/tmp/worker-scheduling-2026-07/learn-manager-day-low-staffing-patched-20260624/generated-schedule-report.json`; staffing readback showed target 3, days 1–23 and 26–29 at 3 managers, days 24/25/30/31 at 4 managers, and `low_staffing_days=[]`.

## June 2026 manager comparison

Context: after retuning manager scheduling toward staffing consistency (`rest_request_weight=100`, `fluctuation_weight=1000`, `work_2_rest_1_bonus=100`), Andy asked whether normal solver time could be capped at 180 seconds because longer runs did not appear to improve the schedule materially.

Observed dry-run/writeback comparisons:

- `manager_night` / `幹部-夜`
  - 600s cap: `FEASIBLE`, objective `19100.0`, best bound `18000.0`, elapsed about `600s`.
  - 180s cap with 60s no-improvement: `FEASIBLE`, objective `20400.0`, best bound `18000.0`, elapsed about `180s`.
  - Quality: 180s was slightly worse on objective, but daily staffing stayed balanced at 4/5 workers with no 2-worker or 3-worker low-coverage days.

- `manager_day` / `幹部-日`
  - 180s cap with 60s no-improvement: `FEASIBLE`, objective `11800.0`, best bound `10600.0`.
  - 600s cap with 90s no-improvement: `FEASIBLE`, objective `11800.0`.
  - Quality: no objective improvement from extending to 600s in this run.

## July 2026 operator-day staffing target tuning

Andy clarified that the single 7/21 `作業員-日` low-staffing day is acceptable because most operators are forced to rest that day, but the other operator-day dates should not have a wide 12–17 spread. Preserve this as a durable solver preference:

- Do not rely on manual forced-low day input. Detect forced-low days automatically from hard constraints: hard rest, protected leave, and special-work days that make the maximum staffable count far below the normal target.
- Operator groups (`day`, `night`) should use an automatic normal staffing target derived from required work slots, excluding detected forced-low days from the target divisor. For the 2026-07 `作業員-日` case, this should make the normal target about 14–15 while 7/21 gets its own constrained target of 3.
- Exclude adjacencies touching an automatically detected forced-low day from the normal adjacent-day fluctuation penalty so `17 → 3 → 17` does not consume the smoothness objective for the rest of the month.
- Current tuning after this change: `work_2_rest_1_bonus=50`, `staffing_penalty_weight=500`, `deviations_penalty_weight=500`, `fluctuation_weight=3000`, while keeping `low_staffing_penalty_weight=5000`.
- Regression coverage: `tests/test_shift_scheduler_solver.py::test_operator_day_auto_target_detects_forced_low_day` verifies automatic forced-low detection without manual day input.

## Recommendation pattern

For normal playbook solves, use a shorter cap first:

- `solver_max_time_seconds = 180`
- `solver_no_improvement_seconds = 60`

Escalate to 600s only when one of these is true:

- visible staffing imbalance remains, especially low-coverage days or large adjacent swings;
- Andy points to a specific unacceptable assignment;
- solver status, objective/bound gap, warnings, or generated output looks suspicious;
- the group is unusually constrained compared with normal monthly runs.

When reporting runtime comparisons, distinguish objective improvement from operational quality. A slightly better objective is not worth several extra minutes if the short run already preserves the main business constraint: stable daily staffing.
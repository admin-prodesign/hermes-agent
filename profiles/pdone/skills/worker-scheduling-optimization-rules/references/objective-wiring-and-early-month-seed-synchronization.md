# Objective Wiring and Early-Month Seed Synchronization

## Trigger

Use this diagnostic when a feasible monthly schedule has an obviously avoidable daily staffing valley/peak, especially when many workers independently rest on the first day and work on the second.

## Durable diagnostic pattern

1. Compare complete daily staffing counts, not only solver status or objective value.
2. For the suspicious dates, classify every rest as:
   - hard/protected leave;
   - cross-month or carryover-required reset;
   - employee-requested rest;
   - solver-selected discretionary rest.
3. Inspect each discretionary worker's prior consecutive-work state and the exact period/window constraints. A proposed day-1-to-day-2 shift is only a valid witness if exact rest totals remain unchanged and all carryover, 7-/14-day, role-coverage, and following-month constraints still pass.
4. Audit objective wiring, not just configured values. A setting that is parsed, validated, and printed in a report may still be a no-op if no variable or expression uses it.
5. Search for duplicate objective terms that multiply the same variable family. Treat duplicated penalties as ambiguous precedence until intentionally consolidated and covered by tests.
6. Inspect search receipts. If the grouped primary seed is `UNKNOWN` and one-worker probes are combined, many independent workers may choose the same symmetry-equivalent early rest pattern. A feasible fixed combined hint can therefore be operationally poor even though every hard constraint passes.
7. Compare objective value with best bound and account for seed time. A large gap plus cap exhaustion means the incumbent is not a staffing-quality result.

## August 2026 operator-night example

A 23-worker candidate assigned 17 rests on August 1 and 6 rests on August 2, producing staffing of 6 then 17 against a target of 15. Of the 17 August 1 rests:

- three were hard/cross-month required;
- one was a submitted request;
- thirteen were solver-selected discretionary rests.

For those discretionary workers, prior consecutive work was at most two days, so working August 1 and resting August 2 was not blocked by the maximum-three-consecutive-days rule. The complete revised calendar would still require authoritative August plus following-month validation, but the concentration itself was not explained by hard inputs.

The root causes found were:

- `preferred_minimum_workers_per_day` was parsed, validated, and reported but not connected to any constraint or objective penalty;
- the same coverage-deviation family appeared in two objective terms;
- independently generated one-worker calendars synchronized on similar early-month rest patterns;
- the grouped optimizer returned with a large objective/bound gap before repairing the seed.

## Preferred repair

Do not merely increase one scalar weight. Use a grouped, staged or lexicographic process:

1. Preserve hard leave, exact rests, carryover, labor windows, role coverage, and following-month requirements.
2. Solve the complete primary-month group together.
3. First minimize maximum staffing spread or maximum adjacent-day swing.
4. Then minimize total adjacent-day fluctuation and low-staffing shortfall.
5. Only then optimize requested-rest preferences, individual rhythm, and tie-breakers.
6. Fix the selected primary calendar and prove the following-month continuation.

Wire every configurable preference to a named variable family, include an objective-component breakdown in the report, and add a regression where several interchangeable workers must distribute rests across adjacent dates rather than synchronize on day 1.

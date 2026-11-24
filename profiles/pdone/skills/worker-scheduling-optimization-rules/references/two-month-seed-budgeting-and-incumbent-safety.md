# Two-Month Seed Budgeting and Incumbent Safety

## Purpose
Use when a two-month CP-SAT schedule regresses after continuation checks, a prior feasible report is reused as a warm start, or an incumbent-assisted run returns `UNKNOWN` or `MODEL_INVALID`.

## Coordinated seed invariant
The primary month must be solved for the whole group before following-month worker probes run. Independent worker probes may prove only worker-local continuation feasibility; they must never choose or replace the grouped primary calendars.

Required sequence:

1. Solve the complete primary-month group with staffing-quality terms active.
2. Accept only `FEASIBLE` or `OPTIMAL` as a primary candidate.
3. Hold that exact primary calendar fixed while constructing following-month continuations.
4. Validate the combined hint in the authoritative grouped two-month model.
5. Re-optimize primary quality only after fixed-calendar continuation feasibility passes.
6. Write only the primary month.

## One total runtime budget
Recursive phases must share one measured outer budget. Explicitly reserve time for:

- coordinated primary solve;
- fixed-primary continuation probes;
- grouped fixed-hint validation;
- final primary-quality optimization.

Do not give every nested solve the full outer cap. If the normal bounded run expires, preserve `UNKNOWN`; do not substitute a shorter diagnostic run or call the requested band infeasible.

## Incumbent report reuse
A prior generated report is a warm start, not proof.

- Validate run group, year, month, day count, and the full top-level WorkerID set.
- Recursive one-worker probes may project only a strict subset of that already validated set.
- Add at most one hint per CP-SAT variable. Track `(WorkerID, day-index)` keys across all seed phases; duplicate hints can make the model `MODEL_INVALID`.
- A hint may violate a tighter band. The new model must still prove every hard rule and the following-month continuation.
- Do not persist an absolute one-run artifact path as permanent production configuration. Remove it after qualification or use a bounded artifact registry.

## Objective and acceptance checks
- Trace each configured preference to a variable and objective expression; parsed/reported does not mean active.
- Avoid accidental duplicate charges on the same deviation variable.
- Keep grouped staffing quality above worker-rhythm tie-breakers.
- Review the entire daily series, including first and last days; fixing an early-month valley does not qualify an unexplained month-end peak.
- Report minimum, maximum, spread, maximum adjacent swing, total fluctuation, objective, best bound, and runtime phase usage.

## Regression coverage
Keep separate tests for:

1. Fast primary-only symmetric-worker balancing; assert a narrow group staffing spread.
2. Two-month exact-rest and cross-month hard-law feasibility.
3. Incumbent period/group/WorkerID validation.
4. Recursive subset projection.
5. Duplicate-hint prevention.

## Writeback gate
The exact report selected for writeback must have fresh preflight, complete `FEASIBLE`/`OPTIMAL` status, acceptable full-month staffing, exact primary rests, fixed-calendar following-month proof, code/test receipts for solver changes, and scoped write/readback receipts. Never write an older feasible artifact merely because later experiments failed.

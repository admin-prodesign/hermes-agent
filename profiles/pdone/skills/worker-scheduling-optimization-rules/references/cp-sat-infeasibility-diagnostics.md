# CP-SAT Infeasibility Diagnostics

Use this reference when a worker-scheduling CP-SAT preview is proven `INFEASIBLE`, especially when the reported assumption core is empty.

## API facts

The project venv inspected during the August 2026 diagnosis contains OR-Tools `9.15.6755`.

The installed Python API defines:

- `CpModel.add_assumption(lit)` by appending the literal's Boolean index to the model assumptions.
- `CpSolver.sufficient_assumptions_for_infeasibility()` as returning `Sequence[int]` and documenting that it returns assumption indices.
- SAT negation as `-index - 1` (`CpModel.negated(index)`).
- `SufficientAssumptionsForInfeasibility()` as the deprecated compatibility alias for the lower-case method.

The OR-Tools troubleshooting guidance says assumption-based infeasibility analysis is not compatible with parallelism; set `num_search_workers=1` for the diagnostic solve. A normal parallel solve can still prove `INFEASIBLE`, but its core should not be trusted as a diagnostic receipt.

## Safe decoding shape

For a map keyed by the positive Boolean variable index:

```python
def _decode_assumption_literal_index(raw_lit: Any) -> int | None:
    try:
        index_attr = getattr(raw_lit, "Index", None)
        if callable(index_attr):
            raw_idx = int(index_attr())
        elif index_attr is not None:
            raw_idx = int(index_attr)
        else:
            raw_idx = int(raw_lit)
    except (TypeError, ValueError, AttributeError):
        return None

    return raw_idx if raw_idx >= 0 else -raw_idx - 1
```

If named assumptions may themselves be negated, first look up the raw literal index directly, then use the normalized variable index only as a fallback. The current worker scheduler creates positive assumption BoolVars, so normalization to the positive variable index is sufficient for its current model.

Recommended decoder tests cover:

- `0 -> 0`
- `7 -> 7`
- `-1 -> 0`
- `-8 -> 7`
- a literal-like object with `Index() == 12`
- a literal-like object with `Index() == -13`

Every integration test that asserts `infeasibility_assumptions` should pass `cp_sat_num_search_workers=1`; otherwise the test relies on behavior OR-Tools explicitly does not guarantee.

## August 2026 day-group diagnosis

Receipt: `/home/prodesign/.hermes/profiles/pdone/tmp/worker-scheduling-mcp/20260722T064322Z_solve_preview_day_night_manager_day_manager_night/`

The day group returned `INFEASIBLE` with 20 workers and an empty core. The receipt also shows `cp_sat_num_search_workers: 8`, so the empty core is not evidence that the decoder failed.

The parsed source row for W42 / `喬那司 | ABALA MARK JONAS PADIGOS` contains:

- `previous_consecutive_work_days = 17`
- `max_consecutive_work_days = 3` from the solver configuration
- August hard rest day 21
- required rest count 11

### Correction: historical first-day carryover-reset bug

The historical model created this first-day recurrence:

```text
consec_W42_1 = previous_consecutive_work_days + work_W42_1
```

That recurrence is incorrect because a day-1 rest (`work_W42_1 = 0`) leaves the carryover count unchanged instead of resetting it to zero. It can therefore make day 2 look like an additional consecutive workday after a legal reset rest and can falsely report that an exact-11-rest calendar needs a twelfth rest.

The correct first-day semantics are:

```text
if work_day_1 == 1: consec_day_1 = previous_consecutive_work_days + 1
if work_day_1 == 0: consec_day_1 = 0
```

For a Boolean `work_day_1` and constant carryover, an equivalent bounded linear form is `consec_day_1 = (previous_consecutive_work_days + 1) * work_day_1`; later days must likewise set the counter to zero on rest and increment only on work.

A source value above `max_consecutive_work_days` should still be flagged as a prior-period data/law issue, but it is not an intrinsic new-month contradiction if day 1 is a valid rest. Do not silently clamp it. Verify the prior-month schedule, preserve the audit warning, and test the new-month reset correctly.

Required regressions include:

- `previous_consecutive_work_days=3`, day 1 rest, day 2 work: feasible with `consec_day_1=0`, `consec_day_2=1`;
- a 31-day exact-11-rest witness such as rests on `1,4,7,10,13,16,19,22,25,28,30`, which has a maximum August work streak of 2;
- a genuinely contradictory no-reset case tested separately;
- independent witness validation before accepting a rest-count probe's claim that 12 rests are required.

August 21 is a separate constrained-but-modeled day: 17 day workers have hard rest while W37, W39, and W40 have mandatory work. The operator auto-target logic is intended to detect this forced-low staffing day, so it is not the first suspected infeasibility once the W42 carryover contradiction is removed.

## Diagnostic reporting

Report separately:

1. solver status (`INFEASIBLE` is a solver proof);
2. whether core extraction was run serially and produced a non-empty receipt;
3. source rows whose carryover state is intrinsically contradictory;
4. other dense hard-rest/mandatory-work dates that are constrained but not independently infeasible;
5. every exact-rest probe candidate with its actual status and elapsed/cap information;
6. any constructive witness result, including exact rest dates, flex/special-leave choices, maximum consecutive work, and every encoded 7-/14-day period.

An exhausted candidate loop is not itself a proof. If the code accepts only `FEASIBLE`/`OPTIMAL` and falls through after `UNKNOWN`, timeout, or `MODEL_INVALID`, its summary must say the probes were inconclusive—not “remained infeasible through N.” A valid constructive witness disproves that diagnostic sentence even if the old artifact failed to retain the underlying per-candidate statuses.

Do not claim a unique minimal unsatisfiable core: OR-Tools returns a sufficient set, not necessarily a minimal one. Do not recommend a global monthly rest-count increase from one worker's boundary conflict; run the roster-wide method in `cross-month-rest-count-exceptions.md` and use per-worker, per-month exceptions.

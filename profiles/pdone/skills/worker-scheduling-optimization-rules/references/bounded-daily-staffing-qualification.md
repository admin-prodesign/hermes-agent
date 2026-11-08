# Bounded Daily Staffing Qualification

Use this procedure when operations requests a daily staffing interval such as “11–15 workers per day.” The interval is an acceptance criterion, not merely an objective-weight suggestion.

## Proof ladder

1. **Freeze the source snapshot.** Record period, group, roster count, exact-rest inputs/overrides, prior-month carryover, qualifications, and request semantics.
2. **Measure the baseline.** Report all daily counts, minimum, maximum, spread, and adjacent-day swings. A `FEASIBLE` baseline outside the requested interval is rejected.
3. **Test the complete hard band.** Add period/group-scoped lower and upper bounds and run the normal bounded primary+following-month solve. Do not turn the interval into a global default.
4. **Separate lower- and upper-bound conflicts.** If the full band is proven `INFEASIBLE`, test:
   - upper bound only; and
   - lower bound only when useful.
   An upper-bound-only primary-month proof of `INFEASIBLE` establishes that at least one day must exceed the requested cap under the frozen hard constraints. A full two-month failure alone does not localize the conflict to the primary month.
5. **Stage primary versus continuation proof.** First solve the complete group for the primary month under the staffing rule. If that is feasible, fix or hint that exact primary calendar while constructing following-month continuations, then validate the combined calendar in the full grouped joint model. Per-worker independent primary calendars must not be combined as a staffing-quality seed because their aggregate headcounts can fluctuate wildly.
6. **Accept only a realized interval.** Even when the lower edge is modeled as a strong preference rather than a hard bound, accept the result only if every reported daily count actually satisfies the requested interval and the following-month proof is `FEASIBLE`/`OPTIMAL`.

## Status and diagnostic rules

- `UNKNOWN` is indeterminate, never infeasible. Do not reduce the normal cap and reinterpret a shorter `UNKNOWN` as proof.
- Report which layer produced the status: primary-only group seed, continuation construction, fixed complete-hint validation, or final grouped joint solve.
- Model daily bounds with named assumptions such as `hard_staffing_minimum_day_N` and `hard_staffing_maximum_day_N` so receipts show that the requested rule was active.
- An assumption core is sufficient, not minimal. A broad core containing every daily bound does not identify one conflicting date; do not claim a specific day without a focused proof.
- Worker-local diagnostic probes do not explain group-level staffing-band infeasibility. Skip or separately budget per-worker probes after a group-level bound proof; otherwise diagnostics can run far beyond the nominal solver phase and add no relevant evidence.
- Static eligibility capacity is only a coarse check. A day can have 20 statically eligible workers while carryover, anchored rest periods, exact monthly rests, and mandatory/special-day constraints still force a staffing peak or trough.

## Safe configuration and rollback

- Store temporary bounds in a period/group-scoped configuration source with a reason and acceptance floor; never hard-code a person or make one month’s requested interval a global solver default.
- Keep all qualification runs non-writing.
- If the requested band is infeasible or a repair is `UNKNOWN`, disable/remove the experimental active bound before closing the task so future normal runs are not silently blocked.
- Preserve the dry-run receipt path, source snapshot, status, worker count, bound values, candidate update count, and `write_enabled=false` evidence.

## August 2026 lesson

For the 20-worker August 2026 day group after removing 沈拍玉, the baseline feasible incumbent ranged 5–19. A strict 11–15 band was proven infeasible. A second primary-only test with only the hard cap of 15 was also proven infeasible, establishing that the frozen August model required at least one day above 15. No generated schedule was written, September remained unwritten, and the experimental month-scoped bound was disabled afterward. This is a worked example of the proof ladder—not a reusable staffing-number policy for later months.

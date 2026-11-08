# Bounded cap search and balanced-incumbent qualification

Use this procedure when a feasible monthly schedule has operationally unacceptable daily headcount swings and the requested narrow band is infeasible or unresolved.

## Goal

Find the tightest feasible daily staffing cap while improving the realized floor, without weakening rest counts, leave, qualifications, labor rules, or following-month feasibility.

## Procedure

1. **Preserve a baseline receipt.** Record the full daily count series, minimum, maximum, target, adjacent-day swings, solver status, and following-month proof.
2. **Test the requested interval as hard bounds.** A complete primary-group `INFEASIBLE` result proves that interval impossible for the primary month. A joint two-month failure alone does not localize the blocker.
3. **Isolate the upper cap.** Remove the hard floor, retain the candidate hard maximum, and keep the normal balancing objective. Accept `INFEASIBLE` only from a complete authoritative solve; preserve `UNKNOWN` exactly.
4. **Exploit cap monotonicity correctly.** If `staffed[d] <= C` is infeasible for every day, every tighter cap below `C` is also infeasible. Thus a later proof that cap 17 is infeasible also resolves an earlier cap-16 `UNKNOWN` as impossible. The reverse inference is invalid.
5. **Search upward one cap at a time.** Stop at the first `FEASIBLE`/`OPTIMAL` cap. This is the tightest proven feasible maximum only when the immediately lower cap is proven infeasible (or excluded by monotonicity).
6. **Improve the floor constructively.** Preserve the first feasible report before trying a hard floor. Increase the floor conservatively under the same cap and normal runtime. If the tighter attempt is `UNKNOWN` or `INFEASIBLE`, retain the prior qualified report rather than losing it.
7. **Allow realized-band qualification.** A candidate solved with a softer/lower configured floor may still qualify a stricter operational floor when every realized daily count meets it. Report both the configured hard bounds and the realized range; do not imply the stricter floor was solver-enforced.
8. **Require the authoritative joint witness.** Final acceptance requires the full grouped primary+following-month model to be `FEASIBLE` or `OPTIMAL`, the primary month to admit the continuation, and every modeled following-month worker to have the exact supplied rest count.
9. **Review the full distribution.** Report compact date ranges at each headcount, not only min/max. Include target-day frequency, boundary spikes, qualification/skill-coverage warnings, objective/bound, and whether the runtime cap was reached.
10. **Keep it non-writing.** Preserve the selected output directory and report, confirm `write_enabled=false`, verify no write receipt, and disable temporary period-scoped bounds after the experiment. A later writeback must use the selected report and obtain separate scope-specific confirmation.

## Seed correctness

- Build a complete primary-month group seed with the candidate hard cap/band; never combine independent per-worker primary calendars as if they proved group staffing quality.
- For continuation probing, fix each worker's exact primary calendar and solve the following month.
- Use the complete calendars only as hints for the authoritative joint solve. Do not force the first seed if the full model can find a different valid primary calendar.
- Seed, probe, and fixed-hint statuses are diagnostic. Only the final complete group status is authoritative.

## Status language

- `FEASIBLE` / `OPTIMAL`: valid hard-constraint witness; still requires staffing-quality review.
- `INFEASIBLE`: proven contradiction at the scope actually solved.
- `UNKNOWN`: indeterminate runtime result; never relabel as infeasible and never rerun with a much shorter cap merely to obtain a status.

## Compact reporting example

Prefer:

- baseline `5–19`;
- selected realized range `11–18`;
- days 1–3: 11, days 4–26: 13, days 27–28: 12, days 29–30: 13, day 31: 18;
- cap 17 proven infeasible, cap 18 feasible;
- following month feasible with exact rests;
- no write.

This makes the operational improvement and remaining boundary spike visible without dumping the whole schedule.
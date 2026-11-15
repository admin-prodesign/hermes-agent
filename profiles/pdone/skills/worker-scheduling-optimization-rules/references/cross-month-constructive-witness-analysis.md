# Cross-Month Constructive Witness Analysis

Use this reference when operations supplies a hand-built schedule that appears to disprove an `INFEASIBLE` result or a rest-count probe.

## Required comparison

Do not evaluate only the target-month row. Reconstruct the exact model inputs:

1. Read the live target-month employee row and date headers; derive the explicit rest dates.
2. Read the exact matched previous-month employee row used by the solver.
3. Apply the same historical marker classification as the parser. For the current Pro-Design scheduler, previous-month rest history counts literal `V` and `申`; do not silently count other markers.
4. Verify target-month exact rest count and day-1/max-consecutive recurrence.
5. Enumerate the model's cycle-anchored 7-day and 14-day periods from the configured cycle start. Do not substitute generic calendar weeks or only windows wholly inside the target month.
6. For each cross-month period, count fixed previous-month rests plus target-month rests. Report exact dates, count, and minimum.
7. Separate soft requests from hard constraints. A denied requested rest may affect objective quality without causing infeasibility.

## Classification rule

- If the hand-built witness passes exact rest count and max-consecutive work but fails an encoded cross-month period, the solver did not miss the possibility; the remaining question is whether the encoded policy matches intended business/legal policy.
- If the witness passes every encoded hard constraint using the exact same previous history and marker classification, treat the discrepancy as a model/probe defect and add the witness as a regression before recommending extra rest days.
- Never recommend a source or policy change merely from `first feasible at 12`; first produce the constructive proof or exact failing period.

## August 2026 W57 example

Live August rests were `1,4,7,10,13,16,19,22,23,26,29` (11 total). The schedule passed maximum consecutive work and every encoded 7-day period.

The failing model period was `2026-07-20..2026-08-02`, requiring five rests. The matched July row contributed rests on July `23,26,29`; August contributed only August `1`, for four total.

The next two disjoint 14-day periods, `2026-08-03..2026-08-16` and `2026-08-17..2026-08-30`, each already required and contained five rests. Therefore the encoded periods require at least `2 + 5 + 5 = 12` August rests with that fixed July history. This explains the probe without claiming that the cycle-anchored policy itself is necessarily correct.

## Reporting format

Return:

- target-month rest dates and count;
- maximum consecutive work result;
- each 7-/14-day period with counted dates and threshold;
- the exact failing constraint name when available;
- whether the discrepancy is search/model failure or policy-semantics disagreement;
- confirmation that the investigation was read-only.

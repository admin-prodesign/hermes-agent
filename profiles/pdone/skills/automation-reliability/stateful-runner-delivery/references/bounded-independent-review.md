# Bounded Independent Review and Verdict Recovery

Use this pattern when a code-remediation task needs an independent PASS/FAIL but a broad reviewer risks exhausting its time or context budget.

## Freeze before dispatch

Record the exact implementation and test approval set before review:

- file paths plus SHA-256 and byte size when the permitted surface supports them;
- the exact fixed compile/unit-check tool or command;
- the prior findings that must be closed;
- the reviewer boundary: read-only, no deployment, no external sends.

Any implementation or test edit after the review starts invalidates that verdict. Re-run the fixed checks and request a fresh review against the new hashes.

## First-pass review

Ask the reviewer to:

1. run the fixed checks once;
2. inspect only the changed state transitions, side-effect boundaries, and directly relevant tests;
3. issue scoped P0/P1/P2 findings and a code-only PASS/FAIL;
4. distinguish code PASS from operational release GO.

Broad repository discovery is useful only once. Avoid repeatedly reading entire large source files when exact method ranges and earlier transcripts already identify the review surface.

## Timeout recovery

A completed tool trace or green test run is not a verdict. If the reviewer times out before writing PASS/FAIL:

- do not infer PASS from silence, task completion, or checked-off reviewer todos;
- preserve the complete append-only transcript as evidence;
- dispatch a verdict-only reviewer with the transcript path, frozen hashes/sizes, exact method ranges, and prior findings;
- cap the second pass to a small number of tool calls and one run of each fixed check;
- forbid edits so the second pass remains independent.

The focused reviewer should reuse the first pass rather than repeat broad discovery. Its output must state whether hashes were independently recomputed or only compared by size/path because the read-only surface lacked a hash primitive.

## Verification receipt

After the verdict:

- recompute hashes from the controlling lane if possible;
- write a versioned receipt rather than silently mutating the pre-review baseline;
- record exact test totals, review verdict, P0/P1/P2 counts, and remaining non-code gates;
- keep employee/live submissions disabled while any qualification, trust, execution-surface, deployment, or live-readback gate is open.

## Common pitfalls

- Treating a timeout as a PASS because no finding was emitted.
- Letting a reviewer edit code and still calling the verdict independent.
- Reusing a PASS after any reviewed code or test changed.
- Re-running broad discovery instead of using the earlier transcript and exact line ranges.
- Claiming independent hash verification when the reviewer only checked byte sizes.
- Calling code PASS a release GO while native qualification or deployment evidence is missing.

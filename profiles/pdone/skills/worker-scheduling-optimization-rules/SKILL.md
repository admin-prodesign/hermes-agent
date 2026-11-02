---
name: worker-scheduling-optimization-rules
description: "Design, implement, and verify source-backed staffing preferences and constraints for monthly worker-scheduling solvers."
metadata:
  hermes:
---

# Worker Scheduling Optimization Rules

## Overview

Use this skill when adding or changing business rules in a monthly workforce scheduler: role/skill coverage, weekday/weekend preferences, staffing floors, rotation, fairness, leave-aware biases, or objective weights.

This is a companion to `monthly-worker-scheduling`:

- `monthly-worker-scheduling` governs the operating cycle, source rollover, solves, writeback, HR MAX, and monthly receipts.
- this skill governs how a **new scheduling rule** is modeled, sourced, implemented, tested, and introduced without turning policy into brittle code.

Load the monthly skill as well before touching live Pro-Design scheduling data or running its solver.

## Core principles through CP-SAT diagnostics
Load `references/optimization-rules-body.md`. For infeasibility work, also load `references/cp-sat-infeasibility-diagnostics.md`.

# Worker Scheduling Optimization Rules

## Overview

Use this skill when adding or changing business rules in a monthly workforce scheduler: role/skill coverage, weekday/weekend preferences, staffing floors, rotation, fairness, leave-aware biases, or objective weights.

This is a companion to `monthly-worker-scheduling`:

- `monthly-worker-scheduling` governs the operating cycle, source rollover, solves, writeback, HR MAX, and monthly receipts.
- this skill governs how a **new scheduling rule** is modeled, sourced, implemented, tested, and introduced without turning policy into brittle code.

Load the monthly skill as well before touching live Pro-Design scheduling data or running its solver.

## Verification Checklist

- [ ] Live source workbook resolved from scheduler preflight.
- [ ] Stable identity/role source verified for the effective period.
- [ ] Rules tab/schema read back successfully.
- [ ] Exactly one intended effective rule is active, or multiplicity is explicitly supported.
- [ ] Hard constraints and protected inputs remain dominant.
- [ ] Rule affects only intended schedule groups and eligible dates.
- [ ] Required rest counts and consecutive-work constraints remain valid.
- [ ] A separately supplied following-month rest count is present; the joint model proves the first-month schedule admits a feasible full following month while ignoring following-month requested-rest preferences, and only first-month cells are eligible for writeback.
- [ ] Any month-scoped rest override is keyed by resolved period + WorkerID, verifies expected name/group, permits only the approved transition, and appears as a structured applied-override receipt.
- [ ] For every overridden worker, day 1/day 2 are counted rests and `rest_v + rest_requested` equals the effective required-rest total.
- [ ] Generated report explains coverage and misses.
- [ ] Daily staffing quality was explicitly reviewed: target, all daily counts, min/max/spread, below-target days, adjacent-day swings, objective/bound, and runtime-cap status are operationally acceptable. `FEASIBLE` alone is not acceptance.
- [ ] If operations requested a bounded interval, every realized daily count falls inside it; any infeasibility claim identifies whether it was proved in the primary-only group model or only in the joint lookahead model, and failed experimental bounds were disabled before closeout.
- [ ] Baseline and candidate previews use the same source snapshot.
- [ ] Tests cover missing/duplicate config, exclusions, and cross-group isolation.
- [ ] No live generated-schedule write occurred during implementation QA.

## References

- `references/bounded-daily-staffing-qualification.md` — proof ladder for requested daily staffing intervals, primary-versus-lookahead localization, cap/floor isolation, non-minimal assumption-core cautions, and safe experimental-bound rollback.
- `references/bounded-cap-search-and-balanced-incumbents.md` — monotonic cap search, complete-group seed correctness, best-incumbent preservation, realized-band qualification, and compact staffing-distribution reporting.
- `references/post-solve-staffing-quality-gates.md` — mandatory post-solve quality review, roster-change invalidation, poor-incumbent handling, experimental repair rollback, and the distinction between solution quality and write-delivery receipts.
- `references/2026-08-carryover-repair-and-isolated-mcp-verification.md` — exact `solve_groups` MCP selector, one-group-at-a-time verification pattern, carryover reset acceptance evidence, and handling of duplicate/partial runtime receipts.
- `references/cross-month-constructive-witness-analysis.md` — procedure for checking a hand-built schedule against exact prior-month history, marker classification, and cycle-anchored 7-/14-day periods; includes the W57 worked example.
- `references/cross-month-rest-count-exceptions.md` — roster-wide audit for workers forced to rest on both target-month days 1 and 2, classification of 12-rest exceptions versus historical violations, per-worker override design, and probe-status reporting discipline.
- `references/two-month-feasibility-lookahead.md` — joint two-month horizon semantics, required dual-month inputs, boundary constraints, proof/status fields, symmetry-control search staging, non-authoritative hint-probe warnings, regressions, and primary-only writeback.
- `references/objective-wiring-and-early-month-seed-synchronization.md` — diagnose parsed-but-unused preferences, duplicate objective terms, synchronized day-1 rests from independent worker seeds, objective-gap evidence, and grouped staged smoothing repairs.
- `references/two-month-seed-budgeting-and-incumbent-safety.md` — shared recursive runtime accounting, coordinated-primary seed invariants, safe report-incumbent validation/subsetting, duplicate-hint prevention, regression coverage, and final writeback gates.
- `references/manager-day-weekend-supervisor-bias.md` — Pro-Design pattern for preferring a day-shift 課長 on eligible weekends, including live-source resolution, role verification, rule schema, solver precedence, and receipts.

# Current-Source Identity Drift and Bounded-Seed UNKNOWN

## Purpose

Use this note when a monthly roster/request refresh changes source-row-derived WorkerIDs or when a hard staffing cap changes a previously feasible joint solve into `UNKNOWN`.

## Current-source and group isolation

- Re-read the exact current parsed request row for every employee explicitly flagged by operations.
- Report the employee's current run group before solving. A changed request in another group is evidence to acknowledge, not permission to solve or write that group.
- Compare current source markers with the published destination, but bind the candidate report to the current source snapshot. Never reuse an older preview after request, roster, AP:AT, or control changes.

## Fail-closed WorkerID drift

Some scheduling WorkerIDs are derived from source row positions and may shift after roster insertion, removal, or reordering. Month-scoped exceptions must therefore retain identity guards.

If an override key now resolves to another person:

1. Stop before solve/write; do not weaken the guard.
2. Reconcile the exact current source row, employee name/identity, run group, and historical basis for the exception.
3. If the same person remains and the exception still applies, update only the month-scoped key while preserving expected name, expected group, required-rest transition, and reason.
4. Require the generated report to show the corrected applied override for the intended person.
5. Never retarget an exception merely because the old key now belongs to another worker.

## Bounded-seed UNKNOWN pattern

Observed diagnostic shape:

- unrestricted joint primary/following-month model returns `FEASIBLE` but poor staffing spread;
- adding any hard cap returns `UNKNOWN` under the normal runtime;
- `feasibility_phase.primary_group_seed_status` is `UNKNOWN` and worker count is zero;
- independent one-worker continuation probes are individually feasible;
- their fixed combined hint is `INFEASIBLE` because each probe generated a different primary calendar;
- the authoritative grouped feasibility search receives little remaining time and returns `UNKNOWN`.

Interpretation: this is a search-path/runtime result, not proof that the cap is infeasible.

Safe response:

- Never combine independently generated per-worker primary calendars as a group seed.
- Continuation probes may be fixed together only when they share one feasible grouped primary-month calendar.
- If the common grouped seed is unavailable, skip incompatible fixed-combination attempts and reserve budget for the authoritative grouped model.
- Keep the total normal solver cap and all hard constraints intact unless a separately reviewed change authorizes otherwise.
- A budget-allocation or seed-path repair remains experimental until a fresh isolated solve returns a terminal `FEASIBLE`/`OPTIMAL` report with complete current-source, staffing, rest-count, and following-month receipts.
- `UNKNOWN` is never writeable. Preserve the last qualified incumbent; if none exists, stop without schedule writes.

## Soft-bound fallback and rollback

A soft staffing preference is not automatically a safe fallback after capped runs time out.

- The `worker-scheduling-monthly-staffing-bounds.v1` loader requires every entry to contain at least one hard `minimum_workers_per_day` or `maximum_workers_per_day`; `preferred_minimum_workers_per_day` alone is schema-invalid.
- If a soft-only experiment is needed without excluding schedules, a hard minimum of `0` plus the preferred minimum is the schema-equivalent configuration. Treat this as an experiment, not a qualified policy default.
- Compare the full realized daily series against the unrestricted incumbent. A preferred-floor result may still have a lower minimum, the same peaks, or a wider spread because `FEASIBLE` does not mean the objective was optimized within the cap.
- Reject a soft candidate that is not materially better on the requested business metric, even when its objective value is numerically lower and following-month feasibility is proven.
- After unsuccessful bounded or soft experiments, restore the staffing-bounds file to its prior state (often an empty `entries` list), revert unqualified solver-budget edits, and verify that no live write action occurred.
- Do not describe an experimental config-parser failure as solver infeasibility: it failed before model construction and provides no scheduling evidence.

## Qualification after repair

Before writeback, verify:

- selected group only;
- current source snapshot and exact request changes;
- applied month overrides match expected names/groups;
- complete daily staffing series and realized min/max/spread;
- exact primary-month rest totals;
- following-month feasibility proof;
- fresh preflight immediately before write;
- full value, format, and readback receipts;
- destination-only legacy rows for removed workers are explicitly cleared or otherwise resolved.

# August 2026 Carryover Repair and Isolated MCP Verification

## Durable technique

The worker-scheduling MCP group selector is `solve_groups` as a list:

```json
{"solve_groups": ["day"]}
```

The returned command must include `--solve-group day`. Keys such as `group` or `solve_group` may be ignored and can accidentally start all four groups.

Run one group at a time to a terminal receipt. Parallel or accidental duplicate jobs can contend for CP-SAT resources and Google read quota; a `429`, wrapper timeout, or partial all-group result is not infeasibility evidence. Use exactly one isolated receipt per group as authoritative.

## Carryover semantics verified

The repaired recurrence is:

- day 1 work → `previous_consecutive + 1`;
- day 1 rest → `0`;
- later work → prior consecutive value + 1;
- later rest → `0`.

Verification must preserve cross-month 7-day and 14-day rest laws and include a constructive exact-rest witness. Inspect the active source and tests first; if the repair is already present, avoid a duplicate patch and verify the active runtime.

## Observed acceptance evidence

Using the confirmed August source and normal-cap isolated previews:

- Day Operators changed from `INFEASIBLE` to `FEASIBLE` with all 21 workers planned.
- Nomer was no longer an individual blocker at exactly 11 rests.
- Night retained two workers whose first feasible exact rest total was 12.
- Manager-day retained one 12-rest conflict and four worker-local conflicts unresolved through 15 rests.
- Manager-night retained one 12-rest conflict and three worker-local conflicts unresolved through 15 rests.

This separates the repaired false infeasibility from remaining source-backed hard constraints. Do not change AP:AT or weaken labor constraints merely to force all groups to `FEASIBLE`.

All authoritative runs were previews with `live_write_requested=false`; candidate schedule cells were not written.

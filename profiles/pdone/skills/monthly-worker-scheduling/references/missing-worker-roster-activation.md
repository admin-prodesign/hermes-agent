# Approved missing-worker roster activation: bounded execution and fail-closed handling

Use this note when a target-month schedule already displays a worker name or leave markers, but the worker is not yet an active solver participant.

## Distinguish staged display rows from active roster rows

A destination row is not an active roster entry merely because the name and early-month markers are visible. Verify together:

- stable worker ID (not blank or `#N/A`);
- intended shift/class field is populated;
- exactly one matching name/ID appears on the intended destination tab;
- the source statistics `B:D` manual row exists with the intended class, exact name, and verified previous consecutive work days;
- formula-owned structured fields resolve for that source row;
- the worker is absent from night/manager groups unless separately authorized.

For operator tabs whose date row maps day 1 onward to schedule columns, read the exact worker row and map dates from the live date row rather than assuming fixed letters. Early markers can already be correct while identity/shift activation remains incomplete.

## Minimal bounded readback sequence

1. Run `source_setup` dry-run to verify the target year/month/rest controls are already current.
2. Run scheduler `preflight` and search parsed records for the exact worker ID/name.
3. Read the intended destination row narrowly enough to include identity, shift, grade, carryover, and the required marker dates.
4. Read the candidate source row across `B:AX` to distinguish manual `B:D` cells from spill/formula-owned output.
5. Read night and manager rosters when the authorization explicitly prohibits changes there.

A source→destination preflight reporting zero missing matches does **not** prove the reverse direction. A destination-only staged worker can remain invisible to preflight when absent from source records.

## Write-capability gate

Roster inclusion/exclusion is a non-routine write. Use a dedicated worker-scheduling action that can:

- dry-run exact source and destination ranges;
- write only source manual `B:D` plus the exact intended destination identity/shift cells;
- preserve `E:AI`, `AK:AO`, `AU:AX`, formulas, formatting, and unrelated tabs;
- reject duplicate IDs/names and cross-group writes;
- return post-write source and destination readbacks.

Andy 2026-09-23 standing rule: dest-only employed names on the target-month schedule tabs **must be added** to the request list (`申請日期-當月統計` `B:D`) so the solver cannot skip them. Do not wait for a separate include prompt for dest-only operators. If the dispatcher still lacks a roster-add action, Andy/admin sessions may use the bounded `sheets_safe_ops.py` `B:D`-only write used for 2026-10 達迎, then read back spill. Do not write `E:AI`, `AK:AO`, `AU:AX`, and do not invent Forms/`原資料` rest rows.

## Blocked-result evidence

When fail-closed blocking is required, preserve concise evidence:

- exact destination row/range showing current identity, shift, and marker state;
- exact source row/range showing the worker is absent;
- scheduler preflight receipt path;
- the dedicated dispatcher’s allowed-action response;
- explicit statement that no source, destination, night, or manager cells were modified.

Do not report the worker as scheduled until stable ID, shift, source participation, and post-write readback all agree.

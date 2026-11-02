# Source-stats formula spill repair and grouped writeback recovery

Use this reference when maintaining `申請日期-當月統計` for a monthly worker-scheduling run and a missing worker must be added, or when a generated writeback times out mid-run.

## Critical pitfall: manual fields vs formula-owned fields

`申請日期-當月統計` has manual participation fields followed by formula/spill-owned structured columns. For a missing worker addition, write only the manual fields:

- `B:D` = class, name, previous consecutive work days.
- Do **not** write `E:AI` visual request grid unless explicitly verified and intended.
- Do **not** write `AK:AO` or `AU:AX`; these are arrayformula-owned structured fields such as `WorkerID`, `Name`, `Grade`, `TotalDaysInMonth`, `RequiredRestDaysCount`, `Year`, and `Month`.

If formula-owned cells are accidentally populated, the header or spill range may show `#REF!`. A `#REF!` in `WorkerID`, `Name`, `Grade`, `TotalDaysInMonth`, or `RequiredRestDaysCount` can make the parser fail. A `#REF!` in `AO1` (`RequestedRestDays`) does not fail closed. The parser renames that header when it sits between `PreviousConsecutiveWorkDays` and `HardRestDays`, then reads the cells below. Leftover typed values become the whole request set.

## RequestedRestDays spill block

`AO` is formula-owned. Do not type day lists into it. `sheets_safe_ops.py` refuses a value write into `E2:AJ70`, `AK1:AO70`, or `AU1:AX70` on this source sheet. Before every solve:

1. Read `AO1`, `E2`, and `AK1:AX1` as formatted values. Any `#REF!` means stop and flag that cell before solve. Do not proceed.
2. Find the typed cells in `AO2:AO` that block the spill. Clear only those cells.
3. Read `AO1` back. It must be the header text `RequestedRestDays`, not `#REF!`.
4. Count target-month dates in `原資料!K:O`. Compare them with non-blank AO lists and with parsed `requested_rest_days`.
5. Sample one row whose dates cross months. Column V uses only the first date. Column W joins every day number and ignores month. A first date outside the target month drops later target-month dates. A first date inside the target month injects other months' day numbers. A green spill is not a complete capture.
6. If raw dates are many and AO is nearly empty, or the sample does not match, do not solve and do not write the schedule.

## Replace the AO formula

Clearing typed blockers only unblocks the spill. The old formula is still wrong if it filters on column V and joins column W.

1. Probe the live grid before writing the formula. A range past the sheet's max row returns `#REF!`. Do not use an open `$C$2:$C` spill, and do not guess a raw row past the grid.
2. Put the header in `AO1`. Map only source rows that exist, from `C2` through the last source row.
3. For each source name, test each date in `原資料!K:O` separately. Keep the day only when `YEAR` equals `A2` and `MONTH` equals `A4`. Wrap `原資料!B` and `原資料!AJ` in `ARRAYFORMULA(IFERROR(...,""))` before the test. A `#N/A` in column B poisons `FILTER` and blanks the spill. Do not collect the days with a nested `LAMBDA` or `FILTER`. Those calls drop rows even when the name matches. Test each day with `SUMPRODUCT` inside the `MAP`. Before solve, read back `楊正義`, `林三原`, `阮紅蓉`, `帕薩`, `林玉彩`, and `珍安`.
4. Match `原資料!B` to source column C exactly, including the full `Chinese | ENGLISH` form. A short name does not match a bilingual source name.
5. Keep the status rule: include a raw row only when `AJ` starts with `-`. Build that test with `ARRAYFORMULA(LEFT(status_range&"",1)="-")`. A bare `LEFT` inside `LET` evaluates only the first cell. If that cell does not start with `-`, the header still spills and every data row is blank. List excluded status rows in the audit. Do not call them captured, and do not widen the status rule unless the requester changes it.
6. Emit a zero-padded day list such as `01, 02`. The `申` grid and `parse_day_list` both read that text. Do not type the list into AO.

## E2 calendar spill block

`E2:AJ` is formula-owned. It paints `申` from `AO`. Do not type values into that range. Do not apply cell format there. An empty-looking cell with stored format still blocks the spill. The error names the first blocking cell, for example `AF21`. Clearing the displayed text is not enough. Clear both `userEnteredValue` and `userEnteredFormat` on the spill range, and keep the formula in `E2`. Writing `""` through a values update can leave a blocker. Use a cell clear, then read `E2` back. It must not be `#REF!`.

The spill ranges `E2:AJ70`, `AK1:AO70`, and `AU1:AX70` must stay write-protected. Protection is a hard block, not a warning. Only `admin@prodesign-group.com` may be an editor. Do not remove that protection. `sheets_safe_ops.py` also refuses a value write into those ranges. A formula write is allowed only in `AO1` or `E2`. Use a cell clear, not an empty value, to remove a blocker. Do not paint borders back onto the spill cells.
7. Read `AO1` back as `RequestedRestDays`, then read several data rows. A header with blank rows below is a failed formula, not a successful capture. Then check three samples: a same-month row, a row whose first date is outside the target month, and a row whose first date is inside the target month but which also has a date in another month. The foreign day must not appear.
8. Answer "fully read" only from preflight `requested_rest_days`, not from `audit_rest_requests`. That action flags submission-month mismatches on blank-AD rows. It does not compare target-month dates with AO. An empty parsed list still needs a raw check. Say separately whether the visual `申` grid is empty, and whether the last solve used this parse.

## Which group to redo

Answer "were requests read" from a date-by-date compare, not from parsed empty lists or a write receipt.

1. Read `AO1` as formatted text. `#REF!` stops the claim.
2. Read `原資料!B:C` and `K:O` on the same start row. Sheets omits trailing blank rows, so a short `row_count` is not an empty column. Map the sheet row as the start row plus the index.
3. Keep a raw day only when the year and month match the source controls, the raw name matches source column C exactly, and `AJ` starts with `-`. `- 未決定 Unprocessed` matches. A blank `AD` does not exclude it.
4. Compare that day with the same worker's AO list. A first date inside the target month can still be missing. Do not treat "the formula should have included it" as captured.
5. If any worker in a run group is missing a qualifying day, that whole group needs a new solve. Do not resume the old output dir. A few workers with `申` do not clear the group. An unfinished cadre solve still needs a redo when AO is empty and raw dates exist.
6. Do not count a company flex day as a missed request. Report a raw date that is also mandatory work as a conflict, not as a day to grant.
7. `mismatched_actions=0` only proves the sheet matches the generated report. All `V`, `rest_requested=0`, and no `申` means the solve ignored requests. Stop writeback.

## Repair pattern

1. Dry-run/live write the worker only to `B:D`.
2. Dry-run/live clear the same row's formula/spill-owned range, at minimum `E:AX` for that row if it was accidentally populated.
3. Read back the header row with formulas rendered, e.g. `A1:AX1 --render FORMULA`; verify the structured columns are formulas/headers, not `#REF!`.
4. Read back the worker row; expected formula-populated fields should reappear automatically, e.g. `WorkerID`, name, grade, month/year, days-in-month, required-rest count.
5. Rerun scheduler dry-run and confirm parse succeeds with `missing_destination_match_count=0`.
6. Rerun the bidirectional name cross-check using **real employee rows only**:
   - ignore schedule footer/summary rows such as `X`, `休假人數`, `幹部人數`, `日上班人`, `夜上班人`, and `#N/A` placeholders;
   - compare schedule names against nonblank-class source stats names;
   - keep blank-class source rows as intentional exclusions only when verified, e.g. transferred/out-of-company rows.

## Grouped writeback timeout recovery

Generated schedule writeback may complete a group and then the terminal call can time out before all groups finish. Do not assume the whole run failed or succeeded.

Recovery steps:

1. Inspect the output directory and the per-group `generated-schedule-write-report.json` / `generated-schedule-write-verification-report.json` receipts.
2. Before resuming, confirm that group's generated report contains `申` for every qualifying raw request. A clean verification does not prove capture. If requests are missing, discard that output dir and solve again after AO is repaired. Do not write cadre groups from an operator report that has no `申`.
3. If one group completed before timeout and its requests were captured, rerun only the remaining or uncertain group(s) with `--solve-group <group>` and the same approved solver caps.
4. Record each group's output directory separately.
5. Aggregate final receipts across all groups:
   - `groups_with_write_failures` should be `0` for every group;
   - verification mismatches should be `0`;
   - if a rerun reports `0` checked/changed actions because the first attempt already wrote the values, explain that with the first attempt's write receipt and the rerun's `groups_written=1 / failures=0` receipt.
6. Append one tracker row with the source repair receipts, dry-run receipt, cross-check receipt, output directories, and aggregate summary.

## Tracker note

When recording this class of repair, explicitly mention that missing-worker additions must only manually write `B:D`, and that `AK:AO` / `AU:AX` are arrayformula-owned.
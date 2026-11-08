# Destination roster vs request-list (`申請日期-當月統計`) sync

Andy 2026-09-23: before AP:AT / preflight / solve, compare **every named row on the target-month schedule tabs** (`115年M月-日` / `-夜` / `-幹部`) with **names on the request/stats list** (`申請日期-當月統計` column B). A destination name that is missing from the request list must be **added** to that list so the solver cannot skip them.

## What “request list” means

`申請日期-當月統計` columns `B:D` (class, exact dest name, previous consecutive work days). Do **not** invent a Google Forms / `原資料` rest application for the added worker.

## Required step (every monthly run)

1. Collect dest names with a stable employee ID and a real 班別 (`日`/`夜` or class `作業員-日` / `作業員-夜` / `幹部-日` / `幹部-夜`). Skip blank name rows and visual spacer rows.
2. Collect source `B` names (and IDs from spill) for the same year/month.
3. Dest-only employed names → **add** a new empty source row `B:D` only:
   - `B` = dest class (`作業員-日` / `作業員-夜` / `幹部-日` / `幹部-夜`). Visual-only `幹部` (Noel / 黃俊中 style) is **not** auto-promoted into a solver group.
   - `C` = exact destination name string.
   - `D` = verified previous consecutive work days (derive from previous-month same-shift tail; dest `Last Days Worked` is not trusted after a shift switch).
4. Read back `B:D` and formula spill. Do not write `E:AI`, `AK:AO`, `AU:AX`.
5. Source-only names still need an include/exclude decision (do not delete).
6. After adds, continue AP:AT / preflight / solve. Do not treat dest-only employed operators as a stop.

2026-10 miss: 達迎 was dest day row 27 / `F00110` and absent from source, so the day solve skipped him.

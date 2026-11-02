# Pre-print `未` → `特` finalization

Use this reference for monthly worker-scheduling runs after the 104 HR MAX import/export has been accepted and before the schedule is printed or signed.

## Trigger

Andy says 104 accepted the schedule / Import File output is accepted, and the schedule is ready for the paper/signature workflow.

## Required sequence

1. 104 HR MAX import/export accepted.
2. **Pre-print conversion:** convert remaining literal schedule markers `未` to `特` on the finalized target-month schedule tabs only.
3. Verify the conversion by readback.
4. Tell Anna/HR the schedule can be printed and signed.
5. Only after the schedule is accepted/announced/ready to print, run request closeout in `原資料!AD`.

Do not mark requests processed or tell people to print/sign before the `未` → `特` conversion has been done.

## Scope rules

For a target month such as `2026-07`, scope the conversion only to the final schedule tabs for that month, for example:

- `115年7月-日`
- `115年7月-夜`
- `115年7月-幹部`

Do **not** touch:

- `原資料`
- `申請日期-當月統計`
- prior-month carryover tabs such as `115年-6月` or `115年6月-*`
- future-month tabs such as `8月-*`
- archive/helper/lookup tabs

Only convert literal schedule cells whose displayed/value content is exactly `未`. Do not blindly replace substrings in notes, headers, formulas, or unrelated text such as `未結` or `特休未休完`.

Do not convert the HR MAX export/carryover tab. Its name is `115年-N月` (hyphen before the month, no `日` / `夜` / `幹部`). A prior "arranged" notice is not the print/sign sentence. Send the print/sign sentence only after the conversion readback.

## Locate the cells

1. Read each target tab's date grid as `FORMATTED_VALUE`, not `FORMULA`. Operators: day 1 is column `I`. 幹部: day 1 is column `G`. Do not reuse day-tab column letters on 幹部.
2. Keep a cell only when the displayed value is exactly `未`.
3. Confirm each candidate with a one-cell formatted read of the marker and the name on that row. A formula render of a wide row can drop leading cells, so a column letter counted from that dump points at an empty cell or the wrong day.
4. Write a JSON array of `{range, values}` under an approved tmp/artifacts/cache path. Use `RAW`. Quote sheet names that contain spaces or special characters.
5. Dry-run the batch, then live-write with `confirm_live_write` `RUN LIVE SHEETS BATCH UPDATE` and a readback range for every written A1. Do not call the conversion done until each readback is `特`.

## Closeout after conversion

After scheduling is finished and Andy confirms all rest requests for that month were granted, close every blank `AD` row that has any date in the scheduled month. A mixed-month row is in that set. Do not leave it blank. Listing it in the receipt is not a hold.

1. Dry-run `closeout_processed_requests` for the scheduled month.
2. If every candidate `AD` cell is blank, run the same action live with `RUN LIVE WORKER SCHEDULING SOURCE WRITE`. The value is `0 Processed`.
3. Read back every written range, including mixed-month rows. Each cell must be `0 Processed`.
4. Do not overwrite a nonblank AD status.
5. If Andy has not confirmed that all requests were granted, stop and list the candidates. Do not write.

Sheets omits trailing empty cells. A readback that drops a trailing blank is not a pass for a cell that should now be `0 Processed`.

## Preferred implementation

Use the safest available typed tool/MCP/AppSheet-safe wrapper for the worker-scheduling spreadsheet. The operation should produce a dry-run receipt and a live readback receipt with:

- spreadsheet/workbook ID or title
- target tabs
- per-tab candidate count
- per-tab changed cell ranges/A1s or grouped ranges
- post-write remaining `未` count
- proof that only target tabs were touched

If using Apps Script, prefer a narrow function that:

- opens the schedule workbook, not the request-source workbook;
- iterates the explicit target tab list;
- reads `getDataRange().getValues()` and `getFormulas()`;
- converts only cells where `value === '未'` and formula is blank;
- uses `RangeList(...).setValue('特')` or bounded grouped updates;
- calls `SpreadsheetApp.flush()`;
- reads the same ranges back and returns/logs a JSON receipt.

## Pitfalls from the 2026-07 run

- The Custom Actions menu visible on the request workbook contained draft-generation actions, not a visible pre-print `未` → `特` menu item. Do not assume the menu already covers this step.
- The actual schedule workbook may be separate from the rest-request source workbook. Confirm the script/config schedule workbook and target tabs before writing.
- The signed/printed schedule semantics differ from solver/export preview semantics: `未` can be intentional preview/export output, but the final paper schedule should show `特`.
- If Apps Script prompts for authorization, do not report the conversion as complete until the function actually runs and readback proves the changed cells. Authorization dialogs are not receipts.
- If this pre-print step is missed and request closeout already happened, still run/verify the conversion before printing/signing, then patch the playbook so future runs preserve the ordering.

## Employee-facing announcement wording

After verified conversion, it is safe to say, for example:

> 104 has accepted the schedule, the pre-print `未` → `特` conversion is complete, and the schedule can now be printed and signed.
>
> 104 已接受班表，列印前的 `未` → `特` 轉換也已完成，現在可以列印並簽名。

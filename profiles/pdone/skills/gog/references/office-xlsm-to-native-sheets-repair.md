# Office `.xlsm` → native Google Sheets repair pattern

Use when a user asks PD One to repair Google Drive spreadsheet files that originated as Excel macro workbooks and now have broken buttons/macros/internal links in Google Sheets.

## Key distinction

- A Drive file with MIME type `application/vnd.ms-excel.sheet.macroEnabled.12` is still an Office `.xlsm` object, even if Drive previews it in a Sheets-like UI.
- Google Sheets API / bound Apps Script behavior applies to native Sheets files with MIME type `application/vnd.google-apps.spreadsheet`.
- Excel VBA buttons/macros cannot run directly in Google Sheets. Rebuild the user workflow as native Sheets controls: custom menu, assigned drawing/button, checkbox/dropdown actions, or Apps Script functions.

## Diagnostic sequence

1. Resolve the exact Drive file IDs from the request/thread, not from similar filenames.
2. Read Drive metadata and record MIME type, title, parents, permissions/ownership if needed, and whether each file is native Sheets vs Office `.xlsm`.
3. If the source is `.xlsm`, download/export the binary workbook and inspect it locally:
   - sheet names and hidden/very hidden sheets;
   - overview/control sheets;
   - hyperlinks and formulas, especially internal links like `#'Sheet Name'!A1`;
   - macros/VBA presence if available (`keep_vba=True` with openpyxl can preserve evidence but not execute/translate VBA).
4. Build a link inventory. Flag links whose targets are missing, blank, or resolve to broken placeholders such as `null!A1`; do not promise a complete repair for those without a target decision.
5. Decide the repair target before writing:
   - preferred: create native Google Sheets copies of each workbook and rebuild controls/scripts there;
   - alternative: modify an existing production native Sheet only after explicit admin confirmation that it is the intended target.
6. For native repair copies, recreate supported behavior with Apps Script and native links, then verify using Sheets metadata/readback rather than visual preview only.

## Common repair mapping

- Excel overview button that creates/copies a test-record sheet → Apps Script custom menu/button that copies a template sheet and names it from the selected overview row.
- Excel button that shows/hides test-record tabs → Apps Script menu items that show/hide sheets by naming pattern.
- R-column or other internal workbook links → native Google Sheets `HYPERLINK("#gid=...&range=A1", "...")` or rich-text links to the target sheet/range.
- Missing original link target → ask/admin-decide whether to create a blank target sheet, map to a different existing sheet, or leave flagged.

## Review-log handling

If this arises from a Mattermost `review_log` follow-up, keep the row open until the native repair is written and verified. A diagnostic-only pass should update row notes/sources/blockers with the MIME-type finding, link inventory caveats, and the explicit next decision needed; it should not mark the request closed.

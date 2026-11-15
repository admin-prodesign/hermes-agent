# GoogleTranslate Sheet Column Mismatch

Use when AppSheet users see errors like:

```text
Unable to fetch app definition.
There is a mismatch in the number of columns between the spreadsheet for GoogleTranslate and the table schema.
The table has 15 columns but the schema has 14 columns.
Please regenerate the table column structure.
```

## Incident signature

Observed in Pro-Design app `f2073120-8c2e-4930-b13c-105838c5e4c3` around May 2026. Activity logs showed repeated sync failures on local version `26.050608` with `AppDefinitionChanged=true` and the table name `GoogleTranslate`.

Current healthy shape:

- AppSheet schema attributes include `_RowNumber` plus 14 physical sheet columns.
- Physical Google Sheet columns are exactly `A:N`:
  `CreatedAt`, `Timestamp`, `SourceTable`, `SourceKeyColumn`, `SourceRowKey`, `SourceColumn`, `TargetColumn_en`, `TargetColumn_zh-tw`, `Status`, `GoogleTranslateID`, `OriginalText`, `Translated_en`, `Translated_zh-tw`, `PINYIN`.
- The Google Sheets grid `columnCount` should be 14 for the `GoogleTranslate` tab.

## Likely cause

This is usually not an AppSheet action writing a bad field. In the May 2026 review, all AppSheet `ADD_RECORD_TO GoogleTranslate` assignments targeted known schema columns.

The likely cause is Google Sheets grid expansion: if the tab is trimmed to exactly 14 columns, a human edit, paste wider than `A:N`, tab/right-arrow past the last column, insert-column action, or API/script write to `O:O` can silently create a blank 15th grid column. AppSheet counts that blank physical grid column and then refuses sync because its schema expects only 14 physical columns.

## Triage steps

1. Read the live AppSheet `/api/loadApp` raw definition for `GoogleTranslate_Schema`; count attributes and exclude `_RowNumber` when comparing with the sheet.
2. Read Google Sheets metadata for spreadsheet `1n4UtbJkXb_JfrrEt8eeBb_CCgGsPvsr3r7Zmkwbf7NU`, tab `GoogleTranslate`; check `gridProperties.columnCount`.
3. Read `GoogleTranslate!1:2` to verify the header range and current headers.
4. If investigating source, inspect AppSheet actions with `ActionSettings.ReferencedTable == "GoogleTranslate"` and verify every `ColumnToEdit` is a known physical column.
5. Correlate user-visible failures with AppSheet ActivityLog/exportlog rows containing the mismatch text, `localVersion`, `EventTimeStamp`, and `AppDefinitionChanged`.

## Fix / hardening

- Immediate fix: delete/trim any blank grid columns beyond `N` so the tab column count returns to 14. Then verify by reading sheet metadata back.
- Protect or hide the helper tab from manual editing where practical.
- Add a scheduled guard that checks `GoogleTranslate` grid width and trims it back to 14 if extra blank columns appear. For the generic Google Sheets guard pattern, see `google-workspace` → `references/sheets-grid-width-guards.md`.
- Do not "fix" by regenerating schema to include the blank column unless there is an intentional new field. Regenerating can normalize accidental grid damage into the app schema.

## Report wording

Lead with: "The app schema expects 14 physical sheet columns; the sheet temporarily had a 15th blank grid column. AppSheet counts blank grid columns, so sync failed." Then provide evidence and current status.
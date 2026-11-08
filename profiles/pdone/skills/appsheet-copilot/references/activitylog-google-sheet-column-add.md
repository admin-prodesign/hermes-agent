# ActivityLog physical column add on the Google Sheet source

Use when adding a user-facing physical column to `ActivityLog`, not when the table is confirmed `ProviderName=google_tables`.

## Identify the source first

Do not trust `SourcePath` text that says AppSheet Database. Read the live `DataSets[]` row for `ActivityLog`:

- `ProviderName=google` plus `Source=DocId=<spreadsheet id>` and `ProviderSpecificSchema` of type `XlsxPhysicalSchema` means a Google Sheet tab.
- `SourceQualifier` is the tab title. `SourceQualifierId` must match that tab's `sheetId`.
- `ProviderName=google_tables` is a real AppSheet Database table. Do not invent a schema-write API for that case; add the physical column in the Database editor, then resync before row writes.

## Add order

1. Append the new header on the matching sheet tab. Do not insert it between existing headers. If the tab is at its column grid limit, insert one column after the last header with inherit-from-before enabled, then write the header. Inherit-from-before false at the grid edge is rejected.
2. Fresh `/api/loadApp`. Clone a same-type physical attribute, give it a new `ComponentId`, and set only `Name`, `TypeAuxData.Show_If`, `TypeAuxData.Required_If`, `DisplayName`, and `Description`. Clear inherited `Valid_If`, `Default`, and expression caches (`ExprLookup`, `InternalQualifier.ExpressionLookup`).
3. Place that attribute in the same position as the new header. For an appended header, that is immediately after the previous last physical column. Do not place it beside a related field such as `Products`.
4. Before `/api/saveapp`, compare two lists and stop if they differ: sheet header row, left to right, versus schema attributes where `IsVirtual` is false and the name is not `_RowNumber`. This source binds columns by that order. A one-position insert makes `Category` read the `Sub-Category` sheet cells, so grouped views show Lookup keys such as `Incident_DefectRate` instead of the `Translation` label.
5. Category comparisons must use the Lookup key, not the English display name. A dropdown labeled Production Line Clearance can still key as `ActivityLog_ProductionLineClearance`.
6. `Show_If` and `Required_If` are independent. A column can be visible for two categories and required for only one.
7. Schema presence is not form visibility. Add the column name to every explicit `Presentation.Controls[].ViewDefinition.ColumnOrder` for the forms and details that must show it, and to the same list inside `Controls[].Settings` when that field is a JSON string. AppSheet rewrites `ViewDefinition.ColumnOrder` from `Settings` on save, so a view-only edit is dropped. Also add it to `TableSlices[].Columns` when that view's `TableOrFolderName` is a slice. Detail views that already contain `**all other columns**` still need the column on the underlying table or slice. A slice form keeps its own `ColumnOrder`. Appending the new name only to the table form leaves the slice form without the field. A hidden view whose `ShowIf` is FALSE still needs an explicit `ColumnOrder` in both places, or the first launch shows columns in sheet order.
8. Save with `validate=true`. Promote only when the reloaded app is `IsValid`, `IsRunnable`, and `IsDeployable`, with no new Severity 0/1 errors. Pre-existing Severity 2 `INFO_*` notes on unrelated views are not a block. Then follow `references/appsheet-stable-promotion-admin-profile.md`.
9. Read back the sheet header, the stable-version schema attribute, and the same physical-order equality check on the stable version. Do not claim the field is live from the save response alone.

## Pitfalls

- A Google Sheet tab at its column grid limit rejects a header write past the last column. Insert one column after the last header with inherit-from-before enabled, then write the header. Do not insert with inherit-from-before false at the grid edge.
- Cron or system Python will fail this flow with `No module named browser_cookie3` before any write. Re-exec into the appsheet-doc venv, or call that interpreter directly.
- Pre-existing Severity 2 `INFO_*` editor notes, such as image-column suggestions on unrelated views, are not a save or promotion block. Block on Severity 0/1 errors, invalid/runnable/deployable false, or a warning that names the new column.
- A new sheet header without a schema attribute, or a schema attribute without the header, will not become a usable field.
- Do not save a Google Sheet-backed column add when the non-virtual schema order and the sheet header order differ. That mismatch is the Enum-looking failure: group headers show Lookup keys because the named column is reading the next sheet column.
- Slice forms hide a column that is missing from that slice's `Columns` list even when the table `Show_If` is true.
- Promoting latest also publishes every unpublished editor version between the old stable version and the saved version. Say that in the receipt.
- When adding a second Google Sheet workbook as a new table, set that dataset `SchemaName` and `PriorSchemaName` to a new schema name before save. A cloned dataset that still says `SchemaName=Case_Schema` makes AppSheet retarget `Case_Schema.AutoSchemaFrom` and Case notification task `TableName` onto the new tab. Restore both before promotion. Enum base Ref still creates reverse-reference names in slices; hide those virtual columns and do not add user views if the table must stay invisible.
- For a narrative field that needs both languages, append `{Name}_en` then `{Name}_zh-tw` after the last physical column. Do not insert the pair beside the source column. Copy `Show_If` from `Case[Title_en]`: detail view or the matching `Current User[Language]`. Set `Required_If` to false. A new pair does not join the existing translation bot; say that the columns stay blank until a translation job names them.

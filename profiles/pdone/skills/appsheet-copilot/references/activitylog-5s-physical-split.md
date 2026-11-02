# ActivityLog 5S physical split audit and AppSheet Database editor notes

Use with `appsheet-copilot` when migrating Pro-Design `ActivityLog` 5S records into physical AppSheet Database tables, especially after a user asks to avoid copying never-used generic `ActivityLog` columns.

## Naming convention

Use `5S*` names, not spelled-out `FiveS*` names:

- `5S`
- `5S_Attachments`
- `5SRecordID`
- `5SAttachmentID`
- `5S_Attachments_Cached`

This came from explicit user correction during the ActivityLog split work.

## Audit method

1. Query current `ActivityLog` rows with `Category = "5S Action"` and blank parent.
2. Compute nonblank counts for each column.
3. Do **not** assume broad `ActivityLog_Attachments` Data API visibility; in this session attachment selectors returned `[]` while parent rows still showed attachment caches. Use parent `ActivityLog_Attachments_Cached` as a signal and inspect the attachment schema from definition.
4. Only create columns that current 5S rows use or that are required for migration/audit/processing.

Working bounded selector pattern observed:

```appsheet
TOP(
  ORDERBY(
    FILTER(
      ActivityLog,
      AND([Category] = "5S Action", ISBLANK([Parent ActivityLogID]))
    ),
    [Timestamp],
    TRUE
  ),
  200
)
```

Avoid unbounded `Find` over broad `ActivityLog`; it can hang/time out.

## Observed 5S parent column usage snapshot

Sample: 52 latest bounded parent rows where `Category = "5S Action"` and `Parent ActivityLogID` blank.

Strong keep / already useful for physical `5S` table:

```text
5SRecordID                 new physical key
ActivityLogID_Legacy       old ActivityLogID
RowID_Legacy               old AppSheet Database row id/audit
Timestamp
Timestamp - Shift
Timestamp - Month
Shift Date
Shift
BU
Created By
Category_Legacy            fixed/compat value: 5S Action
Description
Description_en
Description_zh-tw
Description_Translated
Thumbnail
5S_Attachments_Cached
Label
Label_en
Label_zh-tw
Flag_Processed
Has Performance Points
Performance Points         low frequency but needed if 5S points assignment remains
LastProcessedAt
Last Updated
Updater
Equipment                  optional but observed ~21%
Label_Helper1              optional equipment label helper
```

Columns observed unused in the 52-row sample; do not create initially unless a current 5S workflow explicitly requires them:

```text
ActivityLog Children
ActivityLog Status
ActivityLog_Children_Cached
ActivityLog_Session_Items_Cached
Destination
Duration
Employee
GeneratedShareLink
Latest Child ActivityLog
Mold Repair Order Number
Molds
Notification Employee
NotificationStatus
Parent ActivityLogID
ProcessingError
Products
RefDocs_Read_Check
Related ActivityLog_Session_Items
Related HR_Employees_PerformanceRecords
Relevant Reference Documents
Relevant Reference Documents (List)
Risk
Sample_Production_Date
Sample_Production_Shift
Sub-Category
Sub-Category 2
ThumbnailStatus
TranslationStatus
TroubleShootingActions_Translated
Troubleshooting Actions
TroubleshootingActions_en
TroubleshootingActions_zh-tw
```

## Recommended lean `5S_Attachments` columns

Start with:

```text
5SAttachmentID
5SRecordID
ActivityLogAttachmentID_Legacy
ActivityLogID_Legacy
Timestamp
CreatedBy
Images
Files
Attachment Category
Updater
Flag_Processed
Last Updated
```

Optional later, if existing thumbnail/translation/queue workflows are retained:

```text
Use_as_Thumbnail
Sort Order
Description
Description_en
Description_zh-tw
ThumbnailStatus
RetryCount
LastError
QueuedAt
Label
```

Legacy `ActivityLog_Attachments` schema fields observed in definition:

```text
ActivityLogAttachmentID, ActivityLog Type, CreatedBy, Images, Files,
Description, Attachment Category, ActivityLogID, Description_en,
Description_zh-tw, Instruction Photo, Instruction File, Sort Order,
Use_as_Thumbnail, Updater, Flag_Processed, TranslationStatus,
ThumbnailStatus, RetryCount, LastError, QueuedAt, Label
```

## AppSheet Database editor quirks

- AppSheet Database physical table/column creation may require browser/editor automation; the public Data API is for row actions, not documented physical table/column creation.
- The editor link shape is like:

```text
https://www.appsheet.com/dbs/database/<database_id>/table/<table_id>
```

- Adding a column can be done from the `Add column` button. Save each column and read back visible headers before continuing.
- Browser automation via DOM `button[aria-label*="Add a new column"]` worked better than raw accessibility clicks in one session.
- Type dropdown options include `Text`, `LongText`, `Number`, `Yes/No`, `EnumList`, etc.; manual click by visible option was more reliable than bulk scripted selection.
- `EnumList` columns may open a second configuration panel and require option/item setup before Save is enabled. For cached legacy ID lists, consider creating the physical DB column as `Text` first (e.g. `5S_Attachments_Cached`) and later handling/refining type inside the AppSheet app schema if needed.
- For AppSheet Database attachment-split columns, do not assume native AppSheet app types (`Image`, `File`, `DateTime`) are available in the DB editor dialog. The editor may show broad categories like `Attachments` / `Date and time`, but the reliable quick-save path for physical DB columns can be generic `Text`; use `Yes/No` only where the selector is clearly available (e.g. `Flag_Processed`). Refine semantic types later in the AppSheet app schema after the DB columns exist.
- When adding many columns through browser automation, add/save in small groups and stop at special type selectors. On timeout or selector failure, immediately read back visible headers (`document.body.innerText`) and continue only with missing columns; successful prior saves may already have committed.
- Treat tab/table focus as a hard precondition before adding columns. After switching from `5S` to `5S_Attachments` (or back), verify `document.title`, `location.href`, and the first visible header/key column before adding anything. If the wrong tab is active, attachment columns can be physically appended to the parent `5S` table and AppSheet Database will auto-suffix duplicates like `5SRecordID (1)`, `ActivityLogID_Legacy (1)`, `Timestamp (1)`, etc.
- For physical `5S` cleanup, attachment-only columns that must not exist on the parent table include `5SAttachmentID`, `ActivityLogAttachmentID_Legacy`, `CreatedBy`, `Images`, `Files`, `Attachment Category`, and any suffixed duplicates such as `5SRecordID (1)/(2)`, `ActivityLogID_Legacy (1)/(2)`, `Timestamp (1)/(2)`, `Updater (1)`, `Flag_Processed (1)`, `Last Updated (1)`, `Images (1)`, `Files (1)`, or `Attachment Category (1)`. The clean `5S_Attachments` table should have exactly the lean attachment columns listed above and no suffixed duplicates.
- For final verification, compare a required column list against visible header text and report `missing: []` only after readback from the live DB editor tab. Verify both tables separately: `5S` parent headers and `5S_Attachments` headers.
- If a script times out, do not assume failure. Re-read `document.body.innerText`/visible headers; many columns may have saved before the tool timeout.

## AppSheet app-definition add step

After the physical DB tables/columns exist, add them to the main app definition before any canary backfill or UX routing. For exact dataset/schema save patterns, use `references/appsheet-db-table-add-to-app-definition.md`.

For the `5S` / `5S_Attachments` split, verified sane app-schema semantics include:

- `5S[5SRecordID]` as key; a human-visible label such as `Description`.
- `5S_Attachments[5SAttachmentID]` as key and label.
- `5S_Attachments[5SRecordID]` as `Ref` to `5S[5SRecordID]` with `IsAPartOf = true`.
- Legacy pointers as refs where useful: `ActivityLogID_Legacy -> ActivityLog[ActivityLogID]`, `ActivityLogAttachmentID_Legacy -> ActivityLog_Attachments[ActivityLogAttachmentID]`.
- Employee/person selectors as `Enum` base `Ref` to `HR_Employees_CurrentlyEmployed_BasicInfo[PersonID]`.
- Equipment as `EnumList` base `Ref` to `ERP_Assets_Equipment_Dropdown[品       號]` when preserving current 5S equipment context.
- Cached child lists such as `5S_Attachments_Cached` as `EnumList` base `Ref` to `5S_Attachments[5SAttachmentID]`, shown/admin-scoped until the maintenance/backfill path is built.

Default canary safety posture:

```appsheet
OR(
  CONTEXT("Host") = "Server",
  IN("IT_Manager", Current User Settings[Appsheet Roles]),
  IN("IT_Admin", Current User Settings[Appsheet Roles]),
  IN("Super_Admin", Current User Settings[Appsheet Roles])
)
```

Use that for `Editable_If` across the new split tables and for `Show_If` on legacy/cache/system fields; use `Show_If = TRUE` only for normal user-facing review fields. Verify `IsValid=true`, `IsRunnable=true`, required columns missing `[]`, keys/labels, refs, and show/edit expression counts after saving.

## Adding the physical tables to the AppSheet app definition

After the AppSheet Database tables exist, the deployed app still needs explicit `AppData.DataSets[]` and `AppData.DataSchemas[]` entries. Use fresh `/api/loadApp/<app_id>` JSON as the source of truth and model new DB-backed datasets after an existing `google_tables` dataset such as `QueueState`, `ActivityLog_Attachments`, or `Maintenance_Session_Items_Attachments`:

```text
ProviderName/DataSourceName: google_tables
Source: ID=base/<database_id>/tables/<frame_id>
SourcePath: ActivityLog Database
SourceQualifier: 5S or 5S_Attachments
SchemaName/PriorSchemaName: <table>_Schema
ServerCachingInterval: FIVE_MINUTE
```

For the current ActivityLog split database, the observed frame IDs were:

```text
5S             -> cy1ZWF2CIq4GA23JLyIKNb
5S_Attachments -> jwDb7P_QeJ4IQhkZz5yea6
```

Set schema semantics deliberately rather than accepting raw DB text types:

- `5S[5SRecordID]` key; label should be human-readable (`Description` worked for the initial schema).
- `5S_Attachments[5SAttachmentID]` key and label.
- `5S_Attachments[5SRecordID]` should be `Ref` to `5S[5SRecordID]` with `IsAPartOf=true` so attachment inline/ref behavior can work.
- Legacy IDs can be `Ref` for admin/debug use:
  - `ActivityLogID_Legacy` -> `ActivityLog[ActivityLogID]`
  - `ActivityLogAttachmentID_Legacy` -> `ActivityLog_Attachments[ActivityLogAttachmentID]`
- Person fields such as `Created By`, `CreatedBy`, `Updater` should be `Enum` base `Ref` to `HR_Employees_CurrentlyEmployed_BasicInfo[PersonID]` when they are picker-like fields.
- `Equipment` should be `EnumList` base `Ref` to the same equipment target used by the ActivityLog 5S flow (`ERP_Assets_Equipment_Dropdown[品       號]`).
- `Images`, `Thumbnail`, `Files`, `Timestamp`, and `Yes/No` columns need type-specific `TypeAuxData` shapes copied from known valid columns of the same type. Do not use plain text qualifiers after changing `Type` to `Image`, `File`, `DateTime`, or `Yes/No`.

Useful default safety expressions for canary-stage physical tables:

```appsheet
Show_If for normal user-facing fields: =TRUE
Show_If for legacy/cache/system fields: admin/server only
Editable_If for all fields during canary: OR(
  CONTEXT("Host") = "Server",
  IN("IT_Manager", Current User Settings[Appsheet Roles]),
  IN("IT_Admin", Current User Settings[Appsheet Roles]),
  IN("Super_Admin", Current User Settings[Appsheet Roles])
)
```

After saving, verify via fresh `/api/loadApp`:

```text
IsValid == true
IsRunnable == true
DataSets include 5S and 5S_Attachments
DataSchemas include 5S_Schema and 5S_Attachments_Schema
missing required columns == []
key/label columns are as intended
Ref / Enum base Ref qualifiers point to the right target tables and key columns
```

## UX/view rollout notes for physical 5S tables

AppSheet UX views live under `Presentation.Controls[]`; matching menu/sidebar entries live under `Presentation.MenuEntries[]`. They are not under `Presentation.Views` in the current raw JSON.

For physical `5S` rollout, clone existing ActivityLog 5S view patterns and retarget them carefully:

- Use `ActivityLog_5S`, `ActivityLog_5S_Detail`, and `ActivityLog_5S_Form` as the closest parent view/detail/form templates.
- Use `ActivityLog_Attachments_Inline`, `ActivityLog_Attachments_Detail`, and `ActivityLog_Attachments_Form` for `5S_Attachments` inline/detail/form templates.
- Retarget `TableOrFolderName` to `5S` / `5S_Attachments`.
- Replace or remove legacy-only columns in settings:
  - `Category` -> `Category_Legacy` where still needed.
  - `ActivityLogID` -> `ActivityLogID_Legacy`.
  - `ActivityLogAttachmentID` -> `ActivityLogAttachmentID_Legacy`.
  - `ActivityLog_Attachments_Cached` -> `5S_Attachments_Cached`.
  - Drop columns not present on the physical split (`Sub-Category`, `ActivityLog Type`, `Instruction Photo`, `Instruction File`, `Sort Order`, `Videos`, etc.).
- Remove ActivityLog-specific action names from new `ActionBarEntries` / form saved events unless equivalent 5S-specific actions already exist. Use `**auto**` for initial form save events.
- Avoid naming a new main UX control exactly the same as the table if the editor appears to treat it ambiguously. Use a distinct control name such as `5S_All` or `5S_Deck`, with `TableOrFolderName="5S"` and display name `="5S"`.
- If a large `/api/saveapp` request times out or returns `409 Conflict`, do not keep blindly reposting the same stale payload. Perform a fresh `/api/loadApp` readback first. If AppSheet returned an `App` payload with the 409, rebase the small intended view/version mutation onto that payload or the fresh live payload, then save once.

Versioning note: for Pro-Design AppSheet major physical splits, follow the established `YY.MMDD00` convention (for example, `26.061800` for 2026-06-18), not semantic bumps such as `27.000001`. Before any `/api/saveapp` or editor save, verify the existing versioning pattern and compute the intended major marker from the current date. AppSheet version numbers are monotonic; a mistaken higher major cannot be self-service reverted by restoring an older version. Read back `Version`, `StableVersion`, `IsValid`, and `IsRunnable`. Do not promote stable unless separately approved.

## Verification checklist after DB-column edits

- Read back visible headers for `5S` and `5S_Attachments`.
- Refresh/sync the deployed AppSheet definition after the physical tables are added to the app.
- Verify new tables appear in `/api/loadApp` with expected source IDs and schemas.
- Verify any cloned UX controls/menu entries under `Presentation.Controls[]` and `Presentation.MenuEntries[]` are valid and reference existing columns/actions only.
- Keep the tables hidden/admin-only until canary backfill passes.
- Do not route live 5S forms/views until a small canary migration and analyzer window prove no regressions.

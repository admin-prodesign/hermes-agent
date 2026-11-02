# ActivityLog 5S table split column audit

Use this when splitting Pro-Design `ActivityLog` category data into physical category-specific AppSheet Database tables, especially the first `5S Action` / `FiveSRecords` migration.

## Core lesson

Do not clone the full 65-column `ActivityLog` schema into a category table. Audit real category rows first and create only columns that are actually used by that workflow. For 5S, the live category value is:

```appsheet
"5S Action"
```

not plain `5S`.

## Read-only audit pattern

1. Pull bounded parent rows, not the whole table. Broad `Find` calls can hang or return `[]` depending on security context.

```appsheet
TOP(
  ORDERBY(
    FILTER(
      ActivityLog,
      AND(
        [Category] = "5S Action",
        ISBLANK([Parent ActivityLogID])
      )
    ),
    [Timestamp],
    TRUE
  ),
  200
)
```

2. Prefer the normal deployed app API context first. In this session, `RunAsUserEmail=admin@prodesign-group.com` timed out for the bounded 5S selector, while the no-RunAs API context returned real rows after ~46–53s. Treat this as an API-context selection pattern, not as a general tool failure.
3. Compute per-column nonblank counts and samples. Classify columns as `KEEP`, `OPTIONAL`, `OMIT`, or `REVIEW`.
4. Pull attachments separately if possible, but do not block the parent audit if `ActivityLog_Attachments` returns `[]`. For 5S, parent rows can still prove attachment usage through `ActivityLog_Attachments_Cached` / `Related ActivityLog_Attachments`.
5. If a newly created AppSheet Database/table is not yet in `loadApp`, you cannot inspect its columns from the app definition. Use browser/editor inspection or ask for/export the current table schema before adding columns to avoid duplicates.

## 5S column usage result from a representative sample

Latest bounded 5S parent pull returned 52 rows. `ActivityLog_Attachments` rows were not visible through the current API context, but 51/52 parent rows had `ActivityLog_Attachments_Cached` nonblank, so a separate `FiveS_Attachments` table remains recommended.

### Strong keep for `FiveSRecords`

Use cleaner new-table names where practical, but preserve legacy back-links for migration/audit.

| Existing ActivityLog column | Usage | Suggested new column |
|---|---:|---|
| `ActivityLogID` | 52/52 | `ActivityLogID_Legacy`; create new key `FiveSRecordID` |
| `Row ID` | 52/52 | `RowID_Legacy` optional audit field |
| `Timestamp` | 52/52 | `Timestamp` |
| `Timestamp - Shift` | 52/52 | `TimestampShift` |
| `Timestamp - Month` | 52/52 | `TimestampMonth` |
| `Shift Date` | 52/52 | `ShiftDate` |
| `Shift` | 52/52 | `Shift` |
| `BU` | 52/52 | `BU` |
| `Created By` | 52/52 | `CreatedBy` |
| `Category` | 52/52 | optional fixed compatibility `Category_Legacy = "5S Action"` |
| `Description` | 44/52 | `Description` |
| `Description_Translated` | 44/52 | `Description_Translated` |
| `Description_en` | 40/52 | `Description_en` |
| `Description_zh-tw` | 40/52 | `Description_zh_tw` |
| `Thumbnail` | 43/52 | `Thumbnail` |
| `ActivityLog_Attachments_Cached` | 51/52 | `FiveS_Attachments_Cached` |
| `Label`, `Label_en`, `Label_zh-tw` | 52/52 | physical cached labels recommended |
| `Flag_Processed` | 52/52 | keep if translation/processing workflow remains |
| `Has Performance Points` | 52/52 | `HasPerformancePoints` |
| `LastProcessedAt` | 52/52 | `LastProcessedAt` |
| `Last Updated` | 52/52 | `LastUpdated` |
| `Updater` | 52/52 | keep only if current workflows need it; values may be mixed |

### Optional / verify before creating

| Column | Usage | Note |
|---|---:|---|
| `Created By Photo` | 52/52 | May be expensive; derive from `CreatedBy` in detail view if possible |
| `LinkToRecord` | 52/52 | Regenerate for new table; do not migrate old deep links as-is |
| `Equipment` | 11/52 | Include only if 5S still tags equipment |
| `Label_Helper1` | 11/52 | Likely equipment label helper; derive or omit if possible |
| `Performance Points` | 3/52 | Include if 5S points assignment/reporting remains |
| `GeneratedShareLink - Timestamp` | 2/52 | Usually defer |
| `Notification Group` | 2/52 | Usually defer unless notification workflow remains |

### Omit initially for 5S

These were 0/52 in the sample and should not be created unless a later requirement proves they are needed:

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

## Recommended `FiveS_Attachments` minimal columns

Because 5S parent rows heavily use attachment caches, split attachments too when the goal is reducing `ActivityLog_Attachments` contention:

```text
FiveSAttachmentID          Text key
FiveSRecordID              Ref/Text to FiveSRecords
ActivityLogAttachmentID_Legacy Text
ActivityLogID_Legacy       Text
File or Image              File/Image
UploadedAt                 DateTime
UploadedBy                 Ref/Text
AttachmentType             Enum/Text optional
ProcessingStatus           Text/Enum optional
ProcessingError            LongText optional
LastUpdated                DateTime
```

Avoid thumbnail-worker/status columns unless the new design intentionally preserves the old thumbnail queue pattern.

## Write-safety

Creating AppSheet Database columns/tables is a source-system write. Before editing columns, present the audited list and get explicit approval for exact column names/types. If the table was manually created by the user, inspect or obtain the current schema first to avoid duplicate columns.

# Facilities Finance Acceptance Form migration

Use this reference when migrating the legacy Google Forms/Sheets Facilities `驗收單給財務` / acceptance form into AppSheet, or when building ISO/Finance forms from `Case` + `Case_Updates`.

## Context verified in session

Legacy workbook/tab:

- Spreadsheet: `ARCHIVED 良器-機修廠務-廠務-維修單 Facilities Repair Order`
- Form tab: `驗收單給財務-單單` (`55 x 20` grid)
- Old implementation pulls a final completed row from `原資料` and uses named ranges for photos:
  - `Named_驗收單_照片_申請`
  - `Named_驗收單_照片_維修`
  - `Named_驗收單_照片_驗收`
  - `Named_驗收單_照片_主管`

Current AppSheet structures involved:

- `Case`
- `Case_Updates`
- `Case_Attachments`
- `Case_Updates_Attachments`

Existing generic Case email report pattern:

- Action: `Case_EmailReport`
- Sets `Case[ExportTrigger] = TRUE`
- Event: `Case - Export Trigger`
- Process: `Process for Case_EmailReport`
- Task: `Export Case Task - 1`
- Then resets `[ExportTrigger]`
- The existing body already loops through `[Related Case_Updates]`, `[Related Case_Updates_Attachments]`, `[Related Case_Attachments]`, and sub-cases.

## Recommended design

Do **not** reuse the existing `ExportTrigger`; it is already the generic Case Report trigger. Prefer the class-level/universal request-column pattern when the `Case` table already has an automation request field:

```text
Case[AutomationRequest]
```

This avoids adding one boolean column per export/action. Use token values such as `CaseReport` and `FacilitiesFinanceAcceptanceForm`, and make every event detect a transition into its own token.

Suggested action:

```text
Case_Request_FacilitiesFinanceAcceptanceForm
```

Action type: set column values in this row.

```appsheet
[AutomationRequest] = "FacilitiesFinanceAcceptanceForm"
```

If no universal request column exists yet, create one text/enum column instead of adding a dedicated boolean trigger unless the app’s existing automation style requires booleans.

Suggested display name:

```appsheet
SWITCH(
  ANY(Current User[Language]),
  "zh-tw", "產生驗收單給財務",
  "Generate Finance Acceptance Form"
)
```

Suggested show condition:

```appsheet
AND(
  [Type] = "Facilities Repair",
  [Status] = "Completed",
  ISBLANK([Parent Case ID]),
  ISBLANK([AutomationRequest]),
  ISNOTBLANK(
    INTERSECT(
      SPLIT(Current User Settings[Appsheet Roles], ","),
      LIST("Case_Manager", "Super_Admin", "Team_Facilities")
    )
  )
)
```

Adjust the role names to the app’s actual role tokens after definition readback. Include `ISBLANK([AutomationRequest])` so users do not overwrite a pending request token.

Suggested automation event:

```text
Case - Facilities Finance Acceptance Request
```

Event type: data change / updates only on `Case`.

```appsheet
AND(
  [_THISROW_BEFORE].[AutomationRequest] <> [_THISROW_AFTER].[AutomationRequest],
  [AutomationRequest] = "FacilitiesFinanceAcceptanceForm"
)
```

Use `Ignore security filters = TRUE` if the server-side template must reliably include all related updates and attachments, matching the existing Case email report pattern.

Suggested process:

1. Send/generate the Finance acceptance form attachment.
2. Reset `[AutomationRequest]` to blank, e.g. `[AutomationRequest] = ""`.

## Template approach

For preserving the ISO layout, use the Google Sheets file as the design source, but **do not wire a native Google Sheets file directly as an AppSheet email attachment template**. AppSheet runtime can fail before evaluating formulas with: `Template Type: 'Attachment' could not be read due to FileMimeType 'application/vnd.google-apps.spreadsheet' is unexpected.` Export/convert the sheet to a real `.xlsx` file for an XLSX attachment template, or use a Google Docs template for PDF.

Current design source for this migration is Google Sheet `Facilities Finance Acceptance Form - AppSheet Template`, file id `133DeO7PE704jF0tnU75qGiHcARxCFU_2oqVCxxaUvPI`. The template cells should contain literal AppSheet tags like `<<[CaseID]>>`, `<<Start: ...>>`, and `<<INDEX(SELECT(...), n)>>`; do not leave legacy `#REF!` formulas or named-range formulas from the Google Forms workbook.

If AppSheet image rendering or layout fidelity is poor, switch to a Google Docs template laid out as fixed tables and export as PDF.

Prefer PDF for Finance unless they explicitly need XLSX. Runtime proof on 2026-06-09 showed that AppSheet can generate an XLSX byte stream from an XLSX attachment template even when `AttachmentContentType=PDF`, producing a mislabeled/broken `.pdf` that `file` identifies as `Microsoft Excel 2007+`. If using the XLSX template path, set `AttachmentContentType=XLSX` and use an `.xlsx` attachment name. For a true PDF, rebuild the template as a Google Docs/table-style PDF template rather than relying on XLSX-to-PDF conversion.

When saving through AppSheet editor APIs, adding a new Google Docs/Sheets attachment template by setting `BodyTemplate` to a new DocId can fail with a permissions/source-registration error such as `403 Insufficient permissions to add source`. Treat this as an AppSheet source authorization problem, not as proof the template is invalid. Safe fallback:

1. Keep the task valid by putting a functional draft template in the task `Body` field and leaving `BodyTemplate` blank.
2. Save/read back the action/event/process/task wiring and confirm the app remains valid/runnable.
3. Manually attach/authorize the Drive template in the AppSheet editor, or use an already-authorized template/source, then switch to `BodyTemplate=DocId=...` and verify again.

Suggested attachment name:

```appsheet
CONCATENATE("Facilities_Acceptance_Form_", [CaseID], ".pdf")
```

## Field mapping

| Legacy field | AppSheet source |
|---|---|
| 維修單號 | `<<[CaseID]>>` |
| 申請日期 | `<<[Created On]>>` |
| 維修完成需求日期 | `<<[Deadline]>>` or `<<[Completion Date]>>`, confirm intended meaning |
| 申請者 | `<<[Created By].[Name_ZH_EN]>>` |
| 驗收者 | latest relevant `Case_Updates[Created By]`; add structured field if audit-critical |
| 主管 | latest completed/manager update creator; add structured field if audit-critical |
| 維修單種類 | `<<[Sub-Type]>>` or `<<[Type]>>` |
| 維修地點 | not obvious in current `Case`; add field or derive from equipment/location if needed |
| 機台號碼 | `<<[Equipment]>>` |
| 簡單說明 | `<<[Title]>>` / `<<[Description]>>` |
| 備註/細節 | `<<[Description]>>` plus update history |
| 外包廠 Vendors | not obvious as a structured field; add field if needed |
| 維修歷史 | loop over `[Related Case_Updates]` |
| 驗收歷史 | filtered loop over `[Related Case_Updates]` |
| 主管驗收歷史 | filtered loop over `[Related Case_Updates]` |
| 申請照片 | `Case_Attachments[Images]` |
| 維修/驗收/主管照片 | `Case_Updates_Attachments[Images]`, grouped by update type/status/category |

## Template snippets

All updates:

```appsheet
<<Start: ORDERBY([Related Case_Updates], [Timestamp], FALSE)>>
<<[Timestamp]>> | <<[Created By].[Name_ZH_EN]>> | <<[Update Type]>> | <<[New Status]>>
<<[Update Summary]>>
<<[Update Description]>>

<<Start:[Related Case_Updates_Attachments]>>
Photo/File: <<[Images]>><<[Files]>>
Description: <<[Description]>>
<<End>>

<<End>>
```

Request-level photos:

```appsheet
<<Start: SELECT(
  Case_Attachments[CaseAttachmentID],
  AND(
    [CaseID] = [_THISROW].[CaseID],
    ISNOTBLANK([Images])
  )
)>>
<<[Images]>>
<<End>>
```

All update photos for the case:

```appsheet
<<Start: SELECT(
  Case_Updates_Attachments[CaseUpdateAttachmentID],
  AND(
    IN([CaseUpdateID], [_THISROW].[Related Case_Updates]),
    ISNOTBLANK([Images])
  )
)>>
<<[Images]>>
<<[Description]>>
<<End>>
```

Fixed 7-photo grid cell pattern:

```appsheet
<<INDEX(
  SELECT(
    Case_Updates_Attachments[Images],
    AND(
      IN([CaseUpdateID], [_THISROW].[Related Case_Updates]),
      ISNOTBLANK([Images])
    )
  ),
  1
)>>
```

Repeat with indices `2`, `3`, etc. Use guarded logic if blank cells should show `N/A` rather than fail.

## Audit-critical schema gap

The current `Case` / `Case_Updates` schema may not have structured equivalents for old form fields such as:

- vendor / 外包廠
- repair cost
- repairer name
- reviewer OK/NG
- manager OK/NG
- inspection checkpoints: function, safety, electrical, labels, SOP, achieved purpose
- explicit “needs completion form for Finance” flag

If Finance/ISO requires auditable consistency, add structured fields to `Case_Updates` or create a dedicated child table such as `Case_Facilities_Acceptance` before relying on free-text update history.

## Action visibility and runtime triage

When the Finance acceptance button appears/disappears after wiring changes, do not assume the action was deleted or the role expression is wrong. Separate five layers and prove each one:

1. **Definition layer**: read back the deployed/stable raw app definition and verify the action still exists by name, is on table `Case`, has `Display_Prominently`, is valid, and its `OnlyIf`/show condition still matches the intended completed Facilities parent cases.
2. **User/account layer**: if Andy asks to check a specific AppSheet login such as `pro.design.group.tw@gmail.com`, read `HR_Employees_AppSheet_Settings` / `HR_E_A_S` by exact `Appsheet Email` and inspect `PersonID`, `Language`, `Appsheet Roles`, `Combined Appsheet Roles`, `_Is_Case_User`, and `Updater`. Prefer AppSheet Data API selectors shaped as `FILTER("HR_Employees_AppSheet_Settings", [Appsheet Email]="...")`; a bare selector like `[Appsheet Email]="..."` can return zero rows in this table even when the row exists. For the Finance acceptance action, `Case_Manager` or `Super_Admin` in `Appsheet Roles` should satisfy the current role gate. Team/group tokens such as `Team_Facilities` usually live in `Appsheet Notification Group` / `Combined Appsheet Roles`, not necessarily in `Appsheet Roles`; if team membership is intended to grant visibility, check `Combined Appsheet Roles` explicitly or use direct `IN()` checks instead of assuming comma-split roles contain team tokens.
3. **Row eligibility layer**: probe the same `Case` row through the AppSheet API/server path and verify the row values used by the show condition, especially `[Type]`, `[Status]`, `[Parent Case ID]`, `[AutomationRequest]`, and any user-role/current-user expressions.
4. **Deployment/cache layer**: compare `Version`, `StableVersion`, and the AppTemplateVersion shown in automation logs. If the action fired under an earlier version but the client no longer shows it, ask for a hard AppSheet app reload/full sync and confirm the device/browser is on the stable version before editing definitions.
5. **View/slice layer**: if the action is still eligible server-side but hidden client-side, inspect the specific view/slice/ref view the user is using; prominent actions can be suppressed or surfaced differently depending on view/slice context even when the table action exists.

Runtime log proof is useful but not sufficient for visibility: a successful `Process for Case_FacilitiesFinanceAcceptanceForm` entry proves the request fired at that time; it does not prove the current client is showing the action after version/cache/view changes. Conversely, unrelated queue/heartbeat/thumbnail failures near the same timestamp should not be blamed for button visibility unless they touch the same action/event or leave `[AutomationRequest]` stuck.

### Stuck `AutomationRequest` no-email pitfall

If the Finance Acceptance button is visible but no email arrives, first read back the target `Case` row before editing automation. The event only fires on a transition into the token:

```appsheet
AND(
  [_THISROW_BEFORE].[AutomationRequest] <> [_THISROW_AFTER].[AutomationRequest],
  [AutomationRequest] = "FacilitiesFinanceAcceptanceForm"
)
```

If the row already has `AutomationRequest = "FacilitiesFinanceAcceptanceForm"`, pressing an action that sets the same value again will not create a matching change event, so no email/export run appears. This usually means the reset action did not run after a prior failure/test or the row was manually/API-seeded. Fix path:

1. Read back the row (`CaseID`, `Type`, `Status`, `Parent Case ID`, `AutomationRequest`) and recent exportlog entries for the exact process/task.
2. If the token is stuck, clear only that row's `AutomationRequest` after approval/dry-run.
3. Harden the action `OnlyIf`/condition to include `ISBLANK([AutomationRequest])` so the button does not invite a no-op re-click while work is pending/stuck.
4. Keep `ISBLANK([Parent Case ID])` if only parent Facilities cases should export.
5. For team/facilities visibility, verify whether role tokens live in `Appsheet Roles` or `Combined Appsheet Roles` / notification groups; do not assume `Team_Facilities` is present in the comma-split roles field.

## ProcessingQueue durable export pattern

For Finance Acceptance exports that must not be lost after a one-shot bot/task failure, prefer `ProcessingQueue` as the durable source of truth instead of using `Case[AutomationRequest] = "FacilitiesFinanceAcceptanceForm"` as both command and pending state.

Implemented live on 2026-06-22 in app version `27.000063`:

- Visible action `Case_Request_FacilitiesFinanceAcceptanceForm` is an `ADD_RECORD_TO` action that creates a `ProcessingQueue` row with:
  - `JobType = "facilities_finance_acceptance_export"`
  - `SourceTable = "Case"`
  - `SourceKeyColumn = "CaseID"`
  - `SourceRowKey = [CaseID]`
  - `ScopedJobKey = CONCATENATE("facilities_finance_acceptance_export|", [CaseID])`
  - `Status = "Queued"`, `WorkerLane = "case"`, `NextAttemptAt = UTCNOW()`, `RetryCount = 0`.
- Immediate row-level bot `ProcessingQueue - Facilities Finance Acceptance Ready` processes due `Queued`/`Retry` rows.
- Queue worker actions set the row `Running`, clear then write the active `QueueID` into `Case[AutomationRequest]`, and the existing Case-context email process sends the XLSX attachment.
- `Process for Case_FacilitiesFinanceAcceptanceForm` now marks the queue row `Done` after the email task succeeds and before resetting `Case[AutomationRequest]`.
- `HeartBeat_PQ_FacilitiesFinanceAcceptance` is the fallback/reaper: stale `Running` rows older than 15 minutes become `Retry` with a 5-minute delay; after 5 retries they become `Dead`.

Important retry detail: before writing the active `QueueID` into `Case[AutomationRequest]`, the worker clears that field first. This ensures a retry with the same `QueueID` still creates a value transition and re-fires the Case event. Without the clear-then-set step, a stuck `Running` queue row could retry but fail to trigger because the Case token did not change.

### Queue-worker recipient pitfall

When a previously interactive export button is moved behind `ProcessingQueue`, do not keep email recipients based only on `Current User[...]`. In AppSheet automation/queue-worker context, `Current User[Company Email]` can resolve blank even though it worked when the user pressed the original button directly. The symptom is a generated attachment plus task failure:

```text
No workflow email was sent because 'To', 'CC', 'BCC' are all empty
Email Attachment ByteLength > 0
Email Attachment MIMEType = application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

For queue-backed Finance Acceptance exports, carry an explicit recipient on the queue row and use a deterministic fallback. Recommended pattern:

1. On `Case_Request_FacilitiesFinanceAcceptanceForm`, store the intended recipient in `ProcessingQueue[SourceText_1]`, e.g. the interactive user's company email if available, otherwise the next responsible person's company email.
2. In `Facilities Finance Acceptance Form Task`, use a queue-aware recipient expression instead of only `ANY(Current User[Company Email])`:

```appsheet
IF(
  ISNOTBLANK(LOOKUP([AutomationRequest], "ProcessingQueue", "QueueID", "SourceText_1")),
  LIST(LOOKUP([AutomationRequest], "ProcessingQueue", "QueueID", "SourceText_1")),
  IF(
    ISNOTBLANK([Next Step Responsible Person].[Company Email]),
    LIST([Next Step Responsible Person].[Company Email]),
    IF(
      ISNOTBLANK([Created By].[Company Email]),
      LIST([Created By].[Company Email]),
      LIST("admin@prodesign-group.com")
    )
  )
)
```

If the email task fails before the process reaches the queue `Done` action, the row will remain `Running`/`Retry`; check exportlog task `Errors` before assuming the queue worker itself failed.

Verification receipts for the live migration are under:

```text
/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace/projects/AppSheet/exports/facilities-finance-pq-20260622/
```

## Verification steps

1. Sync/read the deployed AppSheet definition before schema-sensitive advice.
2. Verify current `Case_EmailReport` wiring before copying the pattern; if migrating it, move it from `[ExportTrigger]` to `[AutomationRequest] = "CaseReport"` and verify the old column is no longer used by the event/process.
3. Create/dry-run template in a copy first.
4. After `saveapp`, perform a fresh definition readback and verify all of the following by name: request action, automation event expression, bot, process step order, attachment task, reset action, `IsValid=true`, and `IsRunnable=true`.
5. For attachment templates, verify the exact Drive `DocId` in the definition points to a real `.xlsx` or supported template file, not a native Google Sheets file. A valid-looking task can still fail at runtime if the MIME type is `application/vnd.google-apps.spreadsheet`; a real XLSX should read back as `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
6. Check latest-vs-stable drift before saying users have the new button/template. If `Version` is ahead of `StableVersion` or `PercentOnLatestVersion=0`, the latest editor definition may be correct while deployed/stable users still run the old behavior. Compare the target task/action in a raw history snapshot whose `Version == StableVersion` before recommending promotion.
7. Test with one completed `Facilities Repair` parent case containing multiple updates and attachments only after the user approves a live export/write.
8. Verify generated attachment content, image rendering, reset of `[AutomationRequest]`, recipient/archive settings, and the actual attachment filename. Replace generic names such as `ChangeReport` with a case-specific expression such as `FacilitiesFinanceAcceptance_<<[CaseID]>>.pdf` / `.xlsx` once runtime rendering is proven.
9. Promote only after readback of the saved app definition and a real generated artifact receipt.

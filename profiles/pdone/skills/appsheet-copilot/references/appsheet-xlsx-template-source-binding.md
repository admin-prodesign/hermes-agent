# AppSheet XLSX attachment template duplication and source binding

Use when rebuilding or duplicating AppSheet scheduled email/report XLSX attachment templates, especially after table rename/schema regeneration.

## Key lesson

Duplicating a Google Drive XLSX file and editing the AppSheet task JSON are separate problems. A Drive copy can be valid and accessible, but `/api/saveapp` may still reject binding it as an `AttachmentTemplate` with:

```text
403 / Insufficient permissions to add source.
```

This can happen even for:
- a same-parent Drive API copy of the original template,
- a file owned by the same admin account,
- or a DocId that was previously used but whose binding was removed from the task.

Treat this as an AppSheet Drive-source authorization/add-source problem, not an XLSX expression problem.

## Do not damage the original

If the user asks to duplicate the automation/template, keep the original untouched. Do **not** overwrite the original template DocId as a workaround unless the user explicitly approves replacing the original. If an overwrite was done accidentally, restore the original from a Drive backup immediately and verify checksum/modified time.

## Safe duplication sequence

1. Inspect the original automation graph:
   - `Behavior.AppBots[]`
   - `Behavior.AppEvents[]`
   - `Behavior.AppProcesses[]`
   - `Behavior.Tasks[]`
2. Duplicate the Drive template first and patch the duplicated XLSX placeholders.
3. Save duplicate AppSheet task/bot/event/process objects without touching original objects.
4. Keep the duplicate bot/event disabled until the attachment template binding is accepted.
5. Try binding the duplicate task to the duplicate DocId in a separate save so failure does not block creation of the rest of the duplicate automation.
6. If binding returns `Insufficient permissions to add source`, stop reposting payloads. Use a source-authorized editor session/account to add the Drive source/template, then enable the duplicate automation.

## Stale-version save pitfall

Repeated `/api/saveapp validate=true` calls can create/advance editor versions. If a later save returns `409` saying the version already exists, reload `/api/loadApp` fresh and rebase the patch before retrying. Do not treat this as proof that the object shape is invalid.

## Reporting standard

Report separately:
- Drive duplicate/template patch receipt: DocId, parent folder, checksum or modified time.
- AppSheet definition receipt: saved version, stable version, `IsValid`, `IsRunnable`, exact duplicate object names.
- Binding status: attached vs blocked, with raw AppSheet error text.
- Whether the duplicate bot/event is enabled or intentionally disabled.

## Example object naming pattern

For duplicating a monthly 5S report without altering the original:

```text
Original bot:     ¬ActivityLog_5S_Email_MonthlyReport
Duplicate bot:    ¬ActivityLog_5S_Email_MonthlyReport_NewTable
Original event:   5S Points Email
Duplicate event:  5S Points Email - New 5S Table
Original process: Process for ¬ActivityLog_5S_Email_MonthlyReport
Duplicate process: Process for ¬ActivityLog_5S_Email_MonthlyReport_NewTable
Original task:    ActivityLog_5S_EmailXLSX
Duplicate task:   ActivityLog_5S_EmailXLSX_NewTable
```

Keep the duplicate disabled until the duplicate XLSX template is actually bound and validated.
# AppSheet API schema repair and validation pitfalls

Use with `appsheet-copilot` when repairing AppSheet app-definition errors after table rename, schema regeneration, or AppSheet Database physical-table changes.

## User/workflow preference

For AppSheet app-definition repairs, use the AppSheet editor API (`/api/loadApp`, `/api/saveapp`) rather than browser UI automation whenever possible. Browser interaction is acceptable for physical AppSheet Database editor work only when no reliable API path exists. If the user asks/corrects "use the API," stop browser-driven definition edits immediately.

## Required validation loop

Do not rely only on top-level `IsValid` / `IsRunnable` or generic invalid-object walks. Some editor-visible errors and warnings only appear in the `/api/saveapp` validation response.

Recommended loop:

1. `GET /api/loadApp/<appName>?version=&checkConsistency=true&useUpdatedWarningText=false`.
2. Patch the JSON in memory.
3. `POST /api/saveapp` with `validate=false` for the actual save when the app is large.
4. Reload fresh with `/api/loadApp`.
5. Run a validation pass: `POST /api/saveapp` with `validate=true` on the fresh app JSON and inspect `AppErrors.Errors[]`.
6. Filter validation messages by the user-reported table/view/task names, but do not ignore other severity-1 errors.

## Specific pitfalls from ActivityLog_5S rename/regeneration

### Explicit Yes/No in boolean expressions

AppSheet may reject a `Show_If` such as:

```appsheet
=OR([Has Performance Points], OR(...admin condition...))
```

with `subexpressions must be Yes/No conditions`, even when `[Has Performance Points]` is a Yes/No column. Use an explicit comparison:

```appsheet
=OR(
  [Has Performance Points] = TRUE,
  OR(
    CONTEXT("Host") = "Server",
    IN("IT_Manager", Current User Settings[Appsheet Roles]),
    IN("IT_Admin", Current User Settings[Appsheet Roles]),
    IN("Super_Admin", Current User Settings[Appsheet Roles])
  )
)
```

### Renamed physical AppSheet DB tables can leave stale view references

After renaming `5S` / `5S_Attachments` to `ActivityLog_5S` / `ActivityLog_5S_Attachments` and regenerating schema, cloned views may still point at generated/missing table names such as:

```text
ActivityLog_5S1
ActivityLog_5S1_MyTeam
```

Patch `Presentation.Controls[].TableOrFolderName` back to the real table (`ActivityLog_5S`) and repair matching menu/show expressions. Also search view `Settings` JSON for old nested columns such as `Related ActivityLog_Attachments` and replace with the regenerated current name, e.g. `Related ActivityLog_5S_Attachments`.

### XLSX attachment templates can become invalid after table rename/regeneration

A scheduled email task can remain `IsValid=true` in raw JSON while the editor reports the attachment template invalid. Inspect the task fields:

```text
Behavior.Tasks[].Name
Behavior.Tasks[].TableName
AttachmentContentType
AttachmentTemplate
AttachmentTemplateDataSourceName
UseDefaultContent
```

If the old template was built against the pre-rename schema, either rebuild/rebind the template against the new table or temporarily remove `AttachmentTemplate` to clear the validation error. Preserve the old DocId in the task `Comment` so the report can be rebuilt later.

For the ActivityLog 5S monthly report, the old removed template was:

```text
ActivityLog_5S_EmailXLSX
Previous AttachmentTemplate=DocId=1JXlIF4D1tNOGsQC-vNRYw4zkJad2GAdt
```

Important: re-adding an `AttachmentTemplate = "DocId=..."` through `/api/saveapp` can fail with `403 / Insufficient permissions to add source`, even for a same-folder Drive copy or a DocId that was previously used before the binding was removed. Treat this as an AppSheet Drive-source authorization problem, not an expression/schema problem. Do not keep reposting full payloads; use an editor/account path that can add/authorize sources, or keep the task unbound and report the blocker. For the full rebuild/backup/Drive-copy pattern and status-reporting standard, see `references/appsheet-xlsx-template-source-binding.md`.

### AppSheet Database `SourceQualifier` rename may be blocked

Changing `DataSet.SourceQualifier` for an already-associated AppSheet Database table can cause `/api/saveapp` to fail with:

```text
403 / Insufficient permissions to add source
```

If this happens, retry a schema-only patch that preserves `Source`, `SourcePath`, and `SourceQualifier`. Do not keep reposting the same full payload. If AppSheet still reports "schema out of sync" after schema-only repair, the editor's native regenerate/source-metadata path may be required.

### ProviderSpecificSchema may not clear DB schema mismatch

For `google_tables`, `DataSet.ProviderSpecificSchema` contains `ChangedByUserColumnComponentIds`. Adding app-level semantic overrides (`Ref`, `Enum`, `EnumList`, `Image`, `File`, etc.) to that list is worth trying, but it may not clear `ERROR_TABLE_SCHEMA_DOES_NOT_MATCH_PROVIDER` if the provider-side source metadata is stale after a physical table rename.

### HRS multi-row formula warning

If validation reports:

```text
Ignoring row 2 of table 'HRS_Data' because it contains MultiRow formulas in editable column '英文姓名'
```

an AppSheet schema patch that sets the column read-only may be normalized back by AppSheet. Treat this as likely requiring a backing Google Sheet/source fix for row 2 rather than an app-definition-only fix.

### Logo URL warning

For `WARNING_INACCESIBLE_IMAGE`, verify the URL with both unauthenticated and authenticated GET. If both return 404, the warning is real. Do not remove/replace the logo automatically unless the user approves the branding change or provides a replacement image/DocId.

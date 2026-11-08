# AppSheet Database table rename + schema regeneration repair notes

Use with `appsheet-copilot` when physical AppSheet Database tables are renamed in the editor and AppSheet schema regeneration breaks app-level metadata.

## Trigger symptoms

After renaming physical DB tables and regenerating schemas, AppSheet may show editor errors even when `/api/loadApp` reports top-level `IsValid=true`. Typical symptoms observed:

- `IsRunnable=false` but the explicit editor errors are column/task-specific.
- App-level column types revert to provider defaults such as `Text`.
- `Ref`, `Enum` base `Ref`, `EnumList` base `Ref`, `Image`, `File`, `DateTime`, `Yes/No`, labels, keys, `Show_If`, and `Editable_If` need to be restored.
- Generated reverse-ref/list columns may be auto-added/renamed (for example `Related ActivityLog_5S_Attachments`).
- A previously-valid XLSX/email attachment template becomes invalid because it was authored against the old table/schema shape.

## API-first rule

For AppSheet definition repairs, prefer the AppSheet editor API path over browser UI automation:

```text
GET  /api/loadApp/<appName>?version=&checkConsistency=true&useUpdatedWarningText=false
POST /api/saveapp
GET  /api/loadApp/<appName>?version=&checkConsistency=true&useUpdatedWarningText=false
```

Use the authenticated local AppSheet cookie profile/session when available. Browser/editor UI can be used for observation only when the API does not expose needed state, not as the default write path.

## Critical pitfall: source metadata vs schema metadata

When repairing schemas for an already-associated AppSheet Database source, **do not change** these `DataSet` fields unless intentionally re-adding/repointing a source with an account that has source-add permissions:

```text
Source
SourcePath
SourceQualifier
```

Changing only schemas/types can save successfully, while changing `SourceQualifier` from the original physical name to the renamed table name can make `/api/saveapp` fail with:

```text
Insufficient permissions to add source.
```

For renamed physical DB tables, it is acceptable for the app `DataSet.Name` to be the new logical table name while `SourceQualifier` still shows the original physical source qualifier, as long as `Source` points to the correct `ID=base/<base_id>/tables/<frame_id>`.

## Repair pattern

1. Load fresh app JSON through `/api/loadApp`.
2. Locate the two affected `DataSchemas[]` by their renamed schema names.
3. Restore semantic app types and type qualifiers:
   - parent key: `Text`, `IsKey=true`
   - child parent id: direct `Ref` to renamed parent table, `IsAPartOf=true`
   - employee selectors: `Enum` with `BaseType=Ref`
   - cached child list: `EnumList` with `BaseType=Ref` to the renamed child table
   - images/files/timestamps/booleans/numbers/long text: restore specific AppSheet types, not provider text defaults
4. Restore keys, labels, visibility, and editability.
5. Leave already-associated `DataSet.Source` / `SourceQualifier` untouched unless you are explicitly fixing the source and have source-add permission.
6. Save with `/api/saveapp`; read back with `/api/loadApp` and verify.

## Yes/No expressions inside OR()

When a `Show_If`/`Editable_If` uses a Yes/No column inside `OR()` or `AND()`, compare it explicitly if the editor reports invalid structure:

```appsheet
OR(
  [Has Performance Points] = TRUE,
  OR(
    CONTEXT("Host") = "Server",
    IN("IT_Manager", Current User Settings[Appsheet Roles]),
    IN("IT_Admin", Current User Settings[Appsheet Roles]),
    IN("Super_Admin", Current User Settings[Appsheet Roles])
  )
)
```

Avoid relying on bare `[YesNoColumn]` when AppSheet says subexpressions must be Yes/No conditions.

## Attachment template errors after rename/regeneration

If AppSheet reports that an email/report task attachment template is invalid after a table rename:

1. Inspect the task object in `Behavior.Tasks[]` (for example `ActivityLog_5S_EmailXLSX`).
2. Preserve the old `AttachmentTemplate` DocId in the task `Comment` or patch notes.
3. If you cannot immediately rebuild the template against the new schema, remove or null the invalid template binding so the app no longer points to a broken template.
4. Clearly report that the report attachment must be rebuilt/rebound before the scheduled report can send the intended XLSX.

Do not claim the report is fully restored if the invalid template was only detached.

## Verification checklist

After saving, read back and verify:

```text
save HTTP status == 200
Version advanced
StableVersion unchanged unless promotion was approved
Target DataSet exists
Target DataSchema exists
missing required columns == []
keys and labels are intended
Ref / Enum-of-Ref targets use renamed table names where appropriate
Show_If / Editable_If are syntactically valid
known editor-reported errors are specifically gone
```

If `IsRunnable=false` remains, walk invalid objects but distinguish unrelated pre-existing invalid automations from the table-rename/schema-regeneration errors being fixed.

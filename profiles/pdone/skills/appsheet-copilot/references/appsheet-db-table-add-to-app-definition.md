# AppSheet Database physical table add-to-app definition pattern

Use when physical tables already exist in the AppSheet Database editor and must be added to the main AppSheet app definition with column semantics, refs, display/edit rules, and readback verification.

## When this applies

- The DB editor URL is like `https://www.appsheet.com/dbs/database/<base_id>/table/<table_id>`.
- The physical AppSheet Database table exists and has columns, but `/api/loadApp/<app_id>` does not yet contain matching `AppData.DataSets[]` / `AppData.DataSchemas[]` entries.
- The task needs app-schema-level types such as `Ref`, `Enum` base `Ref`, `EnumList` base `Ref`, `Image`, `File`, key/label flags, `Show_If`, `Editable_If`, and `IsAPartOf`.

## Source IDs and dataset shape

Use the AppSheet Database Frames API from the authenticated editor/browser session to confirm physical table ids and columns:

```js
fetch('/v1/frames:listBaseFrames?key=<frontend-api-key>', {
  method: 'POST',
  credentials: 'include',
  headers: {'content-type':'application/json'},
  body: JSON.stringify({baseId: '<base_id>'})
})
```

The app definition `DataSet.Source` shape for AppSheet Database-backed tables is:

```text
ID=base/<base_id>/tables/<frame_id>
```

Use existing `google_tables` datasets as templates for fields like `AllowedUpdates`, `UpdateMode`, `DataAccessMode`, `ProviderSpecificSchema`, `ServerCachingInterval`, partition fields, and `Visibility`.

## Schema object pattern

Add one `DataSchemas[]` entry named `<TableName>_Schema` with:

```json
{
  "Name": "<TableName>_Schema",
  "AutoSchemaFrom": "<TableName>",
  "IsAutoCreated": true,
  "Attributes": [...]
}
```

Use existing compiled schema attributes as templates by type, then change only the semantic fields:

- `Name`
- `Type`
- `TypeFromProvider`
- `TypeAuxData`
- `IsKey` / `IsKeyPart`
- `IsLabel`
- `IsRequired`
- `IsHidden`
- `IsReadOnly`
- `DisplayName`
- `AppFormula` where intentionally needed
- `ComponentId` must be unique

Keep `_RowNumber` and `Row ID` hidden/system-style when modeling AppSheet Database tables.

## Ref and Enum-of-Ref rules

Direct `Ref` columns use a `TypeAuxData` JSON object with:

```json
{
  "ReferencedTableName": "ParentTableOrSlice",
  "ReferencedRootTableName": "ParentRootTable",
  "ReferencedType": "Text",
  "ReferencedKeyColumn": "ParentKey",
  "IsAPartOf": true_or_false,
  "Show_If": "...",
  "Editable_If": "...",
  "Suggested_Values": "=ParentTable[ParentKey]"
}
```

`Enum` / `EnumList` base `Ref` columns use `TypeAuxData.BaseType = "Ref"` and `BaseTypeQualifier` containing the same ref qualifier JSON string. Use this for employee/person selectors, equipment selectors, and cached attachment key lists.

For parent-child attachment splits, set the child parent ref as:

```text
Child[ParentID] Type = Ref
ReferencedTableName = parent table
ReferencedRootTableName = parent table
ReferencedKeyColumn = parent key
IsAPartOf = true
```

## Display/Edit safety default

For newly added migration/canary tables, a safe default is:

```appsheet
OR(
  CONTEXT("Host") = "Server",
  IN("IT_Manager", Current User Settings[Appsheet Roles]),
  IN("IT_Admin", Current User Settings[Appsheet Roles]),
  IN("Super_Admin", Current User Settings[Appsheet Roles])
)
```

Use it for `Editable_If` on all columns and for `Show_If` on legacy/cache/system/admin fields. Use `Show_If = TRUE` only for normal user-facing fields intended to be visible during canary review.

## Save and readback pitfalls

- Prefer the AppSheet editor API path (`/api/loadApp` → `/api/saveapp` → `/api/loadApp`) for definition changes. Use browser/editor UI automation only when the API does not expose the required state or when the user explicitly asks for UI work.
- When repairing schema/type metadata for an already-associated AppSheet Database table, do **not** change `DataSet.Source`, `SourcePath`, or `SourceQualifier` unless deliberately re-adding/repointing the source with an account that has source-add permissions. A schema-only repair can save successfully while the same payload with a `SourceQualifier` rename may fail `/api/saveapp` with `Insufficient permissions to add source.`
- A cookie profile that can `GET /api/loadApp` can still receive `403` from `POST /api/saveapp`; if the browser editor is authenticated as the correct admin, use the browser session for the save.
- `/api/saveapp` on a large app can exceed the CDP/tool timeout while still committing later. Do **not** retry blindly. Immediately poll fresh `/api/loadApp/<app_id>` and compare version/schema presence.
- If the first readback still lacks the change, wait briefly and poll again before re-posting the full app payload.
- `validate=false` may be needed for transport/streaming practicality, but always verify `IsValid` and `IsRunnable` after save.
- If `IsRunnable=false`, locate invalid objects by walking the app JSON for `IsValid=false`; distinguish pre-existing invalid process nodes from newly added schema errors.

## Post-save cleanup checks

After save, verify at minimum:

```text
Version advanced
IsValid = true
IsRunnable = true
DataSet exists for each table
DataSchema exists for each table
missing required columns = []
key columns are correct
label columns are sane
Ref / Enum-of-Ref qualifiers target the intended root tables and keys
Show_If / Editable_If are present on every new schema column
```

Watch for inherited-template artifacts when cloning attributes:

- Image columns may inherit `IsLabel=true`; turn it off unless intentional.
- Image/File columns may inherit `Required_If` conditions referencing columns that do not exist in the new table; clear or rewrite them.
- DateTime/Image/File/Yes-No type qualifiers have type-specific JSON shapes. Prefer cloning an existing column of the same AppSheet type rather than constructing a text qualifier from scratch.

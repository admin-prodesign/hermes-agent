# AppSheet key-column metadata and API row edits

Use this when an AppSheet API `Edit`/`Delete`/key lookup depends on the row key, or when improving the AppSheet definition parser/schema exports.

## Durable lesson

Do not infer API row keys from column order, `Row ID`, or heuristic `key_candidates` in generated docs. AppSheet API row edits require the real key column(s). In raw editor JSON from `/api/loadApp`, key metadata lives on schema attributes:

```json
{
  "Name": "PersonID",
  "IsKey": true,
  "IsKeyPart": true,
  "IsLabel": true
}
```

The generated markdown/schema artifacts may omit this metadata even though raw `/api/loadApp` has it.

## Known Pro-Design examples

- `HR_Employees` key: `PersonID`
- `HR_Employees_AppSheet_Settings` key: `PersonID` (not `Row ID`)
- `ActivityLog` key: `ActivityLogID`
- `Case` key: `CaseID`
- `Lookup` key: `LookupID`

## API edit checklist

1. Before `Edit`/`Delete`, verify the target table's actual key from raw `/api/loadApp` (`AppData.DataSchemas[].Attributes[]` with `IsKey`/`IsKeyPart`) or from a validated schema map that preserves those fields.
2. Build edit rows using the real key column and only the intended changed columns.
3. Dry-run by computing planned rows and saving a before snapshot.
4. Execute in small batches.
5. Verify with a fresh `Find` and compare intended fields; if formulas should recalculate, verify downstream formula columns too.

## Parser improvement target

When updating the definition parser, expose key/label metadata in both markdown and structured schema exports, e.g.:

```md
- **PersonID** (Enum) [Physical Column] [Key] [Label]
```

and structured JSON:

```json
{
  "name": "PersonID",
  "type": "Enum",
  "is_key": true,
  "is_key_part": true,
  "is_label": true
}
```

# AppSheet Data Mirror Last Updated incremental sync

Use when a table in the PD One AppSheet Data Mirror gains or relies on an edit timestamp column such as `Last Updated`, especially for `ActivityLog`, `Case`, or `HR_Employees_PerformanceRecords`.

## Durable lesson
Creation timestamps alone do not catch late edits. If the mirror pulls recent rows with selectors like `[Timestamp] >= window` or `[Created On] >= window`, edited older rows stay invisible until a full-table sync. Add/update an edit timestamp in AppSheet and include it in the incremental selector.

## AppSheet column shape to verify
For each table being mirrored by edit time, inspect the deployed AppSheet definition/schema first. The edit timestamp column should be:

- Type: `DateTime`
- Initial value/default: `NOW()` (serialized definitions may show `NOW()` or `=NOW()`)
- Reset on edit: `true`
- No app formula that would prevent the reset behavior

Known PD One examples verified in-session:

- `ActivityLog_Schema.Last Updated`: `DateTime`, `NOW()`, `ResetOnEdit=true`
- `Case_Schema.Last Updated`: `DateTime`, `=NOW()`, `ResetOnEdit=true`
- `HR_Employees_PerformanceRecords_Schema.Last Updated`: `DateTime`, `NOW()`, `ResetOnEdit=true`

## Apps Script mirror patch pattern
Keep existing single-column incremental sync callers working, but allow an array of timestamp columns for late-edit-aware tables.

```js
function buildTimestampSelector_(tableName, timestampColumns, windowStart) {
  const stamp = Utilities.formatDate(windowStart, 'Asia/Taipei', 'yyyy-MM-dd HH:mm:ss');
  const columns = Array.isArray(timestampColumns) ? timestampColumns : [timestampColumns];
  const predicates = columns
    .filter(col => col)
    .map(col => `[${col}] >= DATETIME("${stamp}")`);
  if (!predicates.length) throw new Error(`Missing timestamp column for ${tableName}`);
  const predicate = predicates.length === 1 ? predicates[0] : `OR(${predicates.join(', ')})`;
  return `FILTER("${tableName}", ${predicate})`;
}
```

Then use multi-column selectors for tables with both creation and edit timestamps:

```js
syncTableIncremental_('ActivityLog', ['Timestamp', 'Last Updated'], 0.5, 24);
syncTableIncremental_('Case', ['Created On', 'Last Updated'], 6, 48);
syncTableIncremental_('HR_Employees_PerformanceRecords', ['Timestamp', 'Last Updated'], 6, 48);
```

## Live Apps Script project

Current live Apps Script editor/project for `PD One - AppSheet Data Mirror`:

- Project ID: `13O3tZrKXxdAV70NZP_o5ZlLhMeKLQ2Kf8oPeCV1uY3MpwyBp1Xt11--T`
- Editor URL: `https://script.google.com/home/projects/13O3tZrKXxdAV70NZP_o5ZlLhMeKLQ2Kf8oPeCV1uY3MpwyBp1Xt11--T/edit`

A Drive file named `PD One AppSheet Data Mirror Sync - Code.gs` may exist as a source-copy/backup, but updating that file alone does **not** update the live script editor. Patch the live Apps Script project with `projects.updateContent`, then read it back with `gog appscript content "$SCRIPT_ID"` and verify the exact changelog/selector strings.

## Verification recipe
1. Run a syntax check against a temporary JS copy, e.g. `node --check /tmp/data_mirror_sync_check.js`.
2. Unit-check selector output for both array and legacy string inputs. Expected examples:
   - `FILTER("ActivityLog", OR([Timestamp] >= DATETIME("..."), [Last Updated] >= DATETIME("...")))`
   - `FILTER("Case", OR([Created On] >= DATETIME("..."), [Last Updated] >= DATETIME("...")))`
   - Legacy single-column callers should remain `FILTER("Case_Updates", [Timestamp] >= DATETIME("..."))`.
3. If using the AppSheet API for bounded readback, call `Action=Find` with `TOP(FILTER(...), 1)` to verify selector syntax. Large tables can still time out; a timeout is not proof of selector failure if another table accepted the same pattern and local selector tests passed.
4. If a Drive/source-copy file is used as the Apps Script source of record, replace it and download/read back the file to confirm the new selector strings are present.

## Pitfalls
- Do not treat a newly added `Last Updated` physical column as enough; the mirror selector must also include it.
- Do not remove the creation timestamp from selectors. New rows often rely on `Timestamp`/`Created On`, while late edits rely on `Last Updated`.
- Do not harden transient API read timeouts into a rule that the API is broken. Prefer bounded selector checks, local syntax/unit checks, and source-copy readbacks.

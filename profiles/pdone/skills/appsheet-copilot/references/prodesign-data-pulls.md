# Pro-Design data pulls

Use this reference when the user asks to pull/export real Pro-Design AppSheet data, especially historical ActivityLog rows.

## Canonical data-pull app

Use the **prototype app** for AppSheet data pulls, row reads, aggregate analysis, and historical exports unless Andy explicitly says otherwise.

- Purpose: analysis/data-access mirror of the main Pro-Design app with lighter/no date-based security filters for easier history pulls.
- App ID: `3d6f2d39-9f45-488a-9f5d-6a931d83bd63`
- Credentials file: `/home/prodesign/.openclaw/workspace/projects/AppSheet/keydrop/prototype-app.env`
- Env keys:
  - `APP_ID`
  - `APP_ACCESS_KEY`
  - `RUN_AS_USER_EMAIL`

Do **not** print the access key back to the user.

## Deployed-link rule

When providing AppSheet links to Andy or end users, always link to the **deployed app** (`app_id=f2073120-8c2e-4930-b13c-105838c5e4c3`), even if the evidence/data was pulled through the prototype app.

## Schema-first rule

Before guessing any multi-table path, read the deployed-app definition relationship map:

- `/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/references/prodesign-schema-map.md`
- `/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/references/prodesign-schema-map.json`

Regenerate it from the latest synced deployed-app definition when needed:

```bash
python3 /home/prodesign/.openclaw/workspace/skills/appsheet-copilot/scripts/build_prodesign_schema_map.py
```

Treat these as relationship hints built from:
- explicit `Ref` columns
- `Suggested_Values` sources
- dereference usage like `[Created By].[BU]`
- `LOOKUP()` / `SELECT()` evidence in formulas
- slice source + row-filter references so slices can be collapsed back to base tables

## Slice collapse rule

If a selector, Suggested_Values source, or formula points at a slice like `Current User` or `ActivityLog_MyRelatedActivity`, do not treat that slice name as the real join target.

1. Look it up in `prodesign-schema-map.md`
2. Collapse it to `Source Table`
3. Keep the slice row filter as visibility/context evidence, not as a separate physical table

That avoids fake join paths like `ActivityLog -> Current User` when the real path is `ActivityLog -> HR_Employees`.

### Practical collapse examples

- `Current User` -> `HR_Employees`
- `ActivityLog_MyRelatedActivity` -> `ActivityLog`
- `Lookup_Dropdown_Status` -> `Lookup`

Use the slice name only for AppSheet visibility semantics. Use the base table for join planning, person resolution, export routing, and schema reasoning.

## Important table mapping

For person-based ActivityLog requests:

1. Resolve the person in `HR_Employees`.
2. Take `HR_Employees[PersonID]`.
3. Filter `ActivityLog[Created By] = <PersonID>`.
4. Filter the date window with `ActivityLog[Timestamp]`.
5. Export client-side to `json` / `csv` / proper `xlsx`.

### Default person resolution order

Try these in `HR_Employees`:
- exact `PersonID`
- exact/substring `Name_ZH`
- exact/substring `Name_ZH_EN`
- exact `Employee ID`
- exact `Appsheet Email`

If multiple employees match, stop and show the candidate rows instead of guessing.

## ActivityLog semantics

### Generic person-month export
If the user says something like:
- "Pull March ActivityLog records for 程俊龍"
- "Export April logs for SRQUDSAU"

Interpret it as:
- person lookup in `HR_Employees`
- `ActivityLog[Created By] = PersonID`
- `[Timestamp]` constrained to requested window

### "Reads" requests
Treat "reads" as potentially ambiguous.

- If the user clearly means all activity rows for that person, use only `[Created By]` + `[Timestamp]`.
- If the user specifically wants document read events, probe whether `RefDocs_Read_Check = "Y"` is the intended filter.
- If prior context already established that "reads" means `RefDocs_Read_Check = "Y"`, apply it and say so.

Do not silently invent a read filter when the request might just mean "records".

## Known schema fact

`PersonID` is **not** in `ActivityLog`.
Use `HR_Employees -> PersonID -> ActivityLog[Created By]`.

## Selector patterns

### Resolve employee by PersonID
```appsheet
Filter(HR_Employees, [PersonID] = "SRQUDSAU")
```

### Resolve employee by Chinese or display name
```appsheet
Filter(
  HR_Employees,
  OR(
    CONTAINS([Name_ZH], "程俊龍"),
    CONTAINS([Name_ZH_EN], "程俊龍")
  )
)
```

### March 2026 ActivityLog for a resolved person
```appsheet
OrderBy(
  Filter(
    ActivityLog,
    AND(
      [Timestamp] >= DATETIME("2026-03-01 00:00:00"),
      [Timestamp] < DATETIME("2026-04-01 00:00:00"),
      [Created By] = "SRQUDSAU"
    )
  ),
  [Timestamp],
  false
)
```

### Same query but reads-only heuristic
```appsheet
OrderBy(
  Filter(
    ActivityLog,
    AND(
      [Timestamp] >= DATETIME("2026-03-01 00:00:00"),
      [Timestamp] < DATETIME("2026-04-01 00:00:00"),
      [Created By] = "SRQUDSAU",
      [RefDocs_Read_Check] = "Y"
    )
  ),
  [Timestamp],
  false
)
```

## Export command

Use the skill script when you want the lookup + export flow to be repeatable:

```bash
bash /home/pi/.openclaw/workspace/skills/appsheet-copilot/scripts/export_prodesign_activitylog.sh \
  --person-query '程俊龍' \
  --month 2026-03
```

Reads-only variant:

```bash
bash /home/pi/.openclaw/workspace/skills/appsheet-copilot/scripts/export_prodesign_activitylog.sh \
  --person-query '程俊龍' \
  --month 2026-03 \
  --reads-only
```

Exact PersonID variant:

```bash
bash /home/pi/.openclaw/workspace/skills/appsheet-copilot/scripts/export_prodesign_activitylog.sh \
  --person-id SRQUDSAU \
  --month 2026-03
```

## Employee HR performance and legacy risk-report history

For employee mistake/performance history, contract-decision evidence, or combined charts, read `references/hr-performance-and-risk-report-analysis.md` before pulling data. Key distinctions:

- `HR_Employees_PerformanceRecords` is the AppSheet performance table; resolve `HR_Employees[PersonID]` first, then filter performance rows by `[PersonID]` and join `ActivityLog` by `[ActivityLogID]` for incident details.
- Legacy Google Sheet Risk Reports should be searched by Chinese name first because operator codes can change over time; keep broad code-only matches separate as possible/low-confidence matches.
- When combining sources, report old Risk Report name matches and AppSheet PersonID-backed performance records as separate series, with a clear source caveat.

## Export rules

- Prefer `json` + `csv` + proper `xlsx` together for real pulls.
- For `.xlsx`, use a real writer library (`openpyxl`) in a venv. Do **not** hand-roll OOXML zip files again.
- Write artifacts under `/home/pi/.openclaw/workspace/projects/AppSheet/exports/`.
- Use filenames that encode date window + person, e.g.:
  - `activitylog_2026-03_created-by_SRQUDSAU.xlsx`
  - `activitylog_2026-03_reads_created-by_SRQUDSAU.xlsx`

## Operational notes

- Prototype app API access is known-good when the app's API access is enabled and saved.
- If `403 Forbidden` appears, suspect API disabled/not saved, wrong access key, or policy mismatch.
- If a selector returns zero rows but the user expects data, verify:
  - the person resolved to the right `PersonID`
  - the date window is right
  - `RUN_AS_USER_EMAIL` / visibility context
  - whether the user actually wanted a narrower read-specific filter

## Related local material

- `/home/pi/.openclaw/workspace/projects/AppSheet/docs/appsheet-db/query-playbook.md`
- `/home/pi/.openclaw/workspace/projects/AppSheet/docs/appsheet-hub/README.md`

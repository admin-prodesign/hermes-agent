# HR_E_A_S blank-gap runtime investigation pattern

Use this when the hourly `HR_E_A_S blank settings monitor` reports a new blank gap, especially for duplicated app-setting columns such as `Appsheet Views Access`.

## Goal

Distinguish these cases before naming a cause:

1. `HR_E_A_S` was actually cleared by a writer.
2. `HR_E_A_S` was already blank, but `HR_Employees` later gained a value, newly exposing the mismatch.
3. A user/client edit to a slice backed by `HR_Employees_AppSheet_Settings` submitted stale/blank values and overwrote the settings-table row.

## Evidence sequence

1. Inspect adjacent monitor artifacts in `projects/AppSheet/exports/.../hr_eas_blank_monitor/run-*.json`:
   - previous clean run timestamp
   - first alert run timestamp
   - `blank_gap_keys`
   - `blank_gaps_first50`
2. Read current deployed Data API rows for both tables by `PersonID`:
   - `HR_Employees_AppSheet_Settings`
   - `HR_Employees`
   - compare the six duplicated app-setting fields and `Updater` values.
3. Pull AppSheet exportlog windows between the last clean monitor and first alert. Include:
   - base table: `HR_Employees_AppSheet_Settings`
   - legacy source: `HR_Employees`
   - slices/views backed by `HR_E_A_S`, especially `Current User Settings`
   - user-specific logs if the target `UserId` is known from writes or syncs.
4. Search logs for the `PersonID`, row key, email, and any known name token. Do not rely only on `--table-name HR_Employees_AppSheet_Settings`; slice writes may appear under the slice name.
5. For `Current User Settings` payloads, map values using the slice column order from the synced definition. Current relevant order:
   - `PersonID`
   - `Appsheet Email`
   - `Language`
   - `Team Members`
   - `Appsheet Dashboard Type`
   - `Appsheet Data Access Mode`
   - `Appsheet Views Access`
   - `Appsheet Navigation Bar`
   - `Appsheet Menu Items`
   - `Appsheet Roles`
   - `Appsheet Notification Group`
   - `Combined Appsheet Roles`
   - data-window fields
   - `_Is_*` fields
6. Name the cause only after correlating:
   - clean monitor -> write event -> alert monitor, or
   - prior artifact shows target already blank -> source changed later.

## Confirmed examples

### SMXQSZVW pattern

A `Current User Settings` slice edit wrote blank view/nav/menu values to the underlying `HR_E_A_S` row. The base-table exportlog filter did not show a direct `HR_Employees_AppSheet_Settings` edit; the write surfaced under the slice name.

### JQZUFBCV / 劉庭豪 LIU TINGHAO

Monitor sequence:

- `2026-05-22T07:13:13Z`: `0` blank gaps.
- `2026-05-22T08:14:07Z`: `JQZUFBCV||Appsheet Views Access` flagged.

Runtime evidence:

- `2026-05-22T07:14:42Z`: successful `Edit row` on `Current User Settings`, `UserId=106792559`, row key `xqO6KA21CT4cQ44iJ1OBT8`, `PersonID=JQZUFBCV`.
- The submitted payload mapped to:
  - `Appsheet Dashboard Type = Dashboard_Basic`
  - `Appsheet Data Access Mode = ALL_CHANGES`
  - `Appsheet Views Access = ""`
  - `Appsheet Navigation Bar = ""`
  - `Appsheet Menu Items = ""`
  - roles/groups still populated.

Current Data API comparison showed `HR_E_A_S[Appsheet Views Access]` blank while legacy `HR_Employees[Appsheet Views Access]` remained populated. This is high-confidence evidence that the user-side `Current User Settings` edit blanked the settings-table cell.

## Mitigation notes

- Keep normal-user personal settings editable (`Language`, `Appsheet Navigation Bar`, `Appsheet Menu Items`, `Data_Days_*`) only if that is intentional for the app design.
- Admin/security settings such as `Appsheet Views Access`, dashboard type, roles, notification groups, and stored permission fields should be hidden or non-editable for normal users in `Current User Settings`, or split into a separate admin-only slice.
- If repairing via Data API, key `HR_E_A_S` edits by `PersonID` and omit non-updatable `Row ID` unless raw `/api/loadApp` proves otherwise.

# HR_E_A_S client-cache incident debugging

Use this reference when a user reports AppSheet showing blank settings or `_Is_*`/permission booleans as false, but the live `HR_Employees_AppSheet_Settings` database row appears correct.

## Trigger pattern

- User reports AppSheet went blank, dashboard/menu disappears, or `_Is_*` columns appear false.
- A screenshot/report has a precise local time, often Taipei time (TPE/Asia-Taipei).
- Live AppSheet DB / Data API currently shows the expected `HR_E_A_S` values.
- Manual browser logout/login or app restart fixes the user-facing state.

## Investigation workflow

1. Resolve the affected person to `PersonID`, AppSheet email, and AppSheet Monitor `UserId` if possible.
2. Convert the report/screenshot time from TPE to UTC. Query at least +/- 90 minutes around the event.
3. Pull AppSheet Monitor/exportlog rows for both:
   - `user-id=<affected AppSheet UserId>` with syncs/adds/updates/workflows/API enabled.
   - `table-name=HR_Employees_AppSheet_Settings` for the same window.
4. Read the live `HR_Employees_AppSheet_Settings` row via the deployed Data API and compare:
   - core settings: dashboard/views/navigation/menu/roles/notification group
   - `Combined Appsheet Roles`
   - `_Is_*` formula-backed columns
   - maintenance fields such as `Updater` and `Data_Days_*`
5. Check whether any bot/action actually wrote the affected key. Distinguish:
   - direct settings/role clears (serious data issue)
   - daily maintenance writes that only reset `Data_Days_*`/`Updater`
   - app sync/cache behavior showing stale rows
6. Inspect sync log fields for cache staleness:
   - `initiatedBy` (`AppStart`, `User`, `Polling`, `PushedChanges`)
   - `IfModifiedSinceDate`
   - `lastSyncTime` / `dataStamp`
   - `AppDefinitionChanged`
   - `AppTemplateVersion`
   - per-table `Table:HR_Employees_AppSheet_Settings` status, especially `NotModified:True`
   - `perTableParams` etag/time for `HR_Employees_AppSheet_Settings`

## Interpreting the evidence

If a table write occurred near the screenshot but touched only maintenance columns, and the live Settings row has correct values while subsequent user syncs report `HR_Employees_AppSheet_Settings ... NotModified:True`, treat this as AppSheet client/session cache staleness rather than database blanking.

A stale-client signature observed in May 2026:

- User AppStart sync came from a very old `lastSyncTime` / `IfModifiedSinceDate`.
- App definition changed during the incident window.
- `HR_E_A_S_DailyMaintenance` wrote all settings keys, including the affected person, but only via `HR_E_AppSheet_Settings_ResetDataDaysToDefault`.
- Later polling syncs still reported `HR_Employees_AppSheet_Settings` as `NotModified:True`.
- Logout/login forced a clean reload and fixed the UI.

## Response guidance

- Do not run a data backfill solely because the UI looked blank if live Data API/database checks are clean.
- Tell affected users to manual sync; if still wrong, sign out/in; if still wrong, provide email/name and screenshot time.
- If many users are affected, consider a safe stable-version bump or cache-invalidating app-definition change after verifying the DB is correct.
- Keep/extend an hourly monitor for real blank gaps, but note its coverage window explicitly; a monitor that ended before the screenshot cannot prove the exact event time.

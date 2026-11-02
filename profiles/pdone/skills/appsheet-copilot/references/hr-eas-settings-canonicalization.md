# HR_E_A_S AppSheet Settings Canonicalization

Use this reference when continuing or auditing the Pro-Design AppSheet migration that makes `HR_Employees_AppSheet_Settings` (`HR_E_A_S`) canonical for AppSheet runtime authorization/settings while keeping `HR_Employees` (`HR_E`) canonical for HR/person facts.

## Canonical split

- `HR_Employees` remains canonical for identity and HR/employment facts, including `Appsheet Email`.
- `HR_Employees_AppSheet_Settings` remains keyed by `PersonID` and should keep `Appsheet Email` formula-backed from `[PersonID].[Appsheet Email]` for direct `USEREMAIL()` lookups.
- `HR_E_A_S` is canonical for app-runtime fields such as:
  - `Appsheet Dashboard Type`
  - `Appsheet Views Access`
  - `Appsheet Navigation Bar`
  - `Appsheet Menu Items`
  - `Appsheet Roles`
  - `Appsheet Notification Group`
  - `Combined Appsheet Roles`
  - data access/cutoff fields and `_Is_*` permission booleans.
- Do not move general HR/person facts into `HR_E_A_S` just because a user-facing expression can read `Current User Settings`.
- External identity/contact mappings such as `HR_Employees[LINE User ID]` are HR/person facts, not AppSheet runtime settings. Keep them on `HR_Employees` unless a separate many-to-one identity mapping table is intentionally designed; do not store them in `HR_E_A_S`.

## Security-filter pattern

Prefer direct base-table lookup in security filters and update-mode expressions:

```appsheet
LOOKUP(
  USEREMAIL(),
  "HR_Employees_AppSheet_Settings",
  "Appsheet Email",
  "<permission-or-setting-column>"
)
```

Avoid using the `Current User Settings` slice as the default security-filter dependency, e.g. avoid:

```appsheet
ANY(Current User Settings[_Is_SuddenAbsence_User])
```

Use `Current User Settings[...]` mainly for client-side UX/show-if/action readability after confirming the referenced column is an app setting, not a person fact.

## Safe migration sequence

1. Fresh-sync/read the AppSheet definition before advice or writes.
2. If the user asks to begin a significant migration, start a new major version seed (`YY.MMDD00`); AppSheet may save the next patch number.
3. Migrate security filters first, one low-risk filter at a time, from slice `ANY(...)` to direct `LOOKUP(...)`.
4. Migrate Presentation/UX references from `Current User[...]` to `Current User Settings[...]` for app-setting columns.
5. Migrate AppData slice/action conditions only for app-setting columns; leave `Current User[PersonID]`, `Current User[Language]`, and other HR/person facts alone unless explicitly reviewed.
6. Make `HR_E_A_S` settings independently canonical only after a data backfill/verification step. If the next edit rewrites access/security/notification references from `HR_Employees` to `HR_E_A_S`, **do the backfill first, then rewrite references** so users never experience a temporary lack of access because canonical settings are still blank.
   - For every `HR_E_A_S` row, copy the six duplicated app-setting values from the linked `HR_Employees` row when `HR_E_A_S` is blank and HR has a value: `Appsheet Dashboard Type`, `Appsheet Views Access`, `Appsheet Navigation Bar`, `Appsheet Menu Items`, `Appsheet Roles`, and `Appsheet Notification Group`.
   - Preserve existing nonblank `HR_E_A_S` values; do not overwrite them from `HR_Employees` during the migration backfill.
   - Verify that `HR_E_A_S[Combined Appsheet Roles]` recomputes non-blank for expected users before removing `[PersonID].[...]` defaults or changing expressions to depend on `HR_E_A_S`.
  - Also verify and, if needed, backfill physical permission-booleans derived from `Combined Appsheet Roles` (`_Is_ActivityLog_User`, `_Is_Case_User`, `_Is_IT_Admin`, `_Is_HR_E_NA_Viewer`, `_Is_CustomerViewer`, `_Is_InventoryMgmt_User`, `_Is_Maintenance_User`, `_Is_SuddenAbsence_User`). AppSheet API edits to roles/groups can leave stored App formula columns stale even when `Combined Appsheet Roles` looks correct; stale `N` values make Home views appear while table security filters return no rows.
  - Specifically test Andy/normal admin accounts for `_Is_ActivityLog_User` and `_Is_Case_User`; if these flags are `N`, ActivityLog/Case rows can be hidden behind security filters even though menus/views are visible.
  - Do **not** treat a permission-boolean repair as proof that the settings migration is complete. First require zero blank core settings in `HR_E_A_S` where `HR_Employees` still has values for the six duplicated app-setting columns. A common failure after stable promotion is: `HR_E_A_S[Appsheet Dashboard Type]` is blank, but `HR_Employees[Appsheet Dashboard Type]` is populated; the stable app uses `ANY(Current User Settings[Appsheet Dashboard Type])`, so the user's Home/default-start view is empty even though the person row and legacy HR settings are correct.
7. Remove `Default`/initial values that pull duplicated app settings from `[PersonID].[...]` only after the backfill, blank-core-settings audit, and derived permission-boolean verification are complete.
8. Preserve formulas that are intentionally derived:
   - `HR_E_A_S[Appsheet Email] = [PersonID].[Appsheet Email]`
   - `HR_E_A_S[Combined Appsheet Roles] = UNIQUE([Appsheet Notification Group] + [Appsheet Roles])`
9. Resync after each save and audit raw expressions before claiming success.
10. Do not delete old duplicate `HR_E` app-setting columns until a zero-reference audit and an operations cycle confirm no breakage. Hide/deprecate first if needed. If Andy asks to “monitor for a few days,” create a real read-only canary/monitor job rather than merely promising to check later; see `references/appsheet-hr-eas-canary-monitor.md`. Before any actual column removal, also read `references/appsheet-hr-eas-deprecated-column-removal.md`: bot/task recipient and process-condition expressions may still filter `HR_Employees` by `[Appsheet Roles]` or `[Appsheet Notification Group]` via `SELECT()`/`FILTER()` even after UX/security-filter references have been migrated.
11. Do not promote to stable until user/business validation is complete, **unless Andy explicitly chooses stable promotion as the live canary test**. In that case, promote the current latest version to stable as a monitored canary, verify `StableVersion == Version`, document the previous stable version for rollback, and tell Andy what to watch for: missing dashboard/menu items, role/view regressions, security-filter visibility problems, sync errors, and notification-group routing issues.

## Bot/task recipient migration pattern

When migrating bot/task/process expressions that select `HR_Employees` recipients by app-setting fields, preserve the person/communication semantics on `HR_Employees` but move only the settings membership test to `HR_E_A_S` via `PersonID`.

For scheduled email tasks whose attachment is generated but `EmailTo` is blank at runtime, first audit the exact recipient tokens in both the legacy person table and the canonical settings table before changing automation definitions. A confirmed monthly-report pattern is: task `ToList` selects `HR_Employees[Appsheet Email]` while testing `LOOKUP([PersonID], "HR_Employees_AppSheet_Settings", "PersonID", "Appsheet Roles")` for tokens such as `5S_Points_ReportEmailRecipient` or `IncidentReport_Points_ReportEmailRecipient`. Repair flow: scan `HR_Employees` for those tokens in legacy role/group fields, read the matching `HR_Employees_AppSheet_Settings` rows by `PersonID`, append only missing recipient tokens to `HR_E_A_S[Appsheet Roles]` while preserving existing values, omit `Row ID` from the edit payload, then read back both the `Lookup_Dropdown_Appsheet_Role` token rows and the affected `HR_E_A_S` rows.

When using `appsheet_table_probe.py` for this audit, pass a full selector such as `Filter(HR_Employees_AppSheet_Settings, CONTAINS([Appsheet Roles], "5S_Points_ReportEmailRecipient"))`. Bare boolean selectors like `CONTAINS([Appsheet Roles], "...")` can return misleading zero-row results for this workflow even when matching rows exist. Likewise, use `Filter(Lookup_Dropdown_Appsheet_Role, [LookupID] = "...")` for dropdown existence checks.

If the selected output is only email addresses and the role membership is purely in `HR_E_A_S`, prefer the direct canonical recipient expression:

```appsheet
SELECT(
  HR_Employees_AppSheet_Settings[Appsheet Email],
  IN("<ReportEmailRecipientRole>", [Appsheet Roles])
)
```

For scheduled report emails, harden the process with an `IF_ELSE` branch before the report email task:

```appsheet
COUNT(
  SELECT(
    HR_Employees_AppSheet_Settings[Appsheet Email],
    IN("<ReportEmailRecipientRole>", [Appsheet Roles])
  )
) > 0
```

- True branch: run the real report email task with the direct canonical recipient expression above.
- False branch: run a separate failure-notification email to the admin/operator explaining that the recipient list was empty and the report email was not sent. Do not silently add the admin as a fallback recipient to the real report email unless Andy explicitly requests that behavior.
- Literal email addresses in task `ToList` must be quoted expressions such as `="admin@example.com"`; a bare `admin@example.com` is parsed as an expression and can fail validation because hyphens are interpreted as subtraction.
- After `/api/saveapp`, require `IsRunnable=true`, `IsValid=true`, zero severity-0 errors for the changed tasks/processes, `StableVersion == Version` if the live schedule must use the change, and a fresh definition sync/readback showing both branch conditions and task `ToList` values.

Example rewrite pattern:

```appsheet
-- Old membership test inside SELECT(HR_Employees[Appsheet Email], ...)
IN("HR_Manager", [Appsheet Roles])

-- New membership test while still selecting employee emails/language from HR_Employees.
-- LOOKUP() returns scalar text, so split the EnumList text back to a list before IN()/INTERSECT().
IN(
  "HR_Manager",
  SPLIT(
    LOOKUP(
      [PersonID],
      "HR_Employees_AppSheet_Settings",
      "PersonID",
      "Appsheet Roles"
    ),
    " , "
  )
)
```

For notification-group membership use the same pattern with `"Appsheet Notification Group"`. In particular, `INTERSECT(LOOKUP(...), [_THISROW].[Notification Group])` is invalid because `LOOKUP()` is scalar text; use `INTERSECT(SPLIT(LOOKUP(...), " , "), [_THISROW].[Notification Group])`. Keep `HR_Employees[Appsheet Email]`, `[Language]`, `[PersonID]`, and employee ref checks on `HR_Employees` unless the whole expression is intentionally being redesigned. Avoid blind global replacement: patch source expression fields and the matching parsed expression strings only in the targeted automation subtrees, then verify expression-bearing paths rather than schema type qualifiers.

## Raw editor JSON as source of truth

For structure-sensitive AppSheet work, treat fresh `/api/loadApp` raw editor JSON as the authoritative structured definition for editor-managed app configuration. It contains metadata that the old HTML/appdoc export and generated markdown artifacts may omit or flatten, including `IsKey`, `IsKeyPart`, `IsLabel`, table `DataFilter` security filters, update modes, schema attributes, slices, presentation controls/views, tasks/workflow/automation objects, and parsed `ExprLookup` trees.

The old `template/appdoc` HTML download and `doc-to-md.py` parser are deprecated. New sync/tooling should fetch `/api/loadApp`, store the raw parsed app JSON (currently `latest_raw_app.json` in the OpenClaw workspace, with `latest.json.canonical_raw_app_path` pointing to it), and regenerate Markdown/schema indexes from that raw JSON.

Generated markdown/schema indexes are useful human-readable derivatives, but they must not be the only source for API writes or migration planning. In particular, do not infer API edit keys from column order or `Row ID`; read `AppData.DataSchemas[*].Attributes[*].IsKey` from raw JSON first. The HR_E_A_S backfill failure mode was caused by using `Row ID` while the raw editor JSON correctly showed `PersonID` as `IsKey=true` / `IsKeyPart=true`.

When improving the parser, preserve these fields in normalized outputs: `is_key`, `is_key_part`, `is_label`, `is_required`, `default`, `formula`, type qualifier expressions, table `data_filter`, update mode, and automation/bot/process/task wiring.

## `/api/saveapp` implementation pattern

Use the existing OpenClaw helper model:

- Fresh `GET /api/loadApp/<app_id>` using authenticated editor cookies.
- Write a before snapshot.
- Mutate only known JSON paths.
- `POST /api/saveapp` with full app JSON (`appId`, `appJson`, `validate=true`) as gzip JSON.
- Save response JSON.
- Inspect the save response `AppErrors.Errors` and the returned/synced app flags before reporting success.
- Require the saved/latest version to show `IsRunnable = true` and `IsValid = true`, with zero severity-0 validation errors. If the saved version is not runnable, proactively diagnose the save-response errors, patch the expressions/config, save a new version, and re-verify until latest is runnable or a real blocker is reported. Do not leave the user to discover that the latest version is non-runnable.
- Resync definition and compare the returned/synced app version and targeted expressions.

Known working patch scopes from this migration:

- Set new version seed.
- Replace an existing table `DataFilter` security-filter expression.
- Replace Presentation view/menu/default-start expressions.
- Replace AppData slice/action expressions.
- Clear `Default` values on `HR_Employees_AppSheet_Settings_Schema` duplicated app-setting columns.

## Consistency audits before writing

When checking whether employees have consistent AppSheet runtime settings, do a **read-only** audit first; do not normalize rows just because people share a BU/job level.

Recommended grouping hierarchy:

1. Join `HR_Employees_AppSheet_Settings` to `HR_Employees` by `PersonID`.
2. Compare settings by `BU + Job Level` first.
3. Also test whether adding `Job Title` changes the findings (`BU + Job Level + Job Title`). If issue counts do not change, report that job title did not explain the variance.
4. Normalize EnumList settings before comparison by splitting on commas, trimming whitespace, sorting, and rejoining; this prevents order/spacing from looking like a real difference.
5. Compare these columns at minimum:
   - core settings: `Appsheet Dashboard Type`, `Appsheet Views Access`, `Appsheet Navigation Bar`, `Appsheet Menu Items`, `Appsheet Roles`, `Appsheet Notification Group`, `Combined Appsheet Roles`, `Appsheet Data Access Mode`
   - data windows: `Data_Days_ActivityLog`, `Data_Days_Case`, `Data_Days_InventoryMgmt`, `Data_Days_Maintenance`, `Data_Days_ProductionReports`, `Data_Days_RefDocs`
   - permission booleans: `_Is_ActivityLog_User`, `_Is_Case_User`, `_Is_CustomerViewer`, `_Is_HR_E_NA_Viewer`, `_Is_IT_Admin`, `_Is_InventoryMgmt_User`, `_Is_Maintenance_User`, `_Is_SuddenAbsence_User`
6. Classify findings, but treat the classification as review priority rather than proof of error:
   - high: role, notification group, combined roles, cutoff windows, or `_Is_*` differences
   - medium: dashboard/views/menu/nav differences
   - low: blank-vs-nonblank UX differences that may be intentional
7. Report minority/outlier people in each cohort by `PersonID`, name, and job title, but explicitly state that special-duty exceptions may be legitimate.
8. Recommended output artifacts for repeatable audits:
   - `joined_rows.json`
   - `issues.json`
   - `issues.csv`
   - `issue_cohort_detail.csv`
   - `summary.md`

Important interpretation rule: **do not mass-normalize by BU/job level.** Use the audit to create a human review queue and then define explicit baseline templates per cohort. Only future checks should flag deviations from approved baselines.

Typical strong review candidates are rows where peers have baseline `Appsheet Roles`/`Combined Appsheet Roles`/`_Is_Case_User` values but the candidate is blank or `N`. Variations involving maintenance, sudden absence, inventory, QA, customer, point-viewer, or reporting roles often indicate special duties and need confirmation rather than automatic correction.

## Views Access redundancy audits

When Andy asks which `Appsheet Views Access` entries can be removed because `Appsheet Notification Group` already grants the same access, do a grouped read-only audit instead of dumping per-employee rows.

Recommended method:

1. Pull `HR_Employees_AppSheet_Settings`, `HR_Employees`, and `Lookup` read-only from the prototype app.
2. For each `HR_E_A_S[Appsheet Views Access]` token, read the matching `Lookup[LookupID]` row and split `Lookup[Viewable Roles]` as the view's role/group grant list.
3. Treat a view assignment as redundant only when the employee's `Appsheet Notification Group` intersects that view's `Lookup[Viewable Roles]`. Do not count coverage from `Appsheet Roles` when the user specifically asks what Notification Group makes redundant.
4. Inspect the current editor JSON `Presentation.Controls[].ShowIf` before recommending removal:
   - **Safe to remove now:** view ShowIf already uses `Current User Settings[Combined Appsheet Roles]` + `LOOKUP("<view>", "Lookup", "LookupID", "Viewable Roles")`, or otherwise no longer depends on `Appsheet Views Access`.
   - **Migrate ShowIf first:** the view is logically covered by Notification Group but still has `IN("<view>", Current User Settings[Appsheet Views Access])`; removing the value first can hide the view.
   - **Inactive/old-view cleanup:** `Lookup[Active] = "N"` or completed/uncompleted legacy split views; remove from settings as stale configuration, not as live permission simplification.
   - **Needs special check:** active Lookup rows without a detected current ShowIf pattern, especially views surfaced indirectly by dashboards/menu/default-start logic.
5. Group output by cleanup bucket, view family, BU/template cohort, and highest-impact repeated bundles. Avoid raw per-row dumps unless Andy explicitly asks for them.
6. Keep raw artifacts (`json`/`csv` plus a concise `summary.md`) under `projects/AppSheet/exports/<audit-name>/` for auditability, but present only the intelligent grouped summary in chat.

Useful interpretation notes from redundancy audits:

- `ERP_Assets_Molds` was heavily covered by notification groups but still used the legacy `Appsheet Views Access` ShowIf, so it required ShowIf migration before row cleanup. A safe ShowIf migration pattern is to keep the existing menu/nav surfacing guard, then replace the view-access gate with a role/group intersection:

  ```appsheet
  AND(
    OR(
      IN("<view>", Current User Settings[Appsheet Navigation Bar]),
      IN("<view>", Current User Settings[Appsheet Menu Items])
    ),
    ISNOTBLANK(
      INTERSECT(
        ANY(Current User Settings[Combined Appsheet Roles]),
        LOOKUP("<view>", "Lookup", "LookupID", "Viewable Roles")
      )
    )
  )
  ```

  Verify by reloading `/api/loadApp` after save and comparing the exact `Presentation.Controls[].ShowIf` for the targeted view; changing latest/editor version does not imply stable promotion.
- Old Case split-view tokens such as completed/uncompleted Tech Dev, Facilities Repair, or IT variants should be classified as stale settings when all three are true: `Lookup[Active] = "N"`, no current `Presentation.Controls` entry, and no current `Presentation.MenuEntries` entry. Remove those from `HR_E_A_S[Appsheet Views Access]` as inactive-view cleanup, not as live permission simplification.
- Some personal/default views such as `HR_MyData`, `HR_Employees_BasicList`, and `ActivityLog_MyActivity` were not covered by Notification Group and should stay unless a separate role/group model is designed.
- Sudden-absence views may need a separate surfacing check before cleanup even when `Lookup[Viewable Roles]` says notification groups cover them.

## Disabling unsafe HR_E_A_S populate bots

When root-cause evidence shows a bot is reintroducing blank settings rows, disable the bot as a live AppSheet definition change before rerunning any data backfill.

1. Fresh-load the deployed app through `/api/loadApp/<app_id>` and record `Version`, `StableVersion`, `IsRunnable`, `IsValid`, and the target bot's `Disabled`, `EventName`, and `ProcessName`.
2. Find the exact `Behavior.AppBots[]` entry by `Name` (for this migration, `HR_E_AppSheet_Settings_Populate`) and require exactly one match before editing.
3. Mutate only `bot["Disabled"] = true`; do not delete the bot, event, process, or action unless separately approved. This keeps rollback and later redesign easy.
4. Save the full app JSON via `/api/saveapp` with `validate=true`, then reload and require `IsRunnable = true`, `IsValid = true`, zero severity-0 errors, and target bot `Disabled = true`.
5. If the latest version differs from `StableVersion`, promote the current latest with the admin/owner `SetStableVersion` workflow from `SKILL.md`; otherwise the scheduled live bot may still run from the old stable version.
6. Reload again after stable promotion and require `Version == StableVersion` and target bot `Disabled = true` before reporting completion.
7. Sync the local raw definition snapshot and generated `latest.json`/`latest.md`; commit/push the scoped definition backup when a backup repo is configured.

## Verification probes

After saves, verify the full app JSON or the latest synced editor definition for both **latest** and **stable** where user impact depends on stable rollout. A clean latest version is not enough if `StableVersion` still points at an older app definition; explicitly load the stable version with a concrete stable version string (for example `/api/loadApp/<app_id>?version=<StableVersion>`) and run the same blocker scan before declaring stable users clean. Avoid using `?version=stable` as proof of stable content; observed editor behavior can return the latest app while still reporting the older `StableVersion` pointer.

Check latest/stable for:

```text
Current User[Appsheet Dashboard Type]
Current User[Appsheet Views Access]
Current User[Appsheet Navigation Bar]
Current User[Appsheet Menu Items]
Current User[Appsheet Roles]
Current User[Appsheet Notification Group]
Current User[Combined Appsheet Roles]
```

These should be zero in raw expression-bearing fields after migration.

Also check no duplicated setting defaults remain in `HR_E_A_S`:

```text
[PersonID].[Appsheet Dashboard Type]
[PersonID].[Appsheet Views Access]
[PersonID].[Appsheet Navigation Bar]
[PersonID].[Appsheet Menu Items]
[PersonID].[Appsheet Roles]
[PersonID].[Appsheet Notification Group]
```

The save response may contain pre-existing unrelated warnings. Search targeted warnings/errors for the changed columns before reporting success. Always inspect severity-0 errors and `IsRunnable`/`IsValid` in the save response or immediate reload; a save response of `Success:true` is not enough. If latest is not runnable after a migration save, fix it proactively before asking the user to test or promote stable.

## Pitfalls

- API row edits on `HR_Employees_AppSheet_Settings` must use `PersonID` as the row key. Do not assume `Row ID` is the API key just because it appears first in parsed documentation; verify `IsKey`/`IsKeyPart` from raw `/api/loadApp` when uncertain. See `references/appsheet-key-column-metadata.md` for the broader API key-column checklist.
- `Lookup[Viewable Roles]` is an `EnumList`/`Ref` with `Valid_If = Lookup_Dropdown_Appsheet_Role[LookupID] + Lookup_Dropdown_NotificationGroups[LookupID]`. The AppSheet Data API can still reject otherwise-valid notification-group edits for this column (for example adding `Team_SeniorStaff` or `Team_Molding_Staff`) with `Invalid value for column Viewable Roles`. If the requested tokens are verified in the dropdown slices but the Data API rejects the edit, use a bounded editor-definition workaround: save a before snapshot, temporarily clear only the `Lookup_Schema[Viewable Roles].TypeAuxData.Valid_If` via `/api/saveapp`, perform only the targeted `Lookup` row edits, restore the original `TypeAuxData`, promote the restored version stable, and verify the final `Valid_If`, latest/stable version, active flags, and role sets. AppSheet may re-order EnumList values; verify as sets, not strings.
- If `HR_E_A_S[Appsheet Roles]` and `[Appsheet Notification Group]` are blank, `Combined Appsheet Roles` becomes blank and downstream `_Is_*` booleans can incorrectly evaluate `N`, hiding records behind security filters. Backfill existing rows before removing `[PersonID].[...]` defaults.
- Even when `Combined Appsheet Roles` is nonblank, stored `_Is_*` App formula columns can remain stale after API role/group backfills. Symptom: Home/dashboard/menu views are visible from migrated roles, but clicking into views shows no rows because table security filters use `LOOKUP(USEREMAIL(), "HR_Employees_AppSheet_Settings", "Appsheet Email", "_Is_*")`. Audit expected `_Is_*` values from the combined role set and repair mismatches before declaring the migration healthy.
- Do not use broad text replacement across schema type qualifiers; only mutate expression-bearing/config fields or carefully chosen JSON subtrees.
- Replacing both raw text expressions and their `ExprLookup` parsed tree may inflate change counts. That is expected when replacing inside the full saved app object, but the final user-facing audit should focus on targeted expression paths and app validation.
- Clearing defaults affects only new/edited settings rows. Ensure existing `HR_E_A_S` row values already contain the intended settings before removing HR_E-derived defaults.
- `Current User Settings` is readable in UX/client logic, but security filters should prefer direct `LOOKUP()` against the base table.
- After promoting an `HR_E_A_S` migration stable, an empty Home/default-start view for a user usually points first to blank `HR_E_A_S[Appsheet Dashboard Type]`, not to table security filters. Resolve the user by `HR_Employees`, compare the six duplicated app-setting fields between `HR_Employees` and `HR_E_A_S`, and dry-run a backfill that copies only blank `HR_E_A_S` values from populated HR values plus recomputes `Combined Appsheet Roles` and `_Is_*` flags. If the dry-run shows many affected rows, pause for approval on global vs single-row repair before writing.
- When checking for “something overwriting these values,” do not stop at expression/reference hits. Audit actual writers in raw `/api/loadApp` JSON by parsing `AppData.DataActions[].ActionSettings`: classify `SET_COLUMN_VALUE` assignments by `ColumnToEdit`, classify `ADD_RECORD_TO` actions whose `ReferencedTable` is `HR_Employees_AppSheet_Settings`, then map those actions back to `Behavior.AppProcesses` and `Behavior.AppBots`. A key failure mode is not a direct overwrite: active bots can create/repopulate `HR_E_A_S` rows with only `PersonID` (for example employee-added or scheduled populate bots), leaving settings blank after defaults were removed. Report this separately from direct setting-column writes.
- For runtime evidence, pull fresh exportlog rows for `HR_Employees_AppSheet_Settings` with syncs disabled and adds/updates/deletes/API enabled, then separate REST API repair batches from bot/process activity. Treat local definition scans as “is it wired?” evidence and fresh logs as “did it actually run?” evidence.
- A confirmed root-cause pattern from the May 2026 HR_E_A_S migration: a successful REST API backfill can be undone logically (not by clearing existing cells) if `HR_E_AppSheet_Settings_Populate` remains scheduled after `[PersonID].[...]` defaults are removed. In the deployed app this bot ran daily at `5 3 * * *` Taipei time over `HR_Employees_CurrentlyEmployed_BasicInfo` and invoked `Action for Populate HRS_Data_MasterNames by adding PersonID`, an `ADD_RECORD_TO` action that assigns only `PersonID`. Runtime logs show it returned 127 source rows; writer audit showed zero actions directly writing the six core settings columns. Prevention is to disable or narrow this populate bot before/with backfill, or change it to only create missing rows and immediately assign/backfill baseline settings; then add a monitor for blank core settings after the bot's scheduled time.
- Another confirmed May 2026 symptom: a user's browser/client can continue showing stale `FALSE`/blank `Current User Settings[_Is_*]` values even when the AppSheet database and Data API show the physical `_Is_*` columns are already correct. Logging out and back in cleared the browser-side state. When a report says “database is correct but app still shows FALSE,” first check hourly monitor/API values and export logs for writes; if clean, treat it as client/session cache rather than data blanking. App settings at the time: `SyncOnStart=true`, `DeltaSync=true`, `FullOfflineCaching=false`, `ServerCachingInterval=FIVE_MINUTE`; table sync logs may show stale `IfModifiedSinceDate`/etag reuse. Ask affected users to force a full sync or sign out/in; consider a small stable-version bump only if many users need client cache invalidation.
- When an `HR_E_A_S` blank-core-settings monitor alerts on “new blank gaps,” do not assume the `HR_E_A_S` cell was newly cleared. Interpret the alert as “new mismatch since baseline.” Check historical `HR_E_A_S` snapshots/backfill artifacts and the current/previous `HR_Employees` value. A common pattern is: the `HR_E_A_S` setting was already blank, the legacy `HR_Employees` value was also blank during the backfill, then `HR_Employees` later gained a value; the monitor correctly flags a new gap even though no `HR_E_A_S` writer blanked anything. Verify by comparing adjacent monitor artifacts (`run-*.json`), current API rows for both tables, and exportlog windows for both `HR_Employees_AppSheet_Settings` and `HR_Employees` around the transition. For a compact reusable checklist and confirmed examples, read `references/hr-eas-blank-gap-runtime-investigation.md`.
- AppSheet exportlog `tableName=` filters can return sync rows and the agent's own REST `Find` calls but still omit the field-level reason for a value appearing/disappearing. For a suspected setting blanking, separate three evidence types before naming a cause: (1) monitor/API evidence of the current mismatch, (2) historical artifacts showing whether the target cell itself changed, and (3) runtime writer evidence (`Edit row`, `Add row`, REST `Edit`/`Add`) that includes the target key or action. If only (1) is present and historical artifacts show the target was already blank, report it as a legacy blank newly exposed by a source-side change, not as “blanked out again.”
- A confirmed live blanking pattern: edits to the `Current User Settings` slice can write back to the underlying `HR_Employees_AppSheet_Settings` row and overwrite app-setting fields from stale/blank client-side values. In the SMXQSZVW case, monitor first flagged `Appsheet Views Access` blank at 2026-05-21T00:48Z; exportlog showed three successful `Edit row` operations on `Current User Settings` by the same AppSheet user at 00:28:49/52/55Z, with row data key `7HXOXMvWNn4HesdGydjXnb`, `PersonID=SMXQSZVW`, blank view/nav/menu fields, and old `Updater=20260315.203016`. In the JQZUFBCV case, the previous monitor was clean at 2026-05-22T07:13Z, then a successful `Current User Settings` edit at 07:14:42Z submitted `Appsheet Views Access = ""` in the slice payload, and the next monitor flagged the blank at 08:14Z. There was no direct `HR_Employees_AppSheet_Settings` edit in the table-filtered logs because the write surfaced under the slice name. Mitigation: make duplicated app-setting columns non-editable/hidden in `Current User Settings` (or split user-editable personal settings from admin-only app settings), and when auditing writers include slice table names that point to `HR_E_A_S`, not only the base table name. Do not use `CONTEXT("Host") = "Server"` as an `Editable_If` bypass for stored HR_E_A_S admin/runtime setting columns; server/slice saves can then accept stale blank values. In May 2026 this bypass was removed from `Appsheet Dashboard Type`, `Appsheet Views Access`, `Appsheet Roles`, `Appsheet Notification Group`, and `Updater`.
- For `HR_Employees_AppSheet_Settings` Data API `Edit` repairs, omit `Row ID` from the update payload unless it is truly the API key for that table. In the deployed PD One app, an edit keyed by `PersonID` succeeded, while including `Row ID` caused HTTP 400: `field 'Row ID' is not updatable`.
- HR_E_A_S `Data_Days_*` columns are intended to remain user-editable personal sync/data-horizon settings. `Appsheet Navigation Bar` and `Appsheet Menu Items` are also normal-user editable. When hardening `Editable_If`, follow restricted `Show_If` columns only for physically editable/stored columns; do **not** add `Editable_If` to columns that have an App Formula, because AppSheet ignores it and warns: `cannot use an EditableIf constraint if it has an App Formula`. For formula-backed columns such as `Team Members`, `Combined Appsheet Roles`, `Appsheet Data Access Mode`, and `_Is_*` booleans, keep the admin-only `Show_If` for visibility but leave `Editable_If` blank.

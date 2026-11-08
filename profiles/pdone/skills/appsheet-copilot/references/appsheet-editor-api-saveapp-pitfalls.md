# AppSheet Editor API `/api/saveapp` Pitfalls and Verification Notes

Use this reference when implementing AppSheet editor JSON changes through `loadApp`/`saveapp`, especially automation/action/slice edits.

## Durable lessons from ActivityLog queue repair work

### Pro-Design editor version scheme

Before manually editing `Version`, follow `references/appsheet-editor-versioning.md`. Pro-Design AppSheet major versions are date-based:

```text
YY.MMDD00
```

For example, on 2026-06-18 UTC, the major version should be:

```text
26.061800
```

Do not use semantic-major values such as `27.000001` for “major” AppSheet changes. AppSheet enforces monotonic version progression; once a high incorrect version is created, a later correction to the date-based value can be rejected with a 409 conflict because the lower version is no longer allowed.

### Preserve action definition `$type`
When editing `DataAction` objects, keep the typed `ActionDefinition` shape. A safe pattern is:

- serialize `ActionSettings` as plain JSON without `$type`;
- write `ActionDefinition` as the same settings plus the original or inferred `$type`.

If `$type` is omitted from `ActionDefinition`, `/api/saveapp` may reject the payload with a generic:

```text
Unable to deserialize app.
```

In a loaded app, `ActionSettings` is a JSON string and `ActionDefinition` is an object. Keep those types. Clone `ActionDefinition` from an action of the same `ActionType` and edit fields in place. A newly built dict with the same keys and `$type` can still return `Unable to deserialize app`. A rename-only clone of a live action is the deserialize probe.

Common mappings observed:

```text
SET_COLUMN_VALUE -> Jeenee.DataTypes.DataActionSetColumnValue, Jeenee.DataTypes
ADD_RECORD_TO    -> Jeenee.DataTypes.DataActionAddRowTo, Jeenee.DataTypes
REF_ACTION       -> Jeenee.DataTypes.DataActionRef, Jeenee.DataTypes
NAVIGATE_APP     -> Jeenee.DataTypes.DataActionNavigateApp, Jeenee.DataTypes
```

`LINKTOFORM(...)` opens an AppSheet form only on a `NAVIGATE_APP` action. Do not put it in a `NAVIGATE_URL` action. A URL action expects an `http` target. `LINKTOFORM` in that action does not open the form, and the button appears to do nothing. Clone a working `NAVIGATE_APP` action, not the Google Forms URL action, and do not copy `LaunchExternal` onto the app-navigation definition.

### Clone objects with fresh IDs
When cloning actions, slices, bots, events, processes, datasets, or schemas, do not reuse cloned identity fields such as:

```text
Id
ComponentId
ExecutionId
```

Generate fresh values or remove/recompute fields according to the shape of similar objects. Duplicate cloned IDs can make AppSheet merge, overwrite, or reject objects unpredictably.

### Validate save results by reloading, not just by response code
After `/api/saveapp` returns success, reload the app and verify:

```text
IsValid == true
ErrorCount == 0
Severity0Errors == 0
```

Also inspect the exact objects patched or created. For risky changes, run the local structural audit multiple times or with independent predicates before promotion.

A save attempt may leave the live app advanced even if the client sees an HTTP error/exception, a foreground command timeout, or a later retry returns a version-conflict message such as “someone has already created version X”. When this happens, immediately reload `/api/loadApp/<app_id>` before retrying or rolling back; if the intended JSON path, compiled expression, `IsValid`, and `IsRunnable` are correct, treat the first save as having succeeded and continue with stable-promotion verification. If the script wrote `save_response.json` before the timeout, inspect that artifact, but prefer fresh `loadApp` verification over assuming failure. Save scripts should persist response metadata/body before `raise_for_status()` so HTTP 400/409 evidence is not lost; if a script failed before writing that artifact, do a fresh live `loadApp` readback before deciding whether to retry.

When modifying an existing action assignment list, patch `ActionSettings` as the source of truth and keep the typed `ActionDefinition` mirror in sync. A save can return `Success: true` and advance the version while silently dropping an assignment on reload if the new assignment exists only in `ActionDefinition.Assignments` but not in JSON-decoded `ActionSettings.Assignments`.

### If `IsRunnable` remains false with no errors, resave before rollback
A successful `/api/saveapp` can leave the loaded app at:

```text
IsValid: true
ErrorCount: 0
Severity0Errors: 0
IsDeployable: true
IsRunnable: false
```

If the before snapshot had the same benign invalid nodes and `appErrors.Errors` is empty, first try re-saving the same loaded app JSON and then reload again. In the ActivityLog repair session, a same-payload resave advanced the version and restored:

```text
IsRunnable: true
```

Do not immediately rollback solely because `IsRunnable` is temporarily false when there are no validation errors; verify via reload and resave once.

### Promotion gate
Only promote stable after reload confirms:

```text
IsRunnable == true
IsValid == true
ErrorCount == 0
Severity0Errors == 0
```

Do not call `SetStableVersion` on a version whose consistency check has severity-0 errors or `IsRunnable` false. Users receive the stable version when percent-on-latest is 0. AppSheet does not launch that version, so every user is blocked. The editor can still open because `IsValid` can stay true. When users report they cannot open the app, read `IsRunnable`, `Severity0Errors`, and `StableVersion` before treating editor access as proof the deployed app works.

`loadApp?version=<old>` returns the current `StableVersion`, not the stable version at the time of that save. Use the periodic definition-history snapshots for the stable version and `IsRunnable` at that time.

Before promotion, compare the intended latest editor version against the current stable snapshot and separate real definition/config changes from AppSheet's volatile compiled/cache fields (`ExprLookup`, `InternalQualifier`, `ColumnStats`, compiled `*_AppEval`, `ColumnsReferenced`, `TablesReferenced`, `LocaleName`, timestamps/version counters). If the user asks what unpublished changes exist, report the meaningful changes by section (actions, tables/datasets, schemas/columns, slices, views, format rules, bots/events/processes/tasks), not raw cache churn.

### Bot event table and process input
The event table and the process input table must be the same. The process step must run an action of that table, not an action of a referenced parent table. AppSheet then reports `Action '...' cannot be used in this process` and `The table of event and the input of the process must be the same`. Both are severity 0 and set `IsRunnable` false. To repair, set the process `InputSchemaName` to the event table schema and point the step at the same-table action. A save regenerates the process state table from the new input schema. Do not hand-edit those columns first. A referenced-row action belongs inside the same-table ref action, not as the process step.

Then call the stable-version endpoint, poll `/api/loadApp`, and verify:

```text
StableVersion == Version
```

If `/Manage/SetStableVersion` returns HTTP 200 with `Success: false` and `ErrorDescription: "This feature is only available as part of an Enterprise plan"`, retry with the admin/editor Chromium cookie profile used by the proven AppSheet export/patch scripts (for example `workspace/browser-profiles/tailscale-login/Default/Cookies`) before declaring the promotion blocked. Verify the loaded payload role/owner info and final `StableVersion == Version` after the admin retry.

Observed endpoint quirk: a payload using `version=<editor_version>` may return the Enterprise-plan error, while a payload using `stableVersion=<editor_version>` can return `Success: true`. Do **not** treat that response alone as proof of promotion. An unversioned `/api/loadApp` can keep a stale previous `StableVersion`, or `null`, for a short time after `Success: true`. Load the named target version as well. Claim promotion only when a later unversioned load shows `StableVersion` equal to that target and the stable object contains the change. Do not post a second definition save only because the first readback lagged.

After a successful stable promotion, run the JSON-first definition sync again, verify the local raw definition shows matching `Version`/`StableVersion` plus the intended object state, and commit/push only the relevant definition snapshot files unless the user asked otherwise.

### Column requirement edits
`IsRequired=false` does not make a field optional when `TypeAuxData.Required_If` is set. To remove a requirement, set that `Required_If` to JSON null on every schema attribute that carries the exact old formula, including process-output schema clones. Those clones keep the old rule if you patch only the source table schema. Clear that attribute's `ExprLookup` and `InternalQualifier.ExpressionLookup` so the compiled expression does not restore the old formula. Do not change `Show_If`, display name, or type unless asked.

A single `/api/saveapp` can advance `Version` by more than 1. Read the reloaded version. Do not assume `+1` or retry the same payload because the number skipped.

Before promotion, if latest and stable version numbers differ, fingerprint column `Type`, `IsRequired`, `Required_If`, `Show_If`, and `Valid_If`, plus action, bot, and slice names. Identical fingerprints are not an unpublished column blocker. Do not promote when those names differ for an unrelated change.

After the stable object proves the requirement is gone, update any PD One digest or monitor that still lists a blank value of that column as incomplete. Keep informational display of the field.

To allow blank for one case type only, set `Required_If` so that type is excluded. Do not set `IsRequired` false on a shared column — other types still need the value. If `LINKTOFORM` already writes that column, remove that input, or the action value overrides a blank initial value. If the action does not write the column and the form still opens with a value, add an explicit blank literal in `NavigateTarget` (`"Column", ""`). A column `InitialValue` whose formula always returns `""` is stripped on save and does not clear the field.

### Form-only visibility and attachments
Hide translation twin columns on one form by excluding that view in `Show_If`. Do not delete the columns and do not hide them on every form of the shared table. A new required Yes/No on a shared table uses the same type-scoped `Required_If`, or other case types cannot save.

A form stores column order twice: `ViewDefinition.ColumnOrder` and the JSON string `Settings.ColumnOrder`. Patch both. A save that changes only `ViewDefinition` is reverted on reload because the compiler writes `Settings` back. After save, reload and require the two lists to match before claiming the form changed. `Show_If` can hide a listed column, but the column stays in the form list until both stores drop it.

Form events are stored the same way: `ViewDefinition.Events` and the JSON string `Settings.Events`. Patch both, then reload and require the event action names to match before claiming the form event changed.

`LINKTOFORM` cannot create child attachment rows. The new parent key does not exist until save. Put the existing child inline, such as `Related Case_Attachments`, into both column-order stores so the user can add files. Do not add a new virtual Ref list just to show another table's images. That column can be rejected and will be absent on reload even when `Version` advanced. Copy existing parent files only after that key exists, and only claim the copy if the reloaded definition contains it. An Enum parent key cannot dereference image files; a Ref can.

To put a short source description into the title instead of the long description, gate both `LINKTOFORM` inputs on length. Pass the source text to Title only when it is not blank and `LEN` is under the title `MaxLength` (this Case title max is 60, so the gate is 50). In that branch pass `""` for Description, or the short text stays in both fields. A blank source must not replace the default title. When the source is at or over the gate, keep the short title and pass the source text to Description.

A type-scoped `Valid_If` or column `Description` belongs in `TypeAuxData`. Reload can strip the attribute-level field and keep the aux formula. Scope it with `OR([Type] <> "Type Name", ...)` so other types still save. The Google Forms API does not return paragraph length validation. Use the minimum written in the question description, and do not invent a maximum the API did not return.

### Menu views and group-by
Do not set cloned slice or view `*Evaluatable` fields to JSON null. `/api/saveapp` then returns `Unable to deserialize app.` Clone the live object, edit `FilterCondition`, `ShowIf`, `GroupBy`, and `ColumnOrder` in place, and leave the compiled evaluatable for the compiler to rebuild. Patch both `ViewDefinition` and the `Settings` JSON string.

A menu list copied from `Case_My` stays hidden until both of these exist:

- a Lookup row with `Category` `Views`, a non-blank `Sub-Category` menu group, `Viewable Roles`, and bilingual `en` / `zh-tw`;
- the view id in the user's Appsheet Navigation Bar or Appsheet Menu Items, because `ShowIf` requires that list plus a role intersection with `Viewable Roles`.

Name the list `Case_<Type>_All`, not the name of an existing special form. Clone the detail and form views onto the new slice, or row select has no target. Do not reuse `Case_MoldRepair_Form` for the list form.

Do not `GroupBy` a Ref `EnumList` when the requester asked for a related number. The group header shows the Ref label, which on molds is `Friendly Name`, not `模具編號`. Add a virtual Text column, `CONCATENATE([Molds][模具編號])`, and fall back to `CONCATENATE([Molds])` when that column is blank. Group by that text column. A row with more than one mold stays in one combined group. Do not use `TEXT()` to join the list. `TEXT()` in this app formats a date.

### Catalog child-row actions
Do not clone an add-row action that sets the parent key to `MAXROW(parent table, timestamp column)`. That expression binds every new child to the latest parent row, not the row that invoked the action. Pass the parent key as `[_INPUT]` from the referencing action's `InputAssignments`, and confirm the referenced action declares that input name before save. Do not save the action when the caller input shape is not in the loaded definition.

An `ADD_RECORD_TO` action in this app drops a newly attached `Inputs` array on save, even when the input is an exact clone of a working `SET_COLUMN_VALUE` input. Setting `InputParametersUsed` to a list can make `/api/saveapp` return `Unable to deserialize app.` If reload shows `Inputs` empty, remove every `[_INPUT]` reference before the next save. An `[_INPUT]` reference without a declared input leaves `IsRunnable` false. When the input cannot persist, bind the parent key with `MAXROW` filtered by the source row's parent key and the current user. Do not use an unfiltered `MAXROW`. Gate the caller so it runs only when the saved row is that same filtered row, so an edit of an older parent does not copy onto a newer parent.

Ref-action `InputAssignments` items are `{InputName, InputValue}`. `ColumnToEdit` / `NewColumnValue` is the add-row assignment shape. Those keys on a ref action are rewritten to null `InputName` / `InputValue` on save. Do not clone a `SET_COLUMN_VALUE` `Inputs` entry onto `ADD_RECORD_TO` to invent a missing input. The compiler drops it on reload, the assignment still says `[_INPUT].[Name]`, and `IsRunnable` stays false. That is not the benign no-error `IsRunnable` case. Do not resave and promote. Do not set `InputParametersUsed` to a name list to force the input to stick. That payload can fail deserialize.

### Hidden case type
When the requester wants the definition built but not usable, do not add the new value to the type column `Valid_If`, and keep new views `ShowIf` FALSE. To open that type from a button without adding a Lookup row, add a ref-position form and set `Valid_If` so it returns `LIST("New Type")` only when `CONTEXT("View")` is that form or the current value is already that type. Write form column order anyway. Do not enable the new notification tasks. Do not replace a working order-number initial value with `TEXT(COUNT(...))` to force a daily sequence: `TEXT()` in this app formats a date, not a count, so that formula fails validation.

### Closed lists
Do not invent `Valid_If` enum values from a blank sample of a related sheet column. A blank difficulty column is not a value list.

### Artifact handling
Save before/patched/final app JSON and compact verification summaries under a task-specific exports directory. Raw `loadApp` JSON can be tens of MB and may be ignored from git; keep a small `final_verification_summary.json` or equivalent for quick review.

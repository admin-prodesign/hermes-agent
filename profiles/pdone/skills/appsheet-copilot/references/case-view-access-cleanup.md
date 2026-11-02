# AppSheet Case View Access Cleanup

Use this reference when reactivating/deprecating old Case views, cleaning `HR_Employees_AppSheet_Settings[Appsheet Views Access]`, or migrating view visibility from per-person view tokens to role/notification-group grants in `Lookup[Viewable Roles]`.

## When this applies

- The user asks which duplicated/stale Case view tokens can be removed from `HR_E_A_S`.
- Old split views such as completed/uncompleted Tech Dev, Facilities Repair, or IT need to be re-enabled.
- `Lookup[Viewable Roles]` must become the canonical gate for view visibility instead of per-person `Appsheet Views Access` tokens.
- Performance is a concern because settings/security expressions are reading too much from `HR_Employees` or broad per-person token lists.

## Safe sequence

1. Fresh-load the deployed app definition from `/api/loadApp/<app_id>` and use raw JSON as the source of truth for views, menus, ShowIfs, schemas, and key metadata.
2. Read live data for:
   - `Lookup` rows for the target view tokens.
   - `HR_Employees_AppSheet_Settings` rows that contain those tokens in `Appsheet Views Access`.
   - Optional `HR_Employees` join only for labels/cohort review; do not make `HR_Employees` the canonical settings source.
3. Classify each target view token before deleting anything:
   - **Reactivate/update first:** the view should be live again but `Lookup[Active] = N` or `Viewable Roles` is wrong.
   - **Migrate ShowIf first:** current `Presentation.Controls[].ShowIf` still checks `Current User Settings[Appsheet Views Access]`.
   - **Stale cleanup:** `Lookup[Active] = N`, no current `Presentation.Controls` entry, and no current `Presentation.MenuEntries` entry.
4. For views that should be visible by role/group, update `Lookup` first:
   - Set `Lookup[Active] = Y` when re-enabling.
   - Set `Lookup[Viewable Roles]` to the intended role/group token set.
   - Verify EnumList values as sets because AppSheet may reorder the stored comma-separated string.
5. If direct Data API edits to `Lookup[Viewable Roles]` reject valid notification-group tokens, use the bounded valid-if workaround from `references/hr-eas-settings-canonicalization.md`; restore the original valid-if before stable promotion.
6. Only after view activation/roles/show-if are correct, remove stale or superseded tokens from `HR_E_A_S[Appsheet Views Access]`.
7. Verify final state with a fresh read:
   - latest app `Version`
   - `StableVersion == Version` if promoted
   - `Lookup[Active]` for each target view
   - `Lookup[Viewable Roles]` set equals requested set
   - `Lookup[Viewable Roles].TypeAuxData.Valid_If` restored
   - count of `HR_E_A_S` rows still containing removed stale tokens is zero

## Known token mappings / examples

- Tech Dev old split views can be granted by set: `{Team_RnD, Team_SeniorStaff, Team_Molding_Staff}` when Andy asks for R&D, Senior Staff, and Mold Project/Molding Staff access.
- Facilities Repair old split views can be granted by set: `{Team_Facilities, Team_SeniorStaff}`.
- `Case_IT_Uncompleted` may already have `Team_IT`; preserve it unless the user asks to broaden access.

Confirm token names against live `Lookup`/dropdown rows before writing. Do not invent new role tokens from display labels.

## Reporting pattern

Keep the chat report compact and verification-focused:

- latest/stable version
- each changed view with `Active` and `Viewable Roles`
- stale-token cleanup count (`0` remaining when complete)
- any restored temporary editor setting, especially `Lookup[Viewable Roles]` valid-if
- artifact directory if one was written

Avoid long per-person dumps unless Andy explicitly asks; grouped counts and exact changed tokens are usually enough.

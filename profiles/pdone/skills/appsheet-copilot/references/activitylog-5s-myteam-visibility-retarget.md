# ActivityLog 5S MyTeam visibility retarget

Use with `appsheet-copilot` when users report that AppSheet 5S records show other people's records, especially around the `ActivityLog_5S_MyTeam` view.

## Incident pattern

A live visibility leak can be caused by the **view** being wired to the wrong slice, even when a correctly named slice already exists.

Observed pattern:

- View/control: `Presentation.Controls[]` item with `Name = "ActivityLog_5S_MyTeam"`
- Incorrect target: `TableOrFolderName = "ActivityLog_5S_Slice"`
- Correct target: `TableOrFolderName = "ActivityLog_5S_MyTeam"`
- Menu entry may still look correct because `Presentation.MenuEntries[]` uses `ViewName = "ActivityLog_5S_MyTeam"`; the important field is the matching control's `TableOrFolderName`.

`ActivityLog_5S_Slice` can be a broad slice such as 5S + blank parent + active creator. It is not necessarily current-user scoped. A separate `ActivityLog_5S_MyTeam` slice may contain the intended own/team filter.

## Read-only investigation recipe

1. Load fresh `/api/loadApp/<app_id>` JSON.
2. Inspect:
   - `Presentation.Controls[]` where `Name == "ActivityLog_5S_MyTeam"`
   - `Presentation.MenuEntries[]` where `ViewName == "ActivityLog_5S_MyTeam"`
   - `AppData.TableSlices[]` for `ActivityLog_5S_Slice` and `ActivityLog_5S_MyTeam`
3. Confirm whether the control's `TableOrFolderName` points to the broad slice.
4. For runtime proof, use AppSheet Data API `Find` with `RunAsUserEmail` for a normal active 5S user and compare creator IDs:
   - Query the broad `ActivityLog_5S_Slice`; if it returns many distinct `Created By` values, it proves the leak path.
   - Query `ActivityLog_5S_MyTeam`; expected result should be own/team only. If the requirement is strictly own-only, verify there are no other-created rows.

Do not print employee emails in user-facing output; report person IDs/counts only unless explicitly approved.

## Patch recipe

For the bounded fix requested by Andy/admin:

1. Use the admin AppSheet editor cookie profile when saving/promoting:
   `/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace/browser-profiles/tailscale-login/Default/Cookies`
2. Fetch fresh `/api/loadApp` immediately before patching.
3. Mutate only the target control:
   ```json
   Presentation.Controls[Name == "ActivityLog_5S_MyTeam"].TableOrFolderName:
     "ActivityLog_5S_Slice" -> "ActivityLog_5S_MyTeam"
   ```
4. Save through `/api/saveapp` with `validate=true`.
5. Read back fresh latest and verify:
   - `IsValid == true`
   - `IsRunnable == true`
   - `IsDeployable == true`
   - target control has `TableOrFolderName = "ActivityLog_5S_MyTeam"`
6. Promote the saved version using `Manage/SetStableVersion` with `percentOnLatestVersion=0`.
7. Read back both latest and explicit stable version; do not claim completion until the stable-version object contains the corrected `TableOrFolderName`.
8. Refresh the local definition sync so future investigations do not use stale JSON.
9. Re-run the original run-as smoke test against `ActivityLog_5S_MyTeam` and report other-created-row count.

## Important follow-up risk

If a newer physical table such as `ActivityLog_5S` exists and is empty, it may not be the current leak source. Still inspect its `DataFilter` before any backfill/exposure. Do not expose or backfill physical `ActivityLog_5S` until explicit owner/team/admin visibility rules are defined and verified.

## Reporting receipt

Include:

- before/after `TableOrFolderName`
- saved version and promoted stable version
- `IsValid` / `IsRunnable` / `IsDeployable` readback
- explicit stable-version readback proof
- local receipt path
- run-as smoke-test result (`other_created_rows = 0` or explain intended team visibility)
- note that no gateway restart was required

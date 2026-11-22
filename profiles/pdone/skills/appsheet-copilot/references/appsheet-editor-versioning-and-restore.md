# AppSheet editor versioning and restore pitfalls

Use this note for Pro-Design AppSheet editor-definition saves, restores, and major-version work.

## Pro-Design version convention

Before any `/api/saveapp` change that intentionally creates a major AppSheet editor version, verify and use the established Pro-Design format:

```text
YY.MMDD00
```

Example for 2026-06-18:

```text
26.061800
```

Do **not** invent semantic-style versions such as `27.000001` unless Andy explicitly directs a version-scheme change. If the user says “major new version,” interpret it as the Pro-Design `YY.MMDD00` scheme and verify with `date` plus current `loadApp` version history before saving.

## Restore behavior after a wrong version

AppSheet version restore is content restore, not version-number rewind.

Observed on the Pro-Design app:

1. Latest editor version had mistakenly advanced to `27.x`.
2. Historical version `26.061507` was loaded with:
   - `GET /api/loadApp/<appName>?version=26.061507&checkConsistency=true&useUpdatedWarningText=false`
   - response included `restorable: true`.
3. Official UI path was used:
   - `Manage > Versions > Version History`
   - open/read-only historical version
   - click `Restore (make this version current)`
   - confirm `Make this version current`
4. The design content reverted, but AppSheet created a new monotonic `27.x` latest editor version instead of returning to `26.x`.

Therefore, once a bad high version number is saved, restoring an older version does **not** allow saving the next change as the old lower `YY.MMDD00` value. Stop and report the limitation rather than repeatedly saving more wrong versions.

## Safe workflow for future major AppSheet definition changes

1. Load `appsheet-copilot` and relevant references.
2. Fresh readback:
   - current `Version`
   - `StableVersion`
   - `IsValid`
   - `IsRunnable`
3. Compute target major version using UTC date unless Andy specifies otherwise:
   - `date -u +%y.%m%d00`
4. Confirm the target is greater than current editor version and matches the established scheme.
5. Patch app JSON and set `app.Version` to the target **before** the first save.
6. Save once; if `/api/saveapp` streams/times out, poll fresh `/api/loadApp` before retrying.
7. If a 409 conflict occurs, rebase onto the returned/current app payload and preserve the target version only if it is still monotonic and valid.
8. Verify by fresh `/api/loadApp`:
   - `Version == target`
   - `StableVersion` unchanged unless explicitly promoting
   - `IsValid == true`
   - `IsRunnable == true`
   - intended tables/views/actions/bots exist.

## UX/table changes note from 5S split

For physical split work such as `5S` / `5S_Attachments`, clone existing ActivityLog UX settings carefully, but retarget only valid physical-table columns and remove legacy actions or columns that do not exist on the new tables. Verify controls under `Presentation.Controls` and menu entries under `Presentation.MenuEntries`, not `Presentation.Views`.

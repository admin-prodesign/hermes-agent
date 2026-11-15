# Maintenance Session Item Attachments cached-column rollout

Use this when optimizing `Maintenance_Session_Items` sync performance by replacing the expensive reverse-ref virtual column `Maintenance_Session_Items[Related Maintenance_Session_Items_Attachments]` with a physical cached list of `Maintenance_Session_Items_Attachments` keys.

## Trigger / evidence pattern

Reach for this when Performance Analyzer shows any of:

- `Maintenance_Session_Items[Related Maintenance_Session_Items_Attachments]` as a top virtual/computed-column timing sample.
- `Maintenance_Session_Items` table p90 sync timings in the tens of seconds.
- Sync failures with `Maintenance_Session_Items_Attachments` timeout/cache-lock signatures, for example:
  - `Data table 'Maintenance_Session_Items_Attachments' is not accessible due to: Timed out waiting for a resource`
  - `AsyncLocking.AsyncLock+LockTimeoutException`
- User-facing attachment detail/inline views are slow or fail during sync.

## Definition facts to verify first

Before editing, sync/read back the current AppSheet definition and verify the live schema. Do not assume the editor-save is reflected until `loadApp`/definition sync sees it.

Known relationship shape:

- Parent table: `Maintenance_Session_Items`
- Parent key: `MaintenanceSessionItemID`
- Child table: `Maintenance_Session_Items_Attachments`
- Child key: `MaintenanceAttachmentID`
- Child parent Ref column: `MaintenanceSessionID` -> `Maintenance_Session_Items[MaintenanceSessionItemID]`

Important pitfall: the displayed reverse-ref formula may appear as:

```appsheet
REF_ROWS("Maintenance_Session_Items_Attachments", "MaintenanceAttachmentID")
```

Do **not** copy that into cache-maintenance logic. The parent relationship is the child Ref column `MaintenanceSessionID`, not the child key `MaintenanceAttachmentID`.

## Target physical column

Recommended parent physical column:

```text
Maintenance_Session_Items[Maintenance_Session_Items_Attachments_Cached]
```

Type:

```text
EnumList
Base type: Ref
Referenced table: Maintenance_Session_Items_Attachments
Referenced key: MaintenanceAttachmentID
```

The column should be non-virtual, non-required, and hidden/admin/system-managed for normal users.

## Correct rebuild expression

For a parent-row rebuild action on `Maintenance_Session_Items`, use the child Ref column:

```appsheet
SELECT(
  Maintenance_Session_Items_Attachments[MaintenanceAttachmentID],
  [MaintenanceSessionID] = [_THISROW].[MaintenanceSessionItemID]
)
```

or, when accepted for an EnumList Ref target:

```appsheet
FILTER(
  "Maintenance_Session_Items_Attachments",
  [MaintenanceSessionID] = [_THISROW]
)
```

Do not put this expression as an always-reset/app formula on the physical cached column; that recreates sync cost. Use it in targeted parent-row actions/backfills/repair paths.

## Rollout sequence

1. **Verify physical column exists in definition readback.**
   - `IsVirtual=false`
   - `Type=EnumList`
   - base Ref points to `Maintenance_Session_Items_Attachments`
   - referenced key is `MaintenanceAttachmentID`
   - If a user says the column exists but a prior readback did not show it, immediately run a fresh definition sync and inspect durable `latest/latest.json` / `latest/latest_raw_app.json` or `history/<timestamp>.*`; the sync script may print transient `run-*` paths that are later moved/copied.
2. **Hide/admin-scope the physical cache column.** Match the existing IT/admin visibility pattern used by similar cache columns:

   ```appsheet
   OR(
     IN("IT_Manager", Current User Settings[Appsheet Roles]),
     IN("IT_Admin", Current User Settings[Appsheet Roles]),
     IN("Super_Admin", Current User Settings[Appsheet Roles])
   )
   ```

   Apply as `Show_If`; normal users should interact through the related/inline attachment view, not the cached key list.
3. **Create parent cache rebuild action** on `Maintenance_Session_Items`, for example `MSI_Update_Attachments_Cached`, assigning the physical cache column using the correct rebuild expression above. Prefer `Do_Not_Display`; condition may allow `CONTEXT("Host")="Server"` plus IT/admin roles.
4. **Maintain cache on child add/update.** On `Maintenance_Session_Items_Attachments` add/update, run a child-to-parent REF_ACTION:
   - Referenced table: `Maintenance_Session_Items`
   - Referenced rows: `LIST([MaintenanceSessionID])`
   - Referenced action: `MSI_Update_Attachments_Cached`
   - Condition: `ISNOTBLANK([MaintenanceSessionID])`
5. **Handle deletes separately.** Delete paths are easy to miss because the child row is gone after deletion. Use before-image/process state or a queue row that stores the old `MaintenanceSessionID`, then refresh that old parent. A direct delete-triggered REF_ACTION can work when AppSheet preserves the deleted row values; prove it with a real add/delete readback when attachments exist.
6. **Handle reparenting if `MaintenanceSessionID` can change.** Refresh both old and new parents when `[_THISROW_BEFORE].[MaintenanceSessionID] <> [_THISROW_AFTER].[MaintenanceSessionID]`. If direct before/after ref actions are unreliable, enqueue a `ProcessingQueue` row with old/new parent keys.
7. **Backfill in bounded batches.** Start with recent/current maintenance items or parents with recent attachments; compare cached keys against a direct child query before broadening. If the Data API shows zero existing attachment rows with nonblank `MaintenanceSessionID`, record that and skip backfill rather than doing broad writes.
8. **Switch the related VC to the physical cache once maintenance actions are valid.** For low-volume attachment tables, after add/update/delete maintenance is wired and current rows are backfilled/confirmed empty, directly change the compatibility VC to:

   ```appsheet
   [Maintenance_Session_Items_Attachments_Cached]
   ```

   This preserves existing detail/inline views while removing the expensive `REF_ROWS` path. It should no longer contain `REF_ROWS`, `SELECT`, or `FILTER`.
9. **Save/promote with readback.** Use a minimal `/api/saveapp` patch from the freshest `loadApp` JSON, preserve `ActionSettings` and typed `ActionDefinition` mirrors, clone actions/events/processes with fresh IDs, then reload before promotion. Promote only after `IsValid=true`, `IsRunnable=true`, `IsDeployable=true`, and `Severity0Errors=0`; finally verify `StableVersion == Version`.

## Verification checklist

Definition readback:

- Physical cache column exists on `Maintenance_Session_Items` with correct type metadata.
- Cached physical column is hidden/scoped like similar admin-debug cache fields, usually with `Show_If` allowing only `IT_Manager`, `IT_Admin`, and `Super_Admin`:

  ```appsheet
  OR(
    IN("IT_Manager", Current User Settings[Appsheet Roles]),
    IN("IT_Admin", Current User Settings[Appsheet Roles]),
    IN("Super_Admin", Current User Settings[Appsheet Roles])
  )
  ```

- Parent rebuild action exists and uses `[MaintenanceSessionID] = [_THISROW].[MaintenanceSessionItemID]`.
- Compatibility VC formula is a simple dereference of the physical cached column.
- Add/update/delete processes are valid and do not reuse process-scoped action objects in a way AppSheet rejects.
- App flags remain valid/runnable/deployable.
- After save, promote only after reload confirms `IsValid=true`, `IsRunnable=true`, `IsDeployable=true`, and zero severity-0 errors; then re-sync the local definition mirror and verify `Version == StableVersion`.

Runtime proof:

- Sample parent rows with 0, 1, and multiple attachments.
- Add an attachment and verify parent cache gains `MaintenanceAttachmentID`.
- Delete an attachment and verify parent cache removes the key.
- If reparenting is possible, verify old parent loses and new parent gains the key.
- Test as a normal maintenance user under security filters, not only as admin/owner.
- Verify attachment labels do not render as blank phantom refs.
- If there are currently no attachment rows, record that no backfill was needed and at least smoke-test the parent rebuild action on one parent row; still schedule/perform a real add/delete verification when a maintenance attachment exists.

Performance proof:

- Run clean post-promotion sync-only analyzer windows.
- Target: `Maintenance_Session_Items[Related Maintenance_Session_Items_Attachments]` disappears or drops sharply from top VC timings.
- Target: fewer `Maintenance_Session_Items_Attachments` timeout/cache-lock sync failures.
- Separate old-client/stale-version analyzer rows from current `AppTemplateVersion` evidence.

## 2026-06 implementation pattern

A proven live patch used this sequence successfully:

1. Verify latest `loadApp` sees `Maintenance_Session_Items_Attachments_Cached` before patching.
2. Patch `Maintenance_Session_Items_Attachments_Cached` `Show_If` to IT/admin/super-admin only.
3. Create `MSI_Update_Attachments_Cached` on `Maintenance_Session_Items` as a hidden/global `SET_COLUMN_VALUE` action assigning:

   ```appsheet
   SELECT(
     Maintenance_Session_Items_Attachments[MaintenanceAttachmentID],
     [MaintenanceSessionID] = [_THISROW].[MaintenanceSessionItemID]
   )
   ```

4. Create `MSIA_Update_Parent_Attachments_Cache` on `Maintenance_Session_Items_Attachments` as a hidden/global ref action:

   ```appsheet
   Referenced table: Maintenance_Session_Items
   Referenced rows: LIST([MaintenanceSessionID])
   Referenced action: MSI_Update_Attachments_Cached
   Condition: ISNOTBLANK([MaintenanceSessionID])
   ```

5. Add enabled bots/events/processes for child `ADDS_AND_UPDATES` and `DELETES_ONLY`; both run the child-to-parent ref action.
6. Because the actual attachment volume was very low, once the conditional actions existed and backfill check found no current attachment rows, it was safe to directly switch the compatibility VC to:

   ```appsheet
   [Maintenance_Session_Items_Attachments_Cached]
   ```

7. Save via `/api/saveapp` with `validate=true`, reload, promote stable, and re-sync the definition mirror.

Implementation artifact pattern: save before/patched/after app JSON, patch summary, save result, promotion result, promoted verification, and runtime smoke-test output under a task-specific `projects/AppSheet/exports/<topic-date>/` directory. Do not report success from `/api/saveapp` alone; cite fresh reload/stable readback.

## Data API verification notes

- Avoid broad `Find(Maintenance_Session_Items, TRUE)` during live chat; it can be too expensive. Prefer narrow selectors such as `TOP(ORDERBY(Maintenance_Session_Items[MaintenanceSessionItemID], [Timestamp], TRUE), 1)` for a smoke row or known-key `LIST("<key>")` when readback is reliable.
- Some post-action readbacks on this heavy table can time out even when the action call itself succeeds. Record the action HTTP status/result payload, then verify by definition state and later analyzer/runtime evidence rather than looping broad reads.

## Risk notes

- Physical caches become stale unless every add/update/delete/reparent path maintains them.
- Security filters can make cached Ref keys visible as blank/missing for some users; verify with scoped users.
- Broad backfills can create their own sync/automation pressure; batch and read back.
- If the physical column was added in the editor but is absent from `loadApp` readback, stop and fix save/schema-regeneration before planning action wiring.

# ActivityLog attachments cached-column rollout notes

Use this when replacing or supplementing the `Related ActivityLog_Attachments` virtual reverse-ref with the physical `ActivityLog[ActivityLog_Attachments_Cached]` column.

## Durable lessons from rollout

- A physical cache column does **not** self-populate just because its type is `EnumList`/`Ref` or because views point at it. It must be written by an action, initial/reset expression, bot, or backfill.
- Keep the virtual `Related ActivityLog_Attachments = REF_ROWS("ActivityLog_Attachments", "ActivityLogID")` during transition. Use it as the correctness oracle while moving views to the cache.
- For create/delete maintenance, refresh the parent row from the child row with a `REF_ACTION` that calls a parent `SET_COLUMN_VALUE` action.
- Do **not** wire the same process-scoped action object into multiple AppSheet processes. The editor can fail with:

```text
More than one process references action '...': Process A Process B
```

  Clone the action with a distinct `Name` and `ComponentId` for each additional process, then point that process at its clone.
- When editing AppSheet definition JSON, update both parsed and serialized copies where present:
  - action changes: `ActionDefinition` and serialized `ActionSettings`
  - view column order: `ViewDefinition.ColumnOrder` and serialized `Settings` JSON `ColumnOrder`
- A save/readback may show `IsValid=true` while the live editor checker still reports process/action topology errors. If the UI reports an editor error, inspect topology explicitly instead of relying only on top-level validity flags.
- Stable promotion may require the admin/tailscale AppSheet cookie profile even if another profile can save/read. Verify `StableVersion` by `/api/loadApp` readback after promotion.
- If `ActivityLog_Attachments_Cached` is populated with attachment keys but looks blank in the AppSheet Database/editor, check the referenced table's label column before treating it as a cache failure. For `ActivityLog_Attachments`, a blank `Description` label can render a non-empty Ref/EnumList as visually blank; verify by API/readback of raw key values and compare against `Related ActivityLog_Attachments`.
- When validating a recent-row backfill, prefer sampling recent child `ActivityLog_Attachments` rows and reading their parent `ActivityLog` records. Sampling only newest parent `ActivityLog` rows can miss the rows that actually received attachments.

## Recommended rollout sequence

1. Load latest `/api/loadApp` JSON and inspect current schema/actions/processes/views.
2. Ensure parent action on `ActivityLog` exists, for example:

```appsheet
ActivityLog_Update_Cached_Attachments
SET_COLUMN_VALUE / assignments:
ActivityLog_Attachments_Cached = SELECT(
  ActivityLog_Attachments[ActivityLogAttachmentID],
  [ActivityLogID] = [_THISROW].[ActivityLogID]
)
Updater = "20260221"
Last Updated = NOW()
```

3. Ensure child create path calls a child-table `REF_ACTION` with:

```appsheet
ReferencedTable = ActivityLog
ReferencedRows = LIST([ActivityLogID])
ReferencedAction = ActivityLog_Update_Cached_Attachments
```

4. For delete path, create a **separate clone** of the child ref action and wire delete process to the clone.
5. Move target detail views from `Related ActivityLog_Attachments` to `ActivityLog_Attachments_Cached`; keep form views clean if the old related VC was hidden in forms.
6. Backfill bounded recent rows first, comparing cached vs related values before broad backfill.
7. Consider adding column-level initial/reset behavior only after confirming it will not create a new expensive global recalculation path:

```appsheet
Initial value:
SELECT(
  ActivityLog_Attachments[ActivityLogAttachmentID],
  [ActivityLogID] = [_THISROW].[ActivityLogID]
)
```

Use targeted reset/reset-on-edit rather than unconditional resets when possible. The action-based child create/delete refresh is still needed because child changes do not automatically edit the parent row.
8. Verify newest attachment parent rows, not just newest ActivityLog rows. Sample recent `ActivityLog_Attachments`, collect distinct parent `ActivityLogID`s, then read those parent rows and compare:
   - `ActivityLog_Attachments_Cached`
   - `Related ActivityLog_Attachments`
   - `Updater`
   - `Last Updated`
9. Promote stable only after readback confirms topology and data behavior.

## Verification checklist

- `ActivityLog_Attachments_Cached`: `IsVirtual=false`; initial/reset state understood and documented.
- Parent action assignment expression matches the intended SELECT.
- Create and delete processes reference separate child ref actions.
- No process-scoped action object is referenced by more than one process.
- Top-level app flags: `IsValid=true`, `IsRunnable=true`, `IsDeployable=true`, `AppErrors=null`.
- `Version` and `StableVersion` match after promotion if stable rollout is intended.
- Recent parent rows with attachments have cached list equal to related VC list.
- Rows with no attachments are recognized as legitimately blank, not failed cache population.

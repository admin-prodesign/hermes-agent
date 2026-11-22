# ActivityLog attachments cached physical column

Use this note when optimizing an expensive AppSheet reverse-reference virtual column such as `Related ActivityLog_Attachments` into a physical cached column such as `ActivityLog_Attachments_Cached` / short name `AL_A_C`.

## Durable lessons

- Do not rely on `Initial value` + `Reset on edit` alone for a parent cached reverse-reference list when child rows are commonly added after the parent row is created.
  - Initial value only evaluates when the parent row is created, or when reset-on-edit is triggered by an edit of that parent row.
  - If attachments are created after the `ActivityLog` parent, the initial value can be correctly blank at parent creation time.
- Keep a child-row automation path for freshness:
  - On `ActivityLog_Attachments` add/update/delete, run an action/process that updates the parent `ActivityLog` cached physical column.
  - The parent update expression should recompute from child rows, e.g. `SELECT(ActivityLog_Attachments[ActivityLog_AttachmentID], [ActivityLogID] = [_THISROW].[ActivityLogID])` adapted to the actual key/name columns.
- Keep the original virtual column during rollout until all dependent views, slices, actions, and expressions have been audited and migrated.
- For AppSheet Database-backed tables, verify with AppSheet API/app readback as well as the AppSheet Database editor. The database editor can be stale or visually misleading relative to app-layer/API values.
- Backfill in bounded windows:
  1. backfill last week/recent rows first;
  2. verify API readback on sampled rows with and without attachments;
  3. continue older rows in batches to avoid sync/API load spikes.

## Verification pattern

For a row that appears blank in the AppSheet Database editor:

1. Pick an exact parent `ActivityLogID` that should have attachments.
2. Read child `ActivityLog_Attachments` rows where `ActivityLogID = <that id>`.
3. Run the same parent-refresh action/process or API edit used by the rollout for just that parent.
4. Read the parent row back through the AppSheet API/app layer.
5. Compare:
   - physical cached column value;
   - original related virtual column value, if still present;
   - expected child IDs from the child table.

If API/app readback is correct but the AppSheet Database editor still looks blank, treat it as a display/staleness investigation rather than assuming the cache write failed.
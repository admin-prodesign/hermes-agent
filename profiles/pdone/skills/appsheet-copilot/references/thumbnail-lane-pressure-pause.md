# Thumbnail lane pressure and pause boundary

Use when AppSheet Performance Analyzer failures are dominated by thumbnail/noncritical media lanes, especially these exact process names:

- `Process for HeartBeat - PQ - Thumbnail`
- `Process for HeartBeat - PQ - Thumbnail Push`
- `Process for PQ_Thumbnail_Worker`
- `Process for PQ_ThumbnailPush_Worker`

## Read-only workflow

1. Keep this branch separate from sync duration and ActivityLog/attachment add/edit failures. A thumbnail pause may reduce automation pressure, but it is not proof that `ActivityLog`, `ActivityLog_Attachments`, or `getAllTables` sync p90 improved.
2. Use the gate failures-only scan to compute current failure share by the thumbnail target processes.
3. Pull workflow-only all-result Performance Analyzer scans over the same 2-hour window, starting with 15-minute chunks:
   - no syncs/adds/updates/deletes/reports/API/documents;
   - workflows enabled;
   - verify every chunk returned fewer than 1000 endpoint rows before using denominators;
   - if any chunk returns exactly 1000 rows, reject the whole first-pass denominator and rerun the same window with narrower chunks (10 minutes, then 5 minutes if needed); do not mix capped first-pass counts into the final denominator;
   - when the gate window has sub-second bounds but the export endpoint accepts whole seconds, fetch the enclosing whole-second window and post-filter both all-result and failures-only rows back to the exact gate timestamps.
4. Deduplicate by timestamp, operation, table, process, result, and exception head. Compute per-process total/success/failure counts, minutes with failures, failure classes, and AppTemplateVersion distribution.
   - If persisting a redacted denominator artifact, omit scanner stdout/stderr tails and raw compact rows; scanner output can contain row keys, user/client/request IDs, or payload fragments. Store only counts, paths, process names, version buckets, and redacted/classified exception heads.
5. Read the current definition artifact or fresh `/api/loadApp` and name exact objects before recommending a pause.

## Interpretation

If current failure share is dominated by thumbnail drainers and thumbnail is explicitly noncritical/first-to-pause under the governing goal, prefer a bounded pause packet over broad queue rewrites.

For the current Pro-Design pattern, row-only flag pauses are not durable when refresh actions set enabled fields back to TRUE:

- `AppData.DataActions[HeartBeat_Refresh_Thumbnail]` sets `Thumbnail_Enabled = TRUE`.
- `AppData.DataActions[HeartBeat_Refresh_ThumbnailPush]` sets `ThumbnailPush_Enabled = TRUE`.

A minimal durable pause is usually disabling only the worker events:

- `Behavior.AppEvents[HeartBeat - ProcessingQueue - Thumbnail]`
- `Behavior.AppEvents[HeartBeat - ProcessingQueue - Thumbnail 2]`

Preserve enqueue/durability:

- keep `Behavior.AppEvents[ALA_ThumbnailAttachment_New]` enabled;
- keep `Behavior.AppEvents[ALSIA_ThumbnailAttachment_New]` enabled;
- keep enqueue actions intact. In current Pro-Design definitions these may be named `ALA_QueueThumbnailAttachment` / `ALSIA_QueueThumbnailAttachment`; older notes may mention `ALA_EnqueueThumbnailAttachment_New` / `ALSIA_EnqueueThumbnailAttachment_New`. Verify names from the live/current definition before writing an approval packet;
- do not delete or mark `ProcessingQueue` thumbnail rows Done/Retry/Dead as part of a pause.

## Approval packet requirements

Disabling AppEvents is a live AppSheet behavior change. Require approval and include:

- current failure window and denominator counts;
- exact two AppEvents to disable;
- explicit exclusions: no queue mutation, no enqueue disable, no ActivityLog/attachment add-path edits, no sync/security-filter edits, no gateway/permission changes;
- kill switch: re-enable the two events and verify readback;
- rollback: promote the previous stable only if direct event re-enable is insufficient;
- verification: 30-minute, 2-hour, 6-hour, and 24-hour analyzer windows split at the save/promotion timestamp, with thumbnail, priority 0-3 automations, add/edit failures, and sync p90 reported separately.

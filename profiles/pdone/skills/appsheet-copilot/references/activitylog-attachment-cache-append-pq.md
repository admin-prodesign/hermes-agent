# ActivityLog attachment cache append through ProcessingQueue

Use this when optimizing `ActivityLog_Attachments` add-path performance while preserving near-realtime updates to `ActivityLog[ActivityLog_Attachments_Cached]`.

## Problem pattern

A direct add-path parent refresh such as `Action for Updated ActivityLog cached Attachments 2` can call `ActivityLog_Update_Cached_Attachments`, which rebuilds the parent cache with a full expression like:

```appsheet
SELECT(
  ActivityLog_Attachments[ActivityLogAttachmentID],
  [ActivityLogID] = [_THISROW].[ActivityLogID]
)
```

That can make user-facing attachment adds slow and may produce parent-row visibility/read-after-write failures. Do **not** solve this by simply removing near-realtime cache updates; users still expect `ActivityLog_Attachments_Cached` to update shortly after a new attachment.

## Server vs client SELECT (standing constraint)

Interactive parent-row edits may use `ResetOnEdit` + `SELECT()` / `FILTER()` because AppSheet evaluates that Default on the **client** from already-synced rows and submits the EnumList. That is acceptable.

Do **not** let the **server** compute those scans. Avoid:
- HeartBeat / ProcessingQueue / webhook / scheduled bots whose assignments or conditions `SELECT()`/`FILTER()` child tables or queue tables to rebuild a cache
- `ResetOnEdit` Default `SELECT()` firing because a **bot** edited the parent (hourly maintenance, PQ append writing `Last Updated`, generate-items touching the parent). AppSheet has no Host-scoped ResetOnEdit; any parent edit can re-run Default on the server
- PQ workers that `SELECT(ProcessingQueue[SourceRowKey], … Status="Running")` just to recover the child key

Preferred server write is O(1) list math from a key the process already has:

```appsheet
UNIQUE(
  [ActivityLog_Attachments_Cached]
  + LIST([_THISROW-1].[ActivityLogAttachmentID])
)
```

Call that from the **child add process** via `REF_ACTION` / `ReferencedRows = LIST([ActivityLogID])`. If `[_THISROW-1]` is rejected, use action Inputs to pass the child key; do not SELECT it back from ProcessingQueue. Delete path: `[Cached] - LIST([_THISROW-1].[key])`, not a full rebuild.

Bulk webhook inserts with `TriggerDataChangeEvent = false` never reach that add process. Prefer enabling DCE (or putting the same REF_ACTION on the creator process) so each inserted child appends its own key. Do not follow a bulk insert with a parent `FILTER()`/`SELECT()` rebuild.

Keep a full `SELECT()` rebuild only as a rare **manual repair** action, not on HeartBeat/PQ.

## Preferred design

1. Keep old immediate full-rebuild add-path ref actions disabled, e.g. `Condition = FALSE` for legacy actions that call `ActivityLog_Update_Cached_Attachments` from `ActivityLog_Attachments` add.
2. Prefer inline `UNIQUE(cache + LIST(child key))` from the child add process (see above). Use ProcessingQueue only if inline append is proven too slow; if you do enqueue, pass `SourceRowKey` through Inputs/`[_THISROW-1]`, never `SELECT()` it back.
3. Queue row shape:
   - `JobType = "activitylog_attachment_cache_append"`
   - `WorkerLane = "activitylog"`
   - `SourceTable = "ActivityLog_Attachments"`
   - `SourceKeyColumn = "ActivityLogAttachmentID"`
   - `SourceRowKey = [ActivityLogAttachmentID]`
   - store parent key in an available field such as `SourceText_1 = [ActivityLogID]` when AppSheet ref-action inputs are not available or not already used in this app definition.
4. Touch the existing `HeartBeat` row used by the ProcessingQueue worker (for this app, `HeartBeat[ID] = "ProcessingQueue"`) so the `HeartBeat - PQ` bot fires near-realtime.
5. Add a ready slice such as `PQ_ActivityLogAttachmentCacheAppend_Ready` filtering queued/retry rows for this job type/lane.
6. Add a `HeartBeat - PQ` branch that processes one oldest ready append row per heartbeat.
7. Worker flow:
   - set queue row `Running`;
   - ref-action from `ProcessingQueue` to parent `ActivityLog` with `ReferencedRows = LIST([SourceText_1])`;
   - parent action appends the queued attachment key;
   - mark queue `Done` only after the parent cache contains `[SourceRowKey]`;
   - otherwise `Retry`, then `Dead` after bounded retries.

## Parent append expression

When the parent action is executed on `ActivityLog`, append without re-filtering all attachment rows:

```appsheet
UNIQUE(
  [ActivityLog_Attachments_Cached]
  + LIST(<queued ActivityLogAttachmentID>)
)
```

If the app lacks dynamic action inputs, resolve `<queued ActivityLogAttachmentID>` by selecting the currently running append queue row for the current parent, for example by matching `ProcessingQueue[SourceText_1] = [_THISROW].[ActivityLogID]` and `Status = "Running"`.

Also set diagnostic fields if present, e.g. `Updater = "PQ_attachment_cache_append"` and `Last Updated = NOW()`.

## Preserve repair/backstop paths

- Keep hourly maintenance full rebuild (`ActivityLog_Update_Cached_Attachments`) as a reconciliation/backstop.
- Keep delete-path full rebuild/removal behavior. Append-only logic cannot safely remove deleted attachment keys.

## Verification checklist

Definition readback must prove:

- The attachment add process includes translation enqueue, cache-append enqueue, and heartbeat touch.
- The new ready slice and worker actions exist.
- The heartbeat worker contains the append branch.
- Legacy full-rebuild add-path actions remain disabled.
- App is valid/runnable/deployable and stable on the target version.

Runtime proof must be from a fresh current-version client/session:

- Analyzer rows should show `AppTemplateVersion` equal to the promoted version.
- A new `ActivityLog_Attachments` add should enqueue `activitylog_attachment_cache_append`.
- The queue row should transition to `Done`.
- The parent `ActivityLog_Attachments_Cached` should contain the new attachment key.

## Analyzer pitfall

Immediately after promotion, AppSheet exportlogs may still show old client/runtime versions and serialized automation names that no longer match definition readback. Do not treat rows with older `AppTemplateVersion` as proof that the new worker failed or ran. Label them residual/old-client and collect a later clean window from a refreshed client before judging runtime success.

For post-change status reports, split the evidence explicitly:

1. Mixed post-promotion window: useful for seeing whether stale clients are still producing old-path rows or failures, but not headline proof of current behavior.
2. Clean current-version window: filter/count `AppTemplateVersion == <stable>` and report failures, operations, and slow timings separately.
3. Worker proof: if the clean current-version window has no fresh `ActivityLog_Attachments` add, say the worker is not yet runtime-proven; do not claim success just because no errors appeared. Trigger or wait for a refreshed-client attachment add, then verify enqueue -> worker -> parent-cache update -> queue terminal status.

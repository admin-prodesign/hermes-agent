# HeartBeat queue polling cache-lock triage

Use when AppSheet Performance Analyzer / Monitor shows scheduled `HeartBeat` bots taking about 120 seconds, `TaskCanceledException`, `OperationCanceledException`, `AsyncLock.GetAsync`, `GetRootTableDataWithCachingAsync`, `GetSliceDataFromCacheAsync`, or failures inside `VerifyEventConditionAsync` before useful work starts.

## Symptom pattern

Recent evidence from a live Pro-Design pass:

- HeartBeat exportlog rows showed many failures while AppSheet was evaluating event conditions, not while executing the worker action.
- Common stack frames:
  - `AsyncLock.GetAsync`
  - `GetRootTableDataWithCachingAsync`
  - `GetSliceDataFromCacheAsync`
  - `ColumnValuesAsync`
  - `TopFunction.RunAsync`
  - `VerifyEventConditionAsync`
- Top noisy processes included:
  - `Process for HeartBeat_PQ_CaseUpdateParentSync`
  - `Process for HeartBeat_AL_Repair_NG_MissingSessionItems`
  - `Process for HeartBeat_PQ_ActivityLogInit`
  - `Process for HeartBeat_PQ_ActivityLogGenerateItems`
  - thumbnail HeartBeat lanes

Interpretation: the scheduled HeartBeat update is causing many bot event conditions to scan queue/work slices at the same time. AppSheet can block on table/slice cache reads long enough to cancel at the automation timeout. This can happen even after replacing `COUNT(Slice[Key]) > 0` with `ISNOTBLANK(ANY(TOP(Slice[Key], 1)))`, because the slice itself still needs to be loaded.

## Debug workflow

1. Pull recent HeartBeat logs from `/manage/exportlog` with workflows/change-bot rows enabled. Use both failures-only and all rows when comparing before/after.
2. Group by `Properties["Process Name"]`, `Result`, and `Properties["MatchesCondition"]`.
3. If failures have `MatchesCondition` missing/null plus `VerifyEventConditionAsync` in the exception, treat the event condition/slice load as the bottleneck.
4. Inspect current HeartBeat event filters and process branch conditions. Look for:
   - `COUNT(... ) > 0` over slices/tables.
   - `ANY(TOP(Slice[Key], 1))` over expensive slices.
   - conditions referencing ActivityLog repair slices that perform nested `SELECT()`/`COUNT()` checks.
   - many HeartBeat events firing from the same `HeartBeat` row/update.
5. Separate row-action execution failures from event-condition failures. Do not blame the worker action if AppSheet never got past `VerifyEventConditionAsync`.

## Recommended architecture

### 1. Prefer physical queue-state flags over slice scans

Durable fix: stop using HeartBeat event conditions as queue scanners. Add a small physical state surface for lane state, but keep the **HeartBeat event condition itself** as local-row-only as possible.

A dedicated `QueueState` table is still useful as the canonical multi-lane state surface:

```text
QueueStateID              Text, key; same value as Lane
Lane                      Text, label
Enabled                   Yes/No, default TRUE
HasReady                  Yes/No, advisory wake-up flag
FlagUpdatedAtUTC          DateTime
LastWorkerStartedAtUTC    DateTime
LastWorkerFinishedAtUTC   DateTime
LastNoWorkConfirmedAtUTC  DateTime
LastError                 LongText
MaxBatchSize              Number, default 1 for first canary
Notes                     LongText, optional
```

Useful initial lane rows:

```text
case_update_parent_sync
activitylog_init
activitylog_generate_items
thumbnail
thumbnail_push
notify
translate_request
translate_collect
activitylog_ng_missing_session_items_repair
```

However, do **not** assume this HeartBeat condition is cheap enough under contention:

```appsheet
AND(
  TEXT([ID]) = "ProcessingQueue",
  LOOKUP("case_update_parent_sync", "QueueState", "QueueStateID", "Enabled") = TRUE,
  LOOKUP("case_update_parent_sync", "QueueState", "QueueStateID", "HasReady") = TRUE
)
```

Live post-canary logs showed this successfully removed the old `GetSliceDataFromCacheAsync` + `TopFunction.RunAsync` ready-slice scan, but AppSheet still evaluated the cross-table `LOOKUP()` inside `VerifyEventConditionAsync` as `GetRootTableDataWithCachingAsync` + `SelectFunction.RunAsync`, and the HeartBeat event could still time out before useful work started.

For the actual scheduled HeartBeat event condition, prefer direct physical flags on the touched `HeartBeat` row:

```text
Has_CaseUpdateParentSync_Ready
Has_ActivityLogInit_Ready
Has_ActivityLogGenerateItems_Ready
Has_NGMissingSessionItemsRepair_Ready
Has_Thumbnail_Ready
QueueState_UpdatedAt
```

Then make the HeartBeat condition local-row-only:

```appsheet
AND(
  TEXT([ID]) = "ProcessingQueue",
  [Has_CaseUpdateParentSync_Ready] = TRUE
)
```

instead of either the old slice scan:

```appsheet
ISNOTBLANK(ANY(TOP(PQ_CaseUpdateParentSync_Ready[QueueID], 1)))
```

or a cross-table `QueueState` `LOOKUP()` condition.

Maintain the local HeartBeat flags from queue-row create/update bots, bounded repair jobs, or a less frequent steward/refresh process. Keep `QueueState` as the canonical lane-state table if useful, but mirror the wake-up bit onto the HeartBeat row before the scheduled HeartBeat fires.

Pitfall: keep operator kill switches separate from wake-up refresh. A refresh/backstop action may safely recompute `HasReady`, but it should not blindly set `Enabled = TRUE` every tick; otherwise a bounded pressure pause by setting `Enabled = FALSE` will be immediately undone. When pausing a noncritical lane such as thumbnails, verify both the event filters and any periodic refresh actions before relying on a row-level `Enabled` flag.

### 2. Make queue-row events do immediate work

For newly created or updated `ProcessingQueue` rows, run the relevant worker directly from a row-level bot where possible. Keep scheduled HeartBeat as a safety net for:

- retry rows whose `NextAttemptAt` has arrived;
- stale `Running` rows;
- bounded repair/backfill work.

This avoids waiting for a polling cycle and reduces repeated global scans.

### 3. Materialize expensive repair eligibility

Avoid frequent HeartBeat conditions that start from large source tables and compute eligibility with nested `SELECT()`/`COUNT()` expressions. Example: `ActivityLog_NG_MissingSessionItems_RepairReady` can be expensive because it checks `ActivityLog`, session-item existence, active item matching, and existing queue rows.

Preferred pattern:

```text
ActivityLog create/update
→ set physical Needs_SessionItems_Repair / ProcessingStatus
→ enqueue one repair job
→ HeartBeat drains only queued repair jobs
```

### 4. Stagger lanes

If multiple HeartBeat lanes must remain scheduled, split/offset them so one update does not cause all lane conditions to evaluate together:

```text
ProcessingQueue_Case        every 2–5 min
ProcessingQueue_ActivityLog every 2–5 min, offset
ProcessingQueue_Thumbnail   every 5 min, offset
RowCount                    hourly / bounded batch
Repair                      less frequent
```

### 6. Canary one narrow lane first

Start with a narrow, queue-only lane before moving broad repair logic. In the Pro-Design HeartBeat pattern, `case_update_parent_sync` is a good first canary because it is ProcessingQueue-only, has a clear existing worker path, and avoids the higher stale-eligibility risk of `ActivityLog_NG_MissingSessionItems_RepairReady`.

For the first canary:

1. Add `QueueState` and seed the lane rows.
2. Wire only the canary lane to read/update `QueueState[HasReady]`.
3. Keep the old slice-scan HeartBeat path available as fallback until exportlog/readback confirms behavior.
4. Compare before/after exportlog failures for `VerifyEventConditionAsync`, `OperationCanceledException`, and the lane's process success/failure counts.

## Expression cleanup still worth doing

For remaining existence checks, replace full-count checks:

```appsheet
COUNT(SomeReadySlice[QueueID]) > 0
```

with:

```appsheet
ISNOTBLANK(ANY(TOP(SomeReadySlice[QueueID], 1)))
```

But treat this as a first-pass optimization, not the final fix for cache-lock/cancellation patterns.

## Finance/export queue fallback caveat

A queue-backed email/export can appear “stuck on retries” for two separate reasons that must be separated in logs:

1. **Business task failure after the queue worker successfully triggered the source row** — for example, the Case-context email task generated an XLSX attachment but failed because `To`, `CC`, and `BCC` were empty. In that case the queue row stays `Running`/`Retry` because the process never reaches the `Done` action. Fix the business task expression first; do not over-focus on HeartBeat.
2. **HeartBeat fallback evaluation failure** — repeated `TaskCanceledException` / `AsyncLock.GetAsync` / `GetRootTableDataWithCachingAsync` in `VerifyEventConditionAsync` means the fallback event condition or process action is scanning too much queue/table state. This creates noise and missed fallback passes, but it may not be the primary reason the export did not complete.

For newly queued rows, prefer an immediate `ProcessingQueue` row-level bot. Treat HeartBeat as a narrow safety net only. If the immediate worker exists, it is often safe to temporarily disable or simplify the HeartBeat fallback while fixing the task-level failure, especially if HeartBeat is producing many cache-lock failures.

## Reporting guidance

When explaining to Andy/admin users, be explicit:

- “HeartBeat is polling queue/repair slices to decide whether work exists.”
- “The 120s time is often spent evaluating the event condition, before useful work starts.”
- “The durable fix is physical queue-state/event-driven work, not only changing `COUNT()` to `TOP(..., 1)`.”

Do not attribute these failures to unrelated recent feature changes unless definition diff or exportlog evidence ties them to the failing process.
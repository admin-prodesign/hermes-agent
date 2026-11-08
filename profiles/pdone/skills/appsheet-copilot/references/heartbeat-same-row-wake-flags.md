# HeartBeat same-row wake flags for queue workers

Use this when AppSheet scheduled/HeartBeat automation times out in `VerifyEventConditionAsync`, especially after replacing a ready-slice poll with `LOOKUP()`/`SELECT()` against a queue-state table and the logs still show cache/root-table evaluation failures.

## Durable lesson

A HeartBeat event condition should be as close to a local-row boolean check as possible. Even a single-row cross-table `LOOKUP()` can still be evaluated as a root-table scan/select under contention.

Prefer this hot-path shape:

```appsheet
AND(
  TEXT([ID]) = "ProcessingQueue",
  [CaseUpdateParentSync_Enabled] = TRUE,
  [CaseUpdateParentSync_HasReady] = TRUE
)
```

Over these shapes inside the scheduled event condition:

```appsheet
ANY(TOP(PQ_CaseUpdateParentSync_Ready[QueueID], 1))
```

```appsheet
LOOKUP("case_update_parent_sync", "QueueState", "QueueStateID", "HasReady")
```

## Recommended architecture

Keep `QueueState` as the durable lane state/admin table, but mirror only the hot wake-up bits onto the touched `HeartBeat` row.

Example physical columns on `HeartBeat`:

```text
CaseUpdateParentSync_Enabled          Yes/No
CaseUpdateParentSync_HasReady         Yes/No
CaseUpdateParentSync_FlagUpdatedAtUTC DateTime
CaseUpdateParentSync_LastRefreshUTC   DateTime
```

Do **not** make HeartBeat the sole source of truth. It is a wake-up cache.

## Required wiring

Avoid a deadlock where the event condition is false so the process never runs and never refreshes the flag.

For a queue lane:

1. When the enqueue process creates ready work, update both:
   - durable `QueueState.HasReady = TRUE`; and
   - same-row `HeartBeat.<Lane>_HasReady = TRUE`.
2. The HeartBeat event condition reads only same-row `HeartBeat` flags.
3. After the worker/reaper pass, refresh/recompute `QueueState` from real queue state.
4. Mirror the refreshed `QueueState` values back onto the same-row HeartBeat flags.
5. Keep a bounded stale-running repair path: enqueue-only wakeups do not by themselves catch rows that become stale later without any new enqueue.

## Verification pattern

Before rollout:

- Read the current queue reality directly from the backing source: ready count and stale-running count.
- Seed `HeartBeat[ID] = "ProcessingQueue"` with:
  - enabled = true;
  - has-ready = current ready-or-stale truth;
  - timestamps = now.
- Save latest, require valid/runnable/deployable, then promote to stable only with approved admin credentials.
- Fresh-read `/api/loadApp/<appId>` after promotion and verify `StableVersion == Version`.

After rollout, verify **both definition truth and state truth** before saying automatic processing is wired:

1. Fresh `/api/loadApp/<appId>` readback must show the stable version is valid/runnable/deployable and the intended events/actions/slices are present and valid.
2. Pull the live `HeartBeat[ID] = "ProcessingQueue"` row through the **deployed-app** API credentials, not prototype credentials. Check the lane's same-row flags (`<Lane>_Enabled`, `<Lane>_HasReady`, timestamps).
3. Separately read the ready slice or direct queue reality for the lane. If ready `ProcessingQueue` rows exist but `<Lane>_HasReady = FALSE`, the new same-row event condition is correctly idling and the backlog is **not** covered by automatic processing until a refresh/seed/enqueue path sets the flag true.
4. Pull a fresh exportlog window and split evidence by process: same-row events with `MatchesCondition=False` and no failures prove the event condition is cheap/clean; they do **not** prove queued work drained. Look for the worker process or generic PQ process actually matching/running and then verify queue/business-state transition.
5. When the Data API returns empty/blank for a broad ready-slice `Find`, retry with a bounded direct selector such as `TOP(FILTER("ProcessingQueue", ...), 5)` before concluding the slice is empty.

After rollout, pull Performance Analyzer/exportlog rows for the lane and compare signatures:

Bad/old signatures:

```text
VerifyEventConditionAsync + GetSliceDataFromCacheAsync + TopFunction.RunAsync
VerifyEventConditionAsync + GetRootTableDataWithCachingAsync + SelectFunction.RunAsync
```

Desired idle signature:

```text
Operation: Change Bot
Table: HeartBeat
Process: Process for HeartBeat_PQ_<Lane>
Result: Success
MatchesCondition: False
Failures: 0
```

If there is ready work, expect `MatchesCondition=True` and then verify final queue/business state, not just process start.

## 2026-06-12 canary result

For `case_update_parent_sync`, moving from `QueueState` `LOOKUP()` event gating to same-row `HeartBeat` physical flags produced a clean monitored window after stable promotion:

```text
Window: 2026-06-12 07:32:30 -> 07:52:07 UTC
Process: HeartBeat_PQ_CaseUpdateParentSync
Filtered rows: 36
Failures: 0
Matched true: 0
Matched false: 36
Top table: HeartBeat
Top operation: Change Bot
Top failure messages: []
```

This validated that the local-row flag pattern materially improves idle HeartBeat event-condition reliability compared with both ready-slice scans and QueueState `LOOKUP()` gating.

## Post-canary triage pattern: find the next lane, not just the fixed lane

After promoting one same-row HeartBeat canary, immediately run a broad Performance Analyzer/exportlog scan over the post-promotion window. Do **not** assume submit roughness is solved just because the canary lane is clean. Rank failures by `Properties["Process Name"]` and by stack signature.

In the 2026-06-12 follow-up window after the `case_update_parent_sync` same-row flag canary, that lane stayed clean, but the next dominant bottleneck was other HeartBeat event conditions still scanning slices/tables during every HeartBeat update:

```text
65 failures - Process for HeartBeat_AL_Repair_NG_MissingSessionItems
52 failures - Process for HeartBeat_PQ_ActivityLogInit
49 failures - Process for HeartBeat_PQ_ActivityLogGenerateItems
49 failures - Process for HeartBeat - PQ - Thumbnail Push
47 failures - Process for HeartBeat - PQ - Thumbnail
```

Representative bad filters:

```appsheet
AND(
  TEXT([ID]) = "ProcessingQueue",
  ISNOTBLANK(ANY(TOP(PQ_ActivityLog_Init_Ready[QueueID], 1)))
)
```

```appsheet
AND(
  TEXT([ID]) = "ProcessingQueue",
  ISNOTBLANK(ANY(TOP(PQ_ActivityLog_GenerateItems_Ready[QueueID], 1)))
)
```

```appsheet
AND(
  TEXT([ID]) = "ProcessingQueue_Thumbnail",
  COUNT(PQ_Thumbnail_Ready[QueueID]) > 0
)
```

The stack signature remained:

```text
VerifyEventConditionAsync
GetRootTableDataWithCachingAsync / GetSliceDataFromCacheAsync
ColumnSetExpression
TopFunction or COUNT/SELECT
TaskCanceledException
```

When the user reports that AppSheet submissions are still not smooth, prefer converting the lanes closest to the user write path before background-only lanes. For ActivityLog submissions, prioritize `HeartBeat_PQ_ActivityLogInit` and `HeartBeat_PQ_ActivityLogGenerateItems` before thumbnail/repair lanes, because they fire immediately after ActivityLog adds/edits and directly contribute to submit contention.

Suggested column naming pattern for these lanes:

```text
ActivityLogInit_Enabled
ActivityLogInit_HasReady
ActivityLogInit_FlagUpdatedAtUTC
ActivityLogInit_LastRefreshUTC

ActivityLogGenerateItems_Enabled
ActivityLogGenerateItems_HasReady
ActivityLogGenerateItems_FlagUpdatedAtUTC
ActivityLogGenerateItems_LastRefreshUTC
```

Suggested event filters:

```appsheet
AND(
  TEXT([ID]) = "ProcessingQueue",
  [ActivityLogInit_Enabled] = TRUE,
  [ActivityLogInit_HasReady] = TRUE
)
```

```appsheet
AND(
  TEXT([ID]) = "ProcessingQueue",
  [ActivityLogGenerateItems_Enabled] = TRUE,
  [ActivityLogGenerateItems_HasReady] = TRUE
)
```

Roll these out in small lane groups, seed `HeartBeat` from direct `ProcessingQueue` reality, save/promote only after validation, and monitor the broad log window again to confirm both (a) the converted lanes are clean and (b) the next remaining failure cluster is identified.

### Partial-rollout safety: source sheet changed but definition save failed

When adding new physical same-row wake columns, there are two separate write surfaces: the backing Google Sheet columns and the AppSheet definition JSON. Treat them as independently verified steps, not one atomic operation.

Safe sequence for ActivityLog/HeartBeat lane groups:

1. Capture AppSheet version/stable version, valid/runnable/deployable status, and a fresh analyzer/exportlog baseline before edits.
2. Prepare the source sheet helper columns only after recording exact spreadsheet, sheet, inserted column range, headers, and seeded row values.
3. Attempt the AppSheet definition save on a new version, then immediately fresh-read `/api/loadApp/<appId>`.
4. If `/api/saveapp` returns HTTP `400 Bad Request` or no save receipt, do **not** assume the definition partially deployed. Verify the live definition version and target objects directly.
5. If the readback still shows the previous version and missing target columns/process changes, report: source sheet prepared, AppSheet definition unchanged. Pause for explicit direction to retry/fix the definition patch or revert the helper columns before making more write attempts.
6. Record receipts in the wiki/update log with this distinction so future operators do not mistake prepared sheet columns for a deployed AppSheet optimization.

This matters because leaving source-sheet helper columns staged is usually low-risk, but claiming the AppSheet version changed without a fresh definition readback is unsafe. A failed save also means analyzer logs after the attempt are still measuring the old AppSheet definition.

### Emergency fix when source sheet is already ahead of stable schema

If helper columns were already inserted into the backing `HeartBeat` Google Sheet but the AppSheet definition save/promotion failed, Performance Analyzer may shift from the original timeout bottleneck to a production schema mismatch such as:

```text
There is a mismatch in the number of columns between the spreadsheet for HeartBeat and the table schema.
The table has 18 columns but the schema has 10 columns.
```

In that state, stop optimization iteration and do a bounded restore-to-valid fix first:

1. Fresh-read `/api/loadApp` and confirm the current `Version`, `StableVersion`, `IsValid`, `IsRunnable`, and existing `HeartBeat_Schema` attributes.
2. Save a minimal schema-only version that adds the physical columns already present in the sheet. Do **not** combine this emergency fix with broader event-filter/action/process rewiring unless a fresh dry-run has proven that full patch valid.
3. Treat `/api/saveapp` timeouts carefully: the response body can be tens of MB. If the foreground command times out after writing `save_response.json`, inspect that receipt and/or fresh-read `/api/loadApp` before retrying. A timeout after a `200` save response may still have committed the new version.
4. Promote only after readback proves the new version is valid/runnable and the `HeartBeat_Schema` contains the staged columns.
5. Live-test with both:
   - AppSheet Data API `Find` on `HeartBeat` for `ID="ProcessingQueue"`, confirming HTTP `200` and the new fields present; and
   - a post-promotion Performance Analyzer window confirming the previous schema-mismatch failures stopped.
6. Record the revert path explicitly: reverting stable to the old version is not enough if the sheet remains wider. Either keep the new schema version, or revert both stable version and the staged sheet columns together.

This is a restore-to-green step, not the actual performance optimization. After it is stable, apply same-row event-filter/action/process rewiring as a separate version with its own live test.

### Stable-baseline rebase before live approval

When latest is ahead of stable, do a stable-baseline rebase artifact before asking for same-row HeartBeat approval. Use the stable `/api/loadApp` raw app as the baseline, verify the target HeartBeat event/process/schema still match the draft assumptions, and compare the target object list with the latest-vs-stable drift audit. If a proposed wake hook touches an object already changed in unpublished latest (for example `PQ_EnqueueNotify` or a Case/notification action), exclude that hook from the first packet or patch it separately from the stable object so unrelated draft behavior is not promoted accidentally.

For a first low-add-path-risk canary, it can be safer to change only the HeartBeat source/schema columns, local-row event filter, branch conditions, clear/refresh actions, and an existing periodic refresh backstop, while deferring broad enqueue-source wake hooks. Call out the tradeoff explicitly: new rows may wait for the periodic backstop until a later enqueue-hook follow-up, but business-row add paths and unrelated unpublished drift remain untouched.

### Full same-row rewiring save pitfalls

When applying the broader action/event/process rewiring after the schema-only fix, verify the generated AppSheet action metadata before saving or promoting:

- New `REF_ACTION` wake actions cloned from a template may inherit the template's `Table` field. If the wake action condition references `ActivityLog` columns such as `[ActivityLogID]`, force/verify `Table = "ActivityLog"`; otherwise AppSheet may save a valid-but-not-runnable draft with errors such as `Can't find column "ActivityLogID" in table "Case_Updates"` or `Action ... does not exist for table ActivityLog`.
- Multi-column `SET_COLUMN_VALUE` actions should follow the existing AppSheet JSON shape: `$type = Jeenee.DataTypes.DataActionSetColumnValue, Jeenee.DataTypes`, include `Assignments`, and also include `ColumnToEdit`/`NewColumnValue` matching the first assignment. The top-level action metadata must also match the clone family (`TableScope = false`, `ColumnToEdit`, `ColumnAttachment`, and `Value`/`ValueEvaluatable` aligned with the first assignment). Using a guessed plural type or leaving incompatible cloned metadata can make `/api/saveapp` return `Unable to deserialize app`.
- When replacing an `IF_ELSE` wrapper that calls an existing worker process, clone the original `CallProcessNode` rather than inventing a minimal call node. Thumbnail worker calls used `CallMode = LOOKUP` and `Arguments` to pass a selected `QueueID`; dropping those fields makes the saved JSON structurally invalid or changes behavior.
- AppSheet may auto-increment the saved `Version` beyond the requested version and return a very large response; if the foreground command times out, inspect the saved `save_response.json` and fresh-read `/api/loadApp` before retrying. A later `409` can mean the previous save already committed and the local payload is stale, not that the change failed.
- Promotion target should be the fresh-read live `Version`, not the originally requested version. Verify `StableVersion == target` after `SetStableVersion`.
- For the post-promotion analyzer, split at the actual stable-promotion timestamp. A window that spans the save/promote period can still include pre-promotion failures and should not be used as the headline result.

## Backlog blind spot: enqueue-time wake flags need a periodic refresh backstop

Same-row HeartBeat flags solve hot event-condition scans, but they can miss pre-existing backlog rows or rows created before the wake action existed. Do not put the expensive ready-slice scan back into the HeartBeat event condition. Instead:

1. Keep the real-time event condition local-row-only (`<Lane>_Enabled` + `<Lane>_HasReady`).
2. Add/keep an enqueue-time action that sets the same-row `<Lane>_HasReady = TRUE`.
3. Add a native scheduled refresh bot/process (10-min or hourly depending on urgency) that runs on the HeartBeat row that owns those lane columns and recomputes the same-row flags from real queue state. If thumbnail flags live on `HeartBeat[ID]="ProcessingQueue_Thumbnail"`, use a separate periodic event/process for that row; do not attach thumbnail refresh actions to an ActivityLog/ProcessingQueue-only periodic process.
4. Seed the same-row flag once from direct queue reality during rollout so existing backlog starts automatically without manually processing queue rows.
5. Use the same readiness predicate in both refresh and worker selectors. For `NextAttemptAt`, do **not** require it for all statuses: use `OR([Status]="Queued", AND([Status]="Retry", OR(ISBLANK([NextAttemptAt]), [NextAttemptAt] <= NOW(), [NextAttemptAt] <= UTCNOW())))`; otherwise queued rows with old/nonblank `NextAttemptAt` can be hidden.
6. If worker actions use `ReferencedRows = TOP(<ReadySlice>[QueueID], 1)` and the slice/Data API path proves flaky, move the worker/ref-row and refresh expressions to direct `SELECT(ProcessingQueue[QueueID], AND(...ready conditions...))`. This keeps the hot event condition cheap while avoiding a second blind spot where the flag is true but the worker selects no row.
7. After rollout, verify with both sheet readback and AppSheet logs; a saved valid definition is not enough if old backlog flags are still false or workers are timing out after wake-up.

### External flipper option for heavy backlog

If native scheduled refresh bots still add load or clear flags too slowly during a large `ProcessingQueue` backlog, move the flag computation outside AppSheet while keeping the local-row HeartBeat event filters. A safe pattern is a bound Apps Script/time-trigger or bounded local helper that:

1. Reads the `ProcessingQueue` backing sheet directly.
2. Computes only lane-level ready booleans/counts (`activitylog_init`, `activitylog_generate_items`, `activitylog_attachment_cache_append`, `thumbnail_attachment`, `thumbnail_push`).
3. Sends a minimal AppSheet Data API `Edit` to `HeartBeat[ID="ProcessingQueue"]` and/or `HeartBeat[ID="ProcessingQueue_Thumbnail"]` with only `Timestamp`, `<Lane>_Enabled`, `<Lane>_HasReady`, and timestamp fields. This still triggers the local-row AppSheet bots but avoids AppSheet doing the expensive queue scan in the refresh path.
4. Keeps the in-app worker selectors authoritative; the flipper is a wake cache, not a worker.
5. Bounds duplicate cleanup per run and audits it. For duplicate active `ScopedJobKey` groups, mark loser rows `Dead`/superseded rather than deleting, unless the task is specifically duplicate `QueueID` cleanup with row-number verification.
6. Verify by remote script-source readback/hash, queue readback, HeartBeat row readback, and exportlog process/failure counts. A direct Apps Script Execution API call may return `403` for bound projects even when `updateContent` and installed triggers work.

2026-06-14 implementation note: the AppSheet Helper bound Apps Script (`1BtXeg...Q_Iid`) was patched so `callAppSheetHeartbeat_ProcessingQueue*` computes same-row HeartBeat flags from the sheet and marks bounded duplicate active `ScopedJobKey` losers `Dead`. Local fallback script: `/home/prodesign/.hermes/profiles/pdone/scripts/processingqueue_external_heartbeat_flipper.py`.

### Lifecycle reaper for stale `Running` queue rows

Same-row wake flags and external flippers only wake work; they do not guarantee that an AppSheet worker which already set a row to `Running` will always reach `Done`, `Retry`, or `Dead`. When logs show rows becoming `Running` but not finalizing, add a bounded stale-`Running` repair path instead of adding more wakeup machinery.

Safe pattern for `thumbnail_attachment` and similar lanes:

1. Read the queue backing sheet directly. Do not call AppSheet API once per stale row.
2. Target a narrow lane and state, e.g. `JobType="thumbnail_attachment" AND Status="Running"`.
3. Treat rows older than a conservative threshold (for example 15 minutes) as stale.
4. Reset stale rows below the dead threshold to `Retry`, set `NextAttemptAt` a short time in the future, clear/record `StartedAt` as appropriate, and write a specific `LastError` such as `External lifecycle reaper: Running stale for N minutes; resetting to Retry`.
5. Mark rows at/above the attempt threshold `Dead` with `CompletedAt` and `LastError` instead of looping forever.
6. Bound each run (`max_reap_stale`, e.g. 20) and write JSON summaries under `logs/` so the repair is auditable.
7. Run the recurring guard as a quiet script-only cron/no-agent job that emits stdout only when rows were repaired or on failure. Empty stdout should mean no delivery/no noise.
8. Keep this separate from the HeartBeat API flipper path (`--skip-heartbeat`) so the guard does not add more AppSheet automation contention.
9. Document the rollback: pause/remove the cron job first, then revert/remove the local scripts if needed.

Example artifact shape from 2026-06-14:

```text
scripts/processingqueue_external_heartbeat_flipper.py
  --reap-stale-thumbnail-running
  --stale-running-minutes 15
  --retry-delay-minutes 2
  --max-reap-stale 20
  --skip-heartbeat

scripts/processingqueue_thumbnail_lifecycle_reaper.py
  quiet wrapper for cron no_agent=true, every 5m
```

This is a lifecycle safety guard, not a throughput cure. Post-rollout reporting must still split the evidence: direct queue snapshots should show stale `Running` rows returning to `Retry`/`Dead`, while Performance Analyzer may still show AppSheet `OperationCanceledException`/Spanner automation-store contention until the underlying worker/process load is reduced.

### Interpreting a mostly-Queued backlog after external flag flipping

After external HeartBeat flag flipping is installed, a large number of `ProcessingQueue` rows can still remain `Queued` even when the system is not fully stuck. Diagnose with bounded repeated snapshots rather than a single read:

1. Take 3-5 direct backing-sheet snapshots over a few minutes and compare `Done`, `Running`, active totals, and `by_job_status`.
2. Treat rising `Done` plus transient `Running` rows as proof of slow drain, not hard stuck, even if most rows remain `Queued`.
3. Remember many AppSheet queue workers are TOP-1/small-batch: only selected rows briefly become `Running`; most backlog rows naturally remain `Queued` between attempts.
4. If active totals stay flat while `Done` rises, check whether new queue rows are arriving and offsetting progress.
5. Split the backlog by `JobType|Status` and inspect the oldest active rows. Old rows still `Queued` can indicate a worker selector blind spot, priority/order issue, or repeated AppSheet automation failure before older rows are selected.
6. Read the owning `HeartBeat` row flags separately from queue reality. A flag such as `Thumbnail_HasReady=FALSE` while direct queue reality shows ready rows means the lane is being pulsed/cleared and waiting for the next refresh/flipper pass, or the refresh predicate differs from the worker selector.
7. Pull a fresh Performance Analyzer/exportlog window and rank failures by process. If failures are dominated by `OperationCanceledException` / Spanner automation-store reads in HeartBeat or worker processes, the bottleneck is AppSheet automation throughput/contestion, not the external flipper.
8. For old `Queued` rows with nonblank historical `NextAttemptAt`, verify the worker and refresh readiness predicates do not accidentally require `NextAttemptAt` for all statuses. `Queued` should be ready regardless; only `Retry` should be gated by due time.

Report this distinction explicitly: "slow drain" vs "stuck" should be backed by observed row transitions (`Done`/`Running`) and log failure signatures, not by the presence of many `Queued` rows alone.

2026-06-13 ActivityLog fix pattern:
- Added a dedicated `HeartBeat_PQ_ActivityLogAttachmentCacheAppend` local-row flag event/process/bot because the generic `HeartBeat - ProcessingQueue` event only scanned translate/notify/thumbnail job types and ignored `activitylog_attachment_cache_append`.
- Added `ActivityLogAttachmentCacheAppend_*` physical HeartBeat columns and an attachment enqueue wake action.
- Added `Periodic - Refresh ActivityLog PQ HeartBeat Flags` to refresh `ActivityLogInit`, `ActivityLogGenerateItems`, and `ActivityLogAttachmentCacheAppend` flags.
- Replaced `ReferencedRows`/`HasReady` slice lookups for the ActivityLog lanes with direct `SELECT(ProcessingQueue...)` expressions after `PQ_ActivityLog_Init_Ready`/flag refresh proved false while direct sheet queue reality had ready rows.

## Checker/repair lanes: use scheduled refresh plus clear-before-work

Not every HeartBeat lane should be real-time. For background checker lanes such as `Process for HeartBeat_AL_Repair_NG_MissingSessionItems`, prefer moving the expensive readiness scan out of every HeartBeat and into a scheduled/admin refresh while keeping the HeartBeat event condition local-row-only.

Recommended shape:

1. Add physical same-row `HeartBeat` columns, e.g.:

   ```text
   RepairNGMissingSessionItems_Enabled
   RepairNGMissingSessionItems_HasReady
   RepairNGMissingSessionItems_FlagUpdatedAtUTC
   RepairNGMissingSessionItems_LastRefreshUTC
   ```

2. Replace the expensive event filter:

   ```appsheet
   AND(
     TEXT([ID]) = "ProcessingQueue",
     ISNOTBLANK(ANY(TOP(ActivityLog_NG_MissingSessionItems_RepairReady[ActivityLogID], 1)))
   )
   ```

   with local-row flags:

   ```appsheet
   AND(
     TEXT([ID]) = "ProcessingQueue",
     [RepairNGMissingSessionItems_Enabled] = TRUE,
     [RepairNGMissingSessionItems_HasReady] = TRUE
   )
   ```

3. Add a native AppSheet hourly scheduled bot/process to run the expensive readiness scan and set the same-row flags. Hourly native AppSheet automation is usually better than a new Apps Script trigger for low-urgency repair checkers: fewer external failure modes, simpler AppSheet logs, and less background HeartBeat pressure. Only add an Apps Script 15/30-minute trigger if hourly proves operationally too slow.

4. Add a visible/admin ActivityLog repair action for affected records by reusing the existing repair enqueue condition. The button can enqueue the repair work and mark/wake the same-row HeartBeat flag so users/admins do not have to wait for the hourly sweep. Example bilingual display-name pattern:

   ```appsheet
   SWITCH(
     ANY(Current User[Language]),
     "zh-tw", "修復 Session Items",
     "Repair Session Items"
   )
   ```

5. **Important pitfall:** if the hourly/manual refresh sets `<Lane>_HasReady = TRUE`, do not let the real-time HeartBeat process finish by recomputing and re-setting `HasReady = TRUE` while ready rows remain. That creates repeated per-HeartBeat firing. Instead, clear the ready flag before doing the repair enqueue/work, and let only the next hourly/manual refresh set it true again:

   ```text
   HeartBeat_ClearReady_<Lane>
   <existing repair/worker action>
   ```

   The clear action should set:

   ```appsheet
   <Lane>_HasReady = FALSE
   <Lane>_FlagUpdatedAtUTC = UTCNOW()
   ```

6. After rollout, verify both phases:
   - scheduled refresh process succeeds;
   - real-time HeartBeat process shows `Result=Success`, `MatchesCondition=False`, `Failures=0` after the clear-before-work fix.

2026-06-12 validation for `HeartBeat_AL_Repair_NG_MissingSessionItems`: after adding hourly refresh and then fixing the repeated-firing loop by inserting `HeartBeat_ClearReady_RepairNGMissingSessionItems` before the repair action, the post-fix monitor showed:

```text
Window: 2026-06-12 09:41:00 -> 09:58:11 UTC
Process: Process for HeartBeat_AL_Repair_NG_MissingSessionItems
Filtered rows: 31
Failures: 0
Matched true: 0
Matched false: 31
```

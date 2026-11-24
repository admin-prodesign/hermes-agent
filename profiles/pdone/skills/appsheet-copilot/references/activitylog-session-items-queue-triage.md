# ActivityLog Session Items queue triage

Use when users report that `ActivityLog` records (especially NG/reporting-style records) should spawn related `ActivityLog_Session_Items` but the children are missing, delayed, or unreliable.

## What to check

1. Pull fresh AppSheet export logs for the requested window. For multi-day windows, chunk the export (for example 6-hour chunks) because `/manage/exportlog` can return capped/truncated result sets such as 1000 rows.
2. Filter or classify failures for these process names:
   - `Process for HeartBeat_PQ_ActivityLogInit`
   - `Process for HeartBeat_PQ_ActivityLogGenerateItems`
3. Also inspect related worker failures that can block fanout or make symptoms look like missing session items:
   - `Process for HeartBeat - PQ`
   - `Process for HeartBeat - PQ - Thumbnail`
   - `Process for HeartBeat - PQ - Thumbnail Push`
4. Read back live data separately from logs:
   - target parent `ActivityLog` rows in the window/category
   - related `ActivityLog_Session_Items` where `[ActivityLogID]` is in the parent keys
   - cached parent fields such as `ActivityLog_Session_Items_Cached` and `Related ActivityLog_Session_Items`
5. Distinguish **currently missing children** from **intermittent/delayed children that eventually recovered**. Users may have seen real failures even when a later readback shows children exist.

## Failure signatures seen in production

Relevant failures commonly present as AppSheet data/cache read cancellation rather than an obviously wrong condition:

- `System.Threading.Tasks.TaskCanceledException` in `AsyncLock.GetAsync` / `GetRootTableDataWithCachingAsync` / `GetSliceDataFromCacheAsync`.
- `System.OperationCanceledException` while reading AppSheet database/Spanner data.
- `PQ_Run_Init_On_ActivityLog` failed because `ActivityLog_Attachments` was not accessible / rows could not be fetched from AppSheet database.
- `PQ_Run_GenerateItems_On_ActivityLog` failed because `ActivityLog` was not accessible / rows could not be fetched.
- `AL_Group_InitFanout -> AL_Enqueue_GenerateItems` failed because `ActivityLog_Items` or `ActivityLog_Session_Items` was not accessible / rows could not be fetched.
- Queue helper-sheet pressure: errors like `Range (ProcessingQueue!A9782) exceeds grid limits. Max rows: 9778, max columns: 42`, which means AppSheet tried to append beyond the available physical grid.

## Interpretation

- A high count of `ActivityLogInit` / `ActivityLogGenerateItems` failures usually points to AppSheet/AppSheet DB load, cache/read timeouts, or helper-sheet append pressure, not necessarily missing automation wiring.
- `ActivityLogInit` failures can prevent enqueueing the follow-up generate-items job.
- `ActivityLogGenerateItems` failures can prevent child `ActivityLog_Session_Items` creation even after the init job ran.
- If live readback shows children present, report that the current state recovered, but still report the log evidence for intermittent failures.
- For high-priority NG/reporting-style `ActivityLog` rows, do not default to multi-minute retry backoff. Users expect generated session items almost immediately. Prefer near-immediate retries (`NextAttemptAt = UTCNOW()` or a very short delay), bounded attempts/dead handling, and a short-delay reconciliation lane that re-enqueues rows still missing `ActivityLog_Session_Items` after a couple of minutes.
- Keep enqueue-time logic light: avoid child-table anti-joins against `ActivityLog_Session_Items` during the initial `AL_Enqueue_GenerateItems` fanout. Use `ProcessingQueue[ScopedJobKey]` idempotency instead. For normal enqueue, block duplicate jobs in `Queued`, `Running`, `Retry`, and `Done`; for repair enqueue, block only active jobs (`Queued`, `Running`, `Retry`) so an old bad `Done` row does not prevent reconciliation.
- Repair/missing-child checks should use a live child count such as `COUNT(SELECT(ActivityLog_Session_Items[ActivityLogSessionItemID], [ActivityLogID] = [_THISROW].[ActivityLogID])) = 0`, not parent cache fields like `[Related ActivityLog_Session_Items]` when that relationship is backed by a cached enumlist.
- If using `ProcessingQueue[Priority]` for repair/high-priority rows, verify both sides of the priority path: (1) the heartbeat selector must actually order by priority, and (2) the enqueue action for the important parent class must assign the intended high priority. A durable selector such as `ORDERBY(PQ_ActivityLog_GenerateItems_Ready[QueueID], [Priority], FALSE, [CreatedAt], TRUE)` still leaves today's warehouse/NG row stuck if `AL_Enqueue_GenerateItems` or `AL_Repair_Enqueue_GenerateItems` creates it with normal priority `1` behind older priority-1 backlog. For warehouse inspections, inspect the queue row for the specific parent; if it is `Queued` with children missing and `Priority=1`, the immediate bounded repair is to elevate that exact queue row (for example to `99`) and trigger the existing heartbeat sequence, then patch the enqueue assignment so future warehouse inspection generate-items jobs are high priority from creation.
- For `activitylog_generate_items` backlogs, audit queue legitimacy before assuming every queued row should run. The enqueue actions may already check active `ActivityLog_Items` templates, but stale/duplicate queue rows can still block the worker if they already have child `ActivityLog_Session_Items`. Check the effective parent type as `IF(ISBLANK([Sub-Category]), [Category], [Sub-Category])`, compare it to `ActivityLog_Items_Active[Activity Log Type]`, and separately count existing child rows for `[SourceRowKey]`. Add guards in both the ready slice/action path (`PQ_ActivityLog_GenerateItems_Ready` and `PQ_SetRunning_ActivityLogGenerateItems`) and enqueue path: active template count `> 0` and existing child count `= 0`. This prevents no-op queued rows from taking the worker lane ahead of legitimate rows.
- If the heartbeat/action path still returns success-shaped empty results but produces no `ActivityLog_Session_Items`, do not keep looping indefinitely. Use a bounded manual repair: read the target parent, confirm current child count is zero, read active `ActivityLog_Items` for the parent class (for warehouse: `[Activity Log Type] = "ActivityLog_Inspection_Warehouse"`), add one child row per template item through the AppSheet API, then verify the child count and update the parent's `ActivityLog_Session_Items_Cached` with the verified child IDs. Finally mark only the exact queue row `Done` with a clear manual-repair note so the stuck job does not re-run and duplicate children. This is a live operational repair path, not a design substitute; still fix the enqueue/priority/root cause and promote it after readback.
- Before redesigning item/template caching, check for duplicate `ProcessingQueue[QueueID]` values when a ready lane appears idle or a row remains `Queued` after a matching job ran. Duplicate keys in a Google Sheets-backed queue are usually duplicate physical append payloads, not real `UNIQUEID()` collisions. A pair such as the same `QueueID`/`ScopedJobKey` where one row is `Done` and another is still `Queued` can make ref actions by `QueueID` ambiguous and leave the ready slice blocked. Use `references/processingqueue-duplicate-key-triage.md` for the sheet-direct inspection and quarantine pattern.

## Deterministic 3-day monitoring after a design change

When asked to watch whether ActivityLog session-item changes improved reliability/performance, install a deterministic no-agent monitor instead of an LLM-driven scheduled summary. The useful pattern from the NG repair rollout was:

- Schedule `cronjob(no_agent=True)` for a bounded window such as every 30 minutes × 144 runs (3 days), and verify with `cronjob(action="list")` plus one forced run.
- Use a shell wrapper under `~/.hermes/scripts/` with `flock` and absolute paths; the scheduled `script` value should be the relative wrapper filename.
- Pull fresh AppSheet `/manage/exportlog` data each tick for the recent window, using the AppSheet migration `exportlog.py` helper and the AppSheet venv when available. Store raw JSON evidence under `~/.hermes/state/.../exportlogs/` and append compact JSONL run summaries under `~/.hermes/logs/.../runs.jsonl`.
- Report only when a relevant issue appears, on the first/baseline run, or on a periodic cadence (for example every 12 runs / 6 hours). Keep clean intermediate runs silent to avoid channel spam.
- Track these exact process names for the NG/session-items class of incidents:
  - `Process for HeartBeat_PQ_ActivityLogInit`
  - `Process for HeartBeat_PQ_ActivityLogGenerateItems`
  - `Process for HeartBeat_AL_Repair_NG_MissingSessionItems`
- Include the app version seen in logs; after the 2026-05-19 rollout the expected stable version was `26.051902`, so future monitors should set their expected version from the actual promoted version, not hardcode this historical value.
- Classify success/failure counts, condition match counts, ActivityLog REST events, relevant keyword hits, and failure samples. Cool down repeated issue signatures so AppSheet DB/cache instability does not page every 30 minutes for the same stack trace.
- The first post-change baseline may still show many AppSheet DB/table-access failures. Treat this as baseline evidence and continue observing trends rather than declaring the design failed from one noisy sample.

Baseline signatures observed immediately after the NG repair rollout included failures in `HeartBeat_AL_Repair_NG_MissingSessionItems` caused by AppSheet DB fetch/access errors for `ActivityLog`, `ActivityLog_Items`, and `ActivityLog_Session_Items`, plus `TaskCanceledException` during AppSheet async locks/cache reads. These are important because they show the repair safety net is being triggered but may itself be exposed to the same AppSheet table-access instability.

## Report format

Keep the user-facing answer operational:

- Window checked and timezone.
- Fresh log source used (`/manage/exportlog`, not stale local artifacts).
- Counts by relevant process.
- Top failure signatures with examples, not full stack traces unless asked.
- Current readback state: number of parent rows, number with/without child rows, child counts by parent.
- Suggested next fix path: reduce worker read footprint, add retry/dead monitoring for `activitylog_init` / `activitylog_generate_items`, add reconciliation for parents whose session-items cache remains blank/short after N minutes, and keep helper-sheet physical row buffer above append demand.

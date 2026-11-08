# ProcessingQueue race-condition investigation notes (2026-05-18)

Use as an example of evidence to collect when AppSheet helper queues show partial rows, duplicate logical jobs, or unexpected blanking.

## Observed restored queue state

After restoring `AppSheet Helper > ProcessingQueue`, direct Google Sheets readback showed:

- physical rows including header: 7,848
- data rows: 7,847
- nonblank rows: 7,839
- `Case_Updates` queue rows: 7,712
- statuses: `Queued` 7,665; `Done` 81; `Retry` 69; `Running` 21; blank 9; `Dead` 2
- job types: `translate_request` 7,679; `translate_collect` 116; blank 22; `activitylog_init` 15; `thumbnail_attachment` 13; `notify` 2

Deployed AppSheet API readback saw fewer normal rows:

- AppSheet-visible rows: 7,825
- `Case_Updates`: 7,712
- statuses: `Queued` 7,658; `Done` 80; `Retry` 65; `Running` 20; `Dead` 2

Interpretation: the physical sheet contained malformed/blank-key rows not exposed as normal AppSheet rows because `QueueID` is the key.

## Malformed signatures found

- 14 rows missing core fields
- 13 status-only rows
- 11 invalid active rows
- 14 duplicate active `ScopedJobKey` groups, covering 30 physical rows
- 4 duplicate `QueueID` groups, covering 8 physical rows

Suspicious malformed row shape:

- blank `QueueID`
- blank `SourceTable`
- blank `SourceRowKey`
- blank `JobType`
- blank `ScopedJobKey`
- blank `CreatedAt`
- populated `Status`, `StartedAt`, `FinishedAt`, `NextAttemptAt`, or `RetryCount`

Strong duplicate example:

- same `QueueID`: `18f74c69`
- same `ScopedJobKey`: `Case_Updates|CU-FACLEG-45116-98092-R3850-001|translation|translate_collect`
- two physical rows: one `Queued`, one `Running`
- same created time and same GoogleTranslate IDs

This supports a duplicate-claim or duplicate-physical-row failure mode.

## Definition risks to check

In the inspected definition:

- `QueueID` was the key with `UNIQUEID()` default.
- `ScopedJobKey` was not the key and not unique-enforced.
- core columns were not required: `SourceTable`, `SourceKeyColumn`, `SourceRowKey`, `JobType`, `ScopedJobKey`, `Status`, `WorkerLane`.
- ready slices such as `PQ_TranslateRequest_Ready` only checked job/status/timing, not core completeness.
- heartbeat selection used one-row selection patterns such as `ANY(TOP(ORDERBY(...), 1))`.
- `PQ_SetRunning` condition was `true`, so it did not re-check eligibility at mutation time.

## Safe remediation sequence

1. Do not rely on lowering heartbeat cadence as the primary fix; AppSheet scheduled automation granularity can make 5 minutes operationally too slow.
2. Run read-only monitoring snapshots to confirm whether malformed/duplicate counts are increasing.
3. Patch design first: completeness guards, conditional claims, duplicate suppression/idempotency.
4. Then run a cleanup dry-run for malformed rows, duplicate `QueueID`s, and duplicate active `ScopedJobKey`s.
5. Only execute cleanup after user approval and after preserving evidence.

## Hardening applied 2026-05-18

- AppSheet version `26.051803` was saved and promoted stable for `prodesign-group-1163872-25-01-09`.
- Added core completeness guards to `PQ_TranslateRequest_Ready`, `PQ_TranslateCollect_Ready`, `PQ_Notify_Ready`, `PQ_Thumbnail_Ready`, `PQ_ThumbnailPush_Ready`, `PQ_ActivityLog_Init_Ready`, and `PQ_ActivityLog_GenerateItems_Ready`.
- Changed `PQ_SetRunning` from unconditional `true` to a re-check requiring `Status` in `{Queued, Retry}`, due-or-blank `NextAttemptAt`, and nonblank `QueueID`, `SourceTable`, `SourceKeyColumn`, `SourceRowKey`, `JobType`, `ScopedJobKey`, `CreatedAt`, and `WorkerLane`.
- Patched AppSheet Helper bound Apps Script (`1BtXegLehRX78ky0aDnwXVhKZvEm0y8M2C8k6vpp-bXfsClLSCr9Q_Iid`) so `deleteOld_ProcessingQueueRows()` no longer deletes from stale snapshot row numbers. It now snapshots candidates, re-finds the current physical row by unique `QueueID`, re-reads the row, verifies a fingerprint (`QueueID`, `Status`, `SourceTable`, `SourceRowKey`, `JobType`, `ScopedJobKey`, `CreatedAt`), audits to `ProcessingQueue_CleanupAudit`, and only then deletes. Blank/duplicate/missing `QueueID` candidates are skipped/audited instead of row-number-deleted.
- AppSheet version `26.051804` was saved and promoted stable with duplicate-suppression/idempotency conditions on `PQ_CreateFollowupTranslateCollectRow` and `PQ_EnqueueNotify`. These now require complete source identity and skip enqueue if a same-target `ScopedJobKey` already exists in `{Queued, Running, Retry, Done}`.

Note: `UNIQUEID()` makes new `QueueID` generation probabilistically unique, but it does not provide logical idempotency and it cannot prevent duplicates introduced by sheet restore/copy/paste or concurrent duplicate physical writes. Use `QueueID` for physical-row identity; use `ScopedJobKey` for logical duplicate detection and monitoring.

## Fresh-sheet verification note added 2026-05-19

Do not answer ProcessingQueue row-shape questions from old cleanup artifacts alone. First read the current **AppSheet Helper** spreadsheet (`1n4UtbJkXb_JfrrEt8eeBb_CCgGsPvsr3r7Zmkwbf7NU`) tab `ProcessingQueue` directly with `gog sheets get ... 'ProcessingQueue!A1:AP<rowCount>'`, then inspect `ProcessingQueue_CleanupAudit`.

A fresh direct Google Sheets read at `2026-05-19T01:23Z` showed two separate phenomena:

- 20 fully blank physical rows interleaved near the active tail. Each matched a recent `ProcessingQueue_CleanupAudit` `DELETE_ROW` event from `deleteOld_ProcessingQueueRows`, so these are cleanup-gap artifacts around old `Done` queue row removal rather than active queue jobs.
- 14 malformed nonblank rows with blank `QueueID` and missing core identity fields but with leftover `Status`/timing fields. These are the older partial-row artifacts and should be treated separately from fully blank cleanup gaps.

When explaining “empty rows,” distinguish fully blank cleanup gaps from malformed blank-key/status-only rows. Current counts can change quickly because `deleteOld_ProcessingQueueRows()` removes old `Done`/`Dead` rows while AppSheet continues to append new queue rows.

Operator decision captured 2026-05-19: if fresh evidence indicates the fully blank rows were produced by our own cleanup path rather than AppSheet runtime job creation, **hold off on patching the bound Apps Script just to compact blanks**. Treat blank-row compaction as optional hygiene only after proving recurrence or operational impact. Do not present cleanup-artifact blanks as an AppSheet enqueue bug.

## Cleanup execution 2026-05-18

A manual cleanup plan was generated after the guards. It used these rules:

- no deletion by row number;
- no writes to blank-`QueueID` malformed rows;
- no writes to physical duplicate-`QueueID` groups;
- only AppSheet API `Edit` writes by unique `QueueID` after immediate pre-read verification that the row still matched the planned active duplicate `ScopedJobKey`.

Outcome:

- 13 safe AppSheet updates were submitted by unique `QueueID`.
- 12 duplicate active logical rows were verified `Dead` with `LastError` evidence notes.
- 1 planned thumbnail row was auto-closed to `Done` by normal AppSheet automation during the run, so it was no longer an active duplicate after verification.
- Post-cleanup plan showed 0 remaining safe AppSheet update candidates.
- Remaining unresolved rows: 14 blank-key malformed physical rows and 5 physical duplicate-`QueueID` groups (10 rows), which require a hidden immutable physical `RowID` or explicit operator-approved fingerprint procedure before cleanup.

## Bounded physical duplicate cleanup execution 2026-05-31

A later operator-approved bounded cleanup used direct Google Sheets reads/writes because AppSheet API `Find` on `ProcessingQueue` returned empty bodies and duplicate `QueueID` rows cannot be safely targeted by AppSheet key.

Safety pattern used:

1. Read current `ProcessingQueue!A1:AP` directly from AppSheet Helper via `gog sheets get`.
2. Build duplicate `QueueID` groups and duplicate active `ScopedJobKey` groups.
3. For duplicate `QueueID` groups, keep one evidence row, preferring a `Done` row and then the latest `FinishedAt`/`StartedAt`; clear only the other physical row(s), not whole-sheet delete/row shifts.
4. Before each clear, re-read the exact physical row and verify a fingerprint including `QueueID`, `Status`, `SourceTable`, `SourceRowKey`, `JobType`, `ScopedJobKey`, `CreatedAt`, `StartedAt`, `FinishedAt`, and `GoogleTranslateID_1`.
5. Append a `ProcessingQueue_CleanupAudit` row with event `MANUAL_CLEAR_DUPLICATE_QUEUEID` before clearing.
6. For duplicate active logical jobs with unique `QueueID`s, keep the oldest active row and mark later duplicates terminal (`Dead`) with `LastError` evidence only after immediate fingerprint re-read. In the 2026-05-31 run this path was not needed because the active thumbnail duplicate self-resolved before execution.
7. Verify by direct sheet read: duplicate `QueueID` groups and duplicate active `ScopedJobKey` groups both reached zero. Blank physical rows left by `clear` are expected; do not treat them as active queue jobs.

Execution receipt: cleared five stale duplicate-key physical rows (`0666738a`, `839667d0`, `4b48f961`, `31e32d52`, `ce9bf958` duplicate mates), appended five audit rows, and verified `duplicate_queueid_groups=0` and `active_duplicate_scopedjobkey_groups=0` afterward.

# ProcessingQueue duplicate key triage

Use when an AppSheet automation queue backed by Google Sheets shows duplicate `ProcessingQueue[QueueID]` values, ambiguous ref-action behavior, or queue rows that remain `Queued` even though an apparent matching job already ran.

## Durable lesson

Duplicate `QueueID` values in a Google Sheets-backed AppSheet queue are usually **duplicate physical sheet rows with the same generated payload**, not random `UNIQUEID()` collisions.

For short 8-character AppSheet IDs the keyspace is about `16^8 = 4,294,967,296`; multiple duplicate groups in a small active queue are not plausibly birthday collisions. If duplicated rows also share `SourceRowKey`, `ScopedJobKey`, `JobType`, `CreatedAt`, and `WorkerLane`, treat the cause as a repeated/partial-success append path.

Likely sequence:

1. AppSheet evaluates an add-row action and generates `QueueID = UNIQUEID()` once.
2. The Google Sheets append succeeds.
3. AppSheet automation, cache, network, or process state does not cleanly observe/commit the result, or a process step retries.
4. The same row payload is appended again.
5. Google Sheets accepts the duplicate because it has no physical unique constraint.
6. AppSheet now has duplicate logical keys, making refs/actions by `QueueID` ambiguous.

## Why this matters

Ready slices and heartbeat ref actions commonly select rows by key, for example:

```appsheet
PQ_ActivityLog_GenerateItems_Ready[QueueID]
```

If two physical rows share the same key, e.g. one `Done` and one still `Queued`, AppSheet may resolve/update the wrong physical row or leave the `Queued` duplicate eligible forever. This can make a worker lane appear idle even when the heartbeat condition is true.

## What to inspect

Read the backing sheet directly, not only through AppSheet `Find`, because AppSheet may collapse/ambiguously resolve duplicate keys.

For each duplicate `QueueID`, compare:

- physical sheet row number
- `QueueID`
- `JobType`
- `SourceRowKey`
- `ScopedJobKey`
- `Priority`
- `Status`
- `CreatedAt`
- `StartedAt`
- `FinishedAt`
- `RetryCount`
- `LastError`
- `WorkerLane`

Classify:

- same `QueueID` + same `ScopedJobKey` + same `CreatedAt` = duplicate append payload
- same `ScopedJobKey` but different `QueueID` = duplicate business job enqueue
- active loser behind `Done` row = likely lane blocker

## Safe cleanup approach

Before deleting physical rows, prepare a dry-run table. For each duplicate group, keep the most advanced/safest row:

1. Prefer `Done` over `Queued`/`Retry` when it represents completed work.
2. Prefer rows with `StartedAt`/`FinishedAt` evidence over never-started rows.
3. For active work, keep only one active row per `ScopedJobKey`.
4. Mark or remove duplicate losers only after verifying no needed child/business record is missing.

For high-risk queue tables, consider marking losers inert instead of immediate deletion:

```text
Status = Duplicate
LastError = duplicate_queue_row_quarantined
FinishedAt = UTCNOW()
```

If the app does not support a `Duplicate` status, use `Done` with an explicit `LastError` note only when that status will safely exclude the row from all ready slices.

## Durable design hardening

- Treat `ScopedJobKey` as the business idempotency key; `QueueID` is only the physical row key.
- Add a cleanup/quarantine lane for duplicate `QueueID` or duplicate active `ScopedJobKey` rows.
- Ready slices should exclude known duplicate losers; avoid putting very expensive duplicate-detection expressions in every hot ready slice if a periodic cleanup lane can maintain the invariant.
- Enqueue guards that check `ProcessingQueue[ScopedJobKey]` before add do not protect against AppSheet/Sheets retrying the same append payload after partial success.
- If the queue becomes operationally critical, consider moving it from Google Sheets to AppSheet DB or SQL where uniqueness can be enforced more reliably.

## Reporting shape

When reporting to the user, distinguish:

- `UNIQUEID()` random collision — improbable unless only one or two isolated duplicates in a huge population.
- duplicate physical append payload — same key and same metadata; common with retry/partial-success behavior.
- duplicate business job — same `ScopedJobKey` with different keys; caused by enqueue guard race or insufficient idempotency scope.

Include the number of rows read, distinct keys, duplicate groups, and a concrete example row pair.
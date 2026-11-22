# API_Target_Queue and ProcessingQueue maintenance

Use this reference when investigating AppSheet sync slowness, security-filter bypass rows, or whether `API_Target_Queue` rows can be pruned without breaking background processing.

## Roles of the tables

- `ProcessingQueue` is the orchestration/backlog table. It owns work state through fields such as `SourceTable`, `SourceRowKey`, `JobType`, `Status`, `StartedAt`, `FinishedAt`, `RetryCount`, `NextAttemptAt`, and worker/lane columns.
- `API_Target_Queue` is not the main work queue. It is an AppSheet API visibility/allowlist bypass so owner/server/API context can temporarily target rows hidden by security filters.
- Do not conclude that every `API_Target_Queue` row is still needed just because `ProcessingQueue` has a backlog. Cross-match by target row.

## Safe pruning logic

Before deleting or recommending deletion, pull both tables from the helper spreadsheet or through a trusted API context and compute:

- `api_pair = (API_Target_Queue[TargetTable], API_Target_Queue[TargetID])`
- `pq_source_pair = (ProcessingQueue[SourceTable], ProcessingQueue[SourceRowKey])`
- optional thumbnail pair: `(ProcessingQueue[ThumbnailAttachmentTable], ProcessingQueue[ThumbnailAttachmentKey])`

Keep an `API_Target_Queue` row if any condition is true:

1. It is recent enough for the current API pushback window, commonly last 24 hours unless the workflow has a longer SLA.
2. Its `(TargetTable, TargetID)` pair matches an active/nonterminal `ProcessingQueue` source or thumbnail pair.
3. It is the newest row for a duplicate `(TargetTable, TargetID)` pair and that target may still be retried.

Prune candidates are rows that are old, duplicate, or tied only to terminal queue rows (`Done`, `Dead`, `Completed`, `Cancelled`, etc.). For AppSheet changes, dry-run/readback first unless the user explicitly requested the bounded cleanup.

## Investigation checklist

1. Verify the current deployed definition/security filters from `/api/loadApp` before reasoning about visibility.
2. Pull `API_Target_Queue` counts by `TargetTable`, duplicate `(TargetTable, TargetID)`, min/max timestamp, and age buckets.
3. Pull `ProcessingQueue` counts by `Status`, `JobType`, `SourceTable`, and active/nonterminal status.
4. Cross-match active queue rows against API target rows.
5. Report how many API target rows are clearly stale versus still needed by active work.
6. If applying cleanup, delete only the bounded prune set and read back row counts.

## AppSheet security-filter note

If security filters include expressions such as:

```appsheet
IN([CaseID], SELECT(API_Target_Queue[TargetID], [TargetTable] = "Case"))
```

those rows are required only while the server/API needs to target hidden old records. They should not remain indefinitely after successful pushback or terminal queue completion.

## Reporting remaining rows after cleanup

When explaining why rows remain, do not imply every preserved `API_Target_Queue` row is proven to be tied to active `ProcessingQueue` work. Split the remainder into explicit buckets:

- **Confirmed active-target rows**: `(TargetTable, TargetID)` directly matches active/nonterminal `ProcessingQueue` source or thumbnail pairs.
- **Recent safety-window rows**: non-duplicate rows within the API pushback/targetability window, usually 24 hours, kept because deleting them could break server/API updates against security-filter-hidden rows even if they do not currently match the active snapshot.
- **Other preserved rows**: explain the concrete reason, or mark them as candidates for a follow-up cleanup once they age out.

Phrase carefully: `The remaining rows are not all definitely required forever. Some are confirmed active matches; others are recent targetability rows retained conservatively until the safety window expires.`

## Typical conclusion wording

Say: `API_Target_Queue is a targeting bypass, not the ProcessingQueue backlog itself. Rows still needed are either confirmed matches to active ProcessingQueue target/source rows or recent non-duplicate targetability rows inside the safety window. Stale, duplicate, or terminal-only rows can be pruned safely after a dry-run/readback.`

# Legacy Case / Case_Updates ProcessingQueue triage

Use after historical `Case` / `Case_Updates` imports when Andy sees new `ProcessingQueue` rows and asks whether imports are still running or whether Case Updates were migrated to the newer queue flow.

## Core distinction

- **Import completeness** means the expected deterministic `CaseID` / `CaseUpdateID` rows exist in AppSheet.
- **Post-import processing completeness** means downstream automation has finished translation, notification, parent-case updates, and status/flag transitions.
- New `ProcessingQueue` rows after import completion usually indicate the second thing is still catching up, not that the import runner is still adding `Case_Updates` rows.

## Evidence to gather

1. Use Prototype app readback for data-only import completeness checks:
   - Count expected deterministic IDs from dry-run/live-import artifacts.
   - Count unique live `Case_Updates[CaseUpdateID]` by legacy prefix.
   - Treat raw duplicate returned rows cautiously; use unique deterministic keys and physical `Row ID` duplicate checks.
2. Use deployed app / synced definition for automation behavior:
   - Read `latest_raw_app.json` from `/api/loadApp` for bots/events/processes/actions.
   - Confirm whether the active `ReadyToProcess` path writes to `ProcessingQueue` or old direct helper tables.
3. Check deployed `ProcessingQueue` rows by:
   - `SourceTable`
   - `JobType`
   - `Status`
   - `WorkerLane`
   - `ScopedJobKey`
4. To estimate **how many `Case_Updates` are left to be added to `ProcessingQueue`**, compare source rows to queue rows, not queue drain status:
   - Pull `Case_Updates` from the **prototype/Data Studio app** when you need the full visible source backlog; the deployed app can be security-filtered and undercount legacy rows.
   - Count `Case_Updates` where `Flag_Processed = "ReadyToProcess"`.
   - Pull `ProcessingQueue` from the **deployed app** for the active automation queue; if prototype `ProcessingQueue/Find` is too expensive or blank, do not treat that as absence of queue rows. If AppSheet queue reads are filtered/slow, read the physical Google Sheets backing tab directly and use its headers.
   - Build a set of **unique** `ProcessingQueue[SourceRowKey]` where `SourceTable = "Case_Updates"`; do not count queue rows because a single source update may later have multiple job rows (`translate_request`, `translate_collect`, `notify`, etc.).
   - Remaining enqueue backlog = `ReadyToProcess Case_Updates whose CaseUpdateID is not in that SourceRowKey set`.
   - Separately report already-created queue backlog by `ProcessingQueue[Status]` / `JobType`; do not conflate “not yet enqueued” with “queued but not processed.”
   - Reusable read-only probe: `python3 ~/.hermes/skills/appsheet-copilot/scripts/count_case_updates_processingqueue_backlog.py` prints the ReadyToProcess source count, already-enqueued count, remaining-not-yet-enqueued count, queue status/job breakdowns, and sample missing IDs.
5. If the user reports that `ProcessingQueue` suddenly went blank, verify the physical backing sheet/tab before explaining it as queue drain:
   - From `/api/loadApp` or the synced raw definition, resolve `ProcessingQueue` to its actual data source file ID and worksheet gid/name.
   - Read the Google Sheet tab directly, including the header range (for example `ProcessingQueue!A1:AT20`).
   - Check sheet grid properties (`rowCount`, `columnCount`) if available. Allocated rows/columns with no values, including no header row, points to a tab content clear/wipe rather than normal AppSheet row deletion or queue completion.
   - Compare this with any bound Apps Script cleanup logic. A cleanup that deletes old `Done`/`Dead` rows should normally preserve the header; if the header is gone, treat it as a separate sheet-level clear event unless audit/version history proves otherwise.
   - Do not claim who/what caused the wipe without Google Sheets version history, Drive activity, or script execution evidence.

## Current Pro-Design Case_Updates queue wiring pattern

As of the 2026-05 legacy import work, `Case_Updates` is on the newer `ProcessingQueue` path for translation/notification:

- Enabled bot: `Case_U_FlagProcess_ReadyToProcess`
- Process action: `Action for Update Case Info and Translate`
- Composite action sequence:
  1. `Case_Updates_UpdateCaseWithLatestCaseUpdateID`
  2. `Case_Updates_UpdateCaseInformationFromCaseUpdate`
  3. `C_U_Enqueue_TranslateRequest`
  4. `C_U_Enqueue_Notify_NoTranslation`
  5. `C_U_SetFlagProcessed_AwaitingTranslation`

Queue enqueue actions:

- `C_U_Enqueue_TranslateRequest`
  - writes to `ProcessingQueue`
  - `SourceTable = "Case_Updates"`
  - `SourceKeyColumn = "CaseUpdateID"`
  - `SourceRowKey = [CaseUpdateID]`
  - `JobType = "translate_request"`
  - `ScopedJobKey = CONCATENATE("Case_Updates|", [CaseUpdateID], "|translate_request")`
  - `WorkerLane = "translation"`
- `C_U_Enqueue_Notify_NoTranslation`
  - writes to `ProcessingQueue`
  - `JobType = "notify"`
  - `ScopedJobKey = CONCATENATE("Case_Updates|", [CaseUpdateID], "|notify")`
  - `WorkerLane = "notification"`

Older direct helper actions can still exist, for example `CaseUpdates_Translate_UpdateSummary` and `CaseUpdates_Translate_UpdateDescription`; do not assume they are active just because they exist. Verify the active bot/process/action chain.

## Race-condition / malformed-row investigation pattern

When the user reports partially empty `ProcessingQueue` rows, investigate read-only first and preserve evidence before any cleanup:

1. Read the physical Google Sheet tab directly, not only AppSheet API rows. AppSheet can hide malformed physical rows when the key column (`QueueID`) is blank or duplicated.
2. Compare physical-sheet counts with deployed AppSheet `ProcessingQueue/Find` counts. A gap often means blank-key or otherwise invalid rows exist in the sheet but are not normal AppSheet rows.
3. Audit for these signatures:
   - rows with blank `QueueID`, `SourceTable`, `SourceRowKey`, `JobType`, `ScopedJobKey`, or `CreatedAt` but populated `Status`, `StartedAt`, `FinishedAt`, `NextAttemptAt`, or `RetryCount`;
   - duplicate active `ScopedJobKey` values, because `ScopedJobKey` is the logical job identity but is not the table key;
   - duplicate physical `QueueID` values, especially one copy `Queued` and another `Running`;
   - sparse rows with only status/timing fields populated;
   - active rows missing any core identity fields.
4. Inspect the synced definition for queue atomicity hazards:
   - whether core fields are required;
   - whether ready slices require complete key/source/job fields;
   - whether heartbeat selectors use `ANY(TOP(ORDERBY(...), 1))`;
   - whether claim actions like `PQ_SetRunning` re-check `Status IN {Queued, Retry}` and due time at mutation time;
   - whether follow-up enqueue actions suppress duplicate `ScopedJobKey` jobs.
5. Report the hypothesis carefully. Do not claim the exact actor without runtime/version-history evidence. A supported diagnosis is: non-atomic queue claim plus missing idempotency/uniqueness can let concurrent heartbeat runs select the same ready row and enqueue duplicate logical jobs.
6. For a concrete Pro-Design example with counts, duplicate signatures, and definition risks, read `references/processingqueue-race-investigation-20260518.md`.

Hardening recommendations to include in the plan/dry-run before writes:

- add core completeness guards to every `PQ_*_Ready` slice;
- make claim actions conditional on the row still being `Queued`/`Retry` and due;
- add duplicate suppression before follow-up enqueue actions (`translate_collect`, `notify`, thumbnails, etc.);
- consider a unique logical-job registry/lock table or making the logical job key the enforced identity;
- quarantine malformed rows for evidence instead of silently processing or cleanup-deleting them.

## Manual retrigger / push pattern for stuck `ReadyToProcess` rows

When asked to manually "push" `Case_Updates` rows into the bot/queue path, do not batch-write immediately. First build a dry-run list by comparing prototype/Data Studio `Case_Updates[Flag_Processed] = "ReadyToProcess"` against physical/deployed `ProcessingQueue[SourceTable="Case_Updates"][SourceRowKey]`.

Split the missing set into:

1. **deployed-visible retrigger candidates** — rows returned by the deployed app context. These can usually be tested with one canary deployed AppSheet `Edit`/re-save that leaves `Flag_Processed = "ReadyToProcess"`, then verified for queue creation, `Flag_Processed` advancement to `AwaitingTranslation`, and no duplicate `ScopedJobKey` before batching.
2. **deployed-invisible rows** — rows visible in prototype but not deployed context, often older/stale parent Cases affected by security filters. Do not assume a prototype write will trigger deployed automation; inspect/whitelist/special-route these separately.

If the user says they keep seeing new `Case_Updates` entries in `ProcessingQueue`, distinguish first-stage `translate_request` enqueue from second-stage `translate_collect` follow-up rows. New `translate_collect` rows can be normal queue drain for already-enqueued work and are not proof that the same stuck rows are looping or being newly enqueued.

## Interpretation guide

- If deterministic `CaseUpdateID` completeness is 100% but `ProcessingQueue` has many `SourceTable = Case_Updates` rows in `Queued`, `Retry`, or `Running`, report: **import complete; post-import queue backlog still processing**.
- If `ProcessingQueue` row count keeps increasing, check whether rows are being moved from `Flag_Processed = ReadyToProcess` to `AwaitingTranslation`; this is expected catch-up behavior after bulk import.
- If the user says they keep seeing new `Case_Updates` entries in `ProcessingQueue` while the “not yet enqueued” count stays unchanged, separate **first-stage enqueue misses** from **follow-up queue rows** before calling it an infinite loop:
  - Recompute the current `ReadyToProcess Case_Updates` set from the prototype/Data Studio app.
  - Read the physical `ProcessingQueue` tab directly and compare `SourceRowKey` to that current set.
  - Inspect the newest `SourceTable = "Case_Updates"` queue rows by physical sheet row/tail: `JobType`, `Status`, `ScopedJobKey`, `CreatedAt`, `FinishedAt`.
  - Exact-read the newest queue rows’ source `Case_Updates[Flag_Processed]`. If they are already `AwaitingTranslation` and `JobType = "translate_collect"`, they are normal second-stage collection jobs from already-enqueued work, not proof that the stuck `ReadyToProcess` rows are repeatedly re-added.
  - Count duplicate `ScopedJobKey` values overall and among active statuses `{Queued, Running, Retry}`. Zero duplicates argues against a runaway duplicate-enqueue loop.
  - Report the distinction plainly: “queue is still active/draining existing Case_Updates work” vs “these N ReadyToProcess rows still lack their first translate_request queue row.”
- If `ProcessingQueue` is empty in Prototype but non-empty in deployed app, do not conclude no queue exists. Queue visibility/app context can differ; use the app context that owns deployed automation for queue behavior.
- If the physical Google Sheet `ProcessingQueue` tab is completely blank, including headers, and still has allocated grid dimensions, say plainly that the backing tab contents appear to have been cleared. Do not soften this into "queue drained" and do not blame the normal old-row cleanup path unless it can clear the header too.
- When malformed/partial queue rows were seen shortly before a wipe, separate the two findings: malformed rows can support a race/validation concern, but a headerless blank tab is stronger evidence of a sheet-level clear event.
- For suspected wipes, recommend Google Sheets version history / Drive activity review and restoring or copying the tab from just before the wipe before re-enabling backlog processing.
- Separate these claims in the report:
  - imported row exists
  - queue job was enqueued
  - worker picked it up
  - translation/notification side effect persisted
  - final business row state is finished
  - backing helper sheet/tab still contains expected headers/data

## Response pattern

Keep the answer concise and direct:

> `Case_Updates` is imported. The new rows you see in `ProcessingQueue` are downstream translation/notification jobs created for already-imported updates. The active `Case_Updates` ReadyToProcess path does use `ProcessingQueue`; it has not missed the migration. The remaining work is queue backlog drain, not import.`

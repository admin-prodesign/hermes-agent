# QueueState HeartBeat canary dry-run/live-apply pattern

Use when replacing AppSheet HeartBeat queue/slice polling for one ProcessingQueue lane with a small physical `QueueState` control table. This reference covers both the safe dry-run patch shape and the follow-through required when the user approves a live canary rollout.

## When this applies

- AppSheet export logs show `VerifyEventConditionAsync`, `TaskCanceledException`, `OperationCanceledException`, cache lock waits, or slow HeartBeat processes before worker actions run.
- A `QueueState` table has been added to the app definition and you need a **dry-run AppSheet definition patch** for one canary lane.
- Start with narrow queue-only lanes such as `case_update_parent_sync`; avoid broad repair slices as the first canary.

## Fresh readback first

1. Run the JSON-first AppSheet definition sync/readback from `/api/loadApp`.
2. Verify header state:
   - `Version`
   - `StableVersion`
   - `IsValid`
   - `IsRunnable`
   - `IsDeployable`
3. Verify the table is present in raw JSON:
   - `AppData.DataSets[].Name == "QueueState"`
   - `AppData.DataSchemas[].Name == "QueueState_Schema"`
4. Verify the canary row exists through deployed Data API if available:

```text
QueueStateID = "case_update_parent_sync"
Enabled = TRUE
HasReady = FALSE, or TRUE if ready/stale work already exists
MaxBatchSize = 1
```

If the definition contains `QueueState` but deployed Data API readback returns zero rows for the canary key, treat it as a **live-save blocker**: seed/confirm the row before applying any patch that changes HeartBeat to depend on `QueueState`.

## Dry-run patch shape for `case_update_parent_sync`

Do not save live during dry-run. Build an artifact containing the intended JSON patch and a validation/readme summary.

### 1. Replace the HeartBeat event filter

Change `HeartBeat_PQ_CaseUpdateParentSync` from scanning `PQ_CaseUpdateParentSync_Ready` / stale `ProcessingQueue` rows to a cheap `QueueState` lookup:

```appsheet
=AND(
  TEXT([ID]) = "ProcessingQueue",
  LOOKUP("case_update_parent_sync", "QueueState", "QueueStateID", "Enabled") = TRUE,
  LOOKUP("case_update_parent_sync", "QueueState", "QueueStateID", "HasReady") = TRUE
)
```

This is the main performance move: the expensive queue/slice expression no longer runs during every HeartBeat event-condition evaluation.

### 2. Add a QueueState mark-ready action

Add a `QueueState` action, e.g. `QueueState_SetReady_CaseUpdateParentSync`, that sets:

```text
HasReady = TRUE
FlagUpdatedAtUTC = UTCNOW()
LastError = ""
```

Condition should keep it scoped:

```appsheet
=AND([QueueStateID] = "case_update_parent_sync", [Enabled])
```

### 3. Add an enqueue-side ref action

Add a `Case_Updates` ref action, e.g. `Case_Updates_MarkQueueStateReady_CaseUpdateParentSync`, pointing at:

```appsheet
ReferencedTable: QueueState
ReferencedRows: =LIST("case_update_parent_sync")
ReferencedAction: QueueState_SetReady_CaseUpdateParentSync
```

Use the same cheap eligibility as the enqueue trigger, not the duplicate-prevention `COUNT(SELECT(...))` guard. The queue row creation action can still own duplicate prevention.

Example condition:

```appsheet
=AND(
  ISNOTBLANK([CaseUpdateID]),
  ISNOTBLANK([CaseID]),
  OR(
    ISNOTBLANK([New Status]),
    ISNOTBLANK([New Next Step Responsible Person]),
    ISNOTBLANK([New Deadline])
  )
)
```

Append this ref action as a second node after the existing enqueue action in `Process for Case Update Added - Enqueue Parent Sync`:

```text
Case_Updates_EnqueueParentSync
Case_Updates_MarkQueueStateReady_CaseUpdateParentSync
```

### 4. Add a post-worker refresh action

Add `QueueState_Refresh_CaseUpdateParentSync` to recompute `HasReady` after a worker pass. It may still inspect ready/stale `ProcessingQueue`, but this happens after the canary lane has already woken, not inside every HeartBeat condition.

Use the existing readiness/stale logic as the value for `HasReady`:

```appsheet
OR(
  ISNOTBLANK(ANY(TOP(PQ_CaseUpdateParentSync_Ready[QueueID], 1))),
  ISNOTBLANK(
    ANY(
      TOP(
        SELECT(
          ProcessingQueue[QueueID],
          AND(
            [JobType] = "case_update_parent_sync",
            [WorkerLane] = "case",
            [Status] = "Running",
            ISNOTBLANK([StartedAt]),
            ([StartedAt] + "000:30:00") < UTCNOW()
          )
        ),
        1
      )
    )
  )
)
```

Useful assignments:

```text
HasReady = <readiness expression>
FlagUpdatedAtUTC = UTCNOW()
LastWorkerFinishedAtUTC = UTCNOW()
LastNoWorkConfirmedAtUTC = IF(<readiness expression>, [LastNoWorkConfirmedAtUTC], UTCNOW())
LastError = IF(<readiness expression>, [LastError], "")
```

### 5. Add a HeartBeat ref action to refresh QueueState

Add `HeartBeat_QS_Refresh_CaseUpdateParentSync` on `HeartBeat`:

```appsheet
ReferencedTable: QueueState
ReferencedRows: =LIST("case_update_parent_sync")
ReferencedAction: QueueState_Refresh_CaseUpdateParentSync
Condition: =TEXT([ID]) = "ProcessingQueue"
```

Append it as the final node in `Process for HeartBeat_PQ_CaseUpdateParentSync`:

```text
HeartBeat_PQ_ReapStaleRunning_CaseUpdateParentSync
HeartBeat_PQ_Process_CaseUpdateParentSync
HeartBeat_QS_Refresh_CaseUpdateParentSync
```

## Validation checklist

Before live save:

- Candidate action names are unique. Ignore existing repeated built-in names like `Add`, `Edit`, `Delete` across tables.
- `QueueState` schema and dataset are present.
- Canary row exists and `Enabled=TRUE`.
- If current ready/stale work exists, seed `HasReady=TRUE` before switching the HeartBeat event filter.
- Patch only the canary lane. Do not migrate broad repair lanes in the same save.

For live apply after approval:

1. Use fresh `/api/loadApp` JSON immediately before editing; do not apply a patch to a stale exported definition.
2. Verify the canary row through deployed data readback before save. If current ready/stale work exists and `HasReady=FALSE`, seed/refresh it first or the lane can go silent after the event filter switch.
3. Apply the minimal patch.
4. Submit `/api/saveapp` with validation and capture the save response/version receipt.
5. Reload `/api/loadApp` and verify:
   - app is valid/runnable/deployable;
   - the target `Version` is known;
   - event filter persisted;
   - new actions/process nodes persisted;
   - latest/stable version status is understood before claiming user-facing deployment.
6. If stable rollout is intended, promote latest to stable with the verified admin/tailscale AppSheet profile. A non-admin/default cookie may save/read but fail stable promotion with a misleading Enterprise-plan error; retry with the admin profile rather than concluding the plan lacks the feature.
7. Reload `/api/loadApp` again after promotion and require `StableVersion == Version == target` before saying stable is live.
8. Re-read runtime state after stable promotion:
   - `QueueState[case_update_parent_sync]` row exists;
   - `Enabled=TRUE`;
   - `HasReady` matches current ready/stale `ProcessingQueue` reality;
   - `MaxBatchSize` remains the intended canary value.
   `HasReady=FALSE` is a valid post-apply state when both ready and stale work counts are zero.
9. After runtime, compare export logs for the canary process before/after: failures in `VerifyEventConditionAsync`, `OperationCanceledException`, success/failure counts, and whether worker actions actually ran.

## Pitfalls

- Do not remove the old worker actions or ProcessingQueue readiness slices during the first canary. The patch only changes when HeartBeat wakes and adds state refresh.
- Do not rely on the table existing in the definition as proof that seed rows exist. Query/seed the row.
- The refresh action can still scan `ProcessingQueue`; this is acceptable in the canary because it is moved out of the always-evaluated event condition.
- If `HasReady` is false while queued/stale work already exists, HeartBeat will not wake this lane until a new enqueue marks it ready or a manual/steward refresh sets the flag.

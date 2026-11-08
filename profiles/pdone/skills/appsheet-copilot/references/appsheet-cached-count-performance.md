# AppSheet cached-count performance patterns

Use when Performance Analyzer shows `Lookup[RowCount_Realtime]`, `RowCount[Count_RealTime]`, or other user-dependent count/label virtual columns dominating sync time.

## Trigger evidence from 2026-06-03

Fresh sync-only Performance Analyzer window after Case Update cached-writing bots were enabled and promoted stable:

- Window: 2026-06-03 04:47:34 → 07:47:34 UTC.
- Rows: 158 sync rows; 79 detailed performance rows; 8 failures.
- Sync duration: avg 53.37s, p50 43.42s, p90 114.05s, max 154.26s.
- Top virtual/computed columns:
  - `Lookup[RowCount_Realtime]`: p90 52.31s, max 107.33s.
  - `RowCount[Count_RealTime]`: p90 46.29s, max 106.90s.
  - `ActivityLog_Session_Items[Label]`: p90 43.90s, max 90.17s.
  - `Case[Related Case_Updates]`: p90 9.65s — improved enough that it is no longer the first target.
- Failure pattern: `ActivityLog` table timeout / AsyncLock / large-slow table or cross-table-cycle signatures.

Artifacts from that pass:

- `logs/appsheet-performance/scans/cached-bots-stable-20260601-3h/perf-scan-20260603T074734Z.json`
- `logs/appsheet-performance/scans/cached-bots-stable-20260601-3h/perf-raw-20260603T074734Z.json`
- `logs/appsheet-performance/scans/cached-bots-stable-20260601-3h/triage-summary-20260603.md`

## Current definition facts

`RowCount[Count_RealTime]` is a virtual column:

```appsheet
SWITCH(
  [RowCountID],
  "Case_My_NeedsReview",
  COUNT(Case_My_NeedsReview[CaseID]),
  "Case_My_NextStepPerson",
  COUNT(Case_My_NextStepPerson[CaseID]),
  "Case_IT_MyCases",
  COUNT(Case_IT_MyCases[CaseID]),
  ""
)
```

`Lookup[RowCount_Realtime]` is also virtual and calls the RowCount total:

```appsheet
IF(
  [Show_RowCount],
  LOOKUP([LookupID], "RowCount", "RowCountID", "Count_Total"),
  ""
)
```

`RowCount[Count]` is already physical and maintained by an enabled heartbeat pattern:

- Bot: `HeartBeat - RowCount`.
- Process: `Process for HeartBeat - RowCount`.
- Grouped action: `HeartBeat_RowCount_All`.
- Per-row action: `RowCount_Recalculate` writes physical `RowCount[Count]`.

`RowCount_Recalculate` already handles global/materialized counts such as:

- `SuddenAbsenceRequests_Last24Hours`
- `ActivityLog_5S_PointsAssignment`
- `HR_Employees_PerformanceRecords`
- `Case_IT_Unassigned`
- `Case_IT_Uncompleted`

## Design rule

Keep global counts in `RowCount`; move user-dependent counts to `HR_E_A_S` / `HR_Employees_AppSheet_Settings`.

Reason: counts based on slices such as `Case_My_NeedsReview`, `Case_My_NextStepPerson`, or `Case_IT_MyCases` vary by current user/team/role. A single global `RowCount` row cannot cache those correctly for everyone.

`HR_E_A_S` is the right home for per-user cached counts because it already stores the user's AppSheet context:

- `PersonID`
- `Appsheet Email`
- `Team Members`
- `Appsheet Roles`
- `Combined Appsheet Roles`
- `_Is_Case_User`
- `_Is_IT_Admin`
- data-window fields such as `Data_Days_ActivityLog` and `Data_Days_Case`

## Recommended implementation pattern

1. Add physical number columns on `HR_E_A_S` / `HR_Employees_AppSheet_Settings`, for example:
   - `Count_Case_My_NeedsReview`
   - `Count_Case_My_NextStepPerson`
   - `Count_Case_IT_MyCases`
   - `Counts_UpdatedAt`
2. Add an hourly AppSheet bot/process/action pattern, similar to `HeartBeat - RowCount`, that recalculates those columns for each active HR_E_A_S row.
3. Change `Lookup[RowCount_Realtime]` or the home-badge expression to read `Current User Settings[...]` for user-dependent IDs and only fall back to global `RowCount[Count]` for global counts.
4. Keep `RowCount[Count_RealTime]` temporarily for side-by-side verification, then remove/de-scope it after Performance Analyzer confirms the p90 drop.

Example expression shape:

```appsheet
SWITCH(
  [LookupID],
  "Case_My_NeedsReview", ANY(Current User Settings[Count_Case_My_NeedsReview]),
  "Case_My_NextStepPerson", ANY(Current User Settings[Count_Case_My_NextStepPerson]),
  "Case_IT_MyCases", ANY(Current User Settings[Count_Case_IT_MyCases]),
  LOOKUP([LookupID], "RowCount", "RowCountID", "Count")
)
```

## Pitfalls

- Do not update every user's counts on every `Case` change; that creates write storms. Hourly batch refresh is the safe default.
- If freshness matters, show/cache `Counts_UpdatedAt` rather than returning to realtime counts.
- For user-facing correctness, validate counts for several roles/users using Data API readbacks before removing the old virtual columns.
- After promotion to stable, rerun sync-only Performance Analyzer and compare p90 for `Lookup[RowCount_Realtime]` and `RowCount[Count_RealTime]`; do not rely on definition readback alone.
- Separate global-count IDs from user-dependent IDs. Global IDs can remain in `RowCount[Count]`; per-user IDs belong in HR_E_A_S.

## 2026-06-03 implementation receipt

After Andy added/regenerated physical columns on `HR_Employees_AppSheet_Settings` / `HR_E_A_S`, the deployed app editor definition was patched and saved through editor versions `26.060309` → `26.060312`. Stable promotion readback was ambiguous: `stableVersion=<version>` returned `Success: true`, but `/api/loadApp` continued to show `StableVersion: null`; treat this as an endpoint/readback ambiguity and verify analyzer logs/runtime state rather than overclaiming stable status.

Physical columns verified present and non-virtual:

- `Count_Case_My_NeedsReview`
- `Count_Case_My_NextStepPerson`
- `Count_Case_IT_MyCases`
- `Needs_Case_Count_Cache`
- `Counts_UpdatedAt`

Saved definition objects:

- `Lookup[RowCount_Realtime]` now switches the three user-dependent `Case_*` IDs to `ANY(Current User Settings[Count_*])`, and falls back to `LOOKUP([LookupID], "RowCount", "RowCountID", "Count_Total")` for global counts.
- Row action `HR_E_A_S_UpdateCaseCountCache` on `HR_Employees_AppSheet_Settings` writes the three count columns, `Counts_UpdatedAt = UTCNOW()`, and `Updater = TEXT(NOW(),"YYYYMMDD.hhmmss")`.
- Heartbeat ref action `HeartBeat_HR_E_A_S_CaseCountCache_All` on `HeartBeat` targets only the settings table/cache flag. Do **not** add `[PersonID].[Employment Status]` derefs here: `HR_Employees_AppSheet_Settings` / `HR_E_A_S` should contain only currently-employed employees, so that check is redundant cost.

```appsheet
SELECT(
  HR_Employees_AppSheet_Settings[PersonID],
  [Needs_Case_Count_Cache] <> "FALSE"
)
```

- `Process for HeartBeat - RowCount` now runs both `HeartBeat_RowCount_All` and `HeartBeat_HR_E_A_S_CaseCountCache_All`.

Runtime smoke: Data API `Find` returned 137 eligible settings rows; running `HR_E_A_S_UpdateCaseCountCache` on one row updated `Counts_UpdatedAt` and `Updater`, proving the action is callable through the deployed Data API. Helper script committed in OpenClaw backup: `tools/appsheet-migration/scripts/patch_hr_eas_case_count_cache.py`.

## 2026-06-11 heartbeat speedup patch

The live app had `HeartBeat_HR_E_A_S_CaseCountCache_All` still targeting every settings row where `[Needs_Case_Count_Cache] <> "FALSE"`, which meant each scheduled heartbeat could touch all eligible users. The deployed/stable app was patched from version `26.060844` to `26.060845` to bound and rotate the work without adding a physical bucket column.

Reference script committed in the OpenClaw backup repo: `tools/appsheet-migration/scripts/patch_heartbeat_speedup.py`.

Updated Heartbeat ref action target rows:

```appsheet
TOP(
  ORDERBY(
    SELECT(
      HR_Employees_AppSheet_Settings[PersonID],
      AND(
        [Needs_Case_Count_Cache] <> "FALSE",
        OR(
          ISBLANK([Counts_UpdatedAt]),
          UTCNOW() - [Counts_UpdatedAt] > "000:55:00"
        )
      )
    ),
    [Counts_UpdatedAt],
    TRUE
  ),
  25
)
```

Updated row-action condition for `HR_E_A_S_UpdateCaseCountCache`:

```appsheet
AND(
  CONTEXT("Host") = "Server",
  [Needs_Case_Count_Cache] <> "FALSE",
  OR(
    ISBLANK([Counts_UpdatedAt]),
    UTCNOW() - [Counts_UpdatedAt] > "000:55:00"
  )
)
```

Verification receipts:

- `/api/loadApp` header readback after save: `Version = 26.060845`, `StableVersion = 26.060845`, `IsValid = true`.
- Data API selector smoke returned exactly 25 eligible rows with the new `TOP(ORDERBY(SELECT(...), [Counts_UpdatedAt], TRUE), 25)` expression.
- Data API row-action smoke on `PersonID = P-e26d94e4` updated `Counts_UpdatedAt` to `06/11/2026 02:46:41` and `Updater` to `20260611.104642`; a follow-up selector readback no longer included that freshly updated row in the first 25.

Pitfall: `/api/saveapp` can commit the version while the client keeps streaming a huge response. If the save process appears hung, do a lightweight streaming `/api/loadApp` header check before retrying; do not repost stale full-app JSON.

## 2026-06-11 no-physical-column HeartBeat micro-optimizations

For HeartBeat pressure where AppSheet repeatedly scans the same queue slices, the safe no-schema-change first pass is to replace duplicate `COUNT(Slice[Key]) > 0` guards with existence checks and remove duplicate action-level guards when the event filter already controls whether the process should run.

Reference script committed in the OpenClaw backup repo: `tools/appsheet-migration/scripts/patch_heartbeat_no_column_optimizations.py`.

Applied pattern:

- Event filters changed from `COUNT(SomeReadySlice[Key]) > 0` to `ISNOTBLANK(ANY(TOP(SomeReadySlice[Key], 1)))` for existence-only checks.
- `HeartBeat_PQ_CaseUpdateParentSync` stale-running check changed from a full `COUNT(SELECT(...)) > 0` to `ISNOTBLANK(ANY(TOP(SELECT(...), 1)))`.
- `HeartBeat_PQ_Process_CaseUpdateParentSync` and `HeartBeat_PQ_ReapStaleRunning_CaseUpdateParentSync` action conditions changed to `=TRUE` so they do not rescan the same queue slices after the event has already matched; their referenced-row expressions still select zero/one target row.
- `Process for HeartBeat - PQ` notification branch changed from `COUNT(PQ_Notify_Ready[QueueID]) > 0` to `ISNOTBLANK(ANY(TOP(PQ_Notify_Ready[QueueID], 1)))`.

Touched objects:

- Events: `HeartBeat_PQ_CaseUpdateParentSync`, `HeartBeat_AL_Repair_NG_MissingSessionItems`, `HeartBeat_PQ_ActivityLogGenerateItems`, `HeartBeat_PQ_ActivityLogGenerateItems 2`.
- Actions: `HeartBeat_PQ_Process_CaseUpdateParentSync`, `HeartBeat_PQ_ReapStaleRunning_CaseUpdateParentSync`.
- Process node: `Process for HeartBeat - PQ` / `Branch_Notify: send out notifications for one record that has translation ready`.

Pitfall: AppSheet `/api/saveapp` may return HTTP 400 with `Success=false` but `ErrorDescription="App saved successfully"` and a valid returned app. Treat this as an ambiguous save receipt: verify via fresh `/api/loadApp` before deciding whether to retry. In the 2026-06-11 pass, fresh `/api/loadApp` showed `Version=26.060846`, `StableVersion=26.060845`, `IsValid=true`, `IsRunnable=true`, and all touched objects `IsValid=true`; stable promotion still needed a separate verified receipt.

## Related optimization

`ActivityLog_Session_Items[Label]` was also a major p90 contributor. If still high after count caching, add a physical label column on session items and write it on create/update rather than dereferencing `[ActivityLogItemID]` and `[ActivityLogID]` for each row during sync.

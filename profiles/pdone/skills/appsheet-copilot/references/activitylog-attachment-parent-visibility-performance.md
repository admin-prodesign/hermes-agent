# ActivityLog attachment parent-visibility and performance triage

Use when AppSheet users cannot upload `ActivityLog_Attachments`, especially when the error says the parent `ActivityLog` row was not found, or when Performance Analyzer shows slow `ActivityLog` / attachment syncs.

## Incident signature

- User adds an attachment to an ActivityLog/5S record.
- AppSheet reports an add failure on `ActivityLog_Attachments`, often phrased like: unable to find the specified row / parent row not found in AppSheet database.
- Or, after frequent editor/API saves, AppSheet reports: `This data change cannot be applied because there is a newer version of your app ... Please reset data to discard local changes.` In that case, treat it first as stale queued local mutations; users must reset/full-sync before retrying.
- Logs may show duplicate request/retry symptoms after the first add stalls.
- User settings can still be valid (`_Is_ActivityLog_User`, role, and data access mode) — do not assume this is a permission issue.

## Deterministic checks

1. Pull or inspect AppSheet `/manage/exportlog` entries around the failure window.
2. Convert UTC timestamps to TPE when reporting Pro-Design incidents.
3. Check the affected user's `HR_Employees_AppSheet_Settings` row:
   - `Appsheet Email`
   - `PersonID`
   - `_Is_ActivityLog_User`
   - `Appsheet Data Access Mode`
   - roles containing the relevant ActivityLog role
   - `Data_Days_ActivityLog`
4. Inspect current raw editor JSON from `/api/loadApp` rather than generated HTML docs.
5. In `Properties.Performance`, rank table and virtual/computed timings; do not rely only on top-level row status.

## Known hot path

For the Pro-Design deployed app, the expensive pattern observed was:

- `ActivityLog[Related ActivityLog_Attachments]`
- formula: `REF_ROWS("ActivityLog_Attachments", "ActivityLogID")`
- broad views/decks/detail layouts include `Related ActivityLog_Attachments` as nested or ordered columns.

This can force AppSheet to repeatedly scan/dereference attachments during save/sync. It may worsen read-after-write/cache timing issues where the child attachment row is saved before the parent `ActivityLog` is resolvable to AppSheet.

June 2026 follow-up evidence after other HeartBeat/Case optimizations: add-row Performance Analyzer windows still showed over-10s `ActivityLog_Attachments` and `ActivityLog` adds, including a parent-resolution failure (`Unable to find the specified row from AppSheet database`) on an `ActivityLog_Attachments` add. When this remains after unrelated sync optimizations, treat attachment parent visibility/read-after-write as its own add-row architecture problem, not as proof that the preceding sync optimization failed.

## Safer implementation plan

Do **not** start by deleting or replacing the auto reverse-ref virtual column. AppSheet may depend on it for inline/nested child UX and generated ref actions.

Preferred phases:

1. **Baseline first**
   - Save fresh definition/exportlog artifacts.
   - Capture p50/p90/max timings for `ActivityLog`, `ActivityLog_Attachments`, and `ActivityLog[Related ActivityLog_Attachments]`.
   - Confirm latest vs stable definition drift before promotion.

2. **View-level mitigation**
   - Remove `Related ActivityLog_Attachments` from broad list/deck/detail views where users do not need inline child rows.
   - Use lightweight fields such as cached attachment count, `HasAttachments`, or `Thumbnail` in broad views.
   - Keep full attachment rows only in dedicated detail/attachment flows.

3. **Use existing cache infrastructure**
   - Check for a physical `ActivityLog[ActivityLog_Attachments_Cached]` column and existing actions such as `ActivityLog_Update_Cached_Attachments` before creating anything new.
   - Verify add/delete/update triggers refresh the parent cache.
   - Batch repair stale/blank cache rows outside production hours.

4. **Denormalize attachment classification cautiously**
   - `ActivityLog_Attachments[ActivityLog Type]` may be a physical column with an AppFormula dereferencing `[ActivityLogID]`.
   - Avoid a risky in-place AppFormula → Initial Value change as the first step.
   - Prefer adding/storing row-local scalar fields such as `ActivityLogType_Cached`, `RetentionClass`, and `RetentionDeleteAfter`, populated after the parent row is resolvable.

5. **Retention bots**
   - Recurring delete bots that filter on `[ActivityLog Type]` and `[Timestamp]` scan attachments and may trigger parent dereferences.
   - Move them to simple stored predicates, e.g. `AND([RetentionClass] = "5S", [RetentionDeleteAfter] <= NOW())`.

6. **Parent/child visibility hardening**
   - If attachment rows can pass the child security filter while the parent `ActivityLog` is hidden by `Data_Days_ActivityLog`, the parent-not-found error is plausible.
   - `IN([ActivityLogID], ActivityLog[ActivityLogID])` is a correctness improvement but is not guaranteed SQL-pushdown optimized.
   - May 2026 log check: a latest/editor test using this parent-visible `IN(...)` pattern on `ActivityLog_Attachments` still returned ~50k attachment rows and showed a large `ActivityLogID InList ...` provider predicate; one targeted sync rose to ~132s with `ActivityLog.Related ActivityLog_Attachments` at ~79s. Treat the pattern as a diagnostic/correctness test, not a proven performance fix.
   - Because `ActivityLog` is event-log/retention-shaped rather than long-lived like `Case`, prefer a row-local retention/security predicate for attachments (for example stored activity-log date/type/retention fields or an attachment timestamp cutoff aligned with `Data_Days_ActivityLog`) instead of broad parent-key list scans.
   - Prefer long-term row-local cached visibility predicates where possible, and preserve narrow owner/server `API_Target_Queue` exceptions for backend jobs.

7. **Cached-attachment refresh wiring (May 2026 fix pattern)**
   - A physical `ActivityLog[ActivityLog_Attachments_Cached]` column is not enough by itself. Verify the parent-side `SET_COLUMN_VALUE` action exists (observed name: `ActivityLog_Update_Cached_Attachments`) and recalculates the cache from child rows, e.g. `SELECT(ActivityLog_Attachments[ActivityLogAttachmentID], [ActivityLogID] = [_THISROW].[ActivityLogID])`.
   - Verify the child add process (`Process for ActivityLog_A_FlagProcess_0_New`) refreshes the parent after adding `ActivityLog_Attachments`. In the fixed wiring, the process first enqueues translation (`AL_A_Enqueue_TranslateRequest`), then runs the ref action from `ActivityLog_Attachments` back to `ActivityLog` (`Action for Updated ActivityLog cached Attachments 2`) which calls `ActivityLog_Update_Cached_Attachments` with `ReferencedRows = LIST([ActivityLogID])`.
   - Inspect scheduled backfills for infinite blank-cache loops. A backfill that selects `ISBLANK([ActivityLog_Attachments_Cached])` but marks processed rows with `Updater = "20260221"` must exclude that marker, not only an older marker such as `20260201`; otherwise parent rows with no attachments remain blank and re-enter every run.
   - After editor saves, reload `/api/loadApp` and verify `IsValid`, `IsRunnable`, `IsDeployable`, `Version == StableVersion` when promoted, plus the exact process/action names above. Then check runtime truth separately after the next scheduled run or by a bounded `appsheet_table_probe.py` sample.

8. **Cached-column transition phase 1 (June 2026)**
   - Do not set `NOW()` as the Initial Value for EnumList/Ref-list cache columns such as `ActivityLog_Children_Cached`, `ActivityLog_Session_Items_Cached`, or `ActivityLog_Attachments_Cached`; those must remain lists of refs.
   - Use a physical DateTime freshness marker instead. Observed implementation uses `ActivityLog[Last Updated]` with `Default = NOW()` and `ResetOnEdit = TRUE`.
   - For cache refresh actions, update both `ActionDefinition` and serialized `ActionSettings`; AppSheet readback may ignore changes if only the parsed action object is patched.
   - Do not wire the same AppSheet action object into multiple AppSheet processes. The editor can fail validation with `More than one process references action ...`. Clone the ref action with a distinct `Name`/`ComponentId` for each additional process, then point that process at its dedicated clone.
   - For view column-order changes, update both parsed `ViewDefinition.ColumnOrder` and serialized `Settings` JSON `ColumnOrder`; AppSheet readback may keep/reconstruct the old view order if only `ViewDefinition` is patched.
   - New child ActivityLog rows should trigger parent children-cache refresh. In the fixed wiring, `Process for ActivityLog_FlagProcess_0_New` runs both `AL_Group_EnqueueInitialWork` and `Action for Update Cached columns 3`, and that ref action calls `AL_0.70_RefreshChildrenCached` with `ReferencedRows = LIST([Parent ActivityLogID])`.
   - Cache refresh actions should also stamp `Last Updated = NOW()` so later backfill and coverage checks can distinguish freshly touched rows from untouched legacy rows.
   - Do not switch the remaining `Related ActivityLog_Attachments = REF_ROWS(...)` virtual formula until slow/paced backfill has proven records older than two weeks have populated physical caches.

9. **Inline deferral sequence and stale trace interpretation (June 2026)**
   - When add-row Performance Analyzer traces show user-facing `ActivityLog` / `ActivityLog_Attachments` adds spending 80-240s in inline process/actions, make one bounded deferral per AppSheet version and keep receipts plus a fast stable-version revert path. Useful candidates observed in sequence:
     - Remove/defer immediate ActivityLog child/cache refresh work from the user-facing add path while preserving background/HeartBeat repair paths.
     - Remove/defer inline `ActivityLog_Session_Items` parent status updates from set-status paths when they extend add/edit rows.
     - Remove immediate `AL_SetFlag_ReadyToProcess` from `AL_Group_EnqueueInitialWork`, but keep durable queue creation and HeartBeat wake actions (`AL_Enqueue_Init` and `ActivityLog_MarkHeartBeatReady_ActivityLogInit`).
     - Remove inline `ALA_TouchExistingThumbnailAttachmentJob` from `ALA_QueueThumbnailAttachment` while keeping enqueue/manual override paths (`ALA_ClearSiblingUseAsThumbnail`, `ALA_CancelExistingThumbnailAttachmentJobs`, `ALA_ManualSetParentThumbnail`, `ALA_EnqueueThumbnailAttachment_New`).
   - After a successful save/promote/readback, AppSheet Performance Analyzer can still show old serialized action names from old clients or in-flight process instances after the promotion cutoff. Do not assume the definition patch failed if fresh `/api/loadApp` readback shows the composite action children are absent. Label those rows as old-client/in-flight unless the same action names continue in a later clean window.
   - A clean definition readback is necessary but not sufficient. Run a delayed analyzer window and a later “status-now” window; separate definition truth from runtime truth in the report.
   - If post-deferral windows still show `Unable to find the specified row from AppSheet database` on `ActivityLog_Attachments` adds, keep focus on parent visibility/read-after-write and `ActivityLog_A_FlagProcess_0_New` / `Action for Updated ActivityLog cached Attachments 2`. Do not keep optimizing already-removed thumbnail/ready actions just because stale traces mention them.

10. **Phase 1 parent-dereference reduction on thumbnail enqueue (June 2026)**
   - `ProcessingQueue` helps only for work that has actually been moved out of the user-facing add path. It does **not** make parent dereferences unnecessary if formulas, bot conditions, `Valid_If`, or actions still reference `[ActivityLogID].[...]` during the add.
   - First low-risk mitigation: remove parent reads from the immediate thumbnail enqueue condition. Observed risky condition in `Process for ALA_ThumbnailAttachment_New` → `Branch_ShouldQueueThumbnailAttachment`:
     ```appsheet
     AND(
       ISNOTBLANK([ActivityLogID]),
       ISNOTBLANK([Images]),
       OR(
         ISBLANK([ActivityLogID].[Thumbnail]),
         [Use_as_Thumbnail] = TRUE
       )
     )
     ```
     Replace with row-local gating only:
     ```appsheet
     AND(
       ISNOTBLANK([ActivityLogID]),
       ISNOTBLANK([Images])
     )
     ```
     Let the queued/background thumbnail worker decide later whether the parent thumbnail needs updating, when parent and child rows are already committed.
   - When patching via `/api/saveapp`, update both the node `Condition` string and the parsed `ExprLookup.ConditionEvaluatable.SourceExpr` / child expression tree. Readback should show no `[ActivityLogID].[Thumbnail]` and no `[ActivityLogID].` in that node.
   - Keep the queue action itself (`ALA_QueueThumbnailAttachment` or successor) intact; this phase only changes the immediate IF condition so it enqueues based on row-local fields (`[ActivityLogID]`, `[Images]`) rather than reading parent fields.
   - Stable-promotion caveat: AppSheet may save the patched latest version while production stable remains on the previous version. If `Manage/SetStableVersion` returns `This feature is only available as part of an Enterprise plan`, first suspect the wrong/default cookie profile. Retry stable promotion with the admin/tailscale-login browser profile (`.../browser-profiles/tailscale-login/Default/Cookies`) before reporting a blocker. Verify both latest and stable via `/api/loadApp`; load the stable version explicitly and confirm this node has no `[ActivityLogID].[Thumbnail]` or `[ActivityLogID].` before saying production users are fixed.

## Reporting guidance

Lead with whether it is a permission problem or parent-visibility/cache/performance problem. Then separate:

- user setting/access findings,
- runtime log failures,
- Performance Analyzer bottlenecks,
- definition-level implementation risks,
- phased fix plan and verification.

Avoid markdown tables in Discord; use short labeled bullets.
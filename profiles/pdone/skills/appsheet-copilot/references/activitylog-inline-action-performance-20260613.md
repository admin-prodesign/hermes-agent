# ActivityLog inline action performance receipts (2026-06-13)

Use this note as a concrete receipt pattern for AppSheet performance work on ActivityLog add/sync paths. It is not a standalone procedure; pair it with `references/appsheet-performance-versioned-live-test-log.md` and `references/sync-performance-analyzer-triage.md`.

## Versions and receipts

- `26.061145`: removed/deferred an immediate `ActivityLog` child-cache refresh path. Receipt directory observed in-session: `/home/prodesign/.hermes/profiles/pdone/logs/appsheet-definition-edits/defer-activitylog-children-cache/...`.
- `26.061146`: removed `AL_S_UpdateParentALStatus` from `Action for Set Status to Resolved, Update Parent ActivityLog from Sessions`; final readback showed `Version == StableVersion == 26.061146` and valid/runnable/deployable all true. Receipt directory: `/home/prodesign/.hermes/profiles/pdone/logs/appsheet-definition-edits/defer-session-item-parent-status/20260613T000330Z`.
- Post-`26.061146` analyzer receipt: `/home/prodesign/.hermes/profiles/pdone/logs/appsheet-optimization-live/scans/status-now-20260613T002213Z`.
- `26.061149`: disabled two legacy/orphan `ActivityLog_Attachments` cache-refresh ref actions (`Action for Updated ActivityLog cached Attachments 2`, `Action for Update ActivityLog cached 3`) by setting their condition to `FALSE` and display prominence to `Do_Not_Display`, while preserving hourly maintenance and delete-time repair cache paths. Patch/save/promote receipt: `/home/prodesign/.hermes/profiles/pdone/logs/appsheet-definition-edits/disable-legacy-ala-cache-ref-actions/20260613T052528Z/summary.json`.
- Post-`26.061149` analyzer receipt: `/home/prodesign/.hermes/profiles/pdone/logs/appsheet-optimization-live/scans/post-26061149-20260613T054457Z/summary.json`.

## Analyzer outcome after `26.061146`

- Edit rows: under target in the sample; max detailed duration was about `9.73s`, zero failures.
- Sync rows: still above target; successful syncs had detailed durations up to about `121s` and median detailed duration around `16.9s`.
- Add rows: still above target; two successful `ActivityLog` adds had detailed durations around `98s` and `124s`.
- Workflow rows: `HeartBeat` still emitted `OperationCanceledException` failures.

## Trace signature that selected the next candidate

For the slow `ActivityLog` add rows, nested `Properties.Performance` timing pointed to:

```text
Process for ActivityLog_FlagProcess_0_New
  AL_Group_EnqueueInitialWork
    AL_SetFlag_ReadyToProcess
      ActivityLog_Attachments_Cached evaluation
```

One trace spent roughly `107s` evaluating `ActivityLog_Attachments_Cached`. This indicates the remaining add-row bottleneck was still an inline user-facing automation path, not the already-promoted session-item parent-status change.

## Reusable lesson

When a cache/materialization rollout improves one path but another operation remains slow, use the analyzer's nested timing tree to choose the next exact action, not just the table name. Prefer one bounded AppSheet version per action removal/deferral, and verify each version with:

1. save response,
2. stable promotion response,
3. fresh `/api/loadApp` readback,
4. clean post-promotion analyzer window,
5. operation-specific status for sync/add/edit/workflow,
6. revert path: previous stable version plus saved `before_loadapp_response.json`.

## Pitfall: old automation can appear after a clean definition readback

After `26.061149`, fresh definition readback showed the legacy actions disabled and the current `AL_A - New` process containing only `AL_A_Enqueue_TranslateRequest`, but the next analyzer still contained a few mentions of `Action for Updated ActivityLog cached Attachments 2` and old `Update ActivityLog cached attachments` steps. Treat this as an ambiguity to resolve, not proof that the save failed:

- Compare analyzer row timestamps against the exact stable-promotion timestamp; do not headline pre-promotion or straddling rows.
- If the old action appears only in the first delayed window, label it likely serialized old automation/client execution and run another clean post-cut window.
- If it persists after a clean window, inspect/remove the compiled event/process binding that is still emitting the step; condition-only guards may not be sufficient for that path.
- Keep preserved maintenance/repair paths explicit in the report so the user can see the change is bounded rather than a blind cache-refresh deletion.

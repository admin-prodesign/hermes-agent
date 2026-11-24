# ActivityLog session-items action audit

Use when asked whether ActivityLog has duplicate, misleading, or conflicting actions around refreshing or generating `ActivityLog_Session_Items`.

## Source of truth

- Sync/read the current `/api/loadApp` editor JSON first; do not rely on stale generated docs.
- Inspect `AppData.DataActions` from the raw definition and compare action definitions structurally, not just by action name or display name.
- For suspected duplicates, compare all behavior-relevant fields and ignore only identity/evaluator noise such as `Name`, `ComponentId`, `ExprLookup`, `ValueEvaluatable`, and `ConditionEvaluatable`.

## Known duplicate pattern: refresh cache vs generate items

A concrete audit of app version `26.052003` found these two `ActivityLog` actions are exact functional duplicates:

- `AL_0.70_RefreshSessionItemsCached`
- `AL_GenerateItems`

Both are `SET_COLUMN_VALUE` actions on `ActivityLog`, displayed as `Refresh Session Items List` / `刷新工作階段項目清單`, and both set:

```appsheet
[ActivityLog_Session_Items_Cached]
=
FILTER("ActivityLog_Session_Items", [ActivityLogID] = [_THISROW])
```

with the same condition:

```appsheet
AND(
  [ActivityLog_Session_Items_Cached] <> FILTER("ActivityLog_Session_Items", [ActivityLogID] = [_THISROW]),
  OR(
    CONTEXT("View") = "ActivityLog_All",
    CONTAINS(CONTEXT("View"),"_Detail")
  )
)
```

## Interpretation

- `AL_GenerateItems` is misleadingly named in this version: it does **not** generate missing `ActivityLog_Session_Items`; it only refreshes the cached list column.
- Actual generate/repair flow is separate, including actions such as:
  - `AL_Enqueue_GenerateItems`
  - `AL_Request_GenerateItems_Process`
  - `PQ_Run_GenerateItems_On_ActivityLog`
  - `AL_Repair_Enqueue_GenerateItems`
  - `HeartBeat_AL_Repair_NG_MissingSessionItems`
- Before recommending deletion/hiding, recursively search the editor JSON for references to both action names in composite actions, reference actions, views/action bars, bots, processes, and tasks.

## Safe removal/update procedure

When the user asks to remove the misleading duplicate action:

1. Sync or load the latest editor definition first and work from raw `/api/loadApp` JSON.
2. Verify the target action and the keeper action are both present in `AppData.DataActions`.
3. Scan recursively for target/keeper action-name references outside `AppData.DataActions`, with an explicit breakdown for `Behavior.AppBots`, `Behavior.AppProcesses`, `Behavior.AppEvents`, and `Behavior.Tasks`.
4. If references are zero and the user has approved the bounded deletion, remove only the target action from `AppData.DataActions` and save the latest editor version. Do **not** promote stable unless explicitly requested, because stable promotion may deploy unrelated unpublished changes.
5. Reload/sync after save and verify: target count `0`, keeper count `1`, app `IsValid`/`IsDeployable`/`IsRunnable` true, and no final references to the target action.
6. If the user asks what else would be deployed by stable promotion, run an unpublished-change audit: fresh-sync latest, compare latest raw app with a raw history snapshot whose `Version == StableVersion`, and ignore AppSheet evaluator/cache/statistical noise (`ExprLookup`, `InternalQualifier`, `ColumnStats`, compiled `*_AppEval`, `LocaleName` drift on process-output pseudo tables, timestamps/versions). Report meaningful design/config differences by actions, datasets/schemas, slices, views, format rules, bots, events, processes, and tasks.
7. Preserve verification artifacts under ignored `projects/AppSheet/exports/...` paths. Commit/push only the AppSheet definition backup files unless the user requests additional artifacts.

### 2026-05-20 removal result

`AL_GenerateItems` was removed from latest editor version `26.052004` while `AL_0.70_RefreshSessionItemsCached` was kept. Pre-removal and post-removal recursive scans found no references to `AL_GenerateItems` in bots/processes/events/tasks or anywhere outside `AppData.DataActions`. Stable remained `26.052002` (not promoted). Definition backup commit: `af54886` in `admin-prodesign/openclaw-backup`.

## Recommended user-facing answer

Keep it operational and concise:

- State current app version checked.
- Name the duplicate actions.
- Show the shared target column/expression.
- Explain the naming risk: cache refresh is not item generation.
- If removal was performed, report latest version, stable version, target/keeper counts, validation status, and backup commit/push status.
- If removal is only being proposed, recommend keeping the clearer cache-refresh action and hiding/removing/renaming the misleading duplicate only after a dry-run/readback confirms no internal references or user-facing dependencies.

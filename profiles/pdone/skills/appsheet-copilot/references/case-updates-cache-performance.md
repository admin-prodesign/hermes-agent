# Case Updates Cached Parent-Side Performance Pattern

Use this reference when AppSheet sync slowness points to `Case[Related Case_Updates]`, `Case_Updates` row loading, or parent/child virtual-column cost.

## Pattern

When user-specific case visibility prevents hard-coding visibility into child rows, first add/use a user-independent parent-side cache on `Case` rather than changing per-user security semantics.

For Pro-Design's deployed app, parent-side update history should be physical/cache-backed, not dependent on `Case[Related Case_Updates]` during normal sync:

- `Case[Case_Updates_Cached]` is a physical `EnumList` of `Ref` values to `Case_Updates` (not a VC).
- `Case[Case_Updates_en]` and `Case[Case_Updates_zh-tw]` are physical `LongText` running history fields intended to compile Case_Updates timestamp + summary + description onto the parent Case, so history remains visible even when older `Case_Updates` rows are not loaded.

These can be maintained by the existing parent sync path:

```text
Case_Updates_RunParentSyncFromPQ
  -> Case_Updates_UpdateCaseWithLatestCaseUpdateID
  -> Case_Updates_UpdateCaseInformationFromCaseUpdate
  -> Case_UpdateFromLatestCaseUpdate
```

A safe cache-maintenance assignment for `Case_UpdateFromLatestCaseUpdate` is:

```appsheet
=IF(
  OR(
    ISBLANK([Latest_CaseUpdateID]),
    IN([Latest_CaseUpdateID], [Case_Updates_Cached])
  ),
  [Case_Updates_Cached],
  LIST([Latest_CaseUpdateID]) + [Case_Updates_Cached]
)
```

This prepends the latest update ID and avoids duplicate IDs. It preserves user-dependent case visibility because the cache is case-local; it does not encode which users can see the case.

## Definition-level replacement proposal for `Related Case_Updates`

When Performance Analyzer repeatedly flags `Case[Related Case_Updates]` and `Case_Updates` as sync bottlenecks, the preferred first definition dry-run is a narrowly scoped formula replacement on the existing virtual column:

```diff
Case[Related Case_Updates]
- =REF_ROWS("Case_Updates", "CaseID")
+ =[Case_Updates_Cached]
```

Rationale:

- Keeps the existing column name so dependent views/actions/templates can continue referencing `Related Case_Updates`.
- Avoids recalculating the reverse reference by scanning the large `Case_Updates` table during sync.
- Uses the already-maintained physical parent cache instead of introducing new tables, security filters, or workflow semantics.

Dry-run validation is mandatory before live save/promotion because AppSheet may treat `Related Case_Updates` as a `List` VC while `Case_Updates_Cached` is a physical `EnumList` of refs. Validate with `/api/saveapp` and require `Success=true`, `IsValid=true`, `IsRunnable=true`, no new type/ref warnings, and fresh `/api/loadApp` readback proving the formula persisted. If the direct assignment is rejected, try a typed/coercion fallback such as `=LIST() + [Case_Updates_Cached]` and validate again. Do not bundle this patch with unrelated bottleneck fixes; isolate it for clean analyzer before/after comparison.

## Editor API pitfall

When editing an existing AppSheet action's assignments through `/api/saveapp`, update **both** places:

- `DataAction.ActionDefinition.Assignments`
- JSON-decoded `DataAction.ActionSettings.Assignments`

If only `ActionDefinition` is patched, `/api/saveapp` can return `Success: true`, advance the version, and then drop the added assignment on reload because AppSheet rebuilds the typed definition from `ActionSettings`.

Verification must reload `/api/loadApp` and confirm the assignment exists in both `ActionDefinition` and `ActionSettings`.

## Stable promotion notes

Before promoting stable, verify:

```text
IsValid == true
IsRunnable == true
IsDeployable == true
ActionDefinition cache assignment count == 1
ActionSettings cache assignment count == 1
```

If `Manage/SetStableVersion` returns HTTP 200 with `Success: false` and `ErrorDescription: "This feature is only available as part of an Enterprise plan"`, retry with the proven admin/editor Chromium cookie profile used by AppSheet patch scripts (for example `workspace/browser-profiles/tailscale-login/Default/Cookies` plus matching `Local State`) and then reload to verify `StableVersion == Version`.

After stable promotion, run the AppSheet definition sync and commit/push the refreshed latest definition snapshots.

## 2026-06-12 live implementation receipt

The narrow replacement was saved and promoted successfully in the live Pro-Design AppSheet app as stable version `26.061141`:

```diff
Case[Related Case_Updates]
- =REF_ROWS("Case_Updates","CaseID")
+ =[Case_Updates_Cached]
```

Validation/readback requirements that worked:

- `/api/saveapp` returned `Success=true` and advanced the draft to `26.061141`.
- Fresh `/api/loadApp` readback showed `Version=26.061141`, `StableVersion=26.061141`, `IsValid=true`, `IsRunnable=true`, `IsDeployable=true`.
- The formula persisted exactly as `=[Case_Updates_Cached]`; no `LIST() + ...` coercion fallback was needed.
- Receipt directory: `/home/prodesign/.hermes/profiles/pdone/logs/appsheet-definition-edits/case-related-updates-cached/20260612T160605Z/`.

Revert path:

- Fast functional revert: promote stable back to the immediately previous stable version (`26.061140` in this rollout).
- Targeted forward revert: save a new version restoring `=REF_ROWS("Case_Updates","CaseID")`, then promote only after valid/runnable/deployable readback.

Analyzer interpretation pitfall: do not headline a Performance Analyzer window that spans the save/promote interval. In this rollout, a 30-minute sync window contained a long sync failure at `16:10 UTC`, but the final stable promotion readback was `16:11 UTC`; treat such mixed windows as context only and rerun a post-cutoff window before judging the change.

## Backfill safety gates

For historical `Case` rows, use an offline aggregation + AppSheet Data API `Edit` against `Case` only. Do not edit backing sheets directly and do not create/delete `Case_Updates` as part of the cache backfill.

Before live writes, produce a dry-run artifact with:

- source `Case` count and `Case_Updates` count
- parent cases with grouped updates and rows planned for edit
- missing parent refs (`Case_Updates[CaseID]` not found in `Case`)
- duplicate `Case_Updates[CaseUpdateID]` values
- sample before/after payloads
- max generated `Case_Updates_en` / `Case_Updates_zh-tw` lengths and truncation count

Stop before live execution if duplicate `CaseUpdateID` values exist. `Case_Updates_Cached` is a Ref EnumList, so duplicate child keys make the parent cache ambiguous even if AppSheet currently tolerates the source rows. Repair or exclude duplicates explicitly, then rerun dry-run and execute in bounded chunks with readback receipts.

Recommended aggregation:

- group `Case_Updates` by nonblank `CaseID`
- sort newest first by `Timestamp`, with stable fallback by update id / row order
- `Latest_CaseUpdateID` = newest update id
- `Case_Updates_Cached` = newest-first deduped list of update ids
- `Case_Updates_en` / `Case_Updates_zh-tw` = compiled readable history using translated summary/description fields with fallback to original fields

Execution receipts should include attempted/succeeded/failed counts, per-chunk readback samples, final nonblank cache count, and representative cases where `Latest_CaseUpdateID` and `Case_Updates_Cached` match the source aggregation.

## What this does and does not solve

- Helps remove or reduce dependence on expensive `[Related Case_Updates]` virtual-column evaluation in views/slices/actions.
- A cache-maintenance assignment alone is not enough if historical `Case` rows have blank `Latest_CaseUpdateID` / `Case_Updates_Cached`, or if views/slices/tasks still expose `[Related Case_Updates]`. Verify cache coverage with a bounded Data API pull before claiming improvement; if most caches are blank, plan an approval-gated data backfill first.
- `Case_UpdateLatestCaseUpdateID` may still compute `INDEX(ORDERBY([Related Case_Updates], [Timestamp], TRUE), 1)`, so parent-sync actions can continue invoking the expensive VC even after cache assignment exists. Treat that as a separate definition optimization from the physical cache backfill.
- Does not by itself reduce all `Case_Updates` row loading if security filters still broadly expose child rows.
- Best staged rollout: cache/backfill first, replace expensive UI references with cache where safe, then consider child table security-filter tightening.
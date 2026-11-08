# Prototype/Data Studio AppSheet performance review

Use when reviewing whether a cloned/prototype AppSheet app is “optimized” when its purpose is full data reads/writes and feeding Google Data Studio / Looker Studio.

## Interpretation pattern

A Data Studio/full-access prototype has different optimization goals than a human-facing mobile app:

- Full data reads usually mean few/no security filters, so client syncs can be slow by design.
- A clean runnable app (`IsValid=true`, `IsRunnable=true`, `appErrors.Errors=[]`) proves definition correctness, not load-speed optimization.
- For this class of app, answer separately for:
  1. correctness / full-data availability,
  2. Looker/Data Studio completeness,
  3. human interactive loading speed.

Do not call it “optimized” solely because validation errors are gone.

## Verification workflow

1. Fresh-load `/api/loadApp/<appId>` and report `Version`, `IsValid`, `IsRunnable`, and `appErrors`.
2. Inspect definition shape:
   - number of datasets/tables, slices, views, and actions;
   - `Behavior.DeltaSync`, `Behavior.IncrementalSync`, `Behavior.SyncOnStart`;
   - presence/absence of table-level security filters;
   - virtual-column count and obvious heavy expressions (`REF_ROWS`, `SELECT`, `LOOKUP`).
3. Pull fresh sync-only `/manage/exportlog` Performance Analyzer data for the prototype app.
   - If the standard exportlog helper cannot read the Chrome `Local State` file because of filesystem ownership, do not record “exportlog broken”; use the authenticated cookie-loading path that already works for `/api/loadApp`, or repair the ownership separately if approved.
   - Parse `Properties.Performance` with `scripts/perf_raw_timing_analysis.py` rather than relying on top-level rows.
4. Rank table and virtual/computed-column timings. Use p90 plus max; sample size must be stated.
5. If post-fix sample size is tiny, call it directional, not conclusive.

## Known prototype-app pattern

For prototype app `3d6f2d39-9f45-488a-9f5d-6a931d83bd63` after definition-error cleanup:

- Readback was clean/runnable (`IsValid=true`, `IsRunnable=true`, `appErrors.Errors=[]`).
- Definition had broad/full-data shape: 33 datasets/schemas, 124 slices, 168 views, 162 actions, no table-level security filters, only 2 virtual columns.
- Settings: `DeltaSync=true`, `IncrementalSync=false`, `SyncOnStart=true`.
- 24h Performance Analyzer sync samples showed slow full syncs despite low VC cost: p90 around 116s, max around 220s.
- Main table bottlenecks were `ActivityLog`, `ActivityLog_Attachments`, `Case_Updates`, `Maintenance_Session_Items`, then `Reference_Documents`, `Lookup`, and `Case`.

Recommended answer shape:

> Clean/runnable and suitable as a full-data/Data Studio service prototype, but not optimized for human loading speed. The bottleneck is broad full-table syncs on large historical tables, not validation errors or virtual-column formulas.

## Safe optimization recommendations

For full-data/Data Studio purpose, prefer separating roles instead of filtering away needed rows:

1. Keep the full-data prototype for Looker/Data Studio/backend/full access.
2. Create or tune a separate human-facing writer app with date/security filters.
3. Consider incremental sync only after verifying reliable physical `Last Updated` / change timestamp columns on heavy tables.
4. Remove/hide unused views, actions, and slices if the prototype is not meant for interactive navigation.
5. Investigate row volume and source layout for `ActivityLog` and `ActivityLog_Attachments` first, because they dominate sync time.
6. Avoid adding security filters to the Data Studio service app unless the requester explicitly accepts incomplete historical reads.

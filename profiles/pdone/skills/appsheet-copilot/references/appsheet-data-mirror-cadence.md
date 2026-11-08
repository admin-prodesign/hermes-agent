# PD One AppSheet Data Mirror cadence

Use when Andy/admin asks how fresh the `PD One - AppSheet Data Mirror` is, how often it pulls AppSheet/prototype data, or whether dashboard/analysis tabs are live enough for operational use.

## Source-backed nominal cadence

The internal Google Sheets registry entry for `PD One - AppSheet Data Mirror` records this configured/nominal refresh design:

- Recent `ActivityLog`: `syncActivityLogRecent()` every 15 minutes.
- ActivityLog-related tables: hourly.
- Rolling-overlap batches: every 4 hours.
- Low-change reference/full batch: every 4 hours.
- Full rebuild: weekly.

Important caveat: report this as the configured/nominal cadence unless you have just performed a live trigger audit. The registry says `syncHeartBeat()` was manually verified on 2026-04-29 and periodic mirror functions were added on 2026-04-30, but Apps Script Execution API runs may still have Cloud-project binding issues; trigger installation/manual runs may require the Apps Script editor.

## Recommended answer shape

Lead with the cadence in bullets, then add the caveat:

> Nominally, the mirror refreshes recent `ActivityLog` every 15 minutes, related ActivityLog tables hourly, rolling/reference batches every 4 hours, and does a weekly full rebuild. I’m calling that the configured cadence, not a fresh live-trigger audit, unless I have checked the Apps Script triggers/readback in this session.

For Mattermost group/channel replies, keep this bilingual English + Traditional Chinese per Hermes PD One policy.

## Verification path when a live audit is requested

A live trigger audit is higher-impact Google Workspace/AppScript inspection. Use normal approval/safety rules, then verify from Apps Script trigger metadata or the `_SyncLog` / heartbeat/readback rows rather than relying only on the registry note.

## Column drift handling

As of the 2026-05-27 patch, the bound Data Mirror Apps Script expands the write schema for every table from actual AppSheet API response keys before full writes or incremental upserts. This prevents newly added AppSheet/source columns from being omitted just because the stored local schema snapshot is stale; extra response columns are appended as `API Response Column`. `_SyncLog` is sorted newest-first after each append. If Apps Script `scripts.run` returns `404 notFound` due to Cloud-project/API binding issues, source upload can still be verified with `projects.getContent`; sheet-level verification may require either the next trigger run, Apps Script editor execution, or a bounded direct Sheets/API verification backfill approved by Andy/admin.

## Late-edit staleness handling

A dashboard value can be wrong even when the mirror is recently updated if the incremental selector only revisits rows by original `ActivityLog[Timestamp]`. During the QA dashboard 5S audit, direct AppSheet/prototype API showed `張伊妘 ZHANG YIYUN (VIVIAN)` had 17 May 2026 `5S Action` rows totaling 24 points, while the mirror had the same row IDs but 7 rows from 2026-05-27 through 2026-05-29 still had blank `Performance Points`, so the dashboard totaled 16. The likely mechanism was late edits/scoring on old ActivityLog rows after the last full sync; timestamp-based incremental refresh did not revisit them.

When a Data Mirror value disagrees with Data Studio/Looker Studio or direct AppSheet:

1. Pull the disputed rows directly from AppSheet API in the prototype/admin context.
2. Pull the same row IDs from the mirror sheet.
3. Compare key fields row-by-row, not only aggregate totals.
4. Check `_SyncLog` for the latest full table sync and whether incremental entries use a timestamp cutoff.
5. Prefer targeted backfill/full rebuild of affected rows before changing dashboard formulas.

## Targeted Sheets backfill fallback

If the live Apps Script execution channel is unavailable (for example `gog appscript run ...` returns 403 or transient TLS/API failures) but Andy/admin has approved the fix, a bounded fallback is to:

1. Pull the stale row IDs directly from AppSheet API using a stable-key selector such as `FILTER("ActivityLog", IN([ActivityLogID], LIST(...)))`.
2. Re-read the same rows from the Data Mirror sheet to resolve current sheet row numbers and confirm the stale fields are still blank/wrong.
3. Update only the approved mirror cells for those row IDs (for the QA 5S incident: `Performance Points` and `Has Performance Points` in `ActivityLog!AC:AD`). Do not whole-sheet rewrite.
4. Re-read the disputed aggregate from both the mirror table and the user-facing dashboard/helper tab.
5. Report that this was a targeted manual backfill, not proof that unattended incremental sync is fully healthy.

During the 2026-06-05 QA 5S repair, this fallback updated seven stale `ActivityLog` rows for `張伊妘 ZHANG YIYUN (VIVIAN)` / `P-d9e6fdfc`; mirror and dashboard readback then showed 17 May 2026 5S rows totaling 24 with zero blank points.

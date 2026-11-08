# AppSheet Database migration performance assessment

Use when asked whether moving tables from Google Sheets to AppSheet Database will improve AppSheet performance, or which tables to migrate.

## Core workflow

1. **Do not assume Google Sheets is the bottleneck.** Inspect the deployed/exported app definition and Performance Analyzer timing first.
2. In app definition JSON, compare each `AppData.DataSets[]` entry:
   - `ProviderName = "google_tables"` usually means AppSheet Database.
   - `ProviderName = "google"` usually means Google Sheets/Drive-backed table.
   - Also capture `SourcePath`, `SourceQualifier`, `DataFilter`, and `ServerCachingInterval`.
3. Parse the current sync Performance Analyzer raw timings and rank by p90 table timings and p90 virtual/computed-column timings.
4. Join the timing ranking to the provider/source map. Answer the real question:
   - If top slow tables are already `google_tables`, a Sheets→AppSheet DB migration is not the main sync fix.
   - If top slow tables are `google`, then migration might help, but still check row volume, formulas, security filters, and virtual columns.
5. Separately classify runtime/automation failures such as `HeartBeat`/`ProcessingQueue` cache locks or grid-limit issues. These can justify moving helper/queue tables even when they are not top sync table-load bottlenecks.

## Interpretation guidance

### Good AppSheet Database migration candidates

Prioritize small-to-medium AppSheet-owned operational/helper tables where Google Sheets causes append, concurrency, or grid-limit reliability pressure:

- `ProcessingQueue`
- `API_Target_Queue`
- `HeartBeat` after verifying scheduled-event/action behavior
- `RowCount` only after deciding whether physical cached counts can replace expensive realtime count VCs
- `GoogleTranslate` only if schema/grid mismatch or edit reliability keeps recurring
- Small lookup tables such as `Customers`, `Customer_Details`, `HR_OperatorCodes`, if consistency is desired

### Poor first candidates / caution

Be careful with tables whose source of truth is an external import, Google Form, ERP/HR export, or spreadsheet workflow:

- Google Form response tables, unless an ingestion bridge is built
- ERP/HR generated/import tables where moving would change freshness/source-of-truth responsibility
- Large historical operational tables that are already AppSheet DB-backed and slow because of formulas or visibility design

### Bigger wins than migration

If Performance Analyzer shows expensive VCs or reverse references, prefer formula/cache work over source migration:

- Replace broad `REF_ROWS()`/`SELECT()` reverse-reference virtual columns with maintained physical cache columns where safe.
- Replace realtime count VCs (`Lookup[RowCount_Realtime]`, `RowCount[Count_RealTime]`) with physical cached counts or de-scope them from normal sync surfaces.
- Tighten security filters/data windows and avoid dynamic parent-list filters that still pull large row sets.
- Separate user sync bottlenecks from automation queue pressure.

## AppSheet Database limits to mention

Official AppSheet Database limits vary by subscription. Current documented hard technical limits include:

- 20 tables per AppSheet database
- 100 columns per table
- 2,000 characters per cell
- 5,000 characters per `LongText` cell

Plan-level row limits matter:

- Free: about 1,000 rows per database
- Starter/Core/Publisher Pro: commonly 2,500 rows per database
- Enterprise Plus: 200,000 rows per database, potentially increasable through AppSheet Sales

If tables are large or expected to grow substantially, consider Cloud SQL rather than AppSheet Database.

## Report shape

Keep the answer operational:

1. Direct yes/no: “Migration may help reliability, but not the main sync bottleneck” or “Yes, these Sheets-backed timed tables are good candidates.”
2. Evidence: timing window, sample count, top slow tables with p90 and provider/source.
3. Ranked migration candidates with reason.
4. Bigger non-migration performance fixes.
5. Approval gates: any definition save, stable promotion, row backfill, source-system change, or Drive/Sheets change needs explicit approval and readback verification.

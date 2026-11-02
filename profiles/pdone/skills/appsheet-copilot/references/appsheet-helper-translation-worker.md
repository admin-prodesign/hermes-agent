# AppSheet Helper translation worker: wrong-row / row-drift debugging

Use when `AppSheet Helper` / `GoogleTranslate` rows show translations copied to the wrong row, one-row-lag behavior, or suspicious results after many rows are generated quickly.

## Failure signature

- `GoogleTranslate[OriginalText]` does not match `Translated_en` / `Translated_zh-tw`.
- Adjacent rows look shifted: row N's translation appears on row N+1, or a short source text receives the previous row's long translation.
- The audit tab can show `TRANSLATION_STARTED` / `TRANSLATION_WRITTEN` / `PUSHBACK_ATTEMPT` keyed to a row number that later belongs to another `GoogleTranslateID`.

## Root cause pattern

The bound Apps Script `processTranslations()` reads a snapshot with `getDataRange().getValues()` and then writes by numeric `sheetRow`. During bursts, AppSheet or cleanup code can add/delete/reorder rows while the worker is running. The row number from the snapshot is then no longer a stable identity, so later `setValue()` or pushback can mutate the wrong live row.

Treat sheet row numbers as volatile. Treat `GoogleTranslateID` as the row identity.

## Investigation checklist

1. Bound the scan window first, usually `now - 24h` for fresh user reports, and capture the UTC/Taiwan-time window in the final report.
2. Read current `GoogleTranslate` rows from the physical Google Sheet (`GoogleTranslate!A:N`) when checking row-shift or column-shift damage. Do not rely only on AppSheet `Find` output for this helper table during a suspected sheet/schema incident: damaged or extra physical columns can make API field alignment misleading, while the sheet read shows the actual header/value positions.
3. Compare each row's `GoogleTranslateID`, `OriginalText`, `Translated_en`, `Translated_zh-tw`, and `Status`.
4. For bounded semantic checks, it is acceptable to hand the compact row set to `utility-agent`: ask it to classify each row as `OK`, `MISMATCH`, or `PENDING`, and to return JSON with row number, ID, source key/column, reason, and suggested corrected translations for non-OK rows.
5. Read `GoogleTranslate_Audit` for the same `GoogleTranslateID` values, not just the row numbers, when audit history is needed.
6. Compare the audit event sequence per ID:
   - `TRANSLATION_STARTED`
   - `TRANSLATION_WRITTEN`
   - `PUSHBACK_ATTEMPT`
   - `Success: Pushed @ ...` status changes
7. Re-read the live AppSheet target rows by stable source keys (`SourceTable`, `SourceKeyColumn`, `SourceRowKey`) and compare the target translation fields with the bad helper translations. This separates helper-row damage from actual pushed target damage.
8. Treat rows with blank translation columns as `PENDING`, not mismatches, unless their target row already contains a bad pushed value.
9. If rows were generated quickly, assume row-number drift until ruled out.
10. Do not conclude that AppSheet inserted the wrong data unless the row identity trace proves the source payload was wrong. First rule out spreadsheet-side consumer drift.

## Robust fix pattern

In Apps Script workers that consume AppSheet helper rows:

- Require the ID column in the header map, e.g. `GoogleTranslateID`.
- Capture the ID from the snapshot row.
- Immediately before every live write, re-resolve the current row by ID.
- After slow calls such as `LanguageApp.translate()` return, re-resolve by ID again before writing translation values; the row may have moved while the external call was running.
- Before writing a translation result, compare the live row's `OriginalText` to the text that was translated. If it changed, log and skip instead of writing a translation for stale content.
- Re-read the row by ID again before pushback.
- Write statuses/errors/success markers by ID too; do not leave status writes as the remaining stale `sheetRow` path.
- If the ID cannot be found, log and skip; do not fall back to the old row number.
- Add audit event names for guard behavior (`ROW_ID_DRIFT_CORRECTED`, `ROW_ID_NOT_FOUND_SKIP`, `TRANSLATION_WRITE_SKIPPED_ROW_MISSING`, `TRANSLATION_WRITE_SKIPPED_CONTENT_CHANGED`, `PUSHBACK_SKIPPED_ROW_MISSING`) so future incidents can distinguish corrected drift from missing/deleted rows.
- Keep `LockService` but do not treat it as enough: it only serializes script runs, not concurrent AppSheet writes or sheet mutations.

Sketch:

```javascript
function findRowByValue_(sheet, columnIndexZeroBased, value) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return -1;
  const values = sheet.getRange(2, columnIndexZeroBased + 1, lastRow - 1, 1).getValues();
  for (let i = 0; i < values.length; i++) {
    if (String(values[i][0]) === String(value)) return i + 2;
  }
  return -1;
}

// Before writing translations:
const googleTranslateId = row[col.googleTranslateId];
const liveRow = findRowByValue_(sheet, col.googleTranslateId, googleTranslateId);
if (liveRow < 0) {
  // log missing row and skip
  continue;
}
sheet.getRange(liveRow, col.transEn + 1).setValue(en);
sheet.getRange(liveRow, col.transZh + 1).setValue(zh);

// Before pushback, re-read live row by ID rather than using the old sheetRow.
const pushRowNumber = findRowByValue_(sheet, col.googleTranslateId, googleTranslateId);
if (pushRowNumber < 0) continue;
const freshRow = sheet.getRange(pushRowNumber, 1, 1, headers.length).getValues()[0];
```

## ARRAYFORMULA note

ARRAYFORMULA/`GOOGLETRANSLATE()` can reduce script writes for the translation columns, but it does not remove the need for identity-safe pushback into AppSheet. If a worker still pushes values back or marks statuses, it must still re-resolve by `GoogleTranslateID` before touching live rows.

## Historical repair / backfill pattern

When wrong-row translations may already have reached the AppSheet target rows (for example `ActivityLog` Incident Reports):

1. Bound the scan window first (e.g. last 7 days or the known incident window) and work latest-first if the user cares most about recent operational records.
2. Pull parent target rows from AppSheet by stable keys (`ActivityLogID`, `SourceRowKey`, target table key), not by helper sheet row number.
3. For `ActivityLog` Incident Reports, use the exact source/translation pairs:
   - `Description` -> `Description_en`, `Description_zh-tw`
   - `Troubleshooting Actions` -> `TroubleshootingActions_en`, `TroubleshootingActions_zh-tw`
   Do **not** infer a source column named `TroubleshootingActions`; that is the translation-column prefix, not the source field. A wrong source-field name can make valid troubleshooting translations look unsupported and cause accidental clearing.
4. Heuristically flag only fields that are blank or obviously mismatched for their expected language; do not bulk retranslate every row unless the user asks.
   - English field still containing mostly Chinese is suspicious.
   - Traditional Chinese field missing for a Chinese/English source is suspicious.
   - A translated field whose substance clearly belongs to a neighboring source row is suspicious.
5. Correct only the flagged fields with a dry-run/reviewable payload when writes are involved, then execute once scoped.
6. Re-read every edited row and compare each intended translated field to the correction payload.
7. Re-scan the whole bounded window and report remaining heuristic issues separately from the number of rows edited.
8. In the final report, include row keys and field names fixed, plus explicit cost-control wording if you avoided bulk retranslating unaffected rows.

## AppSheet API 404 / row-not-found pushback pattern

When `GoogleTranslate[Status]` shows `Push error ... Row having key '<SourceRowKey>' not found`:

1. First verify whether the source row exists in the same AppSheet app/context used by the pushback script, not only in a prototype or mirror app.
2. Compare prototype/Data Studio vs deployed API reads for the same key. If Data Studio sees the row but deployed returns zero rows, treat the 404 as an app-context/security-filter/visibility problem for that API principal, not proof that the row is physically absent.
3. For Pro-Design `GoogleTranslate` pushback, prefer the Data Studio prototype app context (`projects/AppSheet/keydrop/prototype-app.env`, app id `3d6f2d39-9f45-488a-9f5d-6a931d83bd63`, run-as `admin@prodesign-group.com`) when the target rows can be hidden by deployed app security filters, especially legacy `Case_Updates` imports. The helper is a back-office data repair/translation service, not a deployed-user workflow.
4. Do not implement the context switch as only replacing app credentials and blindly retrying. Safe pushback should `Find` the source row by `SourceKeyColumn = SourceRowKey` in the chosen app context, require exactly one match, then `Edit` only the intended target translation columns.
5. Prefer fixing the bound Apps Script directly when its project ID/URL is known. Use a Hermes-side shim only as a temporary mitigation, then pause/remove it after the bound worker is patched and verified.
6. Still inspect the helper row for row-drift symptoms: if `OriginalText` and `Translated_en`/`Translated_zh-tw` clearly belong to different source texts, the worker is writing/pushing by stale sheet row number and must be fixed before retrying rows.
7. Do not blindly retry all `Push error` rows until both are true: the source row is visible to the script's API context, and each helper row's translated text matches its own `OriginalText`.
8. For Data Studio/prototype pushback, do a `Find` by `SourceKeyColumn`/`SourceRowKey` first, then `Edit` with the key field AppSheet requires for that app/table. Do not assume AppSheet DB physical `Row ID` is the API edit key; for `Case_Updates` in the Data Studio app, the API requires `CaseUpdateID`.
9. If an old worker has already marked an obvious wrong-row translation as success, only clear target fields when the source row still matches `OriginalText` and the source target field exactly equals the bad helper translation; otherwise skip rather than wiping human-corrected or already-changed data.

## Purge / retention starvation pattern

When successful `GoogleTranslate` helper rows are not purging even though `processTranslations()` has a `Success: Pushed @ ...` age check:

- Count the whole `GoogleTranslate!A:N` range from a saved `gog sheets get ... --json` file; large outputs can exceed tool stdout caps, so parse from a temp file rather than trusting truncated tool output.
- Check for `Success: Pushed @` rows older than the intended retention window and compare their physical row numbers with recent `GoogleTranslate_Audit` `TRANSLATION_*` / `PUSHBACK_ATTEMPT` row numbers.
- If old successes sit far above the newest appended rows, and recent audit events only reference high row numbers, the bottom-up worker is being starved: it spends the run translating/pushing newer rows before it reaches older successes. Apps Script time limits can prevent the purge branch from ever reaching the old block.
- Root fix: split retention into a cheap first pass or separate trigger that deletes/compacts old `Success: Pushed @` rows before any slow `LanguageApp.translate()` / AppSheet `Find` / `Edit` calls, and cap translation/push work per run. Include `Success: DataStudio push @` if any temporary shim statuses still exist.
- Use `GoogleTranslateID` as the identity for cleanup: scan row snapshots only to collect candidate IDs, then re-resolve each live row by ID and revalidate status/age immediately before deleting. Row numbers are only acceptable as the final Sheets coordinate after ID resolution.
- For large success purges, avoid one `deleteRow()` per record with per-row audit; it can time out after only a few dozen rows. Prefer row-level audit snapshots plus grouped `deleteRows(startRow, count)` for contiguous validated ranges.
- After grouped deletes, blank/no-ID rows may appear or be exposed. In `processTranslations()`, skip rows without `GoogleTranslateID` before filling `CreatedAt` or doing any status/cleanup/translation work; otherwise the worker turns harmless blank rows into persistent CreatedAt-only pseudo-records.
- Avoid relying on the combined worker's bottom-up loop for both slow pushback and cleanup under bursts; cleanup should not require reaching old rows after hundreds of pending/newer rows.

## Verification

- Create or identify a burst of fresh translation rows.
- Confirm every tested row has `OriginalText` semantically matching both translated columns.
- Confirm no adjacent row has the previous row's translation.
- Confirm audit events for sampled `GoogleTranslateID` values stay consistent even if row numbers changed.
- Confirm AppSheet target row fields match the intended `SourceRowKey` and target columns, not merely that the helper row says `Success`.
- For 404 pushback errors, verify the row is visible in the exact AppSheet app/API context used for pushback; compare deployed vs Data Studio/prototype if legacy imports or security filters are involved. For Pro-Design helper pushback, Data Studio is usually the safer write context because it avoids deployed app security-filter blind spots.
- After historical repair, re-read edited AppSheet rows and re-scan the bounded source window; report both successful field-level readback and remaining heuristic issue count.

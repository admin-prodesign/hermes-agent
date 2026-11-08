# HR new-hire Google Form to HR_Employees transport sync

Use this when asked to populate or retry-populate `HR_Employees` from the new-hire Google Form response sheet, especially transport method and license plate fields.

## Source and target pattern

- Source spreadsheet: new-hire response workbook, tab `新進人員基本資料`.
- The usable header row is row 2, not row 1. Important columns observed:
  - `時間戳記`
  - `工作種類 Role`
  - `中文名字 Chinese Name`
  - `英文名字 English Name`
  - `手機號碼 Cellphone`
  - `LINE ID`
  - `Gmail`
  - `Microsoft 微軟`
  - `交通方式 Transport Method`
  - `車牌 License Plate Number`
  - `填入AppSheet`
  - `拼音名字`
  - `工號`
  - `公司 email`
- Target AppSheet table: `HR_Employees`.
- Verify the key from raw `/api/loadApp` before writes. Current key: `PersonID`.
- Current target columns:
  - `Transport Method` (`EnumList`, values from `Lookup_Dropdown_HR_TransportMethod` / `Lookup` rows where active Type + `Transport Method`)
  - `Moped License Plate`
  - `Car License Plate`

## Current transport values

Active lookup IDs observed for `Transport Method`:

- `Moped` = 機車
- `Car` = 汽車
- `Heavy Motorcycle` = 重型機車 (>250cc)
- `Electric Scooter` = 電動自行車
- `Bicycle` = 腳踏車

For AppSheet API EnumList payloads, preserve the app's observed separator style (`Moped , Car`) unless fresh readback shows a changed serialization.

## Reliable implementation pattern

1. Read the response sheet with `gog sheets get`, not by editing the backing Sheet directly in AppSheet.
2. Treat rows with `填入AppSheet = TRUE` as already processed.
3. Candidate rows are blank/`FALSE` in `填入AppSheet` and have a transport method or plate.
4. Resolve the employee in `HR_Employees` using bounded selectors, preferably:
   - `工號` -> `HR_Employees[Employee ID]`
   - otherwise Chinese/English name, then narrow locally by email or normalized phone if multiple matches appear.
5. If no AppSheet employee exists yet, leave the row pending and retry daily; do not create `HR_Employees` from this form unless explicitly requested and schema-checked.
6. If one employee matches, build a minimal `Edit` payload keyed by `PersonID` with only changed fields.
7. Map license plates carefully because the form has one plate field but AppSheet has separate plate fields:
   - Car-only transport -> `Car License Plate`
   - Moped / Heavy Motorcycle / Electric Scooter only -> `Moped License Plate`
   - Mixed or ambiguous methods -> do not guess the plate column; log/review.
8. Run dry-run first and report counts: candidates, matched, would edit, no-change, not-found/retry, ambiguous, warnings.
9. Live mode requires explicit approval. After each live edit, read back the same `PersonID` and verify intended field values.
10. Only after verified success or verified no-change, mark the source row `填入AppSheet` as `TRUE` if that behavior was approved.

## Automation reliability requirements

- Daily retry should be idempotent and stateful. Keep durable state keyed by a source-row hash, not only row number.
- Use a lock (`flock`) to prevent overlapping runs.
- Keep JSONL logs and a small state file under Hermes state/log paths.
- Clean runs can be silent; failed/ambiguous rows should remain discoverable in logs/state and be included in dry-run summaries.
- For Hermes cron no-agent jobs, schedule a wrapper under the active profile scripts directory; the wrapper can exec the canonical script elsewhere.

## Known local implementation artifact

A dry-run/live-ready implementation was created during the initial setup:

- Canonical script: `/home/prodesign/.hermes/scripts/hr_newhire_transport_sync.py`
- Canonical shell wrapper: `/home/prodesign/.hermes/scripts/hr_newhire_transport_sync.sh`
- PD One cron wrapper: `/home/prodesign/.hermes/profiles/pdone/scripts/hr_newhire_transport_sync.sh`

Do not assume these paths exist in a different profile or host; if absent, recreate from the pattern above rather than declaring the automation unavailable.

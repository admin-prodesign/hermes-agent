# Facilities LINE work-report tracker parsing

Use this when maintaining the `LINE工作回報` tracker populated from the Facilities LINE capture group.

## Tracker and source ids

- Tracker Sheet: `18dffVvJLefw4peSNliNsIuGraRp4QEc3VPH3qgDTpDU`
- Tracker tab: `LINE工作回報`
- LINE group ID: `C7c88572a11e8f3aff11d443aee53c037`
- Importer script: `/home/prodesign/.hermes/profiles/pdone/scripts/facilities_line_capture_to_sheet.py`
- ERP asset Sheet: `ERP_Data`, id `1VUuY49JkiVzCKOSSc-8doKlS2cb4yRolNKowYWv3f1A`
- ERP asset tab: `ERP_Data_Combined`
- Equipment filter: rows where `Type = Equipment`
- Key/header fields: `品       號`, `Friendly Name`, `產品名稱`, `Equipment Type`

## Parsing rules

1. Read live headers, not fixed column positions. Andy may reorder Sheet columns.
2. Add/maintain structured columns for analysis:
   - `Equipment`
   - `Equipment Asset ID`
   - `Equipment Friendly Name`
   - `Equipment Match Status`
   - `Parsed Follow-up Status`
   - `Parse Notes`
   - `Media Drive Links`
3. Equipment shorthand like `T1`, `T22`, `T31` should be matched against `ERP_Data_Combined[Type=Equipment]`, usually from `Friendly Name` values such as `T2 (JW-500G)`.
4. Preserve raw LINE text. Parsed fields are derived analysis columns and should not replace the original report.
5. Mark ambiguous records for clarification/review instead of guessing:
   - `media_only`: image/photo with no text context.
   - `multiple_matches`: e.g. `T4暫拆T31真空泵浦更換，待備品` mentions both T4 and T31; review whether this is one job involving two assets or needs the reporter to clarify the primary equipment.
   - `token_not_in_erp_assets`: equipment-like token exists but no ERP asset match.
   - `no_equipment_token`: no equipment/area token found.
6. Derive simple follow-up flags conservatively, e.g. `更換 -> replacement`, `測試ok -> tested_ok`, `待備品/待料 -> pending_spare_parts`, `更正 -> correction`, `暫拆 -> temporary_removal`.

## Examples verified in session

- `T2更換輸送帶馬達減速機控制器` -> `T2 (JW-500G)`, asset `AJW-500G`, follow-up `replacement`.
- `T22更換螺桿三件組，逆流測試ok` -> `T22 (JW-250J)`, asset `AJW-250J`, follow-up `tested_ok, replacement`.
- `T4暫拆T31真空泵浦更換，待備品` -> `T31 (JW-400B)` and `T4 (JW-500K)`, status `multiple_matches`, follow-up `pending_spare_parts, temporary_removal, replacement`.
- `更正T1輸送帶` -> `T1 (JW-500F)`, asset `AJW-500F`, follow-up `correction`.
- `T11無背壓更換背壓控制板` -> `T11 (JW-250R)`, asset `AJW-250R`, follow-up `replacement`.

## Media upload and local-retention rule

- Do not leave Facilities LINE report images only in local capture paths. Upload images into the Facilities Drive photo folder and write shareable Drive links back to `Media Drive Links`.
- Current photo root folder: `LINE工作回報照片 Facilities Work Reporting Photos`, folder id `10FS807r60GNvunXAlwbi0NS8UmQkv7vl`.
- Use month subfolders such as `2026-06` (known id from implementation: `1mcWPUtPEtRZuOfGYS-154XMofMAF8AZQ`) so the Drive folder stays navigable.
- Set both the root photo folder and month subfolders to `anyoneWithLink` / `reader` only after explicit admin approval, then verify with Drive permission readback before reporting completion.
- After each image upload is verified and the tracker row has a Drive link, delete the local image file. Keep a small state map of local path -> Drive file id/link so reruns are idempotent and already-uploaded files can still populate links if the local file is gone.
- Importer dry-run mode must not upload media, create folders, change permissions, write Sheets, or delete local files. It may report planned uploads/links only.

## Backfill and repair pattern

- For existing rows, map by live headers and stable `Source JSONL`, not fixed column positions. Re-read the referenced JSONL line, parse it again, upload/link media, then patch only the intended cells.
- For bulk row repairs, prefer `gog sheets batch-update --data-json @file` with many single-cell ranges over whole-sheet rewrites; this preserves manual review/status columns outside the intended repair cells.
- If one image was uploaded before a script/state update, seed the upload-state file from a Drive folder listing by filename before rerunning, instead of uploading a duplicate.
- Verify local cleanup with a file search/count for remaining media files under the capture `media/` directory; do not infer deletion from Sheet updates.

## Verification

- Run the importer with `--dry-run --verbose` first.
- For backfills, update only the intended tracker tab/range and read back headers plus sample parsed rows.
- Do not claim image migration is complete until all of these are verified: Drive upload/listing count, Drive permission readback (`anyoneWithLink`/`reader` where approved), tracker `Media Drive Links` readback, and zero remaining local `.jpg` files for migrated captures.

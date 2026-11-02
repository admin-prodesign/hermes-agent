# Legacy Facilities Work Order imports

Use this reference with `references/legacy-case-imports.md` when importing historical Facilities Repair Order Google Sheets into AppSheet `Case` / `Case_Updates`.

## Source shape observed

- Spreadsheet: archived Facilities Repair Order sheet.
- Primary raw tab: `原資料`.
- Unlike Tech Dev Cases, the Facilities raw tab is effectively one row per work order, not one row per update. History columns contain embedded line-delimited repair / acceptance / manager history.
- Header row contains both original submission fields and computed `[+] ...` fields. Prefer `[+]` fields for final work-order number, final progress, request time, updated time, deadline, and history where present.

## AppSheet mapping

- `Case.Type`: `Facilities Repair`.
- Deterministic IDs:
  - `CaseID`: `C-FACLEG-<legacy-maintenance-number>`; if the legacy number is blank, use a stable row/hash fallback.
  - `CaseUpdateID`: `CU-FACLEG-<case-suffix>-<sequence>`.
- Work type → `Case.Sub-Type`:
  - `維修/修改/即興保養/清潔 Repair` → `Facilities_Repair_Case`
  - `專案 Project` → `Facilities_Project`
  - `工程 Engineering` → `Facilities_Engineering`
  - `新購 New equipment` → `Facilities_NewEquipment`
- Andy's historical import rule still applies: legacy fully finished / manager-closed rows (`4 ... Finished` / `結案了`) become `Completed`; all other legacy rows become `Canceled`.
- Preserve legacy person names, requestor, reviewer, repairer, vendor, finance-completion notes, area, equipment/machine, and inspection details in description/update text when they are free text. Do not force free-text names into AppSheet enum/ref person fields unless a high-confidence employee mapping exists.
- Use a safe default `Next Step Responsible Person` only when required by deployed AppSheet validation; for Facilities imports the observed default was the Facilities owner/responsible person from Lookup (`JQZUFBCV`). Re-check current Lookup before reuse.
- `Case_Updates[Update Type]` only accepts deployed lookup values. In the observed app, valid values were `Detail Update` and `Action Record`; do not invent values such as `Review` or `Status Change` unless Lookup allows them.

## Update generation pattern

For each Facilities work order:

1. Treat the legacy raw rows as **status snapshots of the same work order**, not independent Cases. The old system did not have a separate `Case_Updates` child table; progress/status changes were saved by submitting the same form again with changed `Progress` / `進度`.
2. Use `Legacy progress` / progress text to decide parent vs updates:
   - `1.0 未完成 Not completed` = strongest opening Case signal.
   - If no `1.0` row exists, use the earliest/lowest progress row for the opening parent Case (commonly `1.5 未完成，可使用 Temporarily usable`).
   - Later snapshot rows such as `1.5 未完成，可使用 Temporarily usable`, `2 維修完成，待驗收 Acceptance`, `3 驗收完成，待廠務主管確認 Manager`, and `4 廠務主管確認完成，結案了 Finished` should become `Case_Updates` under the one canonical parent Case, not additional parent `Case` rows.
3. Create an opening `Case_Updates` row from the canonical opening/request data (`Detail Update`, `New Status = In Progress`).
4. Convert subsequent status snapshot rows into `Action Record` updates under the canonical parent. Preserve the source legacy CaseID/work-order number, progress text, requestor/reviewer, area/equipment, vendor/finance notes, and any changed description/additional-info in the update body.
5. Split `維修歷史 Repair History`, `驗收歷史 Acceptance History`, and `主管歷史 Manager History` by nonblank lines only after the parent/status-snapshot grouping is correct. Avoid duplicating the same embedded history once per status snapshot; prefer one canonical history timeline per work order.
6. Add or keep one final `Action Record` update whose `New Status` matches the parent final status (`Completed` for final progress `4 ... Finished`, otherwise the agreed historical terminal status such as `Canceled`).

## Production cautions

- Check for existing deployed IDs with `STARTSWITH([CaseID], "C-FACLEG-")` and `STARTSWITH([CaseUpdateID], "CU-FACLEG-")` before writes.
- Temporarily relaxing `Lookup[Editable Roles]` for `Completed` / `Canceled` may be needed, just like Tech Dev imports. Back up the rows first and restore immediately after verification. In the 2026-06 Facilities canary, `Case[Status] = Completed` edits failed until `LookupID=Completed` `Editable Roles` was temporarily blanked and then restored to `Case_Admin`.
- For AppSheet Data API edits/deletes, use the real table key only. In this app `Case` edit/delete rows should use `CaseID` and must not include `Row ID` (including `Row ID` makes AppSheet try to update a non-updatable field). `Case_Updates` delete rows should use `CaseUpdateID`.
- Large Facilities imports are slow through AppSheet API validation. Use a resumable runner with `done_keys`, conservative batches, and a watchdog/restart pattern rather than a single uncheckpointed process. For old `Case_Updates` cleanup, prefer one-by-one `CaseUpdateID` deletes with receipts; bulk/chunked child deletes can hang or progress only partially. Deleting duplicate parent `Case` rows does **not** reliably cascade/delete old child `Case_Updates`, so verify the old child IDs are gone explicitly.
- API readback by deterministic prefix may show zero for old imported rows because of app owner/date security filters. Use temporary deterministic `API_Target_Queue` rows for final verification and delete them afterward.

## Post-import duplicate cleanup lessons

- Do not conflate deterministic import completeness with source-level dedupe completeness. A fresh audit can show every expected `C-FACLEG-*` / `CU-FACLEG-*` deterministic key exists while users still see many duplicate legacy Facilities work orders because the source sheet had repeated snapshots of the same work order.
- For data-only duplicate audits, use the Prototype/Data Studio app first and de-echo AppSheet API duplicate returns by physical `Row ID` before counting real rows.
- A useful Facilities duplicate grouping key is same `Case[Created On]` plus normalized legacy import `Description` / title text. Treat raw duplicate rows returned by the API as suspicious until physical `Row ID` proves there is more than one row.
- Many duplicate Facilities groups include both `Completed` and `Canceled` snapshots. A naive “keep the base non-`-R` `C-FACLEG-*` ID” rule can preserve the wrong canceled snapshot. Prefer the `Completed` snapshot when present; otherwise prefer the base/non-`-R` deterministic ID or most complete row.
- Generate a dry-run with explicit keep/delete Case IDs and child `Case_Updates` counts. Delete child `Case_Updates` under duplicate parent Cases first, then delete duplicate parent `Case` rows, with bounded batches and readback after each batch.
- Keep the cleanup scope strictly to `C-FACLEG-*` unless a separate audit/approval covers Tech Dev (`C-LEGACY-*`) or runtime Cases.

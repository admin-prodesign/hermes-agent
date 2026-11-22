# Legacy Case Google Sheet imports

Use when importing historical Pro-Design Case-like rows from pre-AppSheet Google Sheets into AppSheet `Case` / `Case_Updates`, including Tech Dev Cases and Facilities Repair Orders. For Facilities-specific source shape and mappings, see `references/legacy-facilities-work-order-imports.md`.

> 2026-05 live-import learning: AppSheet Database `Add` is not raw bulk insert. Omit physical `Row ID`, pre-fill deployed required fields such as `Case_Updates[New Next Step Responsible Person]`, checkpoint every batch, and treat `Lookup[Editable Roles]` as a possible API validation gate for terminal statuses. See `references/legacy-case-live-import-20260515.md` for production import/verification edge cases.

## Proven pattern

For Facilities Repair Orders, read `references/legacy-facilities-work-order-imports.md` before applying the general pattern below; the source sheet uses a different row shape and source-specific ID prefix.

1. Read the current AppSheet schema first (`latest_raw_app.json` / `Case_Schema` / `Case_Updates_Schema`) and validate required columns before building payloads.
2. Treat the legacy `[+] 案子單號` as the grouping key. The raw `案子` tab contains one row per opening/update, not one row per case.
3. Sort each group by row `時間戳記` to find the final state; do **not** use `[+] 最後更新時間` to choose the latest row, because it is repeated across all rows for the same case.
4. Use deterministic import keys for idempotency, e.g. `CaseID = C-LEGACY-<legacy-number>` and `CaseUpdateID = CU-LEGACY-<legacy-number>-<sheet-row>`. Use a separate deterministic prefix per legacy source (for example, Facilities Work Orders use `C-FACLEG-*` / `CU-FACLEG-*`) so duplicate checks, verification queues, and rollback targeting can be bounded safely.
5. For Andy's historical-case import rule: final completed cases become `Case[Status] = Completed`; all remaining/uncompleted legacy cases become `Case[Status] = Canceled`.
6. For `Case_Updates`, `New Status` is required. Map every historical row to the nearest AppSheet status and force the final update to the final parent status.
7. Map old work types to `Tech Dev Case` subtypes:
   - `SIP更新` -> `SIP Update`
   - `客訴處理 Customer complaint investigation` -> `Customer Complaint Investigation`
   - `生產問題點處理 Internal incident investigation` -> `Internal Incident Investigation`
   - `專案 Project` -> `Project`
   - `驗證測試 Validation testing` -> `Validation Testing`
   - `新模開發(從畫圖至業務送樣) New mold (from design to sample)` -> `New Mold`
   - `開發/創新主意 Innovation idea` / `新產品圖 New product design` -> `New Product or Innovation Proposal`
   - `成型專案KPI` -> `Molding_Project_for_KPI`
8. Resolve people through `HR_Employees`; for this legacy Sheet import, map `ANDY LIN`, `副總`, and `林耘正` to the normal Andy employee row `DVNSMLZW` (`pro.design.group.tw@gmail.com`) unless Andy explicitly overrides it.
9. Product/mold parsing: legacy product text often contains `PD-###` mold numbers. Import high-confidence `Molds` (`APD-###`) first. For `Products`, follow `references/legacy-case-product-disambiguation.md`: auto-fill only uniquely matched Product SKUs; leave family-ambiguous products blank unless Andy approves a manual mapping table, because one mold can map to many color/material/printing/customer SKUs.
10. Keep Drive/MM/sql links as link fields in the first pass. Create `Case_Attachments` / `Case_Updates_Attachments` only in a separate approved pass if first-class attachment rows are required.

## Validation checklist

- No writes until explicit approval.
- Validate the generated JSON payloads before any live API call:
  ```bash
  python3 /home/prodesign/.hermes/skills/appsheet-copilot/scripts/validate_legacy_case_import_payloads.py \
    /home/prodesign/.openclaw/workspace/projects/AppSheet/exports/case-import-dryrun-YYYYMMDD
  ```
  If running from the OpenClaw skill checkout instead of Hermes, the same script may be under `/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/scripts/`.
- The payload validator must pass these checks: no unknown schema columns, no blank required fields, no duplicate `Row ID`/deterministic keys, every `Case_Updates[CaseID]` has a parent `Case[CaseID]`, and each case's final update `New Status` matches parent `Case[Status]`.
- Pull existing deployed `Case` / `Case_Updates` IDs and check deterministic IDs for duplicates before writes. Use bounded selectors such as:
  ```appsheet
  Filter(Case, STARTSWITH([CaseID], "C-LEGACY-"))
  ```
  ```appsheet
  Filter(Case_Updates, STARTSWITH([CaseUpdateID], "CU-LEGACY-"))
  ```
  Substitute the source-specific prefix for non-Tech-Dev legacy imports, e.g. `C-FACLEG-` / `CU-FACLEG-` for Facilities Work Orders.
- Validate required fields from the schema, but treat AppSheet Database physical `Row ID` specially: it may be schema-required in metadata, yet live `Add` calls should omit `Row ID` so AppSheet DB can generate it. Supplying legacy/import `Row ID` values can fail with a generic AppSheet Database invalid-request error.
- For this legacy import class, `Case_Updates[New Next Step Responsible Person]` may be required by deployed app rules even when older dry-run schema checks do not flag it. Fill blank update rows from the parent `Case[Next Step Responsible Person]` (fallback to `Created By` / Andy-approved default only if needed) before live writes.
- Treat person/product resolution warnings as review items, not schema blockers: for this legacy Sheet import, `ANDY LIN`, `副總`, and `林耘正` map to normal employee `DVNSMLZW`; ambiguous legacy `Products` should usually be left blank while high-confidence `Molds` and uniquely matched `Products` are imported.
- Before live writes that set final `Case[Status]` to `Completed` or `Canceled`, check the corresponding active `Lookup` rows. `Lookup[Editable Roles]` can cause AppSheet API writes to reject otherwise-valid status values under the import run-as context. If Andy approves production writes, back up those Lookup rows, temporarily relax only the needed fields for the import window, and restore them after verification.
- Expect `Case_Updates` writes to be much slower than raw DB inserts. AppSheet API batches run through the AppSheet app layer (valid-if/required-if, refs, virtual/ref columns, formulas/actions/automation checks), so use conservative batch sizes, checkpoint `done_keys`, and make the runner resumable/idempotent instead of increasing batch size blindly. For multi-thousand row imports, use a small watchdog/restart script that resumes from `done_keys` if the background process dies; keep it silent unless it restarts or completes, and remove it after final verification.
- After writes, restore any temporary `Lookup` edits, verify counts by deterministic key prefix, status distribution, parent/child refs, `Latest_CaseUpdateID` where applicable, related update count, high-confidence mold/product fields, and links. If the API run-as user is the app owner, older historical rows can be hidden by owner/date security filters even though the import succeeded; use temporary deterministic `API_Target_Queue` rows for the imported `CaseID` / `CaseUpdateID` keys to make those rows visible for readback verification, then delete the temporary queue rows and confirm `Filter(API_Target_Queue, STARTSWITH([QueueID], "LEGACY-VERIFY-"))` returns zero.
- After `Case_Updates` import completion, do not equate new `ProcessingQueue` rows with continuing imports. First separate deterministic row completeness from downstream queue backlog. The active `Case_Updates` `ReadyToProcess` path can enqueue `ProcessingQueue` jobs via `C_U_Enqueue_TranslateRequest` / `C_U_Enqueue_Notify_NoTranslation`; this means imported updates are being translated/notified, not necessarily added again. Read `references/legacy-case-processingqueue-triage.md` before answering queue-migration/backlog questions.
- For post-import quality audits, compare live AppSheet values back to the dry-run payload, not just import runner state. AppSheet may mutate optional fields during API adds/automation: blank `Deadline` / `Completion Date` can be populated, blank `Created By` can be run-as defaulted, and `Case_Updates[Flag_Processed]` can be overwritten by translation/processing states such as `AwaitingTranslation` or `ReadyToProcess`. Treat URL `{Url, LinkText}` readback and EnumList spacing/order changes as AppSheet normalization, not data mismatch. See `references/legacy-case-post-import-audit.md`.
- Queue-assisted verification can return the same physical row more than once when a row is already visible through the normal date/security-filter branch and also matches `API_Target_Queue`. Treat counts by unique deterministic IDs (`CaseID` / `CaseUpdateID`) as authoritative, not raw returned-row counts; duplicate returned rows with the same physical `Row ID` are a readback artifact, not necessarily duplicate data. Before and after verification, also clean any stale Facilities/legacy queue rows by `TargetID` prefix (`C-FACLEG-` / `CU-FACLEG-`) and require zero remaining queue rows.

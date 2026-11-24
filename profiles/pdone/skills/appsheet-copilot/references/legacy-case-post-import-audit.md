# Legacy Case post-import audit and repair dry-run

Use after historical Google Sheet Case imports into AppSheet `Case` / `Case_Updates` (Tech Dev `C-LEGACY-*` and Facilities `C-FACLEG-*`) to independently verify that AppSheet live state still matches the dry-run payloads.

## What to verify

1. Use deterministic key prefixes, not raw returned row counts:
   - Tech Dev: `CaseID STARTSWITH "C-LEGACY-"`, `CaseUpdateID STARTSWITH "CU-LEGACY-"`.
   - Facilities: `CaseID STARTSWITH "C-FACLEG-"`, `CaseUpdateID STARTSWITH "CU-FACLEG-"`.
2. For data-only readbacks/audits, use the **prototype app** first because it does not have the deployed app's security filters. Only use temporary deployed-app `API_Target_Queue` visibility rows when checking deployed-specific live behavior or before/after a deployed write.
3. If temporary deployed visibility rows are needed, add `API_Target_Queue` rows for every imported `CaseID` / `CaseUpdateID`, run readback, then delete those queue rows and require zero remaining.
4. Treat duplicate returned rows as a possible queue/security-filter artifact. A real duplicate requires more than one physical `Row ID` for the same deterministic key.
5. Compare unique IDs and parent/child invariants:
   - missing/extra Cases
   - missing/extra Case_Updates
   - physical duplicate deterministic keys
   - `Case[Status]` counts and per-key status
   - `Case_Updates[New Status]` counts and per-key status
   - final update `New Status` matches parent `Case[Status]`
   - per-case expected update count matches live unique child updates
6. For Facilities (`C-FACLEG-*`) imports, run a separate **source-level duplicate work-order audit** in addition to deterministic-key completeness. Deterministic import completeness only proves all generated keys exist; it does not prove repeated legacy work-order snapshots were deduped. Group likely duplicate parent Cases by same `Created On` plus normalized imported legacy description/title, then choose a canonical row before proposing deletes. Prefer a `Completed` snapshot when the group contains both `Completed` and `Canceled`; otherwise prefer the base/non-`-R` deterministic ID or most complete row.
7. Compare payload fields to live AppSheet values, but classify AppSheet-normalized values before calling them data errors: Unless a repair/cleanup dry-run is explicitly intended, keep source-level dedupe findings separate from import completeness claims.
   - URL columns may read back as JSON-like objects such as `{Url, LinkText}`; compare their `Url` only.
   - EnumList/list fields may read back with spacing/order changes; compare token sets.

## Known post-import AppSheet mutation signatures

These are not proof of missed rows, but they should produce a repair dry-run or an explicit decision:

- `Case[Deadline]` can be auto-populated even when the import payload/source was blank.
- `Case[Completion Date]` can be auto-populated for terminal statuses, including canceled historical cases, even when the payload/source was blank.
- `Case[Created By]` can be auto-filled from the API run-as/user default when payload/source was blank. For Facilities imports, legacy requester/reviewer names may only be preserved in `Description`; decide whether to leave the structured field as import/system creator, blank it back out, or do a separate HR_Employees mapping pass.
- `Case_Updates[Flag_Processed]` can be overwritten by translation/processing workflows (`AwaitingTranslation`, `ReadyToProcess`, `Finished`). Do not rely on it as the durable import marker after live AppSheet automation runs; prefer deterministic IDs and `Updater`. Do not reset it automatically unless you have checked the translation/processing workflow.
- A specific field can be dropped by validation/automation even when the add succeeds; compare required operational fields such as `Case_Updates[New Next Step Responsible Person]`.

## Repair workflow

1. Build a repair **dry-run payload only** first. Do not edit AppSheet until Andy explicitly approves the repair payload.
2. Scope repairs to deterministic import prefixes only.
3. Candidate repairs often include:
   - restore source/payload deadline where live value differs and the intended value is nonblank;
   - **do not batch-clear `Case[Deadline]` to blank through the row API without a fresh validation check**: the live app has rejected `Edit` rows with `Deadline = ""` as missing a required value, even when the historical source/payload was blank. Filter blank deadline clears into a separate review/exception plan or use an approved editor/schema change before attempting them;
   - clear injected `Completion Date` for canceled cases where source/payload was blank, after probing that the current app validation allows blank completion dates for the target rows;
   - restore missing completed-case `Completion Date` / `Last Updated` where source/payload was nonblank;
   - restore missing `New Next Step Responsible Person` on update rows.
4. For rows hidden by owner/date security filters, keep the temporary `API_Target_Queue` visibility rows present for both `Find` **and** `Edit`; deleting the queue immediately after plan construction can make subsequent row API edits fail with 404 even though the dry-run readback succeeded.
5. Keep `Case_Updates[Flag_Processed]` out of automatic repair unless the user explicitly wants to reset the processing workflow state.
5. After repair writes, repeat the prototype-app unique-key audit for data fields. If the verification must prove deployed write visibility/automation behavior, use a deployed-app readback and include whether `API_Target_Queue` visibility rows were needed. Include a concise status/mismatch summary plus artifact paths.

## Artifact pattern

For a post-import audit, save:

- `legacy_case_import_audit_detail.json` — full counts, duplicate checks, field mismatch summaries/examples.
- `legacy_case_import_actionable_mismatches.csv` — row-level repair candidates with source, table, key, field, expected, actual, and status.
- `legacy_case_import_actionable_mismatches_summary.json` — compact counts by source/table/field and cleanup result.

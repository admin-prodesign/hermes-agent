# Legacy Case live import notes — 2026-05

Session-specific lessons from the first approved production import of pre-AppSheet Google Sheet Cases into deployed AppSheet `Case` / `Case_Updates`. Keep this as a compact reference; the class-level procedure remains `references/legacy-case-imports.md`.

## Production outcomes to expect

- AppSheet API writes are app-layer writes, not database bulk inserts. `Case_Updates` batches of 75 rows took roughly 135–139 seconds each even with near-zero local CPU, because AppSheet evaluates required/valid-if rules, refs, virtual/ref columns, formulas, actions, automation conditions, and sync/index side effects.
- Prefer conservative, checkpointed, resumable batches over increasing batch size blindly. Store `done_keys`, failures, last batch metadata, and response logs so a timeout can resume idempotently.
- Do not treat a terminal timeout as proof of no writes. Re-probe deterministic keys or inspect the state file before retrying.

## Live-write blockers discovered

- AppSheet Database physical `Row ID` should be omitted from live `Add` payloads even when schema metadata marks it required. AppSheet DB generates it; sending synthetic legacy Row IDs can produce generic invalid request failures.
- `Lookup[Editable Roles]` can act as a validation gate for terminal statuses such as `Completed` and `Canceled`. If production import is approved:
  1. back up only the affected `Lookup` rows,
  2. temporarily relax the required fields for the import window,
  3. write and verify the import,
  4. restore the exact backed-up values.
- `Case_Updates[New Next Step Responsible Person]` was required in deployed validation even when earlier dry-run checks did not flag blanks. Fill blanks from parent `Case[Next Step Responsible Person]`; if unavailable, fall back only to an explicitly approved deterministic person mapping.

## Verification pitfall: old rows hidden by security filters

The deployed `Case` / `Case_Updates` data filters can hide old historical rows from owner/run-as API readback unless the imported IDs are present in `API_Target_Queue`. A naive `Filter(Case, STARTSWITH([CaseID], "C-LEGACY-"))` can return zero even after successful import.

Verification pattern:

1. Add temporary deterministic queue rows for every imported key:
   - `QueueID = LEGACY-VERIFY-CASE-<CaseID>` with `TargetTable = Case`, `TargetID = <CaseID>`
   - `QueueID = LEGACY-VERIFY-CU-<CaseUpdateID>` with `TargetTable = Case_Updates`, `TargetID = <CaseUpdateID>`
2. Re-run readback selectors using deterministic prefixes.
3. Verify expected counts, status distribution, parent-child refs, representative Molds/Products/link fields, and sample related updates.
4. Delete all temporary queue rows.
5. Confirm both cleanup selectors return zero:
   ```appsheet
   Filter(API_Target_Queue, STARTSWITH([QueueID], "LEGACY-VERIFY-"))
   ```
   ```appsheet
   Filter(API_Target_Queue, STARTSWITH([QueueID], "LEGACY-LATEST-"))
   ```

## Latest update action caveat

Running `Case_UpdateLatestCaseUpdateID` after the import can populate `Latest_CaseUpdateID` for many multi-update cases, but do not make it the only success criterion for historical imports. Verify `Related Case_Updates`/parent-child refs and row counts as the authoritative import proof; `Latest_CaseUpdateID` may remain blank for some edge cases even when the child row exists and refs are correct.

## Reporting expectations

Report concise final numbers and artifacts, not raw logs:

- total `Case` rows imported and failures
- total `Case_Updates` rows imported and failures
- final status counts (`Completed` / `Canceled` for this import class)
- any temporary app-data changes made and restored
- verification artifact paths
- cleanup confirmation for temporary queue rows/monitors

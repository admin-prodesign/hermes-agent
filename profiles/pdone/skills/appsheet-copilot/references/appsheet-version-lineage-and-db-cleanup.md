# AppSheet version lineage and physical DB cleanup notes

Use this reference after AppSheet editor saves/restores or AppSheet Database column edits create unexpected version or schema state.

## Version lineage facts

- Pro-Design major AppSheet editor versions use `YY.MMDD00` (example: `26.061800` on 2026-06-18 UTC), not semantic-style `27.000001` unless explicitly approved.
- AppSheet restore (`Manage > Versions > Version History` -> view old version -> `Restore (make this version current)`) restores old **content** by creating a **new latest version**. It does not roll the version number back.
- If an accidental higher version has been created, stop and report; do not repeatedly save lower `Version` values. AppSheet returns version-conflict responses and preserves monotonic lineage.
- Stable promotion must remain separate: verify `IsValid=true`, `IsRunnable=true`, and `StableVersion` before/after; never promote just to hide an editor-version mistake.

## Safe recovery sequence after a bad editor save

1. Fresh `/api/loadApp/<appName>` readback: record `Version`, `StableVersion`, `IsValid`, `IsRunnable`, and target objects.
2. If content must be reverted, use the official read-only historical-version restore UI/API path and then fresh readback. Expect a new latest version number.
3. If reapplying changes is still desired, rebase onto the restored latest payload and accept/document the unavoidable latest version lineage unless Google/AppSheet support provides a backend fix.
4. Do not clone the app as a first-line fix; cloning changes app identity, integrations, users, links, bots, and deployment references.

## Physical AppSheet Database table cleanup lessons

- App definition schemas and physical AppSheet Database tables can diverge. Checking `DataSchemas[]` is not enough to prove physical DB columns are clean.
- Verify physical tables in the DB editor by opening the specific table URL and extracting visible headers; check each tab/table independently.
- Before adding columns in the DB editor, verify active table focus with page title, URL, selected tab, and first visible key column.
- If attachment columns are accidentally added to parent `5S`, AppSheet Database may auto-suffix duplicates (`5SRecordID (1)`, `ActivityLogID_Legacy (1)`, `Timestamp (1)`, etc.).
- Clean parent `5S` should not contain attachment-only fields such as `5SAttachmentID`, `ActivityLogAttachmentID_Legacy`, `CreatedBy`, `Images`, `Files`, `Attachment Category`, or suffixed duplicates. Clean `5S_Attachments` should contain the lean attachment column set only.

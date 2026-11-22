# ActivityLog attachment upload failures: version guard vs parent resolution

Use when users report `ActivityLog_Attachments` upload failures and recent Performance Analyzer logs show add-row failures.

## Distinguish the two common classes

### 1. Newer app version / reset data required

Dominant failure signature:

```text
ExceptionHandlerFramework.BypassableSpreadsheetException:
This data change cannot be applied because there is a newer version of your app '<app name>'.
Please reset data to discard local changes.
```

Meaning: the mobile/browser client has queued local add rows from an older app definition version. AppSheet refuses to apply those pending mutations after newer app versions were created.

Operational response:
- Tell affected users to **Reset Data / full sync** before retrying uploads.
- Avoid additional production saves/promotions while users are retrying.
- Do not misdiagnose this as a role/security permission issue.

Analyzer pattern:
- Many `Add row` failures on `ActivityLog_Attachments` across multiple users.
- Often paired with payload/detail rows that contain the attachment data but no result.
- Spikes may follow heavy editor/API save sessions.

### 2. Parent row not resolvable during attachment add

Failure signatures:

```text
Unable to find the specified row from AppSheet database
```

or

```text
Requested item from AppSheet database not found or data may have been deleted
```

For true upload adds, the first signature usually matters more. It can appear when the attachment row references a parent `ActivityLogID` that AppSheet cannot fetch during after-image/readback or formula evaluation.

Definition risks to inspect:
- `ActivityLog_Attachments[ActivityLogID]` is an `IsAPartOf` Ref to `ActivityLog`.
- `ActivityLog_Attachments[ActivityLog Type]` AppFormula dereferences `[ActivityLogID].[Category]` / `[ActivityLogID].[Sub-Category]`.
- Immediate add-process conditions/actions dereference parent fields, e.g. `[ActivityLogID].[Thumbnail]`.
- Parent/child security filters have different timestamp/key visibility rules.

Durable fix direction:
- Reduce inline parent dereferences in the attachment add path.
- Move parent-derived fields to stored/queued values after the parent row is resolvable.
- Keep thumbnail/cache append work queued/background rather than blocking upload.
- Align row-local visibility predicates so child attachments do not outlive visible parent rows.

### 3. Direct ASDB append / after-image readback failure

Failure signature:

```text
AppendRowsAsync -> GetAfterImagesAsync -> AsdbProvider.AsdbTable.GetRowsAsync
Unable to find the specified row
ServerHandler.AddTableRowHandler.AddTableRowInternal
```

Meaning: AppSheet has entered the direct Add-row append path and then cannot read the just-appended row during after-image/readback. Treat this as a platform/database/cache-pressure candidate unless payload decoding proves a bad key/ref. It is not the same as a downstream thumbnail, notification, cache-append, or parent-maintenance worker failure.

Operational response:
- Do **not** immediately edit `ActivityLog_Attachments` definitions, refs, actions, or security filters from this signature alone.
- Build a redacted support-case appendix with aggregate counts, app version, row-size distribution, and stack signature; do not send externally without Andy/admin approval.
- Keep add/edit reliability, thumbnail automation pressure, and sync-duration/getAllTables evidence in separate buckets. Include full-load sync context only as correlation/platform-pressure evidence, not as proof of the add-path root cause.
- If successes and failures share the same app version/user-client cohort and ASDB after-image failures include sub-50KB rows, do not frame the issue as only a large-photo/payload-size problem.

## Analyzer triage recipe

1. Pull add-row failures, not just sync-only analyzer scans:
   - `failuresOnly=True, adds=True`
   - optionally all add rows for the same window to pair payload rows and failures.
2. Filter for `ActivityLog_Attachments`, `ActivityLogAttachmentID`, `Unable to find the specified row`, and `newer version of your app`.
3. For table-scoped all-adds scans, de-duplicate AppSheet's paired result/detail rows: count only rows whose `Result` is `Success` or `Failure` for the add-attempt denominator, and use same-timestamp blank-result rows only as payload/detail companions.
4. Classify rows by signature before proposing a fix.
5. Decode payload rows using current `ActivityLog_Attachments_Schema` column order to extract `ActivityLogID`, `ActivityLogAttachmentID`, image/file fields, and timestamp. If failures have payload + parent refs and all result rows are on the same stable version with no newer-version exception, do not recommend reset/full-sync as the dominant fix.
6. For ASDB after-image failures, pair failures with success rows by request/client/version/requestStartTime/RowSize, then compare app version, client/user concentration, row size, and minute bursts. Save only hashed/redacted request/client/user examples.
7. Report counts by signature, TPE hour, and affected user ID or hashed user bucket depending on audience. For AppSheet Support drafts, omit raw row data, request IDs, attachment payloads, private values, and full `loadApp` JSON unless separately approved/redacted.

## Reporting guidance

Lead with the dominant class. If `newer version` dominates, the immediate fix is user reset/full sync. If parent-row errors remain after resets, proceed to definition-level parent-resolution hardening. If direct ASDB append/after-image failures dominate, prefer a redacted AppSheet Support packet or platform-pressure relief experiment over speculative live app-definition edits.
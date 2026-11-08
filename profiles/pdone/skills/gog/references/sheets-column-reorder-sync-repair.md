# Google Sheets column reorder sync repair

Use this when a PD One-managed Sheet has had columns reordered (for example moving `原始訊息連結` to the final column) and an existing sync may still write fixed-position rows.

## Durable lesson

Column reordering is normal in user-facing Sheets. Sync code must treat row-1 headers as the schema contract and emit rows in the sheet's current header order. A fixed-position append can silently shift values into wrong columns after a manual reorder.

## Repair pattern

1. **Stop the producer or patch it first** so new rows cannot keep arriving misaligned.
2. **Patch sync writes by header name**:
   - Read the live header row.
   - Build each candidate row as `{header: value}`.
   - Emit values as `[record.get(header, '') for header in headers]`.
   - Keep stable dedupe keys independent of column position.
3. **Dry run before write** and report counts such as `posts_seen`, `rows_ready`, and dedupe skips.
4. **Repair existing shifted rows**:
   - Identify rows where values clearly belong in another column, e.g. a channel name like `#iml-loss-control` appearing under `recorded_at`, URLs not under `原始訊息連結`, or paper-batch/work-order values shifted by one or more columns.
   - For duplicate shifted rows, clear/delete the bad duplicate after confirming the correctly aligned row exists.
   - For unique shifted rows, reconstruct the row by header name and write it back in current header order.
5. **Clean administrative conversation leakage**:
   - If the business sheet is a source-record table, remove/skip approval/admin dialogue, PD One status chatter, and image-only or no-business-content rows unless explicitly part of the business record.
6. **Verify with a second no-op sync**:
   - Rerun sync and confirm `rows_ready=0` or only genuinely new source records are appended.
   - Read back problem rows/columns and verify URLs are under the link column, channel names are not under timestamp fields, and the moved column is still last if requested.
7. **Check sharing separately from content repair**:
   - If the audience should view/download/filter but not edit, verify Drive permissions are `reader`/viewer, not `writer`, after repair.

## Reporting receipts

Final status should include:
- Script/code receipt (commit or file path changed).
- Sheet repair counts (cleared rows, repaired rows, skipped admin/image rows if known).
- Sync verification (`rows_ready=0`, `last_successful_sync`, or equivalent).
- Permission verification if access scope changed.

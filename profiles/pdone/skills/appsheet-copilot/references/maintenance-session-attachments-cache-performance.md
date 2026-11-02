# Maintenance session attachments cached-column performance pattern

Use when AppSheet Performance Analyzer shows slow syncs or cache-lock/timeouts around `Maintenance_Session_Items`, `Maintenance_Session_Items_Attachments`, or `Maintenance_Session_Items[Related Maintenance_Session_Items_Attachments]`.

## Trigger evidence

This pattern is appropriate when fresh `/manage/exportlog` sync-only analysis shows evidence such as:

- `Maintenance_Session_Items` table p90 in the tens of seconds or worse.
- `Maintenance_Session_Items[Related Maintenance_Session_Items_Attachments]` appearing as a top virtual/computed column timing.
- Sync failures like:
  - `Data table 'Maintenance_Session_Items_Attachments' is not accessible due to: Timed out waiting for a resource`
  - `AsyncLocking.AsyncLock+LockTimeoutException`
  - AppSheet text about a very large/slow table or cross-table formula cycle.

Treat this as user-visible sync degradation, separate from HeartBeat/ProcessingQueue automation failure volume.

## Recommended design

Add a physical cached list on the parent table:

```text
Maintenance_Session_Items[Maintenance_Session_Items_Attachments_Cached]
```

Suggested type:

```text
EnumList / Ref -> Maintenance_Session_Items_Attachments
```

Values should be attachment keys:

```text
Maintenance_Session_Items_Attachments[MaintenanceAttachmentID]
```

Keep the existing reverse-ref virtual column temporarily as the correctness oracle:

```appsheet
Related Maintenance_Session_Items_Attachments =
REF_ROWS("Maintenance_Session_Items_Attachments", "MaintenanceAttachmentID")
```

Move detail/inline views away from the expensive virtual column only after the physical cache is populated and verified.

## Pitfalls

- A physical cache column does not populate itself. It needs add/delete maintenance, backfill, and a repair/reconciliation path.
- Do not simply add a broad reset/initial expression that runs a full `SELECT()` on every sync/edit; that can move the cost rather than removing it.
- Use full rebuilds only for bounded backfill, delete repair, or periodic reconciliation.
- The existing virtual reverse-ref should stay during rollout so cached values can be compared against AppSheet's relationship truth.

## Maintenance pattern

1. **Add path:** when a `Maintenance_Session_Items_Attachments` row is created, append that `MaintenanceAttachmentID` to the parent `Maintenance_Session_Items_Attachments_Cached` list.
2. **Delete path:** on delete, either remove that key from the cached list or do a bounded full rebuild for the affected parent.
3. **Backstop repair:** scheduled/hourly or manual reconciliation compares cached values against the reverse-ref oracle and repairs drift.
4. **Backfill:** populate recent/current parent rows first; compare cached vs related values before broad backfill.
5. **View swap:** after readback verification, update detail/inline views to use the physical cached list and hide/de-scope the old virtual column from normal sync surfaces where safe.

## Verification checklist

- Fresh definition readback shows the physical cache column is `IsVirtual=false` and typed as an EnumList/Ref to `Maintenance_Session_Items_Attachments`.
- Add/delete actions or processes update only the affected parent row.
- Backfill sample reads recent attachment rows, collects their parent `MaintenanceSessionItemID`s, then reads those parent rows and compares cached values to `Related Maintenance_Session_Items_Attachments`.
- App remains valid/runnable/deployable.
- Post-promotion analyzer window is cleanly split from the deployment time and reports sync p50/p90/max, top table timings, top VC timings, and sync failure classes.
- Report whether improvement is proven, regressed, or inconclusive; do not claim success from definition readback alone.

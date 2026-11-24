# automation-source-key-integrity — Recovery workflow

## Recovery workflow

0. **Classify the Admin card before any write path**
   - Engine failure: `Cronjob Response`, exit 1, traceback through `run_scan_sheet()` / `main()`. Read `hermes cron incidents`, job `last_status`, watchdog state JSON, and a live worker `scan-sheet`. Failed cron output markdown may already be pruned; the incidents table is the durable receipt. Truncated traceback at the scan plus incident type `timeout` or scheduler "external worker did not acknowledge within 30s" means the source read hung or timed out — still not a duplicate-key case.
   - Invariant break: watchdog stdout naming duplicate/missing IDs, or live `scan-sheet` with non-empty duplicates / missing > 0.
   - If live scan is 0 duplicates and 0 missing, watchdog `last_broken` is false, and the latest tick is ok/silent: report probe recovered and stop. Do not enter row classification or Sheet writes.

1. **Authorize the source write**
   - Resolve the requester by the platform's exact stable identity.
   - Require source authority or an approved admin decision before choosing a canonical row or changing production keys.
   - Keep merge/delete decisions separate; approval to repair duplicate key cells does not authorize deleting a row.

2. **Capture the pre-repair invariant**
   - Run the worker's read-only source scan when available.
   - Record active-row count, missing-key count, duplicate-key set, and exact candidate locations.
   - Re-read the complete candidate rows immediately before planning the write; do not rely on an older incident packet or row number snapshot.

3. **Classify the rows**
   - Re-read complete candidate rows immediately before classifying; issue text alone is not enough.
   - If every business field matches, treat the later row as a copy: clear its values (including the key) so scan `missing`/`duplicate` both stay empty. That is identity repair of a copy, not deletion of a distinct assignment.
   - If the rows differ in business ownership or scope, preserve both and repair only identity.
   - Prefer an explicit source-authority choice of canonical row.
   - If approval authorizes repair of distinct rows but names no row, preserve the first physical occurrence of the existing key unless stronger provenance shows which row originally owned it. Assign later distinct occurrences new keys.

4. **Validate the allocator**
   - Inspect the live allocator or bound automation, not only a local source copy.
   - Determine whether new keys come from the live maximum, a persisted counter, a UUID generator, or another canonical service.
   - If allocation uses at least `max(existing keys) + 1`, a direct assignment of the next unused key is safe for future runs.
   - If allocation relies only on a stored counter, use the canonical allocator or update the counter in the same approved change; otherwise the next trigger may recreate the duplicate.

5. **Plan the narrow write**
   - Derive replacement keys from a fresh full-key-column read or canonical allocator.
   - Prepare an explicit cell/range payload and exact readback range.
   - Dry-run and confirm the plan changes only the intended key cells.
   - Avoid clearing a duplicate and waiting for a trigger when the worker also fails closed on missing keys.

6. **Apply and verify the source repair**
   - Perform the approved live update.
   - Require API/readback evidence for every changed cell.
   - Re-run the source scan and require unchanged active-row count, zero missing keys, and an empty duplicate set.

7. **Verify normal production recovery**
   - Wait for the next scheduled run rather than launching the writer manually.
   - Record settled exit status, timer advance, and application-log/receipt advance.
   - If the recovered run processes queued work, verify its write readbacks and report any messages, prompts, reminders, or other side effects that the normal run naturally emitted.
   - Do not treat a green timer alone as recovery evidence.

8. **Close the incident narrowly**
   - Report exact changed cells, before/after keys, source-scan counts, and scheduled-run receipt.
   - State what was not changed: business content, ownership, history, queue state, timers, services, gateway, or configuration.
   - Update the operational project/incident registry only after both the source scan and normal scheduled run pass.

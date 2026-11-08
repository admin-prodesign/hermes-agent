## Core rules

- Treat the source table and its canonical key allocator as the authority; never bypass duplicate/missing-key guards in the worker.
- A duplicate key does not prove the business rows are duplicates. Compare complete candidate rows, especially department, owner, status, history, and source links.
- If every compared business field matches, the later physical row is an accidental copy: keep the first occurrence as canonical and clear the later row so it is neither active nor keyed. Do not mint a replacement key for a copy — that unblocks the writer but creates a second follow-up for the same assignment.
- If the rows differ in owner, department, or other scope, preserve both records and repair only identity on later occurrences.
- Keep source repair separate from queue repair. A duplicated key may not appear in the current waiting queue, but it can still block every writer run.
- Use the smallest bounded write possible, dry-run first, and require exact readback.
- Verify recovery on the next normal scheduled run. A manual writer launch changes timing and may create sends or writes that would not have happened naturally.
- Fail-closed without an operator-visible page is a silent outage. systemd `OnFailure` that only federates to PD Neo, and supervisor audits with `deliver=local`, do not page Andy. Pair every fail-closed source-key guard with a quiet Admin watchdog: empty stdout when duplicate/missing counts are zero; one `@andy.lin` Admin alert on a broken invariant (fingerprint cooldown); one recovery line when it returns. The watchdog must not repair rows.
- A Hermes engine-failure card (`Cronjob Response`, script exit 1, traceback in the watchdog) is a probe/scan failure, not a uniqueness break. The designed invariant page is watchdog stdout that names duplicate or missing keys. Diagnose the probe first; do not classify rows or write keys because the engine card exists.
- Project List source-key watchdog live `scan-sheet` Google/Sheets timeouts retry once, then `transient_failure_gate.py` (`pdone-cron-4d7c09917fd9`, 3 / 1800s, `--quiet`). One-off transients exit 0 with empty stdout. Persistent transients print one designed `@andy.lin` probe-failure line (not a duplicate-ID finding) and still exit 0 so Hermes does not emit an engine card. Non-transient probe failures still exit 1. Do not wrap this job in a supervisor wrapper just to get the gate; it lives in the watchdog.
- An allocator that skips any cell that already has a key will preserve a pasted duplicate of an existing key. After backfill, scan for duplicate keys; do not treat “cell already filled” as uniqueness.

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

## Pitfalls

- Deleting or merging rows because their visible issue text matches, even though they represent separate owners or departments.
- Assigning a new stable key to a later row that is a full copy of the canonical row — the writer recovers, then the same owner is pinged twice.
- Choosing a replacement from a stale local counter without checking the live key column and allocator.
- Clearing one key and leaving a missing-ID outage window.
- Manually running a production writer to prove recovery, which can send reminders or process replies outside the normal schedule.
- Treating a Tuesday-to-Tuesday (or other mid-week) waiting-prompt window as the Project List weekly cycle. Andy's cycle **resets every Thursday**: unanswered waiting prompts from before that Thursday must be superseded and a fresh one-item ping sent. Skip only a prompt already sent this Thursday, or an issue already replied since last Thursday. Mid-week continuation DMs do not extend the cycle past Thursday.
- Using a live reply-poller `--write` to catch up Sheet history after a source-key outage: that path also enqueues the next owner DM. When the ask is history-only, dry-run the poller on a separate audit lock, then `append-history --write` for matched replies. If dry-run `matched_replies` is empty and same-channel posts after each waiting prompt show no owner threaded reply and no plain progress reply, stop — unanswered is not unwritten.
- Reporting only service exit 0 without checking the application receipt or downstream readback.
- Hiding naturally emitted sends after recovery; disclose them even when the scheduler, not the repair command, produced them.
- Treating federation/`OnFailure` as the primary Andy alert for a fail-closed poller — those rails stay local unless a dedicated Admin watchdog (or equivalent) emits stdout to PD One Admin.
- Treating a Hermes cron engine-failure card for the source-key watchdog as a duplicate/missing-key incident — that starts identity repair on a sheet the live scan already shows healthy. Classify engine vs invariant first using live `scan-sheet` plus watchdog `last_broken` and a silent last tick.

## Verification checklist

- [ ] Exact source authority/approval is recorded.
- [ ] Full candidate rows were re-read immediately before repair.
- [ ] Distinct business rows were preserved; accidental full-row copies were cleared instead of re-keyed.
- [ ] Live allocator cannot reuse any replacement key that was assigned.
- [ ] Dry-run changed only intended cells.
- [ ] Live readback matches every intended value.
- [ ] Missing and duplicate counts are zero. Active-row count is unchanged unless copies were cleared, in which case it drops by the number of copies removed.
- [ ] Next normal scheduled run settled successfully.
- [ ] Application receipt/downstream writeback advanced and any sends were disclosed.

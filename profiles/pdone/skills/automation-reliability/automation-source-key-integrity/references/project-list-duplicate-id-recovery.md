# Project List duplicate Issue-ID recovery example

## Incident shape

The production Project List reply poller failed closed because `PL-2026-0067` appeared in two `PD One Issue ID` cells. The rows had the same issue text and history but different departments and responsible people, so they were separate assignments rather than a row to delete or merge.

## Authority-backed decision

After Project List authority approval:

- Preserve the first physical occurrence as canonical: `專案追蹤!N43 = PL-2026-0067`.
- Preserve the second business row but assign the next unused identity: `專案追蹤!N44 = PL-2026-0068`.
- Change only the later Issue-ID cell; do not alter department, responsible person, history, or issue text.

## Allocator check

The live bound Apps Script was inspected before the direct write. Its allocator chooses:

```text
max(document property nextIssueNumber, max(existing current-year IDs) + 1)
```

Because future allocation is bounded by the live maximum, assigning `PL-2026-0068` directly makes the next generated value at least `PL-2026-0069`; no separate counter repair is required. This check is essential—do not assume every stable-ID script behaves this way.

## Safe execution pattern

1. Re-read both complete rows and the full Issue-ID column.
2. Create a one-cell batch update for the later row.
3. Dry-run with readback range covering both candidate ID cells.
4. Apply live only after approval and verify `0067 / 0068` by exact API readback.
5. Run the standard source scan.
6. Wait for the next five-minute production timer; do not invoke the writer manually.

## Acceptance receipts

The completed recovery showed:

- One updated cell and one updated row.
- 50 active rows unchanged.
- 0 missing Issue IDs.
- No duplicate Issue IDs.
- The next normal reply-poller service run exited 0 and advanced its application JSONL receipt.
- That normal run processed one waiting reply with verified Sheet readback and continued the expected prompt/reminder queue; these scheduler-emitted side effects were disclosed.
- No service, timer, gateway, configuration, ownership, history, or queue-state repair was performed as part of the key fix.

## Classify before choosing a write

| Complete-row compare | Repair |
| --- | --- |
| Same issue text **and** different owner/department/link/history | Keep both rows. First physical key stays; later distinct rows get the next unused ID. |
| Every compared field matches (issue, unit, owner, history, link, key) | Accidental copy. Keep the first row; clear the later row `A:N` so it is not active and not keyed. Do **not** mint a new ID. |

Clearing a copy is identity repair. Deleting a distinct assignment still needs a separate delete decision.

After either write: `scan-sheet` must show zero duplicate IDs and zero missing IDs, then wait for the next normal reply-poller timer. Do not launch `poll-dm-replies --write` to prove recovery.

## Reusable lessons

- Identical issue text can still represent distinct business assignments.
- Byte-identical full rows with the same ID are copies; clear the later row instead of minting a new ID.
- Verify the live allocator before writing a sequential replacement key.
- Do not clear a key and wait for backfill when missing keys also block the worker.
- Recovery proof is the next normal scheduled run plus application/downstream receipts, not merely a successful scan or green timer.

## Prevent silent fail-closed

Fail-closed on duplicate or missing Issue IDs is correct. systemd `OnFailure` for the reply poller only federates to PD Neo guarded triage, and the daily supervisor audit is `deliver=local` — neither pages PD One Admin.

Primary Andy page: `/home/prodesign/.hermes/profiles/pdone/scripts/project_list_source_key_watchdog.py` (Hermes no-agent cron → PD One Admin). Empty stdout when live `scan-sheet` has 0 duplicates and 0 missing IDs; one `@andy.lin` alert on a broken invariant with fingerprint cooldown; one recovery line when healthy again. Do not auto-repair rows from the watchdog.

Probe/scan failures are not invariant pages. Live `scan-sheet` Google/Sheets timeouts retry once, then `transient_failure_gate.py` source `pdone-cron-4d7c09917fd9` (3 failures / 1800s, `--quiet`). One-off transients exit 0 with empty stdout (no Hermes engine card). Persistent transients print one designed `@andy.lin` probe-failure line and exit 0. Non-transient probe failures still exit 1. Do not classify Sheet rows from a probe timeout.

If Admin instead receives a Hermes engine card (`Cronjob Response` / exit 1 / traceback), that is the probe crashing during `scan-sheet`, not the invariant page. Diagnose read-only: `hermes cron incidents`, job last status, `state/project-list-source-key-watchdog.json`, then `project_list_maintenance.py scan-sheet`. Failed output files under `cron/output/<job_id>/` may be gone; use the incidents table. A recovered probe is last tick ok + silent, `last_broken=false`, and scan 0/0 — stop there; do not write Issue IDs.

The bound Apps Script must not treat a filled Issue-ID cell as uniqueness. After assigning missing IDs, scan duplicate keys: keep the first physical row; clear later byte-identical copies `A:N` (do not mint a new ID); assign the next unused ID only to later **distinct** assignments.

## Catch-up Sheet history after a fail-closed outage

When the ask is to write collected owner replies into Project List history:

1. Confirm `scan-sheet` has 0 duplicate and 0 missing IDs.
2. Dry-run `poll-dm-replies` on a **separate audit lock**, not the production reply-poller lock.
3. Classify posts after each waiting prompt: owner threaded reply, owner plain progress reply, or bot/unrelated (`no_matching_pending_prompt` is expected for PD One reminders).
4. If matched owner progress replies exist, append with `append-history --write` (duplicate-skip + readback). Do **not** run live `poll-dm-replies --write` for a history-only ask — that path also sends the next owner DM.
5. If dry-run matches are empty and the channel classify shows no owner progress replies after the prompt timestamp, stop and report unanswered, not unwritten. Do not invent Sheet rows.

Do not trust a systemd timer `Description` that still says dry-run; read `ExecStart` (weekly follow-up is `send-followup-prompts --send`).

Live state/logs live under the Hermes PD One profile `legacy-openclaw/workspace/state/project-list-maintenance/` and `.../logs/project-list-maintenance/`.

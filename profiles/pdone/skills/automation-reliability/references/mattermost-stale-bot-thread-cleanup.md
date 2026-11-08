# Mattermost stale bot-thread cleanup

Use when an approved admin asks for deterministic cleanup of old bot-generated Mattermost threads while preserving threads with human engagement.

## Safe deterministic pattern

1. **Fix the scope.** Hard-code and verify the exact channel id/name and authenticated bot username/id before scanning or deleting.
2. **Match only owned roots.** Require a top-level, non-deleted root authored by the authenticated bot plus an anchored, automation-specific title/marker. Do not match generic mentions inside arbitrary posts.
3. **Use strict age semantics.** “Older than 7 days” means `root.create_at < now_utc - 7*24h`; exactly seven days old remains protected.
4. **Read the complete bounded channel history.** Paginate with a fixed page size and hard max. If the max is reached before history ends, fail closed rather than produce a partial deletion plan.
5. **Re-fetch every matched thread.** Use `/api/v4/posts/{root_id}/thread`; do not infer same-thread replies from a channel-wide `after` response.
6. **Classify reply authors, not just user IDs.** Resolve non-owner reply authors with Mattermost user metadata and `is_bot`:
   - any human reply protects the whole thread;
   - a deleted human reply still counts as prior human engagement and protects the thread;
   - owner-bot continuation replies do not count as human;
   - known other-bot/system replies do not count as human;
   - unknown/unresolvable authors fail closed and protect the thread.
7. **Dry-run by default.** Emit a machine-readable receipt and a concise Markdown table of `would_delete` versus `keep`, with cutoff, scanned-post count, root IDs/links, reply counts, and protection reasons. Dry-run must issue zero DELETE requests.
8. **Gate live deletion.** Require an exact confirmation phrase in addition to a live flag. Immediately re-fetch and reclassify each candidate before any DELETE to close the scan/delete race window.
9. **Delete replies before the root.** For an eligible thread, delete replies newest-first, then the root. Read back every post and require either HTTP 404 or a nonzero `delete_at`; otherwise fail the run.
10. **Separate implementation from activation.** A verified dry-run script is not a deployed destructive automation. Create/enable the daily no-agent cron only after explicit destructive-action approval, then register it with the supervisor, route sustained failures to the admin lane, and back up the script/cron/registry changes.

## Production activation and receipt lessons

- **Preserve the batch receipt before scheduler smoke tests.** The core cleaner may update `latest.json` on every run. A later successful no-op wrapper/cron run can therefore replace the batch-deletion view. Treat the timestamped live receipt as the immutable completion evidence and cite that path in Project Registry/status updates; use `latest.json` only for current health.
- **Verify absence with a fresh scan.** After the live batch completes, run a new dry-run scan with local-artifact writes disabled. Require `would_delete=0` and confirm every remaining matched thread is protected; the live receipt alone proves what was deleted, not that the channel is now clean.
- **Use a quiet live wrapper for cron.** The wrapper should capture and parse the core JSON, require `mode=live`, allow only explicitly safe result statuses, append a compact JSONL summary, print nothing on success, and exit non-zero with a concise bilingual error on failure. This prevents daily full-history JSON from becoming chat noise while preserving audit evidence.
- **Schedule after the producer and prove the scheduler path.** Choose a daily time after the briefing producer runs, check for an existing equivalent job before creating one, run the newly created cron once, and read back `enabled/state`, `last_status`, `last_delivery_error`, and `next_run_at`.
- **Register the real failure route.** If successful runs are silent and Hermes `deliver=origin` is the primary non-zero error path, document that route in the wrapper and supervisor registry. When the supervisor audit detects recognized bridge markers, include the marker beside the documented route rather than adding a duplicate alert sender; rerun the audit and require no finding for the new job.
- **Interpret supervisor results narrowly.** A global supervisor audit may remain `ok=false` because of unrelated automations. For deployment acceptance, require zero findings that match the new job ID/name and report unrelated findings separately rather than claiming the whole supervisor is clean.

## Implemented PD One reference

- Script: `/home/prodesign/.hermes/profiles/pdone/scripts/interdepartment_briefing_thread_cleanup.py`
- Tests: `/home/prodesign/.hermes/profiles/pdone/tests/test_interdepartment_briefing_thread_cleanup.py`
- Dry-run receipts: `/home/prodesign/.hermes/profiles/pdone/artifacts/interdepartment-briefing-thread-cleanup/`

PD One Admin unreplied notifications (2-day retention, top-level `pdone` roots only):

- Script: `/home/prodesign/.hermes/profiles/pdone/scripts/pd_one_admin_unreplied_notification_cleanup.py`
- Quiet live wrapper: `/home/prodesign/.hermes/profiles/pdone/scripts/run_pd_one_admin_unreplied_notification_cleanup_live.py`
- Tests: `/home/prodesign/.hermes/profiles/pdone/tests/test_pd_one_admin_unreplied_notification_cleanup.py`
- Receipts: `/home/prodesign/.hermes/profiles/pdone/artifacts/pd-one-admin-unreplied-notification-cleanup/`

## Verification checklist

- [ ] Exact bot and channel identity read back.
- [ ] Anchored root marker tested against positive and negative examples.
- [ ] Pagination completed before the hard limit.
- [ ] Human, deleted-human, other-bot, exact-seven-day, and unknown-author cases unit-tested.
- [ ] Real dry-run reports `delete_requests=0` and `external_mutations=0`.
- [ ] Live-mode confirmation gate fails before network deletion when omitted.
- [ ] Scheduler remains disabled until destructive approval is explicit.
- [ ] Timestamped live batch receipt is preserved before any no-op scheduler smoke run overwrites `latest.json`.
- [ ] Fresh post-live scan reports `would_delete=0` and all remaining threads have a protection reason.
- [ ] Quiet wrapper parses the core receipt, records JSONL evidence, stays silent on success, and fails non-zero on malformed/unexpected results.
- [ ] New cron manual run reports `last_status=ok`, no delivery error, and the expected next run time.
- [ ] Supervisor audit has no finding matching the new job ID/name, even if unrelated findings keep the global audit non-clean.

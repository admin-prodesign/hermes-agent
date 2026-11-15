# Mattermost review_log health check

Use this when Andy asks whether `review_log` is still catching employee interactions with PD One via Mattermost DMs and channels.

## Safe bounded check sequence

1. Read/confirm source-of-truth policy first:
   - `policies/mattermost-channels.md` section `Review logging`
   - `out/wiki-mirror/syntheses/mattermost-review-log-operations.md` if present
2. Check the timer/service without restarting OpenClaw:
   ```bash
   systemctl --user status pd-one-mattermost-review-log-dm-scanner.timer pd-one-mattermost-review-log-dm-scanner.service --no-pager --full
   systemctl --user list-timers 'pd-one-mattermost-review-log*' --no-pager --all
   ```
3. Inspect scanner state files:
   ```bash
   cat /home/prodesign/.openclaw/workspace/state/mattermost-review-log-dm-scan.json
   cat /home/prodesign/.openclaw/workspace/state/mattermost-review-log-interaction-scan.json
   ```
4. Inspect only the recent tail of the scanner log/journal. Transient DNS/connectivity failures can recover on the next run; do not infer gateway failure from one failed scan. The wrapper records transient-alert suppression state in `/home/prodesign/.openclaw/workspace/state/mattermost-review-log-scanner-alert-state.env`; transient-looking failures are suppressed until 2 consecutive failed service runs or 15 minutes unresolved, then alert normally.
   ```bash
   tail -n 240 /home/prodesign/.openclaw/logs/mattermost-review-log-scanner.log
   journalctl --user -u pd-one-mattermost-review-log-dm-scanner.service --since '2 hours ago' --no-pager --output=short-iso
   cat /home/prodesign/.openclaw/workspace/state/mattermost-review-log-scanner-alert-state.env 2>/dev/null || true
   ```
5. Run non-mutating dry-run backstop checks over a bounded recent window. `--dry-run` does not update state or the sheet.
   ```bash
   # Choose since-ms from the desired UTC lookback.
   python3 - <<'PY'
from datetime import datetime, timezone, timedelta
for hours in (24, 48):
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    print(hours, int(dt.timestamp() * 1000), dt.isoformat().replace('+00:00','Z'))
PY

   /usr/bin/python3 /home/prodesign/.openclaw/workspace/tools/mattermost_review_log.py scan-dms --since-ms <SINCE_MS> --dry-run --per-page 120
   /usr/bin/python3 /home/prodesign/.openclaw/workspace/tools/mattermost_review_log.py scan-interactions --since-ms <SINCE_MS> --dry-run --per-page 120
   ```
6. Interpret dry-run rows carefully:
   - `scan-dms wouldAppend: 0` over a recent window means no unlogged DM posts were found in the fetched per-page window.
   - `scan-interactions` may list Andy/admin rows in dry-run because Andy filtering happens at append time through `append_rows()` / `is_recordable_review_row()`. Treat `andy.lin` and `admin <admin@prodesign-group.com>` candidates as expected exclusions, not employee misses.
   - Employee rows in dry-run after filtering Andy/admin are potential missing review-log rows.
   - Current scanner behavior: profiled DM/channel rows require later PD One bot reply evidence in fetched Mattermost history before being marked `closed`. If no bot reply is found, rows should be `dm_no_reply_evidence` or `channel_no_reply_evidence`, with `follow_up_needed=yes` and `review_status=open`. If investigating historical rows from before the 2026-05-14 fix, a profiled DM-enabled user's scanner-backstop row may still be `review_status=closed` even if PD One did not answer during a Mattermost/API/LLM outage; verify delivery separately via Mattermost bot posts/session logs/gateway outage logs before interpreting old `closed` rows as answered.
7. Verify the live Google Sheet has recent employee rows without bulk editing it:
   ```bash
   /home/prodesign/.local/bin/gog sheets get 1kJntZ6L8P72q_Brsp7ixrQsmxnDs6EACMQqpwgGxLOE 'pd_one_review_log!A1:AZ1000' --account admin@prodesign-group.com --json
   ```
   `pd_one_review_log` is the live tab name; older `review_log!` examples are legacy and can 400 on the current sheet. Use the wide bounded read when reporting current non-closed counts, then inspect a narrower row window only for targeted triage. Avoid shell shapes that trigger Hermes approval prompts during routine read-only checks: do not pipe `gog ... --json` into `python3 -c`, and avoid inline `python3 -c` for JSON slicing. Prefer reading the raw JSON with `gog` first, then parse it via Hermes `execute_code`, a temporary reviewed script, or `jq` when available. If parsing via Python, tolerate control characters in `gog` JSON output; use a robust parser if available instead of assuming strict `json.loads` always succeeds.
8. Check notification coverage separately from capture health when Andy asks whether open issues will notify:
   - Immediate append-path alerts are in `tools/mattermost_review_log.py::notify_review_alerts`; they fire only when new appended rows match alert-worthy reasons such as profile setup, permission/scope requests, risky/blocked requests, out-of-scope requests, approval-gated/data-unavailable rows. PD One/Hermes alerts should target Discord channel `1503946606985216090`; when invoking `openclaw message send --channel discord`, use a channel-qualified target such as `channel:1503946606985216090` because bare numeric Discord IDs can be ambiguous.
   - The local OpenClaw cron digest job may be disabled if digest delivery was migrated to n8n. Do not rely only on `/home/prodesign/.openclaw/cron/jobs.json`; verify the active n8n workflows too.
   - If Andy asks to stop receiving the generic digest because `supervisor-agent` sends its own first-pass triage report, load `automation-reliability` reference `references/review-log-supervisor-triage-handoff.md`. Safe replacement means: update/read back the supervisor-agent cron prompt, verify a live successful run, deactivate only the n8n digest workflow, keep the scoped-answer watchdog active unless explicitly replaced, and keep row closure/Sheet edits/employee replies approval-gated.
   - Known n8n review-log workflows: digest `0a1mny8xzyVc3c08` (`PD One review_log digest v2 (n8n)`) and scoped-answer watchdog `U7GU223MQ47ocJw0` (`PD One review_log scoped-answer watchdog v2 (n8n)`). Use `.env.n8n` and the n8n REST API to confirm `active:true`, recent successful executions, and workflow code filters. Redact credentials.
   - Watchdog semantics: it checks recent candidate rows (currently last 36h in workflow code) and de-dupes via static `seen` state; it is a new-candidate alert, not an infinite nag loop for already-seen old open rows.
   - `dm_no_reply_evidence` / `channel_no_reply_evidence` rows can be scanner race false positives: the scanner may append an open no-reply row before the later same-thread bot reply is visible in the fetched Mattermost page. Before sending a corrective DM or declaring a missed answer, fetch the original post/thread and verify whether a later `pdone` reply exists. If it does, close only that row with `follow_up_needed=no`, `review_status=closed`, `response_quality_flags=false_positive_no_reply_evidence_resolved`, concrete `bot_reply_ids`, and `answer_sources=Mattermost same-thread bot reply evidence (...)`.
   - Durable fix for the above race belongs in both layers: `tools/review_log_source_collector.py` should reconcile open no-reply rows by checking later same-thread bot replies and closing false positives; the n8n scoped-answer watchdog (`U7GU223MQ47ocJw0`) should have a no-reply grace window of **20 minutes** (`noReplyGraceMs = 20 * 60 * 1000`) and a cron of **every 10 minutes**. Andy 2026-09-23: keep the grace as a short first-tick buffer (15–20 min), not 120 minutes; fire the workflow every 10 minutes so eligibility is not delayed by an extra 30-minute cadence. Delayed REST-backfill replies after 20 minutes remain alert-worthy until the source collector closes the row. Verify with a watchdog JS simulation where a row younger than 20 minutes is suppressed and a row older than 20 minutes still alerts.
   - If the watchdog reports normal `channel_interaction` / `dm_question` rows where the user did not @mention PD One, split scanner capture from watchdog alerting before blaming the mention gate. The scanner may legitimately record non-mention replies inside an existing PD One thread when there is later bot-reply evidence; those rows should be closed audit evidence, not alert-worthy follow-up. Inspect the live sheet columns and n8n filter together: `review_status` is the watcher source of truth, and legacy `follow_up_needed` should not be used for watchdog selection. If `review_status=open` was set while the row only shows normal bot-reply evidence and `access_status=not_evaluated_in_scanner_backstop`, the likely bug is the append/response-quality layer or watchdog filter reopening placeholder rows without preserving response-quality explanation columns. Patch the watchdog to suppress normal bot-replied scanner-backstop placeholders, and patch the append path so quality review cannot silently flip status when the live sheet lacks columns to explain the decision.
   ```bash
   set -a; source /home/prodesign/.openclaw/workspace/.env.n8n; set +a
   for id in 0a1mny8xzyVc3c08 U7GU223MQ47ocJw0; do
     curl -fsS -H "X-N8N-API-KEY: ${N8N_API_KEY}" "${N8N_API_URL}/workflows/${id}" \
       | jq '{id,name,active,isArchived,updatedAt}'
     curl -fsS -H "X-N8N-API-KEY: ${N8N_API_KEY}" "${N8N_API_URL}/executions?workflowId=${id}&limit=5" \
       | jq '.data[] | {id,workflowId,status,startedAt,stoppedAt}'
   done
   ```
9. Source-collector sanity check: when recent rows still show structured fields such as `answer_sources=...scanner backstop` or `access_status=not_evaluated_in_scanner_backstop`, but `review_log_source_collector.py --dry-run` reports `scanned_candidate_rows: 0`, do not treat that as proof that source/permission capture is complete. Inspect both legacy `notes` and structured columns (`answer_sources`, `access_status`, `mattermost_post_id`, `source_session`, `reply_summary`); stale candidate filters can miss rows after the schema migrated from note tags into dedicated columns. Recent good rows should show:
   - `request_english` for Chinese/non-English employee requests; scanner commands now translate by default and expose `--no-translate` only as an explicit opt-out.
   - `reply_summary` for actual PD One replies, except deliberate no-reply-evidence rows where no reply existed; Chinese reply summaries should include an `English:` line.
   - `access_status=yes approval gated` plus `blocked_or_missing_sources=admin approval requested: <ticket>` when `request_approval` was successfully sent.
   - `access_status=yes approval request failed before creation` when approval escalation/tooling timed out or failed.
   - `access_status=yes_or_partial ...` plus `blocked_or_missing_sources` mentioning `no admin escalation/request_approval evidence found` when PD One refused/scoped a request without an admin escalation.
10. Optional unit tests: run with `PYTHONPATH=/home/prodesign/.openclaw/workspace/tools`. If tests fail due stale mocks/signatures but live deterministic probes pass, report that as a separate test-maintenance issue rather than blocking the health verdict. When tests are stale after review-log schema/API changes, update test expectations for dynamic sheet headers, structured columns (`access_status`, `blocked_or_missing_sources`, `reply_summary`), and auth dictionaries passed to `review_row_for_dm_post`.

## Timeout triage/fix pattern for `scan-interactions`

When the wrapper reports `exit 124` with `scan-dms` succeeding and `scan-interactions` producing no output, treat it as a bounded scanner-runtime incident before considering gateway restarts.

1. Inspect only recent wrapper log, service status, and state files first; do not kill/restart OpenClaw. A currently running service may still be in a wrapper retry from the previous code version, so wait for the next timer tick after patching before judging recovery.
2. Reproduce the expensive path with a bounded deterministic Mattermost API probe: list bot-visible channels, time small `GET /channels/{id}/posts?per_page=5` calls, and compare DM vs non-DM channel count/latency. If DMs dominate, remember `scan-dms` already covers direct messages.
3. Low-risk source fixes that preserve review-log semantics:
   - skip `channel.type == "D"` inside `scan-interactions`; keep DM capture in `scan-dms`;
   - filter Andy/admin rows before best-effort translation enrichment so skipped rows do not spend scanner wall-clock on LLM translation;
   - keep translation enrichment strictly best-effort with short subprocess/model timeouts, because missing `request_english` is preferable to missing deterministic capture/source-collector work;
   - if wrapper per-command timeout is adjusted, keep it narrowly scoped to the slow command and still below the systemd/timer expectations.
4. Verify with `python3 -m py_compile tools/mattermost_review_log.py`, wrapper `bash -n`, then observe at least one live timer run completing with `scan-dms`, `scan-interactions`, and `review_log_source_collector.py --limit 80` all exiting 0. Confirm alert state clears and the next no-op timer run stays successful.
5. If `pytest` is unavailable in the runtime, report that separately as a test-environment blocker; do not encode missing pytest as an operational limitation.
6. Commit/push only the narrow tracked code changes; leave unrelated dirty workspace state untouched.

## Proper fix pattern for false-closed rows

When a health check shows scanner-backstop rows were marked `closed` without evidence that PD One responded, treat it as a code/semantics bug, not just an ops explanation.

1. Add regression tests first in `/home/prodesign/.openclaw/workspace/tests/test_mattermost_review_log.py` for both DM and channel rows:
   - profiled employee message with no later bot reply evidence stays `open` / `follow_up_needed=yes`
   - same message with later PD One bot reply evidence can close normally and records the bot reply id in `notes`
2. Implement in `/home/prodesign/.openclaw/workspace/tools/mattermost_review_log.py` by passing reply evidence from the scanner fetch page into row builders. A reusable helper should search for later PD One bot posts in the same DM/channel/thread window and exclude setup-refusal/approval-gated replies, because those are handled by separate open-row paths.
3. Preserve the semantic distinction: scanner `closed` means "bot reply evidence exists for this Mattermost interaction," not "the answer was high quality". The source collector/session review may still improve `reply_data_sources` and permission tags later.
4. Verify with targeted review-log tests and then the full workspace test suite, e.g. `PYTHONPATH=/home/prodesign/.openclaw/workspace/tools pytest /home/prodesign/.openclaw/workspace/tests/test_mattermost_review_log.py -q` followed by `PYTHONPATH=... pytest tests/ -q` from the workspace.
5. Commit narrowly to the OpenClaw backup repo, then update this reference/wiki docs and commit Hermes backup if skill files changed. Avoid touching historical sheet rows unless Andy explicitly asks for a bounded audit/backfill; existing rows may have been manually reviewed.

## Closing existing open review_log items

Use this when Andy asks to review `review_log` for open items and close anything already handled.

1. Read the live sheet with current headers; do not assume old column order. As of 2026-05 the manually reordered sheet has `follow_up_needed` in column T, `review_status` in column U, `reply_summary` in column V, and `notes` in column W, but always verify the header row first before writing. Older notes may mention prior column letters; trust the live header row.
2. Define the worklist primarily as `review_status=open`. Many older manually reviewed rows may still have `follow_up_needed=yes` while `review_status=closed`; do not reopen or modify those unless Andy explicitly asks for follow-up flag cleanup. If Andy asks what needs resolving, close/resolve current `review_status=open` rows first, then optionally normalize stale closed-row follow-up flags only when closure evidence is already present.
3. For each open row, close only when evidence in the row itself or nearby completion rows shows the item is handled. Common closure evidence:
   - a later `approval_gated_request_completion` / `completed_admin_upload` row for the same `mattermost_post_id`, ticket, or user request;
   - a recorded delayed catch-up reply id in `notes`, `reply_summary`, or `answer_sources`;
   - a newly delivered corrective answer to the original requester, verified by Mattermost post id and recorded in `notes`;
   - for channel/thread `no_reply_evidence` rows, later PD One replies in the same Mattermost thread/root that directly answer the original request or an immediate clarification, even if the scanner row itself was created before those replies and still says `open`; fetch the full thread by `root_id`/`mattermost_post_id`, verify the reply is after the request and from `pdone`, and record concrete reply post IDs before closing;
   - the row is a duplicate of another open/catch-up item already handled;
   - PD One gave safe refusal/escalation guidance and the remaining work is a separate approval/automation request, not an active `review_log` follow-up.
   - a review-log row, even if categorized as normal DM activity rather than `no_reply_evidence`, is actually a reply to a PD One follow-up prompt from another workflow, such as Project List weekly DMs. In that case, find the preceding prompt/reminder post in the same DM/channel, extract the stable item ID (for example `PL-2026-0003`), write the user's reply to the owning system with readback verification, then close the review-log row with both the prompt post id and user reply post id. If multiple reminders/items immediately preceded the user reply and the target item is ambiguous, keep the row open or mark it for corrective/admin review instead of treating a wording-suggestion reply as handled.
   - when Andy/admin decides an open row should stay open, still update the row with a concise triage receipt instead of leaving the failed-reviewer fields untouched: preserve `follow_up_needed=yes` and `review_status=open`, set/adjust quality status and flags if known, append an `admin_reviewed_open:<UTC>` note with the evidence basis and requester, read the row back, then continue to the next open entry.
   - a bounded employee lookup is handled over several later same-DM turns after the employee provides the missing source/link, such as a production-schedule Google Sheet. Do not judge the first incomplete/refusal reply alone; inspect the later same-DM chain and the final source-grounded answer. If the final answer reads the provided source, gives the specific requested status/ETA or clearly states no visible schedule/blocker, and avoids unsupported notification promises, close the earlier row as superseded/handled while recording a quality note that intermediate replies were incomplete/tool-chattery until the source was provided.
   Sensitive personnel/evaluation-data requests need an extra split: creating an admin-only filtered Google Sheet or upload is evidence that data preparation is handled, but it is **not** evidence that employee-facing access is approved or delivered. Keep the employee-request rows open until Andy/admin decides the exact share scope and PD One either delivers the approved controlled subset or sends a final refusal/escalation message. For multi-BU Google Forms response sheets, use the `google-forms` reference `references/sensitive-response-sheet-filtered-copy.md` to create a scoped admin review draft instead of sharing the source sheet.
   Approval-ticket rows need a similar split: Andy approval or `approved/queued` ticket state is not completion evidence by itself. Keep the row open while implementation is still queued/pending; close only after the approved workflow/resource is actually built or a final requester/admin status is sent.
4. Apply targeted cell updates only: set `follow_up_needed=no`, `review_status=closed`, and append a concise `closed_by_pdneo:<UTC>` reason to `notes`. Do not bulk rewrite, sort, normalize, or clear ranges across the sheet.
5. If using row numbers, make sure the operation does not insert/delete/sort rows between read and write. This includes actions that look unrelated to closure but can append/insert their own audit rows, such as creating a schedule watch or recording an admin completion. When there is any chance rows moved, locate the mutable row by stable evidence (`mattermost_post_id`, ticket id, timestamp/user/request) before writing.
6. For sparse or manually sorted review-log sheets, do not enumerate rows from a compact `A1:AB120` values response and assume the array index equals the physical sheet row. Google Sheets API responses can omit empty interior/trailing rows or return multiline/control-character cells that break strict JSON/TSV parsing. When physical row numbers matter, first locate stable ids through a single-column range that preserves the target column well enough for row mapping (for example `review_log!J1:J160` for `mattermost_post_id`), then read/write the exact physical row (`A{row}:AB{row}` / targeted cells). Use a tolerant JSON parser for `gog` output with embedded control characters, and avoid plain TSV for row-sensitive work when cells may contain newlines.
7. Before sending an employee-facing corrective answer, re-read the target row and verify the actual requester from `user_id`, `user_label`, `channel_id`, and `mattermost_post_id`. Do not trust a prior handoff summary or nearby open-case label for the requester; a batch can contain unrelated employees with similar product/context wording.
8. After every write that was based on a row number, immediately read back the exact row and verify it still matches the intended stable identifiers before continuing. If the wrong row was touched, restore that row from the pre-write snapshot and re-target by stable ID, not by shifted row number.
9. When Andy asks to close rows “related to this,” search beyond the current `review_status=open` worklist. Include stale `review_status=closed` rows that still have `follow_up_needed=yes`, rows in the same Mattermost thread/root, rows sharing the same product/watch/ticket ids, and machine-generated audit rows created while resolving the issue. Close or annotate them only after verifying the shared resolution evidence (for example active schedule-watch ids plus smoke-test/readback, or later admin-approved cleanup in the same thread).
10. Verify by re-reading the sheet and confirming there are no `review_status=open` rows except intentionally pending approved/queued work items. If the user asked about a related cluster, also confirm there are no lingering `follow_up_needed=yes` rows in that cluster. Report counts concisely (`closed`, `completed`, `open`) and summarize categories closed; avoid listing private row details unless needed.
9. If the scoped-answer watchdog still flags closed rows after you have verified corrective delivery, inspect the bounded reply set before reopening anything. The watchdog is heuristic: if an earlier refusal/block reply and a later corrective/file delivery both exist, it may classify the row as mixed or redo-candidate even when the sheet row is correctly closed. Prefer adding concrete closure evidence (`reply_summary`, `closed_by_pdneo`, reply/file post ids) and leaving the row closed; treat watchdog tuning as a separate code/test-maintenance issue.
10. PD One-prompted workflow replies are a special case for `response_quality`: sometimes PD One replies to a user’s prompt, and sometimes PD One prompts users for input, ingests the reply, and decides the next workflow step. A short employee reply such as `沒有更新` or `同意` may be valid workflow input, not an off-topic answer, **but the expected success result is the workflow-specific verified outcome**, not merely sending the next prompt. Current generic columns are `workflow_name`, `workflow_item_id`, `workflow_expected_outcome`, `workflow_outcome_status`, `workflow_outcome_verified`, `workflow_outcome_evidence`, and `workflow_next_step`. Keep rows open / `response_quality_status=review` unless `workflow_outcome_verified=yes` (or equivalent verified status). Project List is one implementation: the expected outcome is Project List Google Sheets history-cell write/readback, with legacy `project_update_*` columns retained for readability. ECRN approval is another implementation: the expected outcome is recording the approval/denial in ECRN approval state and advancing/blocking the next stage.
11. For Project List workflow rows during one-by-one `review_log` review, do the workflow write before closing the review row: run/replicate `tools/project_list_maintenance.py append-history --issue-id <PL-ID> --source 'PD One follow-up' --comment <employee reply> --write`, verify the returned `target_range` and `readback_verified:true`, then update `review_log` with both the legacy `project_update_*` receipt and generic `workflow_*` receipt. Only then set `follow_up_needed=no`, `review_status=closed`, and `response_quality_status=ok`. If the append result is dry-run-only, ambiguous, failed, or lacks readback, keep the row open and record the blocker instead of closing from prompt/reply text alone.
12. When reviewing user-message origin, prefer structured columns over inference from reply text. `message_origin=pd_one_prompted_user` means the logged employee post was probably caused by a prior PD One prompt, while `user_initiated` means no prompt was detected. `prompting_context` identifies the prompt class, for example `project_list_prompt`, `ecrn_approval_prompt`, or `pd_one_prompt`. Scanner rows should populate `prompting_post_id` with the prior PD One prompt post id when Mattermost history contains it. For Project List, the legacy success columns are `project_update_status`, `project_update_issue_id`, `project_update_history_range`, `project_update_history_verified`, and `project_update_history_entry`; these are populated from the Project List reply-poller history append/readback receipt. If generic workflow headers are missing, run the review-log header ensure path and expand the Sheet grid first if Google reports the range exceeds grid limits.

## Closed-row note cleanup after open-item closure

Use this only after the primary `review_status=open` worklist is already at zero, or when Andy explicitly asks to clean up already-closed follow-up rows. Some historical/manual rows can have `follow_up_needed=yes` and `review_status=closed` but sparse notes; do not reopen them just because the follow-up flag is stale. Instead:

1. Read the live headers and identify only rows where `review_status=closed`, `follow_up_needed` is truthy, and `notes` is empty or too sparse to explain closure.
2. Reconstruct evidence from stable identifiers, especially `mattermost_post_id`, `reply_summary`, `answer_sources`, source session IDs, and nearby later PD One bot/completion rows. Prefer recording concrete Mattermost reply post IDs when available.
3. If no reply evidence is available, make that explicit in `notes` (for example: no later PD One bot reply evidence found, no `mattermost_post_id`, or post not fetchable) rather than inventing a closure reason.
4. Update only the `notes` cells for this cleanup unless Andy specifically asks to normalize `follow_up_needed`; avoid bulk row rewrites, sorting, or changing review status.
5. Verify by re-reading the sheet and counting: remaining `review_status=open`, updated sparse-note rows, rows with reply evidence, rows with no-reply/no-post evidence, and remaining sparse closed follow-up rows.

## Bounded historical backfill pattern

Use this when Andy explicitly asks to repair historical false-closed `review_log` rows after a Mattermost/API/LLM outage. See `references/mattermost-review-log-outage-backfill.md` for a compact example row-update shape and safety checklist.

1. Scope narrowly before writing: identify exact sheet rows by user, timestamp window, `mattermost_post_id`, current `review_status`, and current source/status columns. Do not bulk rewrite the whole sheet.
2. Verify response evidence in Mattermost first. Fetch the relevant thread/post history and distinguish:
   - no timely bot reply in the scanner window (false closed; candidate for open/no-reply-evidence backfill)
   - delayed catch-up reply after the outage (record as delayed evidence, but do not treat it as timely closure)
   - timely later bot reply in the scanner window (leave closed unless another issue exists)
3. Apply targeted single-row updates only, preserving unrelated columns. For affected rows set `category` to `dm_no_reply_evidence` or `channel_no_reply_evidence`, `assistant_response_type=no_bot_reply_evidence`, `follow_up_needed=yes`, and `review_status=open`. Update `reason`, `notes`, and structured columns such as `answer_sources`, `access_status`, and `blocked_or_missing_sources` to state the historical outage backfill, absence of timely bot reply evidence, and any delayed catch-up reply id/timestamp.
4. Read back the exact updated range and verify every intended row changed and every intentionally unaffected row stayed as-is. Run targeted review-log tests if code changes were part of the same session.
5. Leave a durable local audit note under a tracked docs/runbooks path (not ignored reports directories) summarizing scope, evidence checked, rows updated, and verification. Commit/push that note to the OpenClaw backup repo when available.

## Reporting shape

Keep Andy-facing output concise:
- Timer/service status and latest successful run.
- Whether recent DM/channel dry-runs found missing employee rows after Andy/admin filtering.
- Evidence that the sheet contains recent employee DM/channel entries.
- Notification status when asked: immediate append-path alert coverage, n8n digest/watchdog active/recent executions, and the caveat that the watchdog de-dupes already-seen old open rows rather than repeatedly nagging.
- Any caveat, e.g. transient Mattermost DNS failures recovered, stale unit tests, source collector changes pending, disabled legacy cron after n8n migration, or a recent n8n transient error that later recovered.

Do not restart the OpenClaw gateway during this check without explicit Andy approval.
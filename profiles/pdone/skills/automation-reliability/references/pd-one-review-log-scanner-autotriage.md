# PD One `review_log` scanner auto-triage pattern

Use this reference when a recurring log/review scanner has both a primary human alert path and a secondary Hermes/webhook self-triage path.

## Routing policy

- Preserve the existing primary human alert path. Do not replace the alert that operators already rely on with an agent-only route.
- Treat Mattermost/network/API/Google Sheets/OAuth timeouts as transient: write local logs/state, suppress human alerts, and do not invoke expensive auto-triage.
- For the employee-reply quality supervisor wrapper (`notify__pd_one_quality_supervisor.py` / job `bd82adb4f50a`), `TimeoutExpired`, `timed out after N seconds`, Google OAuth/API deadline, and matching network errors must not post PD One Admin Mattermost and must not call guarded triage. Repeat ticks of the same class stay local-log-only. Auth/permission/schema/readback failures still use the primary human alert.
- For other non-transient scanner failures, send the primary alert first, then POST a bounded event to the local Hermes/webhook triage endpoint. Do not fall back to Mattermost merely because guarded triage was unavailable when the error is a known transient timeout.
- The secondary agent/webhook bridge may be best-effort only if failed delivery is durably queued and drained later by a silent-on-empty worker.

## First-pass triage scope

A bounded repair agent for `review_log` scanner failures may inspect:

- systemd service/timer status for the scanner or wrapper
- scanner state/checkpoint files
- recent wrapper logs and journal entries
- queue files for failed webhook delivery
- whether the latest failure already recovered on a subsequent run

Allowed automatic fixes should be narrow and reversible, such as correcting a malformed local state/queue artifact or documenting a no-op when the latest evidence shows recovery.

## Dedicated review-lane triage pattern

Do not assign this workload to the PD One Automation Supervisor Agent (`8ca621fbe187`). Review-row classification, exact-thread verification, and employee-content inspection belong to the bounded dedicated lanes: employee reply quality supervisor `bd82adb4f50a`, semantic interaction-review shadow `6b3825ccc61c`, and daily digest `5ae242e3e2f2`. When one of those dedicated lanes performs read-only triage, treat it as a review task, not a closure task:

- Read live headers by name and include enough columns for current structured workflow fields. `A1:AB...` is enough for legacy quality columns, but Project List/workflow triage needs columns through at least `AZ` (`message_origin`, `prompting_context`, `project_update_*`, `workflow_*`). Prefer `pd_one_review_log!A1:AZ160` or `pd_one_review_log!A1:AZ220` for recent/digest-window triage, then use a bounded wider read such as `pd_one_review_log!A1:AZ1000` when the supervisor report is expected to state the current non-closed count. Do **not** conclude the whole Sheet is clean from a small recent window; either use the wider bounded read, a header-aware filtered read, or explicitly state the bounded window checked. If the live Google Sheets response returns a smaller actual range than requested (for example `A1:AY745` after asking for `AZ1000`), treat the returned range as the authoritative bound, report it verbatim, and do not assume the missing trailing column exists. The live tab name is `pd_one_review_log`; `review_log!` is a legacy example and may parse-error on the current sheet.
- For cron/supervisor runs, write the `gog sheets get ... --json` result to a temporary file and parse it with a robust Python `json` reader rather than piping raw Sheets JSON through fragile shell text processing. This preserves multiline/control-character cells and keeps the row/physical-number mapping reliable.
- When using a compact JSON tool such as `jq` for a bounded read, build the header map as `{key: header_name, value: column_index}` before `from_entries`; using a different field name silently produces null indexes. Treat each data row as `(. // [])` before indexing because Sheets responses can contain sparse/null rows. Filter `review_status` from the header-derived index, not a hard-coded column number. Use the API response’s returned `range` (for example, a request for `AZ1000` may return `AY905`) as the authoritative physical bound; do not infer that omitted trailing columns or rows exist.
- When searching for durable backlog coverage, match the exact gap/state, not just the automation name. A pre-existing remediation plan for `cron last_status=error` does not cover a later `stale-live-source` finding for the same automation, and vice versa. Before writing a new remediation plan, search for the same automation plus the same gap class (`missed_scheduled_fire`, `delivery failure`, `stale-live-source`, `degraded_noop`, `missing bridge`, etc.) and reuse an exact-match plan if one exists. If the current evidence is the same class but has newer timestamps or item IDs, update the evidence in the report without creating duplicate backlog files unless the gap class materially changed.

### Deterministic-gated supervisor run receipts and exact-thread verification

- Treat the gate packet as the first audit source. Re-run repair, wrapper, and audit scripts for current verification, but do not repeat broad discovery already answered by the packet unless the repair/wrapper pass changes state or a receipt must be confirmed.
- For a wide `gog sheets get` used to count current non-closed `review_log` rows, save the JSON to a temporary file and parse it with a header-derived tool. The API's returned `range` is authoritative: a request for `A1:AZ1000` may return `A1:AY905`; report the returned bound verbatim and do not infer missing columns or rows. Build field indexes from header names, filter on `review_status` (not legacy `follow_up_needed`), and preserve physical row numbers from the returned row position. Delete temporary files containing review-log content after triage.
- For a no-reply row, fetch the exact post and exact thread endpoint `/api/v4/posts/{post_id}/thread` when available. Do not substitute `/channels/{channel_id}/posts?after={post_id}` for exact-thread evidence: it returns unrelated later posts from the whole channel and can falsely look like same-thread closure evidence. Confirm the PD One bot user ID, reply post ID, root ID, and reply timestamp before changing a no-reply classification. A later bot acknowledgment of workflow start is not completion evidence; keep workflow rows open until the structured outcome/readback or signed artifact is verified. If later bot posts exist but their workflow/ECRN item ID does not match the row's structured `workflow_item_id` (or the thread's original item), classify the row as `automation_or_tooling_issue` / workflow-integrity review rather than `likely_closeable_after_verification` or `needs_pd_one_corrective_reply`; record the mismatch as evidence and do not replay or mutate the Sheet.
- In first-pass classification, normal bot-reply rows with `response_quality_flags=reviewer_failed` are normally `automation_or_tooling_issue`, not employee follow-up, when no separate substantive risk exists. Explicit source-scope/permission blocks are `needs_admin_approval`; prompted workflow rows with `workflow_outcome_unverified` remain `keep_open_pending_work`; do not mark any row closeable from bot-reply prose alone.
- For row triage, treat structured verification columns as the decision source over reply prose. A thread with bot-reply evidence but `workflow_outcome_verified=no` stays `keep_open_pending_work` until the workflow receipt/readback exists; do not convert it to closeable solely because the reply text sounds complete.
- Build the watchdog/triage worklist from rows where `review_status` is open/non-closed. Ignore the legacy `follow_up_needed` column for watcher selection; it is metadata only and stale values must not dominate the worklist.
- Do not mark anything `likely_closeable_after_verification` unless row-local or exact nearby evidence proves completion. Bot reply evidence alone can prove “PD One responded,” but it does not prove workflow success, approval completion, or answer quality. In particular, `assistant_response_type=approval_gated_or_blocked_reply`, `response_quality_flags` containing approval/scope blocking, or `access_status` indicating approval/blocked access should remain `needs_admin_approval` even when later bot posts or file attachments exist; those prove response visibility, not completion of the requested source/workflow outcome. Do not let generic `bot_reply_ids`, completion-like prose, or later unrelated thread activity override an explicit blocked/scope state. Apply the ECRN closeability exception only after the row workflow item ID, exact post/root thread identity, deterministic state entry, completed stage, and concrete completion/signed-document receipts all agree.
- For Project List / workflow rows, use structured columns over prose: `message_origin`, `prompting_context`, `project_update_status`, `project_update_issue_id`, `project_update_history_verified`, `workflow_*`. Keep rows open/pending when history write/readback is missing or `workflow_outcome_verified=no`. This applies even when the row has bot-reply evidence or the reply text says an approval/workflow step is complete; prose such as “all approvals complete” is not a workflow receipt unless an exact outcome/readback field or nearby completion row verifies it. In particular, `message_origin=pd_one_prompted_user` plus `prompting_context=pd_one_prompt` / ECRN-like approval language should stay `keep_open_pending_work` when `workflow_outcome_verified=no`, even if PD One later replied that all approvals are complete. If later same-root rows show ECRN attachments or signed document posts, treat them as possible evidence to mention, not automatic closure: recommend approval-needed admin/workflow verification unless a structured ECRN approval/final-release outcome receipt or exact workflow state readback is present.
- ECRN exception: an ECRN row whose structured outcome is still `no` may be upgraded to `likely_closeable_after_verification` only when the exact Mattermost root/thread, the row's workflow item ID, and the deterministic ECRN state entry all agree, the state is advanced/`complete`, and there is concrete completion evidence such as an all-required-approvals post plus a signed-document post with a verified file/post receipt. This is still a read-only recommendation; do not close the Sheet row. If exact-thread ECRN IDs differ from the row's `workflow_item_id` or the thread root maps to another state item, classify it as `automation_or_tooling_issue` / workflow-integrity review, even if the other item is complete; do not replay or mutate either workflow.
- Classify common buckets conservatively: onboarding/profile gaps and scope/approval blocks as `needs_admin_approval`; no-reply evidence or poor employee-facing response as `needs_pd_one_corrective_reply`; reviewer failures/auth failures/stale inconsistent closed+follow-up flags and exact workflow-ID mismatches as `automation_or_tooling_issue`; workflow rows without verified readback as `keep_open_pending_work`. 
- Temporary exports containing Sheet values or Mattermost thread payloads are evidence-only artifacts: delete them, along with ad-hoc parsing helpers, after the bounded report and verification are complete. Retain only concise counts, physical rows, stable IDs, category, and recommendation in durable reports/plans.
- Report counts and concise row IDs/physical row numbers only. Do not paste raw transcripts; do not mutate Sheet cells, send corrective replies, or close rows unless Andy separately approves the exact write/send.
- Separate currently open rows from stale/inconsistent already-closed rows. Rows with `review_status=closed` but `follow_up_needed=yes` are normally an `automation_or_tooling_issue` / cleanup backlog, not employee follow-up and not a reason to reopen in read-only supervisor mode.
- For supervisor reports, a practical compact category breakdown is: `likely_closeable_after_verification`, `needs_admin_approval`, `needs_employee_followup`, `needs_pd_one_corrective_reply`, `automation_or_tooling_issue`, `keep_open_pending_work`, and `unclear_needs_human_review`. Use workflow/readback fields to keep Project List rows in `keep_open_pending_work`; use reviewer/auth/tool-failure flags and stale closed+follow-up flags for `automation_or_tooling_issue`; use no-reply/poor-quality/future-follow-up-without-job rows for `needs_pd_one_corrective_reply`; use explicit approval/scope/source-access blockers for `needs_admin_approval`; use `closed_by_pdneo`, `closure_basis`, or verified reply-post evidence only for `likely_closeable_after_verification`. Do not classify a no-reply row as `needs_admin_approval` solely because old structured columns contain generic approval text such as `approval request failed before creation`; require an actual scope/profile/permission blocker in the row.
- When the supervisor prompt asks for a concise Andy-facing report, group row patterns deterministically before writing prose: current `*_no_reply_evidence` rows with no bot-reply evidence are normally `needs_pd_one_corrective_reply`; explicit approval/scope/source-access blockers are `needs_admin_approval`; Project List or other workflow rows with `workflow_outcome_verified=no` or history readback missing are `keep_open_pending_work`; reviewer failures, provider/auth failures, tool-chattery responses, or already-closed rows that still have `follow_up_needed=yes` are `automation_or_tooling_issue`. This avoids over-counting old approval text or treating a workflow prompt/reply as complete before readback.

Require explicit human approval before:

- restarting OpenClaw/gateway services
- killing processes
- changing tokens, webhook URLs, gateway ownership, or credentials
- replaying external sends/messages
- writing production data
- destructive cleanup beyond a validated generated/cache/queue path

## Recurring scanner boundedness pitfalls

- Keep recurring scan jobs deterministic and bounded. Do not let the timed scanner path spawn one model/agent enrichment task per new row (translation, reply-summary, quality-review, etc.); that can consume the whole wrapper timeout and repeatedly fail with `exit 124` even though Mattermost/Sheets are healthy.
- For PD One Mattermost `review_log` scanner wrapper fixes, prefer disabling enrichment in the cron/systemd path while preserving raw row capture, for example: `scan-dms --no-translate`, `scan-interactions --no-translate`, `REVIEW_LOG_REPLY_SUMMARY=0`, and `REVIEW_LOG_RESPONSE_QUALITY=0`. When the append path normally writes a `not_reviewed` placeholder, add a defer-quality mode that leaves quality fields blank so a separate backfill can find the row. Run enrichment separately/backfill-style with a per-tick limit and an inner reviewer timeout shorter than the enclosing stage timeout.
- Queue acknowledgement must happen only after every required maintenance stage succeeds. Do not read-and-truncate a candidate queue before scanning/backfill: a timeout then loses the exact retry window. Prefer an append-only JSONL queue plus a durable byte checkpoint (including file identity/truncation detection) saved atomically with successful supervisor state. On failure, leave the checkpoint unchanged so the same events retry. Apply backfill limits after filtering already-reviewed/admin rows so a small per-tick limit cannot starve deferred rows.
- Write a compact stage receipt before and after each command (`running` / `completed` / `failed`, elapsed seconds, bounded error). A timeout alert should identify the failed stage instead of only showing the outer subprocess command.
- When auto-repair reads a long retained log, key diagnosis on the latest wrapper attempt (`[timestamp] attempt=N rc=M`) rather than searching the whole tail for old timeout strings. Old failures remain in the log after later successful attempts.
- A guarded repair hook for this class should preserve primary human alerts, then call the allowlisted repair runner. The repair script may reset-failed/start only the specific scanner service when inactive/failed; it must not kill an active scanner, restart gateways, change credentials/policy, or replay external sends.

### Hardened queue and enrichment split

Use this implementation shape when an outer supervisor times out around a scanner that also performs per-row model enrichment:

1. **Capture stage:** run scanners with translation, reply summarization, and semantic quality review disabled. If the normal append helper writes a `not_reviewed` result, add a defer mode that leaves quality fields blank rather than creating a value the backfill will skip.
2. **Queue semantics:** keep the producer queue append-only. Read a bounded batch from a durable byte offset, but do not save the next offset until header checks, scanning, source collection, quality backfill, and final issue enumeration have all succeeded. Include file device/inode plus a short prefix hash in the checkpoint so rotation or same-size truncation resets safely; appends after the claimed batch remain for the next run.
3. **Backfill semantics:** filter admin rows and rows that already have quality status before applying a small per-tick limit. Keep the reviewer's inner timeout shorter than the enclosing backfill stage, and keep the overall wrapper timeout below the scheduler's hard budget.
4. **Receipts:** overwrite a small current-stage JSON receipt on every transition with stage, status, elapsed seconds, timeout, queue count, and bounded error. On success, also save the queue checkpoint atomically with the supervisor state.
5. **Regression tests:** prove retry without acknowledgement on stage failure, acknowledgement only after all stages succeed, newly appended events remain readable after the prior checkpoint, rotation/truncation resets, deferred capture leaves quality blank, filtered limits cannot starve missing employee rows, and reviewer timeout is environment/config bounded.
6. **Live verification:** run compile/unit checks, non-mutating scanner/source/backfill probes, then observe one real scheduler tick. Require `last_status=ok`, a `complete` stage receipt, advanced checkpoint matching the processed queue boundary, and clean/silent cron output. A gateway restart is unnecessary when only cron-invoked scripts change.

Do not treat increasing only the outer timeout as the repair. The durable fix is deterministic capture plus separate bounded enrichment and failure-safe acknowledgement.

## Migrating a legacy OpenClaw scanner to Hermes PD One

When the failure shows legacy OpenClaw command/runtime coupling, migrate the recurring scanner class as a runtime-owner change, not just a command substitution:

- Move scanner state, locks, and wrapper logs under the active Hermes profile, e.g. `/home/prodesign/.hermes/profiles/pdone/state` and `/home/prodesign/.hermes/profiles/pdone/logs`.
- Replace OpenClaw command dependencies (`openclaw agent`, `openclaw message send`, legacy `summarizer`) with Hermes profile-scoped equivalents where available, and run utility/enrichment calls with bounded wall-clock time from `HERMES_HOME=/home/prodesign/.hermes/profiles/pdone`.
- Keep only explicitly documented compatibility reads when source-system credentials have not yet moved; label them as credential/data fallbacks, not runtime ownership.
- Put a nonblocking wrapper lock around the whole recurring scan so a slow run does not overlap the next timer tick and create `already_running` noise across inner scanner locks.
- Prefer one bounded wrapper attempt per timer tick plus a separate guarded auto-repair timer. Multiple in-wrapper retries can collide with the next systemd interval and obscure the real failure source.
- Size the timer interval to the measured successful smoke-run duration plus margin; if a run can take 5-8 minutes, do not schedule it every 5 minutes.

## Verification before reporting success

Read back all relevant evidence before telling the user it is live or repaired:

- webhook/listener or guarded-auto-repair target health/log receipt
- subscription/prompt includes the scanner-specific checks
- smoke-test POST or guarded repair invocation accepted and logged, if safe
- latest scanner attempt shows `rc=0` after the change, not just an older successful run
- systemd timer is active/waiting and the service shows success/inactive or a valid currently-running bounded attempt
- fallback queue worker exists and is enabled/scheduled when webhook delivery is part of the path
- local git/backup status, commit, and push receipts when config/scripts were changed

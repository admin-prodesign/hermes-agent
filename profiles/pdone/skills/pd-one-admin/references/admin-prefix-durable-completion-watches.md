# Admin-prefix durable completion watches

Use this reference when changing or debugging `workspace/plugins/admin-prefix-escalation/index.js` final-result callbacks, `admin:` routing, or approved-ticket execution from Mattermost approval threads.

## Problem solved

`admin:` escalations can exceed the initial synchronous wait window. A purely in-process watcher posts the final admin result later, but it is lost if the OpenClaw gateway restarts before completion. The durable watcher pattern makes pending callbacks restart-survivable.

## Current implementation shape

- Pending watch state lives at `workspace/state/admin-prefix-completion-watches.json`.
- Plugin config may override this with `adminCompletionWatchStatePath`.
- On initial `waitForRun()` timeout, `admin-prefix-escalation` must persist the watch record before returning the interim Mattermost reply.
- The in-process watcher still runs immediately and keeps `activeWatches` as a per-process duplicate guard.
- On plugin registration/startup, pending durable records are loaded and resumed.
- After the final sanitized result is posted to Mattermost, the durable record is removed.
- If waiting/posting fails, the record stays pending and stores attempt/error metadata so a later startup can retry.

## Record fields

Each watch is keyed by `watchKey` such as `admin-prefix:<origin-post-id>` and stores:

```json
{
  "watchKey": "admin-prefix:admin-command-post",
  "runId": "run-1",
  "sessionKey": "agent:admin:mattermost:group:...",
  "accountId": "default",
  "conversationId": "origin-channel-id",
  "rootId": "origin-thread-root-post-id",
  "replyToId": "admin-command-post-id",
  "timeoutMs": 7200000,
  "status": "pending",
  "updatedAt": "...",
  "attempts": 0,
  "lastError": "..."
}
```

## Required tests

Keep `workspace/tests/admin-prefix-escalation-timeout.test.mjs` covering these paths:

1. Approved ticket decision starts the admin runner, completes the ledger, and posts the final result to the origin thread.
2. Approved ticket decision still works for the live Mattermost event shape where `provider`/`event.channel` may be absent or generic and `ctx.channelId`/`event.channelId` is the real Mattermost channel id, not the literal string `mattermost`.
3. Initial timeout followed by in-process completion posts exactly once to the origin thread.
4. Initial timeout persists a pending watch, simulated plugin restart resumes it, final result posts to the origin thread, and a second simulated restart does not repost.

Run with:

```bash
cd /home/prodesign/.openclaw/workspace
node --test tests/admin-prefix-escalation-timeout.test.mjs
python -m pytest tests/test_admin_approval_tickets.py tests/test_admin_approval_listener.py tests/test_admin_approval_executor.py -q
```

## Approval-decision debugging pattern

When Andy says an approved admin thread did nothing, inspect the Mattermost approval thread and ticket state before assuming the admin runner failed:

1. Confirm the approval post exists in the admin approval thread or the ticket's exact recorded origin thread. Strict explicit forms are `approve PDAPP-...` / `reject PDAPP-...`; `admin: approve PDAPP-... @pdone` is also valid when the source post is re-fetched and its sender/channel/root bind exactly to that ticket. Bare bilingual translated forms such as `已核准 / Approved` or `不同意 / Not approved` remain limited to the bound approval thread and one unambiguous pending ticket.
2. Check whether the approval listener accepted it by reading the ticket state: accepted approvals move from `pending` to `queued`; skipped approvals often leave a bot reply that looks like a normal admin-agent/tool failure. If an admin-prefixed or translated approval was missed, inspect the Python listener parser, the JS prefilter in `plugins/admin-prefix-escalation/index.js`, and the Hermes `agent:start` approval hook.
3. Inspect the Hermes hook log before blaming the ledger. `missing_or_invalid_message_id` means the hook lacked the stable Mattermost post receipt needed for source re-fetch and must fail closed. Verify the gateway hook context sets `message_id` from `_reply_anchor_for_event(event)`, the Mattermost adapter builds `MessageEvent(message_id=post_id)`, and the approval hook receives the 26-character post ID.
4. Compare gateway process start time with the relevant gateway/hook source mtimes. If the running gateway started after the receipt fix, do not restart it merely to repeat deployment; if it predates the fix, a restart is still a separate explicit-approval gate.
5. Reproduce both supported event shapes: (a) a bound Admin-thread `approve <ticket>` event and (b) an exact-origin-thread `admin: approve <ticket> @pdone` event with appended translation text. Each should produce one idempotent decision, one queued ticket, and no generic dangerous-command prompt.
6. MCP tool schemas are session-cached. A safe decision tool may exist in `pd_one_safe_ops_mcp.py` and the capability registry yet be absent from an older thread's tool list. Do not improvise with `execute_code` or raw CLI; use a fresh/reloaded MCP session under its approval gate, or let the deterministic pre-agent hook record the exact source post.
7. If replaying the listener manually moves a ticket to `queued`, remember that it does not automatically start live admin execution unless it goes through the approved executor/drain path.

## MCP-backed decision path and fail-closed fallback

Treat approval authorization, ledger mutation, and approved work execution as three separate layers:

1. **Authorization:** a deterministic Mattermost listener validates the exact sender ID, exact decision text/ticket ID, and trusted source-post context. The preferred location is the ticket's bound Admin approval thread. If same-origin-thread approvals are intentionally supported, accept them only when the live post's channel/root exactly matches the origin channel/root stored on that ticket; never accept an approval from an arbitrary channel merely because it names a ticket.
2. **Ledger mutation:** route `approve`/`reject` through a narrow admin-only typed operation (for example `pd_one_admin_approval_decide`), not a generic command runner. Require `ticket_id`, `decision`, and `decision_post_id`; the backend must re-fetch the Mattermost post and independently verify sender, text, thread relationship, current ticket state, and scope. Use the decision post ID as the idempotency key and return a readback transition receipt such as `pending -> queued`.
3. **Execution:** dispatch only a capability registered on the approved ticket. Never expose a generic shell/script MCP operation as the approved executor. Claim, complete, or fail the ticket through bounded typed transitions with receipts and origin-thread completion delivery.

MCP is an adapter, not authorization. An MCP call is safe only when its backend re-validates the trusted Mattermost evidence and enforces the ticket state machine. Model-supplied `actor_user_id`, channel IDs, or `approved=true` flags are not sufficient evidence by themselves.

If a typed decision capability is unavailable or not exposed in the current session, fail closed: report that the approval was not recorded and point to the bound approval location or admin handoff. Do **not** fall back to `execute_code`, terminal, inline Python, the legacy ticket CLI, or a user-visible dangerous-command `/approve` prompt. Likewise, if the approved operational capability is unavailable, keep the ticket queued/pending and surface the capability gap rather than improvising execution.

Required regression coverage:

- exact active admin in the bound approval thread succeeds;
- intentionally supported exact origin-thread approval succeeds only for that ticket's recorded origin;
- wrong sender, wrong thread, quoted approval text, and mismatched ticket ID fail;
- duplicate decision-post replay is an idempotent no-op;
- completed/rejected tickets cannot be reopened;
- missing typed capability produces a clean bounded status, never a dangerous-command prompt;
- end-to-end `pending -> queued -> claimed -> completed` posts one verified completion receipt.

## Backlog/drain pitfall

A ticket with `status: queued` and no `claimed_at_utc` proves the approval was recorded but not drained by a worker. Treat this separately from approval-listener bugs: the approval hook may be fixed while a durable queued-ticket drain/worker is still missing or stalled. Report both conditions distinctly.

## Stuck-ticket monitoring pattern

Approval-ticket health is not proven by the existence of the ledger/tools or by an empty `admin-prefix-completion-watches.json`. For PD One project-triage or reliability reviews, add a read-only ledger replay before calling the workflow healthy:

1. Locate the active ledger, usually `workspace/state/admin-approval-tickets.jsonl`, and replay events by `ticket_id` using the deterministic ticket tool when possible (`admin_approval_tickets.py --ledger ... list-open`) or a small local parser when CLI output is too verbose for chat.
2. Summarize final ticket states, not raw event-line statuses. Useful buckets: `queued`, `in_progress`, `pending`, `approved`, `needs_employee_info`, `needs_employee_confirmation`, `completed`, `failed/rejected/cancelled/expired`.
3. Treat these as stuck conditions for a dry-run/no-agent watchdog:
   - `queued` with no `started_at_utc` or claim older than 30 minutes;
   - `in_progress` whose lease is expired or whose last event is older than the intended execution window;
   - `pending` admin notification older than 24 hours;
   - `approved` or resource-bound tickets without completion older than 24 hours;
   - very old `needs_employee_info` / `needs_employee_confirmation` rows as lower-priority hygiene, not execution failures.
4. The watchdog should be silent when clear and emit only an admin-only concise alert when stuck tickets exist. It should recommend `close / retry / manual run / ask employee for missing info`, but must not mutate tickets, send employee messages, or execute source-system writes automatically.
5. If no systemd/cron watchdog exists for approval tickets, report that as a monitoring gap even when the ticket tools and tests exist.

## Manual approved-ticket execution pattern

When Andy explicitly asks for a manual run of an already-approved request, finish the ticket ledger as part of the run, not just the external side effects:

1. Read the ticket and scope first; identify allowed source channels, write targets, scheduling/sharing limits, and any red lines.
2. If Andy separately asks for a gateway restart, use the bounded restart/health pattern from `references/pd-one-gateway-restart.md` and verify the gateway is ready before executing the ticket. Do not treat a ticket's general approval as implicit restart approval.
3. Claim the ticket before or at the start of the manual run with a stable worker id and idempotency key.
4. Execute only the approved scope. For newly-created resources, bind them back to the ticket with `bind-resource` so continuation policy and future follow-up writes have concrete target ids.
5. Append a concise action journal entry containing the operational summary and durable resource/post ids. Avoid dumping raw tool logs.
6. Complete or fail the ticket explicitly. The final employee-visible summary should separate completed work from remaining blockers, for example disabled schedules or missing source data that require a separate approval/input.
7. Read back the ticket status after completion and report `completed`/`failed` plus the key resource links.

Useful CLI shape:

```bash
python3 tools/admin_approval_tickets.py claim --ticket-id "$TICKET" --worker-id "$WORKER" --idempotency-key "$KEY-claim" --summary "Manual approved run started"
python3 tools/admin_approval_tickets.py bind-resource --ticket-id "$TICKET" --resource-type google_sheet --resource-id "$SHEET_ID" --capability google_sheet_write
python3 tools/admin_approval_tickets.py append-action --ticket-id "$TICKET" --idempotency-key "$KEY-action" --json '{"action":"manual_run_completed","summary":"...","resources":{"spreadsheet_id":"..."}}'
python3 tools/admin_approval_tickets.py complete --ticket-id "$TICKET" --worker-id "$WORKER" --idempotency-key "$KEY-complete" --summary "..."
python3 tools/admin_approval_tickets.py get --ticket-id "$TICKET"
```

For `append-action`, prefer `--json -` with the JSON document on stdin. Passing a long JSON object as the `--json` argument can be interpreted as a filesystem path and fail with `ENAMETOOLONG`; the durable lesson is to use the command's structured stdin mode, not to retry with shell quoting variations.

## Pitfalls

- Do not use the presence of a bot reply in the approval thread as proof the approval hook ran. A skipped approval can fall through to the normal admin agent and generate unrelated tool/search output.
- Do not replay approvals outside the gateway and then claim execution started; manual listener replay only mutates ledger state unless followed by the real approved-ticket execution path.

- Do not return the interim timeout message before persisting the durable watch; a crash in that gap recreates the original lost-callback problem.
- Do not rely only on `activeWatches`; it is intentionally process-local and disappears on restart.
- Remove the durable record only after the final Mattermost post succeeds.
- Keep the final reply sanitized. Read the latest assistant message from the admin session; do not expose raw tool logs, session keys, private prompts, credentials, or stack traces.
- This is at-least-once delivery, not strict exactly-once. If the process crashes after Mattermost accepts the final post but before the durable record is removed, restart may duplicate the final post. Strict exactly-once would require a stronger outbox with post-id/ack journaling.

## Deployment guardrail

Gateway restarts require explicit Andy approval immediately beforehand. Validate config first, restart with the bounded systemd pattern in `references/pd-one-gateway-restart.md`, then verify new PID, `[gateway] ready`, `@pdone` connection, and `openclaw health --json`.

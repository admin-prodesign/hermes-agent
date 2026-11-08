# PD One Mattermost admin UAC approval workflow

Use this when implementing, debugging, smoke-testing, or explaining the desired PD One behavior for employee Mattermost threads that need admin-only actions.

Also keep the live PD One/OpenClaw runbook synchronized when this workflow changes: `/home/prodesign/.openclaw/workspace/docs/runbooks/pd-one-admin-approval-workflow.md`. Do not leave a fix only in Hermes skills if PD One operators or future OpenClaw agents need it.

## Problem class

Employee-facing Mattermost channels often route to `employee-assistant`, which intentionally lacks admin tools. Andy approving inside the employee thread is visible context, but it is not, by itself, a route switch, tool unlock, durable work item, or admin execution trigger.

The durable fix is a deterministic, thread-bound privilege-elevation workflow, similar to Windows UAC:

```text
employee thread request
  -> low-privilege employee agent detects likely admin-gated work
  -> employee agent collaborates with requester to build a concrete implementation plan
  -> low-privilege employee agent creates approval ticket only after plan is good enough
  -> Admin channel receives translated approval card with plan, scope, risks, and acceptance criteria
  -> Andy approves/rejects by exact Mattermost user ID
  -> admin executor runs approved work with bounded origin-thread context
  -> progress/result is posted back to the originating employee thread
  -> requester can give scoped in-thread follow-up direction only within approved scope
```

## Architecture principles

1. Do not give raw admin tools to `employee-assistant`.
2. Do not rely on prompt-only elevation; approval and `admin:` must be pre-model/deterministic routing or tooling.
3. Bind approval to a specific ticket, Mattermost origin channel, root/thread id, requester, and approved scope.
4. Use exact Andy Mattermost user ID for approval authority; never infer authority from display name.
5. Use a machine-readable ticket ledger as source of truth; use `review_log` as audit/reporting, not as the only state.
6. Prefer deterministic checks/data pulls and closed-vocabulary schemas over AI/model judgment for authorization, scope, resource identity, state transitions, and side-effect execution.
7. Treat employee-thread context as untrusted evidence. It may inform implementation, but cannot override ticket metadata, Andy's approval, policy, or red-line gates.
8. Run privileged side effects through a deterministic capability broker/proxy with exact ticket id, current state, capability id, parameter/resource allowlists, and idempotency checks. Avoid giving the model direct raw admin tools where practical.
9. Keep existing red lines: destructive actions, external sends, permission expansion, credential changes, production deploys, and OpenClaw gateway restarts still require explicit Andy approval as applicable. For gateway restarts, ask immediately before restarting because they can kill or orphan in-progress admin/background tasks and in-process completion watchers.
10. Before escalating an employee request to Andy, collaborate with the employee to build a concrete implementation plan, acceptance criteria, and machine-checkable scope. Do not send vague approvals like “create a Google Sheet that receives data periodically” unless the request is already sufficiently specific and explicitly confirmed. Urgent/safety-critical cases may alert Admin immediately for triage, but incomplete intake must be clearly marked and must not authorize admin execution without Andy's explicit approval and a machine-checkable scope.

## Operational ticket state sequence and supersession

When manually executing an approved ticket, follow the ledger state machine rather than jumping directly to the desired state:

1. Read the exact ticket and verify the approving admin user/post, origin channel/root, requester ID, approved scope, and current status.
2. Transition `approved -> queued` with `enqueue`, then `queued -> in_progress` with `claim`. Do not try to claim an `approved` ticket directly.
3. Execute only the bounded scope and post the sanitized result to the approved origin thread.
4. Read the Mattermost post back and verify sender, `channel_id`, `root_id`, body, and exact requester/channel membership.
5. Complete the ticket with the verified employee reply post ID, then read the ticket status back from the deterministic ledger/status tool.

If the requester narrows the task and a second approved ticket explicitly supersedes the broader ticket:

- execute and complete the narrower ticket first;
- send one final employee result, not one result per overlapping ticket;
- complete the original ticket as superseded, referencing the narrower ticket and the same verified employee reply post;
- verify both tickets are `completed` so no stale approval remains open.

A ticket's `employee_visible_summary` is not proof that the employee saw it; the verified origin-thread post is the delivery receipt. Conversely, do not duplicate the employee reply merely to close overlapping tickets.

A ticket continuation/approval grant is not automatically a durable per-user permission. When Andy explicitly grants this class of request going forward, update the canonical exact-sender policy, regenerate the policy cache, verify the effective scope, and back it up separately from closing the ticket.

### Executor-race and conflicting-result guard

The live approval executor may claim, complete, and post while an interactive admin session is still investigating. Prevent duplicate work and contradictory employee replies:

1. Immediately after recording Andy's decision—and again immediately before `enqueue`, `claim`, `complete`, or origin-thread delivery—re-read the ticket status and inspect recent bot posts in the exact origin thread.
2. If the ticket is already `queued`, `in_progress`, or `completed`, do not force a second state transition. Determine whether the live executor is still running or already delivered before doing any manual execution.
3. Treat `employee_visible_summary` and a completed status as delivery/state evidence, not as proof that the underlying investigation is correct. Verify material source claims independently before adopting the summary.
4. If a live executor posted an incomplete or incorrect result, preserve the audit trail: post an explicit same-thread correction, identify the later source-verified report as authoritative, read both posts back, and append a ticket action containing the superseded post ID, authoritative post ID, correction post ID, corrected counts/conclusion, and evidence scope. Do not attempt to reopen or re-complete a terminal ticket merely to change its summary.
5. Before adding a durable permission scope requested in Andy's approval text, inspect the canonical exact-sender policy. Another overlapping approved ticket may already have installed an equivalent scope. If the effective scope already satisfies the request, regenerate/verify the cache instead of adding a duplicate alias.
6. For overlapping tickets, coordinate on one authoritative employee result. A narrower ticket may supersede a broader ticket, but the executor race must be resolved before either workflow posts.

A manual admin session is not allowed to assume it owns the ticket just because it recorded the decision; ownership is established by the current ledger state and active executor lease.

## Recommended implementation shape

### 1. Ticket ledger

Create a helper such as `workspace/tools/admin_approval_tickets.py` with append-only JSONL state, e.g. `workspace/state/admin-approval-tickets.jsonl`, plus optional compact index. Provide commands such as:

- `create`
- `get`
- `list-open`
- `decide`
- `start`
- `complete`
- `fail`

Use file locking around writes and avoid storing credentials, raw unrelated transcript dumps, or broad private context. If multiple workers/hosts or non-local filesystem semantics are involved, use SQLite WAL with an outbox/leases table instead of JSONL. Define one canonical state machine that includes notification failure, queued, in-progress, completed/failed, cancellation, expiry, and explicit retry transitions. Decision + queueing must be atomic or outbox-backed.

Core ticket fields:

```json
{
  "ticket_id": "PDAPP-YYYYMMDD-abcdef12",
  "status": "pending|approved|rejected|in_progress|completed|failed|needs_clarification",
  "requester_user_id": "...",
  "requester_label": "...",
  "origin_provider": "mattermost",
  "origin_channel_id": "...",
  "origin_channel_name": "...",
  "origin_root_id": "...",
  "origin_post_id": "...",
  "admin_channel_id": "...",
  "admin_approval_post_id": "...",
  "request_original": "...",
  "request_english": "...",
  "requested_action": "...",
  "approved_scope": "...",
  "required_capabilities": ["..."],
  "risk_summary": "...",
  "andy_decision": {
    "user_id": "...",
    "decision": "approved|rejected",
    "instructions": "...",
    "post_id": "...",
    "at_utc": "..."
  }
}
```

### 2. Employee plan-building intake before approval

Before `request_approval` sends anything to Admin, the employee-facing agent should refine underspecified admin-gated requests with the employee. It can say: “This looks like it will need approval. Let’s work together to build the plan to a good enough level where I can ask for approval.”

For a Google Sheets/channel-sync request, use a readiness validator such as `google_sheet_channel_sync_v1` and collect a reviewable plan with:

- required deterministic fields: origin provider/channel id/root id/post id, requester id, channel policy, candidate source scope;
- required employee-confirmed fields: business goal, data boundaries, columns or extraction rules, sheet owner/audience, acceptance criteria;
- required scheduled-work fields: cadence, timezone, start date or safe default, initial backfill window, and whether first import must be reviewed before schedule enablement;
- safe defaults: no external recipients, no destructive behavior, no permission changes, schedule disabled initially, first import review required, daily maximum cadence;
- blocking missing fields: source boundary, write/share policy, extraction rules or columns, acceptance criteria, and cadence for scheduled work.

Use deterministic checks/data pulls for facts PD One can safely inspect, such as channel id/name, thread id, visible sample message structure, existing channel policy, and configured schedule limits. Ask targeted questions only for missing requirements. Employee-provided text may inform summaries, but must never directly set trusted capability scope, source ids, write targets, external recipients, red-line flags, or approval status. Validate model-extracted fields through closed-vocabulary schemas and deterministic allowlists before storing them as trusted metadata. Summarize the draft plan back to the employee and require explicit confirmation before escalation except for narrowly logged Admin-triage alerts that do not authorize execution.

### 3. Employee `request_approval` becomes actionable

Modify `workspace/plugins/pd-one-employee-safety-gate/index.js` so its `request_approval` path creates a ticket and posts an Admin-channel approval card, not just a `review_log` row.

The approval card should include:

- ticket id;
- requester and origin thread link;
- concise English summary for Andy;
- implementation plan summary and acceptance criteria;
- unresolved assumptions/options, if any;
- original request excerpt, often Traditional Chinese;
- requested capabilities;
- risk/write/external-send summary;
- approval syntax examples: `approve PDAPP-...`, `approve PDAPP-... with: ...`, `reject PDAPP-...: ...`.

If Admin notification fails, do not tell the employee it was successfully sent; mark the ticket state accordingly.

Implementation pitfalls to avoid:

- Use a stable idempotency key for the approval request, derived from origin thread/channel, requester, normalized requested action, and requested scope. Do not include `Date.now()`, random UUIDs, or the current confirmation message id in the idempotency key, or the later confirmation message will create a new ticket instead of resuming the draft.
- Treat the ticket ledger as the source of truth and `review_log` as non-blocking audit/reporting. If the Google Sheets-backed `review_log` append times out after ticket creation/readiness validation, return the ticket id and mark/report the review-log failure instead of failing the whole tool. Otherwise the model may retry and create duplicate drafts even though the ledger already captured the request.
- The confirmation step must load/reuse the existing `needs_employee_confirmation` ticket and confirm it before any readiness revalidation. Revalidating first can fail closed because readiness validation normally accepts only draft/intake states.
- Andy/admin-policy requesters should not be forced through a separate employee-confirmation loop once readiness passes. If the requester has trusted admin approval authority, confirm/escalate the ticket deterministically and notify Admin; do not strand it in `needs_employee_confirmation` just because it entered through an employee/fallback route.
- Derive confirmation post ids from the current Mattermost event/context when available, but support a bounded explicit confirmation-post-id parameter/fallback so missing runtime context does not permanently block an already confirmed ticket. Do not let a model invent or change approval authority; the ledger state and policy remain authoritative.
- If a repeat call finds an existing ticket already awaiting confirmation, return that state and ask for confirmation rather than trying to mutate it again.
- Preserve real Mattermost origin metadata at ticket creation time. If `ctx.conversationId`, `ctx.channelId`, `ctx.rootId`, or `ctx.threadId` are missing/ambiguous, recover the origin channel and thread from the Mattermost session key before writing the ticket. Support both legacy `...:channel:<id>:thread:<root>` session keys and generic peer session keys such as `...:group:<channel-id>:thread:<root>` / `...:direct:<dm-id>:thread:<root>`. Never let `origin_channel_id` degrade to the literal string `mattermost` or `origin_root_id` to blank for a channel/thread approval request; otherwise the admin executor may complete the work but cannot post the employee-visible completion summary to the original thread.
- Treat the origin employee-thread notification as a required completion side effect, not a courtesy. After Andy approval and admin execution, PD One must post a sanitized result/approval notice in the originating employee thread so the requester knows approval was granted and the work was done. An Admin-channel-only acknowledgement is incomplete. If a legacy or failed run completed the work without notifying the employee, backfill a concise notice from the PD One bot to the origin channel/root, verify by Mattermost readback (`channel_id`, `root_id`, post id/link), and append an audit/ticket action documenting the backfill.

### 4. Admin-channel approval listener

Add a deterministic handler/plugin or worker for Admin channel messages:

- verify sender is Andy's exact Mattermost user ID;
- verify provider/account/team/channel id and exact Admin channel id;
- prefer explicit ticket-id syntax such as `approve PDAPP-...` / `reject PDAPP-...`;
- accept bare approve/reject only as an unambiguous reply to the exact approval-card thread/root for one pending ticket;
- use anchored parser grammar and reject fuzzy/quoted/negative forms such as `I don't approve`, blockquotes, copied approval cards, or edited approval messages;
- parse approval verbs case-insensitively (`approve`, `Approve`, `REJECT`) because the OpenClaw plugin prefilter may be case-insensitive and Andy will naturally vary capitalization;
- reject/log non-Andy attempts;
- ask for clarification if an approval is ambiguous;
- update the ticket and enqueue execution with compare-and-swap/idempotent state transitions.

### 5. Admin executor

Current PD One implementation note (2026-07-20): the active Hermes `pdone` profile separates the short deterministic decision hook from the durable executor. `hooks/pd-one-admin-approval-listener/handler.py` validates the exact Mattermost post and records/enqueues the ticket only. `scripts/pd_one_admin_approval_executor.py`, scheduled by `pd-one-admin-approval-executor.timer`, claims one eligible ticket, runs an isolated Hermes admin session, requires a structured receipt, posts the bilingual result to the exact origin thread with readback, and then completes/fails the ledger ticket. Existing backlog is blocked by an activation cutoff unless exact ticket IDs are allowlisted. Ambiguous crashes/delivery failures remain `in_progress` for reconciliation rather than blind retry. Load `references/hermes-pdapp-durable-executor.md` for the active paths and operating procedure. Legacy `workspace/plugins/admin-prefix-escalation/index.js` and `workspace/tools/admin_approval_executor.py` are historical migration references, not the active runner. User expectation remains: approvals should lead to actual execution before reporting back; a conversational acknowledgement without dispatch is a regression unless explicitly labeled blocked/pending with a machine-verifiable reason.

Create or maintain an executor such as `workspace/tools/admin_approval_executor.py` or an OpenClaw plugin/runtime equivalent. Given a ticket id, it should:

1. load ticket state;
2. fetch bounded origin-thread context via Mattermost API or runtime session history;
3. load relevant channel/user policies;
4. invoke the `admin` agent/subagent with a self-contained prompt containing the ticket, Andy instructions, approved scope, and red lines;
5. route every privileged operation through a deterministic capability broker/proxy that validates the active ticket id, state, capability id, exact parameters/resource ids, red-line flags, and idempotency key before execution;
6. bind resources created by the ticket, such as spreadsheet/workflow/cron ids, back to the ticket before allowing later writes; never accept arbitrary employee-supplied resource URLs as allowed targets;
7. post only sanitized `employee_visible_summary` content to the origin Mattermost thread/root id, keeping `admin_private_details`, raw tool logs, secrets, stack traces, session keys, and private policy details out of employee-visible output;
8. update ticket status and action journal.

For long-running work, prefer durable queued execution over a synchronous wait that can time out.

### 6. Scoped requester continuation

After approval, create a continuation policy bound to the requester, origin channel, root/thread id, approved scope, exact allowed capabilities/resources, and short expiry. Allow in-scope clarifications and implementation choices in the same thread only after deterministic checks pass. If semantic interpretation is needed, the model may propose a classification, but ambiguous cases default to re-approval and the deterministic broker remains the authority. Require new approval for source expansion, new write targets, external sharing, destructive changes, permission/credential changes, production deployments, gateway restarts, or unrelated admin diagnostics.

### 7. Andy `admin:` shortcut

The existing `workspace/plugins/admin-prefix-escalation/index.js` is the right class of mechanism for Andy's direct thread escalation: pre-routing detection, exact sender-ID check, bounded source context, admin subagent execution, and employee-thread response.

For the complete UAC workflow, adapt `admin:` to create or attach to a full structured ticket/work item as an already-approved admin instruction, so it is auditable and durable for long-running work. This must fail closed: if the ticket/ledger record cannot be created and enqueued, do not route the request to the admin agent. It must use the same capability scope, channel/root/post binding, policy validation, red-line flags, expiry, action journal, and output visibility controls as normal approvals. Default to admin-only output for private diagnostics, secrets/logs, unrelated channels, ambiguous visibility, or destructive/external/restart/deployment/credential operations.

If the admin subagent exceeds the initial synchronous wait window, `admin-prefix-escalation` must not leave a manual follow-up burden. It should return an interim message that the final result will be posted automatically, register an in-process background completion watcher keyed by the originating admin command post/run, wait for the admin run to complete, read the final assistant message from the admin session, and send that sanitized final text back to the original Mattermost channel/thread via the Mattermost outbound adapter (`sendText` with `to`, `threadId`, and `replyToId`). Cover this with a regression test that simulates `waitForRun` returning `timeout` first and `completed` later, then asserts the final text is posted to the origin thread.

The background watcher must clean up its in-process guard in a `finally` block (`activeWatches.delete(watchKey)`) so completed, failed, timed-out, or send-failed watches do not permanently block retries or leak memory. The current `admin-prefix-escalation` implementation also persists pending completion watches to `workspace/state/admin-prefix-completion-watches.json` (configurable via `adminCompletionWatchStatePath`) before returning the interim timeout message, removes the durable record after a successful post, and resumes pending records on plugin registration/gateway startup. This makes final-result callbacks restart-survivable in the normal case. See `references/admin-prefix-durable-completion-watches.md` for the focused maintenance pattern and regression tests. Remaining caveat: if the process crashes after Mattermost accepts the final post but before the durable record is removed, a later restart may retry and duplicate the final post; a stronger outbox with post-id/ack journaling would be needed for strict exactly-once delivery.

## Live behavior double-check protocol

When Andy asks whether admin approvals will properly reply to the originating employee thread, verify both the static implementation and the runtime/deploy boundary:

1. Inspect the live approval executor path, currently `workspace/plugins/admin-prefix-escalation/index.js`, and confirm approved-ticket decisions call the admin runner and then `sendMattermostThreadReply` with `conversationId = ticket.origin_channel_id`, `rootId = ticket.origin_root_id`, and `replyToId = ticket.origin_post_id`.
2. Inspect the intake path, currently `workspace/plugins/pd-one-employee-safety-gate/index.js`, and confirm `request_approval` preserves or recovers real Mattermost origin metadata from context/session keys; `origin_channel_id` must never degrade to the literal provider string `mattermost` for channel/thread requests.
3. Run the focused regression commands below, including the tests that assert approved-ticket execution posts to the origin thread and that Mattermost group/thread route recovery works when direct tool context omits channel/thread fields.
4. Run `openclaw config validate` from `/home/prodesign/.openclaw` after any plugin/config change.
5. Check the gateway process start time against the touched files for the relevant plugins/tests/runbook. If code changed after the gateway started, report that the code/tests are correct but a gateway restart is needed before claiming the latest fix is definitely live. Do not restart a healthy OpenClaw gateway unless Andy explicitly approves or the gateway is already unresponsive under the bounded restart rule.
6. Report confidence separately for (a) tickets that already have correct origin metadata, and (b) future intake cases that depend on newly patched metadata recovery.

## Focused regression commands

When changing or double-checking the approval-ticket intake/notification path, run the focused suites before restart/deploy:

```bash
cd /home/prodesign/.openclaw/workspace
node --check plugins/pd-one-employee-safety-gate/index.js
node --test tests/request-approval-tool-timeout.test.mjs tests/admin-prefix-escalation-timeout.test.mjs
PYTHONPATH=tools python3 -m unittest \
  tests/test_admin_approval_tickets.py \
  tests/test_admin_approval_notify.py \
  tests/test_admin_approval_listener.py \
  tests/test_mattermost_review_log.py
```

These should cover: non-blocking `review_log` timeout handling, retry idempotency, admin requester escalation without a separate confirmation loop, admin-prefix timeout completion callbacks, ticket transitions, notification, listener parsing, and review-log utilities.

## Smoke-test checklist

1. In a safe test channel, employee-like user asks for a fake admin-gated workflow.
2. Confirm PD One enters plan-building intake and asks targeted clarifying questions instead of notifying Admin immediately.
3. Employee confirms concrete plan and acceptance criteria.
4. Confirm an approval ticket is created and that repeated confirmation/intake calls reuse the same ticket via stable idempotency keys.
5. Verify ticket origin metadata before approval: `origin_channel_id` is the real source Mattermost channel, `origin_root_id` is the source thread/root id, and neither value is blank/placeholder.
6. Confirm Admin channel receives translated approval card with plan, scope, risks, and acceptance criteria.
7. Verify notification-post failures mark the ticket `notification_failed` and do not claim success to the employee.
8. Andy approves with explicit ticket id, including a mixed-case command such as `Approve PDAPP-...`.
9. Executor posts the employee-visible result back to the origin channel/thread, not to the Admin approval thread. Verify the created Mattermost post by readback (`channel_id` equals ticket origin channel; `root_id` equals ticket origin root). Treat absence of this post as a failed/incomplete approval workflow even if the Admin channel shows success.
10. For previously completed tickets that missed the origin-thread notice, send a PD One bot backfill notice in the original thread, read it back, and journal the backfill action on the ticket/ledger.
11. If execution exceeds the initial wait window, verify the durable/background completion watcher later posts to the same origin thread and does not double-post after gateway restart.
12. Requester makes an in-scope follow-up; it is accepted.
13. Requester makes an out-of-scope follow-up; it creates a new approval request.
14. Ledger and `review_log` share the ticket id.
15. No OpenClaw gateway restart occurs without explicit approval.
16. If Andy asks whether the workflow “exists within PD One,” verify both layers: live implementation in OpenClaw plugins/tools and the PD One runbook under `docs/runbooks/`. If the runbook lacks the latest incident learnings, patch and commit the PD One runbook as part of the fix, then back up the Hermes skill update.

## Explanation pattern

For Andy/admin: “The fix is not to make the employee channel admin. It is to add a ticketed elevation layer: employee agent packages the request, Admin channel approves it, and an admin executor performs only the approved scope back in the original thread.”

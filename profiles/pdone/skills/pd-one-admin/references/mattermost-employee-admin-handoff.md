# Mattermost employee-channel admin handoff pitfall

Use this when diagnosing why PD One acknowledges an approved employee/channel automation request but does not execute it.

## Symptom

In a normal Mattermost channel, an employee asks PD One for an automation or integration (for example, create a Google Sheet and monitor a channel). Andy/admin approves in the same thread with wording such as `admin: approved @pdone` or `Get this set up`, but PD One continues explaining, says admin tools/approval logging timed out, or tells the employee that admin-side setup is still needed.

## Root cause pattern

1. The channel may not be explicitly bound to `admin`; if no specialized binding exists, it falls through to the Mattermost fallback route, commonly `employee-assistant`.
2. `employee-assistant` intentionally runs in the isolated employee workspace and denies privileged tools such as `cron`, `exec`, `read`, `write`, `message`, `process`, `browser`, `gateway`, broad session tools, and admin config access.
3. Approval spoken in that same employee/channel thread is conversational evidence, not a route switch and not a tool-policy elevation.
4. `request_approval` is only a review_log append / approval request wrapper. It does not implement the work, create a Sheet, schedule cron/n8n, deploy code, or automatically wake/assign the admin agent.
5. If review_log contains only `channel_interaction` rows and no open `approval_gated_request` / `blocked_tool_request` row, the approval handoff likely was not captured as an actionable admin work item.

## Triage steps

1. Resolve the Mattermost channel id and thread root. Use a bounded Mattermost API/thread read or existing export; avoid broad log pulls unless needed.
2. Check `/home/prodesign/.openclaw/openclaw.json` bindings:
   - exact channel binding to `admin` means admin agent can handle it;
   - fallback Mattermost binding to `employee-assistant` means the channel agent cannot implement privileged work.
3. Check the relevant channel policy in `workspace/policies/mattermost-channels.md` and agent posture in `workspace/docs/agent-charters.md`.
4. Inspect review_log for the employee request. Distinguish normal `channel_interaction` rows from true open approval/work rows.
5. If the bot said `request_approval` / approval tool timed out, check the OpenClaw gateway journal around the post time for `request_approval failed: spawnSync python3 ETIMEDOUT` or `request_approval review_log append failed after ticket ...`. Then check `workspace/state/admin-approval-tickets.jsonl` for partial `draft_created` / `readiness_validated` events. A 45s timeout immediately after those ledger events usually means the synchronous review-log append step exceeded its timeout (often Google Sheets/network). Current expected behavior is non-blocking review-log failure: the ticket should still be returned and retries should reuse the same ticket.
6. If readiness passed but the ticket stays `needs_employee_confirmation`, check whether the requester is an admin-policy user (for example Andy). Admin requesters should not be forced through a separate employee-confirmation loop; the plugin should confirm and notify admin once readiness passes. If an older/stuck ticket already has an explicit confirmation post in the source thread, repair it by `confirm-draft` with that post id, then `admin_approval_notify.py`.
7. Verify ticket origin metadata before approving/executing. `origin_channel_id` must be the real Mattermost channel id and `origin_root_id` must be the source thread/root id. If either is blank or the literal string `mattermost`, the final employee-visible completion callback cannot reach the originating thread. Current expected behavior is that `request_approval` recovers channel/thread from the Mattermost session key when direct tool context omits them.
8. Explain to Andy/admin that the issue is routing/capability boundary, not lack of user approval. When relevant, also state whether a draft ticket exists, whether it reached `needs_employee_info` / `pending_admin_notification` / `pending`, and whether any admin notification or implementation actually ran.

## Corrective options

- Handle the approved task from an admin-controlled surface (Mattermost admin channel, Andy admin DM, Discord admin lane, or Hermes/PD Neo admin session).
- Add or use a real approved-admin-handoff mechanism: employee-facing agent packages the spec, review_log/admin alert creates an actionable item, and admin/Hermes performs the implementation.
- If the channel should routinely support the workflow, add a deliberate specialized channel binding/policy and implementation path; do not silently grant fallback `employee-assistant` broad admin tools.

## Smoke-test expectations after approval-flow fixes

When validating the admin approval lifecycle, test the full route rather than only the happy-path ledger state:

1. `request_approval` from an employee/fallback Mattermost context must create/reuse exactly one ticket and preserve the real source thread metadata. If direct tool context is incomplete, it should recover `origin_channel_id` and `origin_root_id` from the Mattermost session key; they must not be blank or the literal string `mattermost`.
2. The approval card should appear in the Mattermost `admin` channel, and `approve PDAPP-...` in that admin thread should start admin execution.
3. The final employee-visible result must post to `ticket.origin_channel_id` + `ticket.origin_root_id`, not back into the `admin` channel approval thread.
4. Verify both code-paths: synchronous admin execution and timeout/background completion watch. The durable watch must also resume after gateway restart without double-posting.
5. For a real incident repair, post the missing completion summary to the original thread, then bind that Mattermost post id back to the ticket ledger as `origin_thread_completion_post` so future audits can see the callback happened.

Useful regression coverage in the OpenClaw workspace:

- `node --test tests/request-approval-tool-timeout.test.mjs tests/admin-prefix-escalation-timeout.test.mjs`
- `PYTHONPATH=tools python3 -m unittest tests/test_admin_approval_tickets.py tests/test_admin_approval_notify.py tests/test_admin_approval_listener.py`

## User-facing explanation pattern

For Andy/admin: “The approval is visible in the thread, but the handler is still the employee/fallback agent. Approval did not switch the session to admin or unlock implementation tools. The request needs an admin-side handoff or to be executed from an admin route.”

For employees: keep it simple and non-internal: “Andy has approved the idea; the setup requires admin-side tools, so the admin side will complete the implementation.”

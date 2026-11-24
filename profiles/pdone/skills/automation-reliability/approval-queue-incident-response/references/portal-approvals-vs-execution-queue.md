# Portal Approvals vs PDAPP execution queue

Use when Andy asks why executor-watchdog `PDAPP-*` tickets are not in the PD One Portal Approvals module.

## Two surfaces

| Surface | Question it answers | Typical ticket status |
|---|---|---|
| Portal Approvals default **Needs me** | Does a human still need to decide? | `pending` and PD Neo `review_status=human_required` |
| Executor watchdog | Is authorized work stuck after a decision? | `queued` or `in_progress` with a blocker |

The portal module at `/admin-approvals/` is a decision inbox plus a full ledger browser. It is not the watchdog. A healthy empty Needs me tab with a noisy watchdog is expected when every open ticket is already decided.

## Portal ticket filters

Frontend default `filter` is `needs`.

- **Needs me:** `review_status === 'human_required' && status === 'pending'`
- **PD Neo review:** `review_status === 'pending_review' && status === 'pending'`
- **In progress:** `approved`, `queued`, `in_progress` — includes standing grants that are supposed to stay `approved`, so the tab never drains even when one-shots complete or cancel.
- **Closed:** `completed`, `rejected`, `failed`, `cancelled`, `expired`
- **All:** every ledger ticket

Search matches ticket id, submitter, request, context, and proposal. Approve/deny buttons require `decisionable`: pending, bound action fingerprint, and `human_required`. Already-queued rows cannot be re-approved from the portal.

## Safe diagnosis (read-only)

1. Confirm the watchdog IDs with typed `pd_one_safe_ops.py approval-ticket-status --ticket-id PDAPP-...` (`ticket_status`, timestamps, `failure_reason` only).
2. If needed, read `ApprovalLedger.state()` for status counts. `expire_due_pending()` is a no-op and does not append `ticket_expired` events. A live tickets GET is still a read of the inbox, not proof that work executed.
3. Classify each ID:
   - `pending` + `human_required` → should be on Needs me.
   - `queued` / `in_progress` / `approved` → In progress / All only.
   - `completed` / `rejected` / `failed` / `cancelled` / `expired` → Closed / All only.
4. Scope-conflict watchdog reasons (`deployment_not_approved`, `destructive_action_not_approved`) on a `queued` ticket mean the recorded grant lacks a required capability flag. That is an execution-plane block, not a missing inbox row. Do not expand scope from watchdog prose; route a fresh bounded grant or reconciliation.
5. Report layers separately: portal filter, ledger status, execution blocker. State explicitly that no retry or ledger write ran unless Andy asked.

## Operator-facing answer shape

Lead with the filter mismatch, then a compact ID/status table, then where to click (**In progress** / **All**), then that portal decide controls stay off. Keep bilingual 1:1 in Mattermost channels.

## Follow-on: stuck and do not resume

If Andy asks why **In progress** still has many tickets that should already have run: lead with producer vs dispatcher vs mapping, not only the filter. Standing grants stay `approved` on purpose. One-shots sit there when the bridge is off and `mapping.exists=false`. Switch to `references/freeze-and-abandon-triage.md` for classify/abandon; do not dry-dispatch or enable the bridge to empty the tab.

## Admin sees nothing to approve

When someone says a request is stuck on approval and the admin sees no card:

1. An empty open / Needs me queue is not the end. Search Closed for `expired`, and the ledger by requester plus bound action.
2. Portal-only tickets are not posted to Mattermost. `admin_approval_post_id=portal-only` means nothing was sent to the Admin channel or by DM. Requester-facing handoff text for that class names the portal queue, not the Admin channel. Do not treat older prose that said the ticket was sent to Admin as delivery evidence.
3. Pending tickets do not auto-expire. `expire_due_pending` is a no-op. A missing card is not explained by a 24-hour decision window. Already-expired historical tickets stay expired until a human reopens them.
4. If the admin then authorizes the bound action in the origin thread, execute in-session. Do not open a replacement ticket for them to approve their own request.

## Two expiries — do not collapse them

- **Pending decision window:** removed. `notify_pending` stores an empty `pending_expires_at_utc`. `expire_due_pending` returns `[]`. Pending tickets stay until a human approves, rejects, or cancels. Already-`expired` rows stay closed until a human reopens them.
- **Execution grant expiry:** still active, typically 7 days on `approval_grant.expires_at_utc`. The executor refuses `active_approval_grant_expired`. Removing the pending window does not authorize removing or bypassing this grant.

When the admin asks to remove ticket expiry, change only the pending window. Say which control you left in place.

## Live inbox code is not the profile copy

The running Approvals page imports the portal checkout the static server was started from, not `profiles/pdone/scripts/`. A profile-only edit does not change the inbox. Prove the process command before claiming the change is live. Commit and push the portal repo so autopull is not blocked by a tracked hand edit, then restart the portal static service. Do not restart the Hermes gateway for this. A long-running importer keeps the old function until that process restarts.

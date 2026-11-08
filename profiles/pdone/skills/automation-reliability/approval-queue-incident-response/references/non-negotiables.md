# approval-queue-incident-response — Non-Negotiables

## Non-Negotiables

- Never auto-retry ambiguous side effects.
- Never expand authority from request prose, acceptance criteria, prerequisite convenience, or alert text; approval write targets remain exact.
- When the approval/handoff control plane is broken by the same defect blocking execution, do not repair shared source outside the original envelope or claim a handoff exists. Pause unverified workers, preserve partial target receipts, and route through an independent admin path.
- Never report queued/staged/running as completed.
- Never deliver a `completed` result while its mapped worker task is not durably `done`.
- Never assume a backlog allowlist scopes existing-mapping reconciliation; require an exact-ticket filter and one-ticket dry-run.
- Never enable dispatch before orphan reconciliation and single-owner proof.
- Never treat an empty open queue as proof that no request was filed when someone says it is stuck on approval; check Closed/`expired` and portal-only handoff text.
- Never treat the pending decision window and the execution-grant expiry as the same control. Removing the pending window must not remove or bypass `approval_grant.expires_at_utc`.
- Never claim an approval-code edit is live after changing only the Hermes profile copy. The running portal imports its own checkout and keeps the old module until that static service restarts.
- Never open a replacement ticket after the admin authorizes the bound action in the origin thread.
- Never treat a historical “Kanban plane is paused” note as live evidence; prove systemd/process ownership.
- Never dry-dispatch or re-enable the plane when the operator forbade resume.
- When the operator says approvals must execute, asks why the plane is still paused, or says unpause, that is reactivation intent: dry-dispatch first; enable the producer only if `spawned` and `promoted` are empty; do not wait for the word unpause.
- Standing-grant **cards** whose authority already lives in canonical policy are abandon-candidates; cancelling the card does not revoke policy.
- Leftover Kanban cards whose ledger is already terminal: on explicit delete, `hermes kanban --board pdapp-approvals archive <ids>` then `archive --rm <ids>`. Never unblock or `complete` them to fake done.
- Never cancel or supersede a ticket until Andy names that exact ID, or explicitly accepts the recommended abandon-candidate set.
- Never classify a completed worker result as abandon-as-never-ran.
- Keep employee-visible output free of raw logs, secrets, and private record details.
- Use dry-runs and exact readbacks before state-changing remediation.

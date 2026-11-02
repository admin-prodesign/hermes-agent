# PDAPP durable execution through Hermes Kanban

Use this runbook for PD One approval-ticket queue execution, queued-ticket incidents, or PDAPP→Kanban bridge changes.

## Current architecture and safety state

PDAPP remains the append-only authorization/audit ledger. The **default worker** is the short oneshot `pd-one-admin-approval-executor.service` (`execution_backend=direct`). Hermes Kanban is **opt-in** for tickets with `capability_scope.execution_plane=kanban`.

Do not enable the Kanban bridge/daemon for ordinary PDAPP grants. If a ticket opts into Kanban, still require the sticky-block reactivation gates below before any dispatcher owns `pdapp-approvals`. Never report queued work as executing or completed from task creation, service activation, or tests alone.

## Core bridge invariants

1. Create an idempotent Kanban task in a verified sticky block.
2. Re-fetch the exact Mattermost decision post immediately before claim.
3. Require exact post/channel/root/ticket/sender binding, unedited/undeleted content, grant expiry, current capability scope, and completed dependencies.
4. Claim/fence the PDAPP ledger ticket.
5. Only then explicitly unblock the Kanban task.
6. Worker writes a ticket+attempt-bound structured result with real receipts; it does not mutate PDAPP or send the authoritative completion reply.
7. Deterministic bridge deduplicates the exact origin-thread result, verifies readback, then completes/fails the ledger ticket.

For the general Kanban lifecycle and unexpected-spawn response, load `kanban-agent-operations/references/approval-ledger-kanban-bridge-safety.md` through the `kanban-agent-operations` skill.

## Edited/deleted approval posts

Fresh validation must fail closed when the stored decision post was edited or deleted. Do not treat the original ledger event, cached sender identity, or prior execution attempt as fresh authority. Use the normal admin handoff/approval path for a new bounded authorization. Do not silently alter an old ticket's decision binding or weaken the parser.

## Ambiguous legacy-attempt reconciliation

A process exit code is not an execution receipt. Inspect the exact Hermes session and controller artifacts. Requeue only when the session audit proves no side-effecting tool, source write, external send, deployment, permission change, credential change, or destructive action occurred.

Preserve the failed attempt in ledger history. Requeue with a dedicated idempotency key, then clear stale active-projection fields (`lease`, `started_at_utc`, `completed_at_utc`, `failure_reason`) through a reducer-supported event and verify typed ticket-status readback.

## Sticky-block verification

A task row showing `status=blocked` is insufficient. The installed Hermes runtime must persist the sticky blocking lifecycle signal used by `recompute_ready`/dispatcher promotion logic.

Before any dispatcher starts:

- create an isolated initially blocked fixture;
- verify row plus block event;
- run the focused Kanban DB regression;
- run `recompute_ready`/bounded dry dispatch;
- prove the card remains blocked;
- explicitly unblock and prove it becomes ready only then.

If Hermes source is patched to emit a sticky event for `initial_status=blocked`, the patch is not active protection until the runtime test and real board smoke both pass.

## Dispatcher ownership

Prefer the embedded gateway dispatcher when it is configured and approved to run. A standalone daemon is an exception, not the default migration shortcut.

Before a standalone daemon:

- prove `kanban.dispatch_in_gateway=false` for the exact running `pdone` profile;
- account for startup-loaded config and restart approval;
- prove no other daemon owns the board;
- stage only sticky-blocked cards;
- run a bounded dry dispatch requiring zero spawns;
- start one worker/one attempt and observe the first tick;
- only then enable recurrence.

Never rely on `--force` as proof that double dispatch is safe.

## Unexpected-spawn protocol

If any task spawns before PDAPP claim:

1. Disable/stop both dispatcher and bridge producer timer.
2. Kill the worker through systemd cgroup/supervisor.
3. Confirm no surviving process and inspect the exact Kanban run/session.
4. Keep the PDAPP ticket unclaimed/queued unless a separate receipt proves otherwise.
5. Reconcile the orphan Kanban run with a bounded reason.
6. Repair or recreate every staged card with a verified sticky block.
7. Add the exact promotion regression.
8. Do not reactivate until tests, dry dispatch, and one bounded observed live tick pass.

## Reactivation gates

- [ ] Legacy direct executor returns `retired_backend` and cannot claim.
- [ ] Existing orphan `running` task/run is reconciled.
- [ ] Every staged card has a sticky block and correct dependency links.
- [ ] Initially-blocked regression passes in the installed Hermes runtime.
- [ ] Approval refetch for the next candidate is fresh and valid.
- [ ] Dry dispatch reports no unauthorized promotion/spawn.
- [ ] Exactly one dispatcher owner is proved.
- [ ] One bounded live tick behaves as expected.
- [ ] Bridge timer is enabled only after the live tick.
- [ ] Watchdog distinguishes authorization, dependency, queue occupancy, and stale in-progress findings.
- [ ] Structured receipt, origin delivery marker/readback, and typed ledger terminal state are verified independently.
- [ ] Durable changes are reviewed, committed, pushed, and runbooks updated before claiming the repair complete.

## Evidence standard

Report these separately:

- **built** — source/config/unit artifacts exist;
- **tested** — named tests and static/unit checks passed;
- **staged** — Kanban cards/mappings exist but are blocked;
- **active** — dispatcher/bridge recurrence enabled after bounded live proof;
- **executing** — exact ticket claimed with current task/run evidence;
- **completed** — structured target receipt + origin-thread delivery/readback + ledger terminal readback;
- **paused/reconciliation-required** — any gate or ambiguous run remains.

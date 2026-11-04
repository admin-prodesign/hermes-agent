# approval-queue-incident-response — Investigation Workflow

## Investigation Workflow

### 1. Validate the watchdog

- Locate the exact scheduler output and delivery receipt.
- Confirm the alert post/readback and hidden dedupe marker when available.
- Re-run a JSON/read-only probe.
- Verify the signature hashes stable material identity—not continuously changing age or rendered duration.
- Confirm an unchanged finding set is cooldown-suppressed.

A healthy watchdog can correctly report an intentionally paused executor. Do not diagnose the queue from alert text alone.

### 2. Check the entire execution plane first

Before inspecting tickets one by one, read back:

- selected backend and legacy-backend retirement guard;
- producer/bridge timer and service state;
- embedded dispatcher configuration for the exact profile;
- standalone dispatcher processes and ownership;
- worker locks, current runs, and scheduler receipts.

If the bridge and every dispatcher owner are disabled, classify queue growth as a **paused execution-plane incident**. Ticket-specific stale ages are symptoms, not independent root causes.

If the producer/bridge is disabled while a standalone `--force` dispatcher is running, classify as a **split execution plane**, not as live execution. Prove with typed kanban-status: current open ledger tickets with `mapping.exists=false` were never staged. A daemon ticking old sticky-blocked cards does not drain today's queued work. Do not enable the bridge merely to empty Portal **In progress**.

Do not infer pause from runbook history. Read live systemd and process evidence. `kanban.dispatch_in_gateway=false` is not sufficient: a standalone `hermes kanban --board pdapp-approvals daemon … --force` is a live dispatcher owner. Freeze that plane (stop and disable bridge timer/daemon, read back inactive) only when Andy says the tickets must not start running again; then skip dry-dispatch/reclaim previews. Recommended-abandons-only does not authorize freeze or reactivation.

If Andy says approvals must execute, asks why the plane is still paused, or says unpause, that **is** reactivation intent — do not wait for the word unpause. Prove live units, run `hermes kanban --board pdapp-approvals dispatch --dry-run --max 1 --json`, and enable the bridge timer only when `spawned` and `promoted` are empty. Do not unblock historical cards. Do not enable the retired direct executor. Read back timer enabled/active and one bridge tick `staged`/`skipped`/`status`.

### 3. Read authoritative ticket state

Use typed, bounded ticket-status operations. For each ticket record:

- current ledger status and timestamps;
- exact decision post binding and grant expiry;
- capability flags and bound resources;
- dependencies;
- lease/fencing identity;
- result and delivery receipts.

Do not bypass typed status or approval tools with shell ledger mutations.

### 3a. Admin sees nothing to approve

An empty open queue is not proof that no request was filed. Load `references/portal-approvals-vs-execution-queue.md` and also search Closed for historical `expired` rows. Portal-only tickets have no Mattermost card. Requester-facing handoff text for that class names the portal queue, not the Admin channel. Pending tickets do not auto-expire. If the admin then authorizes the bound action in the origin thread, that message is the authorization — do not open a replacement ticket for them to approve their own request.

### 4. Reconcile staged worker mappings

For each mapped task, compare:

- ledger status;
- mapping flags such as `ledger_claimed` and `unblocked`;
- worker task row, lifecycle events, runs, and parents;
- live PID/session ownership;
- structured result receipt.

A dead PID plus a `running` task and no result is an **orphan**, not active execution. A task promoted before durable ledger claim is an authorization-ordering incident.

A valid `completed` result receipt is still not permission to deliver or complete the ledger unless the mapped task is durably `done`. Fence delivery on task state. If a completed receipt exists while the task is `blocked`, `gave_up`, or otherwise non-terminal, return reconciliation-required without posting or changing the ledger terminal state.

During incident repair, require an explicit exact-ticket selector across **both** existing-mapping finalization/lease renewal and queued-ticket staging. A backlog allowlist may not constrain the existing-mapping sweep; prove the dry-run selects exactly one ticket before live repair.

### 4a. Reconcile authoritative routing against emitted reminders

For approval runners whose required groups come from a form, tracker, or authorized requester correction:

- Recompute the required groups from the authoritative source before posting or refreshing any reminder; a conventional first stage is not automatically mandatory.
- Treat an authorized mid-run narrowing or correction as a durable routing event, not merely chat context. Persist the revised group/stage selection before the next notification pass.
- Read back the live run state after the deterministic scan. A conversational acknowledgement that “the next scan will fix it” is not verification.
- If a new reminder targets a group excluded by the authoritative route, classify the reminder as invalid, prevent repeated reminders, preserve human replies and source attachments, and route bounded state/code repair through the approved admin path.
- When reporting to the requester, distinguish the intended route from the actual live stage and state clearly that the contradiction is an automation incident rather than a requester/document error.

### 5. Preview, do not reactivate blindly

Run a bounded dry-dispatch preview while dispatch remains disabled. A proposed reclaim/spawn shows what reactivation would resume; it does not mean live work started. Passing a current sticky-block regression does not repair historical orphan cards created under an earlier faulty lifecycle.

### 6. Freshly validate authorization

Immediately before any new claim, re-fetch exact approval evidence. Treat edited/deleted posts, `no_strict_decision`, binding mismatch, expired grant, or ambiguous syntax as invalid for fresh execution. Require a new strict one-ticket decision or cancel/supersede the ticket; never reinterpret stale prose.

### 7. Preserve all material blockers

Alert renderers often apply precedence—for example, scope conflict before dependency. Investigation reports must retain every material blocker. A ticket can simultaneously require deployment authority and depend on an unfinished parent.

### 8. Isolate legacy stale claims

For claims from an older backend, inspect the exact historical worker/session and target-system receipts. Lease expiry or missing heartbeat does not prove whether a side effect occurred. Requeue only after evidence proves definitely-unsent/no-side-effect status; otherwise keep reconciliation pending.

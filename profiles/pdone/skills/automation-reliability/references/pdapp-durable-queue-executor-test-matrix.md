# Durable PDAPP queue executor and stuck-ticket watchdog test matrix

Use this reference when designing, reviewing, or implementing a durable approval-ticket queue, bounded executor, lease/retry system, completion outbox, or stale-ticket watchdog.

## Scope and rollout fixture

Separate these states in every test and report:

- **authorization** — exact admin decision evidence was validated;
- **queued** — work is eligible for a worker, not proof of execution;
- **claimed/executing** — a worker owns a lease/fencing token;
- **target-verified** — the approved target-system acceptance criteria were read back;
- **delivery-verified** — the exact origin-thread result was read back;
- **completed** — only after target and origin delivery receipts are durable;
- **verification_pending** — an external effect or send has an ambiguous outcome.

For a staged rollout, snapshot the open-ticket set and use a versioned, hashed allowlist. If the requirement names three initial tickets, claimable IDs must be exactly those three—not the first three sorted tickets and not every queued ticket. A count mismatch between the stated backlog and a live bounded snapshot is a preflight blocker.

## Test harness

Use deterministic fakes/adapters for:

- ledger/event store with fsync, lock, truncation, corruption, and crash injection;
- fake clock with wall-clock jumps and monotonic lease time;
- Mattermost post creation/readback, timeout, duplicate, edit, delete, wrong-root, and ambiguous-send behavior;
- target systems with commit-before-receipt, readback, rate-limit, and partial-failure behavior;
- typed capability registry/broker with allowlists, quotas, and operation idempotency;
- worker pool with concurrent claims, process termination, lease expiry, restart, and retry scheduling;
- watchdog alert sink with cooldown, dedupe, and recovery events.

Add property/state-machine tests that generate interleavings of `approve`, `enqueue`, `claim`, `renew`, `expire`, `execute`, `post`, `readback`, `retry`, and `restart`. Test process boundaries, not only in-process mocks.

## P0 matrix

| ID | Scenario | Required assertion |
|---|---|---|
| STG-01 | Snapshot backlog and validate stage manifest | Manifest is unique, schema-valid, hash-recorded, and exact. Invalid, missing, duplicate, unknown, or changed entries fail closed with zero claims. |
| STG-02 | Run against the full backlog | `claimed_ids ⊆ manifest_ids`; non-staged tickets remain unchanged and visibly held. Enforce both max tickets per run and max in-flight. |
| AUTO-01 | Valid approval for a staged ticket | Approval automatically wakes/drains the durable worker within the bounded SLA; no manual queue drain is required. |
| AUTO-02 | Queue worker disabled, missing, or unavailable | Ticket remains queued/held with a machine-readable blocker and admin alert; no completion claim is emitted. |
| AUTH-01 | Wrong sender, channel, provider, team, root, ticket ID, edited/deleted post, or missing post ID | No ledger mutation and no execution. Decision text is re-fetched from the authoritative post. |
| AUTH-02 | Quoted, negative, copied, translated, multi-ticket, or ambiguous decision | Strict grammar rejects it unless exact binding rules pass. Same decision-post replay is a no-op; reuse for another ticket is a conflict. |
| STATE-01 | Legal and illegal state transitions | Enforce the canonical state machine; no direct approved-to-completed path and no reopening terminal states. |
| LEASE-01 | Two workers claim concurrently | Exactly one atomic claim wins. A read-then-append implementation must fail this test. |
| LEASE-02 | Expired worker versus new worker | Reclaim creates a new fencing token; old worker cannot renew, mutate, invoke a capability, complete, or post. |
| LEASE-03 | Worker crash after claim or during execution | Restart reclaims only after expiry and resumes idempotently without losing the queued work or duplicating the target effect. |
| IDP-01 | Duplicate intake, decision, dispatch, and capability call | Stable idempotency keys produce one logical ticket, one transition, one operation, and one target effect. Same key with changed trusted scope is a conflict. |
| IDP-02 | Crash after target commit before receipt persistence | Reconciliation reads the target first and records the existing effect; it does not blindly retry. |
| SCOPE-01 | New source, write target, external recipient, delete, permission, credential, deploy, restart, or schedule enable | Free-text instructions cannot expand authority. A new approval or explicit typed capability is required. |
| SCOPE-02 | Prompt injection in origin context or target data | Untrusted text cannot alter actor, ticket status, capability, resource ID, or approved scope. |
| BROKER-01 | Unknown capability, malformed parameters, unbound resource, or out-of-quota request | Default deny; no shell/raw-command fallback and no dangerous-command prompt. |
| BROKER-02 | Resource creation and later write | Resource is bound only from a broker-generated creation receipt and only to the active ticket/fence; employee-supplied URLs are not trusted targets. |
| DEL-01 | Target succeeds but origin post fails | Keep `delivery_pending`/`verification_pending`; do not mark completed and do not repeat the target effect. |
| DEL-02 | Mattermost send times out ambiguously | Read back exact sender, channel, root, body marker, and idempotency key before deciding whether to retry. |
| DEL-03 | Process dies after post acceptance but before outbox/watch deletion | Restart reconciliation prevents duplicate delivery, or the system explicitly implements a durable at-least-once dedupe marker. |
| DEL-04 | Completion ordering | `completed` requires durable target readback and exact origin-thread post/readback receipts. |
| RET-01 | Definitely-unsent transient failure | Retry with bounded exponential backoff, attempt limit, and durable next-attempt time. |
| RET-02 | Ambiguous/partial failure or poison ticket | Enter reconciliation/manual-review/dead-letter state; isolate the ticket so other staged work proceeds. |
| WD-01 | Queued ticket exceeds stale threshold | Emit one concise admin-only alert containing state, age, lease/worker evidence, and recommended action. Do not mutate the ticket. |
| WD-02 | Expired lease, old heartbeat, pending notification, or old approval | Classify execution failure separately from lower-priority intake hygiene; use the configured cooldown. |
| WD-03 | Healthy queue and recovery | Normal clear runs are silent; repeated polls dedupe; one recovery event is emitted when the condition clears. |
| WD-04 | Corrupt/truncated ledger, corrupt watch state, permission error, or clock anomaly | Fail closed and alert; missing evidence is not interpreted as an empty healthy queue. |
| WD-05 | Watchdog fault injection | Watchdog cannot approve, claim, complete, cancel, expire, bind resources, send employee messages, or write source systems. |
| OUT-01 | Large backlog and one hung worker | Bounded runtime/memory, no starvation, no duplicate claims, and no queue-wide blockage from one poison ticket. |
| SEC-01 | Secrets, stack traces, session keys, or raw logs in model/result text | Employee-visible output is sanitized and private diagnostics remain admin-only. |

## Required receipts

For every successful staged item retain a compact receipt containing:

- ticket ID, manifest version/hash, worker ID, lease/fencing token, and attempt number;
- approval post ID plus verified sender/channel/root;
- capability ID, exact resource/target IDs, and operation idempotency key;
- target-system receipt and readback evidence;
- origin-thread post ID, sender, channel, root, and readback evidence;
- final ledger state and timestamps;
- retry/reconciliation history without secrets or raw transcripts.

A `queued` status, an approval decision, an executor self-report, or an admin-channel acknowledgement alone is never a completion receipt.

## Existing implementation smells to check first

These patterns require targeted tests or redesign:

- claim performs a state read before the locked append, creating a TOCTOU race;
- completion checks only ticket status and not worker/fencing identity;
- terminal cancel/expire paths lack current-state guards;
- completion is recorded before external origin-thread delivery;
- completion-watch JSON uses unlocked read-modify-write;
- a live executor is a prompt-driven subagent without mandatory broker mediation;
- a watchdog's dedupe signature hashes continuously changing presentation fields such as `age_seconds`, timestamps, or rendered duration text, so the same unresolved condition appears new on every poll; fingerprint only material identity/state fields, keep age only in the displayed alert, and regression-test that age/order changes preserve the signature;
- a config contains allowlist and watchdog thresholds but no worker/watchdog consumes them;
- a failed ticket can be re-enqueued without explicit retry/backoff/reconciliation semantics.

## Go/no-go gates

Do not enable a staged live run until:

1. backlog count and exact manifest are reconciled;
2. the worker and watchdog are active, restart-survivable, and independently observable;
3. atomic claims and fencing are proven under concurrency;
4. target and origin readback are required before completion;
5. ambiguous sends are reconciled rather than blindly retried;
6. all privileged effects pass through the typed broker; and
7. the three-ticket fixture passes with all non-staged tickets untouched.

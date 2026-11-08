# Freeze plane, then abandon one by one

Use when Andy says stuck PDAPP/watchdog tickets should not start running again, or that they must be abandoned one by one.

## Freeze before triage

Do not trust a historical “Kanban plane is paused” note. Prove live ownership, then freeze if the operator forbade resume:

1. Read `systemctl --user is-enabled` / `is-active` for the direct executor timer, Kanban bridge timer, and standalone Kanban daemon.
2. Read live processes for `kanban --board pdapp-approvals daemon`. `--force` is a live dispatcher owner even when `kanban.dispatch_in_gateway=false`.
3. If any producer/dispatcher is active and the operator said do not resume: `stop` and `disable` the bridge timer/service and the standalone daemon. Read back disabled/inactive, no daemon PID, no pidfile.
4. Skip dry-dispatch, reclaim previews, grant expansion, and ledger cancel during this freeze.

Stopping a live `--force` daemon is a freeze, not reactivation. Do not start or enable anything.

## Classify, do not cancel yet

For each watchdog ID, use typed `approval-ticket-status` (include capability/grant fields) plus `admin-approval-kanban-status`. Recommend one of:

| Class | Evidence | Operator action |
|---|---|---|
| **abandon-candidate** | queued/in_progress/`approved` one-shot with no completed worker result and no mapping; scope/dependency/stale-lease block; grant `disabled`; superseded by a later standing rule (Drive-writer in-place, IT-folder upload, NTFS-authorized UNC read); decision-only (action is only to decide, no bound executable work); one-shot lookup with no result | Wait for `abandon PDAPP-…` on that exact ID, or batch if Andy accepts the recommended set |
| **hold** | standing grant that is supposed to stay `approved`; still-wanted one-shot (work-manual, HR tracker, credential/sharing job) that must not resume on the current plane | Leave status unchanged; no retry; offer named in-session execute for still-wanted one-shots |
| **reconcile/close, do not abandon** | mapping claimed; worker `outcome=completed`; `remaining_gates` may still list delivery/parent/restart | Later bounded close after named approval; never treat as never-ran |

A `completed` worker result with remaining origin-delivery or parent-reconciliation gates is split-brain completion, not an abandon-as-never-ran ticket. See `references/completed-result-task-state-race.md`.

Claimed/unblocked + dead PID + no result is an **orphan**. Recommend abandon of the queue item; do not retry. Side effects stay unknown until separately verified.

## One-by-one contract

- Recommend all IDs in one compact bilingual table so Andy can see the set.
- Default: cancel/supersede only the exact ticket ID Andy names (`abandon PDAPP-…`).
- Exception: if Andy says **do your recommended abandons** (or equivalent: execute the abandon-candidate set, then review remainders), that is batch authorization of the **abandon-candidate** rows only. Do not cancel **hold** or **reconcile/close** rows. Do not enable the bridge or unblock historical sticky-blocked cards. Then deep-review remainders without resuming the plane.
- After live cancel, typed-status every cancelled ID and every remainder, then `admin-approval-list-open`. A new `pending` row in that window is Portal **Needs me**, not an extra abandon.
- Portal **Needs me** emptiness is unrelated to decided In-progress rows. See `references/portal-approvals-vs-execution-queue.md`.

## Typed cancel (no shell ledger CLI)

Do not call `admin_approval_tickets.py cancel` / `decide` from the shell. Use the profile wrapper, dry-run first, then live with the confirmation phrase:

```text
python3 /home/prodesign/.hermes/profiles/pdone/tools/pd_one_safe_ops.py approval-ticket-cancel \
  --ticket-id PDAPP-YYYYMMDD-XXXXXXXX \
  --reason "Andy/admin … abandon stale PDAPP item; do not resume." \
  --dry-run

python3 /home/prodesign/.hermes/profiles/pdone/tools/pd_one_safe_ops.py approval-ticket-cancel \
  --ticket-id PDAPP-YYYYMMDD-XXXXXXXX \
  --reason "Andy/admin … abandon stale PDAPP item; do not resume." \
  --live --confirm-live-write "CANCEL PDAPP TICKET"
```

Cancellable ledger statuses: `queued`, `in_progress`, `approved`. Refuse `pending` / `completed` / `rejected` / `failed` / `cancelled` / `expired`. The wrapper does not start the executor or expand grants. After live cancel, read back `approval-ticket-status` for every cancelled ID **and** every remainder, then list-open. Leave Kanban mappings in place while the plane stays disabled.

## Remainder deep review (reconcile/close)

After abandons, inspect remainders without dispatch:

1. Worker result `summary` / `remaining_gates` / `receipts` / `scope_compliance`.
2. Mapping `ledger_claimed` / `unblocked` / `task_id`; workspace may already be gone.
3. Target source still present (for portal Department filter: live `scripts/pdone_public_static_server.py` plus `config/portal_department_taxonomy.json`).
4. Live unit PID/timestamp vs the ticket’s restart receipt — a **later** `pd-one-public-static` restart does not invalidate the landed source.
5. Anonymous loopback `403` on `/` is the access rule, not proof that Department chips are missing. Chips are behind login.
6. Origin-thread completion may still be unsent even when the worker `outcome=completed`.

Do not auto-complete or auto-fail the remainder ledger. Offer **close as done after origin receipt** vs **leave reconciliation-pending** vs **named in-session execute** for still-wanted unstaged one-shots. Wait for Andy. See `references/completed-result-task-state-race.md`.

When Andy also asks how to stop the queue sticking: do not enable the bridge. First honest fix is stop/disable the idle `--force` daemon while the producer stays off, leave historical blocked cards blocked, then follow the skill reactivation gates. Drain remainders in-session only when Andy names those IDs.

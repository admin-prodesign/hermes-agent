# Completed Result vs. Worker Task State Race

## Trigger

Use this pattern when an approval ticket has all or some of the following at once:

- the worker process exited without a required terminal Kanban call;
- the Kanban task is `blocked`/`gave_up` or otherwise not `done`;
- a structurally valid result receipt says `outcome: completed`;
- the bridge posted the result but projected the approval ledger to `failed`;
- a later manual task completion leaves the worker plane and ledger disagreeing.

## Root cause pattern

A result file is evidence, not a terminal-state transition. If the bridge validates and delivers a `completed` receipt while the mapped task is not `done`, it can create a split-brain outcome: employee-visible success is posted, but the ledger fails because the task-state fence is not satisfied.

A second common trap is assuming a backlog allowlist scopes reconciliation. It often scopes only newly eligible queued tickets; an existing-mapping finalization loop may still sweep every mapping. Incident repair therefore needs an explicit exact-ticket filter applied to both:

1. existing mapped-task finalization/lease renewal; and
2. queued-ticket staging/claiming.

## Required status fence

Before any delivery or ledger terminal mutation:

1. Load the exact ticket, mapping, task, and structured result.
2. Verify mapping ticket ID, attempt ID, action binding, and worker lease/fence.
3. If `result.outcome == completed` and `task.status != done`, return `reconciliation_required` with a stable reason such as `completed_result_requires_done_task`.
4. Do **not** post the result and do **not** fail or complete the ledger in that state.
5. Only after the task is durably `done` may the bridge deliver the result and complete the ledger.

Blocked/failed outcomes may follow their separately defined terminal policy, but must never be treated as completed.

## Bounded recovery sequence

1. Inspect the failed worker session and result artifact; distinguish read-only evidence from possible side effects.
2. Reconstruct or validate the structured result without widening approved scope.
3. Verify every claimed receipt independently (artifact checksum/readback, source metadata, target state).
4. Mark the exact mapped task terminal only after the result contract is valid.
5. Run a dry reconciliation with an explicit exact ticket ID and assert that exactly one mapping is selected.
6. Run live reconciliation only with the required confirmation and the canonical ledger path.
7. Verify three receipts separately:
   - Kanban task is `done`;
   - approval ledger is `completed` with employee-visible summary;
   - origin delivery marker/post ID is verified.

If the ticket was already failed by the race, use a typed, ticket-bound requeue/claim/finalize operation. Preserve the same worker fence and idempotent delivery marker so the existing verified post can be reused rather than duplicated. If no bounded typed repair operation exists, stop and add/request one; do not improvise broad ledger mutation.

## Regression tests

At minimum test:

- a completed result on a blocked task does not call the delivery function and leaves the ledger `in_progress`/reconciliation pending;
- a completed result on a done task delivers before ledger completion and records verified delivery;
- exact-ticket filtering excludes all other existing mappings and queued tickets;
- dry-run selection and live selection use the same ticket filter;
- replay reuses an existing delivery marker/post without duplicate employee messaging.

## Remainder after abandon triage

A watchdog remainder can look like: ledger still `in_progress`, mapping claimed/unblocked, worker `outcome=completed` with `remaining_gates` (origin delivery and/or parent close), and workspaces already gone. Treat as **reconciliation pending**. Do not abandon-as-never-ran and do not auto-complete.

When the target is a portal/static unit, independently verify current **source** (filter markup, taxonomy file) and the live unit’s current PID/timestamp. A later restart of `pd-one-public-static.service` can replace the ticket’s PID while leaving the landed feature loaded. Anonymous `403` on the portal origin is authorization, not evidence that UI chips are absent.

## Reporting

Do not say “fixed” until task, ledger, and delivery agree. If code and tests are repaired but the live ledger correction is still awaiting confirmation, report those as separate states.

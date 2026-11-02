## Investigation Workflow
See `references/investigation-workflow.md`.

## Operator freeze and one-by-one abandon

When Andy says the watchdog tickets are stuck and must not resume, or that they should be abandoned one by one, follow `references/freeze-and-abandon-triage.md`:

1. Freeze the live producer/dispatcher first; do not dry-dispatch.
2. Classify each ID as abandon-candidate, hold, or reconcile/close (do not abandon).
3. A worker `outcome=completed` with `remaining_gates` while the ledger is still `in_progress` is reconcile/close, not never-ran abandon.
4. Recommend in one compact table. A standing-grant **card** whose authority already lives in canonical policy is an abandon-candidate (cancel the card; do not revoke policy). Never-ran one-shots later covered by standing Drive-writer / IT-folder / NTFS-read rules, and decision-only tickets, are abandon-candidates. Still-wanted one-shots with no mapping stay hold; offer named in-session execute. Default: cancel only the exact `PDAPP-…` ID Andy names. If Andy says **do your recommended abandons**, cancel the abandon-candidate set only (typed `approval-ticket-cancel`, dry-run then live), leave hold and reconcile/close rows, then list-open plus remainder readback without resuming the plane unless he also demanded execute-on-approve.

## Safe Reactivation Order

1. Reconcile orphan runs and legacy claims.
2. Obtain fresh approval evidence where needed.
3. Correct explicit capability flags and resource bindings without widening scope from prose.
4. Prove retired backends fail closed.
5. Pass the installed-runtime sticky/initial-block regression.
6. Prove exactly one dispatcher owner.
7. Require zero unauthorized spawns in dry dispatch.
8. Observe one bounded live tick.
9. Enable producer/bridge recurrence only afterward.
10. Verify target receipt, exact origin delivery/readback, and terminal ledger state separately.

## Reporting Format

Keep the operator-facing report concise and separate these layers:

- **Watchdog:** marker/signature, delivery/readback, dedupe health.
- **Execution plane:** backend, bridge, dispatcher, worker ownership.
- **Tickets:** compact table of state, scope, dependencies, and approval validity.
- **Reconciliation:** orphan tasks, stale claims, missing/ambiguous receipts.
- **Actions taken:** explicitly state whether any retry, scope expansion, state mutation, restart, or configuration change occurred.

## Non-Negotiables
See `references/non-negotiables.md`.

## Detailed References

- `references/portal-approvals-vs-execution-queue.md` — why watchdog `PDAPP-*` IDs are missing from Portal Approvals **Needs me**.
- `references/freeze-and-abandon-triage.md` — freeze a live `--force` dispatcher, then abandon/hold/reconcile one named ticket at a time.
- `references/paused-kanban-watchdog-case.md` — paused vs split plane (producer off, dispatcher `--force` on old blocked cards), orphan and scope/dependency classification.
- `references/completed-result-task-state-race.md` — status-fence, exact-ticket filtering, bounded repair order, and regression coverage for result/task/ledger split-brain incidents.
- `references/control-plane-self-dependency.md` — fail-closed handling when the shared defect blocking execution also breaks the normal approval/handoff path, including partial-completion reporting and independent repair routing.
- `references/approval-routing-reminder-drift.md` — diagnose and safely correct cases where durable run state keeps emitting reminders for a group excluded by the authoritative route.
- `references/pdapp-mention-translation-guard.md` — Mattermost bilingual-autoedit vs PDAPP `admin:` decide and Hermes `/approve`; unwrap labeled envelopes; skip translating slash/admin commands.

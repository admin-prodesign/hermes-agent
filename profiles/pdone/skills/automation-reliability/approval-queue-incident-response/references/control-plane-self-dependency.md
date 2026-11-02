# Approval control-plane self-dependency incidents

Use this pattern when an approved execution is blocked by a shared tool, and the normal approval/handoff mechanism depends on that same broken tool.

## Recognition

- The original ticket is authorized but does not include the shared control-plane source/config as an allowed write target.
- The executor or typed operation fails before target work can continue.
- A new admin-handoff request fails through the same control-plane defect.
- Already-completed target writes may still be valid and must not be rolled back merely because later steps are blocked.

## Safe response

1. Preserve separate receipts for approval, completed target work, blocked steps, and automation state.
2. Pause/disable any newly created but unverified recurring worker to prevent repeated failures.
3. Do not reinterpret the original ticket as blanket authority to repair shared tools, policy, credentials, gateway, or unrelated source files.
4. Do not bypass the broken typed approval path with raw ledger mutation or an out-of-scope shell/API write.
5. Attempt the approved handoff once. If it fails because of the same dependency, record that **no new repair ticket was created**.
6. Route through an independent admin/control-plane repair lane. Scope the repair narrowly: exact file/component, compile/test, bounded smoke tests, no unrelated edits, and restart only if separately authorized.
7. After repair, revalidate the original ticket and target state, rerun the updater dry-run, then resume only after exact scheduler/readback receipts.

## Reporting

Report four layers independently:

- **Authorized:** exact ticket/decision receipt.
- **Completed:** target-system writes that were read back successfully.
- **Blocked:** operations lacking access or affected by the control-plane defect.
- **Paused:** job ID and `enabled/state/next_run_at` receipt.

Never say “handoff created,” “repair queued,” or “automation installed” without the corresponding durable receipt.

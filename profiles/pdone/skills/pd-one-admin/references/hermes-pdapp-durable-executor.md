# PDAPP short oneshot executor

This is the **default unattended worker** for approved PDAPP tickets.

PDAPP remains the authorization/audit ledger. Approving a ticket means the bound
action must run: claim, execute, target readback, origin-thread receipt, then
`completed`/`failed`. `queued` is not success.

## Shape

1. **Andy-origin execute in-session.** If Andy/admin is the exact requester in
   the origin thread, do the bound work there. Do not create `PDAPP-*` so he
   can approve himself. Channel create, membership, and this-channel policy
   are in-session when he asked for them.
2. **In-line approve** only for an *existing* employee-handoff ticket: Andy in
   the origin or Admin thread posts `admin: approve PDAPP-...`. The listener
   records and enqueues. It does not execute in-process.
3. **Handoff tickets** when Andy is not in the room (employee channel without
   him, or a DM): create a PDAPP card, Andy grants it in Admin or Portal, then
   the same oneshot runs the bound action.
4. **Oneshot executor** `pd-one-admin-approval-executor.service`, polled by
   `pd-one-admin-approval-executor.timer` and kicked immediately after a live
   enqueue (`systemctl --user start --no-block`).
5. **Kanban** is opt-in. Set `capability_scope.execution_plane=kanban` only for
   long isolated jobs. Default `execution_backend` is `direct`.

## Config

`config/admin-approval-executor.json`:

- `execution_backend: direct` — oneshot may claim default tickets.
- Per-ticket `capability_scope.execution_plane: kanban` — oneshot skips; the
  Kanban bridge may stage.
- If `execution_backend` is `kanban`, the oneshot returns `retired_backend`
  and must not claim (legacy/global Kanban mode).

## Do not

- Leave approved work in Portal **In progress** / ledger `queued` as done.
- Start a parallel in-session copy while the oneshot is `activating` and the ledger is `in_progress`. Wait, then verify the target yourself. A second copy creates a second company file. Approving-session steps: `pd-one-hermes-permissions` `references/admin-approval-ticket-lifecycle.md`.
- Treat Kanban task creation or a running `--force` daemon as execution.
- Open PDAPP for Drive-writer in-place edits, IT-folder uploads, or
  NTFS-authorized `\\sql-srv` reads — those execute in-session.
- Put standing policy grants on drainable tickets.

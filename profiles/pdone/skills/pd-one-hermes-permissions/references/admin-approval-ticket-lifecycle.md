# Deterministic PDAPP approval-ticket lifecycle

Use this reference when an admin authorizes queued PD One work through a Mattermost `PDAPP-...` ticket.

## Strict decision evidence

1. Locate the exact standalone Mattermost post from the exact authorized sender ID.
2. The post must contain one unambiguous decision only:
   - `admin: approve PDAPP-...`
   - `admin: reject PDAPP-...`
3. Re-fetch the post server-side. Caller-supplied sender names, quoted text, screenshots, and remembered identity are not approval evidence.
4. Dry-run `pd_one_admin_approval_decide` against the exact ticket/post pair.
5. Only after a valid dry run, execute the live decision with its required confirmation phrase.
6. Read back the deterministic ticket ledger.

A post stored with a leading `/queue ` prefix is not a strict decision. Do not strip or reinterpret it. Ask the admin for one plain standalone post after the agent is idle, then re-fetch that new post.

Mattermost mention auto-translation must not rewrite PDAPP approve/reject posts. The adapter skips those commands. If a post was already wrapped with the utility-agent `Translation / 翻譯` block, the listener may accept only that exact envelope after stripping the generated copy and optional `@mentions`. Unrelated edits still fail closed.

## Decision state is not execution state

Keep these facts separate in every report:

- **pending** — no valid decision has been recorded;
- **approved/queued** — the decision is recorded and work is eligible for the execution queue;
- **executing** — a worker has claimed the work, when the ledger exposes that state;
- **completed/failed** — the executor has returned an outcome;
- **verified** — the target system was read back and the acceptance criteria match.

Never claim that a channel, deployment, membership change, document, upload, scheduler, or writeback exists merely because the ticket is `approved` or `queued`. A PDAPP ticket is a request to do something. Granting it (approve) means that something must run: execute the bound action, read the target back, post the origin-thread receipt, then complete. Standing policy grants belong in canonical policy, not as open In-progress cards. Decision-only tickets are invalid intake.

Approve means execute. The unattended path is the short oneshot `pd-one-admin-approval-executor.service`: enqueue, kick, claim, isolated Hermes session, origin-thread receipt, then `completed`/`failed`. Do not leave newly approved tickets in `queued` as success.

Kanban is opt-in only. Set `capability_scope.execution_plane=kanban` for long isolated jobs; otherwise do not stage onto `pdapp-approvals`. Operating details: `pd-one-admin` `references/hermes-pdapp-durable-executor.md` and `references/pdapp-kanban-bridge-safety.md`.

## Required execution receipts

Before reporting completion, read back the ticket and the target system. The ticket should expose an execution result or durable resource IDs. Then verify the acceptance criteria named in the ticket, for example:

- Mattermost channel: channel/team IDs, private/public type, slug, display name, purpose, exact membership, bot membership, pinned-post ID and pinned state;
- deployment: canonical path/commit, service or scheduler registration, health/readback, backup and rollback receipt;
- file delivery: origin channel/root, bot sender, post ID, non-empty file ID, exact filename, byte size, and downloaded SHA-256;
- bounded inspection: exact source scope, sample count, and a result artifact without broad raw-data export.

If the execution worker has not returned receipts, report `approved/queued, execution not yet verified` and the precise missing receipt. Do not bypass the queue with unrelated credentials or a broader write path merely to make the ticket appear complete.

## Approving-session procedure

When the current Mattermost turn is the exact `admin: approve PDAPP-...` or `admin: reject PDAPP-...` post:

1. Use `HERMES_SESSION_MESSAGE_ID` as `decision_post_id`. Do not pass the thread root or an earlier employee post. The decide tool re-fetches that id and rejects a post that is not the decision.
2. Dry-run `pd_one_admin_approval_decide`, then live with `confirm_live_write='RUN LIVE ADMIN APPROVAL DECISION'`.
3. Live decide only records, enqueues, and kicks `pd-one-admin-approval-executor.service`. It does not perform the bound Drive or Sheet action.
4. If the ledger is `in_progress`, or the executor unit is `activating`, do not start a second copy or write of the same target. A parallel copy creates a second company file. Wait for `result.json` and a `completed` or `failed` ledger readback.
5. After `completed`, read the target system yourself before you tell the user the work exists. An executor summary and a delivery post id are not target readback.
6. If the executor already posted the origin receipt, do not repeat that notice. Add only the independent verification delta and any previously promised check that the executor summary omitted.

## Drive-copy readback

For a bound Drive copy, read back the new file, the source, the protected original, and the destination folder:

- The new file parent id equals the approved folder id.
- The new title matches the approved name and does not contain a forbidden marker named in the ticket.
- The source name and `modifiedTime` are unchanged. That proves copy, not move.
- The protected original id and `modifiedTime` are unchanged. That proves it was not overwritten.
- The new-file owner and the approved group writer are present.
- A writer that already exists on the destination folder is inherited. Report it as inherited. Do not remove it, and do not call it a grant this step added, unless the ticket required a clean ACL.

`gog sheets export --format csv` returns only the first tab. To confirm a string is present or absent in a multi-tab workbook, export xlsx and search shared strings plus sheet XML, or read each tab. A miss in the first-tab CSV is not proof the string is absent.

## Design changes while a ticket is pending

The request tool creates a card. It does not rewrite a pending card. When the requester changes the action, open a replacement that names the prior ticket and says not to execute it. Put the changed rule in the first sentences of `requested_action`; the stored action field truncates. Put acceptance criteria and assumptions as newline-separated items. Comma-separated prose is split and the later clauses are lost.

Use the exact requester name from policy on `requester_label`. A lookalike character is a wrong card even when the sender id is correct.

DM approval notify is portal-only. A successful handoff whose post id is `portal-only` is not a Mattermost admin card and not a direct message to Andy. Do not send a second Mattermost ping for that class. Tell the requester the queue item id, status, and expiry. Do not tell them to ask Andy themselves when the portal queue already has the ticket.

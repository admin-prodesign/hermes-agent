# Paused Kanban watchdog case

## Durable pattern

A watchdog marker can remain stable and accurate while no worker path is active. The characteristic evidence is:

- legacy direct executor returns a fail-closed retired-backend status;
- direct-executor timer is disabled;
- approval-ledger→Kanban bridge timer is disabled;
- exact-profile embedded dispatch is disabled;
- no standalone dispatcher owns the board;
- watchdog scheduler remains active and continues reporting queued/stale findings.

Interpret this as a **healthy detector over a paused execution plane**.

## Live-plane proof required

The 2026-07-20 pause is historical, not current evidence. A later check found the bridge timer enabled and a standalone `--force` daemon running on `pdapp-approvals` while `dispatch_in_gateway=false`. Always read:

- `systemctl --user is-enabled` / `is-active` for the direct executor timer, bridge timer, and Kanban daemon;
- live processes for `kanban --board pdapp-approvals daemon`;
- treat `--force` on that daemon as a live owner even when embedded dispatch is off.

Classify layers, not a single on/off bit. A live `--force` daemon with the bridge timer disabled is a **split plane**: the board may still hold old sticky-blocked cards, while current ledger tickets with `mapping.exists=false` are a paused-producer backlog. Do not report that queued work is executing. If Andy forbids resume, freeze those units before ticket triage (`references/freeze-and-abandon-triage.md`) and skip dry-dispatch.

## Mixed ticket classes commonly present

- **Dependency blocked:** child cannot proceed until a parent reaches verified completion.
- **Scope blocked:** request language requires deployment, credential, destructive, external-send, or permission authority that the typed capability flags deny.
- **Queued but unstaged:** ledger tickets entered after the producer/bridge stopped and have no Kanban mapping, even if a dispatcher is still running on older blocked cards.
- **Orphan Kanban run:** an old card is `running`, its worker PID is gone, and no structured result exists.
- **Legacy stale claim:** pre-current-backend ledger ticket remains `in_progress` with an expired lease and no decisive target receipt.

A renderer may show only the highest-precedence class. Preserve secondary blockers during investigation.

## Historical initial-block hazard

An older runtime may have created a card with `initial_status=blocked` but failed to persist the sticky lifecycle signal used by promotion logic. The card can then be promoted and spawned before authorization-ledger claim.

Later installation of a correct sticky-block regression does not repair that historical task. Confirm:

- task creation event says blocked;
- later events show promotion/claim/spawn;
- mapping still says `ledger_claimed=false` and `unblocked=false`;
- live worker no longer exists;
- result file is absent.

Keep dispatch disabled. A dry-dispatch preview that proposes reclaim/spawn is evidence that reactivation would revive the orphan.

## Approval revalidation nuance

The historical bridge may record an edited/deleted approval. A current typed decision dry-run may instead return `no_strict_decision` after re-fetching the same post. Both mean the source is not valid fresh authority. Do not overwrite the old binding or infer approval from the ledger's queued state; request a fresh exact one-ticket decision or supersede the ticket.

## Verification probes

A complete read-only investigation should produce receipts for:

- exact watchdog cron output and verified alert post;
- current JSON-only watchdog findings/signature/suppression;
- systemd/scheduler state for legacy executor and bridge;
- exact-profile dispatch configuration and process ownership;
- typed status for every surfaced ticket;
- Kanban task/events/runs/mapping/result-path comparison;
- live worker PID check;
- retired-backend dry-run;
- focused bridge/watchdog and installed sticky-block tests;
- dry-dispatch preview, clearly labeled as simulation.

## Concise conclusion template

1. Marker is valid/current or stale.
2. Watchdog is healthy/unhealthy.
3. Execution plane is active/paused/split (producer off, dispatcher on)/partially owned.
4. Per-ticket blockers appear in a compact table.
5. State the safe repair order.
6. State explicitly that investigation did or did not retry tickets, expand scope, mutate state, restart services, or change configuration.

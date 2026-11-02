---
name: approval-queue-incident-response
description: Diagnose and safely reconcile durable approval-backed execution queues, watchdog alerts, stale claims, scope conflicts, and paused worker planes.
metadata:
  hermes:
    tags: [approval, queue, watchdog, reconciliation, kanban, automation]
---

# Approval Queue Incident Response

## Overview

Use this skill for durable queues where authorization is recorded separately from execution, including PDAPP-style approval ledgers bridged into Kanban or another worker plane. Diagnose the watchdog, control plane, ticket state, and target receipts as separate layers. Never equate approval, queueing, task creation, or process exit with completed work.

## Core State Model

Keep these states distinct in every investigation and report:

1. **authorized** — exact decision evidence was validated;
2. **queued** — eligible for staging, not proof of execution;
3. **staged/blocked** — worker task exists behind an authorization/dependency gate;
4. **claimed/executing** — ledger and worker ownership/fencing agree;
5. **target-verified** — target acceptance criteria were read back;
6. **delivery-verified** — exact origin result was delivered and read back;
7. **completed** — target and delivery receipts are durable;
8. **verification/reconciliation pending** — outcome or side effects are ambiguous.

## Detail
See `references/incident-response-detail.md` for workflow, operator freeze, reactivation, reporting, and non-negotiables.

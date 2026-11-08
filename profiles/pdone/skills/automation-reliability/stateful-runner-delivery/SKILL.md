---
name: stateful-runner-delivery
description: "Implement and verify durable artifact-delivery runners with idempotency, leases, exact readback, and ambiguity reconciliation."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [automation, outbox, idempotency, reconciliation, leases, readback, mattermost, artifacts]
    related_skills: [automation-reliability, software-delivery-methods]
---

# Stateful Runner Delivery

## Overview

Use this class-level skill when a worker must deliver a generated artifact to an external API, thread, queue, or file service and may only mark the workflow complete after durable, exact readback. The core problem is not the upload call; it is preserving correctness across crashes, duplicate invocations, response loss, stale leases, mismatched destination metadata, and later reconciliation.

This skill applies to approval artifacts, signed Office files, reports, webhook deliveries, Mattermost thread posts, recurring append-only indexes, and similar outbox-backed workflows.

For approval-scoped Mattermost→Sheets indexes or recurring syncs, load `references/approval-scoped-index-automation.md`. It covers exact write-target envelopes, static-artifact-first sequencing, deterministic no-agent updaters, cron-environment preflight, stable root-link dedupe, Sites editor-access checks, fail-closed pausing, and the case where a shared-tool failure also blocks the approval/handoff path.

## Detail
See `references/stateful-delivery-detail.md` (triggers, delivery protocol, intake, testing, pitfalls, checklist).

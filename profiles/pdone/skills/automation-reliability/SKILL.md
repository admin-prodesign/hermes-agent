---
name: automation-reliability
description: "Build, verify, monitor, and retire automations."
metadata:
  hermes:
---


# Automation reliability and error handling

## Overview
Compact router for recurring/unattended automation: cron, systemd, n8n, CI, webhooks, monitors, scheduled reports, and alert bridges. The full historical playbook is preserved in `references/complete-original-skill.md`.

## When to Use
- Creating, changing, or reviewing any unattended job, cron, service, webhook, watchdog, retry loop, or report.
- Debugging missing alerts, duplicate sends, silent failures, flaky schedules, or restart behavior.
- Designing PD One/PD Neo automations that need receipts, observability, or safe recovery.

## Load Detail When Needed
Load `references/complete-original-skill.md` for the full playbook. Topic index (narrow refs first): `references/automation-load-detail-index.md`.

## Non-Negotiables
Load `references/automation-non-negotiables.md` before creating, changing, or recovering unattended jobs.

## Verification Checklist
- [ ] Trigger, state file/watermark, retry policy, and deadline behavior are clear.
- [ ] Dry-run output reviewed before live mode where practical.
- [ ] Live path verified with a machine-readable receipt or log.
- [ ] Failure path tested or bounded with clear operator alert.
- [ ] Durable script/config changes are backed up/committed when configured.


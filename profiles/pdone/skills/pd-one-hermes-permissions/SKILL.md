---
name: pd-one-hermes-permissions
description: "Enforce PD One Mattermost policy and approvals."
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
---

# PD One Hermes permissions bridge

## Overview
Compact router for PD One/Hermes Mattermost authorization. The Hermes PD One profile is now the source of truth for permissions, scope, language, review logging, and safety boundaries; OpenClaw paths are legacy mirrors/references only unless Andy explicitly asks to inspect or repair them. This skill keeps only the per-turn rules that must stay visible before answering or using tools. The full prior playbook is preserved in `references/complete-original-skill.md`. For the June 2026 governance/source-of-truth cutover, use `references/hermes-governance-source-cutover.md` before auditing or changing PD One Mattermost permission paths.

## Always Use For
- Any PD One Mattermost DM, group, or channel request.
- Requests involving employee scope, source-system access, writebacks, attachments, Mattermost history/logs, permission changes, or unclear channel boundaries.
- Admin requests that mention gateway/config/policy/source edits or review-log handling.

## Source of Truth
- Policy root: `/home/prodesign/.hermes/profiles/pdone`
- Channel policy: `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-channels.md`
- Users/roles: `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-users.json`, `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-roles.json`
- Effective cache: `/home/prodesign/.hermes/profiles/pdone/policy-cache/mattermost/users/{mattermost_user_id}.json`
- Legacy OpenClaw workspace: `/home/prodesign/.openclaw/workspace` is a compatibility/reference mirror, not the source of truth, unless Andy explicitly asks to inspect or repair legacy state.

The gateway injects `[PD One Hermes permission bridge]`; the configured cache source is Hermes-native and the context is mandatory per-turn authorization evidence. Authorize by exact Mattermost sender id only; never by display name, username, memory, or fuzzy matching.

### Exact-sender fallback when injected context is absent

If the injected bridge is missing or incomplete, fail closed and use admin handoff. Do not recover sender identity by printing `HERMES_SESSION_*` or message ids from a shell, `python -c`/`-e`, or `execute_code`. Hermes posts the approval card into the origin thread before that command runs, so a later refusal cannot unsend it. A skill sentence does not stop the card; `plugins/pd_one_sender_tool_gate` must block the tool in `pre_tool_call`. A plugin file edit is not the live gate until the gateway that loaded that plugin restarts. If the bridge is present, or Andy already posted an exact approve in the origin thread, do not probe process identity at all. A username, display label, prior transcript, memory entry, or previously known id is not exact-event evidence.

## Permission migration / storage-change pitfall
See `references/turn-bridge-migration-pitfall.md` and `references/hermes-policy-migration-smoke-checks.md` / `references/hermes-policy-migration-phase-gates.md`.

## Load Detail When Needed
Before sensitive, ambiguous, review-log, permission-expansion, or specialist work, load `references/complete-original-skill.md` and the matching reference below (use `skill_view` with this skill name).

| Topic | Reference |
| --- | --- |
| Full legacy playbook | `references/complete-original-skill.md` |
| Sub-agent delegation | `references/controlled-subagent-delegation.md` |
| PDAPP ticket lifecycle | `references/admin-approval-ticket-lifecycle.md` |
| Channel purpose / access setup | `references/mattermost-channel-purpose-and-access-setup.md` |
| Document-scoped delegated editor | `references/document-scoped-delegated-editor.md` |
| Work-manual editor grants | `references/role-scoped-work-manual-editor-grants.md` |
| Group portal module grants | `references/group-keyed-portal-module-change-grants.md` |
| Group work-manual change grants | `references/group-keyed-work-manual-change-grants.md` |

Also read exact policy/cache files when injected context is absent or incomplete.

## Non-Negotiables
Load `references/turn-bridge-non-negotiables.md` every turn before scoped Mattermost work or privileged tools.

## Review logging and special topics
Load `references/turn-bridge-review-and-special-topics.md` for review-log triage, employee ISO questions, work-manual/ISO contradiction checks, verification checklist, and historical search ladder.


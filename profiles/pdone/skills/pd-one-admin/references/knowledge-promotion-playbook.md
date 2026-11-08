# PD Neo → PD One Knowledge Promotion Playbook

Purpose: when Hermes/PD Neo learns a stable, safe operational fact with Andy, decide whether it should also be promoted into PD One/OpenClaw so employee-facing and operational agents do not fall behind Hermes-only memory.

This playbook is for **knowledge promotion**, not live runtime migration. It must not change messaging tokens, gateway config, bot identity, channel routing, or employee permissions by itself.

## Use this when

Use this playbook after conversations that produce any durable, reusable knowledge such as:

- company terminology or translation conventions;
- where important data lives and how to query it;
- employee-facing workflow explanations;
- AppSheet table/workflow behavior;
- Mattermost/PD One response rules;
- source guides for spreadsheets, documents, or AppSheet tables;
- non-admin capabilities PD One should know about or advertise;
- repeated mistakes/pitfalls that should change agent behavior;
- **Hermes-created or Hermes-updated skills** whose content is not purely Hermes/PD Neo administration.

Do **not** use it for temporary task progress, one-off conclusions, raw transcripts, secrets, credentials, unverified guesses, private HR details, or admin-only diagnostics that should remain scoped.

Admin-only Hermes/PD Neo skill changes include local Hermes setup, model/provider config, gateway secrets/routing, backup mechanics, and `nemo` administration. Mixed skills should be split: keep admin mechanics in Hermes, and promote only the distilled portable operational rule or pitfall to PD One/OpenClaw.

## Core rule

If the fact is stable beyond this week, useful outside the current Hermes chat, and safe for the intended audience, do not leave it only in Hermes memory. Promote a distilled version to the correct Hermes PD One source of truth.

## Google Docs/Sheets source-page rule

When Hermes/PD Neo or PD One answers questions using company Google Docs or Google Sheets, consult the company wiki source page for that file before relying on the live document/workbook. The source page is the routing and safety layer: title/file ID, canonical-vs-backup status, tab/section map, likely headers/fields, freshness model, access/disclosure limits, data-quality caveats, and open questions.

Operational sequence:

1. Search the company wiki by stable Google file ID or exact title.
2. Read the matching `sources/` page and identify the relevant tab/section plus access caveats.
3. Verify exact facts against the live Google Doc/Sheet range/section when the answer depends on current values or exact procedure wording.
4. If no source page exists or the page says the scan is pending, treat the answer as incomplete: create/update the source page or escalate for Andy/admin review before presenting analysis as reliable.
5. Never treat a source page as permission expansion; normal Mattermost/user/channel role policy still controls what can be disclosed.

## Audience classification

Classify before writing:

| Audience | Allowed content | Typical destination |
|---|---|---|
| Employee-facing | concise terminology, authorized procedures, source names, how to ask PD One for help | company wiki, glossary, public skill guidance |
| Manager/supervisor | aggregated evidence, workflow rules, decision-support caveats | wiki/source guide, domain runbook |
| Andy/admin | implementation paths, backup commits, policy mechanics, admin runbooks | `pd-one-admin` references, OpenClaw admin runbooks |
| Agent-only | routing/checklist logic that helps agents behave correctly | skills, runbooks, policies |
| Not promotable | secrets, raw private memory, raw logs, sensitive HR rows, unstable guesses | do not promote; keep local/private or discard |

When unsure, choose the narrower/admin-only destination and ask Andy before making it employee-facing.

## Routing matrix

| Knowledge type | Promote to | Notes |
|---|---|---|
| AppSheet schema, table behavior, data-location rules, query paths | OpenClaw `skills/appsheet-copilot/` and matching Hermes AppSheet skill/reference | Keep schema-backed names exact. Use prototype/deployed context correctly. |
| Employee-facing company knowledge, document/source explanations | company wiki source/synthesis pages | Include provenance, freshness, access guidance, caveats, and open questions. |
| Terminology, translations, bilingual labels | translation glossary and/or wiki terminology page; domain skill if operationally critical | Prefer Andy-approved canonical terms. |
| Mattermost response behavior, authorization, channel rules | OpenClaw Mattermost policies/runbooks; Hermes `pd-one-admin` reference if admin-relevant | Do not expose policy internals to normal users unless intended. |
| Admin-only procedures for OpenClaw/PD One | Hermes `pd-one-admin` reference and OpenClaw admin runbook | Keep private implementation details out of employee-facing docs. |
| Reusable automation/workflow pattern | relevant OpenClaw skill/runbook and Hermes skill if PD Neo also needs it | Include verification and rollback/safety checks. |
| Data source/workbook knowledge | company wiki source guide + relevant domain skill | For Sheets, describe tabs/fields/freshness/caveats; do not dump private data. |
| Stable user preference about Andy/Hermes only | Hermes user profile/memory | Do not promote to PD One unless Andy explicitly wants PD One to share it. |

## Promotion checklist

Before promoting:

1. **Stability:** Is this likely to remain useful beyond the current week?
2. **Evidence:** Is it source-backed or explicitly Andy-approved?
3. **Audience:** Who may safely know this: employees, managers, Andy/admin, or agents only?
4. **Privacy:** Does the distilled version avoid secrets, private memory, raw logs, HR details, and unnecessary internal paths?
5. **Canonical owner:** Which source should own it long-term?
6. **Conflict check:** Does it contradict an existing skill/runbook/wiki page? If so, update the canonical owner and remove/qualify stale wording.
7. **Implementation:** Write the minimal durable update in the canonical place.
8. **Verification:** Re-read/search the destination and confirm the fact is present and scoped correctly.
9. **Backup:** If OpenClaw durable files changed, commit/push only the intentional files and report the commit hash to Andy.

## Safety boundaries

- Do not promote secrets, `.env` values, tokens, keydrop contents, private logs, raw message history, raw personal memory, or private HR row details.
- Do not grant employee agents new tools, roles, data access, or admin authority through a documentation update.
- Do not restart OpenClaw/PD One gateway as part of knowledge promotion unless Andy separately approves a restart for another reason.
- Do not post to public/company channels just to “announce” a promotion unless Andy asks.
- For high-impact policy changes or permission-affecting guidance, queue the recommendation or ask Andy before applying broadly.

## Implementation workflow for requested promotions

When Andy asks to build or change the promotion mechanism itself, use this sequence:

1. **Plan first:** write a short implementation plan with exact files, acceptance criteria, rollback path, and no-runtime-side-effect constraints.
2. **Independent/second-pass review:** double-check the plan for privacy, privilege expansion, gateway/runtime impact, broad commits, and whether employee-facing vs admin-only scope is clear.
3. **Implement narrowly:** edit the smallest canonical files; avoid live gateway/config/message changes unless explicitly requested.
4. **Smoke test reversibly:** prefer read-only classification/search checks proving the routing works; do not public-post, restart, or write live business records just to test documentation.
5. **Commit narrowly:** OpenClaw workspaces often contain unrelated dirty/generated state. Stage only intentional files, inspect `git diff --cached --name-only`, and push a narrow backup commit. For Hermes backup, prefer manual/narrow sync when the broad backup helper would sweep unrelated state.
6. **Mirror into PD One when appropriate:** if the durable learning is meant for PD One/OpenClaw, update both the Hermes playbook/reference and the matching OpenClaw runbook/skill/policy/wiki page when that mirror exists, then commit each backup narrowly.
7. **Report evidence:** include the changed destinations, smoke-test result, and backup commit hashes.

## Reversible smoke-test recipe

Use a dry classification without live side effects:

1. Pick one sample fact.
2. Classify knowledge type, evidence, audience, canonical destination, and exclusions.
3. Confirm the destination already contains the fact or identify the minimal file that would receive it.
4. Do not send public messages, write live records, restart gateway, or change permissions.
5. If the test required a temporary file, remove it before finishing.

Example:

> Fact: “Risk reports / 風險回報 and incident reports / 事件報告 mean the same thing; old reports live in Google Sheets; new reports live in AppSheet.”

Classification:

- Type: terminology + AppSheet/legacy data-location rule.
- Audience: employee-safe in summarized form; admin-safe with file paths/commit details.
- Destination: AppSheet skill/reference; optionally company wiki/glossary if employees need a public explanation.
- Exclusions: no raw HR report rows; no gateway restart; no public post unless requested.

## Reporting format to Andy

Use a compact summary:

```text
Promoted shared knowledge to PD One:
- Fact: <distilled fact>
- Audience: <employee-safe / manager / admin / agent-only>
- Destination: <file/page/skill>
- Verification: <read/search result>
- Backup: <commit hash or not needed>
- Notes: <privacy caveat or next step>
```

---
name: pd-one-admin
description: "PD One admin operating context on Hermes: durable files, runbooks, playbooks, policies, profile boundaries, and legacy OpenClaw migration references. Load when working as the PD One/admin agent or handling Pro-Design admin operations that moved into Hermes. See references/pd-neo-pd-one-profile-boundary.md when distinguishing PD Neo/default-profile Hermes from PD One/pdone."
version: 1.0.0
author: Hermes Agent
license: private
metadata:
  hermes:
    tags: [pd-one, admin, openclaw-migration, prodesign]
---

# PD One Admin Context

This Hermes `pdone` profile is the active PD One runtime/governance home. PD Neo/default-profile Hermes remains the admin/operator surface, while PD One employee-facing Mattermost permission governance now lives in `/home/prodesign/.hermes/profiles/pdone`.

OpenClaw remains available as a legacy compatibility/reference workspace for migrated state and specialized historical assets, but it is no longer the Mattermost permission/governance source of truth unless Andy explicitly asks to inspect or repair legacy OpenClaw state.

Hermes PD One profile root:
`/home/prodesign/.hermes/profiles/pdone`

Legacy OpenClaw admin workspace retained for compatibility/reference:
`/home/prodesign/.openclaw/workspace`

Legacy OpenClaw workspace skills source:
`/home/prodesign/.openclaw/workspace/skills`

Imported Hermes top-level OpenClaw skills currently available under `~/.hermes/skills/<skill-name>/`:
`appsheet-copilot`, `appsheet-incident-briefing`, `automation-reliability`, `chub-docs`, `company-announcement-writer`, `executable-update-auditor`, `gog`, `google-docs-work-manual`, `google-drive-organizer`, `google-forms`, `mattermost-playbooks`, `mold-repair-scheduling`, `monthly-worker-scheduling`, `n8n-automation`, `n8n-workflow-automation`, `production-scheduler`, and `visual-office-qa`.

When refreshing/importing OpenClaw skills into Hermes, copy only skill directories with `SKILL.md`, place each at top level by its frontmatter `name`, and exclude live secrets/runtime clutter (`.env*` except examples/templates, `__pycache__`, `.pyc`, logs/caches, and nested `.git`).

## Required operating rules

1. Messaging settings, secrets, tokens, `.env`, runtime logs, bot state, and message transport config remain sensitive runtime state. Do not migrate or alter them from this context unless explicitly requested. PD One/pdone and PD Neo/default-profile gateways may both exist; keep their credentials and channels separate and avoid token/gateway competition.
2. For PD One/admin tasks, first inspect the relevant source-of-truth files under the Hermes PD One profile root. Start with:
   - `AGENTS.md`
   - `SOUL.md`, `USER.md`
   - policies under `policies/`
   - tools under `tools/`
   - skills under `skills/`
3. Treat OpenClaw files under `/home/prodesign/.openclaw/` as legacy/runtime state unless explicitly asked to edit them. Do not restart any Hermes/PD One/legacy OpenClaw gateway without explicit Andy approval first; a restart can kill or orphan in-progress admin/background tasks, in-process completion watchers, and live user work. Exception: Andy permits a restart without asking first when bounded checks show the relevant gateway is already unresponsive; document the evidence, use the gateway restart runbook, and verify recovery afterward.
4. Maintain audience separation: Andy/admin output can include diagnostics and implementation details when relevant; regular-user/shared-channel output must be concise, scoped, non-admin, and privacy-preserving.
5. If a task touches a domain with a relevant Hermes skill/runbook or legacy OpenClaw reference, read that source before acting.
6. For continuing migration or checking live runtime health, follow `references/admin-migration-playbook.md`: bounded probes first, safe triage before alerting, and no gateway restart or messaging-token migration without explicit approval.
7. When Andy explicitly approves a PD One gateway restart, follow `references/pd-one-gateway-restart.md`: validate config first, avoid foreground gateway restart from a live turn, verify by new PID + ready signal + channel health, and commit any durable config fix.

## OpenClaw plugin allowlist hardening

If OpenClaw logs warn that `plugins.allow` is empty and non-bundled plugins may auto-load, pin the current approved plugin inventory in `/home/prodesign/.openclaw/openclaw.json` under `plugins.allow`. Use the plugin IDs from enabled `plugins.entries` plus any required bundled channel/provider plugins, then validate with `openclaw config validate` and verify logs no longer contain the warning after the gateway reload/restart. Do not restart the gateway yourself unless Andy explicitly approved; OpenClaw may self-defer/restart if the changed config requires it. Commit only the narrow allowlist change and leave unrelated dirty runtime/wiki files untouched.

## PD One LINE webhook and sender recognition

For LINE Messaging API setup, webhook validation, Cloudflare Tunnel ingress, pairing, recognizing Andy's LINE sender as owner/admin, and safely rolling back over-broad LINE group-test settings, use `references/pd-one-line-webhook-operations.md`. Key durable pattern: keep `/line/webhook` publicly reachable but exact-path scoped through Cloudflare Tunnel, rely on LINE signature verification instead of Cloudflare Access, store LINE credentials in `0600` secret files, after pairing record Andy both in `channels.line.allowFrom` and `commands.ownerAllowFrom` as `line:<sender-id>`, and do not use wildcard group `requireMention=false` as a casual test shortcut.

## Known admin assets in OpenClaw

- Agent index and guardrails: `/home/prodesign/.openclaw/workspace/AGENTS.md`
- Core admin rules: `/home/prodesign/.openclaw/workspace/docs/agent-rules/core-operating-rules.md`
- Identity/persona: `/home/prodesign/.openclaw/workspace/IDENTITY.md`, `SOUL.md`, `USER.md`
- Tool notes: `/home/prodesign/.openclaw/workspace/TOOLS.md`
- Heartbeat behavior: `/home/prodesign/.openclaw/workspace/HEARTBEAT.md`
- Runbooks: `/home/prodesign/.openclaw/workspace/docs/runbooks/`
- Policies: `/home/prodesign/.openclaw/workspace/policies/`
- Skills: `/home/prodesign/.openclaw/workspace/skills/`
- Tools/scripts: `/home/prodesign/.openclaw/workspace/tools/`, `/home/prodesign/.openclaw/workspace/scripts/`

## PD One knowledge promotion

When Hermes/PD Neo learns stable, safe, non-admin-specific operational knowledge that PD One or employees may also need, do not leave it only in Hermes memory. Promote a distilled version into the appropriate Hermes PD One source of truth: skill, runbook, company wiki/source guide, glossary, policy, or admin-only reference. Use `references/knowledge-promotion-playbook.md` for the routing matrix, safety boundaries, checklist, implementation workflow, narrow-commit discipline, and reversible smoke-test recipe.

## PD One durable-file size guardrails

When Andy asks to prevent PD One durable/bootstrap files from exceeding injection limits, or when a durable file grows near truncation risk, use `references/durable-file-size-watchdog.md`. The safe pattern is a deterministic Hermes no-agent cron watcher that scans all PD One workspace roots, includes `MEMORY.md` as well as `AGENTS.md`/`USER.md`/`TOOLS.md`/identity files, warns before the 12k-character per-file guardrail, stays silent on OK, records state/log evidence, and backs up both the OpenClaw config change and Hermes cron/script state.

## PD One / PD Neo channel split and alert routing

Current intended split: PD One/OpenClaw is employee/company-facing on Mattermost as the main surface, with Telegram as Andy-only DM backup; PD One should not remain active on Discord unless Andy explicitly asks. PD Neo/Hermes is the admin/operator surface on Discord as main, with Telegram as backup; PD Neo should not remain active on Mattermost unless Andy explicitly asks for temporary migration/testing.

PD One admin/operator alerts that previously went to Discord should now route to the **PD One Admin Mattermost channel** `channel:5gmqtwqf7bde3cyihas79xi8ie`. When auditing this, inspect local scripts/systemd units, Hermes cron delivery, and n8n workflows; active n8n workflow JSON can retain stale `Send Discord` connection references even after node conversion. Use `references/pd-one-admin-alert-routing.md` for the full inventory, reroute, n8n, verification, and commit sequence.

PD Neo operational alerts should deliver to Discord channel `1503946606985216090` unless Andy explicitly requests a different target. For Hermes cron jobs use `deliver: discord:1503946606985216090`. For OpenClaw CLI sends to Discord channels, use channel-qualified targets such as `channel:1503946606985216090`; bare numeric Discord IDs can be ambiguous and fail with `Ambiguous Discord recipient`.

## PD One n8n notification convention

When administering PD One/OpenClaw n8n workflows that send user/admin-facing notifications, route notifications through the shared/common notification workflow by default instead of embedding direct channel-send nodes. See `references/n8n-notification-convention.md` for payload shape, pitfalls, and source-of-truth workspace files.

## PD One failure alerts to Hermes auto-triage

Selected deterministic PD One/OpenClaw failure alerts can be mirrored to Hermes/PD Neo through the loopback-only Hermes webhook subscription `pd-one-failure-autofix`. OpenClaw bridge script: `/home/prodesign/.openclaw/workspace/tools/pd_one_failure_to_hermes.py`; operational runbook: `/home/prodesign/.openclaw/workspace/docs/runbooks/pd-one-failure-alert-autofix.md`. Preserve the original human alert path and call the bridge as secondary best-effort notification (`|| true`); if the webhook listener is unavailable, the bridge queues alerts under `/home/prodesign/.hermes/pd-one-failure-alerts/queue.jsonl` for the Hermes no-agent cron worker. Hermes may auto-triage bounded evidence and apply only low-risk reversible fixes; OpenClaw gateway restarts, process kills, destructive cleanup, messaging-token/gateway changes, external-send replays, and production-impacting writes still require Andy approval. Auto-triage outputs should route alert-worthy summaries to Discord channel `1503946606985216090` unless Andy explicitly requests another target; keep local/log-only only when the automation is purely internal and a primary human alert already exists elsewhere. General implementation pattern: `automation-reliability` reference `references/webhook-alert-fallback-queue.md`.

For `pd-one-session-metrics-collector` failures in `tools/pd_one_metrics/collect_session_metrics.py`, use `references/pd-one-session-metrics-collector.md`. Durable pitfall: OpenClaw session `message.content` can contain both structured dict parts and legacy/plain string entries; collector loops that call `item.get(...)` on every content item can crash with `AttributeError: 'str' object has no attribute 'get'`. Reproduce with temp outputs, patch content iteration narrowly, verify with `py_compile`, a temp collector run, and one live aggregate run, then commit/push only the source fix when a backup remote is configured. Do not restart the gateway or change messaging config for this collector-only failure.

## Company wiki ownership handoff

When planning or executing a company wiki takeover from PD One/OpenClaw to PD Neo/Hermes, separate **canonical ownership** from **employee-facing access**. Hermes should own the canonical vault, maintenance, exports, cron, provenance, and backups; PD One may still query/read a permission-filtered export or controlled query service on behalf of employees when allowed. Do not simply disable all PD One wiki access unless a replacement read path is verified or Andy explicitly wants employees to lose wiki querying. Use a staged import/quarantine flow instead of direct `rsync --delete` into the canonical vault, fail closed on non-admin exports with missing access metadata, and keep the existing private mirror admin-only until a replacement mirror/read path is proven. See `references/company-wiki-ownership-handoff.md` for the cutover checklist, access-control guardrails, mirror handoff rules, and rollback-safe disable pattern.

For Yammer/Viva Engage historical message/attachment migration into the wiki, the operational project currently lives under `/home/prodesign/.openclaw/workspace/projects/yammer-migration`; use the Hermes `company-wiki` skill reference `references/yammer-attachment-archive-resume.md` for attachment downloader resume/recovery guardrails. Routine status should summarize counts/progress/blockers without exposing private filenames unless detailed evidence is needed.

## PD One data source registration

When asked to add an operational data source (especially Google Sheets) to PD One's sources, register it in the canonical memory wiki source layer, link it from the relevant registry, compile the wiki, and commit narrowly to avoid unrelated dirty workspace state. For complex workbooks, a basic registry entry is not the same as analysis readiness; consider a second-pass source guide/data dictionary with tab map, fields, freshness model, analysis recipes, and role disclosure rules. See `references/pd-one-data-source-registration.md` for the source-page template, source-guide checklist, access-recommendation defaults, verification steps, and commit pitfalls.

When answering employee product dimension/reference-document requests from `review_log`, verify the actual requester from the live row, check authorization, and use the AppSheet `Reference_Documents` + canonical `sql-srv/SIP&SOP` lookup pattern in `appsheet-copilot` reference `references/product-reference-doc-dimension-lookup.md`; SIP PDFs are the dimension source of truth, while AppSheet records help resolve product/mold/doc IDs.

For Annual Evaluation / 360 review / personnel skill-test data requests, use `references/annual-evaluation-restricted-access.md`. The canonical form/sheet includes all BUs, so do not share the full response workbook with a department requester; inspect viewer/analysis tabs and provide only an approved restricted BU-scoped view/export (for example `成型` for Leon) or a final refusal/escalation before closing related `review_log` rows.

## PD One Google Sheets/Docs employee assistance

When launching or operating employee-facing help for Google Sheets/Docs, brand it as a **PD One** capability and route shared-channel announcements through PD One/OpenClaw when possible. In the current non-Workspace-domain setup, there is no domain-wide add-on install path; employees must either share files with `admin@prodesign-group.com` for the direct URL workflow, use PD One DMs with links, or rely on later template/add-on alternatives. See `references/pd-one-google-file-assistance.md` for permission wording, Mattermost announcement guidance, and the trial-service template.

For the Project List workbook (`良器-跨部門-專案追蹤表 Project List`), use `references/project-list-maintenance-automation.md`: stable row IDs should be created by a bound Apps Script in a far-right `PD One Issue ID` column, while PD One/OpenClaw backend jobs handle Mattermost thread monitoring, Thursday workday responsible-person DMs, one-item-at-a-time reply collection, and appending progress to column G `改善歷程`. Column I is now `對話連結`; do not rely on the older scanned header `關聯對象`.

## AppSheet operating context

When asked any concrete AppSheet schema/design/expression/security-filter/performance question for Pro-Design, use the migrated OpenClaw AppSheet sources before answering: `/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/SKILL.md`, `/home/prodesign/.openclaw/workspace/docs/runbooks/appsheet-agent-rules.md`, and `/home/prodesign/.openclaw/workspace/projects/AppSheet/appsheet_definition.json`. Do not ask Andy for exports or answer from generic AppSheet memory when the local synced definition already contains the needed schema/wiring.

For sensitive multi-BU HR/evaluation Google Forms response sheets, create an admin-only scoped filtered review copy before any employee-facing share decision, and do not close related review_log rows merely because admin-side prep is done. See `google-forms` reference `references/sensitive-response-sheet-filtered-copy.md` and this skill's `references/mattermost-review-log-health-check.md`.

For `appsheet-definition-sync.service` failure alerts, treat transient network/DNS evidence as a low-risk auto-triage candidate: inspect the bounded service status/journal plus `logs/appsheet-definition-sync.log` and `data/appsheet-definitions/<app_id>/state.json`, verify DNS/HTTPS to `www.appsheet.com`, then run the documented quiet idempotent sync once if connectivity has recovered. Verify by `state.json` (`status=ok`, `failure_count=0`) and latest artifact metadata/version; note that `systemctl --user status` may still display the previous failed `ExecMainStatus` after a manual script rerun even when `systemctl show Result=success` and sync state are healthy. Do not change OpenClaw messaging settings just because the failure notification send also failed.

When asked to clean up duplicated AppSheet settings columns between `HR_Employees` and `HR_Employees_AppSheet_Settings` / `HR_E_A_S`, audit `Current User` vs `Current User Settings`, direct `LOOKUP(USEREMAIL(), ...)` calls, security filters, views, slices, actions, and HREAS formulas. See `references/appsheet-settings-migration-audit.md` for deterministic scripts, current slice interpretation, and migration order.

## AppSheet stale Case analysis

When asked to identify stale AppSheet `Case` records, use a read-only prototype-app pull of `Case`, `Case_Updates`, attachments, and employees; score only non-terminal cases by inactivity, overdue deadline, created age, and sparse updates. See `references/appsheet-stale-case-analysis.md` for the exact table set, activity calculation, terminal statuses, output artifacts, and report shape.

## Mattermost missed-message catch-up

When Andy says PD One/Hermes or PD Neo/default-profile Hermes was offline/failing, or asks which Mattermost threads “should have replied but didn’t,” check both bot surfaces when scope is ambiguous, use bounded logs/health only to establish outage windows and runtime-failure evidence, then use Mattermost REST post/thread history plus Hermes PD One channel binding/policy as the source of truth. Include configured `requireMention: false` channels as reply candidates even without explicit mentions, and correlate high-confidence misses by channel/thread ID against routed agent lanes such as `session:agent:<agent>:mattermost:group:<channel_id>:thread:<root_id>`. If a missed authorized message clearly needs a reply, answer in the original thread, keep channel replies bilingual, and verify the created post before claiming delivery. See `references/mattermost-missed-message-catchup.md`.

## Mattermost parent-post attachment visibility pitfall

If PD One says it cannot see files in a Mattermost thread, verify whether the files were attached to the **thread root/parent post** while the later `@pdone` request is a reply with no `file_ids`. Mattermost ingress should treat an explicit bot mention in a thread as permission to inspect the full visible thread history: fetch `/api/v4/posts/<root>/thread`, collect prior/root `file_ids`, and pass those files through the normal remote-media path. Use Mattermost REST (`GET /api/v4/posts/<id>/thread`, `/api/v4/files/<file_id>/info`, and a bounded `/api/v4/files/<file_id>` download check) to distinguish permission/download failures from context-construction limitations. Do not make users re-upload files already present in the thread as the primary solution. See `references/mattermost-thread-history-attachments.md` for the diagnostic and patch pattern.

When missed replies coincide with OpenClaw instability, triage and mitigate runtime churn before replay: check for PPID=1 orphan `openclaw` / `openclaw-acp` processes that generate `protocol mismatch`, check `journalctl --user -u openclaw-gateway.service` for `stalled session`, `codex app-server client is closed`, and event-loop liveness warnings, and temporarily disable noncritical high-frequency OpenClaw cron jobs or review-log scanners if they are repeatedly launching agent/summarizer work and degrading PD One. Prefer reversible `cron disable`/`systemctl --user stop <timer>` over gateway restart when health still answers; restart only under the approved unresponsive-gateway rule and verify with a live `openclaw agent` PONG probe plus Mattermost health.

## Mattermost review_log health checks and open-item closure

When Andy asks whether `review_log` is still catching employee interactions with PD One in Mattermost DMs/channels, or asks to review/close open `review_log` items, use the bounded timer/state/log + dry-run/backstop and open-item closure sequence in `references/mattermost-review-log-health-check.md`. Do not restart the OpenClaw gateway; filter dry-run candidates for Andy/admin rows because append-time filtering intentionally excludes Andy/admin activity from employee review logging. For closure work, treat stable identifiers such as `mattermost_post_id`, ticket id, timestamp/user/request as authoritative over row numbers because related actions can insert new audit rows while you work. For explicitly requested historical outage repair, use the bounded single-row backfill pattern and row-update checklist in `references/mattermost-review-log-outage-backfill.md`.

When creating a new PD One employee role, editing an existing role, changing role/source permissions, or changing the access policy gate, always smoke-test PD One by pretending to be different employees before reporting success. Use `references/employee-access-smoke-tests.md`: keep it read-only/no-message, cover representative employee classes plus an unknown sender, test both allowed and denied specialist paths, and watch for the deny-text regex pitfall in `pd-one-employee-safety-gate` scope matching. If SIP/SOP Reference Docs access is part of the test, also load `appsheet-copilot` reference `references/appsheet-enumlist-row-api.md` for the separate AppSheet visibility-row checks.

For Python test-suite cleanup around `tools/mattermost_review_log.py` and `tools/review_log_source_collector.py`, use `references/mattermost-review-log-test-maintenance.md`: reproduce with the targeted `PYTHONPATH=... pytest ...` commands, account for dynamic sheet headers, structured note columns, and the current DM `auth` dict API, then run the full `tests/` suite before a narrow commit.

## Mattermost channel agent provisioning

When asked what agent a PD One Mattermost channel should use, or to add a channel-specific agent, first classify whether the channel is ordinary employee help, durable department/workflow scope, or true admin-only scope. Durable department/workflow channels should usually get a scoped channel agent, not `admin`; define business scope and write boundaries before editing `openclaw.json`. See `references/mattermost-channel-agent-provisioning.md` for the decision rule, config/documentation checklist, permission defaults, read-only source invariant pattern, and commit/restart pitfalls.

## Mattermost employee-channel admin handoff pitfall

If PD One acknowledges Andy approval in a normal Mattermost thread but still does not implement an automation/integration, check whether the channel falls through to `employee-assistant` instead of `admin`. Approval text in an employee/channel thread is not a route switch or tool-policy elevation, and `request_approval` only logs/requests approval; it does not create Sheets, cron/n8n jobs, or code changes. If `request_approval` timed out, inspect the gateway journal and `state/admin-approval-tickets.jsonl` for partial draft/readiness events before claiming nothing was captured; the synchronous review-log append path can time out after a draft ticket exists. See `references/mattermost-employee-admin-handoff.md` for triage steps and explanation patterns.

## Mattermost admin UAC approval workflow

When asked how to implement, debug, or verify employee-request/admin-approved work in PD One, use a deterministic ticketed elevation layer: employee agent creates an approval ticket, Admin channel gets a translated approval card, Andy approves by exact Mattermost user ID, and an admin executor runs the approved scope back in the originating thread. Do not grant broad admin tools to `employee-assistant` or rely on prompt-only `approve` text. Keep the live PD One runbook `/home/prodesign/.openclaw/workspace/docs/runbooks/pd-one-admin-approval-workflow.md` synchronized with this Hermes skill. See `references/admin-uac-approval-workflow.md` for the implementation pattern, data model, listener/executor shape, `admin:` shortcut handling, durable async final-result watcher behavior, and smoke-test checklist. Approved tickets now create conservative reusable approval grants so same-requester/same-channel follow-ups can skip repeated admin pings while red-line changes still require fresh approval; live runbook: `/home/prodesign/.openclaw/workspace/docs/runbooks/admin-approval-grants.md`. For focused maintenance of the restart-survivable admin-prefix final-result callback, use `references/admin-prefix-durable-completion-watches.md`.

For employee-facing SOP generation, use the scoped draft/preview/confirmation/admin-approval pattern in `references/pd-one-sop-assistant-workflow.md`: employees may search, draft, and receive a Word preview; PD One must ask whether the Word result is correct and whether the values should be submitted to update the master XLSX; only then should it create an admin-approval request. Keep approval required until several clean runs justify explicitly relaxing that specific write path.

## Mattermost bilingual channel enforcement

When PD One/OpenClaw Mattermost channel/group replies become monolingual, audit the routed agent workspace, not only the canonical policy. Department channels often route to specialized agents whose `AGENTS.md` must carry the hard bilingual pre-send rule directly; pointer-only references to shared policy are not sufficient. See `references/mattermost-bilingual-enforcement-audit.md` for source locations, session-prompt inspection, visible-output checks, the Option A remediation pattern, and the guard script `/home/prodesign/.openclaw/workspace/tools/mattermost_channel_agent_guard.py` that should pass before deploying new channel-specific agents.

## PD One translation glossary enforcement

When Andy asks whether PD One translations/final answers use the official translation list, verify and maintain both layers: prompt-visible glossary guidance and a deterministic outgoing/pre-send glossary guard. Prompt-only instructions are not enough for company-facing terminology. The guard should be conservative: correct known bad English terms and English-section source terms, but avoid rewriting Traditional Chinese sections. See `references/pd-one-translation-glossary-guard.md` for the implementation shape, verification checklist, and restart/reportback pitfalls.

## Mattermost channel posting pitfall

For Pro-Design Mattermost posts, do not assume Hermes' bare `mattermost`/home target is the intended public or AI channel; it may resolve to the admin channel. If Andy asks for a PD One/company-channel post and provides a channel id, prefer routing the request through PD One/OpenClaw or a verified Mattermost API path, and verify the target channel before sending. Known AI channel id: `imj7bt6w4tdk5rsbttiga44agc`. If a post is accidentally sent to admin, send a concise correction/escalation to PD One rather than reposting repeatedly through ambiguous Hermes targets. See `references/mattermost-channel-posting.md` for the posting sequence and pitfall wording.

## Migration exclusions

The requested migration excludes:
- OpenClaw messaging/channel/gateway settings
- provider/API keys and all `.env*` files
- secrets directories
- runtime logs, bot state, temporary files, browser profiles, and bulk exports/backups unless explicitly requested

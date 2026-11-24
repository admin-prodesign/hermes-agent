# Automation supervisor agent pattern

Use this reference when Andy asks for a broader supervisor/steward agent, default automation babysitting reduction, alert/autorepair coverage audits, or making new automations compliant by default.

## Purpose

A supervisor agent is not the business worker. It is an auditor and guarded repair orchestrator that verifies unattended automations continue to satisfy their intended outcome without Andy having to remind PD One to add alerts, receipts, or repair hooks after each build.

Core goal statement:

> Every unattended automation should have a registered purpose, owner, schedule, health/readback checks, alert route, and auto-repair classification. The supervisor stays silent when healthy and reports only actionable gaps or approval-needed repairs.

## Recommended architecture

1. **Machine-readable automation registry**
   - Keep a central registry under the owning Hermes profile, e.g. `/home/prodesign/.hermes/profiles/pdone/supervisor/automations.json`.
   - Each entry should record: name, owner, criticality, schedule/source timer, script/service path, source systems touched, state/log paths, expected freshness, health checks, alert route, auto-repair target if any, approval-required actions, and verification receipts.

2. **Read-only supervisor audit**
   - Inventory active Hermes cron jobs, relevant systemd timers/services, and known non-Hermes scheduled workers.
   - Compare live scheduler state against the registry.
   - Inspect scripts/wrappers for guarded-triage markers such as `pd_neo_cron_failure_alert`, `pd_neo_failure_to_hermes`, `pd_one_failure_to_hermes`, `pd_one_cron_failure_alert`, `emit_pd_one_event`, or `hermes_guarded_autorepair`.
   - Check logs/state for stale receipts, stuck queues, recent failures, missing readbacks, and delivery errors.
   - Classify each automation as healthy, missing alert bridge, missing registry entry, missing auto-repair classification, stale/no recent receipt, failed delivery path, approval-only recovery, or do-not-autorepair.
   - Silent on success; concise stdout only for actionable findings.

3. **Deterministic safe-repair layer**
   - Prefer deterministic scripts for narrow supervision repairs before giving an LLM broad agency.
   - Safe repair can self-register newly discovered scheduler entries, add conservative fail-closed auto-repair classifications, and write remediation-plan files for missing alert/failure bridges.
   - Keep safe repair stdout machine-readable when scheduled as `no_agent=true`; emit concise JSON/text receipts and stay silent or minimal when no action is needed.
   - Do not use deterministic repair as a hidden business worker. It must not perform source-system writes, employee DMs, message replays, credential/token repair, gateway restarts, permission expansion, or schema/data cleanup.

4. **Guarded wrapper installer**
   - Use the shared allowlisted runner (`hermes_guarded_autorepair.py`) and target registry where possible instead of bespoke repair scripts.
   - For cron jobs that need failure triage, an allowlisted wrapper installer may rewrite a cron script path only when the registry explicitly sets an allow flag such as `supervisor.allow_autonomous_wrapper=true`.
   - The wrapper must preserve the original worker's stdout, stderr, and exit code, and only add failure-event emission/readback around the worker.
   - Installing a wrapper must not execute the wrapped business job; validate with script compile/shell syntax, cron readback, and a bounded smoke run of the supervisor/installer only.
   - Approval-gated by default: gateway restarts, credential/auth repair, employee DMs, source-system writes, Google Drive permission/move operations, message replays that could duplicate external sends, broad cleanup/deletion, and schema/data-integrity changes.

5. **LLM supervisor agent layer**
   - Add an LLM supervisor only after the deterministic audit/repair substrate exists and has receipts.
   - The LLM supervisor prompt must be self-contained because cron runs do not inherit chat context; include paths, allowed actions, forbidden actions, validation steps, commit/backup discipline, and the no-recursive-cron rule.
   - Scope the LLM supervisor to running audit/repair scripts, inspecting findings, making safe plumbing changes, validating/committing them, and reporting approval-needed items.
   - Do not let the LLM supervisor restart gateways, send employee prompts/replays, repair auth, modify source systems, alter permissions, or create new cron jobs recursively.

6. **Workflow compliance gate**
   - Treat supervision as part of “done” for every new recurring automation: worker implemented, dry-run tested, live receipt verified, alert/failure route wired, auto-repair decision recorded, registry entry added, and durable changes backed up when configured.
   - If an automation is intentionally exempt, record why in the registry rather than relying on memory.

## Audit starter checklist

- `cronjob list` for Hermes cron jobs.
- `systemctl --user list-timers` and targeted `systemctl --user status` for relevant user timers.
- Read the guarded auto-repair registry, usually `/home/prodesign/.hermes/profiles/pdone/autorepair/targets.json`.
- Health-check allowlisted targets with `hermes_guarded_autorepair.py --target <name> --health-only --json`; interpret `health: none` targets as trigger-only rather than automatically broken.
- Run the existing alert architecture audit when available: `/home/prodesign/.hermes/scripts/automation_alert_architecture_audit.py`.
- Supplement narrow audit scripts with direct script-marker scans and state/log freshness checks; a green timer alone is not proof that the workflow outcome is healthy.

## Project Tracker / Project List-specific supervisor signals

For the Project List follow-up automation, supervisor checks should include both timer health and business-outcome health:

- weekly sender produced prompt `post_id` receipts when expected;
- `pending_dm_prompts` exists after live sends unless all prompts completed;
- reply poller checks nonzero prompts after live sends;
- plain and threaded DM replies after prompt timestamps are either matched or deliberately rejected;
- Sheet column-G append has readback before prompt completion is marked;
- stale waiting prompts and reminder/deadline state are surfaced;
- queue records with completion fields but `status: waiting_reply` are treated as corruption;
- state-file saves from different workers merge dict-valued buckets instead of overwriting each other.

## PD One starter implementation pattern

When Andy asks to start/continue a broader supervisor audit, the minimal safe build is a read-only script-only cron plus registry, not an LLM agent with broad write privileges:

- Registry: `/home/prodesign/.hermes/profiles/pdone/supervisor/automations.json`.
- Audit script: `/home/prodesign/.hermes/profiles/pdone/scripts/pd_one_supervisor_audit.py`.
- Cron pattern: `no_agent=true`, `profile="pdone"`, `deliver=origin`, daily cadence, stdout silent when no findings.
- Script scope: discover enabled Hermes cron jobs, selected `systemctl --user` timers/services, guarded autorepair target registry, and workflow-specific state/log receipts; compare live state to registry; emit findings only.
- Add a deterministic safe-repair script after the first audit if Andy wants less babysitting. In the PD One implementation this lives at `/home/prodesign/.hermes/profiles/pdone/scripts/pd_one_supervisor_repair.py` with wrapper `/home/prodesign/.hermes/profiles/pdone/scripts/pd_one_supervisor_repair_json.sh` and cron `ce885aff7a8d`; it runs every 10 minutes, self-registers cron jobs, writes conservative classifications, applies allowlisted wrappers, stays silent on no-op, and creates remediation plans without touching business systems.
- Add an allowlisted wrapper installer only after registry classifications exist. In the PD One implementation this is `/home/prodesign/.hermes/profiles/pdone/scripts/pd_one_supervisor_apply_wrappers.py`; it must require explicit per-automation opt-in such as `supervisor.allow_autonomous_wrapper=true` and preserve original worker stdout/stderr/exit code. For faster repair loops, call the wrapper installer from the deterministic safe-repair wrapper and keep stdout silent unless actions occurred.
- Native Hermes agent/prompt cron jobs with no script cannot use script wrappers. The PD One audit should instead enforce scheduled-fire receipts: `next_run_at` is not overdue, the previous scheduled due time has a `last_run_at` receipt within the grace window, `last_status=ok`, and `last_delivery_error` is empty. Do not flag these as missing script wrappers; flag missed-fire/status/delivery failures.
- Add an LLM supervisor agent only after deterministic receipts exist. In the PD One implementation the 2-hour deterministic-gated supervisor cron is `8ca621fbe187`. Its cron prompt is compact and automation-only, while `conditional_llm_cron_gate.py` enforces the same scope in code so stale prompt text cannot restore removed responsibilities. It processes at most one highest-severity changed automation finding, can run audit/repair scripts and validate/commit safe plumbing, verifies native no-script jobs by scheduler receipts, and is explicitly barred from interaction-row/Mattermost/ECRN inspection, gateway restarts, employee sends/replays, auth repair, source-system writes, permission changes, broad cleanup, and recursive cron creation. Employee reply/review work belongs to the dedicated quality supervisor, semantic-review shadow, and daily digest lanes.
- Verification before reportback: `python3 -m py_compile` for Python scripts, shell syntax for wrappers, `python3 -m json.tool` for the registry/cron file, manual `--json` or text runs, `cronjob run` for created jobs, and `cronjob list` readback showing `last_status=ok` and the next scheduled run.
- Backup discipline: sync/profile backup or git commit/push after adding scripts/registry, after scheduling cron jobs, and after first run receipts if cron state is backed up separately.

The first audit should intentionally flag existing gaps rather than hide them. Common initial findings are missing guarded-triage bridge markers in enabled cron scripts, delivery-only jobs without wrapper scripts, stale workflow queues, and eligible auto-repair targets that are registered but not wired into the business monitor. Convert these to remediation-plan files so future supervisor runs have a structured backlog instead of relying on chat memory.

## Reporting style

For Andy/admin, report concise receipts and concrete next fixes:

- what was inspected;
- number of active jobs/timers;
- current critical gaps;
- which gaps are safe to fix without approval vs approval-gated;
- no broad employee-visible details unless explicitly requested.

Notifications delivered to chat must be human-readable Markdown, not raw JSON. It is fine for scripts to keep `--json` for machine use, but scheduled/no-agent stdout that reaches Andy should translate action dictionaries into short bullets such as “Registered cron job…”, “Wrote remediation plan…”, or “Installed guarded wrapper…”. Include paths/job IDs only as receipts, and do not paste full JSON unless Andy explicitly asks for it.

Do not present a supervisor as an unrestricted autonomous fixer. The safer framing is: **auditor + allowlisted repair orchestrator + compliance gate for future automations**.

## Deterministic-gated supervisor runs and semantic receipts

When a deterministic gate packet already contains the audit findings, use it as the first evidence source. Re-run the repair, wrapper, and audit commands for current verification, but do not repeat broad discovery unless a repair changed state or a source-of-truth readback is needed.

Treat structured JSON semantics as authoritative over process exit codes: an audit command may return `rc=0` while reporting `ok=false` and unresolved `findings`. Record both values in the receipt; `rc=0` means the audit executed, not that the automation estate is healthy.

For remediation-plan deduplication, match the automation identity plus the gap/state class (`missing bridge`, `missing-live-cron`, `stale-live-source`, `stale waiting prompt`, etc.), not only the latest timestamp or finding text. Reuse an existing exact-class plan and report current evidence without creating a new file for every repeated observation. Do not update old evidence merely to make it look current unless the run is explicitly authorized to maintain plan records.

Interaction-row and employee-content review is not part of the automation supervisor. Keep it in the dedicated quality supervisor, canonical semantic-review shadow, and daily digest lanes, each with its own bounded queue/checkpoint and privacy controls. The automation supervisor may inspect only aggregate health receipts for those lanes; it must not fetch raw Sheet rows or Mattermost threads.

### Prevent self-triggering supervisor loops

Do not use remediation-plan/report/backup mtimes as standalone LLM invocation reasons. Those artifacts are outputs of supervisor work, so advancing their mtime after a successful run creates an output-to-trigger feedback loop. Retain the latest artifact mtime in the deterministic evidence packet for readback, but invoke the LLM only for a normalized audit-signature change, actionable queue presence, explicit force, severity escalation, or the bounded periodic scan.

When a legacy supervisor prompt has accumulated unrelated work, enforce the split twice: replace the cron prompt with a compact operator-readable contract, and make the gate choose a hard-coded mode-specific supervisor prompt instead of blindly appending the legacy prompt. Regression tests should prove that a plan-mtime-only change yields `invoke_agent=false`, the legacy workload marker is absent from the generated supervisor prompt, and the live cron prompt delegates removed work to named dedicated lanes.

## Autonomous supervisor run pattern for unresolved audit findings

When a scheduled supervisor-agent run finds unresolved critical/warning items and the fix is approval-gated, it can still make a useful safe local change: write a timestamped remediation-plan JSON under `/home/prodesign/.hermes/profiles/pdone/supervisor/remediation-plans/` with the finding evidence, actions already tried, recommended admin action, `autonomous_status: blocked`, `block_reason`, and `approval_required: true`. This turns ephemeral audit output into durable backlog without touching business systems.

Before writing a plan, search for an exact match on both automation and gap/state. Reuse an existing plan when the gap is the same class even if the automation name is unchanged; do not create a duplicate for a new run of the same stale-success, missing-live-cron, missing-bridge, or delivery-failure condition. Only create a new plan when the current evidence is materially different from prior plans for that automation (for example, `missing bridge` vs `missing live cron` vs `stale-live-source`). When a matching plan already exists, report its path as the durable backlog receipt and stop there.

A practical pattern for bounded supervisor reports is: inspect the live audit output, search plans for exact-gap coverage, and if needed write one new plan plus validate it. Keep the plan narrow and local; never use the plan writer as a business worker or a substitute for the missing source-system fix.

After writing remediation plans, validate with `python3 -m json.tool` for the new plans plus the registry, and `python3 -m py_compile` for supervisor scripts if they were part of the run. If backup sync is configured, run `/home/prodesign/hermes-backup/scripts/sync-hermes-backup.py`, then commit/push only the relevant supervisor files/plans; do not sweep unrelated dirty backup changes into the supervisor commit.

Self-monitoring findings are valid backlog items but should be handled conservatively. If the supervisor audit reports `last_status=error` for the supervisor-agent cron itself, do not create a duplicate supervisor cron, recursively edit its prompt, or restart scheduler/gateway components from the same run. Write a remediation plan for the cron error with the job id, `last_run_at`, `next_run_at`, `last_status`, and any delivery error, and recommend a post-run cron readback plus saved execution-log inspection. Treat changes to the supervisor's own schedule/prompt/runtime as admin approval-gated unless the run was explicitly authorized to repair that exact path.

Missing live cron findings for registered one-shot jobs should be handled as a registry/scheduler reconciliation issue, not an automatic recreation. If a registered Hermes cron job (especially a one-shot report) is no longer present in live cron, first search existing remediation plans for the same job id plus missing-live-cron/not-found state. If no exact plan exists, write a plan that preserves the ambiguity: the job may be intentionally completed/expired and should be retired from the registry, or it may need an approved recreation from a saved prompt/script with explicit delivery and receipts. Scheduled supervisor-agent runs must not create replacement cron jobs or delete/reclassify registry entries unless the run was explicitly authorized for that exact repair. Commit only the new exact plan file after backup sync, leaving unrelated backup dirt untouched.

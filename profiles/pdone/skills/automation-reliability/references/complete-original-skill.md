---
name: automation-reliability
description: 'Use for recurring/unattended automation: cron, systemd, n8n, CI, webhooks, monitors, scheduled reports. Enforce retries, idempotency, observability.'
---

# Automation reliability and error handling

## PURPOSE
Make unattended automation safe to run repeatedly: auditable, idempotent where possible, failure-visible, alert-disciplined, and easy to recover.

## WHEN TO USE
Use this skill before creating, installing, reviewing, or changing any automation that can run without someone watching it, including:
- `cron` / user crontab jobs
- systemd services, timers, and user units
- OpenClaw `cron` jobs
- n8n / webhook / low-code workflows
- scheduled shell, Python, Node, or CI jobs
- recurring reports, syncs, monitors, imports, exports, cleanup jobs, and self-healing scripts

Do not use this as a substitute for platform-specific skills. Pair it with the relevant skill/runbook when touching n8n, systemd, OpenClaw cron, Google Workspace, AppSheet, or production systems.

## REQUIRED DESIGN GATES
For every unattended automation, define these before enabling it. If the automation was created in response to a user request, also treat the visible user-facing reply as part of the automation: do not claim it is live, scheduled, completed, or will run later unless the job has a machine-verifiable receipt and a verification/readback step.

1. Owner and purpose
   - Who cares if it breaks?
   - What business/system outcome proves success?

2. Trigger and frequency
   - Schedule, timezone, expected duration, concurrency policy, and overlap prevention.
   - Use `flock`, lock files, queue semantics, or systemd concurrency controls when overlap would be harmful.

3. Idempotency and safe reruns
   - Dedup key, output naming, checkpoint/state file, or transaction boundary.
   - Retrying must not duplicate external sends, rows, files, payments, tickets, or destructive actions.

4. Logging and durable run evidence
   - Generate or record a `run_id` when practical.
   - Persist start, success, skip/no-op, retry, and failure states.
   - Capture enough context to debug without dumping secrets or private raw data.
   - For long-running sync or inventory jobs, expose a lightweight status file that can be polled without reading large result files. Include current item/folder, completed/total counts, run directory, result paths, and start timestamp. If a full result file can become large, poll the small status first and only fetch/decode the result when needed.

5. Error handling
   - Fail closed when outputs would be misleading or partial.
   - Distinguish expected no-op/empty-result from real failure.
   - Capture stderr/exception details and final exit code.
   - Do not swallow errors with unconditional `|| true`, broad `except`, or success-looking fallback output unless the fallback is explicitly logged as degraded.

6. Alert policy
   - Never allow silent failure: every final failure must be discoverable through logs, status rows, monitor state, or a review queue.
   - High-impact or infrequent jobs may alert immediately after retry exhaustion.
   - Frequent recurring jobs must avoid alert spam: confirm the issue is more than transient before external alerts by using retries with backoff, consecutive-failure thresholds, time-window thresholds, or error budgets.
   - For content-change watchers with review/suggestion layers, decide and document the notification boundary before alerting. Default human-facing edit alerts to committed/approved/live content, not drafts or suggested edits, unless the user explicitly wants proposal-review alerts.
   - For responsiveness/degradation watchdogs, prefer a sustained-evidence gate over immediate threshold alerts: keep local state/log evidence for every threshold hit, but require multiple consecutive scheduled samples plus a minimum elapsed duration before external people alerts. Example: a 5-minute cron can require 4 consecutive problem samples and at least 15 minutes of persistence before alerting, with a multi-hour per-condition cooldown.
   - Log every failed attempt immediately even when suppressing external alerts.
   - Send recovery/clear notifications only when useful and not noisy.

7. Review queue and manual recovery
   - For failed records/items, write enough metadata to reprocess safely.
   - Approval is required before replaying writes, external sends, destructive cleanup, or production-impacting fixes unless the user already approved that exact behavior.

8. User-facing commitment receipt
   - Any reply that says the automation is done, live, scheduled, or will follow up must include evidence appropriate to the audience: job ID, cron ID, run ID, status row/file, output URL, row count, post ID, or commit hash.
   - Verify by readback when possible. A command/API success response is not enough when the created schedule, written data, or sent message can be checked directly.
   - For canary/monitoring requests after risky app/config changes, run an immediate baseline check before scheduling follow-ups when safe; this gives the user a current `check 1/N` result and distinguishes pre-existing noise from new regressions.
   - If the action cannot be completed or tracked yet, say it is blocked/pending and name the missing approval, credential, permission, runtime, or input. Do not phrase it as completed.
   - If promising future follow-up, create a real expiring follow-up/monitor job in the same turn; if that cannot be created, state explicitly that no automatic follow-up is in place.

9. Monitoring and verification
   - Add a small verification step after install/change: dry-run, one-shot run, `systemctl --user status`, recent log tail, status row check, or equivalent.
   - Document where to inspect logs/state and how alerts are routed.

## CRON / SHELL CHECKLIST
- Use absolute paths and explicit environment loading.
- Wrap commands so stdout/stderr go to a bounded log.
- Preserve exit status from the real command.
- Avoid overlapping runs (`flock` or equivalent) when needed.
- For launchers that use `systemd-run --user --unit=<fixed-name>` to start long-running workers from frequent cron ticks, do not rely only on the worker's internal lock. Check `systemctl --user is-active` and/or the same `flock` lock *before* calling `systemd-run`; reusing a fixed transient unit name can stop/restart the older unit before the worker-level lock gets a chance to protect it.
- Avoid bare pipelines without `set -o pipefail` in shell wrappers.
- Do not validate a side-effecting shell wrapper by invoking it with `--help`, `--dry-run`, or a dummy argument unless the script explicitly implements that mode and exits before side effects. Many ad-hoc wrappers ignore unknown args and will run the real action. For syntax/permission checks, use `bash -n`, `shellcheck` when available, `stat`, and inspect guard clauses instead.
- Do not report success unless the core command succeeded and expected outputs passed validation.
- When a long-running job is in progress, report bounded evidence from a lightweight status artifact first rather than blocking on a full output file. Schedule an expiring follow-up check when the user wants completion reporting and the job is expected to outlive the current turn.
- For progress monitors on batch workers whose coarse completion counters only advance after large units finish, include an intermediate liveness signal before warning on "no progress". Examples: cache/temp/output file mtimes and size growth, worker heartbeat updates, active child process elapsed time, or per-item download/extract logs. Suppress stale/no-progress alerts only while that intermediate signal is fresh; keep the warning path active when both completion counters and liveness signals stall.
- When intentionally pausing, disabling, or handing over a monitored backend process for manual operation, also pause or adjust dependent watchdogs/alerting jobs in the same change window. Verify both layers: the underlying process/task is in the desired state and the monitor will not emit expected-noise false alerts while the manual intervention is underway.
- For Hermes no-agent cron scripts, place scripts under `~/.hermes/scripts/` and pass the cron `script` value as the relative filename only; verify by manually running the cron and reading back the output/status artifact. If a Python no-agent script fails because the scheduler resolves a missing project venv/interpreter, keep the Python logic in a `.py` file but schedule a tiny `.sh` wrapper that execs `/usr/bin/python3 /absolute/path/to/script.py`.
- For no-agent wrappers that contain their own fallback or guarded-triage bridge, budget internal timeouts below the Hermes scheduler script timeout (`cron.script_timeout_seconds` / `HERMES_CRON_SCRIPT_TIMEOUT`, default commonly 120s). A wrapper that spends the full scheduler budget on the primary command can be killed before the fallback/bridge runs, producing a human-readable timeout with no auto-repair event. Use explicit per-phase timeouts (for example shorter primary timeout + bounded repair timeout), log phase starts/exits, and re-run the alert-architecture audit afterward.
- For scheduled monthly playbook kickoffs into Mattermost, use the same no-agent reliability pattern as other external sends: a shell wrapper under `~/.hermes/scripts/`, Python logic with `--check-only` and `--dry-run`, `flock` overlap protection, durable JSON state keyed by the target business period, JSONL run logs, and a Mattermost post ID readback before claiming it is live. If the automation is created on the due date itself, manually run the verified script once so the current cycle is not missed, then rely on idempotent state to avoid duplicate sends.
- For post-change canary/monitoring requests, prefer deterministic `no_agent` monitors over LLM-driven jobs when the task is log collection/classification. Use a tiny locked shell wrapper under `~/.hermes/scripts/`, durable state under `~/.hermes/state/<monitor>/`, JSONL run logs under `~/.hermes/logs/<monitor>/`, and raw evidence files. Run an immediate baseline, force one scheduler run, then read back `cronjob list`; include job ID, repeat count, next run, state/log paths, and backup/commit evidence in the reply. Make clean runs silent, first/baseline and periodic summaries visible, and issue alerts cooldown-limited by signature.
- For Mattermost online/offline status panels, use `references/pd-one-mattermost-status-post.md`: maintain one editable Mattermost post via `posts/{post_id}/patch`, store post/state/log evidence under `~/.hermes/state` and `~/.hermes/logs`, use 1-2 failures as degraded and 3+ as offline, and verify a real scheduled tick. If Hermes cron creation does not prove execution because the scheduler is not visibly persistent, switch to a systemd user timer and back up copies of the unit files under Hermes state.
- For OpenClaw/Codex SQLite log bloat, use `references/openclaw-codex-log-retention.md`: inspect DBs read-only, trim rows older than a bounded retention window, checkpoint/VACUUM, check `lsof +L1`, configure analytics/log-level mitigations, and install a silent-on-success retention job.
- For scheduled external sends with a clear useful delivery window, prefer the retry-until-deadline wrapper pattern in `references/retry-until-deadline-cron.md`: durable per-date success state, bounded retry cron, alert suppression before the final attempt, and no duplicate sends after success.
- For user-visible promises made by an agent, use `references/action-commitment-lifecycle.md`: commitment receipts, verification readbacks, and an auditor pattern for catching “said it would/did, but no evidence exists.”
- For chat/agent bridges that routed a message but failed before replying, use `references/missed-message-replay.md`: evidence-based candidate detection, thread readback, idempotent replay state, audit logging, and response-output-shape verification before posting.
- For Google Sheet + chat maintenance loops, use `references/sheet-chat-maintenance-automation.md`: split Sheet-local ID assignment from backend chat monitoring, validate live headers before writes, use stable IDs instead of row numbers, guard against duplicate history appends, lock both scheduled and manual runs, and read back Sheet writes.
- For local self-hosted sidecars/services wired into an agent runtime (memory backends, local APIs, model services), use `references/self-hosted-agent-service-integration.md`: isolate the service directory, bind to loopback/non-default ports, use a private user-editable key file plus generated `.env`, start slow Docker builds with background completion notification, verify service + agent status before claiming it is live, and back up durable config.

## SYSTEMD TIMER CHECKLIST
- Prefer `Type=oneshot` for scheduled jobs.
- Set useful `Description=`, `WorkingDirectory=`, and explicit `EnvironmentFile=` when needed.
- Do not assume user-systemd has the interactive shell `PATH`; if commands like `gog`, `gh`, or project CLIs live under `~/.local/bin`, set `Environment=PATH=/home/USER/.local/bin:/usr/local/bin:/usr/bin:/bin` or call absolute command paths.
- Use `OnCalendar=` with documented timezone assumptions.
- Consider `Persistent=true` for catch-up behavior only when safe.
- Use `Restart=` carefully: retries must be idempotent and not spam external systems.
- Verify with `systemctl --user daemon-reload`, `systemctl --user list-timers`, status, and journal logs when appropriate.
- When recovering a failed oneshot by manually running the underlying script instead of `systemctl start`, remember that `systemctl status` can still display the previous failed `ExecMainStatus`. Verify recovery with the automation's own state/output artifacts plus `systemctl show ... -p Result -p ActiveState`, and reset failed state only after evidence shows the job is healthy.

## SELF-HEALING GENERATED CHECKOUTS

For unattended jobs whose output checkout is fully derived and safely regenerable, a narrow auto-fix is acceptable before alerting on common Git failures such as exit `128`: validate the exact checkout path and expected remote, remove stale Git lock files, reset/clean only the generated checkout, reclone only if validation fails, retry once, and alert if repair or retry fails. Never apply this pattern to canonical source directories, hand-edited working trees, or production data without explicit approval and a rollback plan. A concrete company-wiki implementation is documented in the `company-wiki` skill reference `references/wiki-mirror-git128-autorepair.md`.

For watchdogs around long-running sync tools, distinguish stale scheduler/status errors from current run evidence before alerting or auto-fixing. A prior failed run should not keep paging people after a bounded remediation timestamp is newer than the failed run; suppress stale repeats while waiting for the next scheduled sample, but keep alerting on new distinct stderr, failed result, warnings/errors, or stalled-progress evidence.

## WEBHOOK / AGENT ALERT FALLBACK QUEUES

When a recurring job sends a secondary alert to a webhook/agent for auto-triage, preserve the original human alert path and add a durable fallback queue for webhook downtime. The bridge may be best-effort (`|| true`) only if it queues failures and the primary alert path already ran. Drain the queue with a silent-on-empty no-agent cron/script worker, lock against concurrent drains, cap alerts per run, and keep remediation prompts bounded and approval-gated for restarts, process kills, destructive cleanup, token/gateway changes, external-send replays, and production writes.

Detailed implementation and verification checklist: see this skill's `references/webhook-alert-fallback-queue.md`.

For PD One/OpenClaw recurring monitors and scanners that need to federate actionable failures to PD Neo/Hermes, use the existing PD One → PD Neo bridge rather than inventing a new queue/protocol. Preserve primary Mattermost/Discord/user-facing alerts first, add a secondary admin-only best-effort event, and keep employee requests/approvals/specialist handoffs off the failure bridge. Internal heartbeat/runtime-health alerts from employee-facing bots should not be posted into employee channels; route them to the admin alert rail plus the guarded auto-repair bridge instead. Concrete wiring and verification pattern: `references/pd-one-federation-alert-wiring.md`.

For PD Neo/Hermes-owned scripts and cron jobs, use the PD Neo guarded-triage bridge instead of relying only on human-visible Discord/origin output. Route actionable failures/warnings through `/home/prodesign/.hermes/scripts/pd_neo_failure_to_hermes.py`; shell wrappers can use `/home/prodesign/.hermes/scripts/pd_neo_cron_failure_alert.py` for threshold/cooldown state. Fallback queue is `/home/prodesign/.hermes/pd-neo-failure-alerts/queue.jsonl`, drained by cron job `7fb19f50dea1` (`PD Neo failure alert queue worker`) every 2 minutes. Preserve the primary human alert path first; this is a secondary repair/triage rail. Allowed events are `pd-neo.failure`, `pd-neo.incident`, `pd-neo.runtime_health`, `pd-neo.automation_warning`, `pd-neo.knowledge_candidate`, and `pd-neo.capability_gap`. Detailed wrapper/audit/verification pattern: `references/pd-neo-guarded-alert-bridge.md`. Future cron/automation creation must also follow `references/future-automation-guarded-autorepair.md`; daily audit job `ed6ca3025b37` (`Automation alert architecture audit`) checks enabled Hermes cron scripts and reports only when a future script appears human-readable-only or missing guarded auto-repair wiring.

For log/review scanners such as PD One `review_log`, classify recovered Mattermost/network/API errors as transient local-log events, and reserve human alerts plus Hermes auto-triage for persistent or non-transient failures. The secondary triage agent should inspect service status, scanner state, logs/journal, and recovery evidence before making narrow reversible fixes; restart/kill/token changes, external-send replays, and production writes remain approval-gated. Scanner-specific checklist: `references/pd-one-review-log-scanner-autotriage.md`.

## OUTPUT EXPECTATIONS
When proposing or implementing automation, include:
- trigger/frequency
- idempotency/safe-rerun behavior
- logging/state location
- retry policy
- alert threshold, especially for frequent recurring jobs
- fallback queue/drain behavior when webhook or agent delivery is secondary
- user-facing commitment receipt or explicit blocker/pending state when the reply promises completion, scheduling, delivery, or follow-up
- verification performed or blocker to verification
- for long-running jobs still in progress: current lightweight status, where detailed results will land, and any expiring follow-up job created
- for human-facing alerts: translate raw platform codes/counters into plain-language impact and likely cause; keep raw codes as evidence, but do not make humans decode scheduler exit codes, CSV counters, or opaque API statuses

## STOP AND ASK
Ask before enabling or changing automation when it can:
- send external messages/emails/posts
- write to production systems or AppSheet/Google Sheets
- delete/move/rename data
- restart services or modify system security
- create noisy alerts to people/channels
- require credentials or permission expansion

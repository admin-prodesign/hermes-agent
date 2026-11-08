# Future automation guarded auto-repair checklist

Use this checklist before enabling or updating any Hermes/PD Neo or PD One/OpenClaw unattended automation.

## Required alert architecture

1. Preserve the primary human-visible behavior:
   - cron `deliver=origin` / Discord / Mattermost output stays useful and bounded;
   - silent-on-success jobs remain silent when healthy.
2. Add a secondary guarded-triage route for actionable failures/warnings:
   - PD Neo/Hermes-owned jobs: `/home/prodesign/.hermes/scripts/pd_neo_cron_failure_alert.py` or `/home/prodesign/.hermes/scripts/pd_neo_failure_to_hermes.py`;
   - PD One/OpenClaw-owned jobs: `/home/prodesign/.openclaw/workspace/tools/pd_one_failure_to_hermes.py` or `pd_one_federation_bridge.emit_pd_one_event`.
3. Keep fixes approval-gated unless a narrow runbook pre-approves them:
   - service restarts, process kills, token/gateway changes, destructive cleanup, external-send replays, and production writes require approval.
4. Use threshold/cooldown for frequent cron jobs.
5. Add fallback queue coverage through the existing bridge scripts, not a new protocol.
6. Run the daily audit job after adding new cron jobs:
   - Job: `Automation alert architecture audit`
   - Script: `/home/prodesign/.hermes/scripts/automation_alert_architecture_audit.py`
   - Silent when no gaps are found.

## PD Neo wrapper template

```bash
#!/usr/bin/env bash
set -euo pipefail
CMD=(/usr/bin/python3 /home/prodesign/.hermes/scripts/example_worker.py "$@")
rc=0
"${CMD[@]}" || rc=$?
/usr/bin/python3 /home/prodesign/.hermes/scripts/pd_neo_cron_failure_alert.py \
  --source example-worker \
  --rc "$rc" \
  --summary "Example worker failed repeatedly" \
  --command "${CMD[*]}" \
  --threshold 2 \
  --cooldown-seconds 3600 || true
exit "$rc"
```

## Direct warning template

```bash
/usr/bin/python3 /home/prodesign/.hermes/scripts/pd_neo_failure_to_hermes.py \
  --source example-monitor \
  --summary "Example monitor warning needs triage" \
  --event-type pd-neo.automation_warning \
  --severity warning \
  --detail "$warning_text" \
  --command "/home/prodesign/.hermes/scripts/example_monitor.py" \
  --what-was-tried "Primary human-readable alert remains visible; this is a secondary guarded-triage event." || true
```

## Generic guarded auto-repair runner

For PD One/Pdone automations, prefer pointing monitors at the shared allowlisted runner instead of embedding one-off repair logic. When asked to “wire auto-repair” or make repairs generic, first inventory enabled cron/jobs and existing one-off repair scripts before adding new machinery; the user expects reuse/consolidation, not parallel bespoke repair paths.

- Runner: `/home/prodesign/.hermes/scripts/hermes_guarded_autorepair.py`
- Target registry: `/home/prodesign/.hermes/profiles/pdone/autorepair/targets.json`
- Logs: `/home/prodesign/.hermes/logs/guarded-autorepair/`
- State/cooldowns: `/home/prodesign/.hermes/state/guarded-autorepair/`

Pattern:

```bash
/home/prodesign/.hermes/scripts/hermes_guarded_autorepair.py --target <allowlisted-target> --health-only --json
/home/prodesign/.hermes/scripts/hermes_guarded_autorepair.py --target <allowlisted-target> --trigger "short bounded cause" --json
```

The registry should encode the concrete safe action (`docker_restart`, `command`, etc.) and health check (`cdp`, `none` for trigger-only verifier targets, etc.). Do not pass arbitrary shell commands from a monitor into the runner. Repair actions that restart browser/noVNC containers are still distinct from Hermes gateway restarts; never restart Hermes gateways unless Andy explicitly approves or the gateway is already unresponsive.

## Migration workflow for existing automations

1. Enumerate live scheduler state (`cronjob list` plus root/profile `cron/jobs.json` when needed) and map enabled jobs to the exact script path they run.
2. Search for existing repair/retry/fallback scripts before creating a new target; migrate narrow one-off repairs behind the generic runner when the action is already bounded.
3. Classify each automation as one of:
   - **wire now**: repair is narrow, reversible/low-risk, allowlisted, cooldown-safe, and has a health/readback check;
   - **leave inline**: recovery is a mode of the business script or a local stale-lock/systemd reset that would lose semantics if moved too early;
   - **do not auto-repair**: auth, schema/data-integrity, external-send replay, source-system writes, broad cleanup, gateway/provider changes, or anything needing approval.
4. Add each “wire now” case to `targets.json`; keep command targets fixed allowlist commands and pass only bounded `--repair-arg` values when the target explicitly allows them.
5. Document the inventory in a durable reference/runbook next to the registry so later sessions know why some automations were not wired.
6. Verify syntax, target registry readback, usage readback (which scripts call the runner), health-only/no-op target checks, and the alert architecture audit before reportback.

## Verification before reportback

- `bash -n` for shell wrappers.
- `python3 -m py_compile` for Python scripts.
- For stdout-delivery shell wrappers that pipe through `tee`, verify the wrapper uses `PIPESTATUS[0]` and exits with the original command status, not `tee`'s status.
- For audit-reported human-readable-only cron jobs, inspect the actual scheduler JSON/readback and script path before editing: jobs may live in the root Hermes cron store while the active Mattermost profile is `pdone`, and the audited script may be under `/home/prodesign/.hermes/scripts/` rather than `/home/prodesign/.hermes/profiles/pdone/scripts/`. Wrap the script that the enabled job actually runs; do not “fix” a similarly named profile-local watchdog unless the enabled cron points there.
- For Python workers scheduled directly by cron/no-agent, verify the top-level exception path writes a bounded failure log, calls the threshold helper, and still exits nonzero.
- `cronjob list` readback for enabled jobs when the scheduler context exposes jobs; if it does not, use the deterministic audit/status scripts as the architecture receipt instead of assuming no jobs exist.
- Dry-run `pd_neo_failure_to_hermes.py` or `pd_neo_cron_failure_alert.py`.
- Run `automation_alert_architecture_audit.py`; it should be silent when coverage is complete.

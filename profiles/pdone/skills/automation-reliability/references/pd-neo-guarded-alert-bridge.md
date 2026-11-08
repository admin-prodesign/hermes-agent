# PD Neo guarded alert bridge for auto-triage

Use this when Hermes/PD Neo-owned cron scripts, watchdogs, imports, exports, or maintenance wrappers need to notify PD Neo for guarded auto-triage/auto-repair without relying only on human-visible Discord/origin cron output.

## Route and files

- Webhook route: `pd-neo-failure-autofix`
- Bridge script: `/home/prodesign/.hermes/scripts/pd_neo_failure_to_hermes.py`
- Threshold/cooldown helper: `/home/prodesign/.hermes/scripts/pd_neo_cron_failure_alert.py`
- Fallback queue: `/home/prodesign/.hermes/pd-neo-failure-alerts/queue.jsonl`
- Queue worker script: `/home/prodesign/.hermes/scripts/pd_neo_failure_alert_queue_worker.py`
- Queue worker cron: `PD Neo failure alert queue worker` (`7fb19f50dea1` when present), every 2 minutes, script-only/no-agent, silent when empty.

Accepted event types:

- `pd-neo.failure`
- `pd-neo.incident`
- `pd-neo.runtime_health`
- `pd-neo.automation_warning`
- `pd-neo.knowledge_candidate`
- `pd-neo.capability_gap`

## Wrapper pattern for cron/no-agent scripts

Keep the primary cron behavior authoritative: preserve the underlying command's exit status and any existing human-visible cron delivery. Add the PD Neo helper as a secondary thresholded alert path.

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

For no-agent wrappers whose stdout is the primary human-visible delivery, do **not** redirect output only to a temp file. Preserve stdout with `tee`, capture the real command status with `PIPESTATUS[0]`, then call the helper and exit with the original status:

```bash
#!/usr/bin/env bash
set -euo pipefail
LOG_DIR=/home/prodesign/.hermes/logs/example
mkdir -p "$LOG_DIR"
TMP=$(mktemp "$LOG_DIR/example-worker.XXXXXX")
CMD=(/usr/bin/python3 /home/prodesign/.hermes/scripts/example_worker.py "$@")
set +e
"${CMD[@]}" 2>&1 | tee "$TMP"
rc=${PIPESTATUS[0]}
set -e
/usr/bin/python3 /home/prodesign/.hermes/scripts/pd_neo_cron_failure_alert.py \
  --source example-worker \
  --rc "$rc" \
  --summary "Example worker failed repeatedly" \
  --command "${CMD[*]}" \
  --log "$TMP" \
  --threshold 2 \
  --cooldown-seconds 3600 \
  --event-type pd-neo.incident \
  --severity error || true
if [[ "$rc" -eq 0 ]]; then
  rm -f "$TMP"
fi
exit "$rc"
```

For Python no-agent workers that are scheduled directly (not through a shell wrapper), wrap only the top-level `main()` call: catch unexpected exceptions, write a bounded failure log under `~/.hermes/logs/<area>/`, call `pd_neo_cron_failure_alert.py` with that log path, then exit nonzero. Do not swallow the failure or convert it into success-looking output.

Use a direct bridge call for warning conditions detected inside a script, especially when the cron stdout already goes to a human/origin target:

```bash
/usr/bin/python3 /home/prodesign/.hermes/scripts/pd_neo_failure_to_hermes.py \
  --source example-progress-monitor \
  --summary "Example monitor warning needs triage" \
  --event-type pd-neo.automation_warning \
  --severity warning \
  --detail "$warning_text" \
  --command "/home/prodesign/.hermes/scripts/example_progress_monitor.py" \
  --what-was-tried "Primary progress alert remains visible in the cron delivery target; this is a secondary guarded-triage event." || true
```

## Verification checklist

1. Syntax check modified scripts:
   - `python3 -m py_compile ...`
   - `bash -n ...`
2. Verify webhook subscription exists and accepted events include the needed event type.
3. Run a dry-run route smoke test:
   - `/usr/bin/python3 /home/prodesign/.hermes/scripts/pd_neo_failure_to_hermes.py --source smoke --summary 'dry-run' --event-type pd-neo.runtime_health --severity info --detail 'dry-run only' --dry-run`
4. For helpers, run a dry-run threshold alert:
   - `/usr/bin/python3 /home/prodesign/.hermes/scripts/pd_neo_cron_failure_alert.py --source helper-smoke --rc 1 --summary 'helper dry-run smoke' --command helper-smoke --threshold 1 --cooldown-seconds 0 --dry-run`
5. Check queue health:
   - queue file absent or size 0 is OK;
   - processing file absent or size 0 is OK;
   - failed directory absent or empty is OK.
6. Verify the queue worker cron is enabled and last status is OK.
7. If a live smoke is appropriate, send a low-impact `pd-neo.runtime_health` event with a unique idempotency key and verify the webhook returns accepted status. Do not use live smoke if it would create user-facing noise.

## Safety policy

PD Neo guarded-triage alerts may automatically inspect local state, logs, queue files, and recent cron output. They may perform only low-risk, reversible, evidence-backed fixes. Keep these actions approval-gated unless a narrower pre-approved runbook says otherwise:

- restarting OpenClaw/Hermes/gateway services;
- killing processes;
- changing tokens, credentials, webhook secrets, or gateway ownership;
- replaying external sends or user-visible posts;
- destructive cleanup or deletion;
- production-impacting writes.

## Common migration pitfall

Some Hermes/PD Neo-owned wrappers were originally using PD One helper names such as `pd_one_cron_failure_alert.py`. When inventorying alert coverage, check whether the script is truly PD One-owned or PD Neo/Hermes-owned. PD Neo-owned cron wrappers should use `pd_neo_cron_failure_alert.py`/`pd_neo_failure_to_hermes.py` so alerts route through `pd-neo.*` events and the PD Neo fallback queue.

## Human-visible-only audit pattern

When asked whether anything only alerts humans, compare two inventories:

1. Human-visible alert/send/warning paths (`openclaw message send`, Mattermost, Discord, Telegram, cron origin output, warning text).
2. Federation/guarded-triage emits (`emit_pd_one_event`, `pd_one_failure_to_hermes.py`, `pd_neo_failure_to_hermes.py`, `pd_neo_cron_failure_alert.py`).

For PD One/OpenClaw legacy scripts that send Mattermost/Discord failure alerts but do not emit a federation event, preserve the primary human alert and add a secondary `pd-one.incident`/`pd-one.failure` event via `pd_one_federation_bridge.emit_pd_one_event`. For PD Neo/Hermes scripts, use the PD Neo bridge instead.

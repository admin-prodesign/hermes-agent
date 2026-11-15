# PD One federation alert wiring pattern

Use this when wiring an existing PD One recurring monitor, watchdog, scanner, or wrapper into the PD One → PD Neo/Hermes federation bridge.

## Hermes migration note

PD One's active policy/runtime authority is the Hermes `pdone` profile. OpenClaw paths in this reference are legacy/migration implementation paths or historical compatibility labels unless a live inspection proves an active dependency. When reporting to Andy/admin, say "PD One/Hermes" for the active control plane and explicitly label any OpenClaw path as legacy/reference/archive.

If a wiring task uncovers active-policy keys or status fields still named for OpenClaw, rename them to PD One/Hermes terms and regenerate derived policy/cache artifacts. The cleanup precedent is `openclaw-health-readonly` → `pd-one-host-health-readonly` and `openclawStatus` → `pdOneHostStatus`.

## Canonical bridge

- Primary bridge script: `/home/prodesign/.openclaw/workspace/tools/pd_one_failure_to_hermes.py`
- Lightweight helper used by Python callers: `/home/prodesign/.openclaw/workspace/tools/pd_one_federation_bridge.py`
- Hermes route: `pd-one-failure-autofix`
- Fallback queue when webhook delivery is unavailable: `/home/prodesign/.hermes/pd-one-failure-alerts/queue.jsonl`

## Core rule

Preserve the existing primary alert or user-facing behavior first. Add federation as a secondary, admin-only, best-effort event for actionable system failures. Do not reroute normal employee reminders, approvals, specialist handoffs, or employee-facing requests through the failure bridge.

## Status and reverse-rail helpers

- Live status check: `cd /home/prodesign/.openclaw/workspace && python3 tools/pd_one_federation_status.py --include-cron`
  - Checks webhook `/health`, the `pd-one-failure-autofix` event allowlist, fallback queue/processing files, reverse handoff queue, and the active queue-worker cron named `PD One failure alert queue worker`.
  - Do not hard-code the queue-worker cron job id in status checks; recreated Hermes cron jobs receive new ids.
  - Hermes CLI cron currently has no `--json` option; parse `hermes cron list` text or use the tool API when available.
- Reverse PD Neo → PD One digest: `cd /home/prodesign/.openclaw/workspace && python3 tools/pd_neo_reverse_handoff_digest.py`
  - Default is read-only. `--consume` archives the current queue after admin review only; it does not post employee-facing messages or execute recommendations.
- Reverse queue path: `/home/prodesign/.openclaw/workspace/data/cross-agent/pd-neo-to-pd-one/queue.jsonl`

## Python caller pattern

Prefer importing the helper from the same tools directory:

```python
from pd_one_federation_bridge import emit_pd_one_event

# after the primary alert/report/log path runs
emit_pd_one_event(
    source="source-name",
    summary="Short actionable summary",
    detail=message_or_bounded_json,
    event_type="pd-one.runtime_health",  # or pd-one.incident/failure/attachment_failure/capability_gap
    severity="error",
    command="tools/source_script.py",
    what_was_tried=["Primary Discord/Mattermost alert path executed before secondary federation event."],
    dry_run=args.dry_run,  # when the caller has dry-run mode
)
```

The helper must not make the original job fail only because Hermes/PD Neo is unavailable. The bridge itself should queue when webhook delivery is unavailable; callers should log bridge non-zero output as secondary evidence only.

## Where to emit

- Watchdogs/monitors that already decide an alert is warranted: emit immediately after the primary alert send.
- Retry-until-deadline senders: suppress secondary federation during ordinary retries; emit only on the final exhausted attempt or when the primary failure alert path has already fired.
- Scanners with an existing cron wrapper but no primary alert: catch exceptions around the scanner body, emit a bounded failure event, then re-raise so systemd/cron still sees the failure.
- Shell wrappers around noisy/frequent jobs: preserve the core command exit status, then call a small Python threshold helper with the captured `rc`; the helper should keep consecutive-failure state, alert only after a threshold/cooldown, and return `0` so wrapper alerting cannot mask the real job result.
- Replay/recovery tools: emit on missing prerequisites, replay errors, or crashes; keep normal empty/success scans silent.
- Work/manual/content watchers: use federation for watcher failures, ambiguous/mass changes, or capability gaps; keep normal employee/content notifications on the existing rails.

## Threshold helper pattern for shell wrappers

When a shell wrapper only logs and exits, add a companion helper instead of embedding complex alert logic in bash:

```bash
flock -n "$LOCK_FILE" python3 "$ROOT/tools/job.py"
rc=$?
echo "[$(date -Is)] end job rc=$rc"
python3 "$ROOT/tools/job_failure_alert.py" --rc "$rc" || true
exit "$rc"
```

The helper should:
- reset `consecutive_failures` on `rc == 0` and optionally record `last_recovered_at_utc`;
- increment failures on nonzero rc and store `last_failure_at_utc`, `last_rc`, and `log_path`;
- alert only when `failures >= threshold` and the cooldown has elapsed;
- include a bounded log tail in `detail`;
- support `--dry-run` and call `emit_pd_one_event(..., dry_run=args.dry_run)`;
- never mutate durable state in dry-run mode.

## Event type guidance

The live `pd-one-failure-autofix` route should allow all current PD One federation event types; if a live smoke returns HTTP 200 with `{"status":"ignored"}`, inspect `/home/prodesign/.hermes/webhook_subscriptions.json` for a stale `events` allowlist before debugging the bridge. Current expected events:

- `pd-one.runtime_health`: OpenClaw/system health, slowness, resource pressure, stuck runtime.
- `pd-one.incident`: failed cron/systemd units, missed-reply replayer failures, high-impact automation failure.
- `pd-one.failure`: general deterministic tool/script failure.
- `pd-one.attachment_failure`: Mattermost attachment/review-log scanner failure.
- `pd-one.capability_gap`: watcher found a gap that needs admin review rather than immediate runtime repair.
- `pd-one.knowledge_candidate`: stable operational learning that may need promotion into skills/runbooks/wiki/glossary/policies.

Do **not** invent narrow custom event types such as `pd-one.project-list.mapping_issue` unless the route allowlist is updated and smoked at the same time. For workflow-specific gaps, keep the event taxonomy broad and put the workflow-specific detail in `source`, `summary`, `detail`, `what_was_tried`, and `idempotency_key`. Example: unresolved Project List responsible-person → Mattermost mappings should be emitted as `pd-one.capability_gap` (or `pd-one.failure` if the sender could not complete a required alert/action), with detail listing the unmapped names and candidate-search results.

Treat `{"status":"ignored"}` as a delivery miss, not a success, even when the HTTP status is 2xx. Bridges/wrappers should log or queue ignored events so PD Neo/admin can see that a federation handoff was attempted but not accepted by the route.

## Verification checklist

Run syntax and dry-run checks without sending real employee-facing messages when possible:

```bash
cd /home/prodesign/.openclaw/workspace
python3 -m py_compile \
  tools/pd_one_federation_bridge.py \
  tools/pd_one_failure_to_hermes.py \
  tools/<changed-script>.py
python3 tools/pd_one_failure_to_hermes.py \
  --source federation-wiring-smoke \
  --summary "dry-run smoke" \
  --event-type pd-one.runtime_health \
  --detail "smoke" \
  --dry-run | python3 -m json.tool >/dev/null
git diff --check -- tools/pd_one_federation_bridge.py tools/<changed-script>.py
```

For broad batches, also run import checks with `importlib.util.spec_from_file_location` after adding `/home/prodesign/.openclaw/workspace/tools` to `sys.path`; this catches missing imports without running each script's main body.

Do not blindly validate every Python script with `--help`: some older PD One scripts do not use argparse/help guards and may execute the real job or hang. First inspect whether the script defines argparse/help behavior; otherwise prefer `py_compile`, import-only checks, targeted dry-run/self-test modes, or a purpose-built helper dry-run.

For shell wrappers, verify with `bash -n` and, if you added a companion threshold helper, unit-test the helper by temporarily overriding its state/log paths in an import-only harness so you can force the threshold without touching production state. When using the shared `/home/prodesign/.hermes/scripts/pd_one_cron_failure_alert.py` helper, a safe dry-run probe is:

```bash
python3 /home/prodesign/.hermes/scripts/pd_one_cron_failure_alert.py \
  --source verify-dry-run \
  --rc 1 \
  --summary 'verify dry run' \
  --command verify \
  --threshold 1 \
  --cooldown-seconds 0 \
  --dry-run >/tmp/pd-one-cron-helper-verify.out
```

The shared helper defaults should stay conservative: threshold `2`, cooldown `3600s`, success resets consecutive-failure state under `/home/prodesign/.hermes/state/pd-one-cron-failure-alerts/`.

For specific PD One monitors, prefer their existing dry-run/self-test modes:

- `python3 tools/pd_one_missed_reply_replayer.py self-test`
- `python3 tools/automation_self_heal_monitor.py --dry-run --report --no-send`
- `python3 tools/openclaw_slowness_watchdog.py --dry-run --force-alert --cooldown-seconds 0 --consecutive-alert-runs 1 --min-alert-seconds 0`
- `python3 tools/system_health_monitor.py --dry-run --force-alert`
- `python3 tools/work_manual_watcher.py --dry-run --process-notifications-only`

Use targeted `git diff --check -- <touched files>` in dirty OpenClaw workspaces; broad `git diff --check` may report unrelated generated-file whitespace.

## Work Manual Bot heartbeat routing

For `projects/mattermost-work-manual-bot/integrations/mattermost-interactive/bot.py`, do not post internal heartbeat errors into the employee-facing Work Manual Mattermost channel. Route non-transient heartbeat failures to the PD Neo admin alert Discord channel (`1503946606985216090`) and also emit a secondary `pd-one.runtime_health` event through `emit_pd_one_event(...)` for guarded auto-repair. Keep normal employee request/preview/confirm replies in Mattermost.

Classify short-lived Mattermost/API transport failures as transient and local-log-only before escalating. In addition to ordinary DNS/timeout/refused/reset errors, include these urllib/SSL variants in the transient set: `Remote end closed connection without response`, `IncompleteRead` / `incomplete read`, `UNEXPECTED_EOF_WHILE_READING`, `EOF occurred in violation of protocol`, `SSL: unexpected EOF`, and `broken pipe`.

Verification pattern for this bot after heartbeat-routing changes:

```bash
cd /home/prodesign/.openclaw/workspace
python3 -m py_compile \
  projects/mattermost-work-manual-bot/integrations/mattermost-interactive/bot.py \
  tools/pd_one_federation_bridge.py \
  tools/pd_one_failure_to_hermes.py
python3 - <<'PY'
import importlib.util, os
from pathlib import Path
os.environ.setdefault('MATTERMOST_URL','https://mattermost.prodesign-group.com')
os.environ.setdefault('MATTERMOST_TOKEN_WORK_MANUAL_BOT','dummy')
os.environ.setdefault('MATTERMOST_CHANNEL_ID_WORK_MANUAL','dummy-channel')
os.environ.setdefault('MATTERMOST_WORKSPACE_ROOT','/home/prodesign/.openclaw/workspace')
os.environ.setdefault('DISCORD_BOT_TOKEN','dummy')
path=Path('/home/prodesign/.openclaw/workspace/projects/mattermost-work-manual-bot/integrations/mattermost-interactive/bot.py')
spec=importlib.util.spec_from_file_location('wm_bot', path)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class E(Exception): pass
assert all(mod.is_transient_network_error(E(s)) for s in [
  'Remote end closed connection without response',
  'IncompleteRead(0 bytes read)',
  '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol',
  'broken pipe',
])
PY
```

If a live code change is deployed, restart only the `pd-one-mattermost-work-manual-bot.service` user service, then verify `systemctl --user is-active ...` and recent journal/log tail. This is not an OpenClaw gateway restart.

## Backup/receipt

When durable OpenClaw files change and a remote backup exists, commit only the touched files and push. Include the commit hash in the user-facing receipt. Leave unrelated dirty/generated files alone.

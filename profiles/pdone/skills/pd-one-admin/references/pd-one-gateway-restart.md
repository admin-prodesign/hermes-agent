# PD One / PD Neo gateway restart and config reload notes

Use when Andy has explicitly approved restarting a Hermes/PD One/PD Neo/OpenClaw gateway for the current situation, especially after plugin/config changes or runtime updates. Do not treat code/config edits, prior general approval, or a desire to deploy as implied restart permission; a restart can kill or orphan in-progress admin/background tasks, in-process completion watchers, and live user work.

Exception: Andy permits Hermes/PD Neo/PD One gateway restarts without asking first only when bounded checks show the gateway is already unresponsive. In that case, collect concise evidence of unresponsiveness first, use this runbook's bounded restart pattern, verify recovery afterward, and report what happened. This exception does not authorize restarts for routine deploy/reload convenience while the gateway is still responsive.

## Hermes profile gateway restart pattern

Use this for the active Hermes gateways, not the legacy OpenClaw gateway:

- **PD Neo/default Hermes profile**: `hermes-gateway.service`, `HERMES_HOME=/home/prodesign/.hermes`, state file `/home/prodesign/.hermes/gateway_state.json`, normal webhook health `http://127.0.0.1:8644/health`.
- **PD One/pdone profile**: `hermes-gateway-pdone.service`, `HERMES_HOME=/home/prodesign/.hermes/profiles/pdone`, state file `/home/prodesign/.hermes/profiles/pdone/gateway_state.json`, normal LINE listener/health surface on `:8646` plus platform state in the JSON file.

Before restart, capture the old PID and current state. After approved restart, verify a **new PID**, `systemd` active/running, process `cwd`/`HERMES_HOME`, profile state JSON, expected listener, and platform connection states. The state file may temporarily show `gateway_state: starting` or a platform `connecting` even after `systemctl restart` returns; keep polling until `gateway_state: running` and required platforms are connected, or until a bounded timeout produces actionable logs.

From inside the live PD One gateway, `systemctl --user restart hermes-gateway-pdone.service` and `hermes gateway restart` are blocked by the self-restart guard, and a child of that unit is killed with it. After Andy explicitly asks for this restart, issue it on the user bus and start any receipt watcher with `systemd-run --user` so it is outside the gateway cgroup:

```bash
busctl --user call org.freedesktop.systemd1 /org/freedesktop/systemd1 \
  org.freedesktop.systemd1.Manager RestartUnit ss hermes-gateway-pdone.service replace
```

Do not ask Andy to run that `systemctl` command himself. PD One's steady `gateway_state` can stay `degraded` when Telegram or Discord have no token; success is a new PID, `active/running`, Mattermost connected, and LINE connected. If the old main process hangs in `deactivating`, `KillUnit … main 9` can force systemd to continue its configured restart path.

Example bounded Hermes restart/verification skeleton:

```bash
SERVICE=hermes-gateway.service                 # or hermes-gateway-pdone.service
STATE=/home/prodesign/.hermes/gateway_state.json # adjust for pdone
HEALTH=http://127.0.0.1:8644/health             # omit/adjust if not applicable

systemctl --user show "$SERVICE" -p MainPID -p ActiveState -p SubState -p ExecMainStartTimestamp --no-pager
OLD_PID=$(systemctl --user show "$SERVICE" -p MainPID --value)
systemctl --user restart "$SERVICE"

for i in $(seq 1 90); do
  PID=$(systemctl --user show "$SERVICE" -p MainPID --value)
  ACTIVE=$(systemctl --user is-active "$SERVICE" || true)
  python3 -m json.tool "$STATE" >/tmp/gateway_state.pretty 2>/dev/null || true
  curl -fsS --max-time 2 "$HEALTH" || true
  [ "$ACTIVE" = active ] && [ "$PID" != "$OLD_PID" ] && grep -q '"gateway_state": "running"' /tmp/gateway_state.pretty && break
  sleep 2
done

systemctl --user status "$SERVICE" --no-pager -n 40
python3 -m json.tool "$STATE"
```

Report concise receipts: old/new PID, start timestamp, `gateway_state`, health JSON if applicable, listener, active agents, and per-platform states. Non-blocking Discord voice-library warnings (`PyNaCl`/`davey` not installed) are not a failed chat gateway restart if Discord connects and text routes are healthy.

## Pre-restart checks

1. Load `pd-one-admin` and read the OpenClaw guardrails (`AGENTS.md`, core rules, and relevant runbook).
2. Validate config before restart:

```bash
cd /home/prodesign/.openclaw/workspace
/home/prodesign/.npm-global/bin/openclaw config validate --json
python3 -m json.tool /home/prodesign/.openclaw/openclaw.json >/dev/null
```

3. If validation fails, fix the config before restarting. Recent pitfall: plugin configs can reject additional keys even if the plugin code can use defaults. Logs show this as:

```text
[reload] config reload skipped (invalid config): plugins.entries.<plugin>.config: invalid config: must NOT have additional properties
```

For the admin-approval plugins, `adminChannelId` and `approvalLedgerPath` are defaults in code; do not add unsupported config keys unless schema allows them.

## Preferred restart pattern after explicit approval

Avoid foreground `openclaw gateway restart` from inside a live agent turn. A plain `systemctl --user restart ...` may block in the tool call and hide progress. If systemd restart blocks or appears to have no effect, use a bounded external-supervisor pattern:

```bash
OLD_PID=$(systemctl --user show openclaw-gateway.service -p MainPID --value)
echo "old_pid=$OLD_PID"
systemctl --user kill -s SIGTERM openclaw-gateway.service
for i in $(seq 1 30); do
  sleep 2
  PID=$(systemctl --user show openclaw-gateway.service -p MainPID --value)
  STATE=$(systemctl --user is-active openclaw-gateway.service || true)
  echo "check=$i state=$STATE pid=$PID"
  if [ "$STATE" = active ] && [ -n "$PID" ] && [ "$PID" != "$OLD_PID" ]; then
    systemctl --user show openclaw-gateway.service -p ActiveState -p SubState -p MainPID -p ExecMainStartTimestamp --no-pager
    exit 0
  fi
done
exit 3
```

This relies on the service's `Restart=always` behavior and produced a clean shutdown/restart in the observed case. If bounded SIGTERM polling leaves the same PID running after several checks, re-check current state/PID, then use a bounded `systemctl --user restart openclaw-gateway.service` and poll for a new PID rather than leaving the restart half-finished. Always verify by new PID plus journal readiness afterward.

## Codex app-server closed / event-loop starvation before restart

If the incident is `codex app-server client is closed`, repeated Codex startup retries, stalled embedded runs, or Mattermost replies failing before an embedded response, first load `references/codex-app-server-closed-triage.md`. Treat the error as a Codex app-server lifecycle symptom and correlate it with liveness warnings, stalled sessions, OOM/memory peaks, and concurrent scheduled jobs before considering restart. The usual restart exception still applies only when bounded checks show the gateway is actually unresponsive.

## Verification

After restart, verify all three layers:

```bash
systemctl --user show openclaw-gateway.service -p ActiveState -p SubState -p MainPID -p ExecMainStartTimestamp --no-pager
journalctl --user -u openclaw-gateway.service --since '5 minutes ago' --no-pager | grep -E 'ready|connected as|invalid config|reload|error|timeout|warning' | sed -n '1,120p'
/home/prodesign/.npm-global/bin/openclaw health --json
```

Success indicators:

- New `MainPID` compared with pre-restart PID.
- Journal shows `[gateway] ready`.
- Mattermost shows `connected as @pdone`.
- `openclaw health --json` returns `ok: true` and channels are `running`/`connected`.

For code/hotfix deploy restarts, add a fourth verification layer: prove the active installed runtime contains the expected code markers. PD One often runs from `/home/prodesign/.npm-global/lib/node_modules/openclaw/dist/index.js`, not directly from the source checkout. A pushed source commit alone is not proof of live behavior. Check the relevant `dist/channel.runtime-*.js` bundle for patch markers (for example Mattermost attachment grounding markers) and, when the fix depends on Mattermost thread files, probe the Mattermost REST thread endpoint to confirm the expected unique `file_ids` are visible. If a websocket reconnect appears after restart, wait briefly and re-check; if reconnect loops continue while health is live, a second bounded restart may be justified, but report it with the final PID and journal evidence.

Startup may show transient event-loop delay, Discord fetch timeout, model warmup timeout, or RPC probe timeouts while embedded Codex/model runs are active. Treat those as warnings to monitor, not automatic restart failure, if the gateway is ready, systemd is active, config is valid, and Mattermost/Discord are connected. Prefer a bounded direct health call such as `timeout 20 openclaw gateway call health --json` plus journal/systemd corroboration; do not restart-loop solely because `openclaw health --json` or `openclaw gateway status --require-rpc` times out under live event-loop pressure.

## Scheduled update + restart maintenance

When Andy asks to run an OpenClaw/PD One update at a later time and restart the gateway:

- Treat the request as approval for that bounded maintenance window, but still make the schedule machine-verifiable: job ID, exact timezone, script path, log path, and status path.
- Use a wrapper with `flock`, bounded timeouts, pre/post backup, explicit service restart, health verification, and a final status file. The wrapper must be safe to re-run: if the target version is already installed, skip reinstall and proceed only with the approved restart/verification.
- Be careful when validating the wrapper: do not run it with a fake `--help`/dummy arg unless the script explicitly handles that mode before side effects. Use `bash -n`, file mode checks, and code inspection instead.
- If an update command uses `--no-restart` while the managed gateway is running, the CLI package can still update while the old gateway process keeps serving the previous version until restart. Verify both CLI version and the post-restart service/journal/health state.
- If validation accidentally starts the maintenance early, do not hide it: stop any leftover transient update unit only if safe, verify current version/service/channels, make the later scheduled job idempotent, and report the early side effect plus current evidence clearly.

## Commit discipline

If restart work required durable config fixes, commit and push the OpenClaw backup. If Hermes skill/docs are updated, also commit/push Hermes backup according to user preference.

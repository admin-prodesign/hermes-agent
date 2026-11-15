# PD One admin migration playbook

Use this reference when continuing the migration where Hermes/PD Neo administers `nemo` and the PD One/OpenClaw runtime while OpenClaw keeps employee-facing and company-facing agent duties.

## Boundary

- Hermes/PD Neo administers the machine and supervises OpenClaw from outside the OpenClaw runtime.
- OpenClaw/PD One remains the Mattermost/company-facing interface and should continue serving employee-assistant and department agents.
- Do not migrate, copy, or compete for OpenClaw messaging/channel/gateway settings, bot tokens, provider secrets, `.env*`, runtime logs, bot state, browser profiles, or transport config unless Andy explicitly asks.
- Never restart the OpenClaw gateway without explicit Andy approval first; treat restarts as potentially disruptive because they can kill or orphan in-progress admin/background tasks, in-process completion watchers, and live user work.

## Standard opening sequence

1. Load `pd-one-admin`.
2. Inspect OpenClaw source-of-truth files relevant to the task, at minimum:
   - `/home/prodesign/.openclaw/workspace/AGENTS.md`
   - `/home/prodesign/.openclaw/workspace/docs/agent-rules/core-operating-rules.md`
   - `TOOLS.md` and any domain runbook/skill touched by the task.
3. If Hermes Agent configuration/code is being changed, also load `hermes-agent` and follow its dev/config workflow.
4. Prefer bounded deterministic probes over broad live-runtime diagnostics.

## Safe live-health pattern

Prefer the bundled bounded probe script from this skill. It wraps the safe checks below, redacts common secrets, and avoids broad status/log sweeps or restarts:

```bash
python3 /home/prodesign/.hermes/skills/pd-one/pd-one-admin/scripts/pd_one_bounded_probe.py
python3 /home/prodesign/.hermes/skills/pd-one/pd-one-admin/scripts/pd_one_bounded_probe.py --triage --backup-status
python3 /home/prodesign/.hermes/skills/pd-one/pd-one-admin/scripts/pd_one_bounded_probe.py --logs --log-limit 120 --log-max-bytes 120000
```

Use OpenClaw health rather than broad status/log sweeps during normal chat paths:

```bash
cd /home/prodesign/.openclaw/workspace
/home/prodesign/.npm-global/bin/openclaw health --json > /tmp/openclaw-health.json
```

If health reports event-loop/cpu/memory/disk pressure, do safe triage before alerting or suggesting remediation:

```bash
uptime
ps -eo pid,ppid,comm,%cpu,%mem,etime,args --sort=-%cpu | head -12
ps -eo pid,ppid,comm,%cpu,%mem,rss,etime,args --sort=-%mem | head -12
df -h / /home /tmp 2>/dev/null
for f in /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io; do echo "-- $f"; cat "$f"; done
```

Report cause/risk succinctly. Ask before killing processes, destructive cleanup, service restarts, OpenClaw gateway restarts, or permission expansion.

## Approved gateway restart pattern

Only after Andy explicitly approves an OpenClaw/PD One gateway restart, follow `references/pd-one-gateway-restart.md`. Key lessons:

- Validate `/home/prodesign/.openclaw/openclaw.json` first with `openclaw config validate --json`; do not restart into a known invalid config.
- Treat `config reload skipped (invalid config)` as a config/schema problem to fix before restart, not as a reason to repeatedly restart.
- Prefer an external-supervisor systemd flow over foreground `openclaw gateway restart` from inside a live agent turn. If `systemctl --user restart` blocks or no new PID appears, send SIGTERM to the service main process and let `Restart=always` bring it back, then verify the new PID.
- Verify success by new `MainPID`, journal `[gateway] ready`, Mattermost `connected as @pdone`, and `openclaw health --json` with connected channels.

## Change/commit discipline

- Treat `/home/prodesign/.openclaw/` as live runtime state. Edit only on explicit scope.
- If durable OpenClaw docs/config are changed, update relevant documentation and push the OpenClaw backup per OpenClaw rules.
- If durable Hermes files are changed for this user, commit/push through the Hermes backup or relevant git remote when configured.
- Keep final admin reports explicit about what changed, what was only inspected, whether any gateway/runtime restart was avoided or still required, and whether alert delivery targets were verified when alerts are part of the task.
- PD One/Hermes alert destinations default to Discord channel `1503946606985216090` unless Andy explicitly requests otherwise. Hermes cron uses `deliver: discord:1503946606985216090`; OpenClaw CLI Discord sends should use `--target channel:1503946606985216090` to avoid bare-ID ambiguity.

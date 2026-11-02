# Codex app-server `client is closed` triage for PD One/OpenClaw

Use when PD One/OpenClaw logs show `codex app-server client is closed`, `codex app-server connection closed during startup`, or Mattermost/Telegram replies fail before an embedded agent response.

## Interpretation

Treat `codex app-server client is closed` as a symptom, not a root cause. In observed PD One incidents it meant the Codex app-server child process / stdio connection closed while OpenClaw was starting or resuming a Codex harness turn. The actionable root-cause search is around why Codex closed and why the gateway could not recover cleanly.

## High-signal evidence to collect

Use bounded read-only checks before restart/reconfiguration:

```bash
# Narrow the incident window first; adjust timestamps.
journalctl --user -u openclaw-gateway.service \
  --since 'YYYY-MM-DD HH:MM:SS UTC' --until 'YYYY-MM-DD HH:MM:SS UTC' --no-pager \
  | grep -Ei 'codex|app-server|harness|cleanup|startup|timed out|timeout|closed|idle|turn|thread|liveness|memory|diagnostic|stalled|long-running|queue|delivered|failed|error' \
  | sed -n '1,260p'

# Include system/user-unit pressure signals around the same window.
journalctl --since 'YYYY-MM-DD HH:MM:SS UTC' --until 'YYYY-MM-DD HH:MM:SS UTC' --no-pager \
  | grep -Ei 'oom|out of memory|killed process|openclaw|hermes|memory peak|swap peak|codex|node\[' \
  | sed -n '1,220p'

# Current live state.
systemctl --user show openclaw-gateway.service -p ActiveState -p SubState -p MainPID -p ExecMainStartTimestamp --no-pager
/home/prodesign/.npm-global/bin/openclaw health --json
ps -eo pid,ppid,lstart,etimes,pmem,rss,cmd --sort=-rss | grep -E 'codex|openclaw|node|app-server' | head -40
free -h; df -h / /home | sed -n '1,5p'
```

Do not print environment variables or auth profile contents. Redact tokens/secrets from any copied output.

## Diagnostic pattern from the May 2026 incident

Observed chain:

1. Multiple embedded agent runs started close together using the Codex harness (`openai-codex/gpt-*`).
2. One or more runs stalled after Codex progress notifications such as `item/completed`, `rawResponseItem/completed`, or `turn/completed` without terminal completion.
3. Gateway liveness warnings showed event-loop starvation and CPU saturation: P99 event-loop delay in multi-second range, eventLoopUtilization near `1`, and delayed timers/fetches.
4. System/user-unit logs showed memory pressure/OOM or high memory/swap peaks from OpenClaw/Hermes/adjacent scheduled jobs.
5. New Codex harness startups repeatedly logged:
   - `codex app-server connection closed during startup; restarting app-server and retrying`
   - then `retries exhausted`
   - then lane errors / `Embedded agent failed before reply: codex app-server client is closed`.
6. Mattermost was usually the victim, not the root cause: messages during the stall window lacked later bot replies because embedded agent runs died before producing responses.

## Source-code anchors

In the built OpenClaw package, useful anchors were:

- `dist/run-attempt-*.js`: `CODEX_APP_SERVER_STARTUP_CONNECTION_CLOSE_MAX_ATTEMPTS = 3`; startup retry loop; `isCodexAppServerConnectionClosedError`; `agent cleanup timed out` around `codex-trajectory-flush-startup-failure`.
- `dist/shared-client-*.js`: shared Codex app-server client lifecycle, `getSharedCodexAppServerClient`, `createIsolatedCodexAppServerClient`, and `clearSharedCodexAppServerClientIfCurrent`.
- `dist/client-*.js`: throws the literal `codex app-server client is closed` when a request is made against a closed client/transport.

These generated filenames change between builds; search by symbols/log strings instead of hardcoding exact chunk names.

## Triage conclusions to report

Good concise answer shape:

- Current status: gateway active/health/Mattermost connected or not.
- Whether this is a direct Mattermost issue: usually no, unless channel connection is also unhealthy.
- Root-cause confidence: `client is closed` = Codex app-server lifecycle failure; likely drivers are concurrent stalled Codex runs plus event-loop/resource pressure unless logs show an auth/config/binary error.
- Impact window and missed messages: use `references/mattermost-missed-message-catchup.md` if Mattermost replies were lost.
- Restart decision: only restart without asking if bounded checks show the gateway is actually unresponsive; otherwise gather evidence and avoid restart loops.

## Remediation options

Prefer low-risk mitigations first:

- Reduce overlapping PD One/Hermes scheduled jobs during busy windows; inspect timers/services that run near incident time.
- If repeated after recovery, consider temporarily routing some PD One agents away from Codex or limiting concurrent Codex harness runs, following `references/pd-one-agent-model-routing.md`.
- Check installed Codex CLI/OpenClaw versions against upstream only as a hypothesis; do not present an update as root cause unless changelog/repro confirms it.
- PD One custom branch `admin-prodesign/openclaw` `pd-one/custom-openclaw-patches` includes `scripts/pd-one-hotpatch-codex-self-heal.mjs`, which idempotently hot-patches the installed `dist/run-attempt-*.js` to recycle all shared Codex app-server clients after startup connection-close failures before retrying. It also repairs the optional `openclaw` peer symlink under `~/.openclaw/npm/node_modules/` needed by the installed `@openclaw/codex` plugin. After applying it, restart `openclaw-gateway.service` and run an `openclaw agent --agent utility-agent ... --json` smoke that expects a fixed reply.
- If the hotpatch stabilizes production, treat it as an upstream candidate but do **not** PR the PD One script as-is. Create a fresh branch from upstream `origin/main`, reimplement the recovery in OpenClaw source (not generated `dist` chunks and not `/home/prodesign` paths), add focused tests, and describe the PD One incident evidence/smoke result in the PR. Keep the symlink/installed-plugin repair as downstream remediation unless upstream packaging/loader analysis proves a portable fix.
- After any source/config change, preserve downstream OpenClaw custom patches and backup/commit per PD One conventions.

# PD One durable-file size watchdog

Use this reference when Andy asks to keep PD One/OpenClaw durable/bootstrap files under injection limits, or when reviewing whether `MEMORY.md`, `USER.md`, `AGENTS.md`, `TOOLS.md`, etc. are close to truncation.

## Why it exists

OpenClaw bootstrap injection has a per-file character guardrail (`bootstrapMaxChars` defaults to about 12,000 chars). If a durable file grows past the limit, instructions can be truncated and PD One may behave incorrectly. The watcher should catch growth before the hard limit.

## Current implementation pattern

- Deterministic no-agent Hermes cron job, silent on OK.
- Script lives in `~/.hermes/scripts/`; Hermes cron `script` values must be relative filenames, not absolute paths.
- Scans PD One OpenClaw workspace roots under `/home/prodesign/.openclaw/workspace*`, plus nested `/home/prodesign/.openclaw/workspace/main` when present.
- Uses the config at `/home/prodesign/.openclaw/workspace/tools/durable_file_size_check.config.json` for durable filenames and limits.
- Include at minimum:
  - `AGENTS.md`
  - `SOUL.md`
  - `IDENTITY.md`
  - `USER.md`
  - `TOOLS.md`
  - `HEARTBEAT.md`
  - `MEMORY.md`
- Warn at 90% of per-file limit and per-workspace aggregate limit; alert only on warning/critical.
- Store state under `/home/prodesign/.openclaw/workspace/memory/` and JSONL run evidence under `/home/prodesign/.openclaw/workspace/logs/`.
- Suppress duplicate identical alerts for a bounded window (currently 12h) to avoid noisy repeated posts.

## Verification checklist

1. Run a baseline manually:
   ```bash
   /home/prodesign/.hermes/scripts/pd-one-durable-file-size-watchdog.py --baseline
   ```
2. Expected healthy output is an `OK:` line with file count, workspace-root count, aggregate chars, and largest files.
3. Create/run the Hermes cron as no-agent, using only the script filename. Route PD One/Hermes alert output to Andy's shared alert Discord channel unless the request explicitly names a different destination:
   ```text
   script: pd-one-durable-file-size-watchdog.py
   no_agent: true
   deliver: discord:1503946606985216090
   schedule: every 6h
   ```
4. Manually run the cron once and verify the output record says `silent (empty output)` when healthy.
5. Read back state/log evidence:
   - `/home/prodesign/.openclaw/workspace/memory/durable-file-size-watchdog-state.json`
   - `/home/prodesign/.openclaw/workspace/logs/durable-file-size-watchdog.jsonl`
6. Backup both sides narrowly:
   - Commit/push any OpenClaw config change in `/home/prodesign/.openclaw`.
   - Run `/home/prodesign/hermes-backup/scripts/commit-hermes-backup.sh` for the Hermes cron/script state.

## Pitfalls

- Do not only check the main `workspace/MEMORY.md`; department workspaces and nested `workspace/main` also inject durable files.
- Do not leave `MEMORY.md` out of the durable-file checker config; it is often the file most likely to approach the limit.
- Avoid alerting every healthy run. For this class of monitor, no-agent + silent-on-OK is preferred.
- A cron creation failure caused by an absolute script path is a Hermes cron input-shape issue, not a script failure: place the script under `~/.hermes/scripts/` and pass only the filename.
- Alerts from this watcher are PD One/Hermes alerts; deliver them to Discord channel `1503946606985216090` by default, not to the originating thread.
- Do not commit broad dirty OpenClaw runtime/wiki changes just because the watcher config changed; stage and commit the narrow config diff only.

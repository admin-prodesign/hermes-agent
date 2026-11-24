# OpenClaw-managed Codex `logs_2.sqlite` retention

Use this reference when root disk pressure is caused by OpenClaw/Codex app-server diagnostic SQLite logs under:

```text
/home/prodesign/.openclaw/agents/*/agent/codex-home/logs_2.sqlite
```

## Durable findings

- Codex app-server can persist high-volume structured logs into `logs_2.sqlite` and `logs_2.sqlite-wal`; TRACE-heavy rows may continue even when `RUST_LOG=warn` is set, so config alone is not a sufficient disk-safety control.
- The largest payload column is typically `feedback_log_body`; inspect level/target/body-size distribution before deleting.
- Open GitHub issues observed in 2026 describe excessive SQLite/WAL writes and stale Codex processes holding deleted WAL files open. Always check `lsof +L1` when `du` and `df` disagree after deleting or vacuuming logs.
- These DBs are diagnostic/runtime log history, not the canonical OpenClaw operational database. Trimming old rows is usually safer than removing app data, but it does discard debug history.

## Safe cleanup pattern

1. Inspect disk and DBs read-only:
   - `df -h /`
   - DB sizes under `/home/prodesign/.openclaw/agents/*/agent/codex-home/logs_2.sqlite`
   - SQLite `PRAGMA integrity_check` or `quick_check`
   - row counts, min/max `ts`, level counts, largest targets, and `SUM(LENGTH(feedback_log_body))`
2. For each DB, delete rows older than a bounded retention window, e.g. 24h:
   - `DELETE FROM logs WHERE ts < ?`
   - `PRAGMA wal_checkpoint(TRUNCATE)`
   - `VACUUM`
3. Verify:
   - DB sizes dropped
   - row min/max timestamps are within retention expectations
   - `df -h /` improved
   - `lsof -nP +L1` has no large deleted `logs_2.sqlite-wal`/`-shm` handles

## Long-term mitigation pattern

Use defense in depth rather than relying on one Codex setting:

- Set `[analytics]\nenabled = false` in each OpenClaw-managed Codex home config when analytics are not intentionally desired.
- Set `RUST_LOG=warn` in the OpenClaw gateway systemd environment for future spawned Codex app-server processes.
- Do not restart a healthy OpenClaw gateway solely to apply logging changes unless the user confirms; otherwise note that the env change applies on the next normal restart.
- Add a silent-on-success retention automation with failure visibility. A good pattern is:
  - Python script performs DB discovery, bounded deletion, selective WAL checkpoint/VACUUM, durable status writing, and nonzero exit on real maintenance failure.
  - Bash wrapper invokes `/usr/bin/python3 /absolute/path/to/script.py`.
  - Hermes no-agent cron uses the `.sh` wrapper, not the `.py` directly, when the scheduler environment may point at a missing project venv.
  - No-agent job should be silent on success and deliver/alert only on nonzero exit.
  - Add a nonblocking `flock` so overlapping hourly runs exit successfully as `already_running` rather than competing for SQLite locks.
  - Keep the script's internal runtime budget below the scheduler timeout. Hermes no-agent cron may kill scripts around 120s, so use an internal deadline around 90–95s and write a status file before exiting.
  - Avoid expensive hourly full-table work on active Codex DBs. `PRAGMA quick_check`, `COUNT(*)`, `wal_checkpoint(TRUNCATE)`, and `VACUUM` can push large/active DB maintenance over the scheduler timeout. Prefer an index-backed probe such as `SELECT 1 FROM logs WHERE ts < ? LIMIT 1`; delete only when expired rows exist.
  - Detect active DB/WAL/SHM holders via `/proc` or `lsof`. If a live Codex process has a DB open, skip checkpoint/VACUUM for that DB and let a later idle run compact it.
  - Treat expected `database is locked` / `database is busy` during maintenance as a per-DB skip, not a whole-job failure, unless disk pressure is critical.

## Verification receipt to report

Include these in the user-facing summary:

- reclaimed root disk space and current `%` used
- before/after size for the main offending DB
- whether all agent Codex DBs were bounded
- retention job ID, schedule, script path, and last run status
- whether the gateway was restarted or whether env changes are pending next normal restart
- backup/commit hash if Hermes state backup is expected

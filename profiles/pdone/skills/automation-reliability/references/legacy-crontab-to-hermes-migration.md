# Migrating legacy crontab/systemd automations to Hermes cron

Use when retiring an older scheduler/control-plane executable while preserving existing scheduled operational tools.

## Safe migration pattern

1. Inventory first:
   - Save `crontab -l` to a timestamped profile-local backup.
   - List matching systemd user/system services and timers with `systemctl --user show ...` / `systemctl list-timers`.
   - Search scheduled entrypoint scripts for hard dependencies on the retiring executable, not just path names.
2. Separate **scheduler dependency** from **script-internal dependency**:
   - Moving a crontab entry into Hermes cron removes the user crontab scheduler dependency.
   - It does **not** remove internal calls such as `openclaw message send`, `openclaw agent`, or `shutil.which("openclaw")` inside the script.
   - Do not uninstall the old executable until scheduled entrypoints and their transitive scripts no longer require it.
3. For many existing crontab entries, prefer a manifest + runner bridge before hand-creating dozens of one-off Hermes jobs:
   - Store each old cron expression and command in a profile-local JSON manifest.
   - Run a Hermes `no_agent` cron every minute.
   - The runner uses `croniter.match()` to execute only jobs due in the current UTC minute.
   - Preserve existing `flock` locks and `run_with_capped_log.sh` logging in each command.
   - Keep a per-job minute watermark to avoid duplicate runs if the runner overlaps or restarts.
4. For alerting jobs, prefer stdout delivery under Hermes cron:
   - Patch scripts to support an environment flag such as `PD_ONE_HERMES_CRON_STDOUT=1`.
   - When set, print the alert body to stdout and let Hermes cron deliver it.
   - Keep existing federation/queue fallbacks if already present, but avoid calling the retiring CLI for primary sends.
5. Verification:
   - `py_compile` Python runner/scripts.
   - Run the runner once manually; it should exit 0 and either run due jobs or report no due jobs.
   - Read the runner state file to prove due jobs ran and recorded exit codes.
   - Re-list Hermes cron jobs and verify `enabled`, `state`, `next_run_at`, and `last_status` after at least one tick when practical.
   - Re-scan scheduled entrypoint files for retiring-executable invocations before uninstalling anything.
6. Backup:
   - Commit/push the manifest, runner, new Hermes cron definitions, and crontab backups to the configured private backup repo.

## Pitfalls

- A clean user crontab does not prove the old executable is safe to uninstall; migrated scripts may still call it internally for notifications or agent enrichment.
- Logs can contain old matches for the retiring executable; distinguish historical log evidence from live scheduled entrypoint code.
- `deliver=origin` can route failures to the migration thread instead of the owner/admin alert lane. For operational jobs, intentionally choose `local`, `origin`, or a Mattermost target based on alert expectation.
- Do not restart gateways as part of scheduler migration unless a separate approved config/runtime change requires it.

# Retarget a script-only Hermes cron job to rich notifications

Use when an existing no-agent/script-only cron job currently posts non-empty stdout to its origin thread/channel, and an approved admin asks to route future human-visible notifications through the established PD Neo notification helper.

## Pattern

1. **Identify and read back the existing job first**
   - Use the cron job list/readback to confirm the exact job id, name, schedule, `deliver`, `script`, `enabled`, `state`, `next_run_at`, `last_status`, and `last_delivery_error`.
   - Update the existing job in place; do not create a duplicate recurring job for the same purpose.

2. **Preserve the existing business script and guarded failure path**
   - If the current job already runs through a supervisor/guarded wrapper, make the notification wrapper call that wrapper, not the raw business script.
   - This preserves stdout/stderr/exit-code behavior and existing admin-only failure triage.

3. **Create a thin notification wrapper**
   - Keep silent no-op behavior: empty stdout on success means no notification.
   - On non-empty stdout, format it as Markdown if needed and send a routed notification.
   - On nonzero exit, include stdout/stderr tails or a log path, send a routed notification, and return the original exit code.
   - Use the shared rich email helper when available, e.g. `/home/prodesign/.hermes/scripts/pd_neo_notify.py`, invoked via `sys.executable` rather than relying on executable bits.
   - Use stable automation keys and subjects so Discord forum reports remain referable and grouped.

4. **Switch cron delivery to local**
   - Set `deliver='local'` so Hermes does not also post the same stdout back to the old chat thread.
   - Set the cron `script` to the new notification wrapper.
   - Keep the original schedule and repeat settings unless the user asked to change them.

5. **Verify before claiming success**
   - Add a wrapper self-test that runs the notification helper with `--dry-run` only.
   - Verify the dry-run reports the expected Discord forum channel, subject, chunk count, and `discord_forum` route.
   - Re-read the cron job after update and report the exact readback fields.
   - Validate edited JSON/state files with a parser.
   - If the automation registry/supervisor tracks alert expectations, update it with the new notification route.

6. **Backup durable runtime changes**
   - Copy changed profile-local cron/scripts/registry files to the configured private backup repo, commit, and push when this profile uses that convention.
   - Report the commit hash.

## Pitfalls

- Do **not** send a live notification unless the user explicitly approves it; a dry-run proves configuration/formatting without creating an external send.
- Do **not** run the underlying business sync merely to test the notification route if it touches source systems. Use a wrapper self-test/dry-run path.
- Do **not** replace a guarded supervisor wrapper with a raw script call; that silently removes failure triage.
- Do **not** leave `deliver=origin` while also externally delivering non-empty output unless duplicate notifications are explicitly desired.
- Project registry helpers may create a new row if the title differs; prefer the existing stable project id when known to avoid grid-limit or duplicate-row issues.

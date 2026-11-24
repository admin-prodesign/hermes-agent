# PD One monitor chat reminder cleanup

Use this when maintaining PD One monitors/watchdogs that post stale-state reminders into Mattermost or another chat channel.

## Pattern

1. **Make reminders actionable.** User-facing reminders should include a clickable source URL (for example a Google Sheet link), not only an opaque source ID.
2. **Treat reminders as state.** Store posted reminder IDs in monitor state, usually `last_alert_post_id`; use a bounded `alert_post_ids` list if repeated reminders can occur before the condition is resolved.
3. **Clean up on source change.** When the monitor detects new entries or another content change that resets the stale timer, delete previously stored reminder posts where the chat API permits it, clear the stored post IDs, and record `last_cleanup_at_utc` / `last_cleanup_deleted_post_ids` in state. For repeating same-thread reminders (SDS annual renewal), delete only the latest previous bot reminder, and keep it if any non-bot reply landed after that reminder.
4. **Do not conflate no-change and cleanup.** No-change ticks should stay quiet under duplicate suppression. Change ticks may perform cleanup even when no new alert is posted.
5. **Verify before reporting.** Read back the deleted post or platform-equivalent receipt; Mattermost deleted posts commonly read back as `404` through REST.
6. **Update the registry/runbook.** If the monitor is tracked in the Project Registry, touch the project row in the same turn with the code/state paths and cleanup evidence.
7. **For bounded historical bulk cleanup, fail closed.** Match the exact channel, authenticated bot identity, top-level/root shape, title, hidden automation marker, and requested time window; paginate until the cutoff is actually reached; dry-run the complete candidate count; then re-fetch and revalidate every post immediately before deletion. Verify each delete by `404` or `delete_at > 0`, and run the same dry-run again afterward expecting zero candidates. For PDAPP executor-watchdog alerts in PD One Admin, use `/home/prodesign/.hermes/profiles/pdone/scripts/pdapp_watchdog_notification_cleanup.py`; live mode requires its exact confirmation phrase and updates the watchdog state's deleted-delivery receipt without resetting cooldown.

## Mattermost implementation notes

- Use the same bot credentials that created the reminder where possible.
- A cleanup helper should tolerate missing/already-deleted posts as success (`404` is acceptable for readback after deletion).
- Preserve admin approval/write boundaries: deleting bot-generated stale reminders is cleanup of PD One's own channel noise, but still verify exact channel/thread scope and keep evidence concise.

## Example state fields

```json
{
  "last_alert_post_id": null,
  "alert_post_ids": [],
  "last_cleanup_at_utc": "2026-07-09T07:57:58Z",
  "last_cleanup_deleted_post_ids": ["<post_id>"]
}
```

# Editable Mattermost status post monitor pattern

Use this pattern when the user wants PD One/OpenClaw to show online/offline status in Mattermost without spamming channels.

## Shape

- Prefer a deterministic script plus systemd user timer for this class of monitor when the Hermes cron scheduler is not clearly running as a persistent daemon.
- Maintain exactly one Mattermost post and update it via `PUT /api/v4/posts/{post_id}/patch`.
- Store the `post_id`, last status, last healthy check, consecutive failures, and post URL hint in durable JSON state.
- Keep clean runs silent; log every run to JSONL for audit/debugging.

## Checks that worked for PD One

- `systemctl --user is-active openclaw-gateway.service`
- local OpenClaw gateway health endpoint: `http://127.0.0.1:18789/healthz`
- Mattermost API identity check: `GET /api/v4/users/me` with the bot token

## Recommended state/log locations

- Script: `~/.hermes/scripts/<monitor>.py`
- Wrapper: `~/.hermes/scripts/<monitor>.sh`
- State: `~/.hermes/state/<monitor>/state.json`
- Logs: `~/.hermes/logs/<monitor>/runs-YYYYMM.jsonl`
- If using systemd, place active units under `~/.config/systemd/user/` and keep backup copies under `~/.hermes/state/<monitor>/systemd/` so Hermes backup captures them.

## Status thresholds

Avoid false alarms from one transient failure:

- all checks pass: `🟢 online`, reset consecutive failures
- 1-2 failed checks: `🟡 degraded`
- 3+ consecutive failed checks: `🔴 offline`

The monitor should still update the status post every run so the `Last checked` timestamp proves freshness.

## Employee-visible channel/post handling

When the user asks for an employee-visible status panel:

- Put the post in the requested user-facing channel and pin it for quick access.
- Make the status content bilingual if PD One employees will see it: English plus Traditional Chinese, including title, check names, timestamps, failure counts, and maintenance footer.
- Do not try to "move" a Mattermost post between channels. If the configured channel changes, preserve `previous_channel_id`/`previous_post_id`, clear the active `post_id`, create one new post in the new channel, then pin/read back the new post.
- Keep old/admin-lane posts as previous metadata unless the user explicitly asks to unpin/delete them.

## Bot avatar presence dot

The bot icon's online/offline dot is Mattermost user presence, not the same as full PD One health. In current Mattermost webapp builds, bot account presence can be API-visible but UI-hidden.

- Read it with `GET /api/v4/users/{bot_user_id}/status` or discover the bot via `GET /api/v4/users/me` using the bot token.
- Mattermost supports `PUT /api/v4/users/{bot_user_id}/status` with statuses `online`, `away`, `offline`, and `dnd`, but manual non-online states can override automatic activity-based presence until reset to `online`.
- Do not assume setting the status API will make a green/yellow/red circle appear on a bot avatar. The Mattermost web UI may intentionally suppress bot presence indicators by passing empty status/`hideStatus` when `user.is_bot`/`teammate.is_bot` is true, including DM/channel avatar and profile popover surfaces.
- If the user says they do not see a status circle on a bot account, inspect the actual UI/screenshots and, when needed, the deployed webapp bundle/source for `is_bot`, `hideStatus`, and status-avatar rendering before proposing API writes.
- Prefer leaving avatar presence automatic and using the pinned status post as the authoritative health indicator, because native presence mainly proves Mattermost session/WebSocket activity and can be misleading about gateway/model/backend health.
- Only add manual presence automation after explicit approval and after confirming the UI will display it on the target surface. A safe mapping is healthy → `online`, degraded → `away`/`dnd`, offline after threshold → `offline`, with readback verification after every mutation.
- If bot-avatar visibility itself is required, prefer dynamic avatar badging (green/yellow/red overlay) or, less desirably, display-name prefixes (`🟢/🟡/🔴 PD One`) over patching Mattermost or converting the bot into a human/service user. Warn that avatar changes may be client-cached and display-name changes can be noisy in history/mentions.
- Mattermost can also show a bot-specific profile line via the bot account `description` field. The webapp renders this as `bot_description` in the profile popover for bot accounts, while it hides the normal custom-status row when `hideStatus` is true. For PD One, updating `PUT /api/v4/bots/{bot_user_id}` with `{"description": "🟢 Online / 在線 — ..."}` worked and read back through both `/api/v4/bots/{bot_user_id}` (`description`) and `/api/v4/users/me` (`bot_description`). Use this for profile-popover health text rather than custom status.

### Dynamic avatar badging implementation notes

When implementing avatar badging for PD One/Mattermost, avoid generating a new image on every run. Instead:

1. Download the current bot avatar once via `GET /api/v4/users/{bot_user_id}/image` and save it under the monitor state directory, e.g. `~/.hermes/state/<monitor>/avatar/base-current.png`.
2. Create three cached variants from that base avatar, e.g. `pd-one-avatar-online.png`, `pd-one-avatar-degraded.png`, and `pd-one-avatar-offline.png`, using green/yellow/red badge overlays. Use deterministic local image editing such as Pillow; do not spend image-generation tokens for simple status-dot overlays.
3. Patch the existing monitor so it maps the already-computed health status to avatar variants: all checks pass → `online`; 1-2 failed checks → `degraded`; 3+ consecutive failures → `offline`.
4. Upload the selected variant with `POST /api/v4/users/{bot_user_id}/image` as multipart form field `image` only when the status changes or state says the current avatar variant is unknown. Store `avatar_status`, `avatar_path`, and `avatar_updated_tpe` in state so normal 5-minute checks do not re-upload the same avatar.
5. Keep avatar-upload failure non-fatal to the status post update: log a warning and preserve the pinned post as the source of truth. Do not expose the Mattermost token in curl commands, logs, state, or user-facing summaries.
6. Verify by reading back `/api/v4/users/me` for `last_picture_update`, downloading `/api/v4/users/{bot_user_id}/image` to an evidence file, visually checking the badge, and confirming the pinned status post remains in the employee-visible channel.
7. If a manual run accidentally uses the wrong channel default and creates a replacement post in an admin lane, delete that accidental post if safe, restore the canonical `post_id`/`channel_id` in state, and set the script's default channel to the employee-visible channel in addition to any systemd environment override.

### Profile popover status via bot description

The real-user custom-status row is hidden for bot profile popovers in the deployed Mattermost webapp when `hideStatus` is true, and on this instance `/api/v4/users/me/status/custom` returned 404. To show a concise health line in the bot profile popover:

1. Map health to short bilingual descriptions, for example:
   - online: `🟢 Online / 在線 — PD One is healthy. See pinned status post for details.`
   - degraded: `🟡 Degraded / 狀態不穩定 — PD One has a temporary health-check issue. See pinned status post for details.`
   - offline: `🔴 Offline / 離線 — PD One failed repeated health checks. See pinned status post for details.`
2. Update the bot account with `PUT /api/v4/bots/{bot_user_id}` and JSON body `{"description": "..."}`. The same bot token was sufficient for `@pdone`; if a future bot lacks permission, use a system-admin token only narrowly and keep it redacted.
3. Store `bot_description_status`, `bot_description`, and `bot_description_updated_tpe` in monitor state and only update when the status/description changes.
4. Keep failures non-fatal to the main pinned post update: log a warning, save `bot_description_error`, and preserve the pinned post as source of truth.
5. Verify by reading back `/api/v4/bots/{bot_user_id}` (`description`) and `/api/v4/users/me` (`bot_description`).

## Verification receipts

Before telling the user it is live, verify:

1. Script syntax/compile check and executable permissions.
2. Manual run creates or patches a Mattermost post and writes state/logs.
3. Timer is enabled and active: `systemctl --user is-enabled/is-active <timer>`.
4. Forced or scheduled timer run exits with `Result=success`, `ExecMainStatus=0`.
5. State readback shows current status, `post_id`, and URL hint.
6. If pinned/employee-visible, Mattermost API readback shows expected `channel_id`, `is_pinned: true`, and bilingual message text.
7. If bot avatar presence was changed, Mattermost status API readback shows the intended status and whether `manual` is set.
8. Backup commit/push if Hermes state/scripts changed.

## Pitfalls

- A `cronjob(action='create')` receipt alone is not sufficient if no persistent Hermes scheduler process is visible. If the forced run/list does not prove execution, switch to a systemd timer and verify a real scheduled tick.
- Do not create a new Mattermost message on every run. If the saved `post_id` is missing or patch fails because the post disappeared, create one replacement, pin it, and update state. Treat transient patch failures/timeouts/5xx as fail-closed errors, not replacement triggers; otherwise one slow `posts/{post_id}/patch` call can create a duplicate status post while the original pinned post still exists.
- Redact tokens from logs and summaries; read env files only for the narrow Mattermost/OpenClaw credential need.
- Use admin/private Mattermost channels by default for runtime status unless the user explicitly asks for employee-facing visibility.

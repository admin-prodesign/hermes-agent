# Mattermost channel posting notes

Use this when Andy asks Hermes/PD Neo to post something to a Pro-Design Mattermost channel on behalf of PD One.

## Lessons

- Hermes' bare `mattermost` / home target can resolve to the admin channel. Do not treat it as an intended employee/public channel.
- If the user names any Mattermost channel and provides a raw Mattermost channel id, preserve that id exactly and verify the posting route before sending.
- For PD One/company-facing announcements, use PD One's direct Mattermost REST posting path as `pdone`, because PD One owns the Mattermost employee-facing integration.
- **All Mattermost channel announcement rule:** do **not** use `send_message("mattermost:#...")`, a raw channel id as a `send_message` target, or any ambiguous Mattermost home target for Mattermost channel announcements. These can fail to resolve or route incorrectly. Use the direct Mattermost REST posting path as `pdone`; verify `/api/v4/users/me`, post to `/api/v4/posts` with the exact target `channel_id`, read back the returned post, and verify sender/channel/message before reporting the post id receipt. If direct API posting is unavailable, state that clearly and do not claim the announcement was sent.
- Known AI channel id: `imj7bt6w4tdk5rsbttiga44agc` (`🤖 AI討論及IT需求提出 AI Discussion and IT Requests`). This is **not** the IT department channel, even though the name includes IT requests.
- Known IT department channel id: `jp47xmyu8prytmqrhimaw9hy7e` (`🅱️ IT (Information Technology)`, channel name `bu-it`, private channel). If Andy asks for the “IT MM channel” or “IT department channel,” post here, not the AI/IT requests channel.
- Known IT Work channel id: `itbmu3ycsjb3tfuscmw69b9iny` (`🅱️ IT工作 | IT Work`, channel name `it-work`, private channel). Use this for Portal/website/EIP/infrastructure implementation status, not department support tickets and not PD One Admin.
- Known SOP update channel id: `51gpdrkmhtr1z8w1e4smiga46a` (`SOP更新 | SOP Update`).
- Known current Sales channel id: `g1xqux4t3iy3bx3m59zosympco` (`🅱️ 業務部 | Sales Dept`, channel name `sales-dept`). Do not confuse this with deleted/legacy search hits such as old `sales-bu` channels; when Sales is requested, resolve and verify the non-deleted `sales-dept` channel before posting.
- If channel search does not find a private channel, query the bot's joined channels through Mattermost API (`/api/v4/users/me/teams/{team_id}/channels`) and filter by name/display name/purpose/header; Mattermost search may miss private or localized channel names, and may also surface deleted legacy channels if you query deleted endpoints.

## Recommended sequence

1. Draft/confirm the exact message text. If the user says “that message,” use the most recent approved message body from the active conversation rather than inventing a new announcement. For announcements drafted through `company-announcement-writer`, preserve the approved bilingual text exactly unless the user explicitly asks for edits. For PD One top-level/company-facing Mattermost posts, the approved bilingual order should be Traditional Chinese first, then English; fix English-first drafts before asking for approval or sending.
2. Resolve the intended channel(s) explicitly. Do not use the default Mattermost target unless the user said admin/home.
3. For Mattermost channel announcements, the required route is direct Mattermost REST as `pdone`:
   - load PD One Mattermost URL/token from the OpenClaw/Hermes approved credential path without printing secrets;
   - verify `GET /api/v4/users/me` returns username `pdone`;
   - `POST /api/v4/posts` with the exact approved target `channel_id` and the exact approved message;
   - read back the returned post id with `GET /api/v4/posts/{post_id}`;
   - verify sender is `pdone`, channel id matches the approved target channel, and message text matches the approved announcement exactly;
   - report the Mattermost post id as the receipt.
4. Prefer direct PD One bot posting through the maintained PD One Mattermost context when available: import `mattermost_review_log.py::mattermost_context()` from `/home/prodesign/hermes-backup/hermes/profiles/pdone/tools` (legacy references may mention `/home/prodesign/.openclaw/workspace/tools`, which is no longer present on the active Hermes host) and verify `/api/v4/users/me` is the PD One bot. Current helper shape may be a tuple, not a dict; unpack it as `(base_url, token, ...)` before building REST headers instead of assuming `ctx['base_url']` / `ctx['token']`.
5. Before the live send, run a dry-run/readiness probe that prints the sender username/id, channel id/name/display name, and message length. For AI channel announcements, expected channel id is `imj7bt6w4tdk5rsbttiga44agc` and expected sender username is `pdone`.
6. For image/file attachments, upload the file once per target channel with `POST /api/v4/files` using that channel's `channel_id`, then create the post with the returned `file_ids`. Do not reuse a file id uploaded to a different channel. A reusable helper is available at `scripts/post_mattermost_channel_with_attachment.py` for approved message-file + attachment posts through PD One credentials.
7. Verify each destination separately: read back the returned post and record returned `post_id`, `channel_id`, `user_id`, and whether the message matches the approved source text exactly; for attachments also verify non-empty `file_ids` before reporting success.
8. Treat a send result note such as “Sent to mattermost home channel” or a returned `chat_id` that differs from the intended channel id as a wrong-route warning even if `success=true`; immediately use the verified API route instead of reporting success.
9. If Hermes tooling cannot resolve the raw channel id or PD One credentials are unavailable, send an admin request to PD One with:
   - target channel id,
   - exact message body,
   - attachment path or durable artifact location,
   - instruction not to modify the text except Mattermost formatting.
10. Report clearly whether Hermes posted directly as PD One, asked PD One to post, or could not confirm delivery.

## Attachment/review-log note

- Mattermost policy says employee-facing attachments should be captured in `review_log` with `category: attachment_sent` and `notes` including `attachment_type:<type>`.
- However, `mattermost_review_log.py append` deliberately skips Andy/admin rows (`skippedAndyRows`) because Andy's own activity is not logged. Treat that as expected for Andy-requested admin sends; do not keep retrying the log append.

## Scheduled PD One posts with attachments

When Andy asks to schedule a PD One/Mattermost announcement for later:

1. Treat the request as approved for that scheduled external send, but still verify the exact target channel and sender before creating the job.
2. Use a no-agent cron/script path rather than a future LLM prompt when the content is already approved. The script should be deterministic, idempotent, and silent on success. For Hermes `cronjob` jobs under the `pdone` profile, put the script in `/home/prodesign/.hermes/profiles/pdone/scripts/` and pass only the relative filename (for example `post_ai_audio_transcription_announcement.py`) in the cron `script` field; absolute paths are rejected by the scheduler.
3. Use `mattermost_review_log.py::mattermost_context()` from `/home/prodesign/hermes-backup/hermes/profiles/pdone/tools` when posting as PD One so the `/api/v4/users/me` readback verifies the bot username (for example `pdone`) and avoids Hermes' ambiguous Mattermost home target.
4. For image/file attachments, upload first with `POST /api/v4/files` using `channel_id`, then create the post with `file_ids: [uploaded_id]`. Verify the returned post has a non-empty `file_ids` list containing that id before claiming delivery.
5. Store any generated attachment under a durable Hermes/OpenClaw artifact path before scheduling; do not leave the cron dependent on `/tmp`.
6. Add durable per-send state keyed by scheduled local time + channel + announcement purpose so retries or manual reruns do not duplicate the post.
7. For morning announcements, prefer the retry-until-deadline pattern from `automation-reliability/references/retry-until-deadline-cron.md` (for example first attempt at 08:00 local, retry until 08:30) and log attempts locally while suppressing noisy non-final alerts.
8. After creating the cron job, read it back and report the job id, local/UTC scheduled time, verified channel name/id, verified sender username, attachment path, and retry/idempotency behavior.

## Pitfall wording

If a post goes to the wrong channel, acknowledge directly: "I posted to the admin channel because Hermes' Mattermost home target maps there; I should have routed this through PD One for the AI channel." Then take the corrective route rather than retrying ambiguous targets.

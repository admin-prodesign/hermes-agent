# Mattermost Direct DM by Verified Username/User ID

Use this reference for Andy/admin requests to send a short Mattermost DM to a specific employee when the normal `send_message` target resolver cannot resolve the username, but the employee is present in PD One's exact-user policy files.

## Trigger

- Andy/admin explicitly asks PD One to DM a specific Mattermost user.
- `send_message(action='list')` does not expose the DM target, or `send_message(action='send', target='mattermost:<username>')` fails to resolve.
- The recipient can be verified by exact Mattermost username/email/user ID in `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-users.json` or the corresponding policy cache.

## Safety boundaries

- This is an external send. Only proceed when Andy/admin has clearly authorized the exact message and recipient.
- Do not use display-name/fuzzy matching. Verify exact Mattermost username and stable user ID from policy, then confirm live REST lookup resolves to the same ID.
- Do not send sensitive content beyond the approved scope. For Google Sheet/docs handoffs, summarize provenance and link only; do not dump raw confidential rows.
- Do not impersonate Andy. Send as PD One / `pdone` and word the message as a PD One notification.

## REST workflow when `send_message` cannot resolve

Use a short script that keeps tokens inside the process and prints only non-secret receipts:

1. Load Mattermost URL/token from the active PD One Hermes profile `.env` and, only if needed, legacy OpenClaw `.env`.
2. `GET /api/v4/users/me` to identify the bot sender.
3. `GET /api/v4/users/username/<username>` to resolve the live recipient.
4. Compare the returned `id` to the exact policy user ID. Abort if it differs.
5. `POST /api/v4/channels/direct` with `[bot_user_id, recipient_user_id]`.
6. `POST /api/v4/posts` with `channel_id` and the approved message.
7. `GET /api/v4/posts/<post_id>` and verify `message` matches exactly.
8. Report only receipt fields: post ID, channel ID, recipient username/id, sender username, and readback match.

## Receipt pattern

```text
Sent to <username> on Mattermost.
Receipt: post `<post_id>` in DM channel `<channel_id>`, sent as `<sender_username>`, readback verified.
```

## Replying after admin setup / prior onboarding gap

When Andy/admin asks to “reply back” to a newly enabled employee’s original Mattermost DM:

1. Resolve the employee by exact policy username/user ID and live REST lookup before sending.
2. Recover the original request from the durable `review_log` row or verified Mattermost thread/history evidence, not from fuzzy memory.
3. Draft a scoped employee-facing reply that answers the original request within the newly granted permissions. Do not expose policy internals or mention the admin setup mechanics unless needed.
4. Send through the verified direct-DM REST workflow above and read back the post body.
5. Close or update the related `review_log` row with targeted cell updates only: set follow-up to `no`, status to `closed`, add a concise reply summary/reason, and include the verified reply post ID in notes when no dedicated reply-post column exists. Read back the row before reporting completion.

## Manual catch-up for `dm_no_reply_evidence`

When a `review_log` watchdog item says a profiled DM-enabled user had no later PD One reply and Andy/admin says to make sure the user was replied to:

1. Treat Andy/admin’s instruction as approval for the bounded employee DM follow-up, but still verify the exact recipient from policy/cache and live Mattermost username/user ID before posting.
2. Fetch the exact Mattermost post/thread by REST from the watchdog permalink/post ID. Confirm the original post belongs to the expected policy user and inspect the thread for any later `pdone` reply.
3. If a later bot reply already exists, do not duplicate; report the existing post ID and close/update the review row if appropriate.
4. If no reply exists, draft a concise, scoped employee-facing answer to the original message. Post it in the original DM thread (`root_id` = original post when it was the root), as `pdone`, then read back the exact post body/user ID.
5. Update only the targeted `review_log` row/cells: `follow_up_needed=no`, `review_status=closed`, `assistant_response_type=answered_follow_up` or equivalent, a short `reply_summary`, and notes containing the verified reply post ID. Read the row back before reporting completion.

If the REST lookup fails, token is unavailable, policy/live ID mismatches, or the original request cannot be recovered from durable evidence, do not retry blindly. Report the blocker and ask Andy/admin for the correct target, source row/thread, or permission path.

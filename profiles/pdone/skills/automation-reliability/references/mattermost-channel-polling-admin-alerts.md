# Mattermost channel polling → admin alert automation

Use when Andy/admin asks PD One to watch a Mattermost channel and notify an admin lane when matching posts appear.

## Durable pattern

1. **Resolve exact channels first.** Use Mattermost REST as `pdone` and read back bot identity, source channel id/name, and destination admin channel id. Do not use ambiguous Mattermost home targets for channel posts.
2. **Prefer deterministic no-agent cron.** Put the script under `/home/prodesign/.hermes/profiles/pdone/scripts/` and schedule it with Hermes cron using the relative script filename only. For low-urgency admin onboarding/notification watches, default to a 15-minute cadence rather than frequent 1–2 minute polling unless the user explicitly asks for near-real-time behavior. The LLM/agent should not run during normal polling; only deterministic matching/sending should run, with any agent/human-visible escalation reserved for sustained failures or requested diagnosis.
3. **Use a watermark/state file.** Store state under `/home/prodesign/.hermes/profiles/pdone/state/<automation>.json` with at least:
   - `source_channel_id`
   - `admin_channel_id`
   - `last_create_at`
   - `notified_post_ids`
   - `last_run_at`
4. **Initialize before enabling live alerts.** For “future posts only” requests, run an explicit `--init` mode that sets the watermark to the latest existing post, then dry-run to verify zero pending historical alerts. This prevents spam from older channel history.
5. **Bound matching criteria.** For introduction/onboarding-style watches, only alert on top-level human posts: skip bot posts, deleted posts, system posts, empty messages, and replies (`root_id`) unless the user asks to include replies.
6. **Make the send idempotent.** Add the source post id to `notified_post_ids` only after the admin alert post is read back successfully. Retain a bounded tail (for example 500 ids) so state stays small.
7. **Live run should be quiet on success.** Successful no-op and successful alert runs can print nothing; the alert post plus JSONL log are the receipt. Dry-run/init modes should print JSON receipts.
8. **Verify the scheduler.** After creating the cron job, run it once, then read back cron status: `last_status=ok`, no delivery error, enabled/scheduled state, next run time.
9. **Register with the supervisor/audit surface.** Add a fail-closed entry to `/home/prodesign/.hermes/profiles/pdone/supervisor/automations.json` with state/log paths, criticality, duplicate-send risk, and `approval-required` autorepair classification.
10. **Back up durable state.** Copy the script, cron jobs file, supervisor registry, and initial state into the configured Hermes backup repo and commit/push when available.

## Admin alert content

Use a concise bilingual message in the admin channel. Include:

- source channel name and link to the source post
- Mattermost username/display name
- exact Mattermost user id
- source post id
- short excerpt, not a raw full-history dump

Do not claim onboarding itself is completed; the alert asks Andy/admin to onboard the person.

## Pitfalls

- A dry-run without an initialized watermark may reveal many old qualifying posts. Do not enable live mode until the user’s desired backfill behavior is clear; for “when someone introduces themselves” default to future-only initialization.
- Cron `deliver='origin'` is acceptable for failure/output routing, but live Mattermost admin alert posts must use direct REST with exact `channel_id`, not the Hermes ambiguous Mattermost target.
- Transient Mattermost SSL/read timeouts should not raise unhandled exceptions or print tracebacks into chat. Catch `requests.Timeout` / `ConnectionError` and 429/5xx responses, log JSONL/local failure state, exit 0 for short outages, and emit only a concise no-agent alert after a sustained consecutive-failure threshold. Do not call an LLM/agent for normal polling or first transient failures.
- If a future repair/replay is needed, inspect state and admin-channel readbacks first; replaying can duplicate onboarding requests.

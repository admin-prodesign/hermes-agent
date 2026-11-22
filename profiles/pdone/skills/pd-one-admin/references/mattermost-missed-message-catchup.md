# Mattermost Missed-Message Catch-up

Use this when Andy says PD One/OpenClaw or PD Neo/Hermes was offline and asks whether Mattermost messages were missed.

For PD One automatic-reply recovery involving review-log scanner wrappers, missed-reply replayer/timers, `NO_REPLY` replay, or company-wiki promotion of durable custom rails, also load `references/mattermost-auto-reply-recovery-rails.md`.

## Scope first

There may be two separate Mattermost bots on `nemo`:

- Hermes/PD Neo bot: configured under `/home/prodesign/.hermes/.env` with `MATTERMOST_URL` and `MATTERMOST_TOKEN`.
- PD One/OpenClaw bot: configured under `/home/prodesign/.openclaw/workspace/.env` or `/home/prodesign/.openclaw/.env` with `MATTERMOST_URL` and `MATTERMOST_BOT_TOKEN`.

Check the bot the user actually means. If unclear and the request mentions “Mattermost messages” broadly, check both surfaces and report separately.

## Bounded evidence sequence

1. Establish the suspected outage window from gateway logs or health output.
   - Hermes: `~/.hermes/logs/gateway.log`.
   - PD One: prefer bounded probes such as `openclaw health --json` and `openclaw logs --limit 200 --max-bytes 30000`; avoid broad status/log pulls from live chat paths.
2. Resolve bot identity with `GET /api/v4/users/me`; keep only username/id in output, never the token.
3. Use the Mattermost REST API with the relevant bot token to enumerate channels the bot is a member of: `GET /api/v4/users/{bot_id}/channels`.
4. For PD One/OpenClaw, also parse `/home/prodesign/.openclaw/openclaw.json` to resolve configured Mattermost bindings and channel policy:
   - `bindings[]` entries where `match.channel == "mattermost"` and `match.peer.kind == "channel"` map channel IDs to agent IDs.
   - `channels.mattermost.requireMention` and per-channel `channels.mattermost.groups.<channel_id>.requireMention` determine whether an unmentioned channel post should still route.
   - Treat `requireMention: false` channels, especially the Admin channel, as free-response surfaces where ordinary user posts can be expected to trigger PD One.
5. For each bound/member channel, fetch recent posts with `GET /api/v4/channels/{channel_id}/posts?since=<epoch_ms>&per_page=...`. For individual evidence, re-read `GET /api/v4/posts/{post_id}` and `GET /api/v4/posts/{root_id}/thread`.
6. Candidate missed messages are:
   - DMs/group DMs to the bot.
   - Channel posts explicitly mentioning `@<bot_username>` or the bot user id.
   - Channel posts in a configured `requireMention: false` channel.
   - Follow-up posts in threads where the bot had already participated, if the channel policy expects threaded follow-up handling.
7. Exclude system posts, deleted posts, and the bot’s own posts.
8. Determine whether each candidate already got a bot reply after it in the same thread/root. For DMs/group DMs, a later bot post in the same conversation shortly after the user post is usually enough; for channels, prefer same root/thread matching.
9. Search team posts for explicit bot mentions as a backstop: `POST /api/v4/teams/{team_id}/posts/search` with `@bot_username`, `bot_username`, and bot user id.
10. When the question is specifically “which threads should PD One have replied to but didn’t,” correlate candidates with OpenClaw routing/failure logs. A high-confidence missed thread has all of:
    - the post is a routing candidate by mention/thread policy or `requireMention: false`,
    - no later bot reply exists in the same Mattermost thread,
    - logs show the same channel/thread routed to an agent lane such as `session:agent:<agent>:mattermost:group:<channel_id>:thread:<root_id>`, or logs show a runtime failure around that time.
11. If the deterministic missed-reply replayer returns no candidates but user-visible DMs were missed, run a manual DM/group-DM REST scan: for each bot-member DM/GDM channel, fetch posts since the suspected outage window, group by `root_id` or the post id for rootless posts, and mark user posts with no later bot post in the same thread/conversation. Then correlate their timestamps with gateway diagnostics such as long-running sessions, queued work, event-loop starvation, app-server/tool-call timeouts, and harness failures.
12. While checking runtime health, also look for stale local OpenClaw/ACP processes and repeated loopback `protocol mismatch` noise. Record process age/cmdline as evidence, but treat cleanup as a separate approval-gated action unless the gateway is already unresponsive under the established restart exception.
13. If review-log/missed-reply helper timers are implicated, inspect both timer and service state. A oneshot review-log scanner can sit in `activating` after its core scan timed out if an unbounded failure alert/auto-triage send blocks; bound those alert calls with `timeout`, stop/reset only the stuck helper service (not the gateway), then verify the next timer tick and log tail.
14. If the missed-reply replayer fails inside systemd with `No such file or directory: 'openclaw'`, treat it as a service execution-environment issue, not a gateway outage. Verify the helper can resolve OpenClaw under a minimal systemd-style `PATH`, prefer an explicit `OPENCLAW_BIN` or script-level absolute/fallback resolver, run the helper self-test, run a dry-run replay, and then verify the next normal timer tick exits successfully. Do not restart OpenClaw just for this failure mode.

## Safe catch-up reply

If a missed message clearly needs a reply and the target scope is already authorized:

1. Reply in the original channel/thread (`channel_id` + `root_id`), not a new public post.
2. In Mattermost channels/groups, use bilingual English + Traditional Chinese with equivalent substance unless a policy explicitly says otherwise.
3. Keep the reply concise and acknowledge the delay without over-explaining internal failure details.
4. Verify delivery with `GET /api/v4/posts/{new_post_id}` or by re-reading the thread; only claim delivery after a created post is confirmed.

## Pitfalls

- Hermes/PD Neo and PD One/OpenClaw use different tokens and bot usernames; checking only Hermes can miss PD One employee messages.
- Gateway logs show connection health, but not all actionable missed mentions; use REST API post history as the source of truth.
- For Hermes/PD One Mattermost WebSocket misses, absence of `inbound message` in `~/.hermes/profiles/pdone/logs/gateway.log` is meaningful only after confirming the post exists via `GET /api/v4/posts/{post_id}` and should have routed. Useful corroborating evidence: no `Mattermost: appended utility-agent translation to mentioned post {post_id}` for a channel mention, no heartbeat/session for the post's `root_id`, and nearby WebSocket reconnect/`Server disconnected` churn. Treat this as a missed live `posted` event/backfill gap, not a permission failure, when REST shows an explicit bot mention by an allowed user.
- Do not rely only on explicit mention search. PD One/OpenClaw channels can be configured with `requireMention: false`; those ordinary posts should be included as candidates.
- Mattermost post create times and OpenClaw failure-log times can differ by seconds if queueing/retry happened; correlate by `channel_id` + `root_id` in the lane string when available, not timestamp alone.
- The missed-reply replayer is intentionally conservative. It handles failed routed Mattermost lanes and can also inspect session JSONL/trajectory files for successful runs whose only visible assistant output was `NO_REPLY`. The `NO_REPLY` path must still pass thread readback and routing-policy gates: skip if a later bot reply exists after the target post; in `requireMention: true` channels, replay only explicit bot mentions/bot-id mentions; allow no-mention catches only in configured `requireMention: false` channels. If Andy reports a specific thread and the replayer returns empty, inspect the exact Mattermost thread via REST and the matching agent session JSONL/trajectory; a routed user message followed by assistant `NO_REPLY` is still a missed employee-facing reply when the employee directly asked/mentioned PD One.
- If Andy reports “several user messages” and the replayer returns empty, manually scan Mattermost DMs/group-DMs via REST for posts after the suspected window that have no later bot post in the same DM/thread. Include rootless DM posts as their own roots.
- Queue stalls can produce unreplied messages without a clean `Embedded agent failed before reply` on the Mattermost lane. Check for diagnostics such as `long-running session`, `queued_behind_active_work`, `gateway timeout`, `codex dynamic tool call timed out`, event-loop starvation, and `codex app-server client is closed` around the candidate post times.
- Repeated `protocol mismatch` logs from an old local ACP/OpenClaw process can create noisy churn and may contribute to latency, but do not treat the error string alone as the root cause. Bound it with process age/cmdline, gateway health, event-loop diagnostics, and reply evidence; do not kill stale processes unless the user approves or the gateway is already unresponsive under the restart/kill exception.
- A missing harness/module error or other runtime failure that later resolves after restart is not itself durable knowledge; capture the correlation method and safe restart/verification pattern, not the obsolete module filename as a permanent constraint.
- Do not restart OpenClaw while investigating unless bounded checks show the gateway is unresponsive and the restart rule allows it.
- Do not print tokens or raw env files. Load env vars only inside the command environment and redact any diagnostic output.

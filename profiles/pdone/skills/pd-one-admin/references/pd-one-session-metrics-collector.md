# PD One session metrics collector triage

Use for `pd-one.failure` alerts from `pd-one-session-metrics-collector` or failures in `tools/pd_one_metrics/collect_session_metrics.py`.

Andy 2026-09-04: do **not** post the weekly engagement report to Mattermost. The live surface is the PD One Portal module. `send_weekly_mattermost_report.py` still writes weekly artifacts and syncs the engagement-history Sheet, but live Mattermost posting is retired unless `--post-mattermost` is explicitly passed. Keep `legacy-crontab-15-pd-one-engagement-metrics` collecting.

## Known durable pitfall: mixed session content shapes

OpenClaw session JSONL records are not guaranteed to have only structured dict content parts. Some legacy/plain records can include string entries inside `message.content` (or other non-dict shapes). Metrics code that loops over `message.get("content")` and calls `item.get(...)` will crash with:

```text
AttributeError: 'str' object has no attribute 'get'
```

Safe collector pattern:

- Parse only aggregate metadata; do not persist raw message bodies in metrics artifacts.
- Normalize content iteration through helper functions:
  - one helper for structured dict parts used by tool-call counters;
  - one helper for visible text that accepts both plain strings and `{type: "text", text: ...}` dicts.
- Ignore unsupported content item shapes instead of failing the whole aggregate run.
- Keep the fix narrow and reversible; no gateway restart is needed for a pure collector script fix.

## Known durable pitfall: Hermes migration data source split

After PD One moved to Hermes profile `pdone`, current Mattermost activity is stored in `/home/prodesign/.hermes/profiles/pdone/state.db` plus `/home/prodesign/.hermes/profiles/pdone/sessions/sessions.json`, not only legacy `/home/prodesign/.openclaw/agents/admin/sessions/*.jsonl`. A weekly report that reads only OpenClaw JSONL can show nonzero assistant-only automation posts but zero user messages, tool calls, tokens, and users.

Safe collector pattern:

- Prefer Hermes `pdone` `state.db` for current Mattermost metrics; keep OpenClaw JSONL as a fallback for historical/manual environments.
- Use `sessions` rows for session-level token/tool/cost aggregates and `messages` rows for role/message/day counts.
- Use `sessions/sessions.json` origin metadata for Mattermost user/channel/chat-type aggregates; do not persist raw message bodies.
- Hermes stores usage at session level, so daily token allocation is approximate. Attribute session usage to the last message day inside the requested window; weekly totals are the primary reliable metric.
- No gateway restart is needed for collector/report script changes.

## Known durable pitfall: legacy OpenClaw source after Hermes PD One migration

If a weekly/monthly engagement report shows impossible zeros (for example non-zero assistant answers but `user_messages=0`, `unique_users=0`, `tool_calls=0`, `tokens_totalTokens=0`), first check whether the collector is still reading the legacy OpenClaw session store instead of the active Hermes `pdone` profile/session database.

Diagnostic pattern:

- Confirm the posted report artifact and weekly sender script path under `tools/pd_one_metrics/`.
- Dry-run the weekly report with the same `--now-utc` as the bad post and `OPENCLAW_STATE_DIR=/home/prodesign/.openclaw` to reproduce the exact output without sending a new Mattermost post.
- Inspect only aggregate shapes/counts: roles seen in the old OpenClaw JSONL, whether records are assistant-only automation posts, and whether `toolCall`/usage fields are present. Do not dump raw prompts or message bodies.
- Compare against Hermes profile session metadata/session DB under `/home/prodesign/.hermes/profiles/pdone` to confirm current Mattermost sessions exist outside the old OpenClaw source.

Fix pattern:

- Treat this as a data-source migration bug, not real zero engagement.
- Update the metrics collector to read the active Hermes PD One session metadata/session DB, or merge it with legacy OpenClaw data only if deduplication is explicit.
- Preserve privacy: aggregate counts only, no raw prompts/message text/per-user details in artifacts.
- Re-run the weekly report as a dry-run first, then regenerate/send only after approval if it will post externally or overwrite durable reporting artifacts.
- No gateway restart is required for a pure collector/reporting script fix.

## Bounded triage sequence

1. Reproduce with a temp output path first:

   ```bash
   cd /home/prodesign/.openclaw/workspace
   OPENCLAW_STATE_DIR=/home/prodesign/.openclaw python3 tools/pd_one_metrics/collect_session_metrics.py \
     --json-out /tmp/pd_one_metrics_test.json \
     --md-out /tmp/pd_one_metrics_test.md
   ```

2. For bad weekly Mattermost posts, reproduce the exact rendered report without sending:

   ```bash
   cd /home/prodesign/.openclaw/workspace
   OPENCLAW_STATE_DIR=/home/prodesign/.openclaw python3 tools/pd_one_metrics/send_weekly_mattermost_report.py \
     --dry-run \
     --now-utc 2026-06-05T07:00:02.508292+00:00
   ```

   Use the posted report's `Generated`/state timestamp for `--now-utc`. If the dry-run matches the bad post, diagnose source selection before changing counting logic.

3. If the traceback points at content iteration, patch the collector to tolerate mixed content item types rather than filtering sessions out. If counts are impossible zeros after the Hermes migration, patch the collector's data-source adapter to read Hermes `pdone` session metadata/session DB, with explicit dedupe if legacy OpenClaw is also read.
4. Verify syntax:

   ```bash
   python3 -m py_compile tools/pd_one_metrics/collect_session_metrics.py
   ```

4. Verify the temp run succeeds, then run the live collector once:

   ```bash
   python3 tools/pd_one_metrics/collect_session_metrics.py
   ```

5. Confirm the generated aggregate artifacts exist and were updated:

   - `data/pd-one-metrics/session_metrics_latest.json`
   - `reports/pd-one-metrics/session_metrics_latest.md`

6. Commit and push only the narrow durable source fix when a backup remote is configured. Generated metric artifacts may remain dirty from the verification/live rerun unless there is a separate reason to snapshot them.

## Safety

- Admin-only evidence; avoid broad scans and do not inspect message bodies beyond what is needed to diagnose parser shape.
- Do not restart OpenClaw gateway, kill processes, replay sends, or change messaging config for this collector-only failure.
- Final auto-triage report should state event/source, action taken, verification, backup commit if any, and remaining blockers.
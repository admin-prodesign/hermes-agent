# Mattermost `review_log` test maintenance

Use this when cleaning up PD One/OpenClaw Python tests around `tools/mattermost_review_log.py` and `tools/review_log_source_collector.py`.

## Targeted commands

From `/home/prodesign/.openclaw/workspace`:

```bash
PYTHONPATH=/home/prodesign/.openclaw/workspace/tools \
  pytest -q tests/test_mattermost_review_log.py tests/test_review_log_source_collector.py -vv

PYTHONPATH=/home/prodesign/.openclaw/workspace/tools pytest -q tests
```

## Common stale-test patterns

1. **Dynamic sheet headers**
   - `append_rows()` reads the live `review_log` header via `review_log_headers()` before insert/update.
   - Unit tests should stub `mrl.review_log_headers = lambda: list(mrl.HEADERS)` rather than letting tests call `gog sheets get`.
   - Expected update ranges should use the current header width (`A:AB` for 28 headers at time of writing) or compute from the headers rather than assuming the legacy `A:Q` range.

2. **Structured note columns**
   - `normalize_review_log_row()` parses legacy note tags into structured columns such as `access_status`, `blocked_or_missing_sources`, `answer_sources`, `event_source`, `mattermost_post_id`, and `auth_debug`.
   - Tests should assert the structured column values after normalization, not expect migrated tags such as `permission_blocked:*` to remain in `notes`.

3. **DM auth API**
   - `review_row_for_dm_post()` takes an `auth` dict and derives profiled/DM-enabled behavior from `auth["dmEnabled"]`.
   - Do not use the old `profiled=True` test helper shape.
   - For profiled DM tests, pass a minimal auth dict with `mattermostUserId`, `found: True`, `dmEnabled: True`, `decision`, and `sourceHash`, then assert auth debug tags such as `auth_dm_enabled:true` when checking raw row notes.

4. **Reply-evidence API**
   - `review_row_for_dm_post()` and `review_row_for_channel_post()` now distinguish closed normal activity from no-reply evidence.
   - Tests for profiled DM/channel rows should cover both branches: no `normal_bot_replies` produces `*_no_reply_evidence`, `follow_up_needed=yes`, `review_status=open`; a non-empty `normal_bot_replies` list produces the normal closed category and should include `bot_reply_ids:<id>` in notes.
   - Scanner tests should pass through the helper that finds later PD One bot posts in fetched Mattermost history rather than assuming every profiled user post is closed.

5. **Mixed session message content shapes**
   - OpenClaw session transcripts may store `message.content` as a plain string, a single dict, or a list of typed content dicts.
   - Source-collector helpers that inspect content should normalize this shape before calling `.get()` on content parts; add a regression test with string content so scheduled collectors do not crash on older/mixed transcripts.

## Commit discipline

- Keep changes narrow to the failing test files unless production behavior is actually wrong.
- Verify targeted tests first, then the full `tests/` suite.
- Commit/push only the relevant test changes; leave unrelated dirty workspace state untouched.

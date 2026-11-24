# Mattermost review_log outage backfill notes

Use this as a compact example of the bounded backfill pattern for scanner rows that were historically marked `closed` during an outage without timely PD One reply evidence.

## What to verify before editing

- Exact `review_log` rows and `mattermost_post_id` values.
- Current values for `category`, `assistant_response_type`, `follow_up_needed`, `review_status`, `reason`, `notes`, and structured source/status columns.
- Mattermost thread history around each user post:
  - user post timestamp
  - first later PD One bot post timestamp/id
  - whether that bot post falls inside the scanner reply-evidence window
  - whether the bot post is a delayed catch-up reply after an outage

## Targeted row update shape

For a false-closed outage row with no timely bot reply evidence:

- `category`: `dm_no_reply_evidence` or `channel_no_reply_evidence`
- `assistant_response_type`: `no_bot_reply_evidence`
- `follow_up_needed`: `yes`
- `review_status`: `open`
- `reason`: note historical outage backfill, no timely bot reply in scanner window, and any delayed catch-up reply timestamp/id.
- `notes`: include `historical_backfill:<date>`, `outage_false_closed`, `mattermost_post_id:<id>`, `root_id:<id>`, and delayed catch-up reply id if present.
- `answer_sources`: say Mattermost scanner/backfill evidence only; no timely bot reply within window.
- `access_status`: `yes no timely Mattermost bot reply evidence found by backfill` or equivalent.
- `blocked_or_missing_sources`: state employee-facing answer was delayed/unverified and needs review/replay confirmation.

## Row-update command pattern

Use the existing review-log helpers to avoid column-order mistakes:

```python
import json, sys
sys.path.insert(0, '/home/prodesign/.openclaw/workspace/tools')
import mattermost_review_log as mrl
headers = mrl.review_log_headers()
idx = {h: i for i, h in enumerate(headers)}
# Read a bounded exact range, update only target rows in memory, then write:
# rownum and row must be prepared by the caller after reading/verifying the row.
mrl.run([
    mrl.GOG_BIN, 'sheets', 'update', mrl.SHEET_ID, f'review_log!A{rownum}:{mrl.col_letter(len(headers))}{rownum}',
    '--values-json', json.dumps([row], ensure_ascii=False),
    '--input', 'RAW', '--account', mrl.GOG_ACCOUNT, '--json',
])
```

Prefer exact row ranges like `review_log!A5:AB5` over append/sort/clear operations.

## Safety rules

- Do not bulk edit/sort `review_log`; update only confirmed rows.
- Do not change a row that has timely bot reply evidence unless there is another explicit defect.
- Do not overwrite human-reviewed status cells outside the bounded target set.
- Read back the exact range after writing and record a tracked docs/runbooks audit note when the backfill is operationally important.
- If the skill/reference is updated, run the Hermes backup script after patching so the skill change is pushed to the private backup repo.

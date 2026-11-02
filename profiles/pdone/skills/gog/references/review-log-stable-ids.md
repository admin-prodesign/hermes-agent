# review_log stable ID column pattern

Use this when adding or maintaining reference IDs on PD One `review_log` or similar Google Sheets audit logs.

## Why

Andy needs a short, stable `review_log_id` so he can refer to a specific review item without quoting a Mattermost URL or relying on row numbers that change when new rows are inserted.

## Recommended ID shape

For Mattermost-backed rows:

```text
RL-YYYYMMDDHHMMSS-<first 8 chars of mattermost_post_id>
```

Example:

```text
RL-20260605073108-xmykngu8
```

For non-Mattermost/legacy rows, use the same timestamp prefix plus a compact deterministic hash from stable row fields such as `timestamp_utc`, `user_id`, `channel_id`, `category`, and `request_summary`.

If two legacy rows collide, suffix later duplicates with `-02`, `-03`, etc. during backfill so every non-empty data row has a unique ID.

## Safe Sheet update sequence

1. Read the full live header row and current data range before changing the sheet.
2. Generate planned IDs locally and verify:
   - data-row count;
   - no blank planned IDs for non-empty rows;
   - uniqueness after duplicate suffixing.
3. Prefer appending the new column at the end unless the user explicitly asks for a position. Avoid row-number-based references.
4. After writing, read back the whole used header/data range and verify:
   - `review_log_id` header exists;
   - every non-empty row has a nonblank ID;
   - IDs are unique;
   - existing operational columns, especially `access_status`, are still present and populated as expected.
5. Patch the producer code in the same session so future appended rows populate `review_log_id`; otherwise the sheet backfill will decay immediately.
6. Run producer syntax checks and a dry-run/no-op readback path before reportback.

## Pitfalls observed

- `gog sheets insert ... cols 1 --dry-run` may show an apparently valid request, while the live insert can fail with a Google API `range.startIndex must be set` error. If insertion at the front is not required, append the new column at the end with a direct header/value update instead.
- A failed/partial column-add repair can leave an important column header displaced or missing from the visible header set. Compare before/after header lists by header name, not only by column count.
- Do not bulk rewrite/sort `review_log` while adding IDs; preserve Andy/manual `follow_up_needed`, `review_status`, notes, and source-status edits.

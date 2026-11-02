# Safe Google Sheets operations without approval-noisy shell shapes

Use this reference when PD One needs to read or write Google Sheets through Gog but should avoid unnecessary Hermes dangerous-command prompts.

Employee-lane exception: if `terminal` is blocked for this sender, do **not** use this helper. Use `tool_search` then `mcp__pdone_safe_ops__pd_one_sheets_get_range` / `mcp__pdone_safe_ops__pd_one_sheets_batch_update` (exact catalog names). Do not `tool_describe` short names, do not browser-type Sheets, and do not treat a blocked terminal as missing Sheets API.

## Why

Hermes flags command shapes such as:

- `python -c ...`
- `python <<'PY' ... PY`
- `node -e ...`
- `bash -c ...`
- `gog ... | python ...`
- other pipe-to-interpreter patterns

Those patterns are intentionally suspicious even when the business operation is only a bounded Google Sheets write. For Google Sheets work, prefer checked-in helper scripts and JSON files so the terminal command is a simple script invocation.

## Standard helper

Use:

```bash
/home/prodesign/.hermes/profiles/pdone/scripts/sheets_safe_ops.py --help
```

The helper wraps `gog` with `shell=False`, defaults to `admin@prodesign-group.com`, blocks Gmail send, never prints tokens, and defaults all writes to dry-run unless `--live` is explicitly supplied.

## Bounded read

```bash
/home/prodesign/.hermes/profiles/pdone/scripts/sheets_safe_ops.py get \
  SPREADSHEET_ID 'Sheet1!A1:Z50' \
  --out /home/prodesign/.hermes/profiles/pdone/tmp/TASK/readback.json
```

This prints row/column counts and can save the raw Gog response for later inspection without piping through `python -c`.

## File-backed batch update

Create a JSON file:

```json
[
  {"range": "'Sheet1'!B2:C2", "values": [["status", "note"]]}
]
```

Dry-run first:

```bash
/home/prodesign/.hermes/profiles/pdone/scripts/sheets_safe_ops.py batch-update \
  SPREADSHEET_ID \
  --data-json /home/prodesign/.hermes/profiles/pdone/tmp/TASK/update-ranges.json \
  --readback "'Sheet1'!B2:C2" \
  --receipt /home/prodesign/.hermes/profiles/pdone/tmp/TASK/dry-run-receipt.json
```

After the write is approved and the dry-run looks bounded, run live:

```bash
/home/prodesign/.hermes/profiles/pdone/scripts/sheets_safe_ops.py batch-update \
  SPREADSHEET_ID \
  --data-json /home/prodesign/.hermes/profiles/pdone/tmp/TASK/update-ranges.json \
  --live \
  --readback "'Sheet1'!B2:C2" \
  --receipt /home/prodesign/.hermes/profiles/pdone/tmp/TASK/live-receipt.json
```

## Chunked append

Create a JSON 2D array file, then dry-run/live:

```bash
/home/prodesign/.hermes/profiles/pdone/scripts/sheets_safe_ops.py append \
  SPREADSHEET_ID "'Log'!A:D" \
  --values-json /home/prodesign/.hermes/profiles/pdone/tmp/TASK/append-rows.json \
  --chunk-size 50
```

Add `--live` only after verifying the dry-run. Record `--receipt` for writeback evidence.

## Header-aware row update

Create a JSON object of header names to values:

```json
{
  "review_status": "closed",
  "follow_up_needed": "no"
}
```

Then find the row by a stable key header and update only those cells:

```bash
/home/prodesign/.hermes/profiles/pdone/scripts/sheets_safe_ops.py header-update-row \
  SPREADSHEET_ID \
  --sheet review_log \
  --key-header review_log_id \
  --key-value RL-123 \
  --values-json /home/prodesign/.hermes/profiles/pdone/tmp/TASK/header-update.json \
  --receipt /home/prodesign/.hermes/profiles/pdone/tmp/TASK/dry-run-receipt.json
```

Add `--live` after approval/dry-run. This reads live headers and avoids fixed column assumptions.

## Rules

- Prefer JSON files under `/home/prodesign/.hermes/profiles/pdone/tmp/<task>/`; do not pass large inline JSON in command arguments.
- Do not pipe Gog output into interpreters. Save receipts/readbacks to files and inspect with `read_file` or the helper's summary output.
- Do not use `execute_code` for approved Sheets writes when a helper plus `terminal` can do the job. If the user says "use the API" or "don't use the browser," still prefer `sheets_safe_ops.py`/`gog` from `terminal`; those are API-backed and keep the approval surface visible without dangerous-command prompts.
- For recurring automations, call the helper from a no-agent script and keep the script silent on no-op ticks.
- Continue to require the normal user/admin approval for live source-system writes; this helper reduces false-positive command-shape prompts, not business approval requirements.

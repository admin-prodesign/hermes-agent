# PD One engagement-history Google Sheet sync

Use when Andy/admin asks whether PD One engagement history is tracked in Google Sheets, or asks to set up/repair a privacy-safe engagement metrics tracker.

## Scope and privacy boundary

- Use aggregate counts only: conversations, assistant answers, user messages, unique users, token totals/costs, tool-call counts, top-tool aggregates.
- Do **not** write prompts, raw message text, transcripts, or per-user content into the Sheet.
- Prefer the existing PD One workbook when appropriate: `PD One` / spreadsheet ID `1kJntZ6L8P72q_Brsp7ixrQsmxnDs6EACMQqpwgGxLOE`.
- Recommended tabs:
  - `pd_one_engagement_dashboard`
  - `pd_one_engagement_weekly`
  - `pd_one_engagement_daily`

## Discovery pattern

1. Search Drive for existing Sheet trackers by names/full text such as `engagement`, `互動`, `PD One Weekly Engagement Report`, and `PD One` before creating anything new.
2. If a generic existing `PD One` workbook already holds PD One registry/review tabs, add engagement tabs there instead of creating another workbook, unless Andy asks for a separate file.
3. Read existing metrics artifacts first:
   - weekly JSON artifacts under `legacy-openclaw/workspace/data/pd-one-metrics/weekly/`
   - latest aggregate output at `legacy-openclaw/workspace/data/pd-one-metrics/session_metrics_latest.json`

## Build/update pattern

- Generate bounded value-range JSON and update with `gog sheets batch-update --data-json @file --input USER_ENTERED`.
- Use header rows and stable tab names; keep formulas/dashboard references by tab/header semantics rather than fragile column assumptions where practical.
- Format header rows after writing values. Gog `sheets format` expects a Sheets API `CellFormat` object and field names **relative to** `userEnteredFormat`; do not pass `userEnteredFormat(...)` in `--format-fields`. Example:

```bash
gog sheets format "$SPREADSHEET_ID" 'pd_one_engagement_weekly!1:1' \
  --format-json '{"backgroundColor":{"red":0.85,"green":0.92,"blue":0.98},"textFormat":{"bold":true},"horizontalAlignment":"CENTER"}' \
  --format-fields 'backgroundColor,textFormat,horizontalAlignment' \
  --account admin@prodesign-group.com --json --no-input
```

## Dashboard formula pitfalls

- Google Sheets may return `0` from `MAX()` over ISO timestamp text. For visible last-sync cells, prefer the last nonblank row:

```gs
=IFERROR(INDEX(pd_one_engagement_weekly!D2:D,MATCH(2,1/(pd_one_engagement_weekly!A2:A<>""))),"")
```

- `QUERY(... limit 8)` spill formulas need enough allocated rows below the formula. If trimming the dashboard grid, keep at least the formula row plus expected spill rows (for example 24 rows for an 8-row recent-weekly table), not only the static rows in the source payload.

## Grid trim and token hygiene

- After creating tabs, trim allocated blank rows/columns and verify `gridProperties`.
- If using `sheets_trim_grid.py`, export a temporary Gog token into a private task directory, use it only for the trim call, then delete it and verify removal.
- If future syncs clear values after a tab has been trimmed, clear only the actual intended range (`A:U`, `A:N`, `A:D`, etc.). Clearing `A:Z` on a trimmed tab can expand columns again.

## Automation wiring

- If the weekly Mattermost engagement report is the source of truth, wire the weekly report sender to run the Sheet sync immediately after writing weekly artifacts and before posting the report. Dry-run mode should call the Sheet sync in dry-run mode and print the receipt.
- Verify with:
  - script syntax check (`py_compile`),
  - weekly report dry-run receipt,
  - live Sheet readback from dashboard/weekly/daily tabs,
  - grid dimension readback,
  - future cron/job receipt or project registry note when this becomes an ongoing operational tracker.

## Final report receipts

Report back with:

- Sheet URL and tab names.
- Row counts read back (weekly/daily).
- Grid trim dimensions.
- Privacy statement: aggregate-only, no raw prompts/message text/per-user content.
- Confirmation that future weekly automation is wired, if applicable.

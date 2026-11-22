# Review-log first-pass triage receipts

Use this as a compact reference when the supervisor run is read-only triage only.

## Bounded read pattern
- Read the live tab by name: `pd_one_review_log`.
- Prefer a wide bounded range for current counts, e.g. `A1:AZ1000`.
- Save raw `gog ... --json` output to a temp file first, then parse with a robust JSON reader.
- Treat the returned range as authoritative if Sheets truncates the requested bound.

## Classification habits that held up in this run
- Direct DM rows with later bot-reply evidence are only “likely closeable after verification” until the exact reply IDs/timestamps are re-verified.
- Workflow rows with `workflow_outcome_verified=no` stay open even when the reply prose sounds complete.
- Approval-gated / access-scope rows stay open and should be routed to Andy/admin rather than converted to closure from prose.
- Rows with no later bot reply evidence remain corrective-reply candidates until the exact thread proves otherwise.

## Reporting shape
- Report counts first, then concise row IDs/physical row numbers.
- Say explicitly: `No Sheet rows were changed; this is first-pass triage only.`
- Do not paste raw transcripts.
- Keep closure recommendations phrased as verification-only unless the exact write/send is separately approved.

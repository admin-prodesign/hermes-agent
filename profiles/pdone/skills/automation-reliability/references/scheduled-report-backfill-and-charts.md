# Scheduled report backfill and chart updates

Use this when changing recurring report generators that post to Mattermost/Discord/email and need a corrected/manual rerun for an already-issued report.

## Pattern

1. Keep the normal scheduled path unchanged; add narrow, explicit backfill knobs instead of editing state by hand.
   - Example: `--now-utc 2026-05-29T07:00:00Z` to reproduce the original report window/generation timestamp.
   - If the collector stamps `generated_at` internally, overwrite the emitted metric artifact timestamp from the effective report time so dry-run/live output is reproducible.
2. For charts inside chat reports, prefer text/Markdown-safe charts unless the delivery path supports verified file attachments.
   - Include the date, raw count, and scaled bar so the chart is readable even when fonts/clients differ.
   - State filtering assumptions directly in the report, e.g. `workdays only; weekends/non-work days omitted`.
3. Dry-run first with the same effective time/window that the live rerun will use.
4. For live reruns, use the system’s explicit resend/force flag only after confirming the report should be reposted.
5. Read back the created post/message and verify the new section exists before reporting success.
6. If the report generator lives in a backed-up repo, commit and push code/docs plus any intentionally preserved generated artifact; do not commit ignored transient logs/state unless explicitly needed.

## Pitfalls

- Running a dry-run at the current time may shift a rolling weekly window and make the result differ from the original report; use a report-time override for same-day corrections.
- A collector may use the real current time for `generated_at` even when collection windows are overridden; normalize the artifact timestamp before rendering.
- Generated Markdown under ignored report directories may not be tracked; verify `git check-ignore`/status and commit only durable code/docs/data artifacts.

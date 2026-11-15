# Supervisor plan dedup and read-only triage notes

This reference captures two recurring lessons from PD One supervisor runs:

1. Exact-gap remediation-plan dedupe
   - Before writing a remediation plan, search existing plans for the same automation and the same gap/state class.
   - Reuse an existing plan when the new finding is the same exact issue family, even if the run is later in time.
   - Do not create duplicate plans for repeated sightings of the same missing-bridge, missing-live-cron, delivery-failure, or stale-live-source condition.
   - Only create a new plan when the evidence is materially different and the old plan does not cover the new gap class.

2. Read-only `review_log` first-pass triage
   - Use a bounded live read with headers, then classify only rows where `review_status` is non-closed.
   - For sparse sheets, do not trust array position alone; preserve physical row mapping when row numbers matter.
   - Parse `gog ... --json` with a tolerant JSON reader (`strict=False` worked on this run) because cells may contain multiline content.
   - If a bounded wide read such as `review_log!A1:AZ1000` returns zero non-closed rows, report that fact directly instead of guessing there are hidden open rows.
   - Do not invent triage categories when the scan is clean; the correct receipt is often simply that no open rows were present in the bounded live window.

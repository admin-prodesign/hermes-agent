# PD One review_log supervisor triage handoff

Use this when Andy wants the PD One Automation Supervisor Agent to replace the generic `review_log` digest with a first-pass review report.

## Intended shape

The supervisor-agent may do **read-only first-pass triage** of non-closed `review_log` rows, but should not become an autonomous closer or employee-facing responder by default.

Recommended scope for each supervisor-agent run:

1. Load `automation-reliability` and the PD One admin `mattermost-review-log-health-check` reference before reading rows.
2. Run the normal supervisor repair/wrapper/audit workflow first.
3. Read live `review_log` headers and recent/open rows by header names, not assumed column letters.
4. When using `gog sheets get ... --json`, write the raw output to a temporary file first and parse that file with a robust JSON reader. This preserves multiline/control-character cells and keeps the physical row mapping reliable.
5. Prefer a wide bounded read such as `pd_one_review_log!A1:AZ1000` when reporting current non-closed counts; use narrower windows only for targeted follow-up on rows already identified by stable ids.
6. Build the worklist from rows where `review_status` is open/non-closed; include recent digest-window rows only when their `review_status` is non-closed. Ignore legacy `follow_up_needed` for watcher/triage selection because `review_status` is the source of truth.
7. Classify each row into one of:
   - `likely_closeable_after_verification`
   - `needs_admin_approval`
   - `needs_employee_followup`
   - `needs_pd_one_corrective_reply`
   - `automation_or_tooling_issue`
   - `keep_open_pending_work`
   - `unclear_needs_human_review`
6. Report concise counts plus row IDs/physical row numbers, category, requester label, and recommended next action.
7. State explicitly that no Sheet rows were changed and the report is first-pass triage only.

## Guardrails

- `review_log` triage inside supervisor-agent is read-only unless Andy separately approves a specific write/send.
- Do not close rows, edit cells, send corrective employee replies, replay messages, change workflow state, modify permissions, or restart gateways from the triage path.
- Do not mark a row closeable unless row fields or exact nearby evidence indicates handling/completion; approval/queued alone is not completion.
- For no-reply-evidence rows, later same-thread PD One replies are closure evidence only if exact post IDs/timestamps can be verified.
- For onboarding/access gaps, identify the safe next admin action but do not modify policy or message the employee.
- For sensitive/personnel/payroll/private requests, keep scoped and mark approval/safety review needed.
- Avoid broad Mattermost history searches; fetch exact thread/post evidence only when needed to classify a row.

## Replacing the old digest

If Andy approves replacing the n8n digest with supervisor-agent reporting:

1. Update the existing supervisor-agent cron prompt (current PD One implementation: `8ca621fbe187`) to include read-only `review_log` triage workflow and report format.
2. Trigger/read back a live supervisor-agent run and verify `last_status=ok`, `last_delivery_error=null`.
3. Deactivate only the n8n digest workflow (known id: `0a1mny8xzyVc3c08`, `PD One review_log digest v2 (n8n)`) after supervisor-agent reporting is live.
4. Keep the scoped-answer watchdog active (known id: `U7GU223MQ47ocJw0`) unless Andy explicitly asks to replace that alerting path too.
5. Back up/commit the cron prompt change; n8n active-state changes may need separate operational receipts because they are source-system state, not always represented in Hermes cron files.

## Reporting receipt shape

For Andy/admin, keep the setup receipt short:

- supervisor-agent job id, schedule, and last successful run receipt;
- digest workflow active=false readback;
- watchdog active=true readback;
- commit/push receipt for durable cron prompt changes;
- explicit note that no gateway restart and no `review_log` Sheet row edits occurred.

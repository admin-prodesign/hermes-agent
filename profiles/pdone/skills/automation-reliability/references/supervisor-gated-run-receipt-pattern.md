# Gated supervisor run receipt pattern

Use this when a deterministic gate packet has already decided that the expensive supervisor pass is actionable.

## Gate-first execution

1. Treat the packet as the first evidence source. Re-run only the required repair/wrapper/audit commands and any verification that depends on fresh state.
2. Run the safe sequence in order:
   - `pd_one_supervisor_repair.py --json`
   - `pd_one_supervisor_apply_wrappers.py --json`
   - `pd_one_supervisor_audit.py --json`
3. Interpret a zero-action repair/wrapper result as a valid receipt, not as a reason to skip the audit.
4. Do not create/recreate cron jobs, restart gateways, send employee messages, replay external messages, repair credentials, or write source-system data from the supervisor pass.

## Remediation-plan reuse

Before writing a plan, match both the automation identity and the gap/state class. Examples of distinct classes are `missing-live-cron`, `stale-live-source`, and `stale waiting prompt`. Reuse the existing plan path when both match; do not create a duplicate merely because the evidence timestamp changed. If the class differs, create a new narrow plan only when the run is authorized to write local remediation plans.

## Bounded review-log read

- Read the live tab by name with a wide bounded range such as `pd_one_review_log!A1:AZ1000`.
- Save the raw `gog ... --json` response to a temporary file before parsing it. Use a tolerant JSON reader (`strict=False` when necessary) because multiline/control-character cells can invalidate strict parsing.
- Treat the returned Sheets range as authoritative. For example, a request for `AZ1000` may return `AY905`; report that actual bound and do not infer missing trailing columns.
- Build the worklist from non-closed `review_status`, not the legacy `follow_up_needed` field.
- Prefer structured fields (`workflow_outcome_verified`, `project_update_history_verified`, `response_quality_status`, `response_quality_flags`, `access_status`, `answer_sources`) over prose. Workflow rows with unverified outcomes remain `keep_open_pending_work`, even when a reply sounds complete. Reviewer failures with row-local bot-reply evidence belong in `automation_or_tooling_issue`, not duplicate employee follow-up.
- Report counts first, then concise physical row numbers, stable row IDs, requester labels, category, and next action. State explicitly that no Sheet rows were changed for read-only triage.

## Search/validation pitfalls

The `search_files` content pattern is a regular expression, while its file-name search uses glob syntax. Do not pass shell-style `*term*` as a content regex; use a literal term or an escaped/valid regex. After any safe local write, validate JSON and Python/shell syntax; if no durable changes occurred, record that validation was limited to read-only smoke checks and do not create a backup commit just for the run.

## Bounded Sheets parser fallback

For the live `gog sheets get --json` export, keep the raw response in a temporary file and parse it with a header-derived reader. If an ad-hoc `jq` classifier fails twice—especially around `def`/pipeline syntax or loss of the top-level `range` field—stop iterating on shell quoting and switch to a temporary Python helper. The helper should:

1. load the export with tolerant UTF-8/control-character handling;
2. derive every field index from the returned header row;
3. preserve physical row numbers from the returned range and row offset;
4. filter only non-closed `review_status` rows;
5. emit only stable IDs, physical rows, requester labels, and structured triage fields—not request text or transcripts;
6. delete both the export and helper in a `trap`/`finally` cleanup path.

A parser failure is not a source-system failure: report it as a local read-parser retry only after the corrected parser produces a receipt. Do not retain temporary review-log exports or commit the helper as a durable skill artifact unless the helper is intentionally promoted into `scripts/`.

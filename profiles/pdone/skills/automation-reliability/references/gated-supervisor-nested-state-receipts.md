# Gated supervisor: nested state receipts and evidence hygiene

Use this reference during deterministic-gated supervisor runs when a review-log/workflow row needs more than the row's structured fields to distinguish response visibility from verified workflow completion.

## Gate-first bounded sequence

1. Treat the deterministic gate packet as the discovery baseline.
2. Run the narrow repair → wrapper → audit sequence once for current verification; do not repeat broad scheduler discovery already answered by the packet.
3. For a live `review_log` count, request a bounded wide range (normally `pd_one_review_log!A1:AZ1000`) into a temporary file. Parse with a tolerant JSON reader (`strict=False` or an equivalent control-character-safe parser), derive indexes from the returned header row, and use the API-returned range as the authoritative physical bound.
4. Compute physical row numbers from the returned range start row plus each returned data-row offset. Preserve stable `review_log_id`, `mattermost_post_id`, and `root_id` as the cross-run identity; never reuse a physical row number from an older plan.

## Exact-thread and state alignment

For a no-reply or workflow row that may have later evidence:

- Fetch the exact post by `/api/v4/posts/{mattermost_post_id}`.
- Resolve the thread root as `post.root_id or post.id`, then fetch `/api/v4/posts/{root_id}/thread`.
- Confirm the PD One bot user ID from `/api/v4/users/me`; compare bot author IDs and `create_at` timestamps explicitly.
- Never substitute a channel-wide `posts?after=` result for exact-thread evidence.
- Compare every structured workflow item ID in the Sheet with item IDs found in the exact thread and the deterministic state entry. A different but complete item is an automation/tooling identity mismatch, not closure evidence.

## Extracting nested deterministic receipts

Workflow state is often nested below a root key rather than exposed as a flat status. For the exact root object, inspect only the bounded fields needed for triage:

- root key and stored `root_id`;
- `stage` / outcome status;
- completion post receipt (`all_required_complete_posted.id`, `root_id`, timestamp);
- signed-document receipt, when applicable, including nested `post_receipt` or `post.id`, `root_id`, and `file_id`;
- approval count or other deterministic completion marker.

A row can be reported as `likely_closeable_after_verification` only when the row root, exact thread, workflow item, and deterministic state agree, with concrete completion IDs. This is a recommendation category, not authorization to edit the Sheet. Keep the row open and require admin-approved targeted reconciliation.

Conversely, if the exact thread contains later bot posts for another item ID, classify `automation_or_tooling_issue` / workflow-integrity review even if the other item is complete. Do not replay, close, or “correct” either workflow in a read-only supervisor run.

## Evidence hygiene

- Keep temporary Sheets exports and exact-thread JSON in `/tmp` or another explicitly temporary path.
- Emit only concise counts, physical rows, stable IDs, categories, and receipt IDs into the report.
- Do not retain raw transcripts, attachment contents, credentials, or full thread payloads in remediation plans.
- Delete temporary exports and helper parsers after verification, and confirm the files are gone.
- Reuse an existing remediation plan when automation plus gap/state class matches; do not create a new plan solely because timestamps or physical row numbers changed.

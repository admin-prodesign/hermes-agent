# Supervisor evidence extraction recipe

Use this reference for deterministic-gated supervisor runs that need a bounded `review_log` read plus exact Mattermost/workflow verification without mutating business data.

## Evidence pipeline

1. Save the wide `gog sheets get --json` response to a temporary file. Validate it with `python3 -m json.tool`; do not stream multiline Sheets JSON through ad-hoc text parsing.
2. Parse the returned `range` and header row first. The API-returned range is authoritative: a request for `A1:AZ1000` may return `A1:AY934`. Build indexes from the returned headers and calculate physical rows from the returned start row plus the data-row offset.
3. Filter only rows whose `review_status` is not `closed`; ignore `follow_up_needed` for worklist selection. Normalize every cell to a string before regex cleanup or truncation because Sheets may return numbers as integers.
4. Classify from structured fields before prose. Keep workflow rows with `workflow_outcome_verified=no` pending unless exact thread and deterministic state prove completion. Treat `reviewer_failed` / `response_quality_status=error` as tooling issues. Treat explicit approval/scope/access blocks as admin approval. Use corrective-reply triage only for non-workflow no-reply rows after exact-thread verification.
5. For a no-reply or workflow candidate, fetch only:
   - `GET /api/v4/posts/{mattermost_post_id}`;
   - derive `root_id = post.root_id or post.id`;
   - `GET /api/v4/posts/{root_id}/thread`;
   - `GET /api/v4/users/me` to identify the PD One bot.
   Compare `create_at` timestamps and author IDs; never use a channel-wide `posts?after=` query as same-thread evidence.
6. For ECRN/workflow rows, compare the Sheet `workflow_item_id`, exact-root/thread item IDs, and deterministic state key. A complete different item is an automation/tooling identity mismatch, not closure proof. A matching item can be reported as `likely_closeable_after_verification` only with concrete completion and artifact receipts (for example, completion post plus signed-document post/file ID).
7. If a temporary helper extracts IDs with regex, validate it against a known-positive receipt before trusting its output. In generated Python source, `r"E-\d{6}-\d{2}"` is the intended regex; an accidentally double-escaped `r"E-\\d..."` silently returns no matches. Validate both JSON syntax and non-empty stable IDs/receipt IDs.
8. Delete temporary Sheet exports, exact-thread payloads, and helper scripts after verification. Keep only counts, physical rows, stable IDs, categories, recommendations, and durable remediation-plan paths in the final report.

## Receipt shape

Report separately:

- repair result (`ok`, action list, plans written);
- wrapper result (`changed` and actions);
- audit process return code and semantic JSON health (`ok` plus findings);
- authoritative Sheet range and non-closed count;
- exact-thread/state receipt IDs used for any verification candidate;
- explicit confirmation that no Sheet rows were changed in first-pass mode.

Reuse remediation plans by automation identity plus gap/state class. Do not create a new plan solely because physical row numbers or timestamps changed; stable IDs and current evidence belong in the report.

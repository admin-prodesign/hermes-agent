# Supervisor bounded-read and ECRN workflow-identity verification

Use this reference during a deterministic-gated PD One supervisor run when a live `pd_one_review_log` read contains workflow rows, especially ECRN approval rows, or when a scanner says “no reply” but later thread activity may exist.

## Bounded live Sheets read

1. Request a bounded wide range by the live tab name:
   `pd_one_review_log!A1:AZ1000`
2. Save the raw `gog sheets get --json` response to a temporary file before parsing. Parse with a tolerant JSON reader (`strict=False` / replacement handling for control characters); do not pipe raw multiline Sheets JSON through fragile text filters.
3. Treat the response's returned `range` as authoritative. If the request for `AZ1000` returns `A1:AY915`, report `AY915`; do not infer missing columns or rows.
4. Build every field index from the returned header row. Preserve physical row numbers from the returned range start row plus the response-row offset.
5. Select the worklist from non-closed `review_status`; do not use legacy `follow_up_needed` as the watcher source of truth.
6. Keep the temporary export only for parsing/verification, then delete it. Do not place raw Sheet rows or transcripts in remediation plans.

Minimum structured fields for triage are `review_status`, `review_log_id`, `mattermost_post_id`, `root_id`, `user_id`, `category`, `assistant_response_type`, `response_quality_status`, `response_quality_flags`, `access_status`, `message_origin`, `prompting_context`, `workflow_name`, `workflow_item_id`, `workflow_outcome_status`, `workflow_outcome_verified`, `reply_summary`, and `answer_sources`.

## Exact-thread verification

For a row with `no_reply_evidence`, fetch the exact post and exact thread:

- `GET /api/v4/posts/{mattermost_post_id}`
- derive `root_id = post.root_id or post.id`
- `GET /api/v4/posts/{root_id}/thread`

Do not substitute a channel-wide `posts?after=` query. Compare `create_at` timestamps and the verified PD One bot user ID. A later bot post proves response visibility, not workflow completion.

## ECRN identity mismatch rule

For ECRN/workflow rows, compare all three identities:

- review row `workflow_item_id`
- original post/root identity
- later bot/state completion item ID

If the exact thread contains later PD One bot replies but their ECRN item ID differs from the review row (for example, the row is `E-202606-06` while later bot posts reference `E-202607-04`), classify the row as `automation_or_tooling_issue` / workflow-integrity review. Do not classify it as closeable, do not replay the employee message, and do not close or mutate the Sheet. Record a narrow remediation plan with the physical row, stable review-log ID, root/post ID, both item IDs, bot reply IDs, timestamps, and the recommended deterministic-state reconciliation.

If the IDs align, the row still remains pending unless deterministic ECRN state or a structured workflow readback verifies the expected outcome. Approval-token capture, a generic “all approvals complete” reply, or a signed-document marker without matching item/state evidence is not closure proof.

## Remediation-plan handling

Search existing plans by automation identity plus gap class before writing. Reuse a plan for the same `missing-live-cron`, `stale-live-source`, `stale waiting prompt`, `missing bridge`, or reviewer-failure class. A workflow-ID mismatch is a distinct gap from a generic reviewer failure or no-reply row, so it may require one separate narrow plan. Validate the new plan and the registry with `python3 -m json.tool`, sync the Hermes backup, stage only the new plan path, and leave unrelated backup-tree changes unstaged.

## Reporting

Report counts first, then concise physical row numbers, stable IDs, requester labels, category, and next action. State explicitly: “No Sheet rows were changed; this is first-pass triage only.” Mention the authoritative returned range and exact-thread mismatch evidence without pasting raw Mattermost text.

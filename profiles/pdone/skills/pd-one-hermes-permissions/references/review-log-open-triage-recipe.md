# review_log open triage recipe

Use this when Andy/admin asks to review open `review_log` cases. This is a concise operational recipe, not a full incident transcript.

## Goal
Find truly open rows, verify whether each still needs employee/admin follow-up, and prepare targeted Sheet updates only after approval.

## Strict-open filter
Read the `review_log` Sheet headers and rows, then treat a row as open if:

- `review_status` is exactly `open` (case-insensitive), or
- `review_status` is not a closed/done/resolved value **and** `follow_up_needed=yes`.

Do **not** count rows that are already `review_status=closed` just because `follow_up_needed=yes`; report those separately as stale-normalization candidates.

## Response-quality reviewer failures

For normal answered `dm_question` / `channel_interaction` rows, distinguish employee follow-up from quality-pipeline health:

- If the row has normal PD One bot reply evidence and no blocked/no-reply/poor-quality risk signal, do not recommend duplicate employee contact just because `response_quality_status=error` or `response_quality_flags=reviewer_failed`.
- Treat cheap-model reviewer timeout/failure as a backfill/pipeline issue. Recommend suppressing the watchdog alert or normalizing the row (`follow_up_needed=no`, `review_status=closed`) while leaving a concise quality/backfill note for retry if desired.
- Only keep/open the row for human review when the quality result is substantively `review`, `blocked`, or `poor_quality`, or when another explicit risk category, approval/scope block, no-reply evidence, or missing-delivery signal exists.

## Verification patterns

### DM no-reply / onboarding rows
Before recommending a duplicate DM, verify the exact Mattermost DM/channel history around `mattermost_post_id`:

- fetch the original post and channel;
- check for later `pdone` replies in the same root/thread;
- for DMs, also count a later same-channel bot answer on a sibling top-level root (Hermes `/steer` of a follow-up DM). Ignore `Redirected current run` bubbles as evidence;
- check for later top-level onboarding/catch-up messages in the same DM channel when the row is an onboarding/setup case;
- if evidence exists, recommend closing the row instead of contacting the employee again. The scanner (`require_same_thread=False` on DM scans) and source collector should close this class without Andy review.

Useful evidence note shape:

```text
verified YYYY-MM-DD via Mattermost REST: bot reply ids <ids> in original DM thread; later onboarding DM <id> delivered.
```

### ECRN approval-token rows
For rows where the user message is an approval token such as `同意`, verify the deterministic ECRN approval pilot instead of treating it as a normal unanswered channel request:

1. Run the pilot dry-run without sheet sync (example shape):
   `python3 .../tools/ecrn_approval_pilot.py --no-sync-sheet --pages 2 --max-threads 5`
2. Inspect state for the exact root/post/user:
   `state/ecrn-approval-pilot.json`
3. If the state records the post as `status=approve` and the workflow is `stage=complete` or advanced, recommend closing the review row.

Useful evidence note shape:

```text
verified YYYY-MM-DD: ECRN approval pilot dry-run --no-sync-sheet observed root <root_id> / <ecrn_no> at stage=<stage>; state records post <post_id> as approve for user <user_id>.
```

## Update discipline
- Review-log updates are writes. First present a dry-run closure plan to Andy/admin.
- Use targeted `batch-update` ranges only; do not rewrite the sheet.
- Typical targeted columns in the current Sheet layout are `follow_up_needed`, `review_status`, `reply_summary`, and `notes`; always resolve headers rather than assuming fixed column letters if the layout might have changed.
- After approval and update, read back the edited rows and report `review_status`, `follow_up_needed`, and the evidence note receipt.

## Chat-facing report format
Keep admin report concise:

```markdown
Review complete — no writes made yet.
Found N strict-open rows; M closed rows with stale follow-up flag.

| Row | Case | Verification | Recommendation |
|---:|---|---|---|
| 57 | ... | ... | Close / keep open / needs approval |
```

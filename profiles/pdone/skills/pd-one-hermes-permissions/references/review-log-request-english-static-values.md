# review_log `request_english` static-value maintenance

Use this reference when the Mattermost `review_log` translation helper column drifts, needs backfill, or must be retired from a Sheet-level formula.

## Problem pattern

- The review-log writer inserts new rows directly below the header to keep newest-first order.
- A formula like `={"request_english";MAP($P$2:$P,...)}` can be rewritten by Google Sheets after row insertions, drifting to a later range such as `$P$7:$P`.
- The visible symptom is `request_english` values no longer aligning with the adjacent `request_summary` rows.

## Preferred permanent fix

1. Verify current live headers and Q-column formula with formula rendering.
2. Patch `tools/mattermost_review_log.py` so `request_english` is **not** treated as a protected formula column.
3. Ensure the helper populates `request_english` as a static value by live header name:
   - If an `English:` line is already embedded in `request_summary`, split it into `request_english`.
   - If the summary is already English, copy the summary into `request_english`.
   - If the summary contains CJK, translate best-effort and write the static translation.
4. Keep a bounded diagnostic escape hatch such as `--no-translate` for dry-runs/backfills.
5. Backfill only the approved time window first, not the whole sheet by default.
6. Replace `Q1` with plain header text `request_english` so the arrayformula is fully removed.
7. Read back the affected range with formula rendering and confirm there are no formula cells in Q.
8. Run targeted tests and commit/push the durable code change.

## Translation fallback lesson

When replacing a live Sheets `GOOGLETRANSLATE` formula with static helper writes, do not depend solely on an OpenClaw summarizer/agent hop. If the summarizer is unavailable, static values would otherwise be blank for Chinese rows. Add a best-effort Google Translate API fallback (or equivalent approved translation service) so behavior remains close to the old Sheet formula while avoiding row-reference drift.

## Verification receipts to report

- Number of backfilled non-header rows and row range.
- `q_formula_cells: []` from formula-rendered readback.
- Sample adjacent `request_summary` / `request_english` rows.
- Test command and pass count.
- Commit hash and push target.
- State explicitly if no gateway restart was performed.

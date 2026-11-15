# Annual Evaluation / 360 review restricted access

Use this when a PD One employee request asks for Annual Evaluation / 360-degree evaluation data, skill/test review data, reviewer/reviewee scores, or a link to the Annual Evaluation response sheet.

## Known source files

Current canonical Google Forms/Sheets found by Drive search for `Annual Evaluations` / `Annual Evaluation` under the `人事 HR` folder. If these IDs ever stop resolving, repeat Drive search by title rather than assuming the files were deleted:

- Google Form: `良器-年度審核表單 Annual Evaluation`
  - Form ID: `1A1P5JI3_gTXurs89qNq8A0rSPG6iwuHpVmmmjE5_eN0`
  - URL: `https://docs.google.com/forms/d/1A1P5JI3_gTXurs89qNq8A0rSPG6iwuHpVmmmjE5_eN0/edit`
- Response Sheet: `良器-年度審核表單 Annual Evaluation (Responses)`
  - Sheet ID: `1EGzkZgVbF_7a5mcBw3I81NHbxm6SDUKmEBd0ftTwzXQ`
  - URL: `https://docs.google.com/spreadsheets/d/1EGzkZgVbF_7a5mcBw3I81NHbxm6SDUKmEBd0ftTwzXQ/edit`
  - Parent folder: `人事 HR` (`1pdIFvTypBRXZyuS0nBXVRtfji_IyihGZ`)

Important tabs observed in the response sheet:

- `表單回應` — raw form responses. Includes all BUs/departments; sampled headers include `部門 Department`, `填表者 Reviewer`, `被考核者 Reviewee`, score columns, and free-text feedback/translations.
- `Data 2024`
- `分析-分數 Scores`, `分析-分數 Scores 2024`, `分析-只有分數 Only Scores`
- `分析-Final Score-作業員`, `分析-Final Score-幹部`, `分析-Final Score-模修`, `分析-Final Score-技術發展部`
- `Lookup_Viewers`, `Lookup_Reviewers`, `Lookup_Scoring`, `Lookup_Questions`
- BU/output tabs such as `成型幹部`, `品保`

## Access-control rule

The Annual Evaluation workbook includes personnel evaluation data across multiple BUs. Do **not** share the full response sheet or a broad all-BU export with a department requester.

For Leon / Molding (`成型` / `成型部 Injection Molding`) style requests, the intended access pattern is:

1. Treat the full response workbook as HR/admin source material.
2. Inspect `Lookup_Viewers` and the relevant analysis/output tabs before deciding what the requester can see.
3. Build or provide only a restricted view/copy/export for the allowed scope, e.g. Molding/`成型` rows or approved Molding summary tabs.
4. Exclude other BU/departments' raw responses, reviewer details, feedback text, or scores unless Andy explicitly approves broader access.
5. Prefer a filtered copy or controlled summary over granting direct access to the canonical response sheet.
6. Before delivery, verify the filtered artifact has no hidden/all-BU tabs, formulas, pivot/cache ranges, named ranges, protected ranges, notes, or links that expose non-Molding data.

## Filtered-copy recipe

For the reusable mechanics, also load `google-forms` reference `references/sensitive-response-sheet-filtered-copy.md`. Session-proven details for this workbook:

- `表單回應` 2025 raw responses can be filtered by `部門 Department` prefix `成型部`; remove `電子郵件地址` and `填表者密碼 Reviewer Password` from scoped employee-review drafts.
- `Data 2024` can be filtered by `部門 Department` prefix `成型部`; remove password/check/duplicate/internal key columns such as `填表者密碼 Reviewer Password`, `Password Check`, `是否重複?`, `是否不應該考核?`, `Year_Reviewer_Reviewee`, and `Duplicate check` from scoped drafts.
- Final-score analysis tabs group rows by department; after the first `成型部` row, following blank-department rows still belong to the same group until the next nonblank department marker. Carry that marker forward when filtering, otherwise only the first Molding row is kept.
- Include `README`, `Access Audit`, and `Source Inventory` tabs in any admin review draft, and verify post-upload department columns contain zero non-`成型部` values.
- When a department manager may only need results rather than reviewer evidence, prefer a **reduced admin-only final-score/summary draft** before considering any raw-row filtered workbook. For Leon/Molding, the proven safer shape was: `Final Scores + AI Summaries`, `Scores Only`, `README`, `Access Audit`, and `Source Inventory`; no raw response tabs, no free-text feedback rows, no reviewer names, no reviewer email/password/internal check columns, and no non-Molding rows. Generate neutral per-employee AI summaries only from anonymous in-scope feedback patterns, clearly mark them as draft/admin review, and do not share with the requester until Andy approves the exact artifact.
- For 2025 exports of this workbook, do not invent a source final-score field if the sheet exposes only scoring-code inputs and P-KPI fields. Report the calculated 2025 competency-score average separately from the 2025 P-KPI average, and state that 2024 `Source Final Score Avg` comes from the source `Data 2024` final-score field.
- Google Sheets conversions often create default 1000-row tabs; trim blank rows/columns before finishing.
- After building local workbooks or LLM chunk inputs from HR evaluation data, delete temporary files, chunk directories, token files, and JSON records from `/tmp` (or the working directory) before reportback. Keep only the approved Drive artifact and non-sensitive audit notes.

## Safe discovery commands

Read-only Drive discovery:

```bash
gog drive search "Annual Evaluation" --json --account admin@prodesign-group.com --all-drives --no-input --max 50
```

Read spreadsheet metadata/tabs:

```bash
gog sheets metadata 1EGzkZgVbF_7a5mcBw3I81NHbxm6SDUKmEBd0ftTwzXQ --json --account admin@prodesign-group.com --no-input
```

Small header/sample checks only; avoid dumping raw sensitive rows into chat:

```bash
gog sheets get 1EGzkZgVbF_7a5mcBw3I81NHbxm6SDUKmEBd0ftTwzXQ '表單回應!A1:AI3' --json --account admin@prodesign-group.com --no-input
gog sheets get 1EGzkZgVbF_7a5mcBw3I81NHbxm6SDUKmEBd0ftTwzXQ 'Lookup_Viewers!A1:S20' --json --account admin@prodesign-group.com --no-input
gog sheets get 1EGzkZgVbF_7a5mcBw3I81NHbxm6SDUKmEBd0ftTwzXQ '成型幹部!A1:L8' --json --account admin@prodesign-group.com --no-input
```

## Review-log closure implication

For `review_log` open items involving Leon's Molding skill/evaluation data request, finding/admin-uploading source data is not enough to close the employee-facing item. Close only after one of these is true:

- Andy approves a specific controlled Molding-only share/export and PD One verifies delivery to the requester; or
- Andy decides the requester should not receive the data and PD One sends a final refusal/escalation message; or
- the requester withdraws the request.

Record the final Mattermost post ID / share receipt in `review_log` notes when closing.
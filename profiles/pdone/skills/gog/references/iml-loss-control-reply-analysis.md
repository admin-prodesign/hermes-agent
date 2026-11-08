# IML Loss Control Google Sheet: reply-reason analysis patterns

Use this reference when maintaining the Pro-Design IML Loss Control / 紙張損耗異常回覆表 workbook or similar Mattermost-to-Sheets operational analysis workbooks.

## Report positioning

- Treat `回覆原因分類` as **reply reason analysis**, not final root-cause judgment.
- If multiple people reply under one abnormality and give different reasons, counting each valid reply is acceptable only when the report is labeled as “reasons mentioned in replies.”
- Do **not** present `每月原因分類比例` or `原因每月趨勢` as the final cause distribution for abnormality cases unless a separate confirmed-main-cause workflow exists.
- Recommended note for manuals/report tabs:
  > 本表為「回覆原因分析」，依 Mattermost 對話串中的有效回覆內容進行分類與統計。若同一筆異常有多位人員回覆，可能會產生多筆回覆原因分類。本統計用於觀察回覆中常見原因與趨勢，不作為單一異常案件的最終主因判定。

## Classification reference governance

- `原因分類參考` is the rule source; `回覆原因分類` is the generated/classified result.
- When Ivy or an owner edits `原因分類參考`, downstream reports do not automatically reflect old rows until `回覆原因分類` is regenerated using the latest reference.
- Daily sync/update logic should follow this order:
  1. Read the latest `原因分類參考`.
  2. Reclassify/regenerate `回覆原因分類` for relevant replies, not just newly appended rows when classification rules changed.
  3. Let `每月原因分類比例` and `原因每月趨勢` consume the refreshed `回覆原因分類`.
- Add/update status fields when practical:
  - `原因分類參考最後更新時間`
  - `回覆原因分類最後重新整理時間`
  - `本次分類使用的原因分類參考版本`

## Unknown/new reasons

- Do not automatically add official categories to `原因分類參考` just because a reply is hard to classify.
- Put unmatched items under `其他 / 原因不明` or `其他 / 待確認`, then produce a suggested-category review list with:
  - suggested major category
  - suggested subcategory
  - keywords
  - example reply text
  - why existing categories do not fit
- Require Ivy/owner/admin confirmation before adding official categories. This prevents category sprawl such as multiple near-duplicates for the same machine issue.

## Edited original messages and cause timing

- Do not infer that a cause was known at original post time just because the original Mattermost message later contains a cause-like title.
- If an original abnormality message is edited after replies, treat added titles as later notes. Cause analysis should primarily use valid replies/follow-up explanations.

## Parser/report rebuild pitfalls seen in this workbook

- Ignore Markdown heading markers such as `#####`; do not treat them as paper batch IDs.
- Paper batch parser should target actual values like `#293-28`, `#293-22`, `#A935K-1GI(2025)` and preserve slash/parentheses variants when they are part of the batch code.
- Trend charts depend on clean upstream `記錄_拆分整理`; if June/month data is missing in `紙張批號趨勢`, first check whether `記錄_拆分整理` parsed that month correctly before blaming chart settings.
- Rebuild order for the daily automation should be: Mattermost sync/dedupe → read latest `原因分類參考` → regenerate `回覆原因分類` → rebuild `每月原因分類比例` → rebuild `記錄_拆分整理` → rebuild `紙張批號趨勢`. Otherwise rule changes or parsing fixes will not flow through all downstream reports.
- When regenerating `紙張批號趨勢`, preserve the current B2 selected batch when it is still valid; otherwise choose a sensible recent batch for verification. Always read back the selected batch table and confirm expected month rows appear.
- For business-facing views, hide internal tracking fields (`原始訊息ID`, `Thread ID`, `回覆訊息ID`, `來源頻道`) if needed for sync dedupe, but avoid showing them in daily-use sheets unless requested.
- Google Sheets API `addProtectedRange` fails if the sheet already has whole-sheet protection. Before adding warning-only/generated protections, inspect existing `protectedRanges(...,range)`; delete only automation-owned protections and skip adding a duplicate whole-sheet protection when a manual one already exists.
- Add sync status rows when practical so owners can verify whether rule changes flowed through: `原因分類參考最後讀取時間`, `回覆原因分類最後重新整理時間`, `本次分類使用的原因分類參考筆數`, and `回覆原因分類輸出列數`.

## Ivy / IML workbook standing approval handling

- The canonical Mattermost policy/cache may include a document-scoped grant for Ivy Chen on the IML workbook (`imlLossControlSheetNonDeleteWrites=true`). When present for the exact sender id, treat Ivy-requested non-delete workbook repairs in this same Sheet as approved: add/update sheets, formulas, charts, filters, formatting, validation, selectors, and analysis/report tabs.
- Still gate or refuse hard-limit actions: deleting sheets/rows/source data, external sharing, Drive moves, credential/config/gateway/policy changes, unrelated files, source-system writebacks, broad Mattermost history/audit searches, and destructive cleanup unless Andy separately approves.
- After Andy says future fixes like this are approved for Ivy, update/report against the policy-backed grant rather than repeatedly asking for the same non-destructive Sheet repair approval.

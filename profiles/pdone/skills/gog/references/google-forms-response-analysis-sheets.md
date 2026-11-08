# Google Forms response analysis in linked Google Sheets

Use this when Andy asks to turn a reused Google Form survey into a live Google Sheets analysis tab.

## Discovery pattern

1. Read the Google Form with `gog forms raw <formId> --json -a admin@prodesign-group.com --no-input`.
2. Use `linkedSheetId` from the raw Forms response to identify the linked response spreadsheet. Do not assume the response tab is named `Form Responses 1`; Pro-Design forms often use Chinese tab names.
3. Inspect spreadsheet metadata and tab names with `gog sheets metadata <linkedSheetId> --json ...` before writing formulas.
4. Read the response header row from the actual response tab. Google Forms grid questions may produce repeated header text when the form was reused or changed across cycles; formulas should match by header text and filter by timestamp, not rely on fixed column positions.

## Formula design for reused operator grade surveys

For current-cycle grade analysis:

- Add the analysis to an existing/approved summary tab when requested, or create a clearly named analysis tab only after approval.
- Put the cycle start date in a visible control cell, e.g. `B2 = 2026-06-01`, instead of hard-coding it invisibly throughout the sheet.
- Use timestamp filtering so old 2023/2024 responses do not affect the current cycle.
- Score ratings as `A=3`, `B=2`, `C=1` and ignore `N/A`/blank answers in the average.
- Compute the new grade from the numeric average with the agreed rule, e.g. `A >= 2.5`, `B >= 1.5`, else `C`.
- When the response sheet contains duplicated operator columns across form revisions, collect all columns whose header exactly matches `作業員品質等級評估 Operator Quality Rating [<operator>]` after the timestamp filter, then flatten/count ratings. This handles duplicate historical column groups without fixed ranges.
- For operator quality grade analysis requested in Mattermost/channel workflows, prefer transparent `gog sheets batch-update --data-json @payload --input USER_ENTERED --dry-run` followed by the same live command after approval; do **not** wrap the live Sheets write in `execute_code`, because it triggers dangerous-command approval and obscures the actual API command.
- For shift-aware operator analysis, split operators by current operator code (`A*` = day shift / 日班, `C*` = night shift / 夜班), sort each shift by descending current-cycle average, and add a top summary tally for A/B/C/no-current-grade counts per shift.
- Preserve historical average-score records by adding one column per response month (for example `2026-06 avg`, `2024-04 avg`) using month filters such as `TEXT(timestamp_range,"yyyy-mm")=TEXT(month_key_cell,"yyyy-mm")`. Keep current-cycle grade/tally separate from historical monthly averages.
- If the current HR/AppSheet A/C roster contains an operator not present in the Google Form operator question, include the operator in the analysis with a clear note instead of silently dropping them; their formulas will produce blank/no-current-grade until the Form Ranger list is updated.

Example pattern for one operator row, assuming:

- response tab: `作業員品質等級`
- operator name in analysis row cell `A4`
- cycle start date in `$B$2`

```gs
=LET(
  headers,'作業員品質等級'!$A$1:$DB$1,
  data,FILTER('作業員品質等級'!$A$2:$DB,'作業員品質等級'!$A$2:$A>=$B$2),
  vals,TOCOL(FILTER(data,headers="作業員品質等級評估 Operator Quality Rating ["&$A4&"]"),1),
  a,COUNTIF(vals,"A"),
  b,COUNTIF(vals,"B"),
  c,COUNTIF(vals,"C"),
  IFERROR(ROUND((a*3+b*2+c)/(a+b+c),2),"")
)
```

Grade formula:

```gs
=IF($D4="","",IFS($D4>=2.5,"A",$D4>=1.5,"B",TRUE,"C"))
```

## Safety and verification

- The sheet analysis may expose derived grades, so only do it for an approved admin/requester with appropriate scope.
- Do not report individual grades back into a shared Mattermost thread unless explicitly approved; report the sheet/tab/range receipt instead.
- Dry-run or preview formula ranges where practical, then write and read back both formula view and displayed values for a small bounded range.
- If a live write would be routed through a command-approval gate, avoid ending the turn after the blocked action. Report exactly what was stopped/verified and what still needs approval.

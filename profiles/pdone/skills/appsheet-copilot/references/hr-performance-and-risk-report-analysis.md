# HR performance + legacy Risk Report analysis

Use this when Andy asks for an employee's historical mistakes, performance deductions, contract-decision evidence, or a chart combining AppSheet HR performance rows with the old Risk Reporting Google Sheet.

## AppSheet performance table

1. Resolve the person in `HR_Employees` first; do not rely only on current operator code.
   - Match by `Name_ZH`, `Name_EN`, `Name_Nickname`, `Name_ZH_EN`, `Employee ID`, or `PersonID`.
2. Query `HR_Employees_PerformanceRecords` (plural table name) through the prototype app API by `PersonID`:

```appsheet
OrderBy(
  Filter(
    HR_Employees_PerformanceRecords,
    [PersonID] = "<PersonID>"
  ),
  [Timestamp],
  true
)
```

3. Join linked details from `ActivityLog` using `HR_Employees_PerformanceRecords[ActivityLogID]` when the user needs reasons/descriptions, not just counts.
4. Export `json` + `csv` + `xlsx` under the AppSheet exports directory; include both raw rows and a compact summary sheet.

## Terminology

- In Pro-Design employee/performance context, **Risk Reports** (`風險回報`) and **Incident Reports** (`事件報告`) refer to the same operational concept. Employees may use either term.
- Legacy/old incident reports live in the Google Sheets-based Risk Report workbook; newer incident reports live in AppSheet.

## Legacy Risk Report Google Sheet

For the old Google Sheet-based risk reports, use `gog sheets` if Hermes Google OAuth is not configured but `gog` is available.

Typical read-only discovery:

```bash
gog sheets metadata <SPREADSHEET_ID> --json --no-input
```

Then read the relevant data tabs, usually:

```bash
gog sheets get <SPREADSHEET_ID> '風險回報!A1:BK6799' --json --no-input > /tmp/risk_current.json
gog sheets get <SPREADSHEET_ID> '風險回報-歷史!A1:AX2770' --json --no-input > /tmp/risk_history.json
gog sheets get <SPREADSHEET_ID> '員工代號!A1:C120' --json --no-input > /tmp/emp_codes.json
```

Search by the employee's Chinese name first (`Name_ZH`, e.g. `阿弟`) because operator codes can change over time. Use the `員工代號` tab only as supporting evidence for current/recent code mappings; do not treat one current code as complete history. Keep broad code-only matches in a separate “possible code matches” sheet because codes like `C8` can also appear in machine/product/context text and create false positives.

## Combined monthly chart workflow

1. Count legacy Risk Report rows by month from the `時間戳記` field, using strong name matches.
2. Count AppSheet `HR_Employees_PerformanceRecords` rows by month from `Timestamp`.
3. Produce a combined chart with distinct colors, e.g. blue = old Risk Reports, red = AppSheet performance records.
4. Include a CSV with columns:
   - `Month`
   - `Old Risk Report name matches`
   - `AppSheet HR_Employees_PerformanceRecords`
   - `Combined total`
5. In the chart footer, state the source caveat: legacy rows are Chinese-name matches; AppSheet rows are PersonID-backed performance records.
6. Verify chart legibility before delivering: title not overlapping legend, x-axis dates readable, bars visible, totals/peak months correct.

## Reporting cautions

- Distinguish “records involving the employee” from “records proving fault.” Some old risk rows mention an operator who discovered or reported a problem rather than caused it.
- Call out operator-code changes explicitly when found.
- For contract-decision summaries, separate evidence periods: old Risk Reports vs AppSheet performance rows, and state the latest observed record date rather than claiming there were no informal issues.

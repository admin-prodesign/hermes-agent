# Molding monthly KPI sources and formulas

## UNC map (operational, not bonus)

Root (year folder name follows the live share):

`\\sql-srv\製造部\成型課\6-年度資料\KPI.績效統計\{year}-績效統計\KPI-月報`

| What | Path | Use |
| --- | --- | --- |
| Month ERP working copy | `KPI-月報\{n}月\ERP計算-月報(公式)-0127 - 複製.xlsx` | Primary snapshot source when `last_write_time` is in/after that month |
| Department template | `KPI-月報\2026-1226-成型KPI月報(範本).pptx` | Layout reference only; do not paste its Excel pictures |
| Project-team scorecard | `KPI-月報\…成型專案組KPI-月報.xlsx` | Different KPI set (專案經理/工程師). Use only if month cells are populated |
| Cadre / bonus scorecard | `…\績效獎金計算\…幹部KPI-月報` | Red-line. Do not list or open unless Andy excepts that exact UNC |

A `{n}月` directory that still has the empty-shell timestamp is not a month pack.

## Seven official department KPIs

| KPI | Target (standing) | In month ERP copy? | Formula to print |
| --- | --- | --- | --- |
| 總良率 | ≥98.7% | Yes | Prefer total-row `[良率]` = 完工數量 ÷ `[總投入]` (開機不良+成型不良 in `[總不良數]`) |
| 模內貼不良率 | ≤2.5% | Partial | Default: 產品名稱 contains `膜內貼`, `[總不良數]` ÷ `[總投入]`. Official 專案組 is 不良÷貼紙使用數 — only if that month has sticker counts |
| 產能達成率 | ≥93% | Yes | Total-row `[扣時達成率]` = 完工×標時 ÷ (耗用工時秒 − 扣時秒). Not daily-report 達成率（異常扣除後） |
| 換模工單工時達成率 | ≥90% | No | Needs 換模工單 standard vs actual hours. ERP 備註「換模」 is not the KPI |
| 客戶抱怨 | ≤1 | No | ERP退換貨 / owner export. Not AppSheet Case |
| 重工／報廢／呆滯損失 | year ≤6萬 / month ≤5千 | No | Amount ledger. Do not pull finance or bonus trees |
| 工安事故 | 0 | No | Official monthly count ledger. Project-team 工安 sheet is not the department 7-KPI series |

Until the last four have a **non-獎金** file (or a narrow excepted UNC), print **無來源** and keep the deck a snapshot.

## Exception lists (not 對策)

From completion rows in the month (`完工日期` in that calendar month):

- Yield misses: 總投入 ≥300 and 完工÷投入 < 98.7%, sort by 不良 descending. Columns: 品名, 機台, 完工, 不良, 良率, 備註 (truncate).
- IML worst: 膜內貼 in 品名, sort by 不良率.
- Capacity follow-up: low `[扣時達成率]` with 完工≥300; drop 0% rows caused by missing 標時.

Omit 作業員代碼 from the employee-facing table unless the requester asks.

## Headline vs row-weighted

If the total row and a row-weighted recompute disagree on 扣時達成率, **print the total row** and use rows only for lists. 配方標準 stored as text (`28` vs `28±2`) and 缺穴 rows bias a naive weighted sum.

# Pro-Design layout router (PD One)

How `pptx-author` picks a slide layout from this golden.

**Rule:** extra layouts live **on the two existing masters** (Light white / Dark navy). Do not add masters. Prefer **Light** unless the employee asks for a dark / night / navy deck.

**Exact names** below are the `p:cSld/@name` values in the pptx / potx. Use them verbatim when adding a slide.

Light canvas is **white (`#FFFFFF`)** so office printers do not flood a cream field. Paper `#F6F3EC` is for cards and accents only.

---

## How to pick

1. Read the employee ask (ZH or EN).
2. Match **intent keywords** in the table (first strong hit wins).
3. Use the **exact layout name**.
4. Fill bilingual placeholders only. Do not invent McKinsey / client chrome.

If several layouts fit, prefer the more specific graphic (e.g. “illustrate a flow” → `流程 Flow`, not `內文 Content`).

---

## Core text layouts

| Exact name | Purpose | Use when (intent keywords) |
|------------|---------|----------------------------|
| `封面 Title` | Meeting / report cover (ZH title + EN subtitle) | cover, title, 封面, kickoff title |
| `章節 Section` | Divider between chapters | section, divider, 章節, break |
| `內文 Content` | One body column of bullets | notes, bullets, 內文, write-up (no graphic asked) |
| `雙欄 Two Column` | Pair of text columns | two column, 雙欄, status + next, left/right text |
| `結語 Closing` | Decisions and actions close | closing, 結語, wrap up, end slide |

---

## Conceptual graphic layouts

| Exact name | Purpose | Use when (intent keywords) |
|------------|---------|----------------------------|
| `流程 Flow` | Chevron / n-step process (5 steps) | **flow**, process, steps, chevron, pipeline, 流程, illustrate a flow, 步驟 |
| `時間軸 Timeline` | Journey / stages along a time line | **timeline**, journey, roadmap, gantt, milestones, 時間軸, 旅程 |
| `議題樹 Issue tree` | MECE pyramid with branches + leaves | **tree**, issue tree, pyramid, MECE, 議題樹, breakdown, structure the problem |
| `決策樹 Decision tree` | Yes / No branch | decision, yes-no, yes/no, 決策樹, branch, if-then |
| `Venn` | 3 overlapping sets | venn, overlap, intersect, 文氏, 交集, shared vs unique |
| `漏斗 Funnel` | Narrowing stages | **funnel**, conversion, filter, 漏斗, qualify |
| `從到 From-to` | Before → after | **from-to**, from to, before/after, as-is to-be, 從到, 現況目標 |
| `矩陣 2×2` | Prioritization / 2×2 matrix | **matrix**, 2x2, 2×2, prioritize, quadrant, 矩陣, 象限 |
| `循環 Cycle` | Continuous loop (4 nodes) | **cycle**, loop, pdca, continuous improvement, 循環, 迴圈 |
| `階梯 Staircase` | Maturity / rising levels | staircase, stairs, maturity, levels, 階梯, 成熟度 |
| `三驅動 3 drivers` | Three equal drivers / pillars | 3 drivers, three drivers, pillars, 三驅動, 三大 |
| `指標 KPI` | 3–5 big-number metric row | **kpi**, metric, big number, 指標, dashboard row |
| `計分表 Scorecard` | Comparison table | **scorecard**, comparison table, vs, compare rows, 計分表, 對照 |
| `議程 Agenda` | Agenda + next steps / decisions | **agenda**, next steps, decisions list, 議程, 下一步, 決議 |
| `泳道 Swimlane` | Process map / simple RACI | **raci**, swimlane, process map, lanes, 泳道, 權責 |
| `瀑布 Waterfall` | Multi-year / bridge stack (shapes, not an Excel chart) | waterfall, bridge, stack, savings, 瀑布, 增減 |
| `價值鏈 Value chain` | Activity row + support band | value chain, activities, 價值鏈 |
| `四格框架 Framework` | Generic 4-part model around a core | **framework**, model, levers, enablers, 4-part, 框架, 構面 |

---

## Data chart layouts

Native PowerPoint charts (employees edit the workbook). Left plot, right comments, bottom source. Sample series are **SAMPLE / 示意** only. User decks strip that chip and an unused comments card with `scripts/prepare_deck.py`, and they drop the gallery slides. Do **not** use `從到 From-to` for a before/after **data** chart.

| Exact name | Purpose | Use when (intent keywords) |
|------------|---------|----------------------------|
| `長條圖 Bar` | Clustered column, two series | **bar**, column, clustered, 長條, 直條 |
| `堆疊長條圖 Stacked bar` | Composition per category | **stacked**, stack, composition, 堆疊 |
| `折線圖 Line` | Two series over time | **line**, trend, monthly, 折線, 趨勢 |
| `散佈圖 Scatter` | Two groups, two measures | **scatter**, xy, correlation, 散佈, 散布 |
| `前後對比圖 Before / after` | Paired bars (navy before / cyan after) | **before/after**, before after, paired bars, 前後對比, 改善前後 |

---

## Keyword cheat sheet

| Employee phrasing (examples) | Layout |
|------------------------------|--------|
| illustrate a flow / 畫一個流程 / process steps | `流程 Flow` |
| timeline / journey / 時程 | `時間軸 Timeline` |
| issue tree / MECE / 拆解問題 | `議題樹 Issue tree` |
| yes or no / decision branch | `決策樹 Decision tree` |
| venn / overlap | `Venn` |
| funnel / conversion | `漏斗 Funnel` |
| from → to / as-is to-be cards | `從到 From-to` |
| clustered bar / 長條圖 | `長條圖 Bar` |
| stacked / 堆疊 | `堆疊長條圖 Stacked bar` |
| line / monthly trend / 折線 | `折線圖 Line` |
| scatter / xy / 散佈 | `散佈圖 Scatter` |
| before/after paired bars / 前後對比資料圖 | `前後對比圖 Before / after` |
| 2×2 / prioritize / matrix | `矩陣 2×2` |
| cycle / PDCA / loop | `循環 Cycle` |
| maturity / staircase | `階梯 Staircase` |
| three drivers / 三大 | `三驅動 3 drivers` |
| KPIs / big numbers | `指標 KPI` |
| scorecard / compare | `計分表 Scorecard` |
| agenda / next steps | `議程 Agenda` |
| RACI / swimlane | `泳道 Swimlane` |
| waterfall / year-by-year stack | `瀑布 Waterfall` |
| value chain | `價值鏈 Value chain` |
| framework / 4-part model | `四格框架 Framework` |

Do **not** label a 4-part model as a branded “Influence Model.” Use `四格框架 Framework` or `矩陣 2×2`.

---

## Masters

| Master | When |
|--------|------|
| Pro-Design Light | Default. White canvas. |
| Pro-Design Dark | Only if asked (dark, navy, night, 深色). |

Every conceptual name and every data-chart name exists on **both** masters.

# Calibration map — line-clearance raster deck

Fingerprint (not creator, not filename):

- 9 slides, each exactly one PNG, zero `a:t`.
- PNG 1376×768 RGBA. Canvas `16256000` × `9144000` EMU. Firm template is `12192000` × `6858000`.
- Gemini watermark is in the raster only.

The spec is the prompt. English in placeholders is a translation of visible Chinese, not a new requirement. Keep `依造` until the requester confirms `依照`.

| # | Depicts | Relations worth keeping | Disposition | Layout |
|---|---|---|---|---|
| 1 | Cover emblem + title | Title, subtitle, unit, date. Shield does not add a requirement. | Shield `drop`. Text `rebuild-native`. | `封面 Title` |
| 2 | Two states and a gate | Left card annotates 調機階段. Right card annotates 正式量產. Bottom sentences are the bodies, not extra slides. | Gate and gears `drop`. Structure `rebuild-native`. | `從到 From-to` |
| 3 | Four-step clearance flow on a conveyor | Each gate has a name and a one-line effect. Conveyor is style, not a station map. | Conveyor `drop`. Four nodes `rebuild-native`. Not `流程 Flow` (5 slots; do not invent step 5). | `四格框架 Framework` |
| 4 | Injection-machine schematic | Callouts 落下板 and 輸送帶 name the inspection targets. Three cards are when / action / requirement, and the action card points at those two parts. | Machine art `rebuild-diagram`: native labels for those two parts only. Do not crop the blueprint. Do not image-generate a machine. Cards `rebuild-native`. | `三驅動 3 drivers` plus two callouts |
| 5 | Tablet showing two shop photos | Callouts 無調機品 / 淨空確認 annotate the photos. Truncated ids sit under them. Three cards are the rule. | Inner rectangles class `photograph` (black sheet, green aisle). Bezel and neon cards class `generated-graphic`, so `drop`. Copy-crop only if the photo rectangle excludes that chrome and stays legible; otherwise `fetch-original`. Never image-generate the photos. Ids stay truncated: `A-A-20261001-114702-889…`, `A-A-20261001-114546-3e6…`. Cards `rebuild-native`. | `三驅動 3 drivers` |
| 6 | Two role cards | Left text is 品保. Right text is 包裝. Icons repeat the titles. | Icons `drop`. Columns `rebuild-native`. Not swimlane. | `雙欄 Two Column` |
| 7 | Divert: good path vs quarantine | Three cards are the rule. GOOD PARTS / DEFECTIVE PARTS / QUARANTINE ZONE caption the box; they are not four funnel stages. | Box art `drop`. Cards `rebuild-native`. Not `漏斗 Funnel`. | `三驅動 3 drivers` |
| 8 | Comparison matrix | Headers 維度 / 調機階段 / 正式量產. The glowing divider marks the boundary the columns already show. Highlighted cell is the SOP start, as text. | Divider `drop`. Table `rebuild-native`. Not Scorecard. | `內文 Content` + native table |
| 9 | Closing restatement of the four gates | Body sentence is the commitment. Conveyors repeat slide 3. | Conveyors `drop`. Text `rebuild-native`. | `結語 Closing` |

No region on this deck is a default `copy-crop`. The only copy candidates are the two slide-5 photos, and only after a clean crop or the original AppSheet files.

Suggested output name if rendered: `良器-成型-清線標準化-LineClearance.pptx`.

## Not this fingerprint

A one-page Gemini image that asks for English is not these 9 slides. Translate only the strings on that image. Do not add steps, machine ids, or photo rules from this map.

## English shop terms

Use these pairs for injection-line clearance text. They are wording, not extra requirements. Do not say drop plate for 落下板. Painted slide-7 captions do not override different Chinese on the source page.

| 中文 | English |
|---|---|
| 成型產線 / 成型產線清線 | injection line / injection-line clearance |
| 清線 | line clearance |
| 調機 / 調機品 / 正式量產 | setup / setup parts / mass production |
| 落下板 | drop board |
| 輸送帶 | conveyor belt |
| 品保 / 首件 | QA / first piece |
| 包裝人員 / 產品調整到位 | packaging staff / product is adjusted in place |
| 異常品 / 不良品 | nonconforming parts |
| 不良品區 | nonconforming area |

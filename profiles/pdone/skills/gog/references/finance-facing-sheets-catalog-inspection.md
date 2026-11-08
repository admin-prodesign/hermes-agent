# Finance-facing Google Sheets catalog inspection

Use this when Andy asks which company Google Sheets are useful for Finance or another internal analyst group.

## Goal

Produce a finance/analysis-facing recommendation list grounded in live workbook structure, not just Drive titles.

## Safe scope

- Read-only only unless Andy separately approves a write/share change.
- Drive visibility is not sharing approval. Mark restricted/system sheets separately.
- Exclude or down-rank broad-sharing recommendations for HR/personnel/evaluation/payroll/system/admin/security/archive/temp workbooks even when the admin account can read them.
- For Finance, prioritize workbooks with operational quantities, prices/costs, dates, suppliers/customers, products/materials/orders, status/risk, inventory, production, quotations, procurement, energy, maintenance, or quality/loss signals.

## Inspection workflow

1. Inventory accessible native Google Sheets with `gog drive ls --all --query "mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false" --account admin@prodesign-group.com --json --no-input`.
   - On this host, avoid relying on a custom Drive `--fields` mask until the output is verified; some masks may return `nextPageToken` without `files`. Use the default fields first, then narrow only if confirmed.
   - Use Drive query spacing like `mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false`; compact spacing can behave unexpectedly with wrappers.
2. Filter out restricted/system/archive/temp candidates before content inspection. Keep their existence in the catalog only if useful, but do not recommend broad Finance access.
3. For each candidate, open the workbook with `gog sheets get SPREADSHEET_ID A1:Z12 --account admin@prodesign-group.com --json --no-input` to read the default visible tab's headers and small samples.
4. If the default tab is a guide, dashboard, quick-links page, README, or summary-only sheet, also read metadata and inspect likely data tabs by name, such as:
   - `Raw`, `Data`, `原資料`, `資料`, `總表`, `明細`, `記錄`, `回覆`, `Extracted Lines`, `Shipments Raw`, `匯率紀錄`, `美元應付明細`, `生產排程`, `庫存`, `日報表總表`, `模具維修明細表`.
5. Base recommendations on inspected columns and sample rows. In the final reply, cite the exact inspected tabs/columns that support each recommendation.
6. Separate results into:
   - highest-value Finance analysis sources,
   - targeted/secondary sources,
   - restricted/system/not recommended for broad Finance analysis.

## Finance-analysis scoring signals

High-value fields include:

- price/cost/money: `金額`, `單價`, `價格`, `報價`, `匯率`, `成本`, `費用`, `USD`, `NTD`, `price`, `amount`, `cost`, `quote`, `currency`, `rate`.
- quantity/volume/inventory: `數量`, `重量`, `用量`, `庫存`, `出貨`, `產量`, `噸`, `qty`, `quantity`, `stock`, `inventory`, `shipment`, `weight`.
- time: `日期`, `時間`, `月份`, `週期`, `date`, `time`, `month`, `week`.
- counterparty: `客戶`, `供應商`, `廠商`, `customer`, `supplier`, `vendor`, `sales`.
- operational join keys: `工單`, `訂單`, `製令`, `機台`, `模具`, `品名`, `料號`, `BOM`, `產品`, `material`, `order`, `machine`, `mold`, `product`.
- status/risk: `狀態`, `進度`, `異常`, `風險`, `完成`, `status`, `progress`, `risk`, `issue`.

## Reporting pattern

For each recommended workbook, include:

- **Why Finance can use it** / **為什麼財務可用**
- **Inspected columns/tabs** / **已檢查欄位／分頁**
- **Best analyses** / **最適合分析**

For Mattermost group/channel replies, keep the report bilingual English + Traditional Chinese with equivalent substance.
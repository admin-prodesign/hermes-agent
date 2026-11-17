# ERP movement export to slow-stock analysis

Use this when a requester wants a new period to follow an existing slow-stock or obsolete-stock workbook, and the source is an ERP 「各期庫存各項進出表」.

## Order

1. If they say they are giving the movement export and this message has no file, say it did not arrive. Stop re-reading the analysis workbook.
2. Read the print header first: company-code range, year, month range, print time.
3. Sample data rows for grain, sign, cost category, and item-number prefix. Do not treat a truncated preview as the whole sheet.
4. Map each source column to the confirmed rule. List every source column the rule does not name.
5. Stop before a script or a new workbook until they confirm the company code and the unmatched columns.
6. Do not compute amounts from the movement export. Amounts need a separate period-end unit-cost file. A blank price stays blank.

## Grain

One source row is one year, one month, one warehouse, and one item. The analysis row is one item.

Sum every warehouse of the named company before you judge that item. 撥庫 nets only after that sum. Do not count 撥庫 or 分解 as demand.

## Signs

出貨, 製令發料, and 委外發料 are negative in this export. The rules use a positive outbound quantity. Take the magnitude, or net signed issue and return first, then use the positive result. Do not add the raw signed cells and call that outbound.

## Columns the rules split, but this export does not

- 「收料入庫+備品」 includes 備品. Do not drop 備品 unless a separate column exists.
- 「產品結合+入-領」 is one column. Positive is inbound. Negative is issue. Do not invent two source columns.
- 「分解入+領-」 is not demand.

## Columns the default rule does not use

Do not add these into 有效出庫 unless the confirmed rule names them: 委外退料, 製令退料, 不良退庫, 完工退庫, 副產品入庫, 庫存報廢, 盤盈數量, 借入-借出.

直接調整, 庫存報廢, and 盤盈 are separate. Do not treat 直接調整 alone as the whole loss bucket.

## Company code

The print range is the export filter, not the analysis company. Item numbers in the analysis workbook may use a different prefix from the export. Ask for the company code. If that code is outside the print range, say this file is not that company's source. Do not start the script.

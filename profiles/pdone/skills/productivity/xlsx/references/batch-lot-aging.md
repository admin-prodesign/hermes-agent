# Batch-lot balance aging

Use this when the requester wants current batch stock graded as slow-moving, and the sources are a 批號庫存餘額 snapshot plus a 批號進出 pivot. Do not reuse an item-level 各期庫存各項進出表 script. That export has a different grain.

## Read

Read the balance snapshot with `read_file`. That extract is one TSV row per source row. Read the pivot with `pd_one_office_file_ops` action `read`, `max_cols` 23, and `max_rows` high enough for the sheet. A full-width read is unusable because empty month cells explode the result. The 23-column read keeps 進出批號, 倉庫代碼, 單別名稱, and both totals.

Read the print header before you name the company or the year. A range such as A to D is not one company. A company code absent from the data rows is not a zero balance. If the header has a print time and no separate settlement date, the print date is the judgment date. Say that.

## Rules that stay unless the requester writes a different rule

- Current quantity is 批號庫存. Do not subtract 預定保留數. The same reserved number often repeats on every batch of one item. Do not sum it.
- A blank cell is not 0.
- Do not compute an amount. These files have no unit cost.
- Last movement is the later of 最後入庫日 and 最後出庫日. If one side is blank, use the other. If both are blank, the grade is 無法判定.
- Slow stock starts only when last movement is strictly before `EDATE(judgment, -3)`. The boundary day is not slow.
- The grade is 超過N個月, where N is the number of calendar months the age strictly exceeds. On the exact anniversary, subtract 1 from `DATEDIF`. One row gets one grade.
- The join key is 倉別|批號. The movement pivot has no item number. The same key can match more than one item row. Say that.

## Movement pivot

Do not copy the pivot into the spec by hand. Continuation rows leave 批號 and 倉庫代碼 blank. A blank batch inherits the batch above until the next non-blank batch. A non-blank warehouse on that row starts a new key. Do not add that row to the warehouse above. Sum every row in that key. A sum of only the labeled row misses the other side. A blank month is not 0. A blank total on one row means that side is absent on that row, not that the group has no movement.

Use column position, not the last non-blank number on the row. Index 21 is the inbound total. Index 22 is the outbound total. A 存貨結合單 row can have both.

## Net sign column

Use this when the requester asks to add a Jan-Sep net column and label by sign. Do not also apply the date grade or the balance-versus-net comparison.

Net equals the group inbound total minus the group outbound total. The key is 倉別|批號.

- Net above 0: 10月之後異動.
- Net below 0: 期初的餘數.
- Net equal to 0: label 相等，規則未分. The requester confirmed that label. Do not ask again unless they write a different label.
- No movement rows for that key: leave the net blank and mark 無法用這個比較判斷. Do not treat the missing movement as 0.

The same key can match more than one item row. Put the same net on each of those rows. Say that the pivot has no item number.

Do not attach a workbook until every balance data row has a checked net or an explicit unmatched label. A checked sample is not the file. Do not compute an amount.

## Balance versus Jan-Sep net

Use this only when the requester writes a comparison of 批號庫存 with the net, and says to ignore 最後入庫日 and 最後出庫日. Do not keep the date grade in that result. Do not use this section when they ask only for the sign column.

Compare 批號庫存 with Jan-Sep inbound total minus Jan-Sep outbound total. The key is 倉別|批號.

- Balance greater than that net: 有10月之後的異動.
- Balance less than that net: 有更之前的庫存.
- Equal: 這個比較沒有看出10月後異動，也沒有看出更早庫存.
- No movement rows for that key: 無法用這個比較判斷. Do not treat the missing movement as 0.

The difference equals opening stock plus the net change from 1 October through the print date. Both labels can be true together. Still use the requester's labels, and say that limit. Sum the pivot with the continuation-row rule above.

Do not use balance less than Jan-Sep net as the screen for pre-January stagnant stock. That case means some Jan-Sep net increase left after September. It is later movement, not proof that old stock remains.

When the requester wants possible pre-January quantity still in the balance, compare balance with Jan-Sep inbound, not with inbound minus outbound. A balance greater than Jan-Sep inbound is only a candidate. The excess can be stock from before January or receipts after September. These files cannot separate the two. If Jan-Sep inbound is greater than or equal to the balance, do not call that row pre-January stock. Do not use outbound to prove the remainder is old stock. Do not call the row confirmed stagnant without a date or an October-November line.

## Build without a shell

Employee senders cannot use `terminal` or `execute_code`. Write a JSON spec and call `pd_one_office_file_ops` action `write`.

1. Put the judgment serial in one input cell on a 說明 sheet. Every grade formula references that cell.
2. Write data rows as values. Put a short placeholder tuple in the formula columns, the same text on every row.
3. One `replace_all` swaps that tuple for the real formulas. Use `INDEX`/`ROW` so the formula text does not change by row. Do not append long formula rows in small patches. The patch truncates and the sheet ends early.
4. Do not use `MAP`, `LAMBDA`, or another spill formula. The PDF check returns `#NAME?`.
5. On the 說明 sheet, `SUM` the quantity block and `COUNTA` the data rows. Compare both to the source total row and the source data-row count. Bound the ranges to the data block. A full-column sum includes a later block that reuses the column.
6. Add a grade-total sheet with `COUNTIF` and `SUMIF` on the grade text. The grade-quantity sum must equal the source total.

## Check before attach

Convert with `pd_one_office_convert_to_pdf`, then `read_file` the PDF. Attach only when both differences are 0 and the text has no `#NAME?`, `#VALUE!`, or `Err:`. A file that opens is not that check. Attach with `MEDIA:` and an ASCII filename with no spaces.

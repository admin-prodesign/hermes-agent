# Dest pre-assigned days before solve

Andy 2026-10-28: this step is critical. Do not run the solver until it is done and read back.

## Gate

Stop before `solve_preview` if this receipt is missing. A solve that skips it is not valid for writeback.

## Read

Read every target-month dest tab: `日`, `夜`, and `幹部`.

1. Map dates from that tab's date row. Operators use `I=1`. Cadres use `G=1`. Do not reuse day-tab column letters on 幹部.
2. Read cell values and cell notes for every named employee row.
3. Bind each mark or note to the name and employee ID on that same row.

## Write into source `AP:AT`

Match the dest name to `申請日期-當月統計` by the exact name string.

- Visible `V` with no vacation note, or a note that requires rest (example: `該員須體檢須排休`), goes to `HardRestDays` (`AP`).
- A `V` note that means holiday or vacation goes to `FlexRestDays` (`AR`), not hard rest.
- `特` goes to `FlexRestDays` (`AR`).
- `喪` goes to `ProtectedLeaveDays` (`AQ`).
- `訓` goes to `SpecialWorkDays` (`AT`).
- A blank cell whose note forbids rest goes to `MandatoryWorkDays` (`AS`). Do not infer `AS` from an unmarked blank.
- Keep an Andy instruction that is not yet on the dest tab. Do not clear `11/28` flex rest or `11/26` 5S mandatory work just because the dest cell is still blank.

## Receipt

List every noted cell: tab, cell, name, date, value, and note. Read back every changed `AP:AT` cell before solve.

November 2026 example: `115年11月-日!AD15` and `AD16` are day 22 `V` for 蕾查兒 and 觀貝拉. The note requires medical-exam rest. Those days belong in `AP`.

# Quick schedule marker readback

Use this for small read-only questions such as “Which 幹部 are scheduled for training on 7/21?” when the answer is visible in the live monthly schedule sheet.

## Scope

- Read-only schedule lookup only; do not run the solver or write back.
- Treat employee scheduling data as scoped operational data and report only the requested names/shift/status.
- Use the live schedule sheet as the source of truth when the question is about the current written schedule.

## Recommended path

1. Identify the workbook/tab from the scheduling skill/run tracker. For the Injection Molding worker schedule, the workbook is:
   - `良器-成型部-排班表 Injection Molding Shift Schedule`
   - Spreadsheet ID: `10DU9Yro5tDacrjBlOfuGE9JCcYFkC7ribJKuaxnRWhE`
2. Use the PD One safe Sheets read helper rather than ad-hoc shell/API code:
   - script: `/home/prodesign/.hermes/profiles/pdone/scripts/sheets_safe_ops.py`
   - `get` arguments are positional, not flags: `get SPREADSHEET_ID RANGE`
   - add `--print-values` when you need cell contents in the JSON output.
3. Read a bounded range around the target tab, e.g. `115年7月-幹部!A1:AI80`.
4. Locate the date in the date row (for the July 2026 manager tab, row 3 contains day numbers; 7/21 was column `AA`).
5. Scan only real employee rows. Ignore blank rows and summary/footer rows such as `日上班人`, `夜上班人`, counts, notes, and `X` rows.
6. Match the marker requested by the user, e.g. `訓` for training.
7. Return a compact answer grouped by shift, with a short verification note naming the tab/date column. Do not paste the full sheet.

## Example: 2026-07 manager training query

Question: “Which 幹部 are scheduled for training on 7/21, both day and night shift?”

Read: `115年7月-幹部!A1:AI80`

Date 21 column: `AA`

Rows with `AA = 訓`:

- Day shift: 王柏凱 (`AA11`), 呂會銘 (`AA13`), 呂鎮安 (`AA15`)
- Night shift: 楊正義 (`AA20`), 林三原 (`AA21`)

Mattermost shared-channel reply should be bilingual and concise, with equivalent English/Traditional Chinese substance.

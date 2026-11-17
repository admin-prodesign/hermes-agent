---
name: xlsx
description: "Create, read, edit Excel .xlsx spreadsheets and CSVs."
version: 1.0.0
author: Anthropic (adapted by Nous Research)
license: Proprietary. LICENSE.txt has complete terms
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Excel, XLSX, Spreadsheets, Office, Productivity]
    category: productivity
    related_skills: [docx, pdf, powerpoint]
---

# XLSX Skill

Create, read, and edit Excel workbooks — formulas, formatting, charts, data cleaning, and format conversion. Every formula-bearing output must be recalculated and error-free before delivery.

## When to Use

Use this skill any time a spreadsheet file is the primary input or output: opening, reading, editing, or fixing an existing .xlsx, .xlsm, .xltx, .csv, or .tsv file; creating a new spreadsheet from scratch or from other data; converting between tabular formats; cleaning messy tabular data into a proper spreadsheet. Trigger whenever the user references a spreadsheet file by name or path — even casually. For an ERP 「各期庫存各項進出表」 joined to a slow-stock analysis workbook, also load `references/erp-movement-aging.md`. For a 批號庫存餘額 snapshot plus a 批號進出 pivot, load `references/batch-lot-aging.md`. Do NOT trigger when the deliverable is a Word document (`docx` skill), HTML report, standalone script, or Google Sheets API integration. For finance-grade modeling conventions (DCF, LBO, three-statement), the optional `excel-author` skill adds stricter standards on top of this one.

## Prerequisites

```bash
pip install openpyxl pandas "markitdown[xlsx]"
which soffice || sudo apt install -y libreoffice   # formula recalculation (scripts/recalc.py)
```

macOS: `brew install libreoffice`.

## Quick Reference

| Task | Approach |
|---|---|
| **Create** or **edit** with formulas/formatting | `openpyxl` — see gotchas below |
| **Bulk data** in or out | `pandas` (`read_excel`, `to_excel`). A non-ASCII export uses `to_excel`, never `to_csv`. |
| **Quick look** at a sheet | `markitdown file.xlsx` — `## SheetName` per sheet; reads `.xlsm` too. No cell coordinates, so don't plan edits from it. (`read_file` also auto-extracts .xlsx) |
| **Read** a model (formulas *and* values) | two `load_workbook` passes — see gotchas |

> Script paths below are relative to this skill's directory.

## Requirements for every output

- **Professional font** (Arial, Times New Roman) throughout, unless the user says otherwise.
- **Zero formula errors.** Never ship while `recalc.py` reports `errors_found`. If you think an error predates you, prove it: load the *original* with `data_only=True` and look at that cell. An error you introduced looks exactly like one you inherited.
- **Use formulas, never hardcoded results.** Write `sheet['B10'] = '=SUM(B2:B9)'`, not the Python-computed total. The sheet must recalculate when its inputs change.
- **Follow the user's spec literally.** Exact tab names, exact column headers, and the formula they spelled out. A redesign that computes something else fails, however elegant.
- **Deliver a table as xlsx, not CSV.** Do this for every delivered table, including a small one. When the sheet export contains Chinese or other non-ASCII text, write an XLSX file with Unicode shared strings. Do not write a CSV, including a UTF-8 or UTF-8-BOM CSV. Excel on Windows opens a CSV without a BOM as the local code page, and the Chinese text becomes garbled. Use a normal openpyxl `Workbook` or `pandas.DataFrame.to_excel(..., engine="openpyxl")`. Do not use `Workbook(write_only=True)` for that file: write-only mode stores inline strings, not shared strings. After save, open the zip and confirm `xl/sharedStrings.xml` contains the non-ASCII text before you attach the file. If a prior delivery was a CSV, replace it with that xlsx. Do not send another CSV. ASCII-only machine indexes and checkpoint files may stay CSV. A file a person opens in Excel is a sheet export.
- **Document every assumption and hardcoded number** where the reader will see it — a cell comment, or an adjacent cell at a table's end. Cite a real source when one exists; when the number came from the user, say so plainly.
- **A workbook *you create* for someone to fill in** needs a short legend naming which cells to edit, and one example row of realistic values showing the expected format. Never add such a row to a file you were asked to edit.
- **Editing an existing file: match its conventions exactly.** They override every guideline here. Find its designated input cells first — a distinct font color, fill, or shading marks them — write only there, and leave every existing formula untouched.

## Recalculate (mandatory whenever the file contains formulas)

openpyxl writes formulas as strings with **no cached values**. Until you recalculate, every formula cell reads back as `None` to anything reading cached values — `pandas`, `load_workbook(data_only=True)`, and most previewers.

```bash
python scripts/recalc.py output.xlsx [timeout_seconds]   # default 30
```

LibreOffice computes every formula, the file is **rewritten in place**, and you get JSON: `status` (`success` | `errors_found`), `total_formulas`, `total_errors`, and an `error_summary` naming up to 100 cells per error type (`locations_truncated` says how many it withheld — trust `total_errors`, not the length of the list). Fix what it names and run it again. **JSON with an `error` key instead of a `status` means nothing was recalculated**, and only that case exits non-zero — `errors_found` exits 0, so never treat a clean exit as a clean workbook.

**A green recalc proves your formulas *evaluate*, not that they are *right*.** An off-by-one range or a reference to the wrong row yields a clean, error-free file with wrong numbers. Write 2–3 formulas first and check they pull the values you expect, before building out a grid.

**A workbook that links to another file loses those links** if you re-save it with openpyxl and then recalculate. Such a formula reads `='[1]Returns Analysis'!$B$2` — the `[1]` is an index into the workbook's external-reference list, naming a *separate file on disk*, not a sheet. That file is rarely present, so the cell's cached value is the only thing holding its data. openpyxl strips that value on save; LibreOffice then has to resolve the reference for real, fails, writes `#NAME?`, and deletes every link. `recalc.py` refuses to run in that state — copy those cells' values out of the original before you save over them (`--force` overrides, and accepts the loss).

## Choosing formulas that survive verification

LibreOffice implements fewer functions than Excel, and one it cannot evaluate becomes a literal `#NAME?` baked into the file you deliver.

- **Prefer Excel-2007-era functions** — `SUMIFS`, `INDEX`, `MATCH`, `IFERROR`, `SUMPRODUCT` — which need no prefix.
- **Six post-2007 functions work, but only with an `_xlfn.` prefix**, because openpyxl writes your formula into the XML verbatim and Excel stores post-2007 names prefixed (its UI hides the prefix): `_xlfn.TEXTJOIN`, `_xlfn.CONCAT`, `_xlfn.IFS`, `_xlfn.SWITCH`, `_xlfn.MAXIFS`, `_xlfn.MINIFS`. Written bare, each yields `#NAME?`.
- **Never use `XLOOKUP`, `XMATCH`, `SORT`, `FILTER`, `UNIQUE`, `SEQUENCE`, `MAP`, `LAMBDA`, `BYROW`, or `MAKEARRAY`.** LibreOffice cannot reliably evaluate them. `MAP`/`LAMBDA` come back as `#NAME?` in the PDF check, and that error is what you would ship. Spilling functions that do run still have no spill metadata in an openpyxl file, so only the top-left cell gets a value while `recalc.py` can report `total_errors: 0`. Use one `IF`/`EDATE`/`DATEDIF`/`TEXT`/`INDEX`/`ROW` formula per row. Use `INDEX`/`MATCH` for lookups. Sort, filter, and de-duplicate before writing the cells.
- A formula LibreOffice could not parse is written back **lowercased** — a quick tell beside a `#NAME?`.

## openpyxl gotchas

- **Reading a model takes two loads.** `data_only=True` yields cached values with the formulas gone; the default yields formula strings with no values. One pass cannot give you both.
- **`data_only=True` is destructive if you save.** That workbook has no formulas left, so saving replaces every one with a literal — permanently.
- **`data_only=True` on a file openpyxl just wrote returns `None` everywhere** — run `recalc.py` first. (A formula whose result is `""` also reads back as `None`.)
- **Merged cells: write the top-left anchor only.** Every other cell in the range is a `MergedCell` whose `.value` is read-only.
- **`.xlsm` loses its macros unless you pass `keep_vba=True`** to `load_workbook`.
- **A sheet name containing a space must be quoted** in a cross-sheet reference: `='Assumptions Inputs'!$B$5`. Unquoted, it evaluates to `#VALUE!`.

## Financial models

Unless the user says otherwise, or the existing file already does something else.

**Color:** blue text (`0,0,255`) for hardcoded inputs and scenario levers · black for formulas · green (`0,128,0`) for links to another sheet · red (`255,0,0`) for links to another file · yellow fill (`255,255,0`) for key assumptions and cells the user should fill in.

**Numbers:** currency `$#,##0`, with the unit named in the header (`Revenue ($mm)`) · zeros render as `-`, including in percentages (`$#,##0;($#,##0);-`) · negatives in parentheses · percentages `0.0%`, **stored as fractions** (`0.15` renders `15.0%`; storing `15` renders `1500.0%`) · valuation multiples `0.0x` · years as text (`"2024"`, never `2,024`).

**Structure:** every assumption in its own labeled cell, referenced by the formulas that use it (`=B5*(1+$B$6)`, never `=B5*1.05`) · formulas consistent across every projection period, since a lone edited cell mid-row is the commonest silent error · guard denominators that can be zero.

For full investment-banking conventions (balance checks, sensitivity tables, named ranges), install the optional skill: `hermes skills install official/finance/excel-author`.

## Aggregation ranges

Bound `SUMIF` and `SUMIFS` to the block that owns those columns. A later section that reuses the key column and a different metric in the summed column is included by a full-column sum, so the formula evaluates and still misses the source total.

## Join a unit-price sheet onto a formula workbook

When a price sheet is added to an existing analysis workbook:

- Do not overwrite the uploaded cache copy. Deliver a corrected copy of that same workbook: same sheets, new columns appended. Attach it in the origin thread with `MEDIA:`. If they ask where the file is, or say to put the fields into the original and correct it directly, re-attach that copy in the same reply. Say the attachment is their analysis with the added columns. Do not lead with "the original was not changed." A path, a sheet list, or a totals summary is not the file.
- Value each analysis quantity as that quantity times the matched unit price. Do not copy the price sheet's amount column unless that row's quantity equals the analysis quantity. State how many rows match.
- Do not multiply other periods' movements by one period's unit price. Leave that sheet unvalued and name the missing price.
- A scrap or residual amount that uses a period-end price is an estimate. Label it as an estimate, not booked cost.
- A blank price is not zero. `INDEX` of an empty cell returns 0, so a lookup that only uses `INDEX`/`MATCH` values a missing price as zero and hides the gap. Gate with `COUNTIFS` on the price column and criteria `"<>"`; return blank when the price is blank. `SUMIFS` then excludes those rows. Count the blank-price keys separately.
- Quote a sheet name that starts with a digit or contains a space: `'9月期未單位成本'!$E:$E`.
- Keep existing formulas. Append new columns to the right. Update the `autoFilter` ref and every `_xlnm._FilterDatabase` defined name to the new last column.
- If you edit OOXML directly, do not round-trip a sheet that uses shared formulas (`t="shared"`). Insert new `<c>` elements before that row's `</row>`. Formula text has no leading `=`. Escape `<` and `>` once; do not escape an already-escaped entity. Match a row tag so the character after the row number is a quote or whitespace — the text `<row r="2"` is a prefix of `<row r="20"`. After adding formulas, remove `xl/calcChain.xml` plus its content-type and relationship, and set `fullCalcOnLoad="1"`.
- Verify with a calculated export of the summary sheet, not only a Python mirror. A large PDF can fail whole-file text extraction when later pages need OCR; extract the summary page range and check the total against an independent quantity-times-price sum.

## Wide monthly workbooks

When the ask is to reorganize a wide month-group workbook and add dimensions, and the requester did not name the dimensions:

- Leave the original file untouched. Deliver a new workbook.
- Convert each month group to one row per period and item. Keep a blank cell distinct from an explicit zero.
- Name an unlabeled trailing column from the arithmetic it already performs. Do not invent customers, machines, materials, yield, or a later year's volume when the source has none.
- Put every lever on one input sheet (blue font, yellow fill). Other sheets are formulas. Add a reconciliation block whose expected values are the source totals.
- A clean formula evaluation is not a match to the source. Check the reconciliation difference, not only that the formula ran.

## ERP movement export to slow-stock analysis

When the input is an analysis workbook plus a 「各期庫存各項進出表」, load `references/erp-movement-aging.md` before mapping columns or drafting a script.

- If they say the next file is the movement export and this message has no attachment, say the file did not arrive. Do not keep re-reading the analysis workbook.
- Read the print header before you ask for the company again. A range such as A to D is not one company. Ask only for the code the header does not resolve. An item-number prefix in the analysis workbook is not proof that company is in the export.
- Do not draft or deploy the imitating script until they confirm the rules and name that company code.
- A bounded sheet preview is not the full file. Do not report a month, company, or cost category as absent unless the print header excludes it or you have read past the truncation.

## Employee Mattermost sessions

Do not run `recalc.py` through `terminal` or `execute_code` for an employee sender. That posts an approval card into the DM. Follow `document-production-workflows` reference `pd-one-safe-doc-artifact-routing.md` for the typed read, build, and PDF check. Do not `write_file` a `.xlsx`: a text write cannot produce OOXML. Do not attach a path you have not read back. If the sheet contains Chinese or other non-ASCII text, do not fall back to CSV unless the requester explicitly asks for a CSV. Use `pd_one_office_file_ops` when that typed tool is on the surface. It reads and writes bounded local XLSX, CSV, DOCX, PPTX, and the other common Office formats in approved document roots. An active profiled employee has that permission. Do not use terminal or execute_code. If the tool is not on the surface, say the writer is not live. When every data row needs the same formula, write the values with a short placeholder tuple, then one `replace_all` of that tuple. Do not append long formula rows in small patches — the patch truncates and the sheet is short. Use `INDEX`/`ROW` so the formula text is identical on every row. For a batch-balance aging workbook, load `references/batch-lot-aging.md`. When they ask for a Jan-Sep net column labeled by sign, follow that reference's sign rule. Do not keep a prior date grade or a balance-versus-net comparison. Do not ask the employee to approve a shell. An ASCII-only verified file may be named `.csv` only when it is CSV, and the reply must say it is not an xlsx. If they ask where the file is, or say to correct the original directly, the same reply must `MEDIA:` the corrected workbook. Say it is their analysis with the added columns. Do not answer with a location or a totals list.

A distinct-count month matrix is not a sum of source rows. Sibling reason rows often repeat quantity columns; those columns are not additive. For a 膜內貼損耗 ERP sheet, bucket the month from 發料日, not from the date inside 製令單號, unless the requester explicitly asks for 開立日. Count one business key once per month. Count it again in a second month when the chosen date spans two months. The sum of month columns is then higher than the unique-key count; state both, and name the cross-month keys. Write that grid as xlsx with Unicode shared strings, not CSV. Before attach, read the workbook back and check two gates: every data row has the header field count, and each month column sums to an independently counted month total. A missing leading blank shifts every later month. Do not attach the grid until both gates pass. A status reply may state the checked month totals only. If the requester changes the date basis, rebuild from the source workbook and void the prior file.

## Verification

1. `python scripts/recalc.py output.xlsx` → `status: success`, `total_errors: 0`. Skip this shell step for an employee Mattermost sender; use the PDF check in the document-production route instead.
2. Spot-check 2–3 computed cells against expected values (`load_workbook(data_only=True)` *after* recalc).
3. `markitdown output.xlsx` — scan for missing sheets, misplaced headers, leftover placeholders.

## Related skills

`docx` (Word documents), `pdf` (PDF work), `powerpoint` (decks), optional `excel-author` (finance-grade modeling standards).

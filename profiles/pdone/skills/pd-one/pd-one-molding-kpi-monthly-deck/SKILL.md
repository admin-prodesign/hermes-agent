---
name: pd-one-molding-kpi-monthly-deck
description: "Use when rebuilding 成型課 monthly KPI PPTX from KPI-月報."
version: 1.0.0
author: Hermes Agent
license: private
metadata:
  hermes:
    tags: [pd-one, molding, kpi, pptx]
    related_skills: [pd-one-pptx-template-migration, pd-one-firm-template, pptx-author]
---

# Molding monthly KPI snapshot deck

Rebuild the 成型課 monthly KPI PPTX from the **operational** `KPI-月報` Excel tree. Do not restyle Excel screenshots and do not open `績效獎金計算`.

## When to use

- Andy/admin asks to rebuild, backfill, or snapshot 成型課 KPI 月報 / molding KPI PPTX for a named month.
- Coverage questions: which of the seven KPIs PD One can prove from known sources.

Do **not** use for: mold-repair / 模修課 monthly KPI (that deck is `mold-repair-scheduling`); restyling an attached deck onto the golden (`pd-one-pptx-template-migration`); mutating `firm-template.pptx` (`pd-one-firm-template`); a live Portal KPI tab. If the ask is a Mattermost permalink or the room is 模修, resolve the attachment name before listing this UNC. A name containing `模修` or `Mold Repair` is not this skill. An id-only search does not find the post; search a short filename token. Do not open 成型課 `KPI-月報` just because that month folder exists.

## Always-on

- Source tree is `\\sql-srv\製造部\成型課\6-年度資料\KPI.績效統計\{year}-績效統計\KPI-月報`. Paths containing `獎金` / bonus stay closed unless Andy explicitly excepts **that one UNC**. NTFS Read is not a red-line bypass.
- Keep this a **monthly snapshot PPTX**. Do not add a Portal live KPI page until 工單不良／工時／扣時 exist as a system source.
- Do not invent KPIs, do not carry a prior month’s number into a gap cell, and do not write meeting 對策. Exception tables are ERP 備註 / high-NG / low-capacity WOs only.
- Do not paste Excel screenshots. Light master, native tables/charts, `pd_one_pptx_ops.load_firm_presentation` + `save_presentation` only.
- Channel replies: no bonus amounts, no sheet dumps, no file bodies. Cite UNC, byte size, mtime, and the three (or fewer) proven rates.
- Default formulas unless the requester locks otherwise: yield = 完工數量 ÷ 總投入 (includes 開機不良); IML = jobs whose 產品名稱 contains `膜內貼`, 總不良 ÷ 總投入 (not 貼紙使用數 unless that column exists for the month).
- Type size: titles at least 28 pt; body at least 14 pt; 10 pt only for footnotes and sources. Shrink or split text that would overflow, and keep content inside the layout safe area.
- Fonts on nemo: renders approximate Aptos and Microsoft JhengHei via host fontconfig aliases (JhengHei→Noto Sans CJK TC, Aptos→close sans) handled by PD Neo Watch on the host. Do not add host fontconfig files.

## Procedure

1. **Confirm month and tree.** List `KPI-月報` then `KPI-月報\{n}月` with `pd_one_sqlsrv_windows_acl_read` (exact Mattermost sender id). A month folder whose `last_write_time` is still the empty-shell date is not ready.
2. **Fetch the month ERP copy, not the project scorecard.** Expected file: `KPI-月報\{n}月\ERP計算-月報(公式)-0127 - 複製.xlsx`. `2026-成型專案組KPI-月報.xlsx` is a **project-team** scorecard (different KPIs); skip it when its month cells are blank or last-write is stale.
3. **Copy bytes locally.** MCP/ACL wrappers strip `content_b64`. Use the winrm venv + `sqlsrv_readonly` with a long Session timeout, `command=read`, write the xlsx under profile scratch. Authorize with the same exact sender id; fail closed on 獎金 paths.
4. **Read the sheet, not row 1.** Header is the row whose first cell is `完工日期`. Row 1–2 often hold formulas plus a **month total** (`[總投入]`, `[總不良數]`, `[良率]`, `[扣時達成率]`). Prefer those totals for the headline yield and capacity rates; they are what the department pastes. Recompute from completion rows only to verify date span and to build exception lists.
5. **Prove only what this file holds.** See `references/sources-and-formulas.md`. Typical ERP month file can prove 總良率, 模內貼 (provisional), 產能扣時達成率. It cannot prove 換模工單標準vs實際工時, 客訴/退換貨, 報廢/重工/呆滯 $, or 工安 official monthly count. Label those **無來源**.
6. **Build the deck.** Delete cloned sample slides. Light layouts in order: `封面 Title`, `議程 Agenda`, two `指標 KPI`, two `計分表 Scorecard`, `內文 Content` for yield / IML / capacity / gaps, `結語 Closing`. Native tables for WO lists. After `add_table`, strip `a:buChar` / auto-num on every cell and add `a:buNone` — python-pptx cells inherit bullets and the table becomes unreadable.
7. **Save and QA.** `save_presentation` to `artifacts/` (CJK name matching prior months is OK if MEDIA/REST readback has no `%`). Office no-corruption gate, visual QA PNGs, `pptx_image_aspect_check.py`. Attach PPTX (+ PDF preview when produced) to the origin thread.

## Pitfalls

- Do not use Daily Production Report `達成率（異常扣除後）` as 產能達成率 — the official KPI is `(完工×標時)÷(耗用工時−扣時)` = sheet `[扣時達成率]`.
- Do not recompute headline capacity from row `配方標準` when the total row already has `[扣時達成率]`; string/穴數 rows skew the weighted rate.
- Do not treat `data_only` row 5 as the header; locate `完工日期`.
- Do not clone the full 56-slide golden as the deliverable. Load the template, delete samples, add only report slides.
- Do not fill missing KPIs from last month’s deck “so the scorecard looks complete.”

## References

- `references/sources-and-formulas.md` — UNC map, seven-KPI coverage, default formulas.

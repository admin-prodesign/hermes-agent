---
name: pd-one-pptx-template-migration
description: "Use when migrating a user PPTX onto firm-template.pptx."
version: 1.0.0
---

# PD One PPTX template migration

Employee or Andy asks to put an attached deck onto the company template. Numbers and evidence come from the source file. Header/footer must ship on every slide.

Requester-attached `.potx` / `.pptx` restyles (apply that template onto the same-thread source deck, or clone a POTX to PPTX) are same-thread document generation. Use `pd_one_pptx_from_template` (`pptx-from-template`). Do **not** open a PDAPP ticket. Employee-lane `execute_code` / terminal stays blocked.

A new deck from a brief, with no source PPTX, is not this wrapper. `pptx-from-template` can open `templates/firm-template.pptx` for inspect, clone, or apply. Clone copies the sealed package. Apply needs an existing source deck. Neither writes new slide text from a spec. Author with `load_firm_presentation()` / `save_presentation()` through a typed tool. Any active profiled employee may request that deck. Do not require Admin, and do not limit it to Andy. Do not report that every reader refuses the template: `pd_one_pptx_inspect` and local file search exclude `templates/`; that refusal is an allowlist miss.

If every slide is one full-bleed picture and there are zero `a:t` text runs, stop. That is a NotebookLM/Gemini raster export. Reflow contain-fits those PNGs into the body box — pasting slide images. Load `notebooklm-pptx-native-rebuild` and follow that skill. Creator name and a missing Gemini watermark do not clear this fingerprint. Judge the project from the visible cover title, not the PPTX file name. A comparison of their converter output is not a start signal for the rebuild.

## Mandatory path for user POTX/PPTX restyle

1. Copy attachments into approved roots (`cache/documents`, `artifacts`, `tmp`).
2. Inspect: `python3 tools/pd_one_safe_ops.py pptx-from-template --action inspect --mode apply --template <potx> --source <pptx>`
3. Stage a **separate** no-space `.pptx` under `artifacts/` (`--action stage --out ...`). Never overwrite source or template.
   Apply **reflows** titles into the template title placeholder and contain-fits pictures/text into the body box. Do not graft source xfrm. A matching 16:9 size is not a reason to keep source xfrm: the new title still covers content that starts under the old header. Always contain-fit into the body box.
   User POTX uses `--compat` sanitize (do not strip non-rect placeholders; that caused Repair).
   4:3 source onto 16:9 company POTX is expected; reflow contain-fits. Do not treat `slide_size_mismatch` as a hard block.
   When pruning unused POTX/PPTX layouts, keep original master relationship Ids for theme/media. Renumbering master rIds breaks logo/watermark blips even though the PNG is still in the zip.
   Pasted Excel tables and data charts need 內文 Content (or 雙欄). Do not map them onto 指標 KPI / 計分表 Scorecard cards unless the requester asked to see that trial. Do not map the last data slide onto 結語 Closing just because it is last — Closing places the title on the table. Use Closing only when the title is a close.
   Trust the stage `layout_map` and the rendered PNG, not the inspect planned map. Inspect can still send slide 2 to Agenda and the last slide to Closing while reflow does not.
   If a reflow edit does not change the staged SHA, the wrapper imported a different `pd_one_pptx_reflow`. Load the profile sibling by file path (`Path(__file__).with_name`), not `import pd_one_pptx_reflow`. Release `INPUT_ROOTS`, `OUTPUT_ROOTS`, and `FIRM_TEMPLATE` are functions; call them before a path check. Do not patch the release tree.
4. Visual QA the staged file. Attach back to the origin thread. The wrapper does not send.

## Mandatory path for firm-template rebuilds

1. Load `/home/prodesign/.hermes/profiles/pdone/templates/firm-template.pptx` via `pd_one_pptx_ops.load_firm_presentation()`. Never `Presentation()`.
2. Map slides with `/home/prodesign/.hermes/profiles/pdone/templates/LAYOUTS.md` exact `p:cSld/@name` values. Prefer Light.
3. Copy source numbers/tables/charts/images. Do not invent KPIs.
4. Save **only** with `pd_one_pptx_ops.save_presentation(prs, path)`.
   - That call **always** runs `apply_layout_header_footer`, strips empty/SAMPLE SOURCE/FOOTNOTE placeholders, then `require_slide_header_footer` before sanitize/gate.
   - Do not leave SOURCE or FOOTNOTE labels on converted slides when there is no citation. Keep the company `ftr` (`Pro-Design Group · 良器集團`).
   - `python-pptx` skips latent `dt` / `ftr` / `sldNum`. Master rails/logo/hairline can show while date, `Pro-Design Group · 良器集團`, and slide numbers stay blank. Do not deliver in that state.
5. Filename: no spaces. Pattern `良器-<dept>-<topic>-<EN>.pptx`. Mattermost `MEDIA:` of CJK/space paths can store a percent-encoded name that will not open. Prefer REST upload and read back `files[].name` with no `%`.
6. Visual QA + `pptx_image_aspect_check.py`. The Office no-corruption gate fails if any slide using a layout with `dt`/`ftr`/`sldNum` is missing those placeholders (sealed `firm-template.pptx` itself is skipped).

## Already-branded cleanup

A source that already shows the firm logo, date, and `Pro-Design Group · 良器集團` footer is still a rebuild when the ask is to fit the company template. Chrome is not layout. Overflow, a split year-header row, a watermark over the last data row, or a one-language close slide means reflow onto named Light layouts. Do not stop because the master already looks branded.

- Wide KPI or Excel-style tables stay on `內文 Content`. Drop a repeated year-header row that splits across month columns. Keep the table above the footer. Split definitions and month values onto two content slides when one table collides with the footer or watermark. Do not copy a prior-month cell into a blank month.
- `pd_one_pptx_ooxml_text_inspect` truncates long slides. Read the rendered PNG for rows the extract cut off. Leave a cell blank when neither the extract nor the render shows a value.
- "Make the last slide bilingual" means every title and item on that slide has Traditional Chinese and English with the same facts. Three work items use `三驅動 3 drivers` (ZH line plus EN line on each card) or `內文 Content` paired lines. Do not leave English-only bullets under a Chinese title.
- Cover uses `封面 Title`: ZH title plus the source month and presenter. Do not ship a Chinese-only cover when the rest of the deck is bilingual. The title-layout skeleton keeps sample lines such as `成型部 · Injection Molding` and `週會 Weekly review · 內部使用 Internal` when the extracted subtitle is empty. Replace those lines with the source cover facts before delivery. Do not leave the sample subtitle.
- A footer date on the PNG is the template date field evaluated at render time. Read stored `a:t` before you treat that date as the report date. Put the source KPI month and presenter on the cover. Do not copy the render date into the subtitle.
- If the source table is already cut at the right edge, do not invent the missing columns. Say the source already cuts them.

## Type size and fonts

Type size: titles at least 28 pt; body at least 14 pt; 10 pt only for footnotes and sources. Shrink or split text that would overflow, and keep content inside the layout safe area.

Fonts on nemo: renders approximate Aptos and Microsoft JhengHei via host fontconfig aliases (JhengHei→Noto Sans CJK TC, Aptos→close sans) handled by PD Neo Watch on the host. Do not add host fontconfig files.

When a reflow leaves a title or body run under that floor, or a text box past the layout placeholder, split the slide or shorten the copy. Do not shrink below the floor to clear the footer.

## Do not

- Raw `prs.save`.
- Skip HF because the master already “looks branded.”
- Invent accent bars or non-rect `p:ph`.
- Re-emit `MEDIA:` after a verified REST attach.
- Emit `id="7\"` from a raw f-string (`rf"...\""`). PowerPoint Repair is triggered by that invalid attribute. Assign shape ids with a lambda/`'"'`, then assert no `id="\\d+\\"` in slide XML.
- Treat near-identical ~924KB restages as expected: pictures dominate. After backslash ids, dense rIds, pack_ms_office, HeadingPairs, and lastView are fixed, Macintosh Repair may only rewrite datetime cache (`9/30/2026`→`10/1/26`) and recompress PNGs (~+34KB). Do not keep shipping generator clones; deliver the PowerPoint-Repaired package when that is the remaining delta.
- Run `pptx-from-template` on a one-picture-per-slide, zero-text NotebookLM export. That pastes the slide images. Use `notebooklm-pptx-native-rebuild`.
- Answer "the company template cannot be opened" from a `pptx-inspect` or local-file-search refusal of `templates/`. Those roots exclude the sealed file. Use `pptx-from-template` inspect to prove the file, then say the missing piece is authoring, not visibility.

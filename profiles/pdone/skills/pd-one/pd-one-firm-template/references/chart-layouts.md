# Company golden chart layouts

Data-chart templates for the Pro-Design meeting/report golden. Conceptual layouts stay in `LAYOUTS.md`. This file is only the **data chart** family.

## Tokens

| Token | Hex | Role |
|-------|-----|------|
| Navy | `#0E2340` | Titles, primary series, dark fills |
| Blue | `#1D4F91` | Mid series / secondary accent |
| Cyan | `#2AB4C6` | Rail, second series, after-state |
| White | `#FFFFFF` | Light slide canvas |
| Paper | `#F6F3EC` | Cards / SAMPLE chip only — not the canvas |
| Ink | `#142033` | Body on light |
| Muted | `#5B6574` | Axis labels, subtitles |
| Hair | `#D4D7DE` | Grid and spines |

Office typeface: Aptos + Microsoft JhengHei. Linux PNG previews: register **Noto Sans CJK TC** (Regular and Bold) so CJK is not tofu. Do not claim the preview file itself is Aptos.

Canvas for previews: 13.333 in × 7.5 in at 144 dpi (16:9 firm size).

## Slide chrome (data-chart layouts)

Every data-chart layout reserves three regions. Do not let the plot go full-bleed. The SAMPLE chip and the comments card are gallery chrome. `scripts/prepare_deck.py` removes the chip from user decks and removes the card when comments are empty.

| Region | Role |
|--------|------|
| Left ~60% | Chart plot |
| Right rail | Comments / supporting text (重點 / 建議 / 備註) |
| Bottom strip | Footnotes / 資料來源 Source |

Live `\\sql-srv` KPI / 經管會 / 產銷彙整 decks paste Excel charts as EMF/pictures (plus OLE) far more often than native `ppt/charts`. The house KPI chart is **clustered column + target line (combo)** under a data table, full-bleed. Tables/heatmaps outnumber charts. Scatter, pie, stacked bar, and before/after data charts are rare there. Keep the five requested templates; add combo when matching live KPI usage. Template chrome still uses the right comment rail even though those live decks do not.

## Live-usage scan (sql-srv PPTX)

1. Named roots, not a whole-share sweep. Typical: 品保 `KPI報告` / `產銷會議-報告`; 成型課 `4-經管會報告` and `產銷會議報告資料-各部門` 彙整 folders. Skip 財務部 / 管理部 / payroll-HR red lines.
2. `pd_one_sqlsrv_windows_acl_read` `list` is **one directory**. For `*.pptx`/`*.ppt` recurse a named root via the sql-srv read-only helper (`Get-ChildItem -Recurse -File`, filter extension + name tokens like KPI/經管/彙整, cap results). Do not use UNC content-search (no PPTX).
3. Read the file bytes, zip-inventory `ppt/charts/*.xml` vs `ppt/media/*.emf` vs `ppt/embeddings`. Zero chart XML plus many EMF means Excel-paste, not native Office charts.
4. Visual-QA a latest 彙整 deck and one department KPI deck. Classify types (clustered column, combo column+line, line, table-only). Do not transcribe live values, customer names, or money into the reply or into SAMPLE previews.

## Chart set

| Kind | Use | Series |
|------|-----|--------|
| Bar | Clustered category compare | Navy current, cyan prior |
| Stacked bar | Composition per category | Navy / blue / cyan stacked |
| Line | Two series over time | Navy target, cyan actual |
| Scatter | Two groups, two measures | Navy group 1, cyan group 2 |
| Before / after | Same items, paired bars + delta | Navy before, cyan after |
| Combo (house KPI) | Clustered columns + target line | Navy/blue/cyan columns, navy or muted goal line |

Do **not** use `從到 From-to` for a before/after **data** chart. That layout is two conceptual cards plus an arrow.

Do **not** treat `瀑布 Waterfall` as an Excel/Office chart — it is a shape stack.

## Preview render (before golden write)

1. Write PNGs under a durable artifacts dir; do not save the golden yet.
2. Hide top/right spines; y-grid in hair; no invented production KPIs.
3. Bilingual title (ZH then EN name) + SAMPLE / 示意 chip.
4. Vision-QA every PNG: CJK glyphs, legend vs title collision, clipping.
5. Attach each chart with its own `MEDIA:` line.

### Before / after pairing

Horizontal paired bars with `invert_yaxis()`: **smaller y is visual top**. Place Before (navy) at the smaller y and After (cyan) at the larger y so each pair reads Before then After. Put the signed delta at the longer bar, teal/cyan, not overlapping the bar fill.

## After approval

Add the approved chart names on Light **and** Dark (the five plus combo when that was in the preview set). Prefer native Office charts so employees can edit workbook data in PowerPoint. Keep extra layouts on the two existing masters only. Do not write Nemo sealed `firm-template.pptx` from this rebuild. Dark copies of chart XML must run `restyle_chart_for_dark` (paper legend, muted-light axes). Layout SOURCE/FOOTNOTE stay empty; SAMPLE source is gallery-slide-only.

### Product-repo builder (`admin-prodesign/pro-design-ppt-template`)

1. Append kinds to `CONCEPTS` / `CHART_KINDS` in `tools/concept_layouts.py`. Shared chrome is `_chart_shell`: title, subtitle, `p:ph type="chart" idx="2"` on **rect**, comments `idx=3` (重點 / 建議 / 備註), source `idx=4`, SAMPLE chip + comments card as deco (no `p:ph` on non-rect). Footer idx 10/11/12 stay reserved.
2. Native chart **bytes** live under `tools/assets/charts/<kind>/` (chart XML + embedding xlsx + a donor `slides/slide1.xml` graphicFrame). `tools/native_charts.py` copies those parts, strips the sample slide's `Chart Placeholder` `p:sp`, and splices a `graphicFrame` with matching `p:ph type="chart" idx="2"` so the layout box hides. The builder must **not** import python-pptx; regenerator is `tools/_gen_chart_assets.py` (optional, venv with python-pptx).
3. `tools/build_employee_template.py` calls `native_charts.install` before pack, adds chart/xlsx content types, and keeps MS-DOS zip headers.
4. Update `docs/LAYOUTS.md` keyword rows, `tools/render_qa.py` name list, and `LAYOUT_FLOORS` dark paths: From-to light stays layout 12, Cycle light 14; dark files are `n_layouts + 12` / `n_layouts + 14` (28+12=40 and 28+14=42 after the five chart layouts).
5. Rebuild, `python3 tools/validate_pptx.py` both binaries, `python3 -m unittest tests.test_pptx_office`. Tests must assert ten `ppt/charts/chart*.xml` (five kinds × two themes) and `type="chart"` on both masters.
6. Open a dedicated andy-auto PR from `main`. After merge: COM-seal the rebuilt PPTX/POTX, commit sealed bytes if hashes change, then GitHub **release tag** (Town Square pin follows `releases/latest`, not main). Copy Nemo `firm-template.pptx` and replace the pin file-reply only from those sealed bytes. If Open fails on both the candidate and the live sealed golden, stop — INCONCLUSIVE, do not ship the builder zip.

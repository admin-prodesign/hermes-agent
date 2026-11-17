---
name: pptx-author
description: "Build PD One decks on the firm template."
version: 1.1.0
author: Hermes Agent
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [powerpoint, pptx, python-pptx, presentation, pro-design]
    related_skills: [pd-one-firm-template, pd-one-pptx-template-migration, visual-office-qa, pd-one-pptx-office-package]
---

# pptx-author

Build a `.pptx` for PD One with `python-pptx` on the sealed Pro-Design firm template. This is a file on disk, not a live PowerPoint session.

Use this skill for a new deck from a brief. Restyling an attached deck is `pd-one-pptx-template-migration`. Changing the golden itself is `pd-one-firm-template`. A one-picture-per-slide NotebookLM or Gemini export is `notebooklm-pptx-native-rebuild`.

`python-pptx` and `matplotlib` are already pinned in the nemo extra (`python-pptx==1.0.2`, `matplotlib==3.11.2`). Do not add Python packages to the Hermes release environment.

## Output

Write the deck under `artifacts/<name>.pptx` (no spaces in the filename). Return that path. A CJK filename is fine when the Mattermost readback has no `%`.

## Firm template

Always load the sealed template from the profile absolute path. A blank `Presentation()` is not this skill.

`/home/prodesign/.hermes/profiles/pdone/templates/firm-template.pptx`

Prefer `pd_one_pptx_ops.load_firm_presentation()` and `save_presentation()` so sanitize and header/footer cannot be skipped. Any active profiled employee may request a company-template deck. Do not refuse because the room is not Admin. The employee path is a typed tool, not a shell. When they say to generate the report deck directly, attach the PPTX. If no typed tool on the surface calls `load_firm_presentation()` and `save_presentation()` for a new brief, say the writer is missing in a few sentences and stop. Do not stop with "writer is missing" for a picture-only NotebookLM or Gemini deck. Do not substitute `pd_one_office_file_ops` blank `Presentation()`. Do not ask them to approve a shell, and do not send them to Admin. A `pd_one_pptx_inspect` or local-file-search refusal of `templates/` is an allowlist miss, not a missing template.

`save_presentation` clones layout `dt` / `ftr` / `sldNum` onto slides, strips empty or SAMPLE SOURCE / FOOTNOTE / `資料來源` placeholders when there is no real citation, and fails closed if header/footer fields are missing. Do not leave SOURCE or FOOTNOTE labels on slides with no citation. Do not invent accent bars, thin navy or cyan edge strips, or non-rect `p:ph` placeholders. Do not emit `sldLayout type="cust"`.

```python
import sys
from pathlib import Path

sys.path.insert(0, "/home/prodesign/.hermes/profiles/pdone/tools")
from pd_one_pptx_ops import load_firm_presentation, save_presentation

prs = load_firm_presentation()
```

## Named layouts and the two masters

Read exact layout names from `pd-one-firm-template/LAYOUTS.md` (tracked with that skill; same table as `/home/prodesign/.hermes/profiles/pdone/templates/LAYOUTS.md` beside the sealed deck). If those two tables disagree, stop and report the mismatch.

The template has two masters only: **Pro-Design Light** (white canvas, default) and **Pro-Design Dark** (only when the employee asks for dark, night, or navy). Every named layout exists on both masters. Do not add a master.

Pick a layout by intent from the LAYOUTS.md keyword table. The first strong keyword hit wins. Add the slide with that exact `p:cSld/@name`. Walk the chosen master's layouts and match `layout.name`. Never select a layout by its numeric position in the layout list.

```python
def layout_by_name(prs, name, master_name="Pro-Design Light"):
    for master in prs.slide_masters:
        if master.name != master_name:
            continue
        for layout in master.slide_layouts:
            if layout.name == name:
                return layout
    raise KeyError(f"{master_name} has no layout {name!r}")

slide = prs.slides.add_slide(layout_by_name(prs, "流程 Flow"))
```

Fill bilingual placeholders only. Prefer Light.

## Charts

Default to a **native PowerPoint chart** on a data-chart layout from LAYOUTS.md (`長條圖 Bar`, `堆疊長條圖 Stacked bar`, `折線圖 Line`, `散佈圖 Scatter`, `前後對比圖 Before / after`). Employees can edit the embedded workbook. `從到 From-to` is two conceptual cards, not a data chart. `瀑布 Waterfall` is a shape stack, not an Office chart. Sample series on the golden are SAMPLE / 示意; a real deck uses source numbers.

Put the chart in the layout's chart placeholder when it has one.

```python
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import PP_PLACEHOLDER

data = CategoryChartData()
data.categories = ["甲 A", "乙 B", "丙 C"]
data.add_series("本期 Current", (12, 15, 11))
data.add_series("前期 Prior", (10, 13, 9))

chart_shape = next(
    shape for shape in slide.placeholders
    if shape.placeholder_format.type == PP_PLACEHOLDER.CHART
)
chart_shape.insert_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, data)
```

An image chart is the rare case: the layout has no native chart placeholder and a picture is the only way to show the figure. Render it with matplotlib, with Traditional Chinese set to **Noto Sans CJK TC**, and embed the PNG. Do not use an image chart for a layout that already has a native chart.

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Noto Sans CJK TC"
plt.rcParams["axes.unicode_minus"] = False
fig, ax = plt.subplots(figsize=(8.0, 4.5))
ax.bar(["甲 A", "乙 B"], [12, 15])
fig.tight_layout()
fig.savefig("artifacts/charts/bars.png", dpi=144)
plt.close(fig)
```

Set picture width only, or set width and height together only when they match the PNG aspect. Contain and center inside the layout box. Letterboxing is correct. Stretching is not.

## Type size and safe area

Type size: titles at least 28 pt; body at least 14 pt; 10 pt only for footnotes and sources. Shrink or split text that would overflow, and keep content inside the layout safe area.

Set those floors on the runs you write. If a placeholder cannot hold the copy at the floor, cut the sentence or split the slide. Do not go under the floor to force a fit. Stay inside the layout placeholders. Do not draw over the master footer (date, `Pro-Design Group · 良器集團`, slide number) or off the 13.333 in × 7.5 in slide.

## Fonts on nemo

Fonts on nemo: renders approximate Aptos and Microsoft JhengHei via host fontconfig aliases (JhengHei→Noto Sans CJK TC, Aptos→close sans) handled by PD Neo Watch on the host. Do not add host fontconfig files.

Name runs Aptos for Latin and Microsoft JhengHei for Traditional Chinese. The matplotlib image-chart path sets `Noto Sans CJK TC` so the PNG itself has CJK outlines. Do not claim the PNG file is Aptos.

## Numbers

Every figure comes from a source you opened. Footnote the workbook, sheet, and cell when a number came from a sheet. Read the cell with openpyxl. Do not transcribe from memory. Recalculate the workbook before `data_only=True`. Keep that workbook under `artifacts/` as well.

## Images, save, and the required visual check

After every write, sanitize. `python-pptx` can drop the presentation-to-theme relationship and emit gapped rIds, which re-triggers PowerPoint Repair. Prefer `save_presentation(prs, path)`.

```python
from pathlib import Path

Path("artifacts").mkdir(exist_ok=True)
save_presentation(prs, "artifacts/weekly-review.pptx")
```

Then, in order:

```bash
DECK=artifacts/weekly-review.pptx
QA=artifacts/weekly-review-visual-qa
python3 /home/prodesign/.hermes/profiles/pdone/scripts/pptx_office_sanitize.py "$DECK"
python3 /home/prodesign/.hermes/profiles/pdone/skills/visual-office-qa/scripts/pptx_image_aspect_check.py "$DECK"
python3 /home/prodesign/.hermes/profiles/pdone/skills/pd-one-admin/scripts/office_no_corruption_gate.py "$DECK" --skip-libreoffice
python3 /home/prodesign/.hermes/profiles/pdone/skills/visual-office-qa/scripts/office_visual_qa.py "$DECK" --out-dir "$QA"
```

The `office_visual_qa.py` line is a required final step. It renders the deck through LibreOffice to PNG and writes `contact-sheet.png` plus one PNG per slide. Inspect `contact-sheet.png` and every slide PNG before delivery. The no-corruption gate's `--skip-libreoffice` flag only keeps Impress from rewriting the package. It does not replace this render. A non-zero aspect check, gate, or render is a blocker. If the renderer is missing, say so. Do not send an unchecked deck.

`pptx_office_sanitize.py` restores the presentation-to-theme relationship, densifies presentation rIds, strips invalid `p:sldSz type`, unique-ifies `p:ph` idx, drops `sldLayout type="cust"`, removes `p:ph` from non-rect geometries, dedupes identical `ppt/media` parts, and MS-DOS-packs the ZIP. Do not LibreOffice-round-trip the golden or splice COM-repaired XML back into a builder package.

## Skeleton

```python
import sys
from pathlib import Path

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.util import Pt

sys.path.insert(0, "/home/prodesign/.hermes/profiles/pdone/tools")
from pd_one_pptx_ops import load_firm_presentation, save_presentation

prs = load_firm_presentation()
cover = prs.slides.add_slide(layout_by_name(prs, "封面 Title"))
cover.shapes.title.text = "週會 Weekly review"
# subtitle placeholder: month and presenter, bilingual, title runs at least 28 pt

body = prs.slides.add_slide(layout_by_name(prs, "內文 Content"))
body.shapes.title.text = "良率較上月上升 Yield rose versus last month"
for paragraph in body.shapes.title.text_frame.paragraphs:
    for run in paragraph.runs:
        run.font.size = Pt(28)

chart_slide = prs.slides.add_slide(layout_by_name(prs, "長條圖 Bar"))
data = CategoryChartData()
data.categories = ["甲 A", "乙 B"]
data.add_series("本期 Current", (12, 15))
placeholder = next(
    shape for shape in chart_slide.placeholders
    if shape.placeholder_format.type == PP_PLACEHOLDER.CHART
)
placeholder.insert_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, data)

Path("artifacts").mkdir(exist_ok=True)
save_presentation(prs, "artifacts/weekly-review.pptx")
```

`layout_by_name` is the helper above. Body runs stay at least 14 pt. A source line may be 10 pt.

## When not to use this skill

- The user is in a live PowerPoint session and an Office tool can edit that file.
- The ask is to restyle an attached PPTX or POTX (`pd-one-pptx-template-migration`).
- The ask is to change the company golden (`pd-one-firm-template`).
- The deck is one full-bleed picture per slide and has no text runs (`notebooklm-pptx-native-rebuild`).

This skill writes a file. It does not email, upload, or post. The orchestration layer delivers it.

---
name: pptx-author
description: "Build and validate PowerPoint decks headlessly."
version: 1.0.0
author: Anthropic (adapted by Nous Research)
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [powerpoint, pptx, python-pptx, presentation, finance]
    related_skills: [excel-author, powerpoint]
---

# pptx-author

Produce a .pptx file on disk using `python-pptx`. Use when you need to deliver a deck as a file artifact, not drive a live PowerPoint session.

Adapted from Anthropic's `pptx-author` and `pitch-deck` skills in [anthropics/financial-services](https://github.com/anthropics/financial-services). The MCP / Office-JS branches of the originals are dropped — this assumes headless Python.

For the broader, already-shipped PowerPoint authoring skill (slides, speaker notes, embeds, media), see the built-in `powerpoint` skill. This skill is a lighter-weight pattern tuned for model-backed decks (pitch decks, IC memos, earnings notes) where every number must trace to a source workbook.

## Output contract

- Write to `./out/<name>.pptx`. Create `./out/` if it does not exist.
- Return the relative path in your final message.

## Setup

```bash
pip install "python-pptx>=0.6"
```

## Core conventions

### One idea per slide
Title states the takeaway; body supports it. A slide titled "Q3 Revenue" is weak; "Revenue growth accelerated to 14% Y/Y in Q3" is strong.

### Every number traces to the model
If a figure on a slide came from `./out/model.xlsx`, footnote the sheet and cell.

```
Revenue: $1,250M  (Source: model.xlsx, Inputs!C3)
```

Never transcribe numbers from memory or from a summary — open the workbook, read the named range, and bind the deck value to it programmatically when you can.

### Use the firm template (profile absolute path — mandatory)
Always load the sealed firm template from the **profile absolute path** so CWD never silently falls back to a blank `Presentation()`:

`/home/prodesign/.hermes/profiles/pdone/templates/firm-template.pptx`

Prefer `pd_one_pptx_ops.load_firm_presentation()` / `save_presentation()` so sanitize and header/footer cannot be skipped. A company-template deck is for any active profiled employee, not Andy only. Do not refuse the fill because the room is not Admin. The employee path is a typed tool, not a shell. When they say to generate the report deck directly, attach the PPTX. If no typed tool on the surface calls `load_firm_presentation()` and `save_presentation()` for a new brief, say the writer is missing in a few sentences and stop. Exception: a picture-only NotebookLM or Gemini deck is `notebooklm-pptx-native-rebuild`, including its one handoff. Do not stop with "writer is missing" for that fingerprint, and do not substitute `pd_one_office_file_ops` blank `Presentation()`. Do not restate the source workbook as the deck. Do not ask them to approve a shell, and do not send them to Admin. Do not treat a `pd_one_pptx_inspect` or local-file-search refusal of `templates/` as a missing template — those allowlists exclude that folder. `pd_one_pptx_from_template` can open the folder, but clone and apply do not author a new brief. If the live sender gate still blocks an admin sender, report that gate mismatch. Do not ask the shared room to approve a shell, and do not send Andy to Admin as the permission model. `save_presentation` always clones layout `dt`/`ftr`/`sldNum` onto slides (`apply_layout_header_footer`), strips empty or SAMPLE SOURCE/FOOTNOTE/`資料來源` placeholders when there is no real citation, and fails closed if header/footer fields are missing. Do not leave SOURCE or FOOTNOTE labels on generated slides with no content. python-pptx skips those latent placeholders, so PowerPoint would otherwise show master rails/logo/hairline with **blank** Header/Footer fields. User-template migrations: also load `pd-one-pptx-template-migration`. Do **not** invent accent bars, thin navy/cyan edge strips, or non-rect `p:ph` placeholders.

```python
from pathlib import Path
import sys
sys.path.insert(0, "/home/prodesign/.hermes/profiles/pdone/tools")
from pd_one_pptx_ops import load_firm_presentation, save_presentation

# Absolute path first; CWD-relative is a fallback only if the absolute file is missing.
FIRM = Path("/home/prodesign/.hermes/profiles/pdone/templates/firm-template.pptx")
candidates = [FIRM, Path("./templates/firm-template.pptx")]
template = next((p for p in candidates if p.exists()), None)
if template is None:
    raise FileNotFoundError("firm-template.pptx missing")
# Preferred:
prs = load_firm_presentation()
```

### Route layouts with LAYOUTS.md (named golden layouts — mandatory preference)
When illustrating concepts, **prefer the named golden layouts** in `/home/prodesign/.hermes/profiles/pdone/templates/LAYOUTS.md` over drawing freeform shapes. First strong keyword hit wins. Examples: flow / process / 流程 → `流程 Flow`; timeline / 時間軸 → `時間軸 Timeline`; matrix / 2×2 → `矩陣 2×2`. Match exact `p:cSld/@name` values from LAYOUTS.md; fill bilingual placeholders only. Prefer Light master unless the employee asks for dark/night/navy.

**Forbidden:** inventing accent bars / edge strips on cards; putting `p:ph` on non-rect geometries (arrows/ellipses stay ordinary shapes); `sldLayout type="cust"`.

```python
from pathlib import Path

layouts_md = next(
    (p for p in [
        Path("./templates/LAYOUTS.md"),
        Path("/home/prodesign/.hermes/profiles/pdone/templates/LAYOUTS.md"),
    ] if p.exists()),
    None,
)
# Parse LAYOUTS.md intent table; map user ask → exact layout name; then:
# slide = prs.slides.add_slide(layout_by_name(prs, "流程 Flow"))
```

### Charts: PNG-from-model beats native pptx charts
When fidelity matters (the model's chart styling must match the deck exactly), render the chart to PNG from the source workbook and embed the image. Native `pptx.chart` charts are fragile and often don't match firm conventions.

```python
from pptx.util import Inches
slide.shapes.add_picture("./out/charts/football_field.png",
                         Inches(1), Inches(2),
                         width=Inches(8))
```

### Images must not be distorted
Never set picture width **and** height independently unless those two values match the source pixel aspect ratio. Place photos with contain+center inside a layout box (scale = min(box_w/src_w, box_h/src_h), then center). Letterboxing is correct; stretching is not.

After every `prs.save(...)` (or equivalent write), **ALWAYS** sanitize — `python-pptx` can drop the presentation→theme relationship and emit gapped presentation rIds, which re-triggers PowerPoint Repair. Prefer `pd_one_pptx_ops.save_presentation(prs, path)` which wires sanitize+gate so a forgetful model cannot skip them.

```python
from pd_one_pptx_ops import save_presentation
save_presentation(prs, "./out/<name>.pptx")  # HF clone → save → sanitize → gate
```

```bash
# If calling save manually, sanitize is still mandatory before delivery:
python3 /home/prodesign/.hermes/profiles/pdone/scripts/pptx_office_sanitize.py ./out/<name>.pptx
python3 /home/prodesign/.hermes/profiles/pdone/skills/visual-office-qa/scripts/pptx_image_aspect_check.py ./out/<name>.pptx
python3 /home/prodesign/.hermes/profiles/pdone/skills/pd-one/pd-one-admin/scripts/office_no_corruption_gate.py ./out/<name>.pptx --skip-libreoffice
```

`pptx_office_sanitize.py` (required after every save): restore **presentation→theme rel**; densify presentation rIds to sequential `rId1..N`; strip invalid `<p:sldSz type>`; unique `p:ph idx` (no collisions with footer 10/11/12); drop `sldLayout type="cust"`; **remove `p:ph` from non-rect geometries**; dedupe identical `ppt/media` parts; MS-DOS-pack the ZIP. Never surgically splice COM-repaired XML back into a builder package. Do not LibreOffice-round-trip goldens. Gate **FAILS** if theme_rel / dense rIds / cust / nonrect / dupidx checks fail. A non-zero aspect-check or gate is a blocker. Andy 2026-09-11: future PPTX exports must check and correct image distortions before delivery.

### No external sends
This skill writes a file. It never emails, uploads, or posts. Orchestration layers handle delivery.

## Skeleton

```python
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pathlib import Path
import sys
sys.path.insert(0, "/home/prodesign/.hermes/profiles/pdone/tools")
from pd_one_pptx_ops import load_firm_presentation, save_presentation

prs = load_firm_presentation()  # absolute firm-template; never blank Presentation()

# Title slide
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "Project Aurora — Strategic Alternatives"
slide.placeholders[1].text = "Preliminary Discussion Materials"

# Valuation summary slide (title-only layout)
slide = prs.slides.add_slide(prs.slide_layouts[5])
slide.shapes.title.text = "Valuation implies $38–$52 per share across methodologies"

# Add a table bound to model outputs
rows, cols = 5, 4
tbl_shape = slide.shapes.add_table(rows, cols,
                                   Inches(0.5), Inches(1.5),
                                   Inches(9), Inches(3))
tbl = tbl_shape.table
headers = ["Methodology", "Low ($)", "Mid ($)", "High ($)"]
for c, h in enumerate(headers):
    tbl.cell(0, c).text = h

# In a real deck, read these from the model workbook with openpyxl
data = [
    ("Trading comps",     "35", "41", "48"),
    ("Precedent M&A",     "39", "45", "52"),
    ("DCF (base)",        "36", "43", "51"),
    ("LBO (10% IRR)",     "33", "38", "44"),
]
for r, row in enumerate(data, start=1):
    for c, val in enumerate(row):
        tbl.cell(r, c).text = val

# Embed a chart rendered from the model
slide = prs.slides.add_slide(prs.slide_layouts[5])
slide.shapes.title.text = "Football field — current price $42"
slide.shapes.add_picture("./out/charts/football_field.png",
                         Inches(1), Inches(1.8), width=Inches(8))

Path("./out").mkdir(exist_ok=True)
# NEVER raw prs.save alone — sanitize (theme rel + dense rIds) is mandatory.
save_presentation(prs, "./out/pitch-aurora.pptx")
```

## Binding deck numbers to the source workbook

Read named ranges or specific cells from your Excel model so deck numbers never drift.

```python
from openpyxl import load_workbook

wb = load_workbook("./out/model.xlsx", data_only=True)
def nr(name):
    """Resolve a named range to its current computed value."""
    rng = wb.defined_names[name]
    sheet, coord = next(rng.destinations)
    return wb[sheet][coord].value

revenue_fy24 = nr("RevenueFY24")
implied_mid  = nr("ImpliedSharePriceBase")
```

Then build deck content using those values:
```python
slide.shapes.title.text = f"Implied share price of ${implied_mid:.2f} (base case)"
```

Remember to recalculate the workbook before reading it — openpyxl only sees computed values if something has already calculated the sheet. Run the recalc helper in the `excel-author` skill first, or open/save through a real Excel session.

## Slide-type checklist for pitch decks

A typical banking pitch deck follows this structure. Not prescriptive, but useful as a starting skeleton:

1. Cover / title
2. Disclaimer
3. Table of contents
4. Situation overview
5. Company snapshot (the target)
6. Market / sector context
7. Valuation summary (football field) — the money slide
8. Trading comps detail
9. Precedent transactions detail
10. DCF summary
11. Illustrative LBO / sponsor case
12. Process considerations
13. Appendix

## When NOT to use this skill

- Users in a live PowerPoint session with an Office MCP available — drive their live doc instead.
- Non-financial slideware (quarterly all-hands, marketing decks) — use the broader `powerpoint` skill.
- Decks with heavy animation, transitions, or speaker notes — use the broader `powerpoint` skill.

## Attribution

Conventions adapted from Anthropic's Claude for Financial Services plugin suite, Apache-2.0 licensed. Original: https://github.com/anthropics/financial-services/tree/main/plugins/agent-plugins/pitch-agent/skills/pptx-author

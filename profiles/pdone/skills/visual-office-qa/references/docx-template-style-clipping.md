# DOCX template reuse: inherited indentation and clipped text

When generating an English DOCX by reusing a Chinese policy/template as the package and layout base, replacing paragraph text is not enough. Paragraph styles and direct `w:pPr` properties can retain tab stops, numbering, or first-line/hanging indentation that does not appear in `python-docx` text readback but causes LibreOffice to render the first characters outside the left page boundary.

## Prevention

For every rewritten paragraph:

1. Preserve the paragraph properties needed for layout, but remove obsolete `w:numPr` when numbering is rendered explicitly in the new text.
2. Remove stale direct `w:tabs` entries unless the translated layout intentionally uses them.
3. Set `paragraph.paragraph_format.left_indent` explicitly.
4. Set `paragraph.paragraph_format.first_line_indent` explicitly to zero for normal paragraphs. Do not use `None` when the source style may define inherited indentation; `None` means “inherit,” not “zero.”
5. For list items, set both left indent and hanging indent explicitly so visible numbering remains inside the page margin.

Example with `python-docx`:

```python
from docx.oxml.ns import qn
from docx.shared import Inches

ppr = paragraph._p.get_or_add_pPr()
for tag in ("w:numPr", "w:tabs"):
    node = ppr.find(qn(tag))
    if node is not None:
        ppr.remove(node)

paragraph.paragraph_format.left_indent = Inches(0)
paragraph.paragraph_format.first_line_indent = Inches(0)
```

For a hanging list item:

```python
paragraph.paragraph_format.left_indent = Inches(0.25)
paragraph.paragraph_format.first_line_indent = Inches(-0.25)
```

## Verification pattern

After the normal LibreOffice render:

- Reopen the DOCX with `python-docx` and verify expected paragraph/article order.
- Extract PDF text and confirm headings, first/last clauses, and critical contact fields survived rendering.
- Rasterize every page and calculate the bounding box of dark pixels. Unexpected content at `x = 0`, especially in short 15–20 pixel-high intervals aligned with text lines, is a strong clipping signal.
- Compare the raster bounding box with the intended page margins. After fixing inherited indentation, text should begin near the configured left margin rather than at the image edge.
- Re-render after the fix; never accept the structural readback alone because it can remain correct while the rendered text is clipped.

Automated bounding-box checks supplement, but do not replace, manual visual inspection when an image-understanding tool is available.
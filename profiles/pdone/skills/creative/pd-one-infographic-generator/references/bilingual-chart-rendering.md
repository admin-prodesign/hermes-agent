# Bilingual chart rendering recipe

Use this when recreating chart/infographic screenshots with exact Traditional Chinese + English labels and native Mattermost image attachment delivery.

## Key lesson

Do not stop at pasted SVG/HTML source when the user asked for a chart image. If file/artifact tools are available, render a PNG and deliver it with `MEDIA:/absolute/path.png`.

## Recommended workflow

1. Build an editable HTML/SVG artifact under a durable artifact directory, for example:
   - `~/.hermes/profiles/pdone/artifacts/<topic>/<name>.html`
   - `~/.hermes/profiles/pdone/artifacts/<topic>/<name>.png`
2. For CJK text, explicitly embed or reference a Traditional Chinese webfont in the HTML:
   ```css
   @font-face {
     font-family: 'Noto Sans TC Local';
     src: url('./noto-sans-tc-regular.woff2') format('woff2');
     font-weight: 400 900;
   }
   svg { font-family: 'Noto Sans TC Local', 'Noto Sans TC', 'Microsoft JhengHei', Arial, sans-serif; }
   ```
   This avoids missing-glyph boxes when headless Chrome lacks CJK fonts.
3. Render with headless Chrome when available:
   ```bash
   google-chrome --headless=new --no-sandbox --disable-gpu \
     --window-size=1200,720 \
     --screenshot=/absolute/path/chart.png \
     file:///absolute/path/chart.html
   ```
4. QA with vision before delivery. Check:
   - Traditional Chinese glyphs render correctly, not as boxes.
   - English labels are readable.
   - Required status markers are present and correct.
   - No legend/title/card overlap or clipping.
5. Deliver the PNG directly in the final message:
   ```text
   MEDIA:/absolute/path/chart.png
   ```

## Pitfalls

- Headless Chrome may silently substitute a font without CJK coverage, producing square boxes. If this happens, embed a local/downloaded Noto Sans TC WOFF2 in the artifact directory and rerender.
- Long bilingual legends can overlap titles. Move legends below the title or shorten them before rerendering.
- If Pillow/CairoSVG/Matplotlib are unavailable, HTML/SVG + headless Chrome is a reliable deterministic fallback; do not present missing Python packages as a user-facing blocker when Chrome rendering is available.

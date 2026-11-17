---
name: visual-office-qa
description: "Visually QA DOCX and PPTX layout before delivery."
metadata:
  hermes:
---

# Visual Office QA

Use this skill as the final double-check for any generated or edited `.docx` or `.pptx` file before delivery.

## Mandatory no-corruption validation

Before delivering any edited/generated Office document, first verify that the file can open cleanly, not merely that it was written to disk.

For DOCX/PPTX this skill's render pass is mandatory for employee-facing output:
1. Verify the file is a valid ZIP/OpenXML package with expected document/presentation XML and relationships.
2. Reopen with a structural library where possible (`python-docx` for DOCX, PPTX parser for PPTX) and inspect expected edited content.
3. Run the LibreOffice/soffice render/export path below. Treat conversion failures, zero-byte PDFs, missing pages/slides, or renderer errors as blockers.
4. Visually inspect every rendered page/slide for corruption symptoms, blank pages, missing fonts/images, clipped text, broken tables, or layout overflow.
4b. For PPTX with pictures: run `scripts/pptx_image_aspect_check.py <file.pptx>` before delivery. Compare each picture shape's width/height ratio to the embedded source pixels. Relative error above 2% is a distortion blocker — do not deliver. Fix by placing images with contain+center (never independently force both width and height unless they match native aspect). Re-run the checker after the fix.
5. For PPTX/POTX, do **not** LibreOffice-round-trip (Impress rewrites masters). Before delivery run `python3 /home/prodesign/.hermes/profiles/pdone/scripts/pptx_office_sanitize.py <file.pptx>` then `office_no_corruption_gate.py --skip-libreoffice`. That strips invalid `p:sldSz type` (custom 13.333″×7.5″ must not use `type="screen16x9"`) and MS-DOS-packs the ZIP. For DOCX, LibreOffice round-trip remains OK when Word Repair was seen.
6. If the render dependency is unavailable and cannot be installed or Docker fallback is unavailable, explicitly report that limitation before delivery; do not silently send an unchecked Office file.

## Required workflow

1. Finish structural checks first: file opens as a ZIP, expected XML/content exists, stale placeholder/source text is gone, and generated fields are correct.
2. Run `scripts/office_visual_qa.py <file.docx|file.pptx> --out-dir <qa-dir>` from this skill directory, or copy/use the script path directly.
3. Inspect the generated `qa-summary.md` and PNG page/slide renders. Use the `image` tool on `contact-sheet.png` when available, or on the individual PNG renders if the contact sheet is absent. **Inspect every page/slide completely, not just the first screen or first contact-sheet viewport.** If the rendered artifact or preview requires scrolling, scroll from top to bottom and capture/inspect additional screenshots until the entire document has been visually checked.
   - Treat native-vision image loading as a serialized handoff: call the image-inspection tool for one contact sheet or page, record the visual verdict in the immediate next reasoning step, and only then load the next image. Do not batch native-vision image calls with unrelated tool results when a per-image verdict is required.
   - If contact-sheet inspection fails or the sheet is too dense, retry with individual page/slide images in order. Preserve completed page verdicts instead of restarting the whole review.
   - If visual ingestion remains unavailable after the bounded retry, report that visual QA is incomplete and name the uninspected pages/slides; do not emit a raw internal error as the employee-facing answer and do not label the artifact visually approved.
4. Fix visible issues before delivery: clipped/overflowing text, bad line breaks, missing logo/images, unexpected blank pages/slides, broken CJK fonts, table/signature misalignment, wrong page orientation, inconsistent headers/footers, slide elements outside safe margins, repeated/overlapping table text, cramped bilingual headers, or rows whose vertical height is too small.
   - For customer-facing bilingual PPTX decks, also check that title/subtitle/body/card font sizes are consistent across slides; every main message has equivalent English + Traditional Chinese; monolingual evidence screenshots have bilingual framing; chart labels are readable; and the deck does not mix wildly different source-template font scales.
   - Stretched/squashed photos are a release blocker even when CJK and overflow look fine. Square sources in wide slots must stay square (letterbox), not fill the slot by distortion. Portrait sources must stay portrait.
   - If a deck is visually inconsistent across many slides, do not merely fix one obvious overlap. Rebuild or normalize the slide system, render again, and compare the full contact sheet until formatting is consistently presentable.
5. For generated SOP/controlled documents, visually verify dynamic control fields too: version appears once (for example `V1.0`, not `VV1.0`), footer/header date matches the intended current/effective date, filenames agree with visible metadata, and embedded step photos are visible rather than external-link placeholders.
6. Re-run the visual QA after fixes. Deliver the Office file only after the render pass is clean, or explicitly tell the user which visual check could not run and why.

## Dependency behavior

The script needs a renderer. Prefer host LibreOffice/soffice headless export to PDF, then Poppler (`pdftoppm`) or ImageMagick to rasterize pages. If host renderers are missing, the script automatically uses the local Docker fallback image `visual-office-qa:latest` when available, running as the current UID/GID so output files remain editable. The fallback image must include LibreOffice Writer, Calc, Impress, and Draw so Word, Excel, PowerPoint, and drawing inputs can be rendered; rebuild the image after adding or changing those packages. **Unattended handling of untrusted employee attachments (such as production ECRN PDF previews or legacy Word conversion used for ECRN routing) is stricter than general QA:** every Office conversion must use an immutable digest-pinned hardened Docker path and fail closed without automatically falling back to host LibreOffice. Disable networking; use a read-only container and source mount; isolate writable output, HOME/profile, and tmpfs paths; drop capabilities; enable `no-new-privileges`; stream and cap actual input/output bytes; and bound CPU, memory, output file size, PID count, and runtime. If routing reads DOCX XML directly without LibreOffice, perform a bounded classic-ZIP central-directory pre-scan before constructing `ZipFile`, reject ZIP64 in EOCD, central/local header versions, offsets, and extra fields, plus mismatched/tampered EOCD counts or directory bounds, then cap parsed archive entry count, XML entry count, per-entry and aggregate expanded bytes, and compression ratio before reading members. If neither host tools nor the Docker image are available, do not pretend a visual check happened; report the missing renderer and perform the strongest structural checks available instead.

Build/refresh the Docker fallback when host package installation is unavailable:

```bash
docker build -t visual-office-qa:latest /home/prodesign/.hermes/profiles/pdone/skills/visual-office-qa
```

### Component-specific conversion preflight

`libreoffice --version` and a successful DOCX conversion prove only that the core/Writer path works. Before relying on another document class, verify its component and run a real smoke file through the production path:

- Word: Writer plus a DOC/DOCX fixture.
- Excel: Calc (`scalc` or the packaged Calc component) plus an XLS/XLSX fixture.
- PowerPoint: Impress plus a PPT/PPTX fixture.

For each class, require a non-empty output with the expected file signature, successful page/slide metadata, and a visual render containing representative CJK text. Rebuild the fallback image after Dockerfile package changes; then rerun every affected fixture. Do not generalize success from one Office class to another.

## Practical command

```bash
python3 /home/prodesign/.hermes/profiles/pdone/skills/visual-office-qa/scripts/office_visual_qa.py /path/to/file.docx --out-dir /tmp/office-qa
```

When the typed `pd_one_office_visual_qa` tool is the available path, set `output_dir` under an approved document root (`artifacts/` or the profile `tmp/`). `cache/scratch` is rejected, so the render never starts. A footer date on the PNG can be a live date field evaluated at render time. Read the stored `a:t` before you treat that PNG date as the file's date.

## Legacy `.doc` inputs

The visual QA script expects `.docx` or `.pptx`. For legacy Word `.doc` files, first convert to `.docx` and then run the normal QA workflow on the converted file. If host LibreOffice is unavailable and the local Docker fallback image is used, run LibreOffice with a writable mounted home/profile; otherwise the container can fail during profile initialization.

Example conversion pattern:

```bash
docker run --rm -u $(id -u):$(id -g) \
  -e HOME=/work/lo-home \
  -v '/path/to/workdir:/work' \
  visual-office-qa:latest bash -lc \
  "libreoffice -env:UserInstallation=file:///work/lo-home/lo-profile --headless --convert-to docx --outdir /work /work/source.doc"
```

After conversion, perform the same structural checks, render pass, and visual inspection on the `.docx` result before delivery.

The output directory should contain:

- `rendered.pdf` from LibreOffice/soffice.
- `page-001.png`, `page-002.png`, etc. or slide PNGs.
- `contact-sheet.png` when Pillow or ImageMagick montage is available.
- `qa-summary.md` with commands, status, page count, and next manual inspection steps.

## Troubleshooting missing CJK fonts in rendered Office output

If DOCX/PPTX structural checks pass but the visual render shows Traditional Chinese/Japanese/Korean text as square boxes/tofu, fix the renderer font environment before delivery; do not treat the document as visually approved. Check available fonts with `fc-match 'Noto Sans CJK TC'` and `fc-list :lang=zh family`. In Hermes profile-sandboxed runs, `$HOME` may be `/home/prodesign/.hermes/profiles/pdone/home`, so user fonts must be available under that profile home (for example `$HOME/.fonts/` or `$HOME/.local/share/fonts/`) and `fc-cache -f -v` must be run there. A working fallback is to install/copy `NotoSansCJKtc-Regular.otf` and `NotoSansCJKtc-Bold.otf`, set the generated Office runs to `Noto Sans CJK TC`, rerender, and visually verify that CJK glyphs are readable. If signature labels wrap into stacked words, widen the label columns and rerender before you replace the table. For the company announcement template, keep the six-cell signature row. A second page whose lower half is blank is acceptable when it keeps a bilingual pair and the signature row together. Do not leave one language of that pair against the footer.

## Troubleshooting visual inspection ingest

If `office_visual_qa.py` creates PNG/contact-sheet artifacts but the `image` tool fails with `Failed to optimize image` or `Optional dependency sharp is required`, check OpenClaw's runtime image optimizer dependency rather than the Office renderer.

1. Verify renderer output exists: `qa-summary.md`, `rendered.pdf`, `page-*.png`, and preferably `contact-sheet.png`.
2. Check sharp from OpenClaw's package context:
   ```bash
   cd /home/prodesign/.npm-global/lib/node_modules/openclaw
   node --input-type=module - <<'JS'
   const mod = await import('./dist/extensions/media-understanding-core/image-ops.js');
   const fs = await import('node:fs/promises');
   const ops = mod.createMediaAttachmentImageOps({maxInputPixels: 100000000});
   const b = await fs.readFile('/path/to/contact-sheet.png');
   console.log(await ops.getImageMetadata(b));
   console.log((await ops.resizeToJpeg({buffer:b,maxSide:1024,quality:80,withoutEnlargement:true})).length);
   JS
   ```
3. On older x64 CPUs, latest `sharp` may fail with `Prebuilt binaries for linux-x64 require v2 microarchitecture`; install `sharp@0.32.6` under the OpenClaw package instead:
   ```bash
   npm install --prefix /home/prodesign/.npm-global/lib/node_modules/openclaw sharp@0.32.6
   ```
4. Restart the gateway only after Andy approves; then re-run the `image` tool on `contact-sheet.png` before declaring the visual-inspection handoff ready.

Do not use image-generation models like `gpt-image-2` as the visual QA judge; they generate/edit images and do not replace the image understanding tool.

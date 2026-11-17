---
name: notebooklm-pptx-native-rebuild
description: "Use when converting or comparing a NotebookLM PPTX."
version: 1.0.0
author: Hermes Agent
license: private
metadata:
  hermes:
    tags: [pptx, notebooklm, template, pro-design]
    related_skills: [pd-one-pptx-template-migration, pd-one-firm-template, pptx-author, document-production-workflows]
---

# NotebookLM PPTX → native firm-template objects

## When to Use

- A requester attaches a NotebookLM or Gemini PPTX and asks to put it on the company template as editable slides, not as pasted pictures. Any active profiled employee. No admin role. Same-thread drafting needs no ticket when `save_presentation` can run. If it cannot, use the handoff below. Do not tell the employee the conversion is done.
- Unzip shows one full-bleed picture per slide and zero text runs. Load this skill before `pptx-from-template`.
- The ask is to compare their converter output with a company-format result. Compare first. Do not treat that ask as a start signal.
- Do not use for a deck that already has real text boxes, tables, or charts (`pd-one-pptx-template-migration`), or for changing the golden itself (`pd-one-firm-template`).
- A single Gemini Notebook image is not this rebuild. Do not open the 9-slide line-clearance map and add its steps, ids, or painted captions. Use the shop-term table in `references/line-clearance-raster-map.md` for wording only. If they want the same picture in English, with icons and font sizes kept, edit that image in place (`pd-one-infographic-generator`). A text SOP is only for an ask that does not require the picture to stay. This skill starts only when the requester wants editable company-template slides from a NotebookLM/Gemini PPTX fingerprint.

A NotebookLM / Gemini export is usually one full-bleed PNG per slide and zero text boxes. Putting that file through `pptx-from-template` contain-fits each PNG into a body box. That is pasting slide images. Do not do it.

Rebuild from a slide spec, not from a style-clone prompt and not from pasted pictures. Vision plus OCR writes the spec: exact text, what the slide depicts, and which text belongs to which region. That spec is the only prompt for the company deck. Each picture region then gets a disposition: copy-crop, fetch-original, rebuild-native, rebuild-diagram, or drop.

Not a golden mutation (`pd-one-firm-template`). Not a restyle of a deck that already has real text boxes (`pd-one-pptx-template-migration`).

## Detect before any restyle tool

Fingerprint (all of these):

- Every slide `spTree` has exactly one `p:pic` and zero `a:t` text runs.
- `docProps` `Words` = 0, `Notes` = 0, `TitlesOfParts` are generic (`PowerPoint 簡報` or equivalent).
- Canvas may be 16:9 but not the firm size. The calibration file is `16256000` × `9144000` EMU; firm-template is `12192000` × `6858000`. Size mismatch is irrelevant once objects are rebuilt. Do not scale the PNG onto the template.

Do **not** use `dc:creator` as the signal. An employee can open the export in PowerPoint; creator will be their name.

A `Gemini Notebook` watermark in the raster confirms the fingerprint. Absence does not clear it.

If any slide already has real text boxes, tables, or charts, stop this skill and use `pd-one-pptx-template-migration` for those slides. Do not OCR over text that is already in XML.

## Do not

- Call `pd_one_pptx_from_template` / reflow / `--action stage` on this fingerprint. Reflow pastes the slide PNG.
- Embed the source PNG, a cropped “almost full slide”, or the Gemini watermark.
- Style-clone NotebookLM navy / cyan / orange. Record the source design in the spec; company color comes from the Light layout.
- Image-generate a replacement for an evidence photo, an AppSheet screenshot, or a measured drawing. That fabricates the record.
- Bake words into a generated picture. Text stays in editable boxes. The picture shows the object or the relationship only.
- Paste the full-slide PNG, or a crop that still includes the Gemini watermark.
- Force every slide into a named layout when that layout drops the picture the text depends on. Use a named layout when its graphic already matches (from-to, two columns, closing, a real table). Otherwise compose on the Light master: generated concept graphic plus editable text in similar positions.
- Invent a step, KPI, role, part, or fifth chevron that is not in the spec. Leave no SAMPLE placeholder text.
- Treat a one-page Gemini image as the 9-slide calibration deck. Slide 7 captions (GOOD PARTS / DEFECTIVE PARTS / QUARANTINE ZONE) do not replace different Chinese on another page. 不良品區 stays nonconforming area unless that page says quarantine.
- Map by the English label painted on the illustration (`Quarantine Funnel` ≠ `漏斗 Funnel`).
- Put a comparison matrix on `計分表 Scorecard` or `指標 KPI`. Scorecard headers are Item / Target / Actual / Status. A different matrix is a native table on `內文 Content`.
- Use `泳道 Swimlane` for two role cards. Swimlane is 3 roles × 4 stages.
- Use `流程 Flow` when the source has 4 steps if that would invent a fifth step. A 4-step picture can be a generated 4-gate graphic with editable labels. Do not invent step 5 to fill `流程 Flow`.
- Crop device chrome, a watermark, or a neon frame along with the photo. If a tight crop cannot separate a real photo from the mockup, disposition is `fetch-original`, not copy-crop and not image-gen.
- Complete a truncated id. Keep the visible characters and the ellipsis.
- Set picture width and height independently. Contain-fit.
- Silently “repair” source wording. Flag a suspected typo and keep the source string until the requester confirms.
- Overwrite the source PPTX or `firm-template.pptx`. Raw `prs.save`. Dark master unless asked.
- Gate this skill on admin role or a dangerous-command prompt. Any active profiled employee may ask in an enabled channel or DM. Same-thread drafting needs no ticket when the writer can run. `save_presentation` is the writer for this conversion for every profiled employee, not an admin privilege.
- Ask the employee to upload the package to an admin cloud folder so you can browse it. Read the files attached in the thread.
- Install their converter, start their server, or use a key from their notes. A package review is read-only.
- Use only the phrase 「公司格式重建」 as the ask. Define the new file first.
- Tell an employee to ask Andy. There is no deferred tool that calls `load_firm_presentation` or `save_presentation`. `pd_one_office_file_ops` PPTX write builds a blank `Presentation()` and is not this conversion. Do not search the catalog again after that miss, and do not ship the blank writer. If the sender cannot run the writer, do not claim the deck is attached. In that same reply, say the file is not ready. Then write the spec and builder under `artifacts/`, and open one bound PDAPP whose action is to run that exact builder and attach the ASCII PPTX back to the origin thread. A later 「轉換完了嗎」 still leads with not done until the PPTX is attached and read back. A later no on a comparison or a second rebuild does not cancel that handoff. Read the handoff before you answer. If it is still pending, lead with that state. Do not say no file is in progress, and do not say they will not receive the file. Ask only whether they want that pending file cancelled. If the ledger is `blocked` for a per-ticket usage ceiling, that attempt stopped and will not retry. Do not reopen that ticket, and do not start the model on the same action. The file is not ready until a PPTX is attached. An admin reattempt in the origin thread fixes the save defect first, then runs that one builder command with no model. The job meter is that command receipt, not the supervision chat's token total. Do not say another job caused the stop until you read both records under the PD One approval-ticket lifecycle. If they ask whether the picture deck itself reached the ceiling, say the stop record is that job's processing total, not the picture size. Do not say every future picture deck needs this handoff, and do not say the handoff is because of the source name or token cost. The handoff is this file only, and only because this sender cannot run the writer.
- Run OCR through employee-lane `execute_code` / terminal. Vision is the reader. Do not paste the slide PNGs to stay inside `pptx-from-template`.

## Employee converter comparison

Do this before any rebuild ask. Render both decks. Read the source cover with vision.

- Count slides. An added Focus or Status slide is a summary page the source does not contain. Do not call it a different project, and do not call its numbers invented, until you check each number against the source raster. An issue tree or a section divider is still an extra page when the author only defends the summary slides.
- A unit in the converter prompt is not a hardcoded-unit defect when the source chart already shows that unit. Check the source label.
- Retained report ids do not prove the certificate pictures survived. If the source raster shows a certificate or declaration image and the rebuild is text only, report the missing picture.
- Compare the source cover date with stored `a:t` in the rebuild. A footer date on the preview PNG is the template date field at render time, not the report date.
- A chat claim that the docs were corrected does not close a documentation finding. Close it only after you read the revised file.
- A department-supplied template is a source claim, not identity with the sealed golden. Follow `pd-one-firm-template` before you say the files match or differ.

Before you ask them to start, say this in the DM language, in short sentences:

- The new file is editable slides made from the source pictures.
- It is not an install of their system, and it is not a paste of the full-slide pictures.
- Titles, numbers, and evidence stay from the source. Every slide gets the company header and footer.
- Do not add summary pages or numbers the source does not have.
- The result is a new file in the thread. The source file is not changed.

Then wait for a yes. If a handoff for the first file is already open, that no applies only to the comparison rebuild. Do not withdraw the first file in chat while that handoff is pending.

## Procedure

1. Copy the attachment under an approved root. Confirm the fingerprint with typed inspect: every shape is a picture, `Words` is 0, and there is no selectable text. Do not unzip through an employee shell. Judge the project from the visible cover title, not the file name. A file name can name a different project than the pictures. If they confirmed a rebuild and the sender cannot run the writer, the next employee reply leads with the file not being ready, then continue the spec and the one handoff. Do not open that handoff for a comparison that has no yes. Working notes are not delivery.
2. If the ask is to put the attached NotebookLM file on the company template, rebuild that file. Do not wait for a second file they might send later. If the ask is to compare their converter output with the company conversion, compare the attached files first. Explain the rebuild in plain language, then wait for a yes. A comparison request is not that yes. Do not write the spec or open the handoff until they confirm. Extract each slide PNG in order only after that yes. Write a slide spec before opening the template. The spec is the generation prompt. Do not generate from memory of the picture.
3. Read every slide with vision. That is the OCR for every requester, including employees. No admin role and no shell. Then zoom small text and read it again. If the two reads disagree, keep `[?]`. Do not pick the prettier string. Do not call tesseract through terminal to "unlock" OCR.
4. Classify each picture region before assigning a disposition. One PNG per slide does not mean the slide is all generated. NotebookLM flattens a photo, a screenshot, and a drawing into the same raster. Judge the region, not the package.
5. Decide layout by fit, not by the first keyword. A named Light layout is right when its graphic already says what the picture said. If the picture is the explanation, do not drop it to fit a text layout.
6. Generate only from the spec. `load_firm_presentation()`, then `save_presentation`. Follow Text, not bullets-per-line: a new body paragraph becomes a bullet, so do not split languages that way unless each line has `buNone`. One bullet per item, never per language line. Headings have no bullet. An employee requester uses the same writer.
7. Copy-crop evidence photos only. For a generated-graphic region whose picture explains the text, generate a new concept image in company navy / cyan / paper, with no letters and no watermark, and place editable text beside or on it in the source reading order. Do not generate a photoreal stand-in for a shop photo.
8. Cover subtitle may carry the source unit and date (`副標 — 單位 / 日期`). Company `dt` / `ftr` / `sldNum` come from `save_presentation`, not from the raster footer.
9. Save the spec next to the deck. Save the deck only with `pd_one_pptx_ops.save_presentation` to a new no-space path: `良器-<dept>-<topic>-<EN>.pptx`. Never the source path. `save_presentation` is available to every profiled employee for this same-thread conversion. Do not withhold the deck for lack of an admin role.
10. Verify, then visual-QA the rendered slides against the spec. Delivery is the Mattermost attachment, not a filesystem path. In the same reply, emit one `MEDIA:/absolute/path/to/file.pptx` line for the deck. A path in backticks is not accessible from Mattermost. Do not use `origin_thread_media_deliver` for PPTX; that grant only accepts mp4/jpg/png and needs a PDAPP ticket. If a REST upload is also used, still emit `MEDIA:` unless that upload's readback already shows the file on this thread.

## Slide spec (the prompt)

One record per slide. Write it to `artifacts/` before `load_firm_presentation()`.

- `depicts`: one phrase for the picture’s job — cover emblem, from-to, four-step flow, injection-machine schematic, tablet evidence, two roles, divert/quarantine, comparison matrix, closing. Not the English label painted on the art.
- `text`: every string, reading order, `[?]` where unclear. Do not guess.
- `relations`: which text annotates which region (a callout on a machine part, a caption under a photo, a column header over cells).
- `design`: emphasis (which step or cell is the punch), source palette noted and not copied, watermark present or not.
- `regions[]`: bounds description, disposition, and why.
- `layout`: exact Light `p:cSld/@name`, or `native-table` on `內文 Content`.
- `prompt`: the spec itself. Forbidden additions: new steps, new parts, fake photos, Gemini chrome.

## Image disposition

Judge each region. Do not use one rule for the whole slide.

| Disposition | Use when | Generate |
|---|---|---|
| `copy-crop` | Workplace photo, system screenshot, or measured drawing that is the content, and a tight crop excludes chrome and the watermark. | Embed that crop, contain-fit. Never image-generate it. |
| `fetch-original` | The evidence is only inside a device mockup, too small, or mixed with chrome. | Ask for the original file. Transcribe labels and visible truncated ids. Do not crop the mockup. Do not image-generate the photo. |
| `rebuild-native` | The meaning is a structure: flow, from-to, pillars, matrix, cover, close. Text already states the nodes. | Named firm layout from the spec. Do not crop the illustration. Do not image-generate a replacement infographic. |
| `rebuild-diagram` | A machine, line, flow, or divert picture whose labels are operational, and the pixels are a Gemini illustration. | Generate a concept graphic with no baked text. Editable callouts name only the parts that were labeled. Do not crop the sci-fi render. Do not generate a photoreal photo. |
| `drop` | Shield, gears, glow, generic icons, device chrome, watermark — the text already carries the meaning. | Nothing. |

Image-generate (`image_generate`) is the normal path for a concept graphic that the named layout cannot draw: a gate row, a machine schematic, a divert, an emblem, an icon. Prompt: company navy `#0F2A44`, cyan, paper `#F6F3EC`, no letters, no watermark, no extra parts. Vision-QA before embed. A failed QA means drop that image, not the slide text.

## Text, not bullets-per-line

A new paragraph in a body placeholder becomes a bullet. Do not use a new paragraph to separate Chinese from English.

- Heading: fill the layout title placeholder. Do not clear it and paint the title in a free text box. An empty title placeholder leaves the cyan rule with no title.
- One language pair is two visible lines. `a:br` is not done until the render shows Chinese above English. If the render keeps them on one line, use two paragraphs with `buNone`, and size the box so neither line wraps mid-word.
- Body and table cells: left or top aligned, Chinese line then English line, box tall enough for both. Do not center a multi-line body. Do not glue the date to the next word.

## Composition

Named layout when the graphic already matches. Free composition on the Light master when it does not. Company header, footer, and slide number still come from `save_presentation`. Do not leave SAMPLE text. Do not paste the source slide.

## Pixel class

Do not use the package to classify pixels. One `p:pic` per slide is the NotebookLM fingerprint, not proof that every region is a drawing. Do not use color variance or edge energy alone. On the calibration file those numbers overlapped across a photograph and a blueprint.

Zoom the region, then class it:

| Class | What you see | What you do not see |
|---|---|---|
| `photograph` | Real materials, uneven light, camera perspective, incidental clutter. A shop floor, a part, a hand. Often a rectangle inside generated chrome. | Neon geometry, perfect isometric, blueprint glow, the illustration style of the surrounding frame. |
| `screenshot` | A real product UI: system font, status bar, list rows, buttons that match that app, pixel-aligned chrome. | A drawn phone with glowing cards. That is a graphic of a device, not a screenshot. |
| `generated-graphic` | Glow, bloom, perfect circles, blueprint lines, circuit emblem, isometric consistency, Gemini watermark, the same decoration style as other slides. | Sensor noise or a real app's UI. |

A photoreal generation can mimic a photograph after NotebookLM recompresses it. Looking photographic is not proof of a camera file. If the region is evidence and you cannot separate it from the frame, disposition is `fetch-original`, not copy-crop and not image-gen. Copy-crop only the inner rectangle that classed as `photograph` or `screenshot` and excludes chrome and the watermark.

Calibration: slide 5 inner rectangles (black sheet, green aisle, attachment-id captions) class as `photograph` inside a generated tablet. The neon cards and bezel are `generated-graphic`. Slide 4's machine and slide 1's emblem are `generated-graphic`, not photos and not screenshots.

## Slot map (firm Light)

| Content shape | Layout | Do not use |
|---|---|---|
| Title + subtitle | `封面 Title` | Dark cover, pasted shield |
| Two states and an arrow | `從到 From-to` (from title/body, to title/body) | A third invented column |
| Exactly 4 named parts | `四格框架 Framework` (core + 4 faces; one line per face) | `流程 Flow` (5 slots) |
| Exactly 3 titled notes | `三驅動 3 drivers` (num / title / body × 3) | Freeform cards |
| Two text columns | `雙欄 Two Column` | `泳道 Swimlane` |
| Matrix whose headers are not Item/Target/Actual/Status | Native table on `內文 Content` | `計分表 Scorecard` |
| Closing commitment | `結語 Closing` | A second copy of the process art |
| 4 narrowing stages | `漏斗 Funnel` | A split / divert picture that merely says “funnel” |

Unused layout slots mean the wrong layout. Clear every visible placeholder you do use. Pass `placeholder.text_frame` into any helper that calls `clear()`. A slide placeholder has no `clear`, so the builder exits before it saves. On `四格框架 Framework`, the four faces start at placeholder index 2.

## Verify before delivery

- The spec exists and every output string is in it. Output `a:t` contains every source title. `Gemini Notebook` is absent.
- No output media hash matches a source slide PNG. Any embedded crop is a strict sub-region, contain-fit, and its disposition in the spec is `copy-crop`.
- No image-generated picture depicts a photo, screenshot, machine, mold, or factory unless the spec recorded the exception and the vision QA passed.
- Every slide has `dt`, `ftr` (`Pro-Design Group · 良器集團`), and `sldNum`.
- No SAMPLE / SOURCE / FOOTNOTE label without a real citation.
- Visual QA: CJK not clipped, no leftover NotebookLM chrome, pictures (if any) contain-fit.
- `office_no_corruption_gate.py` and, if any picture was embedded, `pptx_image_aspect_check.py`.

Calibration map and English shop terms for line clearance: `references/line-clearance-raster-map.md`.

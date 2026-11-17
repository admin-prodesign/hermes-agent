---
name: pd-one-pptx-office-package
description: "Use when a generated PPTX prompts PowerPoint Repair."
version: 1.0.0
author: Hermes Agent
license: private
metadata:
  hermes:
    tags: [pptx, ooxml, repair, powerpoint]
    related_skills: [pd-one-pptx-template-migration, pd-one-firm-template, pptx-author]
---

# PD One PPTX Office package integrity

Headless PPTX that PowerPoint flags Repair. Diagnose the **package** (ZIP, rIds, shape ids, leftover POTX parts, view state). Do not treat Macintosh Repair, LibreOffice PDF convert, or an in-app add-in write-up as proof the generator is clean.

User POTX/PPTX restyle procedure stays in `pd-one-pptx-template-migration` (adopt that skill if it is still user-owned). Firm golden mutations stay in `pd-one-firm-template`.

## When to Use

- A staged or attached PPTX opens with PowerPoint Repair, Repair-on-reopen, or Repair after scroll/thumbnails.
- Generator vs Repair looks the same size and you need to know whether anything actually changed.
- An Office add-in diagnoses media/notes/webextensions and you must check those claims against hashed parts.
- Not for golden layout/chart mutations (`pd-one-firm-template`) and not the restyle apply steps (`pd-one-pptx-template-migration`).

## Procedure

1. Hash the file the user opened vs the staged generator vs any Repair copy. Byte length on picture-heavy decks is not identity.
2. Confirm apply engine is **reflow onto template layouts**, not graft of source `xfrm`. User POTX: `--compat` sanitize (keep non-rect placeholders / idx). Firm golden: full Office gate.
3. Run the checks in `references/repair-triggers.md` in order. Fix the first real mismatch; restage to a **separate** artifacts path. Never overwrite source or template.
4. After dropping POTX sample slides, prune unused `slideLayouts` and extra `slideMasters` so the PPTX keeps only layouts the restyle uses. A POTX may carry dozens of layouts; cloning that catalog into a PPTX keeps Macintosh Repair looping after XML/ZIP look Office-like.
5. Pack with `pack_ms_office` (Office ZIP: create version 45, `attr=0`, deflate-all). Do not `pack_msdos` (version 20, archive bit, stored `[Content_Types].xml`).
6. Visual QA, then attach only to the origin thread. Wrapper does not send. Do not post to another DM until the requester names that destination. REST-upload CJK names; read back `files[].name` with no `%`. Confirm the target channel is type `D` and the named employee plus bot are members before upload. Employee-facing caption: Traditional Chinese first; tell them to use this file and ignore any earlier graft in the same thread.
7. LibreOffice PDF `rc=0` does not prove PowerPoint will skip Repair. First-open without Repair is not done until scroll, thumbnail pane, and reopen are clean.

## Always-on

- Same-thread requester PPTX/POTX restyle is drafting: typed `pptx-from-template`, no PDAPP.
- Assign shape ids with a lambda plus `'"'`. A raw f-string `rf"...\""` writes `id="7\"` and PowerPoint Repair-strips it.
- Keep `HeadingPairs` / `TitlesOfParts`; fill template slide skeletons instead of hand-building `p:sld`.
- Densify presentation rIds after dropping sample slides (gapped leftover rIds Repair on later-slide / thumbnail load).
- Strip `lastView="sldThumbnailView"` from `viewProps` (Repair 10–15s after open when the thumbnail pane builds).
- Strip a leading bullet from title text copied out of a placeholder.
- Do not ship Macintosh Repair as the deliverable when generator vs Repair is only datetime cache, PNG recompress, `Application` Macintosh, or element order. Repair is not idempotent; that file can still Repair on reopen. If those are the only deltas, prune unused POTX layouts next — do not restage another pictures-dominated clone.
- Do not rasterize source EMF chart pictures to PNG unless asked. `nSize=0x6C` is a normal `EMR_HEADER`, not an empty bounds box. EMF is a Windows paste-as-picture risk; it is not the usual Macintosh Repair cause. Rasterizing redraws every chart slide.
- Hash a PowerPoint add-in diagnosis against the staged generator. Open-with-add-in injects `ppt/webextensions/` (empty `<we:snapshot>`) and Macintosh `app.xml`; that is not generator output. `notesSz` without `notesMaster` is inherited from a working POTX and is secondary.

Trigger table: `references/repair-triggers.md`.

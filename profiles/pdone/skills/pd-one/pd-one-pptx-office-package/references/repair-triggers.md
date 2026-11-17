# PowerPoint Repair triggers (generated PPTX)

Walk in order. Stop at the first real mismatch. Do not skip to EMF rasterize or to copying a Macintosh Repair file.

## 1. Hash, then parts inventory

- SHA-256 the opened file, the staged generator, and any `*Repaired*.pptx`.
- Count `ppt/slideLayouts/*.xml`, `ppt/slideMasters/*.xml`, media, notes masters, `ppt/webextensions/`.
- Picture-heavy zips stay similar in byte length across restages; length is not identity.

## 2. Invalid XML / ids

| Check | Fail looks like | Fix |
| --- | --- | --- |
| Shape `id` attributes | `id="7\"` from a raw f-string | lambda + `'"'`; assert no `id="\d+\"` in slide XML |
| Title text | leading `•` / `●` copied from a placeholder | strip those marks from title `a:t` |
| Slide XML decl | missing `standalone="yes"`, LF-only, unused `xmlns:a14` | serialize like PowerPoint (UTF-8 standalone, CRLF, drop unused a14) |
| `app.xml` | stripped `HeadingPairs` / `TitlesOfParts` | keep vectors; retarget slide count |
| Slide construction | hand-built `p:sld` | fill template slide skeletons |

## 3. Relationships and ZIP

| Check | Fail looks like | Fix |
| --- | --- | --- |
| Presentation rIds | leftover high rIds after dropping POTX sample slides (gap in the middle) | densify `rId1..N`; media names `imageN` not `src_` |
| ZIP container | create version 20, archive bit, stored `[Content_Types].xml` | `pack_ms_office`: version 45, `attr=0`, deflate-all |
| Content types | `ct:` prefix on `Types`; missing `emf`/`jpeg` defaults | unprefix; Defaults first |
| User POTX sanitize | firm gate stripped hundreds of non-rect `p:ph` | `--compat` (do not strip non-rect ph / rewrite idx) |

## 4. POTX leftovers in a PPTX

| Check | Fail looks like | Fix |
| --- | --- | --- |
| Unused layouts | PPTX still has the full POTX layout catalog after sample slides were dropped | keep only layouts the restyle uses; drop extra masters |
| `viewProps` | `lastView="sldThumbnailView"` | strip the attribute (delayed Repair when thumbnails build) |
| ZIP member order | slides not immediately after package rels | order slides after package rels; Content_Types Overrides list slides after masters |
| Slide numbers | leftover skeleton numbers on every slide | write 1..N |

A POTX may legally hold dozens of layouts. That same catalog inside a **PPTX** is a Macintosh Repair loop even when masters/layouts XML still match the template byte-for-byte.

## 5. Do not treat as generator bugs

| Observation | Meaning |
| --- | --- |
| Repair vs generator is datetime cache, PNG recompress, Macintosh `Application`, element order | Repair did not find a remaining structural bug; do not ship that Repair file as done |
| `ppt/webextensions/` / empty `<we:snapshot>` | injected when an Office add-in pane is open; hash vs staged generator |
| `notesSz` and no `notesMaster` | same as a working POTX; secondary |
| EMF `nSize=0x6C` and non-zero `rclBounds` | normal `EMR_HEADER`; not empty bounds |
| LibreOffice PDF convert `rc=0` | not a PowerPoint Repair oracle |
| First open clean, scroll or 10–15s later Repair | look at `lastView`, gapped rIds, unused layouts — not titles |

Rasterize EMF to PNG only when the requester wants a Windows-safe copy. That redraws chart slides.

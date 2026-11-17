---
name: powerpoint-to-html-presentation
description: "Use when turning PowerPoint into portable animated HTML."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [powerpoint, pptx, html, presentation, bilingual, animation, visual-qa]
    related_skills: [creative-artifact-generation, visual-office-qa, pd-one-infographic-generator, architecture-diagram, excalidraw]
---

# PowerPoint to Portable HTML Presentation

## Overview

Turn an existing `.pptx` into a polished browser-native presentation while preserving source truth. The deliverable is a self-contained HTML/CSS/JavaScript package that works from `file://` and can also be hosted as a static route. AI may redesign layouts, generate supporting illustrations, write animation code, and localize content; humans still own claims, judgment, and release approval.

## When to Use

Use for company introductions, training decks, customer presentations, technical explainers, and internal briefings that benefit from stronger graphics, motion, bilingual delivery, or browser sharing.

Do not use when the required output must remain an editable native PowerPoint, when source ownership is unclear, or when the request is merely a direct format conversion with no redesign.

## Workflow

1. **Inventory the source.** Preserve the original PPTX unchanged. Extract slide text, notes, media, dimensions, and embedded documents; render every source slide to images or PDF. Completion: slide count and all referenced source assets are accounted for.
2. **Build a claim ledger.** Separate sourced facts from design interpretation. Keep dates, quantities, credentials, customer marks, certifications, and sustainability claims exactly qualified. Remove or soften unsupported claims rather than making the design more confidently wrong. Completion: every material claim traces to the source or is explicitly labeled illustrative.
3. **Choose a design system.** Define audience, visual direction, typography, palette, grid, motion language, and a fixed presentation canvas—normally 1920×1080. Preserve company branding without copying the source deck's weak layout. Completion: representative opening, content-dense, evidence, and closing slides share one coherent system.
4. **Implement offline-first.** Use local HTML/CSS/JavaScript and local assets only. Avoid CDNs, remote fonts, backend dependencies, and install steps. Include slide hashes, counter/progress, keyboard/touch navigation, fullscreen, overview, autoplay, print/static mode, reduced-motion support, and accessible focus/dialog behavior when applicable. Completion: the unpacked folder opens and functions through `file://` with the network disabled.
5. **Generate visuals carefully.** Prefer source media for evidence. For labeled system, architecture, cloud, infra, or data-flow topology slides, load `architecture-diagram` with `skill_view` and follow it; for hand-drawn whiteboard flows, load `excalidraw`. Do not freehand a weaker diagram or replace a topology map with a generated factory illustration. **Image generation is allowed** in Portal-hosted and portable HTML presentations for physical/product process scenes only. Use AI-generated illustrations as editorial explanation, never as documentary proof of a facility, product, machine, certificate, or test result. Ban invented logos, labels, marks, and unsupported text inside generated imagery. Save files locally (e.g. `assets/`) and reference with same-origin `src`; Portal CSP forbids remote images. Completion: every generated visual has a clear role, readable crop, local asset, useful alt text, and documented illustrative status; topology slides used `architecture-diagram` or `excalidraw`.
6. **Localize structurally.** Store English and Traditional Chinese strings separately from layout where practical. Switch language instantly without reloading, persist preference, localize UI/ARIA/alt text, and use solid legible CJK typography rather than decorative outlined Chinese. Completion: every slide and control works in both languages without clipping or collision.
7. **Validate mechanically.** Check slide count, duplicate IDs, missing local references, external dependencies, JavaScript syntax, image load failures, and required controls with a deterministic validator. Completion: validator and syntax checks pass from a clean package.
8. **Visually QA exhaustively.** Render every slide at 1920×1080 in every supported language. Inspect contact sheets and dense/evidence slides individually. Check browser and print/PDF output, overview, dialogs, long Chinese strings, touch/mobile scaling, and console errors. Completion: no visible overflow, clipping, stale asset, unreadable text, broken chrome, or print-only regression remains.
9. **Package and publish safely.** Produce the self-contained folder and ZIP; optionally generate PDF fallbacks. For PD One, deploy under a dedicated static subfolder, add a manifest route, set `portal_hidden: true` when unlisted, and use `allow_google_groups` for the intended employee audience. An obscure URL is not access control. Completion: authorized identity gets `200`, unauthorized and anonymous identities get `403`, the route is absent from portal navigation when unlisted, and live assets hash-match the release package.
10. **Persist the release.** Back up replaced live files, commit only scoped source/config/test paths, push, and read back the remote commit. Completion: live state, rollback copy, and version-controlled backup agree.

## PD One Capability Composition

This workflow composes existing PD One capabilities rather than depending on one magic converter:

- PPTX extraction/authoring and Office rendering
- creative artifact and infographic generation
- HTML/CSS/JavaScript implementation
- image generation or compositing where available
- visual Office and browser QA
- authenticated static microsite deployment

When a requested component is unavailable, fail closed or use a simpler local substitute; do not fabricate that an image, test, deployment, or browser check occurred.

## Common Pitfalls

1. **One-click-conversion expectations.** A raw conversion preserves PowerPoint's weaknesses. Treat the PPTX as source material, then redesign under explicit constraints.
2. **Pretty lies.** Generated factory scenes and icons are explanatory art, not proof. Keep credentials and source documents separate from decorative imagery.
3. **Online-only packages.** Remote fonts, libraries, and image URLs break portability. Bundle everything local.
4. **English-only QA.** Chinese often fails at headings, cards, and UI chrome even when English fits.
5. **Partial visual review.** Checking three attractive slides misses failures in dense and evidence-heavy slides. Render all slides.
6. **Public-by-accident hosting.** Hidden navigation and unguessable paths are not authorization. Use Cloudflare Access plus origin-side group gating for employee material.
7. **Stopping at files.** A hosted request is complete only after the URL, identity gates, services, logs, and rollback path are verified.

## Verification Checklist

- [ ] Original PPTX preserved and fully inventoried
- [ ] Claims trace to source; generated visuals labeled illustrative
- [ ] Package works from `file://` without network access
- [ ] Navigation, accessibility, reduced motion, and print/static modes work
- [ ] English and Traditional Chinese render cleanly on every slide
- [ ] All images/scripts/fonts are local and load successfully
- [ ] Validator, JavaScript syntax, browser console, and PDF checks pass
- [ ] Hosted route has explicit audience, positive and negative access tests, and rollback
- [ ] Scoped source/config/tests are committed, pushed, and read back

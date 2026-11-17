---
name: pd-one-infographic-generator
description: "Create PD One infographic concepts and specs."
version: 1.4.0
author: Hermes Agent
license: private
metadata:
  hermes:
    tags: [pd-one, pro-design, infographic, feature-announcement, avatar, image-generation, brand]
    related_skills: [baoyu-infographic, pro-design-avatar-generation]
---

# PD One Infographic Generator

## Overview

Compact router for Pro-Design/PD One infographic collateral: feature announcements, workflow explainers, SOP visuals, training cards, timeline/status posters, comparison charts, checklists, safety/approval reminders, FAQ explainers, onboarding visuals, and cartoon-like explanation graphics.

Default stance: create a flexible, polished visual artifact with Traditional Chinese employee-facing copy by default, English when requested, and bilingual copy when publishing into shared Mattermost/group contexts.

## Load Detail When Needed

The full pre-compaction playbook is preserved here:

```text
skill_view(name="pd-one-infographic-generator", file_path="references/complete-original-skill.md")
```

Load it before doing detailed brand/avatar prompting, official PD One avatar asset handling, complex image-generation prompts, HTML/CSS compositing, or visual QA beyond a quick draft.

Existing focused references remain available:
- `references/agentic-harness-explainer.md`
- `references/outcome-focused-agentic-explainers.md`
- `references/localized-product-image-edits.md`
- `references/bilingual-chart-rendering.md`

## When to Use

Use this skill when the user asks for:
- Pro-Design/PD One infographics, posters, cards, explainers, visual announcements, or training collateral.
- Visual explanations involving PD One agents, AppSheet workflows, SOP generation, approvals, status tracking, or employee-facing operations.
- Brand-consistent images that may use the official PD One avatar or Pro-Design visual style.
- External prospect sheets and regional sales one-pagers. Follow External prospect sheets below. Do not use the PD One avatar path for these.
- A printable one-page insert for a bound laboratory notebook. Follow Lab notebook paste pages below. Do not start a weekly run before those gates are answered.

Do not use it for plain text announcements only; use `company-announcement-writer` unless a visual artifact is required. For generic infographic ideation not tied to Pro-Design/PD One, load `baoyu-infographic`.

## Visible Guardrails

- Do not invent official policy, commitments, feature availability, or company facts; ground operational claims in provided/source-backed content.
- For employee-facing/shared-channel materials, preserve Traditional Chinese and English substance 1:1 when bilingual output is required.
- Use official avatar/brand assets only from approved local/Drive sources; do not substitute random public images for company identity.
- When generating or editing images, visually inspect the result; do not claim the artifact is final without checking layout, text legibility, and brand fit.
- If the design will be published externally or sent broadly, get approval before sending/posting. Deliver the draft only in the requesting thread until that approval.

### External prospect sheets

Use this path for a customer or prospect audience, including a regional sales one-pager.

- Render the words in HTML/SVG. Do not use an image model for exact sales claims.
- Use the official Pro-Design wordmark and its colors. Do not apply the PD One purple avatar palette, and do not draw a stand-in logo.
- Every claim must come from an own source: the company introduction, the live site, or Drive. If a requested region, lead time, language, agent, or service is absent, say so only in the review note. Do not print a gap box, a draft banner, or an internal-approval footer on the page. Do not imply that region is already served.
- Do not use source-audit labels on the page. Use customer-facing names: Customers, not "Customers we can name"; Sizes, not "Published sizes"; Client regions, not "Published client regions"; Websites, not "Public sites".
- Do not put a region name or a draft status in the header unless the user asks for that line as sales copy.
- When the user names a contact email, use that address. In the review note, state the address the public page still shows. Do not invent a mailbox the user did not name.
- Once the user asks for a shareable file, the download name must not contain "draft". Making the page shareable is not an external send. Deliver it only in the requesting thread until the user approves a send.
- After you remove a side gap box, set that section to one column so the remaining card is full width. If you also remove the footer, pin the contact bar with margin-top auto and a small bottom margin so the bar sits at the page bottom without a hole.
- Keep each commercial-model sentence on its source wording. Do not add a support promise to a different model. A trials or training line stays its own sentence, with the source scope limit.
- If two own sources disagree on a count or a time claim, omit that number from the graphic and list both figures in the review note.
- Name a customer only after a visual match of that logo file. Alt text alone stays in the review note.
- Do not place a caption inside the QR box. The SVG paints over the label. Put the target URL beside the code, then decode the rendered code before delivery.
- Before writing PNG or PDF, confirm page scroll height does not exceed the fixed page box. Write the export only after the expected page text is on screen.
- Put a requested product collage on a white plate in the stated slot, clear of contact text and the QR code. Use the company-introduction pail-range image, not a site banner that shows partner brands. Do not knock out the white background: white products disappear on a dark bar.
- Do not paint over collage callout labels to hide type that is too small. The callout color matches product color, and a rectangle mask covers products. Keep the source photo. Say the labels are small, or enlarge the plate. Crop only empty caption space that repeats a fact already on the page.
- After you add the plate, the sheet must still fit one page. Reclaim space from gaps above before you grow the bar. Do not save an export that clips the footer.

## Lab notebook paste pages

Use this when a project needs a printable one-page insert for a bound laboratory notebook, one page per person per covered topic.

Before you generate pages or schedule a weekly run, confirm:

- The responsibility workbook is the named file, not a photo of a blank page. If the current post has only images, the table may be on an earlier post in the same room.
- The named holders and their topic codes. Do not infer holders from channel membership.
- The scan boundary: this room only, manuals already posted in the room, other rooms, or machine data outside Mattermost.
- The page budget. A weekly page for a year exceeds a 60-page book if a quiet week also gets a page. Ask whether a quiet week is skipped.
- The blank-area width and height in millimeters, and whether the print must leave recorder, witness, and date space for a hand signature.
- Whether the print is the official record or a supplement, and whether the page is Traditional Chinese, English, or both. A bilingual page is harder to keep dense and readable.
- The delivery place, weekday, and Taipei time. Do not start a scheduled post until those answers exist.

A printed page is not an official notebook record until the recorder and the witness sign it. Do not fill signature names from chat.

Size the page to the blank center. Make it dense and readable. Do not deliver a short summary or a transcript dump. Ground every fact in a post or file from the confirmed scan boundary. Do not invent process settings.

## Default Workflow

1. Clarify or infer the audience, purpose, language, format, and delivery surface.
2. Draft the content hierarchy first: headline, core message, 3-6 key points, CTA/owner/date if needed.
3. Choose an approach:
   - Same picture, new language, icons and font sizes kept: `image_generate` with `image_url` set to the source. Prompt must list every replacement string and forbid new icons, steps, and title shrink. Vision-QA every string. A Word translation is not this deliverable.
   - Image model for a new illustrative/artistic infographic.
   - HTML/CSS/SVG overlay for exact text, bilingual charts, QR codes, or strict layout control.
   - Existing asset compositing when official avatar/brand material must remain unchanged.
   - Image source stays an image. Deliver JPG or PNG with MEDIA. Do not deliver DOCX or PDF unless they explicitly ask for a print file. See `document-production-workflows`.
4. Generate the artifact, then visually QA it.
5. Revise until text, layout, and brand consistency are acceptable.
6. Deliver the file path/attachment and a concise summary of what was verified.

## Verification Checklist

- [ ] Full reference loaded when doing detailed avatar/brand/image prompting work.
- [ ] Source facts and dates are grounded; no invented company commitments.
- [ ] Required language handling is correct and complete.
- [ ] Text is readable at intended size; no garbled characters.
- [ ] Brand/avatar usage is approved and visually consistent.
- [ ] Final artifact was opened/rendered/visually inspected before delivery.
- [ ] External prospect sheet: source gaps are in the review note only, not on the page; the page has no draft, audit, or gap-box wording; customer names were visually matched; the QR decodes to the stated URL; the page box does not clip the footer.
- [ ] A product collage sits on a white plate, clear of text and the QR code. The source photo is intact. Small callout type is flagged, not painted out.

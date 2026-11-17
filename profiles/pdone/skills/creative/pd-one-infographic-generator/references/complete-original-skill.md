---
name: pd-one-infographic-generator
description: Use to generate flexible Pro-Design/PD One infographic collateral of any type while preserving company visual style and using official Drive avatar assets for PD One-related visuals.
version: 1.1.0
author: Hermes Agent
license: private
metadata:
  hermes:
    tags: [pd-one, pro-design, infographic, feature-announcement, avatar, image-generation, brand]
    related_skills: [baoyu-infographic, pro-design-avatar-generation]
---

# PD One Infographic Generator

## Overview

Use this skill to create Pro-Design company-style infographic collateral: feature announcements, workflow explainers, SOP visuals, training cards, timeline/status posters, comparison charts, checklists, safety/approval reminders, FAQ explainers, onboarding visuals, and cartoon-like explanation graphics.

This skill adapts the `baoyu-infographic` process to Pro-Design/PD One needs: structured content first, flexible layout selection, company-consistent visuals, image-model-first generation when appropriate, official PD One avatar use for PD One-related collateral, Traditional Chinese employee-facing copy by default, and visual QA before delivery.

Default stance: **use image generation directly** for draft/final poster artwork when exact text is not critical. Current gpt-image-2 text rendering is good enough for many announcement drafts, so do not default to HTML/CSS text overlays unless exact legal/procedural wording, bilingual parity, brand-lockup precision, or post-generation editability is required.

## When to Use

Use when asked to create or revise any Pro-Design/PD One infographic-style visual, including:

- PD One feature announcement infographics.
- SOP/workflow/process explainers.
- Cartoon-like visual explanations to accompany internal announcements.
- Employee-facing visuals that should include PD One avatar/robot elements.
- Training, FAQ, checklist, before/after, timeline, troubleshooting, policy, metric/dashboard, and safety/reminder infographics.
- A reusable prompt/template for announcement graphics.
- PD One vs. traditional chatbot or agentic-harness architecture explainers; for these, use `references/agentic-harness-explainer.md` to include channel adapter, exact identity resolver, policy gate, context builder, skill loader, planner, tool router, verifier, safety controls, and capability table elements.
- Employee-facing “why PD One is different from ChatGPT” visuals; use `references/outcome-focused-agentic-explainers.md` when the goal is to emphasize enabled capabilities such as tools that do work, workflow memory, multi-step autonomy, safety boundaries, and proof/verification in bilingual English + Traditional Chinese.

Do not use for plain text announcements only; use `company-announcement-writer` for message copy. Use `pro-design-avatar-generation` if the task is primarily creating/revising the avatar itself.

## Brand and Flexibility Rules

- **Flexible content, consistent company look.** Do not force every request into a feature-announcement format. Choose the infographic type that fits the message, but keep the Pro-Design look: clean industrial/operations tone, modern rounded cards, off-white/light surfaces, deep purple accents, cyan digital highlights, clear hierarchy, and practical factory/workflow imagery.
- **Tone:** competent, reliable, helpful, and employee-friendly; avoid toy-like mascots, cluttered comic chaos, excessive neon, or generic SaaS stock art.
- **Language:** for employee-facing PD One output, use Traditional Chinese as the main language unless Andy asks otherwise; English may appear as small UI labels where useful.
- **PD One relevance:** if the infographic is about PD One, PD Neo assisting PD One, AI-assisted employee workflows, PD One-generated documents, PD One forms, approvals, Mattermost/Telegram employee usage, or any PD One feature announcement, treat it as PD One-related and use the official PD One/avatar asset workflow below.
- **Non-PD One company visuals:** keep the same company style, but do not force the PD One robot into unrelated topics unless requested.

## Official PD One Avatar Asset Workflow

When the infographic is PD One-related, **use the official PD One / Pro-Design AI avatar from Google Drive whenever possible** instead of inventing a new robot or using a temporary CSS/HTML drawing.

Canonical reference / starting asset:

- Drive path: `文件 Documents/跨部門 Cross-Functional/媒體素材 Media Assets/規格 Specs/Pro-Design AI Agent Master Avatar Spec v1.1 - Square First Infographic.png`
- Drive file ID: `1YxETRcQGhg4ytjkgwV258lkBXTr_ZBSd`
- Drive link: https://drive.google.com/file/d/1YxETRcQGhg4ytjkgwV258lkBXTr_ZBSd/view?usp=drivesdk

Asset folders:

- Root media folder: `文件 Documents/跨部門 Cross-Functional/媒體素材 Media Assets` (`12aq-ypV8m6DrK3QplElw4VsUv4IZoH2a`)
- Avatars: `頭像 Avatars` (`1qn5JHw1UTBqn6a3ZE2mWijQINJBBIjup`)
- Specs: `規格 Specs` (`1z3onVqNFCVAXMmuYE5_VTRRL79oPapvW`)

Procedure:

1. Load `pro-design-avatar-generation` and follow its official-avatar guidance.
2. Check/download the canonical Drive avatar or the current official PD One avatar from `媒體素材 Media Assets/頭像 Avatars` when Drive tools are available.
3. Save the avatar source into the infographic artifact directory, e.g. `source/official-pd-one-avatar.png`, before composing/rendering.
4. Use the downloaded avatar as an image reference or composited foreground element. If the image-generation backend cannot take image references, use the prompt block below and clearly state that it was prompt-based rather than asset-composited.
5. Visual QA must confirm the avatar is visible, not clipped, and still matches the official PD One design.

## Default Workflow

1. **Load supporting skills**
   - `baoyu-infographic` for layout/style vocabulary and content structure.
   - `pro-design-avatar-generation` for official Drive avatar location, constraints, and rejection rules when PD One/PD Neo appears.

2. **Capture source content**
   - Preserve must-include facts and user-specified wording.
   - Strip secrets, tokens, private rows, and unrelated admin details.
   - Identify audience, channel, language, exactness requirements, and whether this is PD One-related.

3. **Choose infographic type, layout × style**
   - Process/tutorial/workflow: `linear-progression` + `corporate-memphis`.
   - Feature overview/release notes: `bento-grid` + `corporate-memphis` or `bold-graphic`.
   - Narrative announcement: `comic-strip` + `bold-graphic`.
   - FAQ / myth-vs-fact: `question-answer-cards` or `comparison-grid` + clean corporate style.
   - Checklist / readiness / do-don't: `checklist-panel` or `split-comparison` + high-contrast operational style.
   - Timeline / rollout / status: `timeline-roadmap` + clean dashboard style.
   - Training / safety reminder: `step-cards` + calm operations style.
   - High-energy poster: `dense-modules` + `retro-pop-grid`; anime/manga style only when explicitly requested.

4. **Write an image-model or render prompt**
   - State exact canvas/aspect.
   - State exact main headline and short card labels.
   - Request readable Traditional Chinese when appropriate, but keep text short.
   - For PD One-related visuals, include/use the official avatar asset and/or the PD One avatar prompt block.
   - Specify the exact number of cards/panels where important.
   - Add negative constraints: no watermarks, no unrelated logos, no tiny paragraphs, no clipped avatars.

5. **Generate or render image**
   - Use `image_generate` with `landscape` for internal announcement graphics unless a different aspect is requested.
   - If exact text/layout/avatar placement matters, use browser-rendered HTML/CSS or a compositing script with the official avatar asset.
   - Save the result to a durable artifact directory, not only cache.

6. **Visual QA**
   - Use vision to check headline, card count, text readability, avatar visibility, safety/approval messages, brand consistency, and major text errors.
   - If text is mostly correct but small details are imperfect, report that honestly as an image-model draft.
   - Regenerate or switch to overlay/compositing if: wrong infographic type, wrong number of cards, missing official PD One avatar in PD One-related output, garbled headline, missing safety gate, clipped content, or unwanted logo/watermark.

7. **Deliver**
   - Include `MEDIA:/absolute/path.png`.
   - Include prompt/source path and QA notes.
   - Back up durable artifacts when the Hermes/OpenClaw backup repo is configured.

## PD One Avatar Prompt Block

Use this block inside the image prompt when PD One should appear and the backend cannot directly use the official Drive avatar as a reference/composited element:

```text
Include a professional internal AI assistant robot guide matching the official Pro-Design PD One avatar: compact humanoid digital colleague robot, rounded rectangular black glass visor head, soft curved cyan digital eyes, premium off-white body, deep purple accents, subtle PD marking on forehead/chest, deep purple reliability cape, helpful guiding posture, holding a tablet or holographic document. It should look competent and trustworthy, not toy-like, not overly cute, not a generic chatbot mascot. Keep the avatar visible and not clipped.
```

For most PD One explainers, place one larger official-avatar guide near the header and optionally one smaller helper near the final approval/reassurance panel.

## Prompt Template

```text
Create a clean Pro-Design company-style {infographic_type} infographic about {topic}.

Canvas: {aspect}, suitable for Discord / Mattermost / Telegram preview. Clean, spacious, readable.

Visual style: modern industrial operations, off-white/light panels, deep Pro-Design purple accents, cyan digital highlights, rounded cards, clear hierarchy, practical workflow imagery, competent and reliable rather than cute.

Language: {language}. Traditional Chinese main text for employee-facing PD One visuals unless requested otherwise. English only as small UI labels where useful.

Main headline:
「{headline}」

Subtitle:
「{subtitle}」

Layout: {layout}. Use exactly {N} main cards/panels, clearly numbered {numbers}, connected by arrows or a readable visual path where appropriate.

Cards:
1. Title:「...」 Subtext:「...」 Visual: ...
2. Title:「...」 Subtext:「...」 Visual: ...
...

Bottom safety / CTA banner:
「{bottom_message}」

PD One-related avatar instruction:
{Use official downloaded PD One avatar asset / or PD One avatar prompt block}

Design rules:
- Keep all text readable with good spacing.
- Keep the Pro-Design company look consistent even when the infographic type changes.
- For a company sales sheet, use the official Pro-Design wordmark. For other pieces, no unrelated logos. PD One text only when the piece is about PD One.
- No watermarks.
- Avoid tiny unreadable paragraphs.
- Avoid distorted human faces/hands; robot visor face is okay.
- Emphasize {key_operating_principle}.
```

## SOP Document Generation Example

For SOP document generation, use:

- Headline: `PD One SOP 文件生成流程`
- Subtitle: `從既有 SOP 到 Word 預覽：先預覽、再審核、最後才寫回`
- Layout/style: `linear-progression` + `corporate-memphis`
- Six cards:
  1. `從真實 SOP 開始` — `沿用既有資料，不從空白頁重做`
  2. `建立結構化草稿` — `章節、步驟、注意事項先排好`
  3. `員工提出修改` — `現場補充與修正都留在流程裡`
  4. `照片對應到步驟` — `每張照片放到該說明的位置`
  5. `產生 Word 預覽` — `先看版面、文字、照片，再決定下一步`
  6. `審核後才正式寫回` — `PD One 協助整理；最後由人員確認`
- Bottom banner: `安全原則：PD One 先產生 Word 預覽；Review → Approval 後才 official write-back。`
- PD One speech bubble: `我協助整理，最後仍由人員核准`
- Avatar: use the official Drive PD One avatar asset if available; otherwise use the PD One avatar prompt block and disclose prompt-based fallback.

## When to Use HTML/CSS Overlay or Compositing Instead

Use browser-rendered HTML/CSS or a Python/Pillow/SVG compositing workflow instead of pure image generation when:

- The exact text is contractual, legal, safety-critical, or must be copy-perfect.
- Bilingual Chinese/English parity must be exact.
- The artifact must be editable after generation.
- The official PD One avatar must be placed exactly from the Drive asset.
- The image model repeatedly misses counts, ordering, avatar details, or text.
- The user asks to preserve an existing infographic/photo exactly and modify only one small product detail.

For localized product retouching, do **not** prompt the image model to “recreate” or regenerate the full infographic. Lock the correct original file as the base, create a tight mask/bounding box around only the product detail, use deterministic raster/vector compositing for seams/highlights/shadows, and verify with a pixel-diff or changed bounding box that everything outside the mask stayed unchanged. If the overlay looks pasted, reduce opacity and prefer subtle molded seam/highlight enhancement over a broad filled panel. Deliver the conservative version unless the user asks for a more obvious edit.

If using overlay, follow `baoyu-infographic` reference `browser-rendered-instructional-infographics.md` and visually QA for clipping and CJK glyph rendering. For bilingual chart recreation tasks, also follow `references/bilingual-chart-rendering.md`: create an HTML/SVG artifact, embed or reference a Traditional Chinese font such as Noto Sans TC when headless Chrome lacks CJK coverage, render a PNG with headless Chrome, QA the result, then deliver the image with `MEDIA:/absolute/path.png` instead of stopping at pasted SVG source.
If the user asks to preserve the entire infographic and only revise a product detail, do **not** keep regenerating the full infographic. Treat the original image as the source of truth, edit only the target region, and visually QA that non-target areas are unchanged. See `references/localized-product-image-edits.md` for the bucket lid tear-tab example and deterministic local-edit checklist.

If using overlay, follow `baoyu-infographic` reference `browser-rendered-instructional-infographics.md` and visually QA for clipping and CJK glyph rendering. For bilingual chart recreation tasks, also follow `references/bilingual-chart-rendering.md`: create an HTML/SVG artifact, embed or reference a Traditional Chinese font such as Noto Sans TC when headless Chrome lacks CJK coverage, render a PNG with headless Chrome, QA the result, then deliver the image with `MEDIA:/absolute/path.png` instead of stopping at pasted SVG source.

## Common Pitfalls

1. **Overloading text.** Even with better text rendering, image models do best with short card labels and concise subtexts.
2. **Forcing one format.** This skill should support many infographic types; choose the form that best explains the source content.
3. **Trusting exact counts blindly.** Always visually verify card/panel counts and sequence numbers.
4. **Avatar drift.** For PD One-related visuals, prefer the official Drive avatar. If forced to prompt it, reinforce competent PD One avatar traits and reject toy-like results.
5. **Approval ambiguity.** PD One must appear as an assistant, not the final approver. Show human review/approval where relevant.
6. **Using admin/internal mechanics in employee visuals.** Do not include Hermes, PD Neo admin paths, tokens, logs, or implementation details unless the audience is Andy/admin.
7. **External prospect sheets.** Follow the External prospect sheets rules in `SKILL.md`. Do not default to image generation, the PD One avatar, or the purple employee palette for a company sales one-pager.

## Verification Checklist

- [ ] Source facts and must-include wording were preserved.
- [ ] Infographic type/layout fits the message instead of being forced into a single template.
- [ ] Main language is correct for the audience.
- [ ] Pro-Design company visual style is consistent.
- [ ] For PD One-related output, the official Drive avatar was downloaded/used when possible, or prompt-based fallback was disclosed.
- [ ] PD One avatar elements are visible, competent, and unclipped.
- [ ] Required number of cards/panels is present.
- [ ] Main headline and safety/CTA message are readable.
- [ ] No watermarks or unrelated logos.
- [ ] Visual QA completed before delivery.
- [ ] Artifact saved to a durable path and backed up when configured.

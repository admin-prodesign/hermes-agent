# Localized product-image edits while preserving an infographic

Use this when the user says the infographic/layout must remain the same and only one product detail should change (for example, bucket lid geometry). Do **not** keep regenerating the whole infographic unless the user explicitly wants a new concept.

## Lesson from bucket-lid tear-tab revision

The user wanted the whole `PLASTIC BUCKET KEY FEATURES` infographic preserved and only the bucket lid tear-tab changed to match a reference photo. Full gpt-image regeneration repeatedly changed the layout, text, card count, or bucket composition. The successful path was a deterministic local edit over the original PNG.

## Recommended workflow

1. Identify the original image that must be preserved and the reference image for the local detail.
2. Use vision to describe the target geometry in implementation terms.
3. Edit only the relevant pixel region:
   - mask/soften the incorrect product detail;
   - redraw molded highlights/shadows/seams/lips/rings as local vector-like overlays;
   - leave all text, panels, icons, background, and product body untouched.
4. Save to a durable artifact path.
5. Visually QA that:
   - non-target areas are unchanged;
   - the edited feature matches the reference;
   - no ghost/double artifacts remain;
   - the output is usable at full infographic scale.

## Bucket lid tear-tab geometry checklist

For the Pro-Design bucket example, the target tear-tab should be:

- on the **front vertical lid band**, not the top surface;
- a molded white horizontal recessed panel/strip;
- slanted/trapezoid end seams;
- diagonal crease/gate lines near both ends;
- a small circular pull ring/hole slightly left of center;
- a short lower pull lip beneath/behind the ring;
- white-on-white injection-molded plastic with subtle shadows, not a colored marker, sticker, or highlighted outline.

## Implementation note

If common image libraries are unavailable, a pure-stdlib PNG edit is possible by decoding PNG scanlines with `zlib`, applying anti-aliased line/polygon/circle overlays, and writing the PNG back. This is a fallback technique for preserving the exact original composition; prefer normal image-editing libraries when available.
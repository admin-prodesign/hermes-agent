# Mattermost Thread History Attachments

Use this reference when PD One/OpenClaw says it cannot see attachments in a Mattermost thread, or when implementing/reviewing Mattermost thread-context behavior.

## Durable lesson

Mattermost thread requests often arrive as a later reply that mentions `@pdone`, while the relevant context was posted earlier in the same thread. That context may be files attached to the root/parent post, or plain text such as a row number, anomaly summary, dates, options, or a clarification question. A channel agent that only passes the triggering websocket post's text/`file_ids`, or only relies on in-memory channel history, will lose context after a gateway restart or reconnect even though the bot account can re-fetch the visible Mattermost thread via REST.

PD One should treat an explicit mention in a Mattermost thread as permission to inspect the full visible thread history for context, subject to the same channel/user access policy. Users should not have to re-upload files already present in the thread or restate dates/details already visible earlier in the thread.

## Diagnostic sequence

1. Resolve the root post ID from the Mattermost permalink or triggering post.
2. Fetch the full thread with `GET /api/v4/posts/<root_post_id>/thread` using the PD One Mattermost bot token.
3. Inspect each post's `file_ids`, especially the root post.
4. For each file ID, verify bot visibility with:
   - `GET /api/v4/files/<file_id>/info`
   - a bounded download check against `GET /api/v4/files/<file_id>`
5. Distinguish:
   - bot cannot download file: permission/Mattermost visibility issue;
   - bot can download root files but agent cannot see them: ingress/context-construction issue.

## Holistic behavior rule

The intended Mattermost behavior is: **mention gates execution; the visible thread becomes the context unit after activation.** In group/channel traffic, an unmentioned message should not wake PD One, but a later mentioned message in that same thread should cause PD One to rehydrate the root post, intervening replies, bot replies, and all visible thread attachments via Mattermost REST. Do not solve this as separate mention/file/reply patches; review it as one ingress contract covering activation, thread fetch, context construction, attachment grounding, session routing, typing parent, and reply target.

## Patch pattern

At Mattermost ingress time, before building the agent context for an activated reply with `post.root_id`:

1. Fetch `/posts/<root_id>/thread`.
2. Build ordered thread context from `thread.posts`, sorted by `create_at` when available (do not assume Mattermost `thread.order` is chronological; it may not match display/time order).
3. Add a compact “Full Mattermost thread context” text block to the inbound envelope before the current message. Include author/sender when available, timestamp, post id, and concise body text. This is required even when there are no attachments.
4. Collect unique `file_ids` across all thread posts plus the triggering post.
5. Pass those IDs through the same remote-media download path as triggering-post attachments.
6. Include an explicit attachment manifest in the model-visible context: filename when available, file id, source post id, download/extraction status, and any failures. If the user asks “based on these docs/files/materials” and expected attachments cannot be downloaded or extracted, the agent must say that plainly instead of answering from general memory or unrelated installed skills.
7. Add a grounding/domain guard for attachment-driven requests: answers should cite or summarize the retrieved files first, then propose actions/skills. If the proposed output names skills/workflows that are not supported by the thread files, treat that as a regression even if the reply is otherwise fluent.
8. Keep failures non-fatal: if thread fetch fails, log/debug and continue with the triggering post so normal replies still work, but expose the missing-thread-context caveat to the agent.

## Source implementation companion

For code-level implementation/review details, helper-shape guidance, and exact regression commands, load `references/mattermost-thread-attachment-ingress-implementation.md`.

## Text-history restart/anaphora regression

Use this scenario when PD One appears to lose context in a Mattermost thread after it asked a clarifying question:

1. Bot posts a clarification that includes specific referents, e.g. `row 1334`, worker name, and dates `2026-05-06`, `2026-05-07`, `2026-05-29`.
2. Gateway restarts or reconnects, clearing in-memory channel history.
3. User replies in the same thread with an anaphoric instruction, e.g. “Correct them to June dates, keeping the day of the month the same.”
4. Expected agent context includes the fetched earlier thread messages, so the model can infer `2026-06-06`, `2026-06-07`, `2026-06-29` without asking the user to restate the dates.
5. Failing behavior: the agent says it only sees the instruction and needs the referenced dates. Treat this as a thread rehydration regression, not a user-communication problem.

## Verification checklist

- Regression/smoke test asserts the dist/source path contains the thread fetch, context builder, thread-level file collection, and media-resolution call.
- Regression/smoke test asserts text-only thread context is injected even when `file_ids` is empty.
- Regression/smoke test covers a gateway-restart/anaphora case: prior thread text contains the referents and the triggering message says “correct them” or similar.
- Syntax check the patched JS bundle/source.
- Live REST probe on the reported thread shows expected thread post count and file count.
- Bounded download checks return HTTP 200 for representative/all file IDs.
- If the original user intent was to ingest/analyze attachments, do a replay smoke test against the original root thread rather than stopping at file visibility: fetch/download the root files with the bot token, process them through the intended downstream workflow, and verify the resulting artifact or reply.
- Gateway restart is required for a dist hotfix to take effect; do not restart without Andy approval unless the approved unresponsive-gateway exception applies.
- For PD One/OpenClaw custom-source fixes, prefer the durable path first: update source, add a regression test, run targeted tests/lint, commit, and push to the configured custom branch. If the live gateway is running from an installed `dist/` bundle and a full package rebuild is blocked by transient dependency/network state, a bounded active-bundle hotpatch is acceptable only after source tests pass: back up the exact bundle, apply the same logic to the active runtime file, run `node --check` on the patched bundle, grep for the expected marker, restart the gateway, and verify `[gateway] ready` plus the channel reconnect. Report this as a temporary hotpatch plus committed source fix, not as a replacement for a clean rebuild.

## Smoke replay pattern for the original request

When Andy asks PD One to “process my original message as intended” after a Mattermost attachment visibility fix:

1. Re-fetch `/api/v4/posts/<root_post_id>/thread` with the PD One bot token and confirm the root post's `file_ids` are present.
2. Download each file by `GET /api/v4/files/<file_id>` into a bounded temp workspace; save a small manifest with original filename, file id, MIME/type, and local path.
3. Run the intended downstream workflow using the downloaded files, not just the triggering mention text. For wiki/document-ingestion requests, follow the company-wiki durable-source workflow and create source/synthesis pages with explicit caveats for files that need OCR/visual review.
4. Run the relevant verification checks (wiki lint/export dry-run, generated artifact readback, or other workflow-specific validation).
5. Post a concise bilingual smoke-result reply back into the original Mattermost thread. If the send command returns an empty or minimal payload, verify delivery by reading the thread via Mattermost REST and recording the new post id.
6. Mirror/backup durable wiki or configuration changes when the configured repo/backup path exists.

## Pitfalls

- Do not ask users to re-upload as the primary fix when files are already in a visible thread.
- Do not ask users to restate row numbers, dates, options, or clarification context that is already visible earlier in the same Mattermost thread; rehydrate the visible thread via REST.
- Do not rely on in-memory channel history after a gateway restart; fetch the thread from Mattermost REST.
- Do not only fetch attachments; earlier plain-text thread messages must also be carried into the model-visible inbound context.
- Do not only fetch text history; root attachments must be carried into the media payload.
- When Andy asks for ideas, skills, strategy, or next actions “based on these documents/files,” do not answer from PD One's existing admin/tooling context until the attachments have actually been downloaded and inspected. The reply must name or otherwise reflect concrete concepts from the files; generic employee-assistant/admin skills are a failure mode if the thread files are AI/design/training/domain material.
- For attachment-grounded skill proposals, separate (a) source evidence from the files, (b) proposed reusable skill names/workflows, and (c) caveats such as image-only PDFs needing OCR/visual review.
- Deduplicate file IDs before downloading to avoid repeated downloads when a post is represented in multiple places.
- Preserve access boundaries: full-thread context is for the visible thread/channel where PD One was mentioned, not arbitrary channel search.

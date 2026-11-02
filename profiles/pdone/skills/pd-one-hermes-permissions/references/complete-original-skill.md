---
name: pd-one-hermes-permissions
description: Use for PD One/Hermes Mattermost requests to resolve Hermes PD One profile permissions, channel policies, user/role profiles, review logging, language rules, and safety boundaries before answering or using tools.
version: 1.0.0
author: Hermes Agent
---

# PD One Hermes permissions bridge

Use this skill whenever the PD One Hermes profile handles Mattermost requests, especially employee DMs/channels, source-system access, writebacks, Mattermost history/log lookup, file/artifact delivery, permission changes, or unclear scope.

## Source of truth

The Hermes PD One profile is authoritative for Mattermost permissions/governance:

- Policy root: `/home/prodesign/.hermes/profiles/pdone`
- Channel policy: `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-channels.md`
- Canonical users: `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-users.json`
- Canonical roles: `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-roles.json`
- Effective user cache: `/home/prodesign/.hermes/profiles/pdone/policy-cache/mattermost/users/{mattermost_user_id}.json`
- Legacy OpenClaw workspace: `/home/prodesign/.openclaw/workspace` is a compatibility/reference mirror, not the source of truth, unless Andy explicitly asks to inspect or repair legacy state.

The Mattermost adapter injects `[PD One Hermes permission bridge]` into channel context when enabled. The label is retained for backward compatibility; treat the injected Hermes-sourced context as mandatory per-turn authorization evidence.

## Resolution order

1. Use the exact Mattermost sender ID from the gateway source/context. Never grant access by display name, username, remembered identity, prior sessions, or fuzzy match.
2. Read the matching effective cache file under `policy-cache/mattermost/users/{sender_id}.json` when the injected context is absent, incomplete, or the task is sensitive.
3. If the cache is missing/unreadable or `found=false`, use the user-facing setup/lookup-failure response. Do not answer substantive scoped questions or use privileged tools.
4. Apply channel policy from `mattermost-channels.md`, especially for admin/free-response lanes, undefined/default channels, language rules, Mattermost history lookup, and review logging.
5. Apply role/user policies from `mattermost-users.json` and `mattermost-roles.json` when the cache points to roles/scopes or when a request asks for expanded access.
6. For specialist or channel-bound channels, read the corresponding workspace charter before acting:
   - Inter-Department Discussion / legacy `senior-staff`: `/home/prodesign/.openclaw/workspace-senior-staff/AGENTS.md`
   - Facilities: `/home/prodesign/.openclaw/workspace-facilities/AGENTS.md`
   - Injection molding management: `/home/prodesign/.openclaw/workspace-injection-molding-management/AGENTS.md`
   - Main/admin: `/home/prodesign/.openclaw/workspace/main/AGENTS.md`

## Hard safety rules

- Mattermost channels/groups require explicit @mention unless a policy says otherwise.
- Mattermost channel/group final replies must be bilingual English + Traditional Chinese with 1:1 equivalent substance and detail; do not truncate, summarize, or make one language less complete than the other. DMs are the normal exception.
- Unknown/unprofiled users get setup/access guidance only.
- In the Inter-Department Discussion channel (`miiyt4zm9frexdbhxokxqgyxeo`, legacy agent id `senior-staff`), normal in-scope read-only cross-source operational lookups are pre-approved when the channel policy and requester role/scope allow them, including Mattermost/Yammer historical synthesis plus mold repair and 技術發展部/R&D references. Do not require per-request Andy/admin approval for ordinary read-only synthesis, and do not refuse merely because the request crosses these approved inter-department sources; apply least-disclosure and provenance guardrails.
- External sends, destructive actions, gateway/config/policy changes, permission expansion, source-system writes, Drive permission/move work, raw transcript or bulk export requests, broad Mattermost history/log search outside the Inter-Department channel policy or another explicitly approved policy, sensitive/private material beyond requester/channel scope, and high-impact operational writebacks require explicit approved-user authorization and dry-run where practical.
- Do **not** automatically restart the Hermes/PD One/OpenClaw gateway merely because code, config, or behavior was added or modified. Status checks, syntax checks, and non-invasive readiness probes are allowed; restarting requires explicit approved-user authorization unless bounded checks show the gateway is already unresponsive under the standing exception.
- If the exact sender id resolves to an active approved admin and the message explicitly uses an admin authorization form such as `admin:`, do not refuse a bounded current-channel config action solely because the surface is a shared/group channel. Instead, apply the normal write safeguards: verify scope, dry-run/readiness probe where practical, perform only the requested narrow change, read back the result, and keep the final bilingual.
- For normal employees, use scoped read/summarize/draft/help behavior; do not expose admin internals, unrelated channel history, private memory, logs, credentials, or raw policy mechanics.
- If data is unavailable or outside scope, do not ask users to paste sensitive data. Offer safe alternatives and log/escalate the access gap.

## Review logging

Follow `mattermost-channels.md` review-log rules for:

- unknown/unprofiled DM/channel requests
- onboarding/access gaps
- privilege/scope/tool/data-access change requests
- risky, ambiguous, out-of-scope, blocked, or approval-gated employee requests
- Mattermost history/log lookups and refusals
- attachments sent to employees

When available, use the deterministic Hermes PD One helper paths referenced by policy, especially `tools/mattermost_review_log.py`. Keep logs concise and never include secrets or unrelated private data.

### Handling `channel_no_reply_evidence` / `dm_no_reply_evidence` watchdog rows

When Andy/admin asks PD One to reply to a missed Mattermost request from a watchdog row:

1. Treat the watchdog digest and linked post as the scoped starting point; do **not** perform broad Mattermost history searches or codebase searches unless the linked post/thread fetch fails.
2. Fetch the linked post and its root thread, plus minimal user/channel metadata needed to address the requester and verify delivery.
3. If the missed request mentions an upload, attachment, file, filename, “yesterday”, “above/below”, “thread”, or a message that seems to depend on prior context, **expand within the same root thread before replying**: inspect sibling posts’ `file_ids`, `metadata.files`, and file-info records; match by exact filename first, then normalized filename fragments when safe. This same-thread expansion is not a broad history search.
4. For CAD/large engineering attachments, do not rely only on the Hermes document cache or filename extension. Also check known staged/input paths from the active work context and OpenClaw inbound media cache; identify STEP/STP files by content signature (`ISO-10303-21`, `FILE_SCHEMA`, `FILE_NAME`) when the saved file has no `.stp/.step` suffix. Report the exact path, internal STEP filename, size, source system/schema, and any parser receipt before claiming the file was or was not available.
5. If the referenced attachment/message is still not found in the root thread and local staged/inbound checks, state that precisely and ask for/link the source; do not say there is no attachment unless the full root thread scan plus relevant local attachment caches found none relevant.
5. Draft a normal employee-facing reply that answers the original user’s likely intent. If the original request reports an upload/filename, acknowledge the exact filename and state what was actually verified: linked post only, full thread, matching file id/name/size, or not found. Avoid implying source-system/Drive confirmation unless it was actually checked.
6. Post in the original thread/channel only after Andy/admin authorization when the row is in an admin review thread; for channel/group posts, make the employee-facing reply bilingual Traditional Chinese + English with 1:1 equivalent substance and detail, with neither side truncated or summarized.
7. Verify the created Mattermost post by readback and report only the delivery receipt/permalink back to Andy/admin.
8. If the review_log row should be closed or annotated after delivery, treat that as a separate writeback: do a dry-run list of the exact row/status/note first unless Andy explicitly asked for the update.
9. Keep the admin thread clean: avoid speculative progress messages, avoid exposing unnecessary tool internals, and do not spend time searching implementation files when a direct Mattermost API/helper path is sufficient.

### Quality-aware closure rule

Do **not** mark an employee DM row as simply `closed` just because PD One sent a reply. Track reply quality separately from delivery/completion:

- If the reply was policy-safe but did not use an available in-scope tool/source, mark `follow_up_needed=true` or `review_status=needs_quality_review` with notes such as `reply_quality_gap: available source/tool not used`.
- For employee requests that ask PD One to perform work (SOP drafts, document edits, source-backed standards, data lookup), closure requires evidence of action or a clear handoff artifact: draft id, source path, candidate file, approval packet, verified source citation, or explicit employee/admin blocking reason.
- For source-backed questions, answer_sources should name the source actually checked. If no source was checked while one was available, keep the row reviewable rather than closed.
- For approval-gated work, distinguish `closed_safely_blocked` from `closed_completed`; a safe refusal can close the safety issue but should leave a quality/follow-up note when a better within-scope draft or approval packet could have been prepared.
- Digest summaries should surface `closed_with_quality_gap`, `needs_quality_review`, and `source_not_checked` rows even if follow-up_needed is false, so Andy can see opportunities to improve reply quality.

### Reviewing open / closeable `review_log` items

#### `request_english` formula drift / translation-column maintenance

When Andy/admin reports that the `review_log` `request_english` column is misaligned or its arrayformula range has shifted:

- Remember the review-log writer inserts new rows directly below the header to keep newest-first order. A normal Sheets reference such as `$P$2:$P` in `Q1` can be structurally rewritten by Google Sheets after row insertions, producing drift like `$P$7:$P`.
- First verify the live `Q1` formula with formula rendering and inspect sample adjacent `request_summary` / `request_english` rows before recommending or applying a fix.
- For an immediate safe formula repair, use an insertion-stable reference such as `={"request_english";MAP(INDIRECT("P2:P"),LAMBDA(source,IF(source="","",GOOGLETRANSLATE(source,"auto","en"))))}` rather than a plain `$P$2:$P` reference.
- Prefer the long-term fix of code-populated static `request_english` values written by live header name, followed by a one-time backfill and removal of the sheet-level arrayformula. This avoids formula drift, live `GOOGLETRANSLATE` volatility/quota behavior, and row-to-row misalignment.
- When implementing the permanent fix, make the helper robust enough to replace the old `GOOGLETRANSLATE` behavior: split embedded `English:` lines, copy already-English summaries, and use a best-effort translation fallback when the summarizer/agent path is unavailable so CJK rows do not silently backfill blank.
- If changing the live sheet or helper code, treat it as a write/config-adjacent operational change: do a dry-run/readback where practical, preserve Andy's manual review fields, run tests, verify sample rows, and commit/push durable OpenClaw changes when applicable.
- See `references/review-log-request-english-static-values.md` for the detailed permanent-fix/backfill checklist and verification receipts.

When Andy/admin asks what is still open, what should be closed, or reports that a `review_log` digest looks wrong:

1. Treat the latest injected Mattermost `review_log` digest/thread context as **diagnostic evidence only**, not a source of truth for row-to-row attribution. Verify with the live sheet/helper when available before making claims or any writeback.
2. If a digest appears to attribute the wrong user, compare the displayed bullet against the live `review_log` row fields (`timestamp_utc`, `user_id`, `user_label`, `channel_name`, `category`, `request_summary`, `mattermost_post_id`, `root_id`, `reply_summary`). Watch for renderer/context-summary bugs that mix an actor from one row with a request summary from another row. Report whether the sheet rows are wrong or only the digest/context rendering is wrong.
3. For suspected digest rendering bugs, recommend fixing the generator to render each bullet from a single complete row object and include the sheet row number/post id; avoid separately zipped actor lists and summary lists.
4. Separate **true unresolved follow-ups** from **close candidates**. A row is not closeable merely because it is old or duplicated; it needs completion evidence such as a verified repair, delivered employee reply, resolved access gap, or a later superseding row that explicitly completed the same request.
3. Do not bulk-close open `capability_gap`, `approval_gated_request`, `channel_no_reply_evidence`, or `dm_no_reply_evidence` rows without checking whether the underlying user request was actually answered or completed.
4. For Google Sheets/Drive/AppSheet-related rows, closure evidence should include readback/verification receipts, delivery/notification status, and permission/write-scope notes when relevant.
5. If evidence is missing, recommend keeping the row open and state the concrete closure condition rather than guessing.
6. When a diagnostic pass discovers concrete blockers but does not complete the underlying request, update the open row with the blocker evidence (`reply_summary`, `notes`, `answer_sources`, `access_status`, `blocked_or_missing_sources` when present) while keeping `follow_up_needed=yes` / `review_status=open`. This makes the next admin pass actionable without falsely closing the request.
7. Any actual review-log status update is a write: require approved-user authorization, prefer a dry-run/explicit list of rows to close, then verify the sheet row after updating.

## Permission expansion across Mattermost roles, channels, and Drive

When Andy/admin approves a permission expansion that touches role bundles, channel policy, agent routing, generated cache, or Google Drive ACLs, treat it as a multi-layer change rather than a single JSON edit. Use the checklist in `references/role-channel-drive-permission-expansion.md`.

Key pitfalls:

- Separate Hermes policy capability from external ACL changes: a role grant does not automatically grant Google Drive writer access, and Drive sharing remains an approval-gated side effect.
- If promoting a default Mattermost channel into a specialist lane, update both the policy source (`mattermost-channels.md` / roles) and `openclaw.json` binding/group mention rule; otherwise the policy may say “specialist” while runtime still routes to the employee assistant.
- For reusable leadership roles, prefer function-level names (`qa_lead`) over title-implying names (`qa_manager`) when Andy asks for future-proofing.
- After canonical policy edits, run `tools/mattermost_policy_lookup.py generate-cache` and verify the target user lookup; expect many generated cache files to change because the source hash changes.
- `tools/mattermost_review_log.py append` skips Andy/admin rows by design (`skippedAndyRows`); do not count that as a failed review-log write.
- Do not restart the gateway solely to activate a config binding unless Andy/admin explicitly approved the restart or the gateway is already unresponsive under the standing restart allowance.

## Mattermost `admin:` escalation pitfall

When implementing or debugging PD One `admin:` escalation, detect the prefix from the raw Mattermost event text before the gateway prepends Hermes policy bridge, thread context, sender prefixes, or `[New message]` wrappers. A prepared message may no longer start with `admin:` even when the user's actual message did. Keep the full policy/thread context in the model prompt, but pass raw text separately to scope resolution. See `references/admin-prefix-escalation.md` for the detailed routing pattern, test cases, and safety constraints.

## References

- `references/cad-step-attachment-verification.md` — pitfall and checklist for Mattermost CAD/STP/STEP uploads saved without extensions or staged outside the Hermes document cache.

## Verification

Before completing a permission-sensitive task, verify:

- exact sender ID was used;
- policy cache was found and active, or the refusal/setup path was used;
- channel/group language and mention rules were followed;
- requested tool/data/action is inside the resolved scope;
- approval/dry-run/verification happened for writes or high-impact actions;
- review-log/escalation was done when policy requires it.

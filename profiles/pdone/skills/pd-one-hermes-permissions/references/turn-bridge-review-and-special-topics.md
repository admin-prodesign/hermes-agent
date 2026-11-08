# PD One permissions — review logging and special topics

## Review Logging
Use Hermes PD One review-log policy for refusals, risky/ambiguous/out-of-scope requests, onboarding/access gaps, blocked tool/data access, employee privilege requests, broad history/log lookups, and employee attachment sends. Keep entries concise and secret-free.

### Review-log open issue triage
When Andy/admin asks to review open `review_log` items:
- Treat review-log status changes as writes: inspect and recommend first; only update rows after approved-user authorization.
- Do a strict open pass (`review_status=open` or non-closed with `follow_up_needed=yes`) so old manually-closed rows with stale `follow_up_needed=yes` do not dominate the review. Report both counts separately: strict-open rows and closed rows that only need stale `follow_up_needed` normalization.
- Prefer a compact triage table for Andy/admin: row number, case/request, verification basis, and recommended action. Avoid dumping raw Sheet rows or long Mattermost excerpts unless asked.
- Build closure plans as targeted cell/range updates only (for example `follow_up_needed`, `review_status`, `reply_summary`, `notes`), run a Sheets dry-run batch update first, and ask for approval before applying.
- For response-quality rows, distinguish “employee needs follow-up” from “reply quality should be learned from.” If the user received an adequate later answer or the issue is historical, recommend closing the row while preserving the quality flags/reason.
- For `dm_no_reply_evidence`, verify the exact DM channel history before sending a duplicate corrective DM. If the employee’s later message already has normal PD One reply evidence, delivered attachments, a setup/onboarding reply in-thread, a later top-level onboarding DM, or a completed artifact in the same/root-linked DM thread, close the stale review row instead of re-contacting the employee. Use a dry-run update plan when practical, then targeted row/cell updates only, and read back `review_status`, `follow_up_needed`, and evidence notes.
- When an older review row is already `closed` but still has stale `follow_up_needed=yes`, normalize it with a targeted update after verifying the underlying issue is resolved; otherwise watchdogs may keep surfacing historical items.
- For automation-related rows, verify the actual producer/cron/job/log receipt before closing; a tracker field such as `Reminder Date` alone is not proof that sends are wired.
- For ECRN approval-thread rows where the employee message is just an approval token such as `同意`, verify the deterministic ECRN approval pilot before recommending closure: run it in dry-run/no-sheet-sync mode, inspect `state/ecrn-approval-pilot.json` for the exact Mattermost post id/user id/status, and confirm the workflow stage advanced or the approval is recorded. Treat a recorded approval as handled workflow evidence, not an employee follow-up requiring a corrective reply.
- For completed ECRN approval threads, the next expected artifact is a signed ECRN document, not just a completion notice. Preserve the original `.doc` formatting and insert timestamp/person/comment approval text into the existing relevant table cells; do not rebuild the form as a new layout unless explicitly requested. In approved `~ecrn` send-mode, post the signed Word-openable file back to the same thread automatically and verify the post/file receipt; draft in an admin review thread only when Andy/admin explicitly requests review-first handling. See `references/ecrn-signed-document-compilation.md`.
- If closing is approved, use targeted row/cell updates only (for example follow-up/status/notes), append a concise closure note with the verification basis, and avoid whole-sheet rewrites that could clobber Andy’s manual review state.
- For `dm_no_reply_evidence` rows, verify the exact DM post/thread by REST before replaying or replying. Confirm the sender’s exact policy/cache user ID matches the live Mattermost user, check for any later `pdone` reply in the same thread, and only send a bounded catch-up when no reply exists and Andy/admin has authorized it. After sending, read back the reply post and close/update only the targeted row/cells with `follow_up_needed=no`, `review_status=closed`, a concise reply summary, and the verified reply post ID in notes.
- For review rows that say a bot reply was found, do **not** assume the case is resolved from “bot reply found” alone. Inspect the exact Mattermost thread and distinguish: (1) a complete employee-visible answer/artifact, (2) a refusal/setup/approval-gated reply, (3) a partial text draft where the requested file/artifact was never delivered, and (4) stale row state. If the employee requested same-thread document formatting/generation from their own attachment and PD One exposed an internal dangerous-command approval gate instead of delivering the file, treat it as a PD One tooling/workflow failure: keep the row open until the printable/exported artifact is generated, attached back to the origin thread, and verified with Mattermost file/post receipts. The admin-facing summary should name the real blocker, not just “bot reply found.”
- For detailed repeatable steps and evidence-note templates when reviewing open `review_log` rows, see `references/review-log-open-triage-recipe.md`.

## Employee ISO / procedure questions
When a scoped employee asks whether Pro-Design/良器 ISO “requires” a specific operational action (for example outsourced-vendor audit frequency, import/export inspection, IQC/OQC responsibility):
- Treat this as quality/work-manual/company-knowledge read-only work unless the request asks to edit a source system or policy.
- Search formal procedure/work-manual/reference-document surfaces first when available; only use Mattermost history or operational chat excerpts as secondary evidence and stay within the requester's scoped channels/data access.
- Do **not** turn operational evidence into a formal ISO requirement. Clearly separate: (1) “formal ISO/procedure text found,” (2) “operational records suggest,” and (3) “not enough basis found.”
- Prefer conservative wording such as “目前查無明文規定…” when no formal clause is found, then state the likely applicable controls (e.g., 進料檢驗 SIP/IQC for incoming materials; 成品/出貨檢驗/OQC, SIP, customer/legal requirements for outgoing/export goods).
- Give the employee a short internal-reply draft they can use, and ask for the exact form/procedure name or screenshot if they need line-by-line confirmation.
- Avoid exposing raw transcripts, private policy internals, or broad-history implementation details; summarize only the minimum evidence needed.

## Issued ISO and work-manual contradiction check
Andy 2026-10-12: work manuals and issued ISO process flows must not contradict each other. The check is bidirectional. Before a work-manual operating-rule edit, read the matching `\\sql-srv\管理部\文管中心\發行版` flow. When an issued ISO document is revised, read the matching work manuals against the new issued text. Report every contradiction. Do not leave both texts in force while they deny each other. A narrower responsibility note inside a right the issued document already grants is not a contradiction. Follow `google-docs-work-manual` reference `historical-procedure-evidence-before-manual-edit.md`.

## Verification Checklist
- [ ] Exact sender-id policy context was present or cache was read.
- [ ] Sender id was not recovered with a shell or `execute_code` print. Shared-room shell stayed on typed tools. A plugin edit is not called active until the gateway that loads it has restarted.
- [ ] Channel scope and language requirements were applied.
- [ ] Approval-gated side effects were dry-run/confirmed when required.
- [ ] Specialist workspace/policy file was read when relevant.
- [ ] Final answer reveals only allowed, minimal information.

## Historical multi-source search
For historical process/parameter lookups, follow `references/historical-search-source-ladder.md`: pre-approved Inter-Dept Mattermost/Yammer synthesis, domain-scoped Yammer tool, and mandatory `Sources checked / 已查來源` reporting.

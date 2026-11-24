# PD One Personal Employee Memory

## When to load
Load this reference when designing, implementing, reviewing, or troubleshooting PD One/OpenClaw per-employee memory, personal profiles, `remember/forget/list` tools, or memory privacy behavior for employee-facing Mattermost interactions.

## Source plan and implementation state
The OpenClaw-compatible implementation plan and first implementation slice are committed in the OpenClaw downstream repo:

- Repo: `/home/prodesign/openclaw`
- Branch: `pd-one/custom-openclaw-patches`
- Plan: `docs/plans/2026-05-21-personal-employee-memory.md`
- Original plan commit: `70796e1022 docs: plan personal employee memory`
- Privacy hardening commit: `1cd8a95acb docs: harden personal memory privacy plan`
- Threat-hardening commit: `9606594529 docs: add personal memory threat hardening`
- Encryption-scope simplification commit: `062130a49a docs: scope personal memory encryption to future hardening`
- Initial identity/config implementation commit: `265ee56cf2 feat: add personal memory identity foundation`
- Storage/tools/prompt/command implementation commit: `cd91850239 feat: add personal memory storage and controls`
- Runtime trusted-context wiring commit: `aa5128040a feat: wire trusted personal memory context`

Use the latest committed plan as the primary implementation checklist before coding. Current bundled-plugin implementation includes config, trusted subject identity resolution, SQLite-backed storage, filters, explicit tools, prompt rendering, natural-language command helpers, suggest-only candidate detection, local CLI helper functions, and additive OpenClaw runtime/plugin context plumbing. The plugin intentionally fails closed if trusted sender/workspace/account/provider/visibility fields are missing or cannot prove a direct/private conversation.

## Core architecture
- Implement personal memory as a bundled, manifest-first OpenClaw plugin named `personal-memory`, not as PD One-specific core logic.
- Keep personal employee memory separate from `memory-core` company/wiki/shared memory.
- Do not replace or conflict with `memory-core`'s exclusive `registerMemoryPromptSection` ownership.
- Prefer prompt injection via `before_prompt_build` for MVP unless the memory supplement API gains trusted per-run sender/account context.

## Subject identity and isolation
- The model must never choose whose personal memory to read or write.
- Trusted sender identity is necessary but not sufficient for memory reads: the conversation must also be proven private.
- Resolve the memory subject only from trusted runtime context, such as Mattermost sender/account/session metadata exposed by OpenClaw.
- Normal employee tools must not accept model/user-supplied `senderId`, `accountId`, `subjectKey`, or equivalent target-subject parameters.
- Key profiles by `(scopeId, channelProviderId, workspaceId/serverUrlHash, agentAccountId, senderId)`, with `scopeId` defaulting to `agent:{agentId}`.
- At-rest encryption and HMAC/secret rotation are optional future hardening unless a compliance/storage-compromise requirement appears. MVP should prioritize application-boundary leak prevention, owner-only file permissions, data minimization, and redacted logs/traces.
- If using deterministic SHA-256 subject keys, hash a canonical JSON array/length-safe tuple rather than delimiter-joining fields.
- Treat provider/workspace/account/sender IDs as opaque: trim only for empty checks, but do not lower-case, NFKC-normalize, or otherwise identity-normalize before hashing. Providers may treat case/Unicode-distinct IDs as different identities.
- Fail closed if trusted sender identity, account/workspace identity, required scope metadata, supported plugin config, or required private conversation visibility is missing.
- Do not parse identity from `sessionKey`, channel names, mentions, display names, or user-visible text for the MVP.
- Shared scope detection must require the exact supported placeholder `{agentId}` for per-agent scopes. Case variants like `{agentid}` or `{agentID}` are literal strings and must be treated as shared/non-agent scopes unless `allowSharedScope: true` is explicit.

## Privacy defaults
- Default plugin disabled until explicitly configured.
- Default `autoCapture.enabled = false` and `autoCapture.suggestOnly = true` until Andy/admin approves broader preference capture.
- Less-conservative approved direction: user preferences about how PD One should work with that person inside their already-authorized scope may be captured when the user is safely identifiable; user claims that could change what they can see, edit, approve, share, or administer must be admin/policy-gated and must not become trusted access facts from self-report alone.
- Live plugin guard: `personal-memory` rejects `role`/`responsibility` category saves and content matching role/team/department/permission/access/edit/approve/share/admin claims, while allowing safe preferences such as response style, language, formatting, and workflow reminders inside existing scope.
- Regression receipt: run `node /home/prodesign/.hermes/profiles/pdone/scripts/personal_memory_access_scope_regression.mjs` after personal-memory changes; it verifies safe preference capture remains allowed and English/Chinese self-reported role/access claims are blocked.
- Default `readsRequirePrivateConversation = true` for every read/list/export/prompt-injection path.
- Start with explicit employee controls: remember, forget, list/"what do you remember", and update profile.
- For MVP, allow personal memory reads only in proven `direct` conversations. Treat `public_channel`, `group`, and `unknown` as fail-closed; consider `private_channel` only after a separate product/security decision.
- A less-conservative production configuration may enable auto-capture for low-risk preference memory, but not for access/authority claims. Safe auto-capture categories include response length/style, language order, formatting preferences, reminder/report cadence preferences, and how the user wants to work within already-authorized scopes.
- Any user statement that could influence what data they can see, edit, approve, share, administer, or otherwise access must be admin/policy gated. Examples: claimed department/team/role/work area, approver authority, ownership of a process, request to edit a protected sheet, or claimed HR/Finance/QA/admin status. Store at most an `unverified_claim` that is never used for authorization, or route to Andy/admin verification before promoting it to trusted profile/policy data.
- Operational preferences can be remembered, but side effects still follow normal approvals. Example: “send reports to me every Friday” can be captured as a preference, while creating the scheduled send still requires the appropriate approval/setup/receipt path.
- Do not silently store HR/evaluation, salary, health, conflict, credential, secret, legal allegation, discipline/performance, or similarly sensitive/private content.
- Redact credentials/secrets rather than preserving them.
- Public/group-channel behavior must fail closed for private memory disclosure and management: do not inject, list, export, suggest, or echo private memory content. However, low-risk interaction preferences stated publicly (for example “reply shorter” or “use Chinese first”) may be captured for that safely identified user if auto-capture is explicitly enabled and the preference does not affect data access/edit scope.
- SQLite DB, WAL, SHM, and sidecar files should be owner-only permissions; logs/doctor output should redact PII.
- Treat prompt logs, traces, installed plugins, and the model provider as privacy trust boundaries; redact/tag personal memory prompt blocks wherever the framework permits.

## OpenClaw compatibility notes
- Extensions/plugins should import only `openclaw/plugin-sdk/*` and local files for OpenClaw SDK surfaces. Node built-ins may be acceptable for runtime utilities in existing extensions, but keep imports minimal and check extension-boundary tests.
- Avoid PD One-specific special cases in OpenClaw core.
- If plugin hooks lack trusted sender/account/conversation/config fields, add additive SDK/context improvements rather than using model-supplied tool arguments as identity.
- Current safe context plumbing adds the same trusted route metadata to plugin tool context and `before_prompt_build` hook context: `channelProviderId`, `workspaceId`, `agentAccountId`, `requesterSenderId`, `currentChannelId`, and `conversationVisibility`.
- Infer privacy from trusted route/session data only: `:direct:` session routes may become `direct`; `:group:` routes or explicit `groupId` must become `public_channel`; otherwise use `unknown`. Use `sessionKey` only for route visibility inference, never for subject identity.
- Delivery context may fill provider/account route metadata (`channel`, `accountId`) but must not fill `requesterSenderId`; sender identity must come from explicit trusted runtime sender fields.
- Direct-chat inbound metadata may include `sender_id` for future personalization paths, but group/public trusted metadata must omit sender id to avoid treating public senders as private-memory subjects.
- Both `before_prompt_build` and `before_agent_reply` need trusted sender/account/config/visibility context for safe injection and command handling; if unavailable, refuse.
- Tool-level privacy gating is mandatory. Do not rely only on natural-language command interception because the model can call list/read tools during a public-channel answer.
- Verify interaction/button paths preserve trusted requester identity; if not, disable personal memory for that path. Future approval buttons must be signed, single-use, expiring, sender-bound nonces; never trust identity from button payload alone.
- Admin CLI list/export/forget/purge must require explicit scope/agent plus channel/account/sender; avoid broad defaults across scopes.

## Session-history backfill workflow
When Andy/admin asks to backfill per-user memory from prior sessions, be active but conservative. Treat plural language like “users' memories” as a fleet backfill across known employee/admin senders in session history, not a current-user-only update; if scope is unclear, default to producing a reviewed multi-user candidate artifact rather than silently doing just Andy/current requester.

1. Search/inspect past sessions for explicit low-risk preference statements and repeated interaction corrections, not inferred identity/access facts.
2. Produce a candidate list with source evidence, category, and disposition before any broad write. Safe examples: brevity/洗版 preference, language order, formatting/table handling, workflow reminders inside existing authorized scope.
3. Exclude or admin-gate anything that could affect data visibility, edit rights, approvals, sharing, administration, role/team/work-area, or source-system scope.
4. Do not infer stable private preferences from task language alone; a Chinese request is not by itself a durable “prefers Chinese” memory.
5. Do not manually insert personal-memory SQLite rows unless the exact trusted private-memory subject tuple is known and policy-verified: `(scopeId, channelProviderId, workspaceId/serverUrlHash, agentAccountId, senderId)`. Guessing the tuple risks unusable or cross-scoped memory.
6. If the exact tuple is unavailable, update the safe human-readable user memory/profile or a reviewed candidate artifact, then note that true plugin-backed per-employee memory needs an admin CLI/helper using explicit tuples.
7. Keep the reportback short: what was backfilled, what was intentionally not saved, and the receipt path/commit if applicable.

## Implementation review checklist
- Cross-user isolation: user A cannot read/write/list user B's memory by prompt injection, tool args, command text, button clicks, or admin CLI scope omission.
- Cross-agent isolation: another agent using the same Mattermost account and sender IDs does not see PD One memories unless scope explicitly allows it.
- Missing identity/config/visibility: no prompt injection, reads, or writes happen when trusted identity, supported config, or private visibility is absent.
- Public/group channel: private profile content is not injected, disclosed, suggested, or written into public/group/unknown contexts, even when the sender id is trusted.
- “What do you remember about me?”: must be DM/private-only, tool-level gated, and tested against session transcript contamination.
- Auto-capture: stays off/suggest-only until filters and explicit approval are proven; suggestions are also private-only.
- Admin inspection: local-only, scope-explicit, permission-checked, redacted by default, and never exposed to normal employee chat tools.
- Deletion semantics: document soft-delete vs purge/VACUUM, WAL/SHM, transcripts, logs, and backup retention expectations.

## Current module map
- `extensions/personal-memory/index.ts`: plugin entry plus `extractPersonalMemoryIdentityContext`; maps trusted tool/hook context into identity context, uses delivery context only for route metadata, and fails closed for missing sender/privacy proof.
- `src/config.ts`: strict fail-closed config defaults; rejects unsafe enabled configs unless explicitly acknowledged.
- `src/identity.ts`: subject resolver and deterministic canonical subject-key hash from trusted context only.
- `src/store.ts`: SQLite store with migrations, WAL, owner-only permission checks, symlink rejection, soft delete, and profile revisions.
- `src/filter.ts`: sensitive-content, prompt-injection, hidden-Unicode/control-character, and chat-output escaping helpers.
- `src/tools.ts`: explicit `personal_memory_list`, `personal_memory_remember`, and `personal_memory_forget` helpers/tools; never expose identity override params.
- `src/prompt.ts`: private-only ephemeral/sensitive prompt block rendering with item/char caps.
- `src/commands.ts`: deterministic `remember/list/forget` natural-language command helpers in English/Chinese.
- `src/candidates.ts`: suggest-only candidate detection; no silent writes.
- `src/cli.ts`: local admin helper functions with explicit subject tuple and raw export acknowledgement.

## Runtime smoke-test credential handling
When validating personal employee memory against the real PD One/Mattermost flow, use a real employee/admin account token rather than the PD One bot token for requester-side smoke tests. The existing Mattermost bot credential verifies bot posting/API access only; it cannot prove memories are keyed to the employee sender identity.

- Preferred @admin PAT drop file: `/home/prodesign/.openclaw/workspace/keydrop/mattermost-admin.env`.
- Required line: `MATTERMOST_ADMIN_TOKEN=<pat>`; optional `MATTERMOST_ADMIN_USERNAME=admin`.
- Keep parent directory mode `0700` and file mode `0600`; do not ask the user to paste the PAT into chat.
- User has approved using this @admin account for future PD One DM smoke tests, Testing-channel behavior tests, and prompt-injection tests.
- After the token is present, verify only `/api/v4/users/me` username/id and do not print the token.
- Known Testing channel for public/private-channel behavior probes: id `shrapa36ifbrtpfcrb1sayjh6o`, name `testing`, display `Testing`, type `P`.
- Smoke test shape: admin DM to PD One can `remember/list/forget`; Testing/channel context must return only the DM redirect and must not reveal whether private memory exists.
- Remove/revoke the PAT only if it was explicitly temporary; otherwise treat the keydrop as the reusable admin-user smoke-test credential.

## Live PD One deployment/integration gotchas
For live PD One smoke tests, do not assume the downstream source checkout is the same thing as the running Gateway package. First confirm the installed package/runtime contains the plugin, then deploy the plugin into `~/.openclaw/workspace/plugins/personal-memory` or install the updated downstream build before enabling it.

- Personal-memory SQLite store parent directories must be owner-only. Use a restricted path such as `/home/prodesign/.openclaw/workspace/keydrop/personal-memory-state/` with directory mode `0700`; otherwise plugin registration can fail with `personal-memory store parent must be owner-only`.
- Non-bundled/workspace plugin manifests that register agent tools need explicit `contracts.tools` entries for `personal_memory_list`, `personal_memory_remember`, and `personal_memory_forget`; otherwise Gateway rejects tool registration.
- Workspace plugin manifests need startup activation metadata (`activation.onStartup: true`) when expecting Gateway to load them at startup.
- Conversation hooks for non-bundled plugins require config permission, for example `plugins.entries.personal-memory.hooks.allowConversationAccess=true`; otherwise `before_agent_reply`/conversation access can be blocked.
- The `before_agent_reply` handler must call `handlePersonalMemoryCommand(deps, messageText)` in that order. If reversed, live logs show `input.normalize is not a function` and the command is ignored while the normal LLM path may answer from transcript context.
- Smoke tests are not proven by the LLM saying it remembers a marker. Verify the SQLite store has an inserted entry and the plugin returns deterministic `Saved private memory ...` / list / forget responses before declaring durable memory working.
- If admin DM messages reach PD One but no deterministic personal-memory reply appears, add temporary hook diagnostics for: command text extracted from `event.cleanedBody`, `ctx.requesterSenderId`, `ctx.agentAccountId`, `ctx.channelProviderId`, and `ctx.conversationVisibility`. This distinguishes hook-not-called, event-shape mismatch, and trusted-context-missing failures.
- Run the Testing-channel fail-closed smoke only after the DM command path is known to be the plugin path; otherwise the channel result may only test normal LLM behavior.

## Regression and review commands
Use TDD for each implementation slice. Useful gates for current implementation:

```bash
pnpm vitest run extensions/personal-memory --config vitest.extension-memory.config.ts
pnpm vitest run src/agents/openclaw-tools.plugin-context.test.ts
pnpm test -- test/scripts/test-extension.test.ts
git diff --check
```

Include runtime-context regression tests when touching identity plumbing: `extensions/personal-memory/src/plugin-context.test.ts` should prove route metadata fallback does not become sender identity, and `src/agents/openclaw-tools.plugin-context.test.ts` should prove group sessions are public and direct sessions forward trusted sender fields. `pnpm tsgo`/full `pnpm check` should still be run when possible, but if it fails on pre-existing unrelated repo errors, record the exact unrelated failure and rely on scoped tests plus staged lint/format only for that slice.

Before committing security-sensitive personal-memory code, ask an independent reviewer/subagent to inspect staged changes. In this session that review caught two subtle blockers: opaque IDs were being lowercased/normalized, and case-insensitive `{agentId}` detection allowed literal shared scopes like `agent:{agentid}` to bypass the shared-scope guard.

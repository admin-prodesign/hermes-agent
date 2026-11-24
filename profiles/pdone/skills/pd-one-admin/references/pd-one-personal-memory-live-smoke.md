# PD One personal-memory live smoke notes

Use this when enabling or repairing the employee private memory feature in PD One/OpenClaw.

## Durable integration lessons

- `personal-memory` must not claim the generic memory plugin kind when `memory-core` owns that slot. Use startup activation instead of `kind: "memory"`.
- External plugins that register tools need manifest tool contracts. For this plugin, declare:
  - `personal_memory_list`
  - `personal_memory_remember`
  - `personal_memory_forget`
- Conversation hooks from non-bundled workspace plugins require explicit config allowance:
  - `plugins.entries.personal-memory.hooks.allowConversationAccess=true`
- The direct command path should run through `before_agent_reply`, before normal LLM generation, so `remember/list/forget` commands are deterministic and do not depend on the model using tools correctly.
- Command-text extraction from hook events should be defensive: read `event?.cleanedBody`, handle nested `text/body/message/content/cleanedBody` containers, cap recursion depth, and return `{ handled: false }` on blank/non-command text.
- Avoid unnecessary plugin runtime dependencies for tool schemas. Plain JSON schemas are sufficient for `personal_memory_*` tool params and prevent missing-package failures in live plugin bundles.
- For live Mattermost DM behavior, the hook context must include trusted sender identity fields, otherwise the memory subject key cannot be built safely:
  - `requesterSenderId`
  - `requesterSenderName`
  - `agentAccountId`
  - `workspaceId`
  - `serverUrlHash` fallback when no workspace/team id is available
  - normalized `conversationVisibility`
- Determine private/direct status from trusted `ChatType`/conversation visibility, not by substring matching a session key. Pass `requesterSenderId`/`requesterSenderName` only when the trusted visibility is direct; channel/public/private-channel turns should fail closed and avoid building a personal subject.
- Keep `agentAccountId` distinct from workspace/team identity. For Mattermost, prefer `GroupSpace`/team id for `workspaceId`; use the account id only as a fallback `serverUrlHash` when no workspace id exists.
- If a `before_agent_reply` hook returns a synthetic reply, ensure the payload is marked for source-suppression delivery; otherwise the command may be handled but no visible message is sent.
- Keep the store parent owner-only (`0700`/`0600` style permissions). The plugin should fail closed if the SQLite store parent is too permissive.
- Keep command handling private/direct by default. Public/channel attempts to manage personal memory should fail closed with copy like: `Please DM PD One to manage private memory.`

## Known-good smoke shape

DM smoke using @admin to PD One should verify all four steps:

1. `remember that <marker>: <preference>`
   - Expected: `Saved private memory <id>.`
2. `what do you remember about me?`
   - Expected: list contains `<id>` and `<marker>`.
3. `forget <id>`
   - Expected: `Forgot that private memory.`
4. `what do you remember about me?`
   - Expected: `I don’t have any private memory saved for you yet.`

Channel smoke in Mattermost `Testing` should verify fail-closed behavior:

1. `@pdone remember that <marker>: channel smoke should not be saved.`
   - Expected: `Please DM PD One to manage private memory.`
2. `@pdone what do you remember about me?`
   - Expected: `Please DM PD One to manage private memory.`
3. Inspect the SQLite store and confirm the channel marker was not written.

## 2026-05 live repair receipts

A known-good live repair ended with source commit `c4ff4fe5e6` on `admin-prodesign/openclaw` branch `pd-one/custom-openclaw-patches-v2026.5.19` (`Fix personal memory command hooks`). The important proof points were:

- Personal-memory extension tests: 10 files / 36 tests passed.
- Core hook tests passed during the repair:
  - `src/auto-reply/reply/get-reply.before-agent-reply.test.ts`
  - `src/plugins/hooks.before-agent-reply.test.ts`
- DM smoke marker was saved, listed, forgotten, then absent on final list.
- Mattermost `Testing` channel smoke replied `Please DM PD One to manage private memory.` and the channel marker was absent from SQLite.
- A hot-patched installed global OpenClaw dist can make PD One work immediately, but it is not a substitute for a proper source rebuild/reinstall; always prefer replacing the hotfix from the committed source once build/install is healthy.

## Runtime cautions

- If source is fixed but live PD One still behaves incorrectly, confirm whether the installed OpenClaw dist/runtime has been rebuilt or hotfixed. Source-only changes do not affect the already-installed global package until deployed.
- Treat keydrop config patches and Mattermost PAT files as sensitive; never copy their raw values into notes.
- Remove temporary diagnostic logging from `personal-memory` after smoke tests pass.
- When polling Mattermost for live-smoke replies, avoid matching stale earlier bot messages. Use a `since` timestamp from immediately before the test post, sort posts by `create_at`, exclude the admin/posting user, and prefer reply/content checks tied to the marker or expected phrase. If polling returns a surprising repeated old post id, fetch recent channel posts and verify the sequence manually before declaring failure.
- After a remember/forget smoke, verify SQLite state by `deleted_at` status, not just by marker text existence. A successful forget may leave a deleted row; the durable pass condition is `active_dm_marker_count == 0`, `active_channel_marker_count == 0`, and, for cleanup evidence, the test DM marker may appear only with `deleted_at is not null`.

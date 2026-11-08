# Mattermost Thread Attachment Ingress Implementation Notes

Use this companion reference when implementing or reviewing OpenClaw/Mattermost code changes that ensure PD One sees documents attached earlier in a Mattermost thread.

## Trigger

A user mentions PD One in a later Mattermost thread reply and asks it to use “these files/docs/materials,” but the relevant files were attached to the root post or an earlier reply. The websocket event for the bot mention may contain no `file_ids`, so resolving only `post.file_ids` silently drops the source documents.

## Source-level pattern

In the Mattermost extension source:

1. Add a client helper for `GET /api/v4/posts/<root_id>/thread` and parse the returned shape with a schema containing at least:
   - `order: string[]`
   - `posts: Record<string, MattermostPost>`
2. At inbound dispatch, before `buildAgentMediaPayload(...)`:
   - if the triggering post has `root_id`, fetch the thread root;
   - collect posts in `thread.order`, plus any posts present in `thread.posts` but missing from `order`, plus the triggering post if it is absent from the fetched thread;
   - collect/deduplicate `file_ids` in that order;
   - download those IDs through the existing Mattermost media resolver, not a new ad hoc fetch path.
3. Preserve the source file ID on each resolved media object (`fileId`) so the attachment manifest can be matched to download results even when some downloads fail.
4. Build a model-visible manifest and append it to both the inbound envelope body and `BodyForAgent`/`RawBody`:
   - `file_id`
   - `source_post_id`
   - `status=pending|downloaded|missing|failed`
   - `content_type` and `local_path` when available
   - thread-fetch/download caveat when applicable
5. Keep failures non-fatal for normal chat routing, but expose the caveat to the agent. A silent fallback to “no files” is the bug.
6. Add the grounding guard inside the visible attachment context: for document-grounded requests, the agent must cite/summarize retrieved files first or state which files were unavailable; it must not answer from general memory or unrelated installed skills.

## Holistic Mattermost ingress contract

Treat Mattermost support as one coherent ingress pipeline, not as isolated patches for mentions, replies, files, or previews:

1. **Mention gates execution.** In channels/groups, PD One should not dispatch the model unless the triggering message explicitly mentions PD One, uses an authorized command bypass, or is in a separately configured direct-message/onchar mode. Dropped unmentioned messages may be recorded as lightweight pending history, but should not download files, invoke tools, or reply.
2. **Thread is the conversation unit after activation.** Once the triggering message is authorized, resolve the canonical thread/root id and fetch the visible Mattermost thread via REST. Include root text, prior replies, prior bot replies, the triggering reply, and all visible thread attachments in the model-visible context.
3. **Do not confuse passive context with activation.** An unmentioned reply earlier in the same thread should not wake PD One, but it should become context later when a subsequent reply mentions PD One in that thread.
4. **Reply routing follows the same canonical thread id.** The reply target, typing indicator parent, session key, `MessageThreadId`, and attachment source ids should agree on the same root/thread identity.
5. **Failure is visible but non-fatal.** If thread fetch or attachment download fails, continue with the current message only when safe, but expose a caveat and attachment manifest to the agent so it does not answer document-grounded requests from unrelated memory.

## Regression tests to add

Minimum tests:

- Root post has files; later reply mentions the bot and has no or different files; collected IDs include root files first and dedupe repeated IDs.
- Mentioned threaded reply fetches and injects full text context: root post, prior human replies, prior bot replies, current reply marker, and chronological order by `create_at` when available.
- Unmentioned channel/thread message is dropped before dispatch and before remote file download; a later mentioned reply in the same thread can still rehydrate that prior text/files from Mattermost REST.
- Reply/session routing for a thread uses the root/effective thread id consistently for `ReplyToId`, `MessageThreadId`, typing parent, and session key.
- Manifest builder includes file ID, source post ID, download status, local path/content type when downloaded, caveat text, and the document-grounding guard.
- Media resolver preserves `fileId` in resolved media metadata so manifest status can be mapped back after partial failures.

## Verification commands

Use the narrow tests first, then a broader Mattermost extension run if time permits:

```bash
node scripts/run-vitest.mjs run extensions/mattermost/src/mattermost/monitor.test.ts extensions/mattermost/src/mattermost/monitor-resources.test.ts
pnpm lint -- extensions/mattermost/src/mattermost/client.ts extensions/mattermost/src/mattermost/monitor.ts extensions/mattermost/src/mattermost/monitor-resources.ts extensions/mattermost/src/mattermost/monitor.test.ts extensions/mattermost/src/mattermost/monitor-resources.test.ts
git diff --check
node scripts/test-extension.mjs mattermost
```

If a full extension run times out on slow unrelated tests, rerun the named failing tests standalone before treating the failure as caused by the attachment patch.

## Typecheck pitfall

If `pnpm tsgo` fails, separate introduced errors from pre-existing repository errors. In this class of patch, a likely introduced error is making a helper accept `logger: { debug?: (...args: unknown[]) => void }`; OpenClaw runtime loggers use `debug?: (message: string, meta?: Record<string, unknown>) => void`, so keep helper logger types compatible with that narrower signature.

## Deployment note

Committing the source patch is not the same as deploying it. The running PD One/OpenClaw gateway must be rebuilt/restarted or otherwise updated through the approved deployment path before Mattermost replies gain the new behavior. Do not restart the gateway without approval unless the configured unresponsive-gateway exception applies.

When a source commit has been pushed but the service is still using the globally installed OpenClaw package, verify the active runtime before claiming the fix is live:

```bash
systemctl --user cat openclaw-gateway.service
readlink -f /home/prodesign/.npm-global/lib/node_modules/openclaw/dist/index.js
grep -n "Mattermost thread attachment manifest\|resolveMattermostThreadAttachments\|MattermostAttachmentManifest\|resolveMattermostMedia(attachmentRefs.fileIds)" \
  /home/prodesign/.npm-global/lib/node_modules/openclaw/dist/channel.runtime-*.js
```

If the global `dist/channel.runtime-*.js` bundle lacks the markers, the source checkout patch is not live. Apply the approved build/install path, or, for an urgent approved local hotfix, back up the installed bundle first, patch that exact runtime file, run `node --check`, then restart and verify a new PID plus marker presence. If `pnpm build`/`node scripts/build-all.mjs` gets blocked by dependency-install registry timeouts on the production host, do not leave the service half-updated: keep the source patch committed/pushed, hotpatch only the active bundle from a timestamped backup, and capture marker grep + service restart receipts. Record the hotfix target and backup path in the OpenClaw local patch runbook so the next package update can replace or reconcile it.

Runtime verification should include both code and data-plane checks:

```bash
curl -fsS http://127.0.0.1:18789/health
journalctl --user -u openclaw-gateway.service --since '5 minutes ago' --no-pager | grep -Ei 'gateway] ready|mattermost|connected|error|failed|reconnect'
# Optional Mattermost REST probe for the target thread: GET /api/v4/posts/<post_id>/thread and count unique file_ids.
```

The important success condition is not just `connected as @pdone`; the active runtime must contain the thread-attachment manifest/aggregation markers and the target thread should be fetchable with the expected file count.

## Deployment drift diagnostic from 2026-05 SDS thread

If users report “I thought we fixed thread attachments” after a source patch was committed, explicitly distinguish **source checkout patched** from **active global runtime patched**:

1. Fetch the reported Mattermost thread with the bot token and prove whether earlier posts have `file_ids`; then bounded-download at least one representative file. If the bot can download it, this is not a Mattermost permission issue.
2. Inspect the active systemd target, not just the repo:
   ```bash
   systemctl --user cat openclaw-gateway.service
   readlink -f /home/prodesign/.npm-global/lib/node_modules/openclaw/dist/index.js
   grep -n "Mattermost thread attachment manifest\|resolveMattermostThreadAttachments\|MattermostAttachmentManifest\|resolveMattermostMedia(attachmentRefs.fileIds)" \
     /home/prodesign/.npm-global/lib/node_modules/openclaw/dist/channel.runtime-*.js
   ```
3. Compare with the maintained source checkout/branch. A source commit such as `fix(mattermost): include thread attachments in inbound context` being present in `/home/prodesign/openclaw` is insufficient if the installed bundle still contains only `resolveMattermostMedia(post.file_ids)`.
4. Root-cause wording should be precise: “the fix exists in source but was not deployed / the global installed runtime lacks the markers,” not “Mattermost could not provide files.”
5. Do not claim restored behavior until after rebuild/install or approved hotfix + gateway restart, marker grep, health/log check, and replay on the exact reported thread.

## Oversized attachment diagnostic from 2026-05 STEP thread

If a later Mattermost post has direct `file_ids` but the agent still says it cannot see the attachment, check the inbound media byte limit, not only thread-context aggregation. The Mattermost runtime path may default to `8 * 1024 * 1024` when `agents.defaults.mediaMaxMb` is unset, so files larger than ~8 MB can be skipped by `saveRemoteMedia(...)`; older bundles only log the failure at debug level and do not expose a model-visible caveat. For CAD/STEP files this is common (for example a 53.9 MB `.stp`). Diagnose by fetching `/files/<id>/info` and comparing `size` to the live runtime limit, then fix both: (a) increase/configure an appropriate media limit or CAD-specific intake path, and (b) ensure the attachment manifest reports `missing/failed/too_large` with filename/size instead of silently making the agent think no attachment was posted.

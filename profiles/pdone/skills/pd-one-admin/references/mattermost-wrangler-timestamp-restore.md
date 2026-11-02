# Mattermost Wrangler timestamp restoration caveat

Use this reference when Andy/admin asks PD One to restore timestamps after Mattermost Wrangler moved/copied posts or threads to another channel.

## Key behavior

Mattermost Wrangler move/copy does **not** move rows in-place at the database/history level. It recreates posts in the destination channel and removes or leaves the originals depending on the command. Recreated posts may preserve message text, file attachments, user attribution, and ordering, but receive **new `create_at` timestamps**.

In the 2026-06-02 ECRN consolidation check, Wrangler-recreated posts in `~ecrn` had props like:

```json
{"from_plugin": "true", "wrangler": true}
```

The recreated posts inspected did **not** include durable original timestamp fields such as `original_create_at`, `source_create_at`, or an original post id in `props`.

## Safe investigation sequence

1. Confirm exact-sender admin authorization and channel scope via the PD One Hermes permission bridge.
2. Treat timestamp restoration as a high-impact Mattermost source-system/database write. Do not write until the requester approves a dry-run mapping.
3. Use bounded Mattermost REST reads first:
   - Verify bot identity with `/api/v4/users/me`.
   - Resolve destination channel by name/id.
   - Fetch recent destination posts and identify Wrangler-recreated posts by `props.wrangler == true` or `props.from_plugin == "true"`.
   - Count affected roots/replies and timestamp window.
4. Inspect a sample post's full JSON for `props`, `metadata.files`, `file_ids`, `create_at`, `update_at`, `edit_at`, `root_id`, and `channel_id`.
5. Search current Mattermost API for text matches only as a sanity check; if originals were deleted by Wrangler, API search will usually find only recreated destination posts.
6. If exact restoration is requested, require an authoritative source for original timestamps before any write:
   - Mattermost DB backup/snapshot before the Wrangler move,
   - audit/export source with original post ids and `create_at`, or
   - another verified archive that can be matched deterministically.
7. Prepare a dry-run mapping before execution:
   - new post id,
   - new root id / reply relationship,
   - current `create_at`, `update_at`, `edit_at`,
   - recovered original `create_at`,
   - source of evidence for the recovered timestamp,
   - SQL/API action that would be applied.
8. Only after explicit approval, apply the smallest database update practical and read back affected posts. Avoid gateway restarts unless separately approved or necessary.

## Reporting pattern

For shared Mattermost channels, reply bilingual and concise:

- Say whether anything was changed.
- Report affected count and evidence source.
- If original timestamps are not present in live post data, say exact restore is blocked until a DB backup/audit source is available.
- Offer a lower-risk alternative: post a bilingual notice that the visible timestamps reflect consolidation time, not original conversation time.

## Future prevention

If visible original timestamps matter, do not use Wrangler move/copy for consolidation. Prefer leaving original messages in place with cross-links, or plan an admin-approved database/export-backed migration with timestamp preservation before moving anything.

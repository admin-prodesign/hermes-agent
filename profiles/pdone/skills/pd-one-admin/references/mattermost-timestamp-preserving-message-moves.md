# Mattermost timestamp-preserving message moves

Use this reference when Andy/admin asks to move Mattermost messages, threads, or whole conversations between channels **while preserving the visible original timestamps**.

## Core rule

Do **not** use Wrangler move/copy when timestamps must be preserved. Wrangler recreates posts in the target channel, giving them new post ids and new `create_at` values. Timestamp-preserving moves require either:

1. leaving messages in place and adding cross-links, or
2. an admin-approved Mattermost database move that updates the original rows in place.

The database path is a high-impact source-system write. Always do a bounded dry run first, get explicit approval, and verify with readback. Never run this from an employee/specialist channel without an admin-approved handoff.

## Supported move types

- **Entire thread/conversation:** move the root post and all visible/non-deleted replies together.
- **Single standalone post:** move only if `root_id` is empty and no replies are attached.
- **Multiple matched threads:** dedupe by `COALESCE(NULLIF(root_id, ''), id)` and move one root group at a time.

Avoid moving only part of a thread unless Andy explicitly approves breaking conversation context.

## Prerequisites

1. Exact-sender Mattermost admin authorization via the PD One Hermes permission bridge.
2. Source and target channel IDs resolved and read back through Mattermost REST.
3. A current DB backup or snapshot confirmed before any write.
4. A dry-run mapping file with:
   - move group/root id,
   - each post id,
   - source channel id/name,
   - target channel id/name,
   - root/reply relationship,
   - current `create_at`, `update_at`, `edit_at`, `delete_at`,
   - file ids and file count,
   - expected SQL action.
5. Explicit approval after the dry-run mapping is shown.

## Dry-run discovery sequence

Use Mattermost REST first; do not touch the DB until the candidate set is deterministic.

1. Resolve bot/admin identity: `GET /api/v4/users/me`.
2. Resolve channels: `GET /api/v4/channels/{id}` or search by name.
3. Search/fetch candidate posts in the source channel.
4. Expand every candidate to a full thread: `GET /api/v4/posts/{root_or_post_id}/thread`.
5. Keep only non-deleted posts unless Andy explicitly asks to move deleted records too.
6. Count visible posts and files before the move.
7. Write a dry-run JSON/CSV receipt locally; do not expose private messages beyond the admin-approved scope.

## Database move concept

The timestamp-preserving operation is an in-place channel reassignment of existing rows, not a repost.

For a full thread, update these Mattermost tables as applicable after verifying the live schema:

- `Posts.ChannelId` for the root and all replies.
- File metadata table (`FileInfo` / `FileInfos` depending on schema) `ChannelId` for files attached to moved posts.
- Thread metadata (`Threads`) `ChannelId` for the moved root if the table exists.
- Channel statistics (`Channels.TotalMsgCount`, `Channels.LastPostAt`, `ChannelMembers.LastViewedAt` etc.) should be repaired by Mattermost maintenance jobs or explicitly recalculated only if the schema/version requires it. Prefer read-only verification first; do not invent updates.

Do **not** change `Posts.CreateAt`, `Posts.Id`, `Posts.RootId`, `Posts.UserId`, `Posts.Message`, or file `PostId` when the goal is timestamp preservation.

## SQL dry-run shape

Before execution, produce a transaction preview similar to:

```sql
-- DRY RUN ONLY: inspect candidate rows
SELECT Id, ChannelId, RootId, CreateAt, UpdateAt, EditAt, DeleteAt, UserId
FROM Posts
WHERE Id IN (...) OR RootId IN (...)
ORDER BY CreateAt;

-- DRY RUN ONLY: inspect attached files
SELECT Id, PostId, ChannelId, CreateAt, DeleteAt, Name
FROM FileInfo
WHERE PostId IN (...)
ORDER BY CreateAt;
```

The approved write should be a small explicit transaction with old-channel predicates so it fails closed if the rows changed:

```sql
BEGIN;
UPDATE Posts
SET ChannelId = '<target_channel_id>'
WHERE ChannelId = '<source_channel_id>'
  AND (Id IN (...) OR RootId IN (...));

UPDATE FileInfo
SET ChannelId = '<target_channel_id>'
WHERE ChannelId = '<source_channel_id>'
  AND PostId IN (...);

-- Only if the Threads table exists in this Mattermost version:
UPDATE Threads
SET ChannelId = '<target_channel_id>'
WHERE ChannelId = '<source_channel_id>'
  AND PostId IN (...root ids...);

-- Verify row counts before COMMIT.
COMMIT;
```

If the schema uses quoted/lowercase table names or plural names, adapt from `information_schema`/`psql \d` readback. Do not guess.

## Verification after approved write

1. REST readback moved roots/threads from the target channel.
2. Confirm `create_at` values match the dry-run mapping exactly.
3. Confirm thread reply counts and file counts match the before snapshot.
4. Confirm source channel no longer shows the moved roots.
5. Confirm target channel ordering looks correct after browser refresh.
6. Save a JSONL receipt: old channel, new channel, affected post ids, row counts, backup id/path, approval post id, verification result.

## Common pitfalls

- **Wrangler is not timestamp preserving.** It reposts, then deletes/leaves originals.
- **Mattermost API post create cannot backdate `create_at`.** API-only moves cannot preserve visible timestamps.
- **Partial thread moves confuse users.** Move root + replies unless explicitly approved otherwise.
- **File metadata may still point to the old channel.** Verify attached files open after the move.
- **DB writes may not update UI counters immediately.** Verify actual posts first; repair counters only if a concrete mismatch appears.
- **No backup, no write.** If a current DB backup/snapshot cannot be confirmed, stop at the dry run.

## Lower-risk alternatives

- Leave messages in the original channel and post a pointer in the target channel.
- Use a summary post with original links.
- If messages were already moved via Wrangler and originals were deleted, restore exact timestamps only from a verified DB backup/audit/export mapping; live recreated posts may not contain original timestamp evidence.

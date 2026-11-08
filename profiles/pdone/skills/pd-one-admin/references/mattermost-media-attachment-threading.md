# Mattermost Media Attachment Threading

Use this reference when PD One/OpenClaw or Hermes Mattermost media attachments (`MEDIA:/...`, generated images, documents, voice/audio, video, or batched image sends) post as top-level channel messages instead of staying in the request thread.

## Durable lesson
Mattermost threaded text replies and media/file uploads may use different send paths. Do not assume a threaded text reply means the following attachment will inherit the same root. Every Mattermost media/file send path must explicitly preserve the originating thread root.

## Expected behavior
- Attachments should be tied to the thread that originated the request unless the requester explicitly asks for a top-level/channel post.
- Prefer a single threaded post containing both caption/text and files when the platform adapter supports it.
- If the adapter sends text and media as separate posts, both posts must carry the same resolved `root_id`.

## Implementation pattern
In the Mattermost adapter, route media/file posts using the same effective-thread logic as text sends:

1. Resolve the effective thread source from `reply_to` first.
2. If `reply_to` is absent, use `metadata.thread_id` or `metadata.root_id`.
3. If reply mode is `thread`, normalize reply IDs to the actual Mattermost thread root via the adapter's root resolver before posting.
4. Put the resolved value in the post payload as `root_id` for every file-post API call.
5. Preserve the same metadata when URL/file upload fallback paths degrade to a plain text send.

Apply this pattern to:
- local image uploads and generated `MEDIA:/...` images;
- batched images / multi-image uploads;
- document/file uploads;
- voice/audio uploads;
- video uploads;
- URL download failure fallbacks that send a link instead of a file.

## Duplicate attachment pitfall in bilingual replies
Mattermost group/channel replies are bilingual, but shared attachment directives are delivery metadata, not language-specific content. If the final answer repeats the same `MEDIA:/path/file.ext` line once in the English section and once in the Traditional Chinese section, the Hermes/Mattermost extraction path treats them as two separate upload requests and Mattermost will show duplicate attachments.

When diagnosing duplicate attachments:
1. Read back the Mattermost thread/post and compare `file_ids`, filenames, sizes, and timestamps.
2. Inspect the agent's final response/session transcript for repeated identical `MEDIA:` directives; in delivered text the `MEDIA:` lines are stripped, so the post body may only show blank attachment-label areas.
3. Reproduce locally with `BasePlatformAdapter.extract_media(response)` when needed: repeated identical `MEDIA:` tags currently produce multiple media entries unless the gateway has been patched to deduplicate.
4. Fix at two layers when possible:
   - formatting discipline: put a shared attachment only once, preferably in a final **Attachment / 附件** section after both language blocks;
   - gateway discipline: deduplicate extracted `MEDIA:` paths before upload while preserving order and voice/document directives.
5. For Hermes gateway source fixes, the class-level dedupe point is `BasePlatformAdapter.extract_media()` in `gateway/platforms/base.py`, before dispatch reaches platform-specific upload methods. Normalize local paths for the dedupe key (`expanduser` + `abspath`/`normcase`) so `~/...` and `/home/...` variants of the same artifact do not double-upload, but still remove every `MEDIA:` directive from visible text.
6. Add/verify tests for identical duplicate `MEDIA:` paths in final responses and for bilingual output containing one shared attachment. A good focused set is:
   - `tests/gateway/test_extract_media.py` for explicit `MEDIA:` dedupe, tilde-vs-expanded dedupe, order preservation for distinct files, and cleanup of visible text;
   - `tests/gateway/test_extract_local_files.py` to ensure bare-path delivery behavior was not regressed;
   - `tests/gateway/test_tts_media_routing.py` to ensure voice/audio routing still works.
7. When the user says to fix but not restart, patch/test/commit/push only. Report that the running gateway still needs an approved restart before the fix is live; do not perform a live Mattermost smoke test until after that restart is approved.

Do not delete duplicate live attachments unless the user/admin explicitly asks for cleanup; diagnosis and code/config changes are separate from destructive Mattermost post deletion.

## Regression tests to add/run
Add tests that mock the Mattermost API and assert the outgoing `posts` payload includes `root_id` for media sends when metadata carries thread context.

Good targeted checks:

```bash
python -m pytest -o addopts= tests/gateway/test_mattermost.py::TestMattermostSend -q
python -m pytest -o addopts= tests/gateway/test_mattermost.py -q
python - <<'PY'
import py_compile
for p in ['gateway/platforms/mattermost.py','tests/gateway/test_mattermost.py']:
    py_compile.compile(p, doraise=True)
print('py_compile ok')
PY
```

Assertions should cover at least:
- `send_image_file(..., metadata={'thread_id': '<root>'})` posts with `file_ids` and `root_id`.
- `send_multiple_images(..., metadata={'thread_id': '<root>'})` posts with all `file_ids` and `root_id`.
- Existing text-send behavior still preserves `metadata.thread_id`.
- `reply_mode='off'` still does not attach `root_id`.

## Deployment and verification
- Commit and push the fix to the maintained downstream/custom branch when applicable.
- A running gateway must be restarted before code changes take effect; get approval first unless the approved unresponsive-gateway exception applies.
- After restart, live-smoke with a generated small PNG in a Mattermost thread and verify the resulting Mattermost post has the expected `root_id` / appears under the originating thread.

## Pitfall
Do not answer that image upload is impossible solely because a channel/scoped assistant previously produced a top-level attachment. First inspect whether the platform adapter's media path dropped thread metadata. The correct fix may be a routing bug, not a policy/capability denial.

# Mattermost Unicode attachment filenames

Use this reference when a Mattermost attachment created through Hermes displays a filename containing literal percent escapes such as `%E5%99...`, especially for Traditional Chinese or other non-ASCII basenames.

## Symptom and bounded diagnosis

1. Read the exact approved Mattermost post and its `file_ids`; do not infer the filename from the local artifact or chat text.
2. Read `/api/v4/files/{file_id}/info` and compare the stored `name` with the intended local basename.
3. Keep inspection bounded to post/file metadata and the relevant upload path; do not expose unrelated thread content.
4. Trace the delivery route. For a Hermes `MEDIA:/path/file.docx` response, the Mattermost path is normally:
   `MEDIA:` extraction → `_send_local_file()` → `_upload_file()` → `aiohttp.FormData` → `POST /api/v4/files`.

## Root-cause test

`aiohttp.FormData()` defaults to `quote_fields=True`. With aiohttp 3.x, a non-ASCII multipart filename can be serialized as a literal percent-encoded parameter:

```python
import aiohttp

form = aiohttp.FormData()
form.add_field("channel_id", "x")
form.add_field("files", b"data", filename="中文公告.docx")
payload = form()
print(payload._parts[1][0].headers["Content-Disposition"])
```

If the header contains `filename="%E4%B8%AD...docx"` and Mattermost file info stores the same string, the document generator did not create the bad name. The upload multipart serializer encoded it and Mattermost preserved that value literally.

## Durable fix

Construct every Mattermost multipart upload form with `quote_fields=False`, but first remove header control characters. Disabling aiohttp field quoting preserves Unicode but otherwise allows a Linux filename containing CR/LF or another C0 control to enter `Content-Disposition` literally.

```python
import re
import aiohttp

safe_filename = re.sub(r"[\x00-\x1f\x7f]", "_", filename)
form = aiohttp.FormData(quote_fields=False)
form.add_field("channel_id", channel_id)
form.add_field("files", file_data, filename=safe_filename)
```

Pass the readable Unicode basename as `filename` after this narrow sanitization. Prefer one shared form-builder used by every Mattermost upload route. Audit all sibling paths, including:

- adapter `_upload_file()` used by local files and downloaded files;
- standalone/send-message Mattermost upload helpers;
- multi-file or batch upload paths that construct their own `FormData`.

Do not fix only the single observed call site.

## Regression verification

Add tests that:

1. serialize a basename containing Traditional Chinese characters;
2. assert multipart `Content-Disposition` contains the readable Unicode basename rather than `%XX` escapes;
3. prove every adapter and standalone upload path uses the shared form builder;
4. verify ASCII filenames remain unchanged;
5. verify CR, LF, NUL, and other header controls are absent/replaced after `quote_fields=False`;
6. run the full Mattermost adapter suite plus standalone-send tests, compilation, lint, and `git diff --check`;
7. in an approved live smoke test, upload a harmless Unicode-named file, read back `/files/{id}/info`, and confirm the stored name exactly matches the local basename.

Code changes and live uploads remain separately approval-gated. A read-only diagnosis approval does not authorize patching or a live smoke upload.

## Live release is not the overlay

Do not treat an older overlay worktree that already sets `quote_fields=False` as the live fix. The running PD One gateway imports `releases/hermes-agent-<SHA>` (`HERMES_RUNTIME_SHA` / `PYTHONPATH`). Re-apply the shared builder on a GitHub PR whose base is that live SHA. Do not edit the live release tree or recycle the gateway unless Andy separately approves cutover.

## Downstream branch and activation discipline

- A clean local commit is not durable backup until the maintained private branch accepts it and remote readback shows the new head.
- If the live checkout and private remote branch have diverged, never force-push just to save the fix. Create a temporary worktree from the current remote custom-runtime branch, cherry-pick the verified fix, rerun the targeted/full Mattermost tests in that worktree, then fast-forward push and verify with `git ls-remote`. Remove the temporary worktree afterward.
- Keep source deployment separate from runtime activation. Confirm the running PD One gateway imports the edited checkout, then remember Python adapter code remains old in memory until restart.
- A healthy gateway must not be restarted merely because the patch is ready. Request explicit restart approval immediately beforehand, especially when gateway state reports active agents. After approval, verify new PID, running state, and Mattermost reconnection before a live Unicode filename smoke test.

## Approval-ticket metadata pitfall

For exact-post diagnosis tickets, distinguish the requester/origin channel from the channel that actually owns the linked post. Preserve the exact approved post ID in scope and record any channel mismatch in admin details. Do not silently broaden into surrounding private history; if policy requires the owning channel to be listed explicitly, correct or re-escalate the ticket before reading beyond the exact approved metadata.

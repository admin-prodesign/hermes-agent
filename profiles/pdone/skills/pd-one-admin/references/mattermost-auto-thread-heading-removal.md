# Mattermost auto thread heading removal

Use when Andy/admin asks to disable Mattermost auto-titling / auto-added thread-root headings for a channel, or to remove Mattermost thread-root headings previously added by PD One/Hermes automation.

## Disable future headings

- In the active PD One Hermes profile config, add the target channel id to `mattermost.auto_thread_root_heading_disabled_channels` while preserving existing disabled channels.
- Make a timestamped config backup before editing.
- Read back the config block and confirm the target channel id is present before reporting completion.
- Do not restart the gateway unless Andy explicitly approves. State clearly that the saved config may require an approved gateway reload/restart before the running process enforces it if hot-reload is insufficient.

## Safety pattern for removing existing headings

- Treat this as a source-system write: require exact-sender admin authorization and keep the scope channel-bounded.
- Do not restart the gateway just to remove already-written headings. Config disablement prevents future headings after it is loaded; removal is a Mattermost post patch/readback operation.
- Prefer a dry-run first. Scan only the target channel and only root/top-level posts (`root_id` empty/none/self). Do not edit replies.
- Match conservatively:
  - first line is a level-5 Markdown heading (`##### ...`), followed by a blank line;
  - heading looks like the automation output, normally `Traditional Chinese / English` with both CJK and Latin text;
  - keep length and slash-count caps so normal authored headings are not removed accidentally.
- Save a JSON backup of every candidate before applying. Include post id, channel metadata, old message, and proposed new message.
- Apply with Mattermost `PUT /api/v4/posts/{post_id}/patch` containing only the restored message body.
- Read back every patched post and verify `message == expected_new_message` before claiming completion.
- Re-run the dry-run scanner afterward; expected result is `candidate_count: 0` for the target channel.

## Minimal implementation sketch

Use the PD One Mattermost helper for credentials rather than exposing tokens:

```python
from pathlib import Path
import sys
sys.path.insert(0, '/home/prodesign/.hermes/profiles/pdone/tools')
from mattermost_review_log import mattermost_context

base, token, headers, me = mattermost_context()
```

Fetch pages with `GET /api/v4/channels/{channel_id}/posts?page=N&per_page=100`, inspect `order` + `posts`, then patch only vetted candidates.

## Receipt format

Keep the admin-facing receipt concise and bilingual in Mattermost groups. Include:

- target channel id/name;
- scanned post count;
- removed heading count;
- readback verification result;
- backup path;
- post-removal re-scan result;
- explicit note that no gateway restart was performed.

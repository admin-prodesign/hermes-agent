# Mattermost long-reply splitting

Use this when PD One bilingual Mattermost replies exceed the practical post length, or when a split cuts a fenced code block or markdown table.

## Rule

Keep one complete reply when it fits. If it must split:

1. Split by language first, in the already-drafted order (English then Traditional Chinese, or the reverse). Prefer a standalone `---` between the two language sections.
2. Within a language, pack at markdown-safe boundaries.
3. Never cut through a fenced code block or GFM table. If one block is itself over the limit, close/reopen fences or repeat table headers rather than cutting mid-fence or mid-row. Each table chunk must keep a blank line before the header row and a blank line after the last data row; otherwise Mattermost prints literal pipes instead of a table.
4. Put continuation markers such as `(1/2)` on their own line after the chunk, never on a fence or table row.

Practical pack budget is `MAX_POST_LENGTH` (4000). The Mattermost server default is 16383; do not raise the pack budget just to avoid language-first posts.

## Implementation

- Helper: `plugins/platforms/mattermost/message_split.py` (`split_mattermost_message`)
- Hook: `MattermostAdapter.truncate_message` in `plugins/platforms/mattermost/adapter.py`
- Tests: `tests/gateway/test_mattermost_message_split.py`

```bash
PYTHONPATH=/home/prodesign/.hermes/hermes-agent \
  /home/prodesign/.hermes/hermes-agent/.venv/bin/python \
  -m unittest tests.gateway.test_mattermost_message_split -v
```

Overflow chunks of a **top-level** send must set `root_id` to the first post id. Otherwise Mattermost CRT shows `(1/2)` and `(2/2)` as two channel roots. Chunks that already have a thread root stay under that root (do not nest under chunk 1).

Adapter source changes are not live until an approved PD One gateway restart loads the release tree that contains `message_split.py`.

## Prompt habit

Draft bilingual channel replies as two full equivalent sections separated by `---`, so the sender can language-split without guessing interleaved headings.

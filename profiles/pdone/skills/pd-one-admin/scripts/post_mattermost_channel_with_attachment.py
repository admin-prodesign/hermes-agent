#!/usr/bin/env python3
"""Post an approved Mattermost channel message with one attachment via PD One credentials.

Usage:
  python scripts/post_mattermost_channel_with_attachment.py \
    --channel-id imj7bt6w4tdk5rsbttiga44agc \
    --message-file /path/to/message.md \
    --attachment /path/to/image.png

Run from the Hermes PD One profile where /home/prodesign/.hermes/profiles/pdone/tools
can provide mattermost_review_log.mattermost_context(). The script prints a JSON receipt
with sender, channel, post id, file ids, and message-match verification.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path

import requests

TOOLS = Path('/home/prodesign/.hermes/profiles/pdone/tools')
sys.path.insert(0, str(TOOLS))
from mattermost_review_log import mattermost_context, mattermost_post_link  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--channel-id', required=True)
    ap.add_argument('--message-file', required=True)
    ap.add_argument('--attachment')
    ap.add_argument('--expect-sender', default='pdone')
    ap.add_argument('--expect-sender-id', default='xo7wmyntdtgndfscwh6so4icow')
    args = ap.parse_args()

    channel_id = args.channel_id.strip()
    message_path = Path(args.message_file)
    message = message_path.read_text(encoding='utf-8')
    attachment = Path(args.attachment) if args.attachment else None

    base, _token, headers, me = mattermost_context()
    chan_resp = requests.get(f'{base}/api/v4/channels/{channel_id}', headers=headers, timeout=20)
    chan_resp.raise_for_status()
    chan = chan_resp.json()

    readiness = {
        'sender_username': me.get('username'),
        'sender_id': me.get('id'),
        'channel_id': chan.get('id'),
        'channel_name': chan.get('name'),
        'channel_display_name': chan.get('display_name'),
        'message_length': len(message),
        'attachment': str(attachment) if attachment else None,
        'attachment_exists': attachment.exists() if attachment else None,
        'attachment_size': attachment.stat().st_size if attachment and attachment.exists() else None,
    }

    if chan.get('id') != channel_id:
        raise SystemExit(f'Channel id mismatch: expected {channel_id}, got {chan.get("id")}')
    if args.expect_sender_id and (me.get('id') != args.expect_sender_id or me.get('is_bot') is False):
        raise SystemExit(f'Unexpected sender username: expected {args.expect_sender}, got {me.get("username")}')

    file_ids: list[str] = []
    if attachment:
        if not attachment.exists():
            raise SystemExit(f'Attachment missing: {attachment}')
        mime = mimetypes.guess_type(str(attachment))[0] or 'application/octet-stream'
        with attachment.open('rb') as f:
            files = {'files': (attachment.name, f, mime)}
            data = {'channel_id': channel_id}
            up = requests.post(f'{base}/api/v4/files', headers=headers, files=files, data=data, timeout=120)
        up.raise_for_status()
        infos = up.json().get('file_infos') or []
        file_ids = [info['id'] for info in infos if info.get('id')]
        if not file_ids:
            raise SystemExit('File upload returned no file_ids')

    payload = {'channel_id': channel_id, 'message': message, 'file_ids': file_ids}
    post = requests.post(f'{base}/api/v4/posts', headers={**headers, 'Content-Type': 'application/json'}, json=payload, timeout=60)
    post.raise_for_status()
    post_json = post.json()

    rb = requests.get(f"{base}/api/v4/posts/{post_json['id']}", headers=headers, timeout=20)
    rb.raise_for_status()
    readback = rb.json()

    receipt = {
        'readiness': readiness,
        'post_id': post_json.get('id'),
        'post_channel_id': readback.get('channel_id'),
        'post_user_id': readback.get('user_id'),
        'file_ids': readback.get('file_ids'),
        'message_matches': readback.get('message') == message,
        'permalink': mattermost_post_link(post_json.get('id'), base_url=base),
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Typed local video compose and origin-thread media delivery for PD One."""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

def PROFILE_ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))

def INPUT_ROOT():
    return PROFILE_ROOT() / 'cache/documents'

def OUTPUT_ROOT():
    return PROFILE_ROOT() / 'tmp/video-compose'
ALLOWED_VIDEO = {'.mp4', '.mov', '.mkv', '.webm'}
ALLOWED_IMAGE = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_INPUT_BYTES = 2 * 1024 * 1024 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024 * 1024
MAX_DURATION_SECONDS = 20 * 60
MAX_INPUTS = 12
STILL_SECONDS = 2.0
MATTERMOST_ID_RE = re.compile('^[a-z0-9]{26}$')
TICKET_RE = re.compile('^PDAPP-\\d{8}-[A-F0-9]{8}$')

def fail(message: str, code: int=2) -> None:
    print(json.dumps({'status': 'error', 'error': message}, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(code)

def emit(payload: dict[str, Any]) -> None:
    from tools.pd_one_ops.hr_guard import guard_hr_payload
    payload = guard_hr_payload(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return False

def require_path(raw: str, root: Path, suffixes: set[str], *, must_exist: bool) -> Path:
    path = Path(raw).expanduser().resolve(strict=False)
    if not is_within(path, root):
        fail(f'path escaped approved root {root}: {path}')
    if path.suffix.lower() not in suffixes:
        fail(f'unsupported suffix {path.suffix}: {path}')
    if must_exist:
        if not path.is_file() or path.is_symlink():
            fail(f'input must be a regular non-symlink file: {path}')
        size = path.stat().st_size
        if size <= 0 or size > MAX_INPUT_BYTES:
            fail(f'input size out of bounds: {path}')
    return path

def probe_duration(path: Path) -> float:
    ffprobe = shutil.which('ffprobe')
    if not ffprobe:
        fail('ffprobe is required')
    proc = subprocess.run([ffprobe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)], text=True, capture_output=True, shell=False, timeout=30, check=False)
    if proc.returncode != 0:
        fail(f'ffprobe failed for {path}: {proc.stderr[-400:]}')
    try:
        duration = float(json.loads(proc.stdout)['format']['duration'])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'ffprobe duration parse failed for {path}: {exc}')
    if duration <= 0 or duration > MAX_DURATION_SECONDS:
        fail(f'duration out of bounds for {path}: {duration}')
    return duration

def compose(inputs: list[str], output: str) -> dict[str, Any]:
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        fail('ffmpeg is required')
    if not inputs or len(inputs) > MAX_INPUTS:
        fail(f'compose requires 1-{MAX_INPUTS} inputs')
    resolved: list[Path] = []
    for raw in inputs:
        _suffix = Path(raw).suffix.lower()
        allowed = ALLOWED_VIDEO | ALLOWED_IMAGE
        resolved.append(require_path(raw, INPUT_ROOT(), allowed, must_exist=True))
    out = require_path(output, OUTPUT_ROOT(), {'.mp4'}, must_exist=False)
    if out.exists():
        fail(f'refusing to overwrite existing output: {out}')
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='compose-', dir=str(OUTPUT_ROOT())))
    if not is_within(work, OUTPUT_ROOT()):
        fail('work directory escaped output root')
    clips: list[Path] = []
    try:
        for index, source in enumerate(resolved, 1):
            clip = work / f'clip-{index:02d}.mp4'
            if source.suffix.lower() in ALLOWED_IMAGE:
                command = [ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-t', f'{STILL_SECONDS:.3f}', '-i', str(source), '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30', '-an', str(clip)]
            else:
                command = [ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source), '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-an', str(clip)]
            proc = subprocess.run(command, text=True, capture_output=True, shell=False, timeout=180, check=False)
            if proc.returncode != 0 or not clip.is_file():
                fail(f'ffmpeg failed normalizing {source.name}: {proc.stderr[-500:]}')
            clips.append(clip)
        list_file = work / 'concat.txt'
        list_file.write_text(''.join((f"file '{clip}'\n" for clip in clips)), encoding='utf-8')
        staged = work / 'output.mp4'
        concat = subprocess.run([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(list_file), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(staged)], text=True, capture_output=True, shell=False, timeout=180, check=False)
        if concat.returncode != 0 or not staged.is_file():
            fail(f'ffmpeg concat failed: {concat.stderr[-500:]}')
        duration = probe_duration(staged)
        size = staged.stat().st_size
        if size <= 0 or size > MAX_OUTPUT_BYTES:
            fail(f'composed output size out of bounds: {size}')
        digest = hashlib.sha256(staged.read_bytes()).hexdigest()
        os.replace(staged, out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {'status': 'ok', 'capability': 'local_video_compose', 'inputs': [str(path) for path in resolved], 'output': str(out), 'duration_seconds': round(duration, 3), 'size_bytes': out.stat().st_size, 'sha256': digest, 'safety': {'admin_only': True, 'approved_roots_only': True, 'source_overwrite_forbidden': True, 'external_delivery': False, 'shell_used': False}}

def _mattermost_env() -> tuple[str, str]:
    sys.path.append(str(PROFILE_ROOT() / 'tools'))
    from mattermost_review_log import gateway_env
    env = gateway_env()
    base = str(env.get('MATTERMOST_URL') or '').rstrip('/')
    token = str(env.get('MATTERMOST_BOT_TOKEN') or '')
    if not base or not token:
        fail('Mattermost bot credentials unavailable')
    return (base, token)

def _mm_request(base: str, token: str, method: str, path: str, data: bytes | None=None, content_type: str | None=None) -> Any:
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}
    if content_type:
        headers['Content-Type'] = content_type
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'Mattermost API {method} {path} failed: HTTP {exc.code}')

def deliver_origin_thread(*, ticket_id: str, file_path: str, channel_id: str, root_id: str, message: str) -> dict[str, Any]:
    if not TICKET_RE.fullmatch(ticket_id):
        fail('ticket_id must look like PDAPP-YYYYMMDD-XXXXXXXX')
    if not MATTERMOST_ID_RE.fullmatch(channel_id) or not MATTERMOST_ID_RE.fullmatch(root_id):
        fail('channel_id and root_id must be exact Mattermost IDs')
    source = require_path(file_path, OUTPUT_ROOT(), {'.mp4', '.jpg', '.jpeg', '.png'}, must_exist=True)
    tools = PROFILE_ROOT() / 'legacy-openclaw/workspace/tools'
    if str(tools) not in sys.path:
        sys.path.append(str(tools))
    from admin_approval_tickets import ApprovalLedger
    ticket = ApprovalLedger().get(ticket_id)
    grant = ticket.get('approval_grant') or {}
    caps = set(grant.get('allowed_capabilities') or [])
    if ticket.get('status') not in {'approved', 'queued', 'in_progress'}:
        fail(f'ticket {ticket_id} is not executable: {ticket.get('status')}')
    if grant.get('status') != 'active' or 'origin_thread_media_deliver' not in caps:
        fail(f'ticket {ticket_id} grant does not include origin_thread_media_deliver')
    if str(ticket.get('origin_channel_id') or '') != channel_id:
        fail('channel_id does not match the ticket origin channel')
    origin_root = str(ticket.get('origin_root_id') or ticket.get('origin_post_id') or '')
    if origin_root != root_id:
        fail('root_id does not match the ticket origin thread')
    if bool((ticket.get('capability_scope') or {}).get('external_send_allowed')):
        fail('this capability delivers only to the bound origin thread; use a separate external-send ticket')
    base, token = _mattermost_env()
    boundary = '----pdoneMedia' + hashlib.sha256(os.urandom(12)).hexdigest()[:12]
    filename = source.name
    body = f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode('utf-8') + source.read_bytes() + f'\r\n--{boundary}--\r\n'.encode('utf-8')
    upload = _mm_request(base, token, 'POST', f'/api/v4/files?channel_id={channel_id}', data=body, content_type=f'multipart/form-data; boundary={boundary}')
    file_infos = upload.get('file_infos') or []
    if not file_infos:
        fail('Mattermost file upload returned no file_infos')
    file_id = str(file_infos[0].get('id') or '')
    if not MATTERMOST_ID_RE.fullmatch(file_id):
        fail('Mattermost file upload returned an invalid file id')
    post = _mm_request(base, token, 'POST', '/api/v4/posts', data=json.dumps({'channel_id': channel_id, 'root_id': root_id, 'message': message[:1500] or f'Completed {ticket_id}', 'file_ids': [file_id]}, ensure_ascii=False).encode('utf-8'), content_type='application/json')
    post_id = str(post.get('id') or '')
    if not MATTERMOST_ID_RE.fullmatch(post_id):
        fail('Mattermost post create returned an invalid post id')
    readback = _mm_request(base, token, 'GET', f'/api/v4/posts/{post_id}')
    if str(readback.get('channel_id') or '') != channel_id or str(readback.get('root_id') or readback.get('id') or '') not in {root_id, post_id}:
        fail('origin-thread readback mismatch')
    return {'status': 'ok', 'capability': 'origin_thread_media_deliver', 'ticket_id': ticket_id, 'channel_id': channel_id, 'root_id': root_id, 'post_id': post_id, 'file_id': file_id, 'file_name': filename, 'size_bytes': source.stat().st_size, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'safety': {'origin_thread_only': True, 'external_send_forbidden': True, 'token_printed': False}}

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    compose_p = sub.add_parser('compose')
    compose_p.add_argument('--input', action='append', required=True)
    compose_p.add_argument('--out', required=True)
    deliver_p = sub.add_parser('deliver-origin-thread')
    deliver_p.add_argument('--ticket-id', required=True)
    deliver_p.add_argument('--file', required=True)
    deliver_p.add_argument('--channel-id', required=True)
    deliver_p.add_argument('--root-id', required=True)
    deliver_p.add_argument('--message', default='')
    return parser

def main(argv: list[str] | None=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == 'compose':
        emit(compose(args.input, args.out))
        return 0
    emit(deliver_origin_thread(ticket_id=args.ticket_id, file_path=args.file, channel_id=args.channel_id, root_id=args.root_id, message=args.message))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Typed employee watches: production-item-on-schedule, owner-bound, no raw cron."""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import argparse
import fcntl
import json
import os
import re
import sys
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

def ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))

def STORE_PATH():
    return ROOT() / 'state/employee-watches/watches.json'

def POLICY_CACHE():
    return ROOT() / 'policy-cache/mattermost/users'

def SCHEDULE_DIR():
    return ROOT() / 'legacy-openclaw/workspace/projects/AppSheet/exports/morning-briefing-context'

def ANDY_MATTERMOST_ID():
    return site_text('PDONE_OWNER_MM_USER_ID')
TAIPEI = ZoneInfo('Asia/Taipei')
WATCH_TYPE = 'production_item_on_schedule'
MAX_ACTIVE_PER_OWNER = 5
DEFAULT_EXPIRE_DAYS = 14
MAX_EXPIRE_DAYS = 30
SOURCE_STALE_SECONDS = 6 * 3600
TOKEN_RE = re.compile('[A-Za-z0-9.]+|[\\u4e00-\\u9fff]+')
MOLD_RE = re.compile('^PD-\\d{3,}$', re.IGNORECASE)
WATCH_ID_RE = re.compile('^PDWATCH-\\d{8}-[0-9A-F]{8}$')
ALLOWED_WATCH_TYPES = frozenset({WATCH_TYPE})

class WatchError(Exception):

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(str(payload.get('error') or payload.get('status')))
        self.payload = payload

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _today_taipei() -> str:
    return datetime.now(TAIPEI).date().isoformat()

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def emit(payload: dict[str, Any], code: int=0) -> int:
    from tools.pd_one_ops.hr_guard import guard_hr_payload
    payload = guard_hr_payload(payload)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    return code

def _normalize(text: str) -> str:
    value = unicodedata.normalize('NFKC', str(text or ''))
    value = value.replace('_', ' ').replace('—', '-').replace('–', '-')
    value = re.sub('\\s+', ' ', value).strip().casefold()
    return value

def _tokens(text: str) -> list[str]:
    return [tok.casefold() for tok in TOKEN_RE.findall(_normalize(text))]

def _load_policy(user_id: str) -> dict[str, Any]:
    path = POLICY_CACHE() / f'{user_id}.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {}
    return data if isinstance(data, dict) else {}

def sender_is_admin(user_id: str) -> bool:
    if user_id == ANDY_MATTERMOST_ID():
        return True
    data = _load_policy(user_id)
    roles = {str(role).strip().lower() for role in data.get('roles') or []}
    return 'admin' in roles

def resolve_sender_id(claimed: str) -> str:
    env = (site_text('HERMES_SESSION_USER_ID') or site_text('HERMES_SESSION_USER_ID_ALT') or '').strip()
    claimed_id = str(claimed or '').strip()
    if env and claimed_id and (env != claimed_id):
        raise WatchError({'status': 'error', 'error': 'sender_mismatch', 'message': 'Caller sender_id does not match the live session sender.'})
    sender = env or claimed_id
    if not sender or len(sender) < 8:
        raise WatchError({'status': 'error', 'error': 'missing_sender', 'message': 'Exact sender id is required.'})
    data = _load_policy(sender)
    if not data or data.get('found') is False or data.get('active') is False:
        raise WatchError({'status': 'error', 'error': 'unknown_sender', 'message': 'Sender is not an active profiled Mattermost user.'})
    return sender

def resolve_channel_id(claimed: str) -> str:
    env = (site_text('HERMES_SESSION_CHAT_ID') or '').strip()
    claimed_id = str(claimed or '').strip()
    if env and claimed_id and (env != claimed_id):
        raise WatchError({'status': 'error', 'error': 'channel_mismatch', 'message': 'origin_channel_id does not match the live session channel.'})
    channel = env or claimed_id
    if not channel or len(channel) < 8:
        raise WatchError({'status': 'error', 'error': 'missing_channel', 'message': 'origin_channel_id is required (current thread only).'})
    return channel

def _latest_schedule_path() -> Path:
    files = sorted(SCHEDULE_DIR().glob('production-schedule_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise WatchError({'status': 'error', 'error': 'schedule_missing', 'message': 'No production-schedule snapshot is available.'})
    return files[0]

def load_schedule(path: Optional[Path]=None) -> dict[str, Any]:
    schedule_path = path or _latest_schedule_path()
    data = json.loads(schedule_path.read_text(encoding='utf-8'))
    rows = data.get('rows') if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise WatchError({'status': 'error', 'error': 'schedule_invalid', 'message': 'Schedule snapshot has no rows list.'})
    mtime = datetime.fromtimestamp(schedule_path.stat().st_mtime, tz=timezone.utc)
    age = (_now() - mtime).total_seconds()
    catalog: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        product = str(row.get('product') or '').strip()
        if product:
            catalog[_normalize(product)] = product
    return {'path': str(schedule_path), 'mtime': _iso(mtime), 'stale': age > SOURCE_STALE_SECONDS, 'age_seconds': int(age), 'rows': [row for row in rows if isinstance(row, dict)], 'catalog': catalog}

def resolve_item(query: str, schedule: dict[str, Any]) -> dict[str, Any]:
    raw = str(query or '').strip()
    if not raw or len(raw) > 80:
        raise WatchError({'status': 'error', 'error': 'bad_query', 'message': 'Query is required and must be <= 80 characters.'})
    tokens = _tokens(raw)
    if not tokens:
        raise WatchError({'status': 'error', 'error': 'bad_query', 'message': 'Query has no usable item tokens.'})
    catalog: dict[str, str] = schedule['catalog']
    exact = catalog.get(_normalize(raw))
    if exact:
        return {'item_key': _normalize(exact), 'item_label': exact, 'match_mode': 'exact', 'query': raw}
    mold_query = raw.strip().upper()
    if MOLD_RE.fullmatch(mold_query):
        matches = sorted({str(row.get('product') or '').strip() for row in schedule['rows'] if str(row.get('mold') or '').strip().upper() == mold_query})
        matches = [item for item in matches if item]
        if len(matches) == 1:
            label = matches[0]
            return {'item_key': _normalize(label), 'item_label': label, 'match_mode': 'exact_mold', 'query': raw, 'mold': mold_query}
        raise WatchError({'status': 'error', 'error': 'ambiguous_item' if matches else 'item_not_found', 'message': 'Mold id did not resolve to exactly one product.', 'query': raw, 'candidates': matches[:8]})
    scored: list[tuple[int, str]] = []
    for _key, label in catalog.items():
        if MOLD_RE.fullmatch(label):
            continue
        product_tokens = set(_tokens(label))
        if not all((token in product_tokens or token in _normalize(label) for token in tokens)):
            continue
        scored.append((len(label), label))
    unique_labels = sorted({label for _length, label in scored}, key=lambda item: (len(item), item))
    if len(unique_labels) == 1:
        label = unique_labels[0]
        return {'item_key': _normalize(label), 'item_label': label, 'match_mode': 'unique_tokens', 'query': raw}
    raise WatchError({'status': 'error', 'error': 'ambiguous_item' if unique_labels else 'item_not_found', 'message': 'Resolve the item to one canonical product name or mold id, then retry.', 'query': raw, 'candidates': unique_labels[:8]})

def matching_rows(schedule: dict[str, Any], item_key: str, *, from_date: Optional[str]=None) -> list[dict[str, Any]]:
    start = from_date or _today_taipei()
    hits: list[dict[str, Any]] = []
    for row in schedule['rows']:
        product = str(row.get('product') or '').strip()
        if _normalize(product) != item_key:
            continue
        date_value = str(row.get('date') or '').strip()
        if date_value < start:
            continue
        qty = str(row.get('quantity') or '').replace(',', '').strip()
        try:
            quantity = float(qty) if qty else 0.0
        except ValueError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            quantity = 0.0
        if quantity <= 0:
            continue
        hits.append({'date': date_value, 'machine': str(row.get('machine') or '').strip(), 'product': product, 'mold': str(row.get('mold') or '').strip(), 'quantity': qty})
        if len(hits) >= 5:
            break
    return hits

def _empty_store() -> dict[str, Any]:
    return {'version': 1, 'watches': []}

def _open_locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(_empty_store(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    handle = path.open('r+', encoding='utf-8')
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    try:
        handle.seek(0)
        raw = handle.read()
        data = json.loads(raw) if raw.strip() else _empty_store()
        if not isinstance(data, dict) or not isinstance(data.get('watches'), list):
            data = _empty_store()
    except Exception:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        data = _empty_store()
    return (handle, data)

def _save_locked(handle, data: dict[str, Any]) -> None:
    handle.seek(0)
    handle.truncate()
    handle.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    handle.flush()
    os.fsync(handle.fileno())

def _public_watch(watch: dict[str, Any], *, admin: bool) -> dict[str, Any]:
    out = {'watch_id': watch.get('watch_id'), 'type': watch.get('type'), 'status': watch.get('status'), 'item_label': (watch.get('resolved') or {}).get('item_label'), 'query': watch.get('query'), 'mode': watch.get('mode'), 'created_at': watch.get('created_at'), 'expires_at': watch.get('expires_at'), 'origin_channel_id': watch.get('origin_channel_id'), 'origin_root_id': watch.get('origin_root_id'), 'last_checked_at': watch.get('last_checked_at'), 'fired_at': watch.get('fired_at')}
    if admin:
        out['owner_sender_id'] = watch.get('owner_sender_id')
        out['owner_username'] = watch.get('owner_username')
        out['notify_post_id'] = watch.get('notify_post_id')
        out['resolved'] = watch.get('resolved')
    return out

def _new_watch_id(now: datetime) -> str:
    return f'PDWATCH-{now.astimezone(TAIPEI).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}'

def create_watch(*, query: str, sender_id: str, origin_channel_id: str, origin_root_id: str, expires_days: int=DEFAULT_EXPIRE_DAYS, store_path: Path=None, schedule_path: Optional[Path]=None) -> dict[str, Any]:
    if store_path is None:
        store_path = STORE_PATH()
    sender = resolve_sender_id(sender_id)
    channel = resolve_channel_id(origin_channel_id)
    root_id = str(origin_root_id or '').strip()
    if not root_id or len(root_id) < 8:
        raise WatchError({'status': 'error', 'error': 'missing_thread', 'message': 'origin_root_id is required. Watches notify the current thread only.'})
    try:
        days = int(expires_days)
    except (TypeError, ValueError):
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        days = DEFAULT_EXPIRE_DAYS
    if days < 1 or days > MAX_EXPIRE_DAYS:
        raise WatchError({'status': 'error', 'error': 'bad_expiry', 'message': f'expires_days must be 1..{MAX_EXPIRE_DAYS}.'})
    schedule = load_schedule(schedule_path)
    resolved = resolve_item(query, schedule)
    hits = matching_rows(schedule, resolved['item_key'])
    if hits:
        return {'status': 'already_scheduled', 'watch_created': False, 'resolved': resolved, 'matches': hits, 'source_path': schedule['path'], 'source_mtime': schedule['mtime'], 'source_stale': schedule['stale'], 'message': 'The item is already on the production schedule. No watch was created.'}
    policy = _load_policy(sender)
    username = str(policy.get('mattermostUsername') or '').strip()
    now = _now()
    handle, data = _open_locked(store_path)
    try:
        active = [watch for watch in data['watches'] if watch.get('owner_sender_id') == sender and watch.get('status') == 'active']
        if len(active) >= MAX_ACTIVE_PER_OWNER:
            raise WatchError({'status': 'error', 'error': 'owner_cap', 'message': f'At most {MAX_ACTIVE_PER_OWNER} active watches per person.', 'active_count': len(active)})
        for watch in active:
            if watch.get('type') == WATCH_TYPE and (watch.get('resolved') or {}).get('item_key') == resolved['item_key']:
                raise WatchError({'status': 'error', 'error': 'duplicate_watch', 'message': 'An active watch already exists for this item.', 'watch_id': watch.get('watch_id')})
        watch = {'watch_id': _new_watch_id(now), 'type': WATCH_TYPE, 'status': 'active', 'mode': 'one_shot', 'owner_sender_id': sender, 'owner_username': username, 'origin_platform': 'mattermost', 'origin_channel_id': channel, 'origin_root_id': root_id, 'query': str(query).strip(), 'resolved': resolved, 'source': 'production-schedule snapshot (今天生產的產品 + 今天生產排程)', 'created_at': _iso(now), 'expires_at': _iso(now + timedelta(days=days)), 'last_checked_at': None, 'last_match': None, 'fired_at': None, 'notify_post_id': None}
        data['watches'].append(watch)
        _save_locked(handle, data)
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
    return {'status': 'ok', 'watch_created': True, 'watch': _public_watch(watch, admin=sender_is_admin(sender)), 'source_path': schedule['path'], 'source_mtime': schedule['mtime'], 'source_stale': schedule['stale'], 'message': 'Watch created. PD One will reply in this thread when the item is scheduled.'}

def list_watches(*, sender_id: str, store_path: Path=None) -> dict[str, Any]:
    if store_path is None:
        store_path = STORE_PATH()
    sender = resolve_sender_id(sender_id)
    admin = sender_is_admin(sender)
    handle, data = _open_locked(store_path)
    try:
        watches = data['watches']
        if not admin:
            watches = [watch for watch in watches if watch.get('owner_sender_id') == sender]
        return {'status': 'ok', 'admin': admin, 'count': len(watches), 'watches': [_public_watch(watch, admin=admin) for watch in watches]}
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()

def cancel_watch(*, sender_id: str, watch_id: str, store_path: Path=None) -> dict[str, Any]:
    if store_path is None:
        store_path = STORE_PATH()
    sender = resolve_sender_id(sender_id)
    watch_id = str(watch_id or '').strip()
    if not WATCH_ID_RE.fullmatch(watch_id):
        raise WatchError({'status': 'error', 'error': 'bad_watch_id', 'message': 'watch_id must look like PDWATCH-YYYYMMDD-XXXXXXXX.'})
    admin = sender_is_admin(sender)
    handle, data = _open_locked(store_path)
    try:
        target = None
        for watch in data['watches']:
            if watch.get('watch_id') == watch_id:
                target = watch
                break
        if target is None:
            raise WatchError({'status': 'error', 'error': 'not_found', 'message': 'Watch not found.'})
        if target.get('owner_sender_id') != sender and (not admin):
            raise WatchError({'status': 'error', 'error': 'forbidden', 'message': 'You can only cancel your own watches.'})
        if target.get('status') == 'active':
            target['status'] = 'cancelled'
            target['cancelled_at'] = _iso(_now())
            target['cancelled_by'] = sender
            _save_locked(handle, data)
        return {'status': 'ok', 'watch': _public_watch(target, admin=admin)}
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()

def _mattermost_post(channel_id: str, root_id: str, message: str) -> dict[str, Any]:
    sys.path.append(str(ROOT() / 'tools'))
    from mattermost_review_log import mattermost_context
    import requests
    base, _token, headers, _me = mattermost_context()
    response = requests.post(f'{base}/api/v4/posts', headers={**headers, 'Content-Type': 'application/json'}, json={'channel_id': channel_id, 'root_id': root_id, 'message': message}, timeout=30)
    response.raise_for_status()
    post = response.json()
    post_id = str(post.get('id') or '')
    if not post_id:
        raise RuntimeError('Mattermost post returned empty id')
    return {'post_id': post_id, 'channel_id': post.get('channel_id')}

def _notify_message(watch: dict[str, Any], matches: list[dict[str, Any]]) -> str:
    username = str(watch.get('owner_username') or '').strip()
    mention = f'@{username}' if username else 'you'
    label = (watch.get('resolved') or {}).get('item_label') or watch.get('query')
    lines = []
    for hit in matches[:3]:
        lines.append(f'- {hit['date']} · {hit['machine']} · {hit['product']} · {hit.get('quantity') or '?'}')
    body_en = f'{mention} {label} is now on the production schedule.\n' + '\n'.join(lines) + '\nThis one-shot watch is complete.'
    body_zh = f'{mention} **{label}** 已出現在生管排程。\n' + '\n'.join(lines) + '\n此為一次性通知，監看已結束。'
    return f'{body_zh}\n\n{body_en}'

def poll_watches(*, store_path: Path=None, schedule_path: Optional[Path]=None, send: bool=True) -> dict[str, Any]:
    if store_path is None:
        store_path = STORE_PATH()
    schedule = load_schedule(schedule_path)
    now = _now()
    now_iso = _iso(now)
    fired: list[str] = []
    expired: list[str] = []
    checked = 0
    handle, data = _open_locked(store_path)
    try:
        for watch in data['watches']:
            if watch.get('type') != WATCH_TYPE:
                continue
            if watch.get('status') != 'active':
                continue
            expires = str(watch.get('expires_at') or '')
            if expires and expires < now_iso:
                watch['status'] = 'expired'
                watch['last_checked_at'] = now_iso
                expired.append(str(watch.get('watch_id')))
                continue
            checked += 1
            item_key = (watch.get('resolved') or {}).get('item_key') or ''
            hits = matching_rows(schedule, item_key)
            watch['last_checked_at'] = now_iso
            if not hits:
                continue
            watch['last_match'] = hits[0]
            post_id = None
            if send:
                receipt = _mattermost_post(str(watch.get('origin_channel_id')), str(watch.get('origin_root_id')), _notify_message(watch, hits))
                post_id = receipt['post_id']
            watch['status'] = 'fired'
            watch['fired_at'] = now_iso
            watch['notify_post_id'] = post_id
            fired.append(str(watch.get('watch_id')))
        _save_locked(handle, data)
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
    return {'status': 'ok', 'checked': checked, 'fired': fired, 'expired': expired, 'source_path': schedule['path'], 'source_mtime': schedule['mtime'], 'source_stale': schedule['stale'], 'send': send}

def main(argv: Optional[list[str]]=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', default=str(STORE_PATH()))
    parser.add_argument('--schedule', default='')
    sub = parser.add_subparsers(dest='cmd', required=True)
    create = sub.add_parser('create')
    create.add_argument('--query', required=True)
    create.add_argument('--sender-id', default='')
    create.add_argument('--channel-id', required=True)
    create.add_argument('--root-id', required=True)
    create.add_argument('--expires-days', type=int, default=DEFAULT_EXPIRE_DAYS)
    listed = sub.add_parser('list')
    listed.add_argument('--sender-id', default='')
    cancel = sub.add_parser('cancel')
    cancel.add_argument('--sender-id', default='')
    cancel.add_argument('--watch-id', required=True)
    poll = sub.add_parser('poll')
    poll.add_argument('--no-send', action='store_true')
    args = parser.parse_args(argv)
    store = Path(args.store)
    schedule = Path(args.schedule) if args.schedule else None
    try:
        if args.cmd == 'create':
            payload = create_watch(query=args.query, sender_id=args.sender_id, origin_channel_id=args.channel_id, origin_root_id=args.root_id, expires_days=args.expires_days, store_path=store, schedule_path=schedule)
        elif args.cmd == 'list':
            payload = list_watches(sender_id=args.sender_id, store_path=store)
        elif args.cmd == 'cancel':
            payload = cancel_watch(sender_id=args.sender_id, watch_id=args.watch_id, store_path=store)
        else:
            payload = poll_watches(store_path=store, schedule_path=schedule, send=not args.no_send)
        return emit(payload, 0)
    except WatchError as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return emit(exc.payload, 1)
if __name__ == '__main__':
    raise SystemExit(main())

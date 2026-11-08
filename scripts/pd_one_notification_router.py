#!/home/prodesign/.hermes/runtime/current/.venv/bin/python
"""Named notification router for PD One operational alerts.

Destinations and failover policy live in notification-routes.json. Callers name a
logical route; they never embed channel IDs, email addresses, or platform policy.
Failed primary deliveries are queued and later summarized by correlation key.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import io
import json
import logging
import os
import re
import smtplib
import ssl
import subprocess
import sys
import tempfile
import urllib.request
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any

from scripts.deploy.nemo import neo_watch_webhook as neo
from scripts.deploy.nemo.layout import resolve_hermes_home

LOG = logging.getLogger(__name__)

DEFAULT_CONFIG = Path('/home/prodesign/.hermes/config/notification-routes.json')
DEFAULT_STATE_DIR = Path('/home/prodesign/.hermes/state/notification-router')
HERMES = '/home/prodesign/.local/bin/hermes'
PDONE_PROFILE = Path('/home/prodesign/.hermes/profiles/pdone')
HERMES_AGENT = Path(os.environ.get("HERMES_AGENT_DIR", "/home/prodesign/.hermes/runtime/current"))
TARGET_RE = re.compile(r'^(mattermost|discord|telegram|email|local|webhook):(.+)$', re.IGNORECASE)
NEO_STATE_REL = Path('state') / 'pd_one_notification_router' / 'state.json'
DEFAULT_HOLD_MINUTES = 10
SEVERITY_ORDER = {'info': 0, 'warning': 1, 'error': 2, 'critical': 3}
RETRY_BASE_SECONDS = 120
RETRY_MAX_SECONDS = 3600


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime | None = None) -> str:
    return (value or utcnow()).isoformat(timespec='seconds')


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def atomic_json(path: Path, payload: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write('\n')
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('routes'), dict):
        raise RuntimeError(f'invalid notification route registry: {path}')
    return data


def validate_target(target: str) -> tuple[str, str]:
    match = TARGET_RE.match(target or '')
    if not match or not match.group(2).strip():
        raise ValueError(f'invalid target {target!r}; expected platform:destination')
    return match.group(1), match.group(2).strip()


def validate_route(name: str, route: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        validate_target(str((route.get('primary') or {}).get('target') or ''))
    except Exception as exc:
        errors.append(f'{name}.primary.target: {exc}')
    fallback = route.get('fallback') or {}
    if fallback.get('target'):
        try:
            validate_target(str(fallback['target']))
        except Exception as exc:
            errors.append(f'{name}.fallback.target: {exc}')
    for key in ('dedupe_window_minutes', 'fallback_after_minutes'):
        if key in route and (not isinstance(route[key], int) or route[key] < 0):
            errors.append(f'{name}.{key}: must be a non-negative integer')
    return errors


def hermes_home_from_config(config_path: Path) -> Path:
    """Infer Hermes home from ``.../config/notification-routes.json``."""
    if config_path.name == 'notification-routes.json' and config_path.parent.name == 'config':
        return config_path.parent.parent
    return resolve_hermes_home(None)


def neo_router_state_path(home: Path) -> Path:
    return home / NEO_STATE_REL


def load_neo_router_state(home: Path) -> dict[str, Any]:
    path = neo_router_state_path(home)
    if not path.is_file():
        return {'acked': [], 'held_for_neo': []}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        LOG.exception('resetting corrupt neo router state %s', path)
        return {'acked': [], 'held_for_neo': []}
    if not isinstance(data, dict):
        return {'acked': [], 'held_for_neo': []}
    data.setdefault('acked', [])
    data.setdefault('held_for_neo', [])
    return data


def save_neo_router_state(home: Path, state: dict[str, Any], *, dry_run: bool) -> None:
    if dry_run:
        return
    path = neo_router_state_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    state['updated_at'] = neo.iso_now()
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def hold_minutes(route: dict[str, Any]) -> int:
    raw = route.get('hold_minutes', DEFAULT_HOLD_MINUTES)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_HOLD_MINUTES
    return max(0, value)


def correlation_from_event(event: dict[str, Any]) -> str:
    explicit = str(event.get('correlation_key') or '').strip()
    if explicit:
        return explicit
    fp = str(event.get('fingerprint') or event.get('idempotency_key') or '').strip()
    if fp:
        return neo.correlation_key(fp)
    summary = str(event.get('summary') or event.get('message') or 'event')
    digest = neo.fingerprint_for_findings([{'subject': summary}], alertable_fn=lambda _: True)
    return neo.correlation_key(digest)


def neo_is_acked(state: dict[str, Any], correlation: str) -> bool:
    acked = state.get('acked')
    if not isinstance(acked, list):
        return False
    return correlation in acked


def deliver_webhook_neo(target: str, event: dict[str, Any], *, dry_run: bool) -> bool:
    platform, rest = validate_target(f'webhook:{target}' if ':' not in target else target)
    if platform != 'webhook':
        raise ValueError('expected webhook target')
    url = rest
    if url in {'neo', 'default'}:
        url = None
    payload = dict(event)
    payload.setdefault('schema', neo.SCHEMA_SUPERVISOR)
    payload.setdefault('sent_at', neo.iso_now())
    return neo.post_json_webhook(payload, dry_run=dry_run, url=url)


def deliver_neo_target(home: Path, target: str, event: dict[str, Any], *, dry_run: bool) -> bool:
    platform, rest = validate_target(target if ':' in target else f'mattermost:{target}')
    if platform == 'webhook':
        return deliver_webhook_neo(rest, event, dry_run=dry_run)
    if platform == 'mattermost':
        message = str(event.get('summary') or event.get('message') or json.dumps(event, ensure_ascii=False))
        receipt = deliver_mattermost(rest, message, dry_run)
        if isinstance(receipt, bool):
            return receipt
        return receipt.get('status') in {'sent', 'dry-run-ok'}
    LOG.warning('neo hold release skipped unsupported target %s', target)
    return False


def flush_held(
    home: Path,
    state: dict[str, Any] | None = None,
    *,
    dry_run: bool,
    now: dt.datetime | None = None,
    registry_path: Path | None = None,
) -> int:
    now = now or utcnow()
    state = state if state is not None else load_neo_router_state(home)
    registry_path = registry_path or (home / 'config' / 'notification-routes.json')
    routes_doc = load_registry(registry_path)
    released = 0
    held = state.get('held_for_neo')
    if not isinstance(held, list):
        return 0
    keep: list[dict[str, Any]] = []
    for entry in held:
        if not isinstance(entry, dict):
            continue
        correlation = str(entry.get('correlation_key') or '')
        if neo_is_acked(state, correlation):
            continue
        hold_until_raw = str(entry.get('hold_until') or '')
        try:
            hold_until = parse_iso(hold_until_raw)
        except (TypeError, ValueError):
            hold_until = now
        if now < hold_until:
            keep.append(entry)
            continue
        route_name = str(entry.get('route') or '')
        route = routes_doc.get('routes', {}).get(route_name)
        if not isinstance(route, dict):
            keep.append(entry)
            continue
        targets = route.get('targets') or route.get('primary_targets')
        if not isinstance(targets, list) or not targets:
            primary = route.get('primary') or {}
            target = primary.get('target')
            targets = [target] if target else []
        if not targets:
            keep.append(entry)
            continue
        event = entry.get('event') if isinstance(entry.get('event'), dict) else {}
        if deliver_neo_target(home, str(targets[0]), event, dry_run=dry_run):
            released += 1
        else:
            keep.append(entry)
    state['held_for_neo'] = keep
    save_neo_router_state(home, state, dry_run=dry_run)
    return released


def send_route(
    home: Path,
    route_name: str,
    event: dict[str, Any],
    *,
    dry_run: bool = False,
    now: dt.datetime | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    now = now or utcnow()
    registry_path = registry_path or (home / 'config' / 'notification-routes.json')
    state = load_neo_router_state(home)
    flush_held(home, state, dry_run=dry_run, now=now, registry_path=registry_path)
    state = load_neo_router_state(home)

    routes_doc = load_registry(registry_path)
    route = routes_doc['routes'].get(route_name)
    if not isinstance(route, dict):
        raise SystemExit(f'unknown notification route {route_name!r}')

    correlation = correlation_from_event(event)
    event = {**event, 'correlation_key': correlation}

    if neo_is_acked(state, correlation):
        return {'status': 'suppressed', 'reason': 'acked', 'correlation_key': correlation}

    pre_targets = route.get('pre_targets')
    if isinstance(pre_targets, list) and pre_targets:
        for target in pre_targets:
            if isinstance(target, str):
                deliver_neo_target(home, target, event, dry_run=dry_run)
        hold = hold_minutes(route)
        hold_until = now + dt.timedelta(minutes=hold)
        held_entry = {
            'route': route_name,
            'correlation_key': correlation,
            'hold_until': neo.iso_now(hold_until),
            'event': event,
        }
        held = state.setdefault('held_for_neo', [])
        if isinstance(held, list):
            held = [
                item
                for item in held
                if not (isinstance(item, dict) and item.get('correlation_key') == correlation)
            ]
            held.append(held_entry)
            state['held_for_neo'] = held
        save_neo_router_state(home, state, dry_run=dry_run)
        return {'status': 'held', 'correlation_key': correlation, 'hold_until': held_entry['hold_until']}

    targets = route.get('targets') or route.get('primary_targets')
    if not isinstance(targets, list) or not targets:
        primary = route.get('primary') or {}
        target = primary.get('target')
        if target:
            targets = [target]
    if not targets:
        raise SystemExit(f'route {route_name!r} has no targets')
    ok = deliver_neo_target(home, str(targets[0]), event, dry_run=dry_run)
    return {'status': 'delivered' if ok else 'failed', 'correlation_key': correlation, 'target': targets[0]}


def cmd_ack(home: Path, correlation: str, *, dry_run: bool = False) -> int:
    state = load_neo_router_state(home)
    acked = state.setdefault('acked', [])
    if not isinstance(acked, list):
        acked = []
        state['acked'] = acked
    if correlation not in acked:
        acked.append(correlation)
    held = state.get('held_for_neo')
    if isinstance(held, list):
        state['held_for_neo'] = [
            item for item in held if not (isinstance(item, dict) and item.get('correlation_key') == correlation)
        ]
    save_neo_router_state(home, state, dry_run=dry_run)
    print(json.dumps({'acked': True, 'correlation_key': correlation}))
    return 0


def cmd_is_acked(home: Path, correlation: str) -> int:
    state = load_neo_router_state(home)
    print(json.dumps({'acked': neo_is_acked(state, correlation), 'correlation_key': correlation}))
    return 0



def load_delivery_env() -> None:
    os.environ.setdefault('HERMES_HOME', str(PDONE_PROFILE))
    if str(HERMES_AGENT) not in sys.path:
        sys.path.insert(0, str(HERMES_AGENT))
    try:
        from hermes_cli.env_loader import load_hermes_dotenv  # type: ignore
        with contextlib.redirect_stderr(io.StringIO()):
            load_hermes_dotenv(hermes_home=PDONE_PROFILE)
    except Exception:
        pass
    if not os.environ.get('MATTERMOST_TOKEN') and os.environ.get('MATTERMOST_BOT_TOKEN'):
        os.environ['MATTERMOST_TOKEN'] = os.environ['MATTERMOST_BOT_TOKEN']


def render_message(title: str, body: str, mention: str = '') -> str:
    pieces = []
    if mention.strip():
        pieces.append(mention.strip())
    pieces.append(f'## {title.strip()}')
    if body.strip():
        pieces.append(body.strip())
    return '\n\n'.join(pieces).strip() + '\n'


def deliver_mattermost(channel_id: str, message: str, dry_run: bool) -> dict[str, Any]:
    load_delivery_env()
    base = (os.environ.get('MATTERMOST_URL') or '').rstrip('/')
    token = os.environ.get('MATTERMOST_TOKEN') or ''
    if not base or not token:
        raise RuntimeError('Mattermost URL/token unavailable')
    headers = {'Authorization': f'Bearer {token}'}

    def request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None
        hdrs = dict(headers)
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            hdrs['Content-Type'] = 'application/json'
        req = urllib.request.Request(base + path, headers=hdrs, data=body, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8', errors='replace') or '{}')

    me = request('GET', '/api/v4/users/me')
    channel = request('GET', f'/api/v4/channels/{channel_id}')
    if channel.get('id') != channel_id:
        raise RuntimeError('Mattermost channel readback mismatch')
    if dry_run:
        return {'status': 'dry-run-ok', 'platform': 'mattermost', 'channel_id': channel_id, 'channel_name': channel.get('name'), 'sender': me.get('username')}
    post = request('POST', '/api/v4/posts', {'channel_id': channel_id, 'message': message})
    post_id = str(post.get('id') or '')
    if not post_id:
        raise RuntimeError('Mattermost did not return a post ID')
    readback = request('GET', f'/api/v4/posts/{post_id}')
    if readback.get('channel_id') != channel_id or readback.get('message') != message:
        raise RuntimeError('Mattermost post readback mismatch')
    return {'status': 'sent', 'platform': 'mattermost', 'channel_id': channel_id, 'post_id': post_id, 'sender': me.get('username')}


def deliver_email(recipient: str, title: str, message: str, dry_run: bool) -> dict[str, Any]:
    load_delivery_env()
    sender = os.environ.get('PDNEO_EMAIL_ADDRESS') or 'admin@prodesign-group.com'
    username = os.environ.get('PDNEO_EMAIL_USERNAME') or ''
    password = os.environ.get('PDNEO_EMAIL_PASSWORD') or ''
    host = os.environ.get('PDNEO_EMAIL_SMTP_HOST') or ''
    port = int(os.environ.get('PDNEO_EMAIL_SMTP_PORT') or '25')
    if not host:
        raise RuntimeError('email SMTP host unavailable')
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = title[:180]
    msg['Date'] = formatdate(localtime=False)
    msg['Message-ID'] = make_msgid(domain=sender.split('@')[-1])
    msg.set_content(message)
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        tls = False
        auth = False
        if smtp.has_extn('starttls'):
            smtp.starttls(context=context)
            smtp.ehlo()
            tls = True
        if smtp.has_extn('auth') and username and password:
            smtp.login(username, password)
            auth = True
        if not dry_run:
            refused = smtp.send_message(msg)
            if refused:
                raise RuntimeError(f'SMTP refused {len(refused)} recipient(s)')
    return {'status': 'dry-run-ok' if dry_run else 'sent', 'platform': 'email', 'recipient': recipient, 'message_id': msg['Message-ID'], 'tls': tls, 'auth': auth}


def deliver_hermes(target: str, message: str, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        proc = subprocess.run([HERMES, '--profile', 'pdone', 'send', '--list', target.split(':', 1)[0], '--json'], text=True, capture_output=True, timeout=30, check=False)
    else:
        proc = subprocess.run([HERMES, '--profile', 'pdone', 'send', '--to', target, '--json', message], text=True, capture_output=True, timeout=60, check=False)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or 'Hermes delivery failed')[-1200:])
    try:
        payload = json.loads(proc.stdout or '{}')
    except json.JSONDecodeError:
        payload = {'raw': (proc.stdout or '')[-1000:]}
    if not dry_run and payload.get('success') is False:
        raise RuntimeError(f'Hermes delivery reported failure: {payload}')
    return {'status': 'dry-run-ok' if dry_run else 'sent', 'platform': target.split(':', 1)[0], 'target': target, 'receipt': payload}


def deliver_target(target: str, title: str, message: str, dry_run: bool = False) -> dict[str, Any]:
    platform, destination = validate_target(target)
    if platform == 'local':
        return {'status': 'local-only', 'platform': 'local', 'target': target}
    if platform == 'mattermost':
        return deliver_mattermost(destination, message, dry_run)
    if platform == 'email':
        return deliver_email(destination, title, message, dry_run)
    return deliver_hermes(target, message, dry_run)


def state_path(state_dir: Path, route_name: str) -> Path:
    safe = re.sub(r'[^a-zA-Z0-9_.-]+', '-', route_name).strip('-')
    return state_dir / f'{safe}.json'


def load_route_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def fingerprint(route_name: str, correlation_key: str) -> str:
    return hashlib.sha256(f'{route_name}\0{correlation_key}'.encode()).hexdigest()[:20]


def fallback_allowed(route: dict[str, Any], severity: str, first_failure: str, now: dt.datetime) -> bool:
    fb = route.get('fallback') or {}
    if not fb.get('target'):
        return False
    minimum = str(fb.get('minimum_severity') or 'critical')
    if SEVERITY_ORDER.get(severity, 0) < SEVERITY_ORDER.get(minimum, 3):
        return False
    delay = int(route.get('fallback_after_minutes') or 0)
    return (now - parse_iso(first_failure)).total_seconds() >= delay * 60


def schedule_retry(item: dict[str, Any], error: str, now: dt.datetime) -> None:
    attempts = int(item.get('attempts') or 0) + 1
    delay = min(RETRY_BASE_SECONDS * (2 ** (attempts - 1)), RETRY_MAX_SECONDS)
    item['attempts'] = attempts
    item['last_failure_at'] = iso(now)
    item['last_error'] = error[-1000:]
    item['next_attempt_at'] = iso(now + dt.timedelta(seconds=delay))


def retry_due(item: dict[str, Any], now: dt.datetime) -> bool:
    value = str(item.get('next_attempt_at') or '')
    if not value:
        return True
    try:
        return now >= parse_iso(value)
    except (TypeError, ValueError):
        return True


def queue_pending(state: dict[str, Any], key: str, event_id: str, title: str, body: str, severity: str, error: str, now: dt.datetime, *, attempted: bool = True) -> dict[str, Any]:
    pending = state.setdefault('pending', {})
    item = pending.get(key) or {'first_failure_at': iso(now), 'count': 0, 'event_ids': []}
    item['title'] = title
    item['body'] = body[-5000:]
    item['severity'] = max(str(item.get('severity') or 'info'), severity, key=lambda x: SEVERITY_ORDER.get(x, 0))
    ids = list(item.get('event_ids') or [])
    if event_id not in ids:
        ids.append(event_id)
        item['count'] = int(item.get('count') or 0) + 1
    item['event_ids'] = ids[-20:]
    if attempted:
        schedule_retry(item, error, now)
    pending[key] = item
    return item


def send_event(registry_path: Path, state_dir: Path, route_name: str, event_id: str, correlation_key: str, severity: str, title: str, body: str, dry_run: bool = False, force: bool = False) -> dict[str, Any]:
    registry = load_registry(registry_path)
    route = registry['routes'].get(route_name)
    if not isinstance(route, dict):
        raise RuntimeError(f'unknown route: {route_name}')
    errors = validate_route(route_name, route)
    if errors:
        raise RuntimeError('; '.join(errors))
    pre_targets = route.get('pre_targets')
    if isinstance(pre_targets, list) and pre_targets:
        home = hermes_home_from_config(registry_path)
        event = {
            'severity': severity,
            'summary': title,
            'message': body,
            'fingerprint': correlation_key or event_id,
            'correlation_key': correlation_key or event_id,
            'event_id': event_id,
        }
        return send_route(home, route_name, event, dry_run=dry_run, registry_path=registry_path)
    now = utcnow()
    path = state_path(state_dir, route_name)
    state = load_route_state(path)
    key = fingerprint(route_name, correlation_key or event_id)
    sent = state.setdefault('sent', {})
    previous = sent.get(key) or {}
    dedupe_minutes = int(route.get('dedupe_window_minutes') or 0)
    if not force and previous.get('at') and (now - parse_iso(previous['at'])).total_seconds() < dedupe_minutes * 60:
        previous['suppressed'] = int(previous.get('suppressed') or 0) + 1
        sent[key] = previous
        atomic_json(path, state)
        return {'status': 'suppressed', 'route': route_name, 'correlation_key': correlation_key, 'suppressed': previous['suppressed']}
    pending_item = (state.get('pending') or {}).get(key)
    next_attempt_at = str((pending_item or {}).get('next_attempt_at') or '')
    if not force and pending_item and not retry_due(pending_item, now):
        item = queue_pending(state, key, event_id, title, body, severity, '', now, attempted=False)
        if not dry_run:
            atomic_json(path, state)
        return {
            'status': 'queued',
            'route': route_name,
            'correlation_key': correlation_key,
            'retry': 'deferred',
            'next_attempt_at': item.get('next_attempt_at'),
        }
    primary = route['primary']
    message = render_message(title, body, str(primary.get('mention') or ''))
    try:
        receipt = deliver_target(str(primary['target']), title, message, dry_run=dry_run)
        if not dry_run:
            sent[key] = {'at': iso(now), 'event_id': event_id, 'correlation_key': correlation_key, 'target': primary['target'], 'suppressed': 0}
            state.setdefault('pending', {}).pop(key, None)
            atomic_json(path, state)
        return {'status': receipt.get('status'), 'route': route_name, 'target': primary['target'], 'receipt': receipt}
    except Exception as exc:
        item = queue_pending(state, key, event_id, title, body, severity, repr(exc), now)
        fb = route.get('fallback') or {}
        fallback_receipt = None
        if fallback_allowed(route, severity, item['first_failure_at'], now):
            fallback_title = f'[Fallback] {title}'
            fallback_message = render_message(fallback_title, body, str(fb.get('mention') or ''))
            try:
                fallback_receipt = deliver_target(str(fb['target']), fallback_title, fallback_message, dry_run=dry_run)
                item['fallback_at'] = iso(now)
                item['fallback_target'] = fb['target']
            except Exception as fallback_exc:
                fallback_receipt = {'status': 'failed', 'error': repr(fallback_exc)}
        if not dry_run:
            atomic_json(path, state)
        return {'status': 'queued', 'route': route_name, 'target': primary['target'], 'correlation_key': correlation_key, 'primary_error': repr(exc), 'fallback': fallback_receipt}


def flush_pending(registry_path: Path, state_dir: Path, route_name: str, dry_run: bool = False) -> dict[str, Any]:
    home = hermes_home_from_config(registry_path)
    flush_held(home, dry_run=dry_run, registry_path=registry_path)
    registry = load_registry(registry_path)
    route = registry['routes'].get(route_name)
    if not isinstance(route, dict):
        raise RuntimeError(f'unknown route: {route_name}')
    path = state_path(state_dir, route_name)
    state = load_route_state(path)
    pending = dict(state.get('pending') or {})
    results = []
    for key, item in pending.items():
        now = utcnow()
        count = int(item.get('count') or 1)
        next_attempt_at = str(item.get('next_attempt_at') or '')
        if not retry_due(item, now):
            results.append({'key': key, 'status': 'retry-deferred', 'count': count, 'next_attempt_at': next_attempt_at})
            continue
        title = f"Recovered notification route: {item.get('title') or key}"
        body = '\n'.join([
            f"- Queued events: **{count}**",
            f"- First failure: `{item.get('first_failure_at')}`",
            f"- Last failure: `{item.get('last_failure_at')}`",
            f"- Severity: `{item.get('severity')}`",
            '',
            str(item.get('body') or '').strip(),
        ])
        primary = route['primary']
        message = render_message(title, body, str(primary.get('mention') or ''))
        try:
            receipt = deliver_target(str(primary['target']), title, message, dry_run=dry_run)
            results.append({'key': key, 'status': receipt.get('status'), 'count': count, 'receipt': receipt})
            if not dry_run:
                state.setdefault('pending', {}).pop(key, None)
                state.setdefault('sent', {})[key] = {'at': iso(), 'target': primary['target'], 'recovered_batch_count': count, 'suppressed': 0}
        except Exception as exc:
            schedule_retry(item, repr(exc), now)
            state.setdefault('pending', {})[key] = item
            results.append({'key': key, 'status': 'still-queued', 'error': repr(exc), 'count': count})
    if not dry_run:
        atomic_json(path, state)
    return {'status': 'ok', 'route': route_name, 'pending_before': len(pending), 'results': results}


def audit(registry_path: Path) -> dict[str, Any]:
    registry = load_registry(registry_path)
    errors: list[str] = []
    for name, route in registry['routes'].items():
        errors.extend(validate_route(name, route))
    return {'status': 'ok' if not errors else 'error', 'routes': sorted(registry['routes']), 'errors': errors}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--state-dir', type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument('--hermes-home', default=None)
    parser.add_argument('--dry-run', action='store_true')
    sub = parser.add_subparsers(dest='command', required=True)
    send = sub.add_parser('send', help='Send through a named route')
    send.add_argument('--route', required=True)
    send.add_argument('--event-id')
    send.add_argument('--correlation-key', default='')
    send.add_argument('--severity', choices=sorted(SEVERITY_ORDER), default='warning')
    send.add_argument('--title')
    group = send.add_mutually_exclusive_group(required=False)
    group.add_argument('--body')
    group.add_argument('--body-file', type=Path)
    send.add_argument('--json', help='Event JSON object (Neo hold / webhook route API)')
    send.add_argument('--force', action='store_true')
    flush = sub.add_parser('flush', help='Release held Mattermost messages and flush pending retries')
    flush.add_argument('--route', required=True)
    ack = sub.add_parser('ack', help='Acknowledge a correlation key (suppress Mattermost release)')
    ack.add_argument('--correlation-key', required=True)
    is_acked = sub.add_parser('is-acked', help='Return whether a correlation key was acked')
    is_acked.add_argument('--correlation-key', required=True)
    sub.add_parser('audit')
    args = parser.parse_args()
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else hermes_home_from_config(args.config))
    if args.command == 'audit':
        result = audit(args.config)
    elif args.command == 'ack':
        return cmd_ack(home, args.correlation_key, dry_run=args.dry_run)
    elif args.command == 'is-acked':
        return cmd_is_acked(home, args.correlation_key)
    elif args.command == 'flush':
        result = flush_pending(args.config, args.state_dir, args.route, args.dry_run)
    elif args.json:
        try:
            event = json.loads(args.json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f'invalid --json: {exc}') from exc
        if not isinstance(event, dict):
            raise SystemExit('--json must be an object')
        result = send_route(home, args.route, event, dry_run=args.dry_run, registry_path=args.config)
    else:
        if not args.event_id or not args.title or (args.body is None and args.body_file is None):
            raise SystemExit('send requires --event-id, --title, and --body|--body-file unless --json is set')
        body = args.body if args.body is not None else args.body_file.read_text(encoding='utf-8')
        result = send_event(
            args.config,
            args.state_dir,
            args.route,
            args.event_id,
            args.correlation_key or args.event_id,
            args.severity,
            args.title,
            body,
            args.dry_run,
            args.force,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get('status') not in {'error', 'failed'} else 1


def parse_target(raw: str) -> tuple[str, str]:
    return validate_target(raw)


load_state = load_neo_router_state


if __name__ == '__main__':
    raise SystemExit(main())

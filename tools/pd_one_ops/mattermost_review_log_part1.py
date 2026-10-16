from __future__ import annotations
__all__ = ['cmd_scan_interactions', '_scan_interactions_locked', 'cmd_scan_attachments', '_scan_attachments_locked', 'load_state', 'save_state', 'is_closed_record', 'needs_follow_up_record', 'is_andy_record', 'top_counts_text', 'record_person', 'record_actor', 'normalized_record_summary', 'parse_utc_timestamp', 'records_in_time_window', 'summarize_closed_records', 'summarize_request_highlights', 'cmd_digest', 'cmd_ensure_review_log_headers', 'cmd_ensure_quality_headers', 'cmd_backfill_response_quality', 'cmd_backfill_mattermost_user_post_links', 'main', 'build_parser']
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import mattermost_policy_lookup
from pd_one_federation_bridge import emit_pd_one_event
from tools.pd_one_ops.mattermost_review_log_part0 import *

def cmd_scan_interactions(args: argparse.Namespace) -> None:
    configure_scan_translation(args)
    INTERACTION_SCAN_LOCK_PATH().parent.mkdir(parents=True, exist_ok=True)
    with INTERACTION_SCAN_LOCK_PATH().open('w') as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            print(json.dumps({'scanned': False, 'skipped': 'already_running'}, ensure_ascii=False, indent=2))
            return
        _scan_interactions_locked(args)

def _scan_interactions_locked(args: argparse.Namespace) -> None:
    max_seen_ms = _PdUnset
    rows = _PdUnset
    since_ms = _PdUnset

    def _pd_phase_1():
        nonlocal max_seen_ms, rows, since_ms
        base, _token, headers, me = mattermost_context()
        try:
            auth_users_policy, auth_roles_policy, _auth_source_hash = load_auth_policies()
        except Exception:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            auth_users_policy = auth_roles_policy = None
        auth_cache: dict[str, dict[str, Any]] = {}
        scan_state: dict[str, Any] = {}
        if INTERACTION_SCAN_STATE_PATH().exists():
            try:
                scan_state = json.loads(INTERACTION_SCAN_STATE_PATH().read_text(encoding='utf-8'))
            except Exception:
                logging.getLogger('pd_one_ops').exception('pd one command failed')
                scan_state = {}
        since_ms = int(scan_state.get('lastScannedAtMs') or 0) if args.since_ms is None else int(args.since_ms)
        max_seen_ms = since_ms
        existing_post_ids, existing_tuples, existing_events = existing_review_log_keys()
        channels_resp = requests.get(f'{base}/api/v4/users/me/channels', headers=headers, params={'per_page': 200}, timeout=30)
        channels_resp.raise_for_status()
        rows = []
        seen_users: dict[str, dict[str, Any]] = {}
        for channel in channels_resp.json():
            if channel.get('type') == 'D':
                continue
            posts_resp = requests.get(f'{base}/api/v4/channels/{channel['id']}/posts', headers=headers, params={'per_page': args.per_page}, timeout=30)
            posts_resp.raise_for_status()
            posts_body = posts_resp.json()
            posts = posts_body.get('posts', {})
            interaction_roots: set[str] = set()
            for post in posts.values():
                root = post.get('root_id') or post.get('id') or ''
                if post.get('user_id') == me.get('id') or post_mentions_bot(post, me):
                    interaction_roots.add(root)
            for post_id in posts_body.get('order', []):
                post = posts.get(post_id) or {}
                create_at = int(post.get('create_at') or 0)
                max_seen_ms = max(max_seen_ms, create_at)
                if create_at <= since_ms:
                    continue
                user_id = post.get('user_id') or ''
                if not user_id or user_id == me.get('id'):
                    continue
                if post_id in existing_post_ids:
                    continue
                root = post.get('root_id') or post.get('id') or ''
                is_dm = channel.get('type') == 'D'
                mentioned = post_mentions_bot(post, me)
                in_pd_one_thread = bool(root and root in interaction_roots)
                if not (is_dm or mentioned or in_pd_one_thread):
                    continue
                ts = datetime.fromtimestamp(create_at / 1000, timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
                if (ts, user_id, channel.get('id', '')) in existing_events:
                    continue
                if user_id not in seen_users:
                    seen_users[user_id] = resolve_user(user_id)
                if seen_users[user_id].get('mattermost_is_bot'):
                    continue
                if is_dm:
                    if user_id not in auth_cache:
                        auth_cache[user_id] = resolve_auth(user_id, auth_users_policy, auth_roles_policy)
                    setup_refusals = setup_refusal_bot_replies_after(posts, me.get('id', ''), post)
                    approval_gated = approval_gated_bot_replies_after(posts, me.get('id', ''), post)
                    normal_replies = normal_bot_replies_after(posts, me.get('id', ''), post, require_same_thread=False)
                    row = review_row_for_dm_post(channel, post, seen_users[user_id], auth=auth_cache[user_id], setup_refusal_replies=setup_refusals, approval_gated_replies=approval_gated, normal_bot_replies=normal_replies)
                else:
                    approval_gated = approval_gated_bot_replies_after(posts, me.get('id', ''), post)
                    normal_replies = normal_bot_replies_after(posts, me.get('id', ''), post)
                    if not should_capture_channel_interaction(mentioned=mentioned, in_pd_one_thread=in_pd_one_thread, has_normal_bot_reply=bool(normal_replies or approval_gated)):
                        continue
                    reason = 'Mattermost channel post explicitly mentioned PD One' if mentioned else 'Mattermost channel thread reply in a PD One interaction thread'
                    row = review_row_for_channel_post(channel, post, seen_users[user_id], reason=reason, normal_bot_replies=normal_replies, approval_gated_replies=approval_gated)
                rec = row_record(row)
                dedupe_key = (rec['timestamp_utc'], rec['user_id'], rec['request_summary'])
                if dedupe_key in existing_tuples:
                    continue
                existing_post_ids.add(post_id)
                existing_events.add((rec['timestamp_utc'], rec['user_id'], rec['channel_id']))
                existing_tuples.add(dedupe_key)
                rows.append(row)
        rows.sort(key=lambda r: r[0])

    def _pd_phase_2():
        if args.dry_run:
            print(json.dumps({'sinceMs': since_ms, 'maxSeenMs': max_seen_ms, 'wouldAppend': len(rows), 'rows': rows}, ensure_ascii=False, indent=2))
            return _PdReturn(None)
        result = append_rows(rows)
        INTERACTION_SCAN_STATE_PATH().parent.mkdir(parents=True, exist_ok=True)
        INTERACTION_SCAN_STATE_PATH().write_text(json.dumps({'lastScannedAtMs': max_seen_ms, 'lastScannedAtUtc': datetime.fromtimestamp(max_seen_ms / 1000, timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z') if max_seen_ms else '', 'lastRunAtUtc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'), 'lastAppended': len(rows)}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'scanned': True, 'appended': len(rows), 'sheet': result}, ensure_ascii=False, indent=2))
    _pd_result = _pd_phase_1()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
    _pd_result = _pd_phase_2()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value

def cmd_scan_attachments(args: argparse.Namespace) -> None:
    configure_scan_translation(args)
    ATTACHMENT_SCAN_LOCK_PATH().parent.mkdir(parents=True, exist_ok=True)
    with ATTACHMENT_SCAN_LOCK_PATH().open('w') as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            print(json.dumps({'scanned': False, 'skipped': 'already_running'}, ensure_ascii=False, indent=2))
            return
        try:
            _scan_attachments_locked(args)
        except KeyboardInterrupt:
            raise
        except BaseException as exc:
            emit_pd_one_event(source='mattermost-attachment-review-log-scanner', summary='Mattermost attachment review_log scanner failed', detail=f'{type(exc).__name__}: {exc}', event_type='pd-one.attachment_failure', severity='error', command='tools/mattermost_review_log.py scan-attachments', what_was_tried=['Attachment scanner failed before completing review_log write/readback.'])
            raise

def _scan_attachments_locked(args: argparse.Namespace) -> None:
    base, _token, headers, me = mattermost_context()
    scan_state: dict[str, Any] = {}
    if ATTACHMENT_SCAN_STATE_PATH().exists():
        try:
            scan_state = json.loads(ATTACHMENT_SCAN_STATE_PATH().read_text(encoding='utf-8'))
        except Exception:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            scan_state = {}
    since_ms = int(scan_state.get('lastScannedAtMs') or 0) if args.since_ms is None else int(args.since_ms)
    max_seen_ms = since_ms
    existing_post_ids, existing_tuples, existing_events = existing_review_log_keys()
    channels_resp = requests.get(f'{base}/api/v4/users/me/channels', headers=headers, params={'per_page': 200}, timeout=30)
    channels_resp.raise_for_status()
    rows: list[list[str]] = []
    seen_users: dict[str, dict[str, Any]] = {}
    for channel in channels_resp.json():
        posts_resp = requests.get(f'{base}/api/v4/channels/{channel['id']}/posts', headers=headers, params={'per_page': args.per_page}, timeout=30)
        posts_resp.raise_for_status()
        posts_body = posts_resp.json()
        posts = posts_body.get('posts', {})
        for post_id in posts_body.get('order', []):
            post = posts.get(post_id) or {}
            create_at = int(post.get('create_at') or 0)
            max_seen_ms = max(max_seen_ms, create_at)
            if create_at <= since_ms:
                continue
            if post.get('user_id') != me.get('id'):
                continue
            file_ids = [str(x) for x in post.get('file_ids') or [] if str(x)]
            if not file_ids:
                continue
            if post_id in existing_post_ids:
                continue
            if channel.get('type') == 'D':
                subject_user_id = dm_other_user_id(channel.get('id', ''), me.get('id', ''))
            else:
                subject_user_id = me.get('id', '')
            if not subject_user_id:
                continue
            if subject_user_id not in seen_users:
                seen_users[subject_user_id] = resolve_user(subject_user_id)
            files = []
            for file_id in file_ids:
                try:
                    info = mattermost_file_info(file_id)
                    info.setdefault('id', file_id)
                    files.append(info)
                except Exception:
                    logging.getLogger('pd_one_ops').exception('pd one command failed')
                    files.append({'id': file_id, 'name': file_id})
            row = review_row_for_attachment_sent(channel, post, seen_users[subject_user_id], files)
            rec = row_record(row)
            dedupe_key = (rec['timestamp_utc'], rec['user_id'], rec['request_summary'])
            if dedupe_key in existing_tuples:
                continue
            existing_post_ids.add(post_id)
            existing_events.add((rec['timestamp_utc'], rec['user_id'], rec['channel_id']))
            existing_tuples.add(dedupe_key)
            rows.append(row)
    rows.sort(key=lambda r: r[0])
    if args.dry_run:
        print(json.dumps({'sinceMs': since_ms, 'maxSeenMs': max_seen_ms, 'wouldAppend': len(rows), 'rows': rows}, ensure_ascii=False, indent=2))
        return
    result = append_rows(rows)
    ATTACHMENT_SCAN_STATE_PATH().parent.mkdir(parents=True, exist_ok=True)
    ATTACHMENT_SCAN_STATE_PATH().write_text(json.dumps({'lastScannedAtMs': max_seen_ms, 'lastScannedAtUtc': datetime.fromtimestamp(max_seen_ms / 1000, timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z') if max_seen_ms else '', 'lastRunAtUtc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'), 'lastAppended': len(rows)}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'scanned': True, 'appended': len(rows), 'sheet': result}, ensure_ascii=False, indent=2))

def load_state() -> dict[str, Any]:
    if STATE_PATH().exists():
        try:
            return json.loads(STATE_PATH().read_text(encoding='utf-8'))
        except Exception:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
    return {'lastProcessedRow': 1, 'lastDigestAtUtc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}

def save_state(state: dict[str, Any]) -> None:
    STATE_PATH().parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH().write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def is_closed_record(record: dict[str, str]) -> bool:
    return str(record.get('review_status', '')).strip().lower() == 'closed'

def needs_follow_up_record(record: dict[str, str]) -> bool:
    """Return true only for still-open rows explicitly marked for follow-up."""
    follow_value = str(record.get('follow_up_needed', '')).strip().lower()
    return follow_value in {'yes', 'true', 'y', '1'} and (not is_closed_record(record))

def is_andy_record(record: dict[str, str]) -> bool:
    user_label = str(record.get('user_label', '')).strip().lower()
    user_id = str(record.get('user_id', '')).strip().lower()
    name_en = str(record.get('name_en', '')).strip().lower()
    channel_name = str(record.get('channel_name', '')).strip().lower()
    username = site_text('PDONE_OWNER_MM_USERNAME').strip().lower()
    email = site_text('PDONE_EMAIL_ANDY_LIN').strip().lower()
    owner_name = site_text('PDONE_OWNER_NAME_EN').strip().lower()
    if username and (user_label == username or user_label.startswith(username + ' ') or user_id == username or channel_name.startswith('dm: ' + username + ' <>')):
        return True
    if email and email in user_label:
        return True
    return bool(owner_name and name_en == owner_name)

def top_counts_text(counts: dict[str, int], limit: int=5) -> str:
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return ', '.join((f'**{name}** ({count})' for name, count in ordered)) or 'none'

def record_person(record: dict[str, str]) -> str:
    person = ' / '.join((x for x in [record.get('name_zh_tw', ''), record.get('name_en', '')] if x))
    return person or record.get('user_label') or record.get('user_id') or 'unknown user'

def record_actor(record: dict[str, str]) -> str:
    """Return an audit-friendly user label including Mattermost identity plus resolved names when available."""
    who = record.get('user_label') or record.get('user_id') or 'unknown user'
    person = ' / '.join((x for x in [record.get('name_zh_tw', ''), record.get('name_en', '')] if x))
    if person and person not in who:
        return f'{who} ({person})'
    return who

def normalized_record_summary(record: dict[str, str]) -> str:
    summary = (record.get('request_summary') or record.get('reason') or '').strip()
    return re.sub('\\s+', ' ', summary).rstrip('.')

def parse_utc_timestamp(value: str) -> datetime | None:
    value = (value or '').strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return None

def records_in_time_window(records: list[dict[str, str]], *, start_utc: datetime | None, end_utc: datetime | None) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for record in records:
        ts = parse_utc_timestamp(record.get('timestamp_utc', ''))
        if ts is None:
            continue
        if start_utc is not None and ts <= start_utc:
            continue
        if end_utc is not None and ts > end_utc:
            continue
        selected.append(record)
    return selected

def summarize_closed_records(records: list[dict[str, str]]) -> list[str]:
    if not records:
        return []
    category_counts: dict[str, int] = {}
    channel_counts: dict[str, int] = {}
    response_counts: dict[str, int] = {}
    people: set[str] = set()
    themes: dict[str, int] = {}
    for r in records:
        category = r.get('category') or 'uncategorized'
        channel = r.get('channel_name') or r.get('channel_id') or 'unknown channel'
        response_type = r.get('assistant_response_type') or 'unspecified response'
        category_counts[category] = category_counts.get(category, 0) + 1
        channel_counts[channel] = channel_counts.get(channel, 0) + 1
        response_counts[response_type] = response_counts.get(response_type, 0) + 1
        people.add(record_person(r))
        summary = normalized_record_summary(r)
        if summary:
            theme = f'{record_actor(r)} — {summary}'
            themes[theme] = themes.get(theme, 0) + 1
    lines = [f'**Closed entries summarized:** {len(records)} total across {len(people)} user(s).', f'- **Categories:** {top_counts_text(category_counts)}', f'- **Channels:** {top_counts_text(channel_counts)}', f'- **Response types:** {top_counts_text(response_counts)}']
    if themes:
        lines.append('- **Main themes:**')
        for theme, count in sorted(themes.items(), key=lambda kv: (-kv[1], kv[0]))[:5]:
            suffix = f' ({count} entries)' if count > 1 else ''
            lines.append(f'  - {theme}{suffix}')
    return lines

def summarize_request_highlights(records: list[dict[str, str]], category: str, label: str) -> list[str]:
    selected = [r for r in records if (r.get('category') or '').strip().lower() == category]
    if not selected:
        return [f'{label}: none']
    people: set[str] = set()
    status_counts: dict[str, int] = {}
    response_counts: dict[str, int] = {}
    themes: dict[str, int] = {}
    for r in selected:
        people.add(record_person(r))
        status = r.get('review_status') or 'unspecified status'
        response_type = r.get('assistant_response_type') or 'unspecified response'
        status_counts[status] = status_counts.get(status, 0) + 1
        response_counts[response_type] = response_counts.get(response_type, 0) + 1
        summary = normalized_record_summary(r)
        if summary:
            themes[summary] = themes.get(summary, 0) + 1
    lines = [f'**{label}:** {len(selected)} item(s) from {len(people)} user(s).', f'- **Status:** {top_counts_text(status_counts)}', f'- **Response types:** {top_counts_text(response_counts)}']
    if themes:
        lines.append('- **Highlights:**')
        for theme, count in sorted(themes.items(), key=lambda kv: (-kv[1], kv[0]))[:5]:
            suffix = f' ({count} entries)' if count > 1 else ''
            lines.append(f'  - {theme}{suffix}')
    return lines

def cmd_digest(args: argparse.Namespace) -> None:
    state = load_state()
    live_headers = review_log_headers()
    values = sheet_values(f'{SHEET_TAB}!A:{col_letter(len(live_headers))}')
    if not values:
        raise SystemExit('review_log is empty or unreadable')
    headers = values[0]
    rows = values[1:]
    current_count = len(values)
    now_dt = datetime.now(timezone.utc).replace(microsecond=0)
    now = now_dt.isoformat().replace('+00:00', 'Z')
    if args.repeat_last:
        start_dt = parse_utc_timestamp(str(state.get('lastWindowStartAtUtc') or ''))
        end_dt = parse_utc_timestamp(str(state.get('lastDigestAtUtc') or '')) or now_dt
    else:
        start_dt = parse_utc_timestamp(str(state.get('lastDigestAtUtc') or ''))
        end_dt = now_dt
    all_sheet_records = [{headers[i]: row[i] if i < len(row) else '' for i in range(len(headers))} for row in rows]
    all_records = records_in_time_window(all_sheet_records, start_utc=start_dt, end_utc=end_dt)
    if not all_records:
        print('NO_REPLY')
        return
    records = [r for r in all_records if not is_andy_record(r)]
    if not records:
        if not args.dry_run and (not args.repeat_last):
            state.update({'lastProcessedRow': current_count, 'lastWindowStartAtUtc': start_dt.isoformat().replace('+00:00', 'Z') if start_dt else '', 'lastDigestAtUtc': now, 'lastRunStatus': 'ok_filtered_andy_only', 'lastNewEntryCount': 0, 'lastFilteredAndyEntryCount': len(all_records)})
            save_state(state)
        print('NO_REPLY')
        return
    needs = [r for r in records if needs_follow_up_record(r)]
    closed = [r for r in records if is_closed_record(r)]
    non_closed = [r for r in records if not is_closed_record(r)]
    lines = ['## 📋 Mattermost review_log Digest', '', f'- **Window:** `{state.get('lastDigestAtUtc', 'previous digest')}` → `{now}` UTC', f'- **New entries:** **{len(records)}**', '- **Generation:** deterministic Python aggregation (no AI/summarizer agent used)']
    if needs:
        lines.append('')
        lines.append('### ⚠️ Needs Follow-up First')
        for r in needs:
            who = record_actor(r)
            lines.append(f'- `{r.get('timestamp_utc', '')}` — **{who}** — **{r.get('category', '')}**: {r.get('request_summary', '')} _[{r.get('assistant_response_type', '')}; {r.get('review_status', '')}]_')
    lines.append('')
    if closed:
        lines.append('### ✅ Closed-entry Synthesis')
        lines.extend(summarize_closed_records(closed))
        lines.append('')
    lines.append('### 💡 Feature Request Highlights')
    lines.extend(summarize_request_highlights(records, 'feature_request', 'Feature requests'))
    lines.append('')
    risky_categories = {'risky_request', 'privilege_request', 'blocked_tool_request', 'build_edit_scope_review'}
    risky_records = [r for r in records if (r.get('category') or '').strip().lower() in risky_categories]
    lines.append('### 🧭 Risky / Blocked Employee Capability Highlights')
    if risky_records:
        for r in risky_records[:8]:
            who = r.get('user_label') or r.get('user_id') or 'unknown user'
            channel = r.get('channel_name') or r.get('channel_id') or 'unknown channel'
            lines.append(f'- `{r.get('timestamp_utc', '')}` — **{r.get('category', '')}** — **{channel}** — **{who}**: {r.get('request_summary', '')}')
        if len(risky_records) > 8:
            lines.append(f'- …and {len(risky_records) - 8} more risky/blocked employee capability item(s).')
    else:
        lines.append('None')
    lines.append('')
    lines.append('### 🚧 Out-of-scope Request Highlights')
    lines.extend(summarize_request_highlights(records, 'out_of_scope', 'Out-of-scope requests'))
    lines.append('')
    if non_closed:
        lines.append('### 🔎 Open / Non-closed Entries')
    else:
        lines.append('### 🔎 Open / Non-closed Entries\nNone')
    for r in non_closed:
        who = record_actor(r)
        channel = r.get('channel_name') or r.get('channel_id') or 'unknown channel'
        lines.append(f'- `{r.get('timestamp_utc', '')}` — **{channel}** — **{who}**: {r.get('request_summary', '')}  ')
        lines.append(f'  - **Reason:** {r.get('reason', '')}')
    if not args.dry_run and (not args.repeat_last):
        state.update({'lastProcessedRow': current_count, 'lastWindowStartAtUtc': start_dt.isoformat().replace('+00:00', 'Z') if start_dt else '', 'lastDigestAtUtc': now, 'lastRunStatus': 'ok', 'lastNewEntryCount': len(records), 'lastFilteredAndyEntryCount': len(all_records) - len(records)})
        save_state(state)
    print('\n'.join(lines))

def cmd_ensure_review_log_headers(args: argparse.Namespace) -> None:
    print(json.dumps(ensure_review_log_headers(dry_run=args.dry_run), ensure_ascii=False, indent=2))

def cmd_ensure_quality_headers(args: argparse.Namespace) -> None:
    print(json.dumps(ensure_response_quality_headers(dry_run=args.dry_run), ensure_ascii=False, indent=2))

def cmd_backfill_response_quality(args: argparse.Namespace) -> None:
    if not args.no_ensure_headers:
        ensure_response_quality_headers(dry_run=args.dry_run)
    headers, rows = quality_backfill_rows(args.days, limit=args.limit, missing_only=not args.refresh_existing)
    commands, stats = plan_quality_backfill_updates(rows, headers, refresh_existing=args.refresh_existing)
    result: dict[str, Any] = {'days': args.days, 'apply': bool(args.apply), 'live_rows_in_window': len(rows), **stats, 'ranges': [range_a1 for range_a1, _values, _headers in commands]}
    if args.apply and commands:
        updates = []
        for range_a1, values, _changed_headers in commands:
            out = run([GOG_BIN(), 'sheets', 'update', SHEET_ID(), range_a1, '--values-json', json.dumps(values, ensure_ascii=False), '--input', 'USER_ENTERED', '--account', GOG_ACCOUNT(), '--json'])
            updates.append(json.loads(out))
        result['updates'] = updates
    print(json.dumps(result, ensure_ascii=False, indent=2))

def cmd_backfill_mattermost_user_post_links(args: argparse.Namespace) -> None:
    if not args.no_ensure_headers:
        ensure_review_log_headers(dry_run=args.dry_run)
    headers, rows = mattermost_user_post_link_backfill_rows(limit=args.limit)
    commands, stats = plan_mattermost_user_post_link_updates(rows, headers)
    result: dict[str, Any] = {'apply': bool(args.apply), 'live_rows_scanned': len(rows), **stats, 'ranges': [range_a1 for range_a1, _values, _headers in commands]}
    if args.apply and commands:
        updates = []
        for range_a1, values, _changed_headers in commands:
            out = run([GOG_BIN(), 'sheets', 'update', SHEET_ID(), range_a1, '--values-json', json.dumps(values, ensure_ascii=False), '--input', 'USER_ENTERED', '--account', GOG_ACCOUNT(), '--json'])
            updates.append(json.loads(out))
        result['updates'] = updates
    print(json.dumps(result, ensure_ascii=False, indent=2))

def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0

def build_parser():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    l = sub.add_parser('lookup-user')
    l.add_argument('user_id')
    l.set_defaults(func=cmd_lookup_user)
    a = sub.add_parser('append')
    a.add_argument('--user-id', required=True)
    a.add_argument('--channel-id', required=True)
    a.add_argument('--channel-name', default='')
    a.add_argument('--dm', action='store_true')
    a.add_argument('--timestamp-utc', default='')
    a.add_argument('--category', required=True)
    a.add_argument('--request-summary', required=True)
    a.add_argument('--assistant-response-type', required=True)
    a.add_argument('--reason', required=True)
    a.add_argument('--follow-up-needed', default='yes')
    a.add_argument('--review-status', default='open')
    a.add_argument('--notes', default='')
    a.add_argument('--data-sources', default='', help='Sources PD One searched/used to answer, e.g. Mattermost database; AppSheet ActivityLog')
    a.add_argument('--permission-blocked', default='', help='yes/no/partial plus concise reason when response was blocked by permissions')
    a.add_argument('--blocked-sources', default='', help='Sources PD One would have searched/used but did not due to permissions/scope')
    a.set_defaults(func=cmd_append)
    d = sub.add_parser('digest')
    d.add_argument('--dry-run', action='store_true')
    d.add_argument('--repeat-last', action='store_true', help='Re-render the most recent digest window without advancing state')
    d.set_defaults(func=cmd_digest)
    s = sub.add_parser('scan-dms')
    s.add_argument('--per-page', type=int, default=30)
    s.add_argument('--since-ms', type=int, default=None)
    s.add_argument('--dry-run', action='store_true')
    s.add_argument('--no-translate', action='store_true', help=argparse.SUPPRESS)
    s.add_argument('--translate', action='store_true', help=argparse.SUPPRESS)
    s.set_defaults(func=cmd_scan_dms)
    si = sub.add_parser('scan-interactions')
    si.add_argument('--per-page', type=int, default=60)
    si.add_argument('--since-ms', type=int, default=None)
    si.add_argument('--dry-run', action='store_true')
    si.add_argument('--no-translate', action='store_true', help=argparse.SUPPRESS)
    si.add_argument('--translate', action='store_true', help=argparse.SUPPRESS)
    si.set_defaults(func=cmd_scan_interactions)
    sa = sub.add_parser('scan-attachments')
    sa.add_argument('--per-page', type=int, default=60)
    sa.add_argument('--since-ms', type=int, default=None)
    sa.add_argument('--dry-run', action='store_true')
    sa.add_argument('--no-translate', action='store_true', help=argparse.SUPPRESS)
    sa.add_argument('--translate', action='store_true', help=argparse.SUPPRESS)
    sa.set_defaults(func=cmd_scan_attachments)
    eh = sub.add_parser('ensure-headers')
    eh.add_argument('--dry-run', action='store_true')
    eh.set_defaults(func=cmd_ensure_review_log_headers)
    qh = sub.add_parser('ensure-quality-headers')
    qh.add_argument('--dry-run', action='store_true')
    qh.set_defaults(func=cmd_ensure_quality_headers)
    qb = sub.add_parser('backfill-response-quality')
    qb.add_argument('--days', type=int, default=7)
    qb.add_argument('--limit', type=int, default=None)
    qb.add_argument('--apply', action='store_true')
    qb.add_argument('--dry-run', action='store_true')
    qb.add_argument('--refresh-existing', action='store_true')
    qb.add_argument('--no-ensure-headers', action='store_true')
    qb.set_defaults(func=cmd_backfill_response_quality)
    lb = sub.add_parser('backfill-mattermost-user-post-links')
    lb.add_argument('--limit', type=int, default=None)
    lb.add_argument('--apply', action='store_true')
    lb.add_argument('--dry-run', action='store_true')
    lb.add_argument('--no-ensure-headers', action='store_true')
    lb.set_defaults(func=cmd_backfill_mattermost_user_post_links)
    return ap
if __name__ == '__main__':
    main()

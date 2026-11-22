#!/usr/bin/env python3
"""Live Google Group member add/remove for PD One (PDAPP ticket or Andy Mattermost post)."""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

from tools.pd_one_ops.site_config import resolve_configured_path

def PROFILE_ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))

def TOOLS():
    return PROFILE_ROOT() / 'tools'

def LEDGER_TOOLS():
    return PROFILE_ROOT() / 'legacy-openclaw/workspace/tools'
ALLOWED_GROUP_DOMAIN = 'prodesign-group.com'
ALLOWED_ROLES = {'MEMBER', 'MANAGER'}
LIVE_CONFIRMATION = 'RUN LIVE GOOGLE GROUP MEMBER CHANGE'
TICKET_RE = re.compile('^PDAPP-\\d{8}-[A-F0-9]{8}$')
MATTERMOST_POST_ID_RE = re.compile('^[a-z0-9]{26}$')
MM_POST_PREFIX = 'mm-post:'
POST_MAX_AGE_MS = 24 * 60 * 60 * 1000
ALLOWED_MM_CHANNEL_IDS = frozenset({
    '5gmqtwqf7bde3cyihas79xi8ie',
    'fwkszerbtpgwdrrptqp7c3883a',
    'y5znzwc5oprrip3jje5iqpbyxr',
})
def _ensure_profile_tool_paths() -> None:
    for path in (str(TOOLS()), str(LEDGER_TOOLS())):
        if path not in sys.path:
            sys.path.append(path)

def fixed_account() -> str:
    _ensure_profile_tool_paths()
    from google_group_owner_ops import FIXED_ACCOUNT
    return FIXED_ACCOUNT

def fail(message: str, code: int=2) -> None:
    print(json.dumps({'status': 'error', 'error': message}, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(code)

def emit(payload: dict[str, Any]) -> None:
    from tools.pd_one_ops.hr_guard import guard_hr_payload
    payload = guard_hr_payload(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

def normalize_email(value: str) -> str:
    email = str(value or '').strip().lower()
    if not re.fullmatch('[^@\\s]+@[^@\\s]+\\.[^@\\s]+', email):
        fail(f'invalid email: {value!r}')
    return email

def andy_user_id() -> str:
    from tools.pd_one_ops.pd_one_safe_ops_part0 import DEFAULT_ANDY_USER_ID
    return str(DEFAULT_ANDY_USER_ID() or '').strip() or '5nak6m7nmf8kudbrwbtccazbgc'

def normalize_mm_post_id(value: str) -> str:
    text = str(value or '').strip()
    if text.startswith(MM_POST_PREFIX):
        text = text[len(MM_POST_PREFIX):]
    if not MATTERMOST_POST_ID_RE.fullmatch(text):
        fail(f'invalid Mattermost mm_post_id: {value!r}')
    return text

def resolve_post_auth_ref(*, ticket_id: str | None, mm_post_id: str | None) -> str:
    post_ref = str(mm_post_id or '').strip()
    if post_ref:
        return normalize_mm_post_id(post_ref)
    ticket_ref = str(ticket_id or '').strip()
    if ticket_ref.startswith(MM_POST_PREFIX):
        return normalize_mm_post_id(ticket_ref)
    return ''

def _default_post_fetcher(post_id: str) -> dict[str, Any]:
    from tools.pd_one_ops.pd_one_safe_ops_part1 import _mattermost_lookup_get, mattermost_context
    base, headers, _me = mattermost_context()
    receipt, post = _mattermost_lookup_get(base, headers, f'/api/v4/posts/{post_id}')
    if receipt.get('status') != 200 or not post:
        fail(f'Mattermost post {post_id} could not be re-fetched for authorization')
    return post

def _authorization_message_text(post: dict[str, Any], post_fetcher: Callable[[str], dict[str, Any]]) -> str:
    parts = [str(post.get('message') or '')]
    root_id = str(post.get('root_id') or '').strip()
    post_id = str(post.get('id') or '').strip()
    if root_id and root_id != post_id:
        root = post_fetcher(root_id)
        if not isinstance(root, dict):
            fail(f'thread root post {root_id} could not be re-fetched for authorization')
        parts.insert(0, str(root.get('message') or ''))
    return '\n'.join(parts)

def post_names_member_and_group(message_text: str, *, group: str, member: str) -> bool:
    haystack = message_text.casefold()
    return group.casefold() in haystack and member.casefold() in haystack

def authorize_andy_mm_post(
    *,
    mm_post_id: str,
    action: str,
    group: str,
    member: str,
    role: str,
    post_fetcher: Callable[[str], dict[str, Any]] | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    post_id = normalize_mm_post_id(mm_post_id)
    fetch = post_fetcher or _default_post_fetcher
    post = fetch(post_id)
    if not isinstance(post, dict):
        fail(f'Mattermost post {post_id} could not be re-fetched for authorization')
    andy_id = andy_user_id()
    if str(post.get('user_id') or '') != andy_id:
        fail("Mattermost post sender is not Andy; caller-supplied sender ids are not trusted")
    if int(post.get('delete_at') or 0):
        fail(f'Mattermost post {post_id} is deleted')
    channel_id = str(post.get('channel_id') or '')
    if channel_id not in ALLOWED_MM_CHANNEL_IDS:
        fail(f'Mattermost post channel {channel_id} is not an allowed authorization room')
    created_ms = int(post.get('create_at') or 0)
    current_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    if created_ms <= 0 or current_ms - created_ms > POST_MAX_AGE_MS:
        fail(f'Mattermost post {post_id} must be 24 hours old or newer')
    bound_text = _authorization_message_text(post, fetch)
    if not post_names_member_and_group(bound_text, group=group, member=member):
        fail('Mattermost authorization post and thread root must name the exact group and member emails')
    _ = (role, action)
    return {
        'authorization': 'andy_mattermost_post',
        'mm_post_id': post_id,
        'channel_id': channel_id,
        'requester_user_id': andy_id,
        'message_excerpt': bound_text[:240],
    }

def authorize_ticket(ticket_id: str, action: str, group: str, member: str, role: str) -> dict[str, Any]:
    if not TICKET_RE.fullmatch(ticket_id):
        fail('ticket_id must look like PDAPP-YYYYMMDD-XXXXXXXX')
    _ensure_profile_tool_paths()
    from admin_approval_tickets import ApprovalLedger
    token = 'google_group_member_add' if action == 'add-member' else 'google_group_member_remove'
    ledger = ApprovalLedger()
    ticket = ledger.get(ticket_id)
    grant = ticket.get('approval_grant') or {}
    caps = set(grant.get('allowed_capabilities') or [])
    scope = ticket.get('capability_scope') or {}
    if ticket.get('status') not in {'approved', 'queued', 'in_progress'}:
        fail(f"ticket {ticket_id} is not executable: {ticket.get('status')}")
    if grant.get('status') != 'active' or token not in caps:
        fail(f'ticket {ticket_id} grant does not include {token}')
    if scope.get('permission_changes_allowed') is not True:
        fail(f'ticket {ticket_id} does not authorize permission changes')
    bound = ' '.join([json.dumps(ticket.get('implementation_plan') or {}, ensure_ascii=False), str(ticket.get('requested_action') or ''), json.dumps(ticket.get('bound_resources') or [], ensure_ascii=False)]).lower()
    if group not in bound or member not in bound:
        fail('ticket bound scope does not include the exact group and member')
    if role not in bound.upper() and role != 'MEMBER':
        fail('ticket bound scope does not include the requested role')
    return ticket

def apply_member_change(
    *,
    action: str,
    group: str,
    member: str,
    role: str,
    dry_run: bool,
    ticket_id: str | None = None,
    mm_post_id: str | None = None,
    confirm_live_write: str | None = None,
    client: Any | None = None,
    post_fetcher: Callable[[str], dict[str, Any]] | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    group = normalize_email(group)
    member = normalize_email(member)
    role = str(role or 'MEMBER').upper()
    if action not in {'add-member', 'remove-member'}:
        fail(f'unsupported live action: {action}')
    if not group.endswith('@' + ALLOWED_GROUP_DOMAIN):
        fail(f'live changes are limited to @{ALLOWED_GROUP_DOMAIN} groups')
    if role not in ALLOWED_ROLES:
        fail('live role must be MEMBER or MANAGER')
    receipt: dict[str, Any] = {
        'status': 'ok',
        'capability': 'pd_one_google_group_change_dry_run' if dry_run else 'pd_one_google_group_change_apply_approved',
        'mode': 'dry-run' if dry_run else 'live',
        'action': action,
        'group': group,
        'member': member,
        'role': role,
        'account': fixed_account(),
        'readback_required': True,
        'safety': {
            'permission_changes_require_approval': True,
            'pdapp_ticket_or_andy_mattermost_post': True,
            'owner_role_forbidden': True,
            'create_group_forbidden': True,
            'credentials_returned': False,
        },
    }
    if dry_run:
        receipt['would_apply'] = True
        return receipt
    if confirm_live_write != LIVE_CONFIRMATION:
        fail(f'live apply requires --confirm-live-write {LIVE_CONFIRMATION!r}')
    post_auth_id = resolve_post_auth_ref(ticket_id=ticket_id, mm_post_id=mm_post_id)
    ticket_ref = str(ticket_id or '').strip()
    authorization: dict[str, Any] | None = None
    if post_auth_id:
        authorization = authorize_andy_mm_post(
            mm_post_id=post_auth_id,
            action=action,
            group=group,
            member=member,
            role=role,
            post_fetcher=post_fetcher,
            now_ms=now_ms,
        )
    elif ticket_ref:
        authorization = {'authorization': 'pdapp_ticket', 'ticket': authorize_ticket(ticket_ref, action, group, member, role)}
    else:
        fail('live Google group changes require --ticket-id or --mm-post-id')
    owned_client = client is None
    if client is None:
        _ensure_profile_tool_paths()
        from google_group_owner_ops import DirectoryApiClient, find_gog, load_gog_access_token, refresh_gog_admin_token
        gog = find_gog()
        refresh_gog_admin_token(gog)
        token = load_gog_access_token(gog, fixed_account())
        client = DirectoryApiClient(token)
    try:
        if not hasattr(client, 'add_member'):

            def add_member(group_email: str, member_email: str, member_role: str='MEMBER') -> None:
                client._request('POST', f'/groups/{client._quote(group_email)}/members', {'email': member_email, 'role': member_role})
            client.add_member = add_member
        before = client.get_role(group, member)
        changed = False
        if action == 'add-member':
            if before is None:
                client.add_member(group, member, role)
                changed = True
            elif before != role:
                client._request('PATCH', f'/groups/{client._quote(group)}/members/{client._quote(member)}', {'role': role})
                changed = True
        elif before is not None:
            client.delete_member(group, member)
            changed = True
        after = client.get_role(group, member)
        receipt.update({
            'before_role': before,
            'after_role': after,
            'changed': changed,
            'authorization': authorization,
        })
        if post_auth_id:
            receipt['mm_post_id'] = post_auth_id
            receipt['ticket_id'] = None
        else:
            receipt['ticket_id'] = ticket_ref
            receipt['mm_post_id'] = None
        if action == 'add-member' and after != role:
            fail(f'readback failed: expected {role}, got {after}')
        if action == 'remove-member' and after is not None:
            fail(f'readback failed: member still present as {after}')
        return receipt
    finally:
        if owned_client and hasattr(client, 'close'):
            client.close()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', required=True)
    parser.add_argument('--action', required=True, choices=['add-member', 'remove-member'])
    parser.add_argument('--member', required=True)
    parser.add_argument('--role', default='MEMBER')
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--live', dest='dry_run', action='store_false')
    parser.add_argument('--ticket-id')
    parser.add_argument('--mm-post-id')
    parser.add_argument('--confirm-live-write')
    return parser

def main(argv: list[str] | None=None) -> int:
    args = build_parser().parse_args(argv)
    emit(apply_member_change(
        action=args.action,
        group=args.group,
        member=args.member,
        role=args.role,
        dry_run=args.dry_run,
        ticket_id=args.ticket_id,
        mm_post_id=args.mm_post_id,
        confirm_live_write=args.confirm_live_write,
    ))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
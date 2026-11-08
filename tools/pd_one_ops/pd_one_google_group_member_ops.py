#!/usr/bin/env python3
"""Ticket-bound live Google Group member add/remove for PD One."""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import os
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

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
for path in (str(TOOLS()), str(LEDGER_TOOLS())):
    if path not in sys.path:
        sys.path.append(path)
from admin_approval_tickets import ApprovalLedger
from google_group_owner_ops import DirectoryApiClient, FIXED_ACCOUNT, find_gog, load_gog_access_token, refresh_gog_admin_token

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

def authorize_ticket(ticket_id: str, action: str, group: str, member: str, role: str) -> dict[str, Any]:
    if not TICKET_RE.fullmatch(ticket_id):
        fail('ticket_id must look like PDAPP-YYYYMMDD-XXXXXXXX')
    token = 'google_group_member_add' if action == 'add-member' else 'google_group_member_remove'
    ledger = ApprovalLedger()
    ticket = ledger.get(ticket_id)
    grant = ticket.get('approval_grant') or {}
    caps = set(grant.get('allowed_capabilities') or [])
    scope = ticket.get('capability_scope') or {}
    if ticket.get('status') not in {'approved', 'queued', 'in_progress'}:
        fail(f'ticket {ticket_id} is not executable: {ticket.get('status')}')
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

def apply_member_change(*, action: str, group: str, member: str, role: str, dry_run: bool, ticket_id: str | None, confirm_live_write: str | None=None, client: Any | None=None) -> dict[str, Any]:
    group = normalize_email(group)
    member = normalize_email(member)
    role = str(role or 'MEMBER').upper()
    if action not in {'add-member', 'remove-member'}:
        fail(f'unsupported live action: {action}')
    if not group.endswith('@' + ALLOWED_GROUP_DOMAIN):
        fail(f'live changes are limited to @{ALLOWED_GROUP_DOMAIN} groups')
    if role not in ALLOWED_ROLES:
        fail('live role must be MEMBER or MANAGER')
    receipt: dict[str, Any] = {'status': 'ok', 'capability': 'pd_one_google_group_change_dry_run' if dry_run else 'pd_one_google_group_change_apply_approved', 'mode': 'dry-run' if dry_run else 'live', 'action': action, 'group': group, 'member': member, 'role': role, 'account': FIXED_ACCOUNT, 'readback_required': True, 'safety': {'permission_changes_require_ticket': True, 'owner_role_forbidden': True, 'create_group_forbidden': True, 'credentials_returned': False}}
    if dry_run:
        receipt['would_apply'] = True
        return receipt
    if confirm_live_write != LIVE_CONFIRMATION:
        fail(f'live apply requires --confirm-live-write {LIVE_CONFIRMATION!r}')
    if not ticket_id:
        fail('live Google group changes require --ticket-id')
    authorize_ticket(ticket_id, action, group, member, role)
    owned_client = client is None
    if client is None:
        gog = find_gog()
        refresh_gog_admin_token(gog)
        token = load_gog_access_token(gog, FIXED_ACCOUNT)
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
        receipt.update({'before_role': before, 'after_role': after, 'changed': changed, 'ticket_id': ticket_id})
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
    parser.add_argument('--confirm-live-write')
    return parser

def main(argv: list[str] | None=None) -> int:
    args = build_parser().parse_args(argv)
    emit(apply_member_change(action=args.action, group=args.group, member=args.member, role=args.role, dry_run=args.dry_run, ticket_id=args.ticket_id, confirm_live_write=args.confirm_live_write))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Bounded Google Groups owner enforcement for Pro-Design administration."""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import argparse
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
ALLOWED_DOMAIN = 'prodesign-group.com'

def ALLOWED_OWNER_EMAILS():
    return (site_text('PDONE_EMAIL_ANDYLIN_GMAIL'), site_text('PDONE_EMAIL_PRO_DESIGN_GROUP_TW_GMAIL'))
MAX_GROUPS = 100
LIVE_CONFIRMATION = 'RUN LIVE GOOGLE GROUP OWNER ENFORCEMENT'
ADMIN_REMOVAL_LIVE_CONFIRMATION = 'RUN LIVE GOOGLE GROUP ADMIN REMOVAL EXCEPT IT'

def FIXED_ACCOUNT():
    return site_text('PDONE_EMAIL_ADMIN')

def PRESERVED_IT_GROUP():
    return site_text('PDONE_EMAIL_IT')
DIRECTORY_API_BASE = 'https://admin.googleapis.com/admin/directory/v1'

def GOG_CANDIDATES():
    return (Path(resolve_configured_path('~/.hermes/profiles/pdone/home/.local/bin/gog')), Path(resolve_configured_path('~/.local/bin/gog')))

def APPROVAL_MODULE_PATH():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/tools/admin_approval_tickets.py'))

def APPROVAL_LEDGER_PATH():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/state/admin-approval-tickets.jsonl'))

def TRUSTED_ANDY_USER_ID():
    return site_text('PDONE_OWNER_MM_USER_ID')
REQUIRED_APPROVAL_CAPABILITY = 'google_group_owner_enforcement'

class ApprovalLease:

    def __init__(self, ledger: Any, ticket_id: str):
        self.ledger = ledger
        self.ticket_id = ticket_id
        self.finished = False

    def complete(self, receipt: dict[str, Any]) -> None:
        if self.finished:
            return
        self.ledger.complete(self.ticket_id, employee_visible_summary='Google Groups owner enforcement completed and verified.', admin_private_details=f'groups_scanned={receipt.get('groups_scanned', 0)}; verified_owner_slots={receipt.get('verified_owner_slots', 0)}; actions_failed={receipt.get('actions_failed', 0)}')
        self.finished = True

    def fail(self, reason: str) -> None:
        if self.finished:
            return
        self.ledger.fail(self.ticket_id, reason=str(reason)[:1000])
        self.finished = True

def _load_approval_module() -> Any:
    spec = importlib.util.spec_from_file_location('pdone_google_group_approval_tickets', APPROVAL_MODULE_PATH())
    if spec is None or spec.loader is None:
        raise RuntimeError('unable to load the approval-ticket module')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def authorize_live_approval_ticket(ticket_id: str, *, ledger: Any=None, approval_module: Any=None) -> ApprovalLease:
    ticket_id = str(ticket_id or '').strip().upper()
    if not re.fullmatch('PDAPP-\\d{8}-[A-F0-9]{8}', ticket_id):
        raise ValueError('live owner enforcement requires a valid approval_ticket_id')
    approval_module = approval_module or _load_approval_module()
    ledger = ledger or approval_module.ApprovalLedger(APPROVAL_LEDGER_PATH())
    ticket = ledger.get(ticket_id)
    if ticket.get('status') != 'approved':
        raise ValueError('approval ticket must be in approved status and unused')
    if not ticket.get('action_binding') or ticket['action_binding'] != approval_module.compute_action_binding(ticket):
        raise ValueError('approval ticket action binding is missing or stale')
    decision = ticket.get('andy_decision') or {}
    if decision.get('decision') != 'approved' or decision.get('user_id') != TRUSTED_ANDY_USER_ID():
        raise ValueError('approval ticket is not bound to the trusted Owner administrator')
    if REQUIRED_APPROVAL_CAPABILITY not in set(ticket.get('required_capabilities') or []):
        raise ValueError('approval ticket does not authorize Google Groups owner enforcement')
    scope = ticket.get('capability_scope') or {}
    if scope.get('permission_changes_allowed') is not True:
        raise ValueError('approval ticket does not authorize permission changes')
    plan = ticket.get('implementation_plan') or {}
    if plan.get('capability') != 'pd_one_google_group_owner_enforcement':
        raise ValueError('approval ticket is bound to a different capability')
    if plan.get('domain') != ALLOWED_DOMAIN:
        raise ValueError('approval ticket is bound to a different domain')
    if sorted(plan.get('owner_allowlist') or []) != sorted(ALLOWED_OWNER_EMAILS()):
        raise ValueError('approval ticket is bound to a different owner allowlist')
    ledger.enqueue(ticket_id, idempotency_key=f'google-group-owner-enforcement:{ticket_id}')
    ledger.claim(ticket_id, worker_id='pd-one-google-group-owner-enforcement', lease_seconds=600)
    return ApprovalLease(ledger, ticket_id)

def find_gog() -> str:
    for path in GOG_CANDIDATES():
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise RuntimeError('approved gog binary not found')

def refresh_gog_admin_token(gog: str, *, runner: Any=subprocess.run) -> None:
    command = [str(gog), 'admin', 'groups', 'list', '--domain', ALLOWED_DOMAIN, '--max', '1', '--json', '--no-input', '--account', FIXED_ACCOUNT()]
    proc = runner(command, text=True, capture_output=True, shell=False, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f'gog Admin SDK refresh failed with exit {proc.returncode}')

def load_gog_access_token(gog: str, account: str, *, runner: Any=subprocess.run) -> str:
    if account != FIXED_ACCOUNT():
        raise ValueError(f'account must be fixed to {FIXED_ACCOUNT()}')
    with tempfile.TemporaryDirectory(prefix='pdone-google-groups-') as temp_dir:
        os.chmod(temp_dir, 448)
        token_path = Path(temp_dir) / 'token.json'
        command = [str(gog), 'auth', 'tokens', 'export', account, '--out', str(token_path), '--overwrite', '--no-input']
        proc = runner(command, text=True, capture_output=True, shell=False, timeout=30)
        if proc.returncode != 0:
            raise RuntimeError(f'gog token bridge failed with exit {proc.returncode}')
        try:
            payload = json.loads(token_path.read_text(encoding='utf-8'))
            token = str(payload.get('access_token') or '')
            if not token:
                raise RuntimeError('gog token bridge returned no short-lived access token')
            return token
        finally:
            token_path.unlink(missing_ok=True)

class DirectoryApiClient:

    def __init__(self, access_token: str, *, timeout: int=45, retries: int=4):
        if not access_token:
            raise ValueError('a short-lived access token is required')
        self._access_token = access_token
        self.timeout = max(5, min(int(timeout), 120))
        self.retries = max(1, min(int(retries), 5))

    @staticmethod
    def _quote(value: str) -> str:
        return urllib.parse.quote(value, safe='')

    def close(self) -> None:
        self._access_token = ''

    def _request(self, method: str, path: str, body: dict[str, Any] | None=None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode('utf-8')
        headers = {'Authorization': f'Bearer {self._access_token}', 'Accept': 'application/json'}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        for attempt in range(self.retries):
            request = urllib.request.Request(DIRECTORY_API_BASE + path, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise KeyError('directory member not found') from None
                if exc.code in {429, 500, 502, 503, 504} and attempt + 1 < self.retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise RuntimeError(f'Directory API {method} failed with HTTP {exc.code}') from None
        raise RuntimeError(f'Directory API {method} exhausted retries')

    def list_groups(self, domain: str) -> list[str]:
        if domain != ALLOWED_DOMAIN:
            raise ValueError(f'domain must be fixed to {ALLOWED_DOMAIN}')
        groups: list[str] = []
        page_token = ''
        while True:
            path = f'/groups?domain={self._quote(domain)}&maxResults={MAX_GROUPS}'
            if page_token:
                path += '&pageToken=' + self._quote(page_token)
            payload = self._request('GET', path)
            page_groups = [str(row.get('email') or '').strip().lower() for row in payload.get('groups', [])]
            if len(groups) + len(page_groups) > MAX_GROUPS:
                raise ValueError(f'group inventory must contain at most {MAX_GROUPS} groups')
            groups.extend(page_groups)
            page_token = str(payload.get('nextPageToken') or '')
            if page_token and len(groups) >= MAX_GROUPS:
                raise ValueError(f'group inventory must contain at most {MAX_GROUPS} groups')
            if not page_token:
                break
        return validate_groups(groups)

    def get_role(self, group: str, member: str) -> str | None:
        try:
            payload = self._request('GET', f'/groups/{self._quote(group)}/members/{self._quote(member)}')
        except KeyError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            return None
        role = str(payload.get('role') or '').upper()
        return role or None

    def add_owner(self, group: str, member: str) -> None:
        self.add_member(group, member, 'OWNER')

    def add_member(self, group: str, member: str, role: str='MEMBER') -> None:
        self._request('POST', f'/groups/{self._quote(group)}/members', {'email': member, 'role': role})

    def promote_owner(self, group: str, member: str) -> None:
        self._request('PATCH', f'/groups/{self._quote(group)}/members/{self._quote(member)}', {'role': 'OWNER'})

    def delete_member(self, group: str, member: str) -> None:
        self._request('DELETE', f'/groups/{self._quote(group)}/members/{self._quote(member)}')

def validate_groups(groups: list[str]) -> list[str]:
    normalized = sorted({str(group).strip().lower() for group in groups if str(group).strip()})
    if len(normalized) > MAX_GROUPS:
        raise ValueError(f'group inventory must contain at most {MAX_GROUPS} groups')
    suffix = '@' + ALLOWED_DOMAIN
    foreign = [group for group in normalized if not group.endswith(suffix)]
    if foreign:
        raise ValueError(f'groups must belong to the approved domain {ALLOWED_DOMAIN}: {foreign}')
    return normalized

def build_owner_plan(groups: list[str], current_roles: dict[tuple[str, str], str | None]) -> list[dict[str, Any]]:
    """Build an idempotent add/promote/no-op plan for the fixed owner allowlist."""
    plan: list[dict[str, Any]] = []
    for group in groups:
        for member in ALLOWED_OWNER_EMAILS():
            role = current_roles.get((group, member))
            action = 'none' if role == 'OWNER' else 'add' if role is None else 'promote'
            plan.append({'group': group, 'member': member, 'before': role, 'action': action, 'after': 'OWNER'})
    return plan

def execute_owner_enforcement(client: Any, *, dry_run: bool=True, confirm_live_write: str | None=None, approval_ticket_id: str | None=None, approval_gate: Any=authorize_live_approval_ticket) -> dict[str, Any]:
    lease = None
    if not dry_run:
        if confirm_live_write != LIVE_CONFIRMATION:
            raise ValueError(f'live owner enforcement requires confirm_live_write={LIVE_CONFIRMATION!r}')
        if not approval_ticket_id:
            raise ValueError('live owner enforcement requires approval_ticket_id')
        lease = approval_gate(approval_ticket_id)
    try:
        groups = validate_groups(client.list_groups(ALLOWED_DOMAIN))
        current = {(group, member): client.get_role(group, member) for group in groups for member in ALLOWED_OWNER_EMAILS()}
        plan = build_owner_plan(groups, current)
        changes = [row for row in plan if row['action'] != 'none']
        action_results: list[dict[str, Any]] = []
        verification: list[dict[str, Any]] = []
        if not dry_run:
            for row in changes:
                try:
                    if row['action'] == 'add':
                        client.add_owner(row['group'], row['member'])
                    else:
                        client.promote_owner(row['group'], row['member'])
                    role = client.get_role(row['group'], row['member'])
                    action_results.append({**row, 'ok': role == 'OWNER', 'readback_role': role})
                except Exception as exc:
                    logging.getLogger('pd_one_ops').exception('pd one command failed')
                    action_results.append({**row, 'ok': False, 'error': str(exc)[:500]})
            for row in plan:
                try:
                    role = client.get_role(row['group'], row['member'])
                    verification.append({'group': row['group'], 'member': row['member'], 'role': role, 'ok': role == 'OWNER'})
                except Exception as exc:
                    logging.getLogger('pd_one_ops').exception('pd one command failed')
                    verification.append({'group': row['group'], 'member': row['member'], 'role': None, 'ok': False, 'error': str(exc)[:500]})
        action_failures = [row for row in action_results if not row['ok']]
        verification_failures = [row for row in verification if not row['ok']]
        receipt = {'status': 'error' if action_failures or verification_failures else 'ok', 'capability': 'pd_one_google_group_owner_enforcement', 'mode': 'dry-run' if dry_run else 'live', 'approval_ticket_id': approval_ticket_id if not dry_run else None, 'domain': ALLOWED_DOMAIN, 'owner_allowlist': list(ALLOWED_OWNER_EMAILS()), 'groups_scanned': len(groups), 'target_slots': len(plan), 'already_owner': len(plan) - len(changes), 'planned_changes': len(changes), 'adds': sum((row['action'] == 'add' for row in changes)), 'promotions': sum((row['action'] == 'promote' for row in changes)), 'actions_succeeded': len(action_results) - len(action_failures), 'actions_failed': len(action_failures), 'verified_owner_slots': sum((row['ok'] for row in verification)), 'verification_failures': len(verification_failures), 'plan': plan, 'action_failures': action_failures, 'verification_failure_details': verification_failures, 'safety': {'dry_run_default': True, 'live_requires_bound_approval_ticket': True, 'remove_or_demote_supported': False, 'arbitrary_members_supported': False, 'arbitrary_domains_supported': False, 'credentials_returned': False}}
        if lease is not None:
            if receipt['status'] == 'ok':
                lease.complete(receipt)
            else:
                lease.fail('owner enforcement or verification returned failures')
        return receipt
    except Exception as exc:
        if lease is not None:
            lease.fail(str(exc))
        raise

def execute_admin_removal_except_it(client: Any, *, dry_run: bool=True, confirm_live_write: str | None=None) -> dict[str, Any]:
    """Remove the fixed admin account from every accessible group except IT.

    The operation refuses any live removal unless both continuity accounts are
    already OWNER in every group from which the admin account would be removed.
    """
    if not dry_run and confirm_live_write != ADMIN_REMOVAL_LIVE_CONFIRMATION:
        raise ValueError(f'live admin removal requires confirm_live_write={ADMIN_REMOVAL_LIVE_CONFIRMATION!r}')
    groups = validate_groups(client.list_groups(ALLOWED_DOMAIN))
    if PRESERVED_IT_GROUP() not in groups:
        raise ValueError(f'preserved IT group is not accessible: {PRESERVED_IT_GROUP()}')
    admin_roles = {group: client.get_role(group, FIXED_ACCOUNT()) for group in groups}
    plan = []
    for group in groups:
        role = admin_roles[group]
        action = 'preserve' if group == PRESERVED_IT_GROUP() else 'none' if role is None else 'remove'
        plan.append({'group': group, 'member': FIXED_ACCOUNT(), 'before': role, 'action': action, 'after': role if group == PRESERVED_IT_GROUP() else None})
    removals = [row for row in plan if row['action'] == 'remove']
    continuity_failures = []
    for row in removals:
        roles = {member: client.get_role(row['group'], member) for member in ALLOWED_OWNER_EMAILS()}
        if any((role != 'OWNER' for role in roles.values())):
            continuity_failures.append({'group': row['group'], 'roles': roles})
    if not dry_run and continuity_failures:
        raise ValueError('refusing admin removal because both continuity owners are not OWNER in: ' + ', '.join((row['group'] for row in continuity_failures)))
    action_results: list[dict[str, Any]] = []
    if not dry_run:
        for row in removals:
            try:
                client.delete_member(row['group'], FIXED_ACCOUNT())
                role = client.get_role(row['group'], FIXED_ACCOUNT())
                action_results.append({**row, 'ok': role is None, 'readback_role': role})
            except Exception as exc:
                logging.getLogger('pd_one_ops').exception('pd one command failed')
                action_results.append({**row, 'ok': False, 'error': str(exc)[:500]})
    verification = []
    if not dry_run:
        for row in plan:
            try:
                role = client.get_role(row['group'], FIXED_ACCOUNT())
                expected = admin_roles[row['group']] if row['group'] == PRESERVED_IT_GROUP() else None
                verification.append({'group': row['group'], 'role': role, 'expected': expected, 'ok': role == expected})
            except Exception as exc:
                logging.getLogger('pd_one_ops').exception('pd one command failed')
                verification.append({'group': row['group'], 'role': None, 'expected': admin_roles[row['group']] if row['group'] == PRESERVED_IT_GROUP() else None, 'ok': False, 'error': str(exc)[:500]})
    action_failures = [row for row in action_results if not row['ok']]
    verification_failures = [row for row in verification if not row['ok']]
    remaining = sorted((row['group'] for row in verification if row['role'] is not None)) if not dry_run else sorted((group for group, role in admin_roles.items() if role is not None))
    return {'status': 'blocked' if continuity_failures else 'error' if action_failures or verification_failures else 'ok', 'capability': 'pd_one_google_group_admin_removal_except_it', 'mode': 'dry-run' if dry_run else 'live', 'domain': ALLOWED_DOMAIN, 'admin_account': FIXED_ACCOUNT(), 'preserved_it_group': PRESERVED_IT_GROUP(), 'continuity_owners': list(ALLOWED_OWNER_EMAILS()), 'groups_scanned': len(groups), 'planned_removals': len(removals), 'already_absent': sum((row['action'] == 'none' for row in plan)), 'actions_succeeded': len(action_results) - len(action_failures), 'actions_failed': len(action_failures), 'verification_failures': len(verification_failures), 'admin_memberships_remaining': remaining, 'continuity_failures': continuity_failures, 'plan': plan, 'action_failures': action_failures, 'verification_failure_details': verification_failures, 'safety': {'dry_run_default': True, 'fixed_admin_only': True, 'fixed_it_exception_only': True, 'requires_two_verified_continuity_owners': True, 'arbitrary_removals_supported': False, 'credentials_returned': False}}

def run_admin_removal_except_it(*, dry_run: bool=True, confirm_live_write: str | None=None, token_loader: Any=load_gog_access_token, client_factory: Any=DirectoryApiClient, refresh_token: bool=True) -> dict[str, Any]:
    gog = find_gog()
    if refresh_token:
        refresh_gog_admin_token(gog)
    token_holder = [token_loader(gog, FIXED_ACCOUNT())]
    client = None
    try:
        client = client_factory(token_holder[0])
        return execute_admin_removal_except_it(client, dry_run=dry_run, confirm_live_write=confirm_live_write)
    finally:
        if client is not None:
            client.close()
        token_holder[0] = ''

def run_owner_enforcement(*, dry_run: bool=True, confirm_live_write: str | None=None, approval_ticket_id: str | None=None, token_loader: Any=load_gog_access_token, client_factory: Any=DirectoryApiClient, refresh_token: bool=True, approval_gate: Any=authorize_live_approval_ticket) -> dict[str, Any]:
    lease = None
    if not dry_run:
        if confirm_live_write != LIVE_CONFIRMATION:
            raise ValueError(f'live owner enforcement requires confirm_live_write={LIVE_CONFIRMATION!r}')
        if not approval_ticket_id:
            raise ValueError('live owner enforcement requires approval_ticket_id')
        lease = approval_gate(approval_ticket_id)
    gog = find_gog()
    if refresh_token:
        refresh_gog_admin_token(gog)
    token_holder = [token_loader(gog, FIXED_ACCOUNT())]
    client = None
    try:
        client = client_factory(token_holder[0])
        return execute_owner_enforcement(client, dry_run=dry_run, confirm_live_write=confirm_live_write, approval_ticket_id=approval_ticket_id, approval_gate=(lambda _ticket_id: lease) if lease is not None else approval_gate)
    except Exception as exc:
        if lease is not None:
            lease.fail(str(exc))
        raise
    finally:
        if client is not None:
            client.close()
        token_holder[0] = ''

def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

def build_parser():
    parser = argparse.ArgumentParser(description='Run fixed-scope Pro-Design Google Groups continuity operations')
    parser.add_argument('--operation', choices=('ensure-owners', 'remove-admin-except-it'), default='ensure-owners')
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--live', dest='dry_run', action='store_false')
    parser.add_argument('--confirm-live-write')
    parser.add_argument('--approval-ticket-id')
    return parser

#!/usr/bin/env python3
"""Authorize a Mattermost user against live Drive ACLs + cached identities/groups.

Never creates Drive permissions. Never prints email addresses in default output.
"""
from __future__ import annotations

class _PdReturn:
    __slots__ = ('value',)

    def __init__(self, value):
        self.value = value

class _PdHandled:
    pass

class _PdUnset:

    def __bool__(self):
        raise UnboundLocalError('pd one local used before assignment')

    def __repr__(self):
        raise UnboundLocalError('pd one local used before assignment')
_PdUnset = _PdUnset()
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
from tools.pd_one_ops.launch import checked_argv
import os
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.append(str(TOOLS))
from drive_acl_common import ACCESS_RANK, SENSITIVE_RE, access_for_role, expanded_members, load_group_v1_cache, load_identity_cache, normalize_drive_role, normalize_email, redact_emails, requester_emails, strongest_access, validate_group_v1_cache, validate_identity_cache

def GOG():
    return resolve_configured_path('~/.local/bin/gog')

def DEFAULT_ACCOUNT():
    return site_text('PDONE_EMAIL_ADMIN')

class AuthDenied(Exception):

    def __init__(self, reason: str, extra: dict[str, Any] | None=None):
        super().__init__(reason)
        self.reason = reason
        self.extra = extra or {}

def deny_payload(reason: str, **extra: Any) -> dict[str, Any]:
    payload = {'status': 'denied', 'canRead': False, 'canComment': False, 'canWrite': False, 'via': 'none', 'groupEmail': None, 'role': 'none', 'access': 'none', 'permissionsCreateAttempted': False, 'reason': reason}
    payload.update(extra)
    return payload

def fetch_permissions(file_id: str, account: str, *, runner: Any=subprocess.run) -> list[dict[str, Any]]:
    command = checked_argv([GOG(), 'drive', 'permissions', file_id, '--account', account, '--json', '--no-input'])
    proc = runner(command, text=True, capture_output=True, timeout=120, check=False)
    if proc.returncode != 0:
        raise RuntimeError('drive permissions lookup failed')
    try:
        data = json.loads(proc.stdout or '{}')
    except json.JSONDecodeError as exc:
        raise RuntimeError('drive permissions lookup returned invalid JSON') from exc
    return [row for row in data.get('permissions', []) if isinstance(row, dict)]

def fetch_file_name(file_id: str, account: str, *, runner: Any=subprocess.run) -> str:
    command = checked_argv([GOG(), 'drive', 'get', file_id, '--account', account, '--json', '--no-input'])
    proc = runner(command, text=True, capture_output=True, timeout=60, check=False)
    if proc.returncode != 0:
        return ''
    try:
        data = json.loads(proc.stdout or '{}')
    except json.JSONDecodeError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return ''
    file_rec = data.get('file') if isinstance(data.get('file'), dict) else data
    if not isinstance(file_rec, dict):
        return ''
    return str(file_rec.get('name') or file_rec.get('title') or '')

def resolve_identity(*, identity_cache: dict[str, Any], mattermost_user_id: str='', mattermost_username: str='') -> dict[str, Any]:
    users = identity_cache.get('users') or {}
    user_id = str(mattermost_user_id or '').strip()
    if user_id:
        rec = users.get(user_id)
        if isinstance(rec, dict):
            return rec
        raise AuthDenied('unknown_mattermost_user')
    username = str(mattermost_username or '').strip()
    if not username:
        raise AuthDenied('missing_mattermost_identity')
    matches = [rec for rec in users.values() if isinstance(rec, dict) and str(rec.get('mattermostUsername') or '') == username]
    if len(matches) != 1:
        raise AuthDenied('unknown_mattermost_user')
    return matches[0]

def authorize(file_id: str, *, mattermost_user_id: str='', mattermost_username: str='', account: str=None, identity_cache: dict[str, Any] | None=None, group_cache: dict[str, Any] | None=None, permissions: list[dict[str, Any]] | None=None, file_name: str | None=None, runner: Any=subprocess.run, now: Any=None) -> dict[str, Any]:
    access = _PdUnset
    emails = _PdUnset
    group_email = _PdUnset
    identity = _PdUnset
    perms = _PdUnset
    role = _PdUnset
    via = _PdUnset

    def _pd_phase_1():
        nonlocal access, account, emails, file_id, group_cache, group_email, identity, identity_cache, perms, role, via
        if account is None:
            account = DEFAULT_ACCOUNT()
        file_id = str(file_id or '').strip()
        if not file_id:
            return _PdReturn(deny_payload('missing_file_id'))
        try:
            if identity_cache is None:
                identity_cache = load_identity_cache(now=now)
            else:
                identity_cache = validate_identity_cache(identity_cache, now=now)
            if group_cache is None:
                group_cache = load_group_v1_cache(now=now)
            else:
                group_cache = validate_group_v1_cache(group_cache, now=now)
            identity = resolve_identity(identity_cache=identity_cache, mattermost_user_id=mattermost_user_id, mattermost_username=mattermost_username)
        except (FileNotFoundError, ValueError) as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            reason = str(exc)
            if 'stale' in reason:
                return _PdReturn(deny_payload('stale_cache'))
            if 'incomplete' in reason:
                return _PdReturn(deny_payload('incomplete_cache'))
            if 'missing' in reason:
                return _PdReturn(deny_payload('missing_cache'))
            return _PdReturn(deny_payload('invalid_cache'))
        except AuthDenied as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            return _PdReturn(deny_payload(exc.reason))
        emails = requester_emails(identity)
        if not emails:
            return _PdReturn(deny_payload('no_cached_emails'))
        name = file_name if file_name is not None else fetch_file_name(file_id, account, runner=runner)
        if name and SENSITIVE_RE.search(name):
            return _PdReturn(deny_payload('sensitive_red_line', sensitive=True))
        try:
            perms = permissions if permissions is not None else fetch_permissions(file_id, account, runner=runner)
        except RuntimeError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            return _PdReturn(deny_payload('drive_permissions_unavailable'))
        access = 'none'
        via = 'none'
        group_email = None
        role = 'none'

    def _pd_phase_2():
        nonlocal access, group_email, role, via
        for perm in perms:
            ptype = str(perm.get('type') or '').lower()
            principal = normalize_email(perm.get('emailAddress') or perm.get('email'))
            perm_role = normalize_drive_role(perm.get('role'))
            perm_access = access_for_role(perm_role)
            if not principal or perm_access == 'none':
                continue
            matched_via = None
            matched_group = None
            if ptype == 'user' and principal in emails:
                matched_via = 'user'
            elif ptype == 'group':
                members = expanded_members(group_cache, principal)
                if emails & members:
                    matched_via = 'group'
                    matched_group = principal
            if not matched_via:
                continue
            previous = ACCESS_RANK.get(access, 0)
            incoming = ACCESS_RANK.get(perm_access, 0)
            if incoming > previous or (incoming == previous and matched_via == 'group'):
                access = perm_access
                via = matched_via
                group_email = matched_group
                role = perm_role
            elif incoming == previous:
                access = strongest_access(access, perm_access)
        if access == 'none':
            return _PdReturn(deny_payload('no_matching_ace', mattermostUserId=str(identity.get('mattermostUserId') or ''), mattermostUsername=str(identity.get('mattermostUsername') or '')))
        return _PdReturn({'status': 'ok', 'canRead': ACCESS_RANK[access] >= ACCESS_RANK['read'], 'canComment': ACCESS_RANK[access] >= ACCESS_RANK['comment'], 'canWrite': ACCESS_RANK[access] >= ACCESS_RANK['write'], 'via': via, 'groupEmail': group_email, 'role': role, 'access': access, 'permissionsCreateAttempted': False, 'mattermostUserId': str(identity.get('mattermostUserId') or ''), 'mattermostUsername': str(identity.get('mattermostUsername') or ''), 'sensitive': False})
    _pd_result = _pd_phase_1()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
    _pd_result = _pd_phase_2()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value

def public_view(result: dict[str, Any], *, redact: bool=True) -> dict[str, Any]:
    view = {'status': result.get('status'), 'canRead': bool(result.get('canRead')), 'canComment': bool(result.get('canComment')), 'canWrite': bool(result.get('canWrite')), 'via': result.get('via') or 'none', 'role': result.get('role') or 'none', 'permissionsCreateAttempted': False, 'reason': result.get('reason'), 'mattermostUserId': result.get('mattermostUserId'), 'mattermostUsername': result.get('mattermostUsername')}
    if result.get('via') == 'group':
        view['via'] = 'group'
    if redact:
        view.pop('groupEmail', None)
        return redact_emails(view)
    view['groupEmail'] = result.get('groupEmail')
    return view

def refuse_individual_share() -> dict[str, Any]:
    return {'status': 'error', 'error': 'individual_drive_share_forbidden', 'detail': 'PD One must not add type=user Drive contributors for employee read/write requests. Use drive-acl-authorize.', 'permissionsCreateAttempted': False}

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file-id', required=True)
    parser.add_argument('--mattermost-user-id', default='')
    parser.add_argument('--username', default='')
    parser.add_argument('--account', default=DEFAULT_ACCOUNT())
    parser.add_argument('--redact', action='store_true', default=True)
    parser.add_argument('--include-group-email', action='store_true')
    args = parser.parse_args(argv)
    result = authorize(args.file_id, mattermost_user_id=args.mattermost_user_id, mattermost_username=args.username, account=args.account)
    print(json.dumps(public_view(result, redact=not args.include_group_email), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get('status') == 'ok' else 2
if __name__ == '__main__':
    raise SystemExit(main())

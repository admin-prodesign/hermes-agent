#!/usr/bin/env python3
"""Authorize Portal module-change requests by group membership and channel.

Exact Mattermost sender id → employee Google identity cache → v1 group
expanded_members. Auto-approve only in the mapped department channel.
DM and other channels redirect; they never execute.

Never prints email addresses. Fail closed on missing/stale/incomplete cache.
"""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import argparse
import json
import sys
from pathlib import Path
from typing import Any
TOOLS = Path(__file__).resolve().parent

def ROOT():
    return profile_root()
if str(TOOLS) not in sys.path:
    sys.path.append(str(TOOLS))
from drive_acl_common import expanded_members, load_group_v1_cache, load_identity_cache, load_json, redact_emails, requester_emails, validate_group_v1_cache, validate_identity_cache

def GRANTS_PATH():
    return ROOT() / 'config' / 'portal_module_change_grants.json'
IN_SCOPE_CHANGE_CLASS = 'in_scope_module_product'
REDIRECT_SENTINEL = 'redirect_to_department_channel'

def load_grants(path: Path=None) -> dict[str, Any]:
    if path is None:
        path = GRANTS_PATH()
    data = load_json(path)
    if data.get('schema') != 'pd-one.portal-module-change-grants.v1':
        raise ValueError('unsupported portal module change grants schema')
    modules = data.get('modules')
    if not isinstance(modules, dict) or not modules:
        raise ValueError('portal module change grants missing modules')
    return data

def deny_payload(reason: str, **extra: Any) -> dict[str, Any]:
    payload = {'status': 'denied', 'decision': 'deny', 'autoApproved': False, 'execute': False, 'reason': reason, 'sentinel': None, 'moduleId': extra.pop('moduleId', None), 'path': extra.pop('path', None), 'channelMatch': False, 'groupMember': extra.pop('groupMember', False), 'changeClass': extra.pop('changeClass', None), 'departmentChannelName': extra.pop('departmentChannelName', None)}
    payload.update(extra)
    return payload

def redirect_payload(grant: dict[str, Any], *, change_class: str, group_member: bool) -> dict[str, Any]:
    name = str(grant.get('department_channel_name') or '').strip()
    return {'status': 'redirect', 'decision': REDIRECT_SENTINEL, 'autoApproved': False, 'execute': False, 'reason': 'must_request_in_department_channel', 'sentinel': REDIRECT_SENTINEL, 'moduleId': grant.get('module_id'), 'path': grant.get('path'), 'channelMatch': False, 'groupMember': group_member, 'changeClass': change_class, 'departmentChannelId': grant.get('department_channel_id'), 'departmentChannelName': name, 'redirectZh': f'請在部門頻道「{name}」提出入口網站模組修改，讓同部門同事都看得到。請勿用私訊提出；私訊不會執行。' if name else '請在部門頻道提出入口網站模組修改，讓同部門同事都看得到。請勿用私訊提出；私訊不會執行。', 'redirectEn': f'Please request portal module changes in the department channel “{name}” so the rest of the department can see them. Do not request this by DM; DM requests are not executed.' if name else 'Please request portal module changes in the department channel so the rest of the department can see them. Do not request this by DM; DM requests are not executed.'}

def resolve_grant(grants: dict[str, Any], *, module_id: str='', path: str='') -> dict[str, Any] | None:
    modules = grants.get('modules') or {}
    wanted_id = str(module_id or '').strip().lower().strip('/')
    wanted_path = str(path or '').strip()
    if wanted_path and (not wanted_path.startswith('/')):
        wanted_path = '/' + wanted_path
    if wanted_path and (not wanted_path.endswith('/')):
        wanted_path = wanted_path + '/'
    if wanted_id:
        rec = modules.get(wanted_id)
        if isinstance(rec, dict):
            return rec
    if wanted_path:
        for rec in modules.values():
            if isinstance(rec, dict) and str(rec.get('path') or '') == wanted_path:
                return rec
    return None

def _cache_deny_reason(exc: BaseException) -> str:
    reason = str(exc)
    if 'stale' in reason:
        return 'stale_cache'
    if 'incomplete' in reason:
        return 'incomplete_cache'
    if 'missing' in reason:
        return 'missing_cache'
    return 'invalid_cache'

def authorize(*, mattermost_user_id: str, channel_id: str='', module_id: str='', path: str='', change_class: str=IN_SCOPE_CHANGE_CLASS, identity_cache: dict[str, Any] | None=None, group_cache: dict[str, Any] | None=None, grants: dict[str, Any] | None=None, now: Any=None) -> dict[str, Any]:
    sender = str(mattermost_user_id or '').strip()
    if not sender:
        return deny_payload('missing_mattermost_user_id')
    try:
        grants = grants if grants is not None else load_grants()
    except (OSError, ValueError, json.JSONDecodeError):
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return deny_payload('invalid_grants')
    grant = resolve_grant(grants, module_id=module_id, path=path)
    if not isinstance(grant, dict) or grant.get('enabled') is not True:
        return deny_payload('module_not_granted', moduleId=module_id or None, path=path or None, changeClass=change_class)
    change_class = str(change_class or IN_SCOPE_CHANGE_CLASS).strip() or IN_SCOPE_CHANGE_CLASS
    in_scope_class = str(grants.get('in_scope_change_class') or IN_SCOPE_CHANGE_CLASS)
    denied_classes = {str(item) for item in grants.get('denied_change_classes') or []}
    try:
        if identity_cache is None:
            identity_cache = load_identity_cache(now=now)
        else:
            identity_cache = validate_identity_cache(identity_cache, now=now)
        if group_cache is None:
            group_cache = load_group_v1_cache(now=now)
        else:
            group_cache = validate_group_v1_cache(group_cache, now=now)
    except (FileNotFoundError, ValueError) as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return deny_payload(_cache_deny_reason(exc), moduleId=grant.get('module_id'), path=grant.get('path'), changeClass=change_class, departmentChannelName=grant.get('department_channel_name'))
    users = identity_cache.get('users') or {}
    identity = users.get(sender)
    if not isinstance(identity, dict):
        return deny_payload('unknown_mattermost_user', moduleId=grant.get('module_id'), path=grant.get('path'), changeClass=change_class, departmentChannelName=grant.get('department_channel_name'))
    emails = requester_emails(identity)
    if not emails:
        return deny_payload('no_cached_emails', moduleId=grant.get('module_id'), path=grant.get('path'), changeClass=change_class, departmentChannelName=grant.get('department_channel_name'))
    group_email = str(grant.get('google_group') or '').strip().lower()
    groups = group_cache.get('groups') or {}
    if group_email not in groups:
        return deny_payload('missing_group', moduleId=grant.get('module_id'), path=grant.get('path'), changeClass=change_class, departmentChannelName=grant.get('department_channel_name'))
    members = expanded_members(group_cache, group_email)
    group_member = bool(emails & members)
    if not group_member:
        return deny_payload('not_group_member', moduleId=grant.get('module_id'), path=grant.get('path'), changeClass=change_class, groupMember=False, departmentChannelName=grant.get('department_channel_name'))
    if change_class != in_scope_class or change_class in denied_classes:
        return deny_payload('change_class_denied', moduleId=grant.get('module_id'), path=grant.get('path'), changeClass=change_class, groupMember=True, departmentChannelName=grant.get('department_channel_name'))
    department_channel_id = str(grant.get('department_channel_id') or '').strip()
    current_channel = str(channel_id or '').strip()
    if not department_channel_id or current_channel != department_channel_id:
        return redirect_payload(grant, change_class=change_class, group_member=True)
    return {'status': 'auto_approved', 'decision': 'auto_approve', 'autoApproved': True, 'execute': True, 'reason': 'department_channel_group_member_in_scope', 'sentinel': None, 'moduleId': grant.get('module_id'), 'path': grant.get('path'), 'channelMatch': True, 'groupMember': True, 'changeClass': change_class, 'departmentChannelId': department_channel_id, 'departmentChannelName': grant.get('department_channel_name'), 'via': 'google_group_expanded_members', 'andyTicket': False}

def public_view(result: dict[str, Any]) -> dict[str, Any]:
    keep = ('status', 'decision', 'autoApproved', 'execute', 'reason', 'sentinel', 'moduleId', 'path', 'channelMatch', 'groupMember', 'changeClass', 'departmentChannelName', 'redirectZh', 'redirectEn', 'via', 'andyTicket')
    view = {key: result.get(key) for key in keep if key in result}
    return redact_emails(view)

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requester-user-id', required=True)
    parser.add_argument('--channel-id', default='')
    parser.add_argument('--module-id', default='')
    parser.add_argument('--path', default='')
    parser.add_argument('--change-class', default=IN_SCOPE_CHANGE_CLASS)
    args = parser.parse_args(argv)
    result = authorize(mattermost_user_id=args.requester_user_id, channel_id=args.channel_id, module_id=args.module_id, path=args.path, change_class=args.change_class)
    print(json.dumps(public_view(result), ensure_ascii=False, indent=2, sort_keys=True))
    if result.get('execute') is True:
        return 0
    if result.get('sentinel') == REDIRECT_SENTINEL:
        return 3
    return 2
if __name__ == '__main__':
    raise SystemExit(main())

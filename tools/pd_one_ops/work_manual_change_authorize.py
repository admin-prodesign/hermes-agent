#!/usr/bin/env python3
"""Authorize work-manual content-add requests by group membership and chat type.

Exact Mattermost sender id → employee Google identity cache → v1 group
expanded_members. Auto-approve only in non-DM settings. DM requests redirect;
they never execute.

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
    return ROOT() / 'config' / 'work_manual_change_grants.json'
IN_SCOPE_CHANGE_CLASS = 'secret_free_content_add'
REDIRECT_SENTINEL = 'redirect_to_department_channel'
DEFAULT_DOCUMENT_KEY = 'it_manual'

def load_grants(path: Path=None) -> dict[str, Any]:
    if path is None:
        path = GRANTS_PATH()
    data = load_json(path)
    if data.get('schema') != 'pd-one.work-manual-change-grants.v1':
        raise ValueError('unsupported work manual change grants schema')
    manuals = data.get('manuals')
    if not isinstance(manuals, dict) or not manuals:
        raise ValueError('work manual change grants missing manuals')
    return data

def deny_payload(reason: str, **extra: Any) -> dict[str, Any]:
    payload = {'status': 'denied', 'decision': 'deny', 'autoApproved': False, 'execute': False, 'reason': reason, 'sentinel': None, 'documentKey': extra.pop('documentKey', None), 'channelMatch': False, 'nonDm': extra.pop('nonDm', False), 'groupMember': extra.pop('groupMember', False), 'changeClass': extra.pop('changeClass', None), 'departmentChannelName': extra.pop('departmentChannelName', None)}
    payload.update(extra)
    return payload

def redirect_payload(grant: dict[str, Any], *, change_class: str, group_member: bool) -> dict[str, Any]:
    name = str(grant.get('department_channel_name') or '').strip()
    return {'status': 'redirect', 'decision': REDIRECT_SENTINEL, 'autoApproved': False, 'execute': False, 'reason': 'must_request_in_non_dm', 'sentinel': REDIRECT_SENTINEL, 'documentKey': grant.get('document_key'), 'channelMatch': False, 'nonDm': False, 'groupMember': group_member, 'changeClass': change_class, 'departmentChannelId': grant.get('department_channel_id'), 'departmentChannelName': name, 'redirectZh': f'請在非私訊場合提交 IT 工作手冊內容（建議「{name}」），讓資訊部同事都看得到。請勿用私訊提出；私訊不會自動寫入。' if name else '請在非私訊場合提交 IT 工作手冊內容，讓資訊部同事都看得到。請勿用私訊提出；私訊不會自動寫入。', 'redirectEn': f'Please submit IT work-manual content in a non-DM setting (prefer “{name}”) so IT colleagues can see it. Do not request this by DM; DM requests are not auto-written.' if name else 'Please submit IT work-manual content in a non-DM setting so IT colleagues can see it. Do not request this by DM; DM requests are not auto-written.'}

def resolve_grant(grants: dict[str, Any], *, document_key: str='', document_id: str='') -> dict[str, Any] | None:
    manuals = grants.get('manuals') or {}
    wanted_key = str(document_key or '').strip().lower()
    wanted_id = str(document_id or '').strip()
    if wanted_key:
        rec = manuals.get(wanted_key)
        if isinstance(rec, dict):
            return rec
    if wanted_id:
        for rec in manuals.values():
            if isinstance(rec, dict) and str(rec.get('document_id') or '') == wanted_id:
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

def _normalize_chat_type(chat_type: str) -> str:
    value = str(chat_type or '').strip().lower().replace('-', '_')
    aliases = {'directmessage': 'dm', 'direct_message': 'dm', 'direct': 'dm', 'd': 'dm', 'private_channel': 'private', 'public_channel': 'public', 'private_group': 'group', 'open': 'public'}
    return aliases.get(value, value)

def _is_mapped_channel(grant: dict[str, Any], channel_id: str) -> bool:
    current = str(channel_id or '').strip()
    if not current:
        return False
    department = str(grant.get('department_channel_id') or '').strip()
    extra = [str(item).strip() for item in grant.get('also_allowed_channel_ids') or []]
    return current == department or current in extra

def _is_non_dm(*, grants: dict[str, Any], grant: dict[str, Any], channel_id: str, chat_type: str) -> bool | None:
    """Return True/False when known, None when chat context is insufficient."""
    dm_types = {str(item).strip().lower() for item in grants.get('dm_chat_types') or ['dm', 'direct', 'direct_message']}
    non_dm_types = {str(item).strip().lower() for item in grants.get('non_dm_chat_types') or ['group', 'channel', 'private', 'public']}
    normalized = _normalize_chat_type(chat_type)
    if normalized in dm_types:
        return False
    if _is_mapped_channel(grant, channel_id):
        return True
    if normalized in non_dm_types:
        return True
    if bool(grant.get('auto_approve_any_non_dm')) and normalized and (normalized not in dm_types):
        return True
    return None

def authorize(*, mattermost_user_id: str, channel_id: str='', chat_type: str='', document_key: str=DEFAULT_DOCUMENT_KEY, document_id: str='', change_class: str=IN_SCOPE_CHANGE_CLASS, identity_cache: dict[str, Any] | None=None, group_cache: dict[str, Any] | None=None, grants: dict[str, Any] | None=None, now: Any=None) -> dict[str, Any]:
    sender = str(mattermost_user_id or '').strip()
    if not sender:
        return deny_payload('missing_mattermost_user_id')
    try:
        grants = grants if grants is not None else load_grants()
    except (OSError, ValueError, json.JSONDecodeError):
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return deny_payload('invalid_grants')
    grant = resolve_grant(grants, document_key=document_key, document_id=document_id)
    if not isinstance(grant, dict) or grant.get('enabled') is not True:
        return deny_payload('manual_not_granted', documentKey=document_key or None, changeClass=change_class)
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
        return deny_payload(_cache_deny_reason(exc), documentKey=grant.get('document_key'), changeClass=change_class, departmentChannelName=grant.get('department_channel_name'))
    users = identity_cache.get('users') or {}
    identity = users.get(sender)
    if not isinstance(identity, dict):
        return deny_payload('unknown_mattermost_user', documentKey=grant.get('document_key'), changeClass=change_class, departmentChannelName=grant.get('department_channel_name'))
    emails = requester_emails(identity)
    if not emails:
        return deny_payload('no_cached_emails', documentKey=grant.get('document_key'), changeClass=change_class, departmentChannelName=grant.get('department_channel_name'))
    group_email = str(grant.get('google_group') or '').strip().lower()
    groups = group_cache.get('groups') or {}
    if group_email not in groups:
        return deny_payload('missing_group', documentKey=grant.get('document_key'), changeClass=change_class, departmentChannelName=grant.get('department_channel_name'))
    members = expanded_members(group_cache, group_email)
    group_member = bool(emails & members)
    if not group_member:
        return deny_payload('not_group_member', documentKey=grant.get('document_key'), changeClass=change_class, groupMember=False, departmentChannelName=grant.get('department_channel_name'))
    if change_class != in_scope_class or change_class in denied_classes:
        return deny_payload('change_class_denied', documentKey=grant.get('document_key'), changeClass=change_class, groupMember=True, departmentChannelName=grant.get('department_channel_name'))
    non_dm = _is_non_dm(grants=grants, grant=grant, channel_id=channel_id, chat_type=chat_type)
    if non_dm is False:
        return redirect_payload(grant, change_class=change_class, group_member=True)
    if non_dm is None:
        return deny_payload('missing_channel_context', documentKey=grant.get('document_key'), changeClass=change_class, groupMember=True, departmentChannelName=grant.get('department_channel_name'))
    return {'status': 'auto_approved', 'decision': 'auto_approve', 'autoApproved': True, 'execute': True, 'reason': 'non_dm_group_member_in_scope', 'sentinel': None, 'documentKey': grant.get('document_key'), 'channelMatch': _is_mapped_channel(grant, channel_id), 'nonDm': True, 'groupMember': True, 'changeClass': change_class, 'departmentChannelId': grant.get('department_channel_id'), 'departmentChannelName': grant.get('department_channel_name'), 'via': 'google_group_expanded_members', 'andyTicket': False}

def public_view(result: dict[str, Any]) -> dict[str, Any]:
    keep = ('status', 'decision', 'autoApproved', 'execute', 'reason', 'sentinel', 'documentKey', 'channelMatch', 'nonDm', 'groupMember', 'changeClass', 'departmentChannelName', 'redirectZh', 'redirectEn', 'via', 'andyTicket')
    view = {key: result.get(key) for key in keep if key in result}
    return redact_emails(view)

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requester-user-id', required=True)
    parser.add_argument('--channel-id', default='')
    parser.add_argument('--chat-type', default='')
    parser.add_argument('--document-key', default=DEFAULT_DOCUMENT_KEY)
    parser.add_argument('--document-id', default='')
    parser.add_argument('--change-class', default=IN_SCOPE_CHANGE_CLASS)
    args = parser.parse_args(argv)
    result = authorize(mattermost_user_id=args.requester_user_id, channel_id=args.channel_id, chat_type=args.chat_type, document_key=args.document_key, document_id=args.document_id, change_class=args.change_class)
    print(json.dumps(public_view(result), ensure_ascii=False, indent=2, sort_keys=True))
    if result.get('execute') is True:
        return 0
    if result.get('sentinel') == REDIRECT_SENTINEL:
        return 3
    return 2
if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Resolve Mattermost user policy deterministically.

Canonical inputs:
- workspace/policies/mattermost-users.json
- workspace/policies/mattermost-roles.json

This is a canonical scope/privilege lookup for agents, not a hard runtime gate.
Agents may still reply agentically to unknown/not-yet-onboarded users, but must
not use scoped company data or privileged tools unless this exact sender-id
resolution permits it.
"""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def ROOT():
    return profile_root()

def USERS_PATH():
    return ROOT() / 'policies' / 'mattermost-users.json'

def ROLES_PATH():
    return ROOT() / 'policies' / 'mattermost-roles.json'

def DEFAULT_CACHE_DIR():
    return ROOT() / 'policy-cache' / 'mattermost'

def EMPLOYEE_CACHE_DIR():
    return ROOT() / 'policy-cache' / 'employee'

def DOCUMENT_ACCESS_CACHE():
    return ROOT() / 'data' / 'google-docs-index' / 'group-document-access-cache.json'
SAFE_USER_KEYS = ['displayName', 'mattermostUsername', 'mattermostEmail', 'status', 'language', 'languageSource', 'roles', 'extraRoles']

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))

def stable_unique(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for value in values:
        marker = json.dumps(value, sort_keys=True, ensure_ascii=False)
        if marker not in seen:
            seen.add(marker)
            out.append(value)
    return out
GENERIC_TOOLS_WRITES = frozenset({'confirm-by-admin', 'confirm', 'never'})
DRIVE_GROUP_WRITES_MARKER = 'Drive-group-authorized'

def merge_dicts(*items: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        if isinstance(item, dict):
            out.update(item)
    return out

def prefer_tools_writes(current: str, incoming: str) -> str:
    """Keep the Drive-group writer exception when a later generic writes flag would clobber it."""
    cur = str(current or '').strip()
    new = str(incoming or '').strip()
    if not new:
        return cur
    if not cur:
        return new
    if new in GENERIC_TOOLS_WRITES and DRIVE_GROUP_WRITES_MARKER in cur:
        return cur
    if cur in GENERIC_TOOLS_WRITES and DRIVE_GROUP_WRITES_MARKER in new:
        return new
    return new

def merge_tools(*items: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            if key == 'writes':
                out[key] = prefer_tools_writes(str(out.get(key) or ''), str(value or ''))
            else:
                out[key] = value
    return out

def policy_hash(document_access_cache: dict[str, Any] | None=None) -> str:
    h = hashlib.sha256()
    for path in [USERS_PATH(), ROLES_PATH()]:
        h.update(path.name.encode())
        h.update(b'\x00')
        h.update(path.read_bytes())
        h.update(b'\x00')
    if document_access_cache:
        h.update(b'google-workspace-document-access\x00')
        h.update(str(document_access_cache.get('cacheHash') or document_access_cache.get('sourceHash', '')).encode())
        h.update(b'\x00')
    return h.hexdigest()[:16]

def load_document_access_cache(path: Path=None) -> dict[str, Any] | None:
    if path is None:
        path = DOCUMENT_ACCESS_CACHE()
    if not path.exists():
        return None
    data = load_json(path)
    if data.get('schema') != 'pd-one.google-workspace-document-access.v1':
        raise ValueError(f'Unsupported Google Workspace document access cache schema in {path}')
    return data

def document_access_for_user(document_access_cache: dict[str, Any] | None, user_id: str) -> dict[str, Any] | None:
    if not document_access_cache:
        return None
    user_rec = (document_access_cache.get('users') or {}).get(user_id)
    if not isinstance(user_rec, dict):
        return None
    documents = user_rec.get('documents') or []
    if not documents:
        return None
    return {'schema': document_access_cache.get('schema'), 'generatedAtUtc': document_access_cache.get('generatedAtUtc'), 'sourceHash': document_access_cache.get('sourceHash'), 'identityRule': document_access_cache.get('identityRule'), 'roleSemantics': document_access_cache.get('roleSemantics', {}), 'summary': user_rec.get('summary', {}), 'documents': documents, 'notes': ['Google Docs/Sheets access comes from exact email mapping plus Drive permission metadata.', 'writer/owner grants read-write eligibility; commenter grants read/comment; reader grants read-only.', 'Live employee read/write of a file is authorized by tools/drive_acl_authorize.py against live Drive ACL plus the v1 group cache and employee identity cache. The 200-doc manifest is not required.', 'Never grant access by adding type=user Drive contributors.', 'Sensitive red-line categories still override this evidence and fail closed unless explicit restricted access exists.']}

def default_setup_response(users_policy: dict[str, Any]) -> dict[str, str]:
    dm = users_policy.get('defaults', {}).get('dm', {}).get('response', {})
    return {'en': dm.get('en', 'Hello — I’m PD One. I’m not set up for your direct messages yet, so I can only provide general setup guidance here. Please ask in the appropriate Mattermost channel, or contact the Vice President if you need DM access.'), 'zh-tw': dm.get('zh-tw', '你好，我是 PD One。我目前還沒有為你的私訊完成設定，所以這裡只能提供一般設定說明。請到適合的 Mattermost 頻道提問，或聯絡副總申請私訊權限。'), 'bilingual': dm.get('bilingual', 'Hello — I’m PD One. I’m not set up for your direct messages yet, so I can only provide general setup guidance here. Please ask in the appropriate Mattermost channel, or contact the Vice President if you need DM access.\n\n你好，我是 PD One。我目前還沒有為你的私訊完成設定，所以這裡只能提供一般設定說明。請到適合的 Mattermost 頻道提問，或聯絡副總申請私訊權限。')}

def default_lookup_failure_response(users_policy: dict[str, Any]) -> dict[str, str]:
    dm = users_policy.get('defaults', {}).get('dm', {}).get('lookupFailureResponse', {})
    return {'en': dm.get('en', 'Hello — I’m PD One. I can’t verify your DM access right now, so I’m pausing scoped help until access is rechecked. Please try again in a moment or ask the Vice President to review your PD One access.'), 'zh-tw': dm.get('zh-tw', '你好，我是 PD One。我現在無法確認你的私訊權限，所以會先暫停需要權限的協助，等權限重新確認後再處理。你可以稍後再試，或請副總協助確認你的 PD One 權限。'), 'bilingual': dm.get('bilingual', 'Hello — I’m PD One. I can’t verify your DM access right now, so I’m pausing scoped help until access is rechecked. Please try again in a moment or ask the Vice President to review your PD One access.\n\n你好，我是 PD One。我現在無法確認你的私訊權限，所以會先暫停需要權限的協助，等權限重新確認後再處理。你可以稍後再試，或請副總協助確認你的 PD One 權限。')}

def resolve_user(user_id: str, users_policy: dict[str, Any], roles_policy: dict[str, Any], document_access_cache: dict[str, Any] | None=None) -> dict[str, Any]:
    users = users_policy.get('users', {})
    roles = roles_policy.get('roles', {})
    setup = default_setup_response(users_policy)
    lookup_failure = default_lookup_failure_response(users_policy)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    base: dict[str, Any] = {'schema': 'pd-one.mattermost-policy-resolution.v1', 'generatedAtUtc': now, 'sourceHash': policy_hash(document_access_cache), 'mattermostUserId': user_id, 'found': False, 'active': False, 'dmEnabled': False, 'language': users_policy.get('languagePolicy', {}).get('defaultLanguage', 'en'), 'displayName': '', 'setupResponse': setup, 'lookupFailureResponse': lookup_failure, 'decision': 'unresolved_user', 'turnHandling': 'agent_may_reply_with_setup_or_general_guidance; do_not_use_scoped_company_data_or_privileged_tools', 'safeScopes': [], 'roles': [], 'channels': {}, 'dataAccess': {}, 'tools': {}, 'approval': {}, 'employeeFacingNotes': ['Use only this exact current sender id resolution for authorization.', 'Do not use names, prior sessions, or fuzzy matching to select a profile.', 'Do not reveal policy internals to employees.']}
    user = users.get(user_id)
    if not isinstance(user, dict):
        return base
    role_names = list(user.get('roles') or []) + list(user.get('extraRoles') or [])
    role_merge_names = [name for name in role_names if name == 'operational_employee_default'] + [name for name in role_names if name != 'operational_employee_default']
    role_objs = [roles.get(name, {}) for name in role_merge_names]
    role_scopes: list[str] = []
    role_dm_allowed_scopes: list[str] = []
    role_dm_enabled = False
    for role in role_objs:
        role_scopes.extend(role.get('scopes') or [])
        dm = role.get('dm') or {}
        role_dm_allowed_scopes.extend(dm.get('allowedScopes') or [])
        if dm.get('enabled') is True:
            role_dm_enabled = True
    user_dm = user.get('dm') or {}
    user_dm_enabled = user_dm.get('enabled')
    if user_dm_enabled is None:
        dm_enabled = bool(role_dm_enabled)
    else:
        dm_enabled = bool(user_dm_enabled)
    active = user.get('status') == 'active'
    if not active:
        dm_enabled = False
    user_scopes = list(user_dm.get('allowedScopes') or [])
    safe_scopes = stable_unique(role_scopes + role_dm_allowed_scopes + user_scopes)
    resolved = dict(base)
    resolved.update({'found': True, 'active': active, 'dmEnabled': dm_enabled, 'decision': 'allow_dm' if dm_enabled else 'inactive_user' if not active else 'dm_disabled', 'turnHandling': 'scoped_dm_allowed' if dm_enabled else 'agent_may_reply_with_setup_or_general_guidance; do_not_use_scoped_company_data_or_privileged_tools', 'displayName': user.get('displayName') or user.get('mattermostUsername') or '', 'mattermostUsername': user.get('mattermostUsername') or '', 'mattermostEmail': user.get('mattermostEmail') or '', 'language': user.get('language') or base['language'], 'languageSource': user.get('languageSource') or '', 'roles': role_names, 'safeScopes': safe_scopes, 'channels': merge_dicts(*(r.get('channels') or {} for r in role_objs), user.get('channels') or {}), 'dataAccess': merge_dicts(*(r.get('dataAccess') or {} for r in role_objs), user.get('dataAccess') or {}), 'tools': merge_tools(*(r.get('tools') or {} for r in role_objs), user.get('tools') or {}), 'approval': merge_dicts(*(r.get('approval') or {} for r in role_objs), user.get('approval') or {}), 'googleWorkspace': {'documentAccess': document_access_for_user(document_access_cache, user_id)}, 'identity': {'source': 'mattermost-users.json exact Mattermost user id', 'appsheetPersonId': (user.get('appsheet') or {}).get('PersonID', ''), 'nameZh': (user.get('appsheet') or {}).get('Name_ZH', user.get('displayName', '')), 'nameEn': (user.get('appsheet') or {}).get('Name_EN', ''), 'identityRule': 'Exact Mattermost sender id only; no name/fuzzy fallback.'}})
    return resolved

def write_cache(cache_dir: Path, users_policy: dict[str, Any], roles_policy: dict[str, Any], document_access_cache: dict[str, Any] | None=None) -> None:
    users_dir = cache_dir / 'users'
    users_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    source_hash = policy_hash(document_access_cache)
    expected_files: set[Path] = set()
    index: dict[str, Any] = {'schema': 'pd-one.mattermost-policy-cache-index.v1', 'generatedAtUtc': generated_at, 'sourceHash': source_hash, 'sourceFiles': [str(USERS_PATH()), str(ROLES_PATH())] + ([str(DOCUMENT_ACCESS_CACHE())] if document_access_cache else []), 'userCount': 0, 'users': {}, 'lookupRule': "Read users/<exact Mattermost sender id>.json when a Mattermost user's scopes/privileges are needed. If missing, inactive, or dmEnabled=false for a DM, the agent may still reply with setup/general guidance but must not use scoped company data or privileged tools. If the cache/source is unreadable or the lookup itself fails, use lookupFailureResponse rather than saying the user is not enabled."}
    for user_id in sorted((users_policy.get('users') or {}).keys()):
        resolved = resolve_user(user_id, users_policy, roles_policy, document_access_cache)
        out_path = users_dir / f'{user_id}.json'
        out_path.write_text(json.dumps(resolved, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        expected_files.add(out_path)
        index['users'][user_id] = {'displayName': resolved.get('displayName', ''), 'mattermostUsername': resolved.get('mattermostUsername', ''), 'active': resolved.get('active', False), 'dmEnabled': resolved.get('dmEnabled', False), 'language': resolved.get('language', ''), 'roles': resolved.get('roles', []), 'googleWorkspaceDocumentAccess': (resolved.get('googleWorkspace') or {}).get('documentAccess', {}).get('summary', {}) if (resolved.get('googleWorkspace') or {}).get('documentAccess') else {}, 'file': f'users/{user_id}.json'}
    for stale in users_dir.glob('*.json'):
        if stale not in expected_files:
            stale.unlink()
    index['userCount'] = len(index['users'])
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (cache_dir / 'README.md').write_text('# Mattermost Policy Cache\n\nGenerated by `~/.hermes/profiles/pdone/tools/mattermost_policy_lookup.py generate-cache`.\n\nAgents read exactly one file when they need current requester scope: `users/<current Mattermost sender id>.json`.\nThis cache is a canonical scope/privilege reference, not a hard gate for whether the model may reply.\nIf a file is missing, inactive, or has `dmEnabled: false` for a DM, agents may still reply with setup/general guidance but must not use scoped company data or privileged tools.\nIf the cache/source is unreadable or the lookup itself fails, use `lookupFailureResponse` rather than saying the user is not enabled.\nDo not edit generated files by hand; edit canonical Hermes PD One policy files under `~/.hermes/profiles/pdone/policies/`, then regenerate.\n', encoding='utf-8')

def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0
if __name__ == '__main__':
    main()

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    lookup = sub.add_parser('lookup', help='Resolve one exact Mattermost user id')
    lookup.add_argument('user_id')
    gen = sub.add_parser('generate-cache', help='Generate per-user Mattermost policy cache')
    gen.add_argument('--cache-dir', type=Path, default=DEFAULT_CACHE_DIR())
    gen.add_argument('--employee-mirror', dest='employee_mirror', action='store_true', default=True, help='Also mirror cache to policy-cache/employee (default)')
    gen.add_argument('--no-employee-mirror', dest='employee_mirror', action='store_false', help='Do not mirror cache to policy-cache/employee')
    return parser

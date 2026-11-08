#!/usr/bin/env python3
"""Shared Drive-group ACL constants and cache IO for PD One."""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def PROFILE_ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))

def IDENTITY_CACHE_PATH():
    return PROFILE_ROOT() / 'policy-cache/employee/google-identity-map.json'

def GROUP_V1_CACHE_PATH():
    return PROFILE_ROOT() / 'policy-cache/google-workspace/group-memberships.json'

def GROUP_V1_STATE_PATH():
    return Path(resolve_configured_path('~/.hermes/state/google-workspace/group-memberships.json'))

def PORTAL_GROUP_CACHE_PATH():
    return PROFILE_ROOT() / 'policy-cache/portal/google-group-members.json'

def USERS_POLICY_PATH():
    return PROFILE_ROOT() / 'policies/mattermost-users.json'
IDENTITY_SCHEMA = 'pd-one.employee-google-identity.v1'
GROUP_V1_SCHEMA = 'hermes.google-workspace-group-memberships.v1'
DEFAULT_MAX_AGE_SECONDS = 1800
ACCESS_RANK = {'none': 0, 'read': 1, 'comment': 2, 'write': 3}
ROLE_ACCESS = {'reader': 'read', 'viewer': 'read', 'commenter': 'comment', 'writer': 'write', 'editor': 'write', 'owner': 'write', 'organizer': 'write', 'fileorganizer': 'write'}
SENSITIVE_RE = re.compile('(finance|financial|accounting|payroll|salary|bonus|compensation|hr\\b|human resources|evaluation|performance review|discipline|disciplinary|credential|password|secret|oauth|admin config|財務|會計|薪資|獎金|人事|績效|考核|懲處|密碼|憑證)', re.IGNORECASE)
EMAIL_RE = re.compile('^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$')
EMAIL_FIND_RE = re.compile('[A-Za-z0-9._%+\\-]+@[A-Za-z0-9.\\-]+\\.[A-Za-z]{2,}')

def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def parse_iso(value: str) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return None

def normalize_email(value: Any) -> str:
    email = str(value or '').strip().lower()
    return email if EMAIL_RE.fullmatch(email) else ''

def normalize_drive_role(role: Any) -> str:
    return str(role or '').strip().lower().replace('_', '')

def access_for_role(role: Any) -> str:
    return ROLE_ACCESS.get(normalize_drive_role(role), 'none')

def strongest_access(left: str, right: str) -> str:
    return left if ACCESS_RANK.get(left, 0) >= ACCESS_RANK.get(right, 0) else right

def redact_emails(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): redact_emails(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_emails(v) for v in value]
    if isinstance(value, str):
        return EMAIL_FIND_RE.sub('(redacted)', value)
    return value

def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n'

def source_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode())
        digest.update(b'\x00')
        if path.is_file():
            digest.update(path.read_bytes())
        digest.update(b'\x00')
    return digest.hexdigest()[:16]

def atomic_write_0600(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(stable_json(payload), encoding='utf-8')
    os.chmod(tmp, 384)
    os.replace(tmp, path)
    os.chmod(path, 384)

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))

def cache_age_seconds(generated_at_utc: str, *, now: datetime | None=None) -> float | None:
    generated = parse_iso(generated_at_utc)
    if generated is None:
        return None
    current = now or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    return max(0.0, (current - generated).total_seconds())

def validate_identity_cache(data: dict[str, Any], *, now: datetime | None=None) -> dict[str, Any]:
    if data.get('schema') != IDENTITY_SCHEMA:
        raise ValueError('unsupported identity cache schema')
    if data.get('complete') is not True:
        raise ValueError('identity cache incomplete')
    max_age = int(data.get('max_age_seconds') or DEFAULT_MAX_AGE_SECONDS)
    age = cache_age_seconds(str(data.get('generatedAtUtc') or ''), now=now)
    if age is None or age > max_age:
        raise ValueError('identity cache stale')
    users = data.get('users')
    if not isinstance(users, dict):
        raise ValueError('identity cache users missing')
    return data

def load_identity_cache(path: Path=None, *, now: datetime | None=None) -> dict[str, Any]:
    if path is None:
        path = IDENTITY_CACHE_PATH()
    if not path.is_file():
        raise FileNotFoundError(f'identity cache missing: {path}')
    return validate_identity_cache(load_json(path), now=now)

def validate_group_v1_cache(data: dict[str, Any], *, now: datetime | None=None) -> dict[str, Any]:
    if data.get('schema') != GROUP_V1_SCHEMA:
        raise ValueError('unsupported group membership cache schema')
    if data.get('complete') is not True:
        raise ValueError('group membership cache incomplete')
    max_age = int(data.get('max_age_seconds') or DEFAULT_MAX_AGE_SECONDS)
    age = cache_age_seconds(str(data.get('generatedAtUtc') or ''), now=now)
    if age is None or age > max_age:
        raise ValueError('group membership cache stale')
    if not isinstance(data.get('groups'), dict):
        raise ValueError('group membership cache groups missing')
    return data

def load_group_v1_cache(path: Path | None=None, *, now: datetime | None=None) -> dict[str, Any]:
    candidates = [path] if path is not None else [GROUP_V1_CACHE_PATH(), GROUP_V1_STATE_PATH()]
    last_error: Exception | None = None
    for candidate in candidates:
        if candidate is None or not candidate.is_file():
            continue
        try:
            return validate_group_v1_cache(load_json(candidate), now=now)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            last_error = exc
            continue
    raise ValueError(str(last_error or 'group membership cache missing'))

def requester_emails(identity: dict[str, Any]) -> set[str]:
    emails: set[str] = set()
    for key in ('companyEmails', 'googleAccountEmails'):
        values = identity.get(key) or []
        if isinstance(values, list):
            emails.update((normalize_email(item) for item in values))
    emails.discard('')
    return emails

def expanded_members(group_cache: dict[str, Any], group_email: str) -> set[str]:
    rec = (group_cache.get('groups') or {}).get(normalize_email(group_email)) or {}
    members = rec.get('expanded_members') or rec.get('expandedMembers') or rec.get('members') or []
    if not isinstance(members, list):
        return set()
    return {email for email in (normalize_email(item) for item in members) if email}

#!/usr/bin/env python3
"""Authorize and (optionally) read \\\\redacted-host using the requester's Windows NTFS rights.

Owner 2026-09-16: profiled employees may ask PD One to read redacted-host documents
when live NTFS for their AD account allows Read or Write (Write implies Read).
SMB I/O still uses the redacted-vm helper identity (REDACTED\\account). Never collect or
impersonate employee Windows passwords. PD One still does not write redacted-host.
"""
from __future__ import annotations
import logging

class _PdLazyMod:

    def __init__(self, name: str) -> None:
        self._name = name
        self._mod = None

    def _load(self):
        if self._mod is None:
            try:
                self._mod = __import__(self._name, fromlist=['*'])
            except ImportError as exc:
                raise RuntimeError(f'PD One needs the {self._name} package for this command') from exc
        return self._mod

    def __getattr__(self, attr: str):
        return getattr(self._load(), attr)

class _PdLazyAttr:

    def __init__(self, module: str, attr: str) -> None:
        self._module = module
        self._attr = attr
        self._value = None

    def _load(self):
        if self._value is None:
            try:
                loaded = __import__(self._module, fromlist=[self._attr])
            except ImportError as exc:
                raise RuntimeError(f'PD One needs {self._module}.{self._attr} for this command') from exc
            self._value = getattr(loaded, self._attr)
        return self._value

    def __call__(self, *args, **kwargs):
        return self._load()(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._load(), name)
import os
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
_SQLSRV_UNSET = object()
sqlsrv: Any = _SQLSRV_UNSET

def _external() -> bool:
    return os.environ.get('PD_ONE_EXTERNAL_INTERPRETER', '').strip() not in {'', '0'}

def PROFILE():
    raw = os.environ.get('PD_ONE_PROFILE_ROOT', '').strip()
    if raw or _external():
        from tools.pd_one_ops.resolved import profile_root
        return profile_root()
    from tools.pd_one_ops.site_config import profile_root
    return profile_root()

def USERS_PATH():
    return PROFILE() / 'policies' / 'mattermost-users.json'

def _owner_username() -> str:
    if _external() or 'PD_ONE_OWNER_MM_USERNAME' in os.environ:
        from tools.pd_one_ops.resolved import owner_mm_username
        return owner_mm_username()
    from tools.pd_one_ops.site_config import site_text
    return site_text('PDONE_OWNER_MM_USERNAME')

def _sqlsrv():
    global sqlsrv
    if sqlsrv is not _SQLSRV_UNSET:
        return sqlsrv
    if _external() or os.environ.get('PD_ONE_SQLSRV_READONLY', '').strip():
        from tools.pd_one_ops.resolved import load_sqlsrv
        sqlsrv = load_sqlsrv()
        return sqlsrv
    from tools.pd_one_ops.site_config import load_external_module
    sqlsrv = load_external_module('sqlsrv_readonly', 'sqlsrv_readonly')
    return sqlsrv
DOMAIN = 'JSPD'
RED_LINE_PATH_RE = re.compile('薪資|payroll|password|密碼|credential|\\.env|考核|evaluation|bonus|獎金|payslip', re.I)
READ_RIGHTS_RE = re.compile('Read|ReadAndExecute|Modify|FullControl|ListDirectory|GenericRead', re.I)

def fail(message: str, extra: dict[str, Any] | None=None, code: int=2) -> None:
    payload = {'ok': False, 'authorized': False, 'error': message}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(code)

def load_user(user_id: str) -> dict[str, Any]:
    data = json.loads(USERS_PATH().read_text(encoding='utf-8'))
    rec = (data.get('users') or {}).get(user_id)
    if not isinstance(rec, dict):
        fail('requester Mattermost id not in canonical policy', {'requester_user_id': user_id})
    status = str(rec.get('status') or 'active').lower()
    if status not in {'active', 'enabled', ''}:
        fail('requester is not an active profiled user', {'requester_user_id': user_id, 'status': status})
    return rec

def company_emails(rec: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ('mattermostEmail', 'email'):
        v = str(rec.get(key) or '').strip().lower()
        if v and '@' in v:
            out.append(v)
    nested = rec.get('appsheet') or rec.get('identity') or rec.get('hr') or {}
    if isinstance(nested, dict):
        for key in ('Company Email', 'Mattermost Email', 'Email', 'Appsheet Email'):
            v = str(nested.get(key) or '').strip().lower()
            if v and '@' in v:
                out.append(v)
    seen: set[str] = set()
    uniq: list[str] = []
    for e in out:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return uniq

def is_admin(rec: dict[str, Any]) -> bool:
    roles = [str(r) for r in rec.get('roles') or []] + [str(r) for r in rec.get('extraRoles') or []]
    uname = str(rec.get('mattermostUsername') or '').strip().lower()
    admin_names = {name for name in (_owner_username().strip().lower(), 'admin') if name}
    return 'admin' in roles or uname in admin_names

def ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"

def authorize_payload(path: str, emails: list[str], display: str) -> str:
    email_ps = ','.join((ps_quote(e) for e in emails)) or ps_quote('')
    _display_ps = ps_quote(display)
    path_ps = ps_quote(path)
    return f"\n$ErrorActionPreference = 'Continue'\n$ProgressPreference = 'SilentlyContinue'\n$result = [ordered]@{{\n  ok = $true\n  path = {path_ps}\n  errors = @()\n  sam = $null\n  display = $null\n  mail = $null\n  identities = @()\n  matched_aces = @()\n  authorized = $false\n}}\nfunction Add-Err([string]$msg) {{ $result.errors += $msg; $result.ok = $false }}\n$emails = @({email_ps})\ntry {{\n  $root = New-Object DirectoryServices.DirectoryEntry\n  $or = ($emails | ForEach-Object {{ '(mail={{0}})' -f $_ }}) -join ''\n  if ($or) {{\n    $filter = '(|' + $or + ')'\n    $searcher = New-Object DirectoryServices.DirectorySearcher($root, $filter)\n    $searcher.PropertiesToLoad.AddRange(@('sAMAccountName','mail','displayName','memberOf','userAccountControl'))\n    $hits = @($searcher.FindAll())\n    if ($hits.Count -ne 1) {{\n      Add-Err ('AD mail lookup hit_count=' + $hits.Count)\n    }} else {{\n      $hit = $hits[0]\n      $uac = 0\n      if ($hit.Properties['useraccountcontrol'].Count -gt 0) {{ $uac = [int]$hit.Properties['useraccountcontrol'][0] }}\n      if ($uac -band 2) {{ Add-Err 'AD account disabled' }}\n      $result.sam = [string]$hit.Properties['samaccountname'][0]\n      $result.mail = $(if ($hit.Properties['mail'].Count) {{ [string]$hit.Properties['mail'][0] }} else {{ $null }})\n      $result.display = $(if ($hit.Properties['displayname'].Count) {{ [string]$hit.Properties['displayname'][0] }} else {{ $null }})\n      $idents = New-Object System.Collections.Generic.List[string]\n      [void]$idents.Add('JSPD\\' + $result.sam)\n      [void]$idents.Add('JSPD\\Domain Users')\n      [void]$idents.Add('NT AUTHORITY\\Authenticated Users')\n      [void]$idents.Add('Everyone')\n      foreach ($g in $hit.Properties['memberof']) {{\n        $dn = [string]$g\n        if ($dn -match '^CN=([^,]+)') {{ [void]$idents.Add('JSPD\\' + $Matches[1]) }}\n      }}\n      $result.identities = @($idents)\n    }}\n  }} else {{ Add-Err 'no company email for AD lookup' }}\n}} catch {{ Add-Err ('AD: ' + $_.Exception.Message) }}\n\ntry {{\n  $p = {path_ps}\n  if (-not (Test-Path -LiteralPath $p)) {{ Add-Err ('Path not found or helper cannot see it: ' + $p) }}\n  elseif ($result.identities.Count -gt 0) {{\n    $acl = Get-Acl -LiteralPath $p\n    $allow = $false\n    $deny = $false\n    $set = @{{}}\n    foreach ($id in $result.identities) {{ $set[$id.ToLower()] = $true }}\n    foreach ($ace in $acl.Access) {{\n      $id = $ace.IdentityReference.Value\n      if (-not $set.ContainsKey($id.ToLower())) {{ continue }}\n      $rights = $ace.FileSystemRights.ToString()\n      $row = [ordered]@{{ identity=$id; type=$ace.AccessControlType.ToString(); rights=$rights; inherited=[bool]$ace.IsInherited }}\n      $result.matched_aces += $row\n      $readish = $rights -match 'Read|ReadAndExecute|Modify|FullControl|ListDirectory|GenericRead'\n      if ($readish -and $ace.AccessControlType.ToString() -eq 'Deny') {{ $deny = $true }}\n      if ($readish -and $ace.AccessControlType.ToString() -eq 'Allow') {{ $allow = $true }}\n    }}\n    $result.authorized = [bool]($allow -and -not $deny)\n    $result.owner = $acl.Owner\n  }}\n}} catch {{ Add-Err ('ACL: ' + $_.Exception.Message) }}\n$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath '__OUT__' -Encoding UTF8\n"

def run_helper(command: str, path: str, max_items: int, max_bytes: int) -> dict[str, Any]:
    helper = _sqlsrv()
    vals = helper.load_env()
    session, host, user, password = helper.make_session(vals)
    target = helper.unc_path(path)
    payload = helper.remote_payload(command, target, max_items, max_bytes, 'redacted-host')
    result = helper.run_via_task(session, user, password, payload, timeout=120)
    result['via'] = {'host': host, 'helper': 'sqlsrv_readonly', 'smb_identity': 'redacted-vm-helper'}
    return result

def _red_line(text: str) -> bool:
    return bool(RED_LINE_PATH_RE.search(str(text or '')))

def _read_aces(aces: list[dict[str, Any]], kind: str) -> bool:
    return any(ace.get('type') == kind and READ_RIGHTS_RE.search(str(ace.get('rights') or '')) for ace in aces)

def authorize(requester_user_id: str, path: str) -> dict[str, Any]:
    """Live NTFS Read/Write for the requester's AD account on ``path``. Every doubt is a refusal."""
    if _red_line(path):
        fail('payroll, credential, and HR-evaluation paths are not readable through PD One', {'path': path})
    rec = load_user(requester_user_id)
    helper = _sqlsrv()
    target = helper.unc_path(path)
    if is_admin(rec):
        return {'ok': True, 'authorized': True, 'admin_bypass': True, 'path': target, 'windows_sam': None, 'matched_ace_count': 0}
    emails = company_emails(rec)
    if not emails:
        fail('requester has no company email for the AD lookup', {'requester_user_id': requester_user_id})
    vals = helper.load_env()
    session, _host, user, password = helper.make_session(vals)
    raw = helper.run_via_task(session, user, password, authorize_payload(target, emails, str(rec.get('displayName') or '')), timeout=120)
    aces = [ace for ace in raw.get('matched_aces') or [] if isinstance(ace, dict)]
    errors = [str(error) for error in raw.get('errors') or []]
    authorized = bool(raw.get('authorized')) and _read_aces(aces, 'Allow') and not _read_aces(aces, 'Deny') and not errors
    result = {'ok': not errors, 'authorized': authorized, 'admin_bypass': False, 'path': target, 'windows_sam': raw.get('sam'), 'matched_ace_count': len(aces), 'matched_aces': aces}
    if not authorized:
        result['error'] = '; '.join(errors) or 'NTFS does not grant Read or Write on that path to the requester'
    return result

def _without_red_line_items(result: dict[str, Any]) -> dict[str, Any]:
    items = result.get('items')
    if not isinstance(items, list):
        return result
    kept = [item for item in items if not (isinstance(item, dict) and any(_red_line(value) for value in item.values() if isinstance(value, str)))]
    return {**result, 'items': kept, 'red_line_items_withheld': len(items) - len(kept)}

def cmd_run(args: argparse.Namespace) -> None:
    auth = authorize(args.requester_user_id, args.path)
    if args.action == 'authorize':
        print(json.dumps(auth, ensure_ascii=False, indent=2))
        return
    if not auth['authorized']:
        fail(auth.get('error') or 'not authorized', {'path': auth.get('path')})
    result = run_helper(args.action, args.path, max(1, min(int(args.max_items), 200)), max(1, min(int(args.max_bytes), 5000000)))
    summary = {key: auth.get(key) for key in ('authorized', 'admin_bypass', 'windows_sam', 'matched_ace_count')}
    print(json.dumps({**_without_red_line_items(result), 'authorization': summary, 'safety': {'read_only': True, 'writes_implemented': False}}, ensure_ascii=False, indent=2))

def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requester-user-id', required=True)
    parser.add_argument('--path', required=True)
    parser.add_argument('--action', choices=('authorize', 'list', 'stat', 'read'), default='authorize')
    parser.add_argument('--max', type=int, default=50, dest='max_items')
    parser.add_argument('--max-bytes', type=int, default=1000000)
    parser.set_defaults(func=cmd_run)
    return parser
if __name__ == '__main__':
    raise SystemExit(main())

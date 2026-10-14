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
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import os
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
sqlsrv = _PdLazyMod('sqlsrv_readonly')
sqlsrv = ExternalModule('sqlsrv_readonly', 'sqlsrv_readonly')
TOOLS = Path(__file__).resolve().parent

def PROFILE():
    return profile_root()

def USERS_PATH():
    return PROFILE() / 'policies' / 'mattermost-users.json'

def HELPER():
    return Path(resolve_configured_path('~/.hermes/scripts/sqlsrv_readonly.py'))
sys.path.append(str(HELPER().parent))
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
    return 'admin' in roles or uname in {site_text('PDONE_OWNER_MM_USERNAME'), 'admin'}

def ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"

def authorize_payload(path: str, emails: list[str], display: str) -> str:
    email_ps = ','.join((ps_quote(e) for e in emails)) or ps_quote('')
    _display_ps = ps_quote(display)
    path_ps = ps_quote(path)
    return f"\n$ErrorActionPreference = 'Continue'\n$ProgressPreference = 'SilentlyContinue'\n$result = [ordered]@{{\n  ok = $true\n  path = {path_ps}\n  errors = @()\n  sam = $null\n  display = $null\n  mail = $null\n  identities = @()\n  matched_aces = @()\n  authorized = $false\n}}\nfunction Add-Err([string]$msg) {{ $result.errors += $msg; $result.ok = $false }}\n$emails = @({email_ps})\ntry {{\n  $root = New-Object DirectoryServices.DirectoryEntry\n  $or = ($emails | ForEach-Object {{ '(mail={{0}})' -f $_ }}) -join ''\n  if ($or) {{\n    $filter = '(|' + $or + ')'\n    $searcher = New-Object DirectoryServices.DirectorySearcher($root, $filter)\n    $searcher.PropertiesToLoad.AddRange(@('sAMAccountName','mail','displayName','memberOf','userAccountControl'))\n    $hits = @($searcher.FindAll())\n    if ($hits.Count -ne 1) {{\n      Add-Err ('AD mail lookup hit_count=' + $hits.Count)\n    }} else {{\n      $hit = $hits[0]\n      $uac = 0\n      if ($hit.Properties['useraccountcontrol'].Count -gt 0) {{ $uac = [int]$hit.Properties['useraccountcontrol'][0] }}\n      if ($uac -band 2) {{ Add-Err 'AD account disabled' }}\n      $result.sam = [string]$hit.Properties['samaccountname'][0]\n      $result.mail = $(if ($hit.Properties['mail'].Count) {{ [string]$hit.Properties['mail'][0] }} else {{ $null }})\n      $result.display = $(if ($hit.Properties['displayname'].Count) {{ [string]$hit.Properties['displayname'][0] }} else {{ $null }})\n      $idents = New-Object System.Collections.Generic.List[string]\n      [void]$idents.Add('JSPD\\' + $result.sam)\n      [void]$idents.Add('JSPD\\Domain Users')\n      [void]$idents.Add('NT AUTHORITY\\Authenticated Users')\n      [void]$idents.Add('Everyone')\n      foreach ($g in $hit.Properties['memberof']) {{\n        $dn = [string]$g\n        if ($dn -match '^CN=([^,]+)') {{ [void]$idents.Add('JSPD\\' + $Matches[1]) }}\n      }}\n      $result.identities = @($idents)\n    }}\n  }} else {{ Add-Err 'no company email for AD lookup' }}\n}} catch {{ Add-Err ('AD: ' + $_.Exception.Message) }}\n\ntry {{\n  $p = {path_ps}\n  if (-not (Test-Path -LiteralPath $p)) {{ Add-Err ('Path not found or helper cannot see it: ' + $p) }}\n  elseif ($result.identities.Count -gt 0) {{\n    $acl = Get-Acl -LiteralPath $p\n    $allow = $false\n    $deny = $false\n    $set = @{{}}\n    foreach ($id in $result.identities) {{ $set[$id.ToLower()] = $true }}\n    foreach ($ace in $acl.Access) {{\n      $id = $ace.IdentityReference.Value\n      if (-not $set.ContainsKey($id.ToLower())) {{ continue }}\n      $rights = $ace.FileSystemRights.ToString()\n      $row = [ordered]@{{ identity=$id; type=$ace.AccessControlType.ToString(); rights=$rights; inherited=[bool]$ace.IsInherited }}\n      $result.matched_aces += $row\n      $readish = $rights -match 'Read|ReadAndExecute|Modify|FullControl|ListDirectory|GenericRead'\n      if ($readish -and $ace.AccessControlType.ToString() -eq 'Deny') {{ $deny = $true }}\n      if ($readish -and $ace.AccessControlType.ToString() -eq 'Allow') {{ $allow = $true }}\n    }}\n    $result.authorized = [bool]($allow -and -not $deny)\n    $result.owner = $acl.Owner\n  }}\n}} catch {{ Add-Err ('ACL: ' + $_.Exception.Message) }}\n$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath '__OUT__' -Encoding UTF8\n"

def run_helper(command: str, path: str, max_items: int, max_bytes: int) -> dict[str, Any]:
    vals = sqlsrv.load_env()
    session, host, user, password = sqlsrv.make_session(vals)
    target = sqlsrv.unc_path(path)
    payload = sqlsrv.remote_payload(command, target, max_items, max_bytes, 'redacted-host')
    result = sqlsrv.run_via_task(session, user, password, payload, timeout=120)
    result['via'] = {'host': host, 'helper': 'sqlsrv_readonly', 'smb_identity': 'redacted-vm-helper'}
    return result

def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requester-user-id', required=True)
    parser.add_argument('--path', required=True)
    parser.add_argument('--action', choices=('authorize', 'list', 'stat', 'read'), default='authorize')
    parser.add_argument('--max', type=int, default=50, dest='max_items')
    parser.add_argument('--max-bytes', type=int, default=1000000)
    return parser

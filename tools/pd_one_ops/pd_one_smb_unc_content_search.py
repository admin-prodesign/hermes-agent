#!/usr/bin/env python3
"""Ticket-bound read-only recursive UNC content search through redacted-vm."""
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
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable
sqlsrv = ExternalModule('sqlsrv_readonly', 'sqlsrv_readonly')

def PROFILE_ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))

def LEDGER_TOOLS():
    return PROFILE_ROOT() / 'legacy-openclaw/workspace/tools'

def HELPER():
    return Path(resolve_configured_path('~/.hermes/scripts/sqlsrv_readonly.py'))

def ACL_TOOL():
    return PROFILE_ROOT() / 'tools/pd_one_sqlsrv_windows_acl_read.py'

def POLICY_CACHE():
    return PROFILE_ROOT() / 'policy-cache/mattermost/users'
STANDING_AOP_ROOT = '\\\\redacted-host\\管理部\\aop計劃'
ALLOWED_EXTENSIONS = {'.docx', '.xlsx', '.txt', '.csv', '.xml'}
MAX_FILES = 400
MAX_HITS = 40
MAX_FILE_BYTES = 2000000
TICKET_RE = re.compile('^PDAPP-\\d{8}-[A-F0-9]{8}$')
USER_ID_RE = re.compile('^[a-z0-9]{26}$')
RED_LINE_PATH_RE = re.compile('薪資|payroll|password|密碼|credential|\\.env|考核|evaluation|bonus|獎金|payslip', re.I)
if str(LEDGER_TOOLS()) not in sys.path:
    sys.path.append(str(LEDGER_TOOLS()))
if str(HELPER().parent) not in sys.path:
    sys.path.append(str(HELPER().parent))
from admin_approval_tickets import ApprovalLedger

def fail(message: str, code: int=2) -> None:
    print(json.dumps({'status': 'error', 'error': message}, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(code)

def emit(payload: dict[str, Any]) -> None:
    from tools.pd_one_ops.hr_guard import guard_hr_payload
    payload = guard_hr_payload(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

def normalize_unc(raw: str) -> str:
    raw = str(raw or '').strip().replace('/', '\\')
    server = 'redacted-host'
    prefix = '\\\\' + server.lower() + '\\'
    if raw.startswith('\\\\'):
        if not raw.lower().startswith(prefix):
            fail(f'Refusing non-{server} UNC path: {raw}')
        path = raw
    else:
        path = '\\\\' + server + '\\' + raw.lstrip('\\')
    rest = path[len('\\\\' + server + '\\'):]
    parts = [part for part in rest.split('\\') if part]
    if any((part in ('.', '..') for part in parts)):
        fail('Refusing path with . or .. components')
    if any((':' in part for part in parts)):
        fail("Refusing path component containing ':'")
    return path

def assert_sqlsrv(path: str) -> str:
    normalized = normalize_unc(path)
    if RED_LINE_PATH_RE.search(normalized):
        fail(f'path matches a PD One red-line class: {normalized}')
    return normalized

def under_root(path: str, root: str) -> bool:
    path_l = path.lower()
    root_l = normalize_unc(root).lower()
    return path_l == root_l or path_l.startswith(root_l + '\\')

def standing_policy_allows(requester_user_id: str, root: str) -> bool:
    if not USER_ID_RE.fullmatch(requester_user_id or ''):
        return False
    cache = POLICY_CACHE() / f'{requester_user_id}.json'
    try:
        data = json.loads(cache.read_text(encoding='utf-8'))
    except Exception:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return False
    if not isinstance(data, dict) or data.get('found') is False or data.get('active') is False:
        return False
    grant = str((data.get('dataAccess') or {}).get('managementAopPlanSmbSearch') or '')
    if not grant or 'deny' in grant.lower():
        return False
    return under_root(root, STANDING_AOP_ROOT)

def ntfs_authorize(requester_user_id: str, root: str) -> dict[str, Any]:
    proc = subprocess.run([str(ACL_TOOL()), '--requester-user-id', requester_user_id, '--path', root, '--action', 'authorize'], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False)
    try:
        payload = json.loads(proc.stdout or '{}')
    except json.JSONDecodeError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        payload = {'ok': False, 'authorized': False, 'error': (proc.stderr or proc.stdout or 'ntfs authorize failed')[:500]}
    if not isinstance(payload, dict):
        payload = {'ok': False, 'authorized': False, 'error': 'ntfs authorize returned non-object'}
    payload.setdefault('authorized', False)
    return payload

def authorize_named_root(*, root: str, requester_user_id: str='', ticket_id: str='', terms: list[str] | None=None, ntfs_fn: Callable[[str, str], dict[str, Any]] | None=None) -> dict[str, Any]:
    normalized = assert_sqlsrv(root)
    reasons: list[str] = []
    if ticket_id:
        authorize_ticket(ticket_id, normalized, terms or [])
        reasons.append('ticket')
        return {'root': normalized, 'authorized': True, 'via': reasons}
    if requester_user_id and standing_policy_allows(requester_user_id, normalized):
        reasons.append('standing_managementAopPlanSmbSearch')
        return {'root': normalized, 'authorized': True, 'via': reasons}
    if requester_user_id:
        auth = (ntfs_fn or ntfs_authorize)(requester_user_id, normalized)
        if auth.get('authorized'):
            reasons.append('ntfs')
            return {'root': normalized, 'authorized': True, 'via': reasons, 'ntfs': {k: auth.get(k) for k in ('windows_sam', 'matched_ace_count', 'admin_bypass')}}
        fail(str(auth.get('error') or 'NTFS does not grant Read/Write on that named UNC'))
    fail('content search requires --requester-user-id (NTFS or standing grant) or an executable --ticket-id')
    raise AssertionError('unreachable')

def authorize_ticket(ticket_id: str, root: str, terms: list[str]) -> dict[str, Any]:
    if not TICKET_RE.fullmatch(ticket_id):
        fail('ticket_id must look like PDAPP-YYYYMMDD-XXXXXXXX')
    ticket = ApprovalLedger().get(ticket_id)
    grant = ticket.get('approval_grant') or {}
    caps = set(grant.get('allowed_capabilities') or [])
    if ticket.get('status') not in {'approved', 'queued', 'in_progress'}:
        fail(f'ticket {ticket_id} is not executable: {ticket.get('status')}')
    if grant.get('status') != 'active' or 'smb_unc_content_search' not in caps:
        fail(f'ticket {ticket_id} grant does not include smb_unc_content_search')
    bound = ' '.join([json.dumps(ticket.get('implementation_plan') or {}, ensure_ascii=False), str(ticket.get('requested_action') or ''), json.dumps(ticket.get('bound_resources') or [], ensure_ascii=False)]).lower()
    bound_ids = []
    for resource in ticket.get('bound_resources') or []:
        rid = str(resource.get('id') or '')
        if rid:
            bound_ids.append(normalize_unc(rid).lower())
    if root.lower() not in bound_ids and root.lower() not in bound.replace('/', '\\'):
        fail('ticket bound scope does not include the exact UNC root')
    for term in terms:
        if term.lower() not in bound:
            fail(f'ticket bound scope does not include keyword {term!r}')
    return ticket

def search_payload(root: str, terms: list[str], match_mode: str, max_files: int, max_hits: int, max_bytes: int) -> str:

    def ps_quote(value: str) -> str:
        return "'" + str(value).replace("'", "''") + "'"
    term_ps = ','.join((ps_quote(term) for term in terms))
    ext_ps = ','.join((ps_quote(ext) for ext in sorted(ALLOWED_EXTENSIONS)))
    return f"\n$ErrorActionPreference = 'Continue'\n$ProgressPreference = 'SilentlyContinue'\n$result = [ordered]@{{\n  ok = $true\n  command = 'search'\n  target = {ps_quote(root)}\n  match_mode = {ps_quote(match_mode)}\n  identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name\n  computer = $env:COMPUTERNAME\n  timestamp = (Get-Date).ToString('o')\n  items = @()\n  unscanned = @()\n  errors = @()\n  files_scanned = 0\n}}\nfunction Add-Err([string]$msg) {{ $result.errors += $msg; $result.ok = $false }}\n$terms = @({term_ps})\n$exts = @({ext_ps})\ntry {{\n  if (-not (Test-Path -LiteralPath {ps_quote(root)})) {{ Add-Err 'Path not found or access denied'; throw 'missing' }}\n  Add-Type -AssemblyName System.IO.Compression.FileSystem\n  $files = Get-ChildItem -LiteralPath {ps_quote(root)} -Recurse -File -Force -ErrorAction SilentlyContinue |\n    Where-Object {{ $exts -contains $_.Extension.ToLower() }} |\n    Select-Object -First {int(max_files)}\n  foreach ($f in @($files)) {{\n    $result.files_scanned++\n    $matched = @()\n    $unsearchable = $false\n    $hay = ''\n    if ($f.Length -gt {int(max_bytes)}) {{\n      $unsearchable = $true\n    }} else {{\n      try {{\n        $ext = $f.Extension.ToLower()\n        if ($ext -in @('.docx','.xlsx')) {{\n          $zip = [IO.Compression.ZipFile]::OpenRead($f.FullName)\n          try {{\n            foreach ($entry in $zip.Entries) {{\n              if ($entry.FullName -match '\\.(xml|rels)$') {{\n                $stream = $entry.Open()\n                $reader = New-Object IO.StreamReader($stream)\n                $hay += $reader.ReadToEnd()\n                $reader.Close()\n                $stream.Close()\n              }}\n            }}\n          }} finally {{ $zip.Dispose() }}\n        }} elseif ($ext -in @('.pdf','.doc','.xls')) {{\n          $unsearchable = $true\n        }} else {{\n          $hay = [IO.File]::ReadAllText($f.FullName)\n        }}\n      }} catch {{\n        $unsearchable = $true\n      }}\n      if (-not $unsearchable) {{\n        foreach ($t in $terms) {{\n          if ($hay.IndexOf($t, [StringComparison]::OrdinalIgnoreCase) -ge 0) {{ $matched += $t }}\n        }}\n      }}\n    }}\n    $hit = $false\n    if ($unsearchable) {{\n      $result.unscanned += [ordered]@{{ full_name=$f.FullName; length=$f.Length; reason='unsupported_or_too_large' }}\n    }} elseif ({ps_quote(match_mode)} -eq 'AND') {{\n      $hit = (@($matched).Count -eq @($terms).Count)\n    }} else {{\n      $hit = (@($matched).Count -gt 0)\n    }}\n    if ($hit) {{\n      $result.items += [ordered]@{{\n        full_name = $f.FullName\n        length = $f.Length\n        last_write_time = $f.LastWriteTime.ToString('o')\n        matched_terms = $matched\n      }}\n    }}\n    if (@($result.items).Count -ge {int(max_hits)}) {{ break }}\n  }}\n}} catch {{\n  if ($_.Exception.Message -ne 'missing') {{ Add-Err ($_.Exception.Message) }}\n}}\n$result.hit_count = @($result.items).Count\n$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath '__OUT__' -Encoding UTF8\n"

def search(*, root: str, terms: list[str], match_mode: str='OR', ticket_id: str | None=None, requester_user_id: str='', max_files: int=MAX_FILES, max_hits: int=MAX_HITS, runner: Any | None=None, ntfs_fn: Callable[[str, str], dict[str, Any]] | None=None) -> dict[str, Any]:
    match_mode = match_mode.upper()
    if match_mode not in {'AND', 'OR'}:
        fail('match_mode must be AND or OR')
    cleaned = [str(term).strip() for term in terms if str(term).strip()]
    if not cleaned or len(cleaned) > 8:
        fail('provide 1-8 search terms')
    if any((len(term) > 80 for term in cleaned)):
        fail('search terms must be <= 80 characters')
    auth = authorize_named_root(root=root, requester_user_id=requester_user_id, ticket_id=ticket_id or '', terms=cleaned, ntfs_fn=ntfs_fn)
    root = auth['root']
    max_files = max(1, min(int(max_files), MAX_FILES))
    max_hits = max(1, min(int(max_hits), MAX_HITS))
    payload = search_payload(root, cleaned, match_mode, max_files, max_hits, MAX_FILE_BYTES)
    if runner is not None:
        raw = runner(payload)
    else:
        winrm_site = Path(resolve_configured_path('~/.hermes/venvs/winrm/lib/python3.12/site-packages'))
        if str(winrm_site) not in sys.path:
            sys.path.append(str(winrm_site))
        import sqlsrv_readonly as sqlsrv
        vals = sqlsrv.load_env()
        session, host, user, password = sqlsrv.make_session(vals)
        raw = sqlsrv.run_via_task(session, user, password, payload, timeout=180)
        raw.setdefault('via', {'host': host, 'winrm_user_len': len(user)})
    hits = raw.get('items') or []
    return {'status': 'ok' if raw.get('ok', True) else 'error', 'capability': 'smb_unc_content_search', 'root': root, 'terms': cleaned, 'match_mode': match_mode, 'files_scanned': raw.get('files_scanned', 0), 'hit_count': len(hits), 'hits': hits[:max_hits], 'unscanned_count': len(raw.get('unscanned') or []), 'unscanned': (raw.get('unscanned') or [])[:20], 'errors': raw.get('errors') or [], 'ticket_id': ticket_id, 'requester_user_id': requester_user_id, 'authorization': auth, 'safety': {'read_only': True, 'sqlsrv_writes_forbidden': True, 'ntfs_or_standing_or_ticket': True, 'external_delivery': False}}

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--term', action='append', required=True)
    parser.add_argument('--match-mode', default='OR', choices=['AND', 'OR'])
    parser.add_argument('--ticket-id')
    parser.add_argument('--requester-user-id', default='')
    parser.add_argument('--max-files', type=int, default=MAX_FILES)
    parser.add_argument('--max-hits', type=int, default=MAX_HITS)
    return parser

def main(argv: list[str] | None=None) -> int:
    args = build_parser().parse_args(argv)
    emit(search(root=args.root, terms=args.term, match_mode=args.match_mode, ticket_id=args.ticket_id, requester_user_id=args.requester_user_id, max_files=args.max_files, max_hits=args.max_hits))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""PD One dispatcher: map one function twin name to an existing call_pd_*.py caller.

Not employee-facing. Fail closed without requester id except --smoke.
Twins never DM employees. Do not mint pd-marketing.
"""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

def TOOLS():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/tools'))

def TWINS():
    return {'hr': {'profile': 'pd-hr', 'caller': 'call_pd_hr.py', 'token': 'PD_HR_OK', 'group': site_text('PDONE_EMAIL_HR')}, 'finance': {'profile': 'pd-finance', 'caller': 'call_pd_finance.py', 'token': 'PD_FINANCE_OK', 'group': site_text('PDONE_EMAIL_FINANCE')}, 'sales': {'profile': 'pd-sales', 'caller': 'call_pd_sales.py', 'token': 'PD_SALES_OK', 'group': site_text('PDONE_EMAIL_SALES')}, 'it': {'profile': 'pd-it', 'caller': 'call_pd_it.py', 'token': 'PD_IT_OK', 'group': site_text('PDONE_EMAIL_IT')}, 'molding': {'profile': 'pd-molding', 'caller': 'call_pd_molding.py', 'token': 'PD_MOLDING_OK', 'group': site_text('PDONE_EMAIL_MOLDING_STAFF')}, 'printing': {'profile': 'pd-printing', 'caller': 'call_pd_printing.py', 'token': 'PD_PRINTING_OK', 'group': site_text('PDONE_EMAIL_PRINTING')}, 'moldrepair': {'profile': 'pd-moldrepair', 'caller': 'call_pd_moldrepair.py', 'token': 'PD_MOLDREPAIR_OK', 'group': site_text('PDONE_EMAIL_MOLD_REPAIR')}, 'engineering': {'profile': 'pd-engineering', 'caller': 'call_pd_engineering.py', 'token': 'PD_ENGINEERING_OK', 'group': site_text('PDONE_EMAIL_RD')}, 'qa': {'profile': 'pd-qa', 'caller': 'call_pd_qa.py', 'token': 'PD_QA_OK', 'group': site_text('PDONE_EMAIL_QC')}, 'warehouse': {'profile': 'pd-warehouse', 'caller': 'call_pd_warehouse.py', 'token': 'PD_WAREHOUSE_OK', 'group': site_text('PDONE_EMAIL_WAREHOUSE')}, 'procurement': {'profile': 'pd-procurement', 'caller': 'call_pd_procurement.py', 'token': 'PD_PROCUREMENT_OK', 'group': site_text('PDONE_EMAIL_PROCUREMENT')}}
PARKED = frozenset({'marketing', 'pd-marketing'})

def _resolve(twin: str) -> tuple[str, dict[str, str]] | None:
    raw = (twin or '').strip().lower()
    if not raw:
        return None
    if raw.startswith('pd-'):
        raw = raw[3:]
    if raw in TWINS():
        return (raw, TWINS()[raw])
    return None

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description='Dispatch a PD One function-twin consult to an existing caller.')
    parser.add_argument('--twin', required=True, help='Twin short name or pd-<short>')
    parser.add_argument('--requester-user-id', default='', help='Exact Mattermost user id')
    parser.add_argument('--task', default='', help='Question for the twin')
    parser.add_argument('--excerpts', default='', help='Optional PD One-authorized excerpts')
    parser.add_argument('--policy-json', default='', help='Optional verified policy JSON object')
    parser.add_argument('--smoke', action='store_true', help='Operator smoke; skip employee auth')
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--json', action='store_true', help='Wrap caller stdout/stderr as a JSON object on stdout')
    args = parser.parse_args(argv)
    twin_raw = str(args.twin or '').strip().lower()
    if twin_raw in PARKED or twin_raw.removeprefix('pd-') in PARKED:
        print('unknown twin (pd-marketing is parked, not a twin)', file=sys.stderr)
        return 2
    resolved = _resolve(args.twin)
    if resolved is None:
        print('unknown twin', file=sys.stderr)
        return 2
    short, meta = resolved
    caller = TOOLS() / meta['caller']
    if not caller.is_file():
        print(f'caller missing: {caller}', file=sys.stderr)
        return 2
    if args.smoke:
        cmd = [sys.executable, str(caller), '--smoke', '--timeout', str(args.timeout)]
    else:
        requester = str(args.requester_user_id or '').strip()
        task = str(args.task or '').strip()
        if not requester or not task:
            print('requester-user-id and task are required unless --smoke', file=sys.stderr)
            return 2
        cmd = [sys.executable, str(caller), '--requester-user-id', requester, '--task', task, '--timeout', str(args.timeout)]
        excerpts = str(args.excerpts or '')
        if excerpts:
            cmd.extend(['--excerpts', excerpts])
        policy = str(args.policy_json or '').strip()
        if policy and short != 'hr':
            cmd.extend(['--policy-json', policy])
    env = os.environ.copy()
    env['PATH'] = resolve_configured_path('~/.local/bin:') + env.get('PATH', '')
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=max(30, int(args.timeout) + 30), env=env)
    except subprocess.TimeoutExpired:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        print(f'PD_{short.upper()}_TIMEOUT', file=sys.stderr)
        return 4
    if args.json:
        payload = {'ok': proc.returncode == 0, 'twin': short, 'profile': meta['profile'], 'caller': str(caller), 'exit_code': proc.returncode, 'stdout': proc.stdout or '', 'stderr': proc.stderr or ''}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + '\n')
        return proc.returncode
    if proc.stdout:
        sys.stdout.write(proc.stdout)
        if not proc.stdout.endswith('\n'):
            sys.stdout.write('\n')
    if proc.returncode != 0 and proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode
if __name__ == '__main__':
    raise SystemExit(main())

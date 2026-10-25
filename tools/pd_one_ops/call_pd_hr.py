#!/usr/bin/env python3
"""PD One -> pd-hr specialist call. Not employee-facing."""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

def PDONE_ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))

def HR_LOOKUP():
    return PDONE_ROOT() / 'tools/pd_one_hr_policy_lookup.py'

def HERMES():
    return Path(resolve_configured_path('~/.local/bin/hermes'))
REQUIRED_SCOPE = 'hr-policy-readonly'
SCHEMA = 'pd-one-pd-hr/v1'

def _load_hr_lookup():
    import importlib.util
    spec = importlib.util.spec_from_file_location('pd_one_hr_policy_lookup', HR_LOOKUP())
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load {HR_LOOKUP()}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _reduced_policy(policy: dict[str, Any]) -> dict[str, Any]:
    return {'found': True, 'active': bool(policy.get('active')), 'roles': list(policy.get('roles') or []), 'safeScopes': list(policy.get('safeScopes') or []), 'required_scope': REQUIRED_SCOPE}

def _build_prompt(*, task: str, requester_user_id: str, policy: dict[str, Any], excerpts: str) -> str:
    packet = {'schema': SCHEMA, 'origin': 'pdone', 'bridge': 'call_pd_hr', 'requester_user_id': requester_user_id, 'verified_policy': _reduced_policy(policy), 'authorized_excerpts': excerpts, 'task': task}
    return 'PD One is invoking PD HR. Honor SOUL.md call contract.\n\n' + json.dumps(packet, ensure_ascii=False, indent=2)

def _build_smoke_prompt() -> str:
    packet = {'schema': SCHEMA, 'origin': 'pdone', 'bridge': 'call_pd_hr', 'smoke': True, 'task': 'Reply with exactly: PD_HR_OK'}
    return 'PD One is invoking PD HR. Honor SOUL.md call contract.\n\n' + json.dumps(packet, ensure_ascii=False, indent=2)

def _invoke_pd_hr(prompt: str, timeout: int) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env['PATH'] = resolve_configured_path('~/.local/bin:') + env.get('PATH', '')
    return subprocess.run([str(HERMES()), '--profile', 'pd-hr', 'chat', '-Q', '-q', prompt, '--max-turns', '8'], check=False, capture_output=True, text=True, timeout=timeout, env=env)

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description='Call the internal pd-hr bot from PD One only.')
    parser.add_argument('--requester-user-id', default='', help='Exact Mattermost user id')
    parser.add_argument('--task', default='', help='HR question for pd-hr')
    parser.add_argument('--excerpts', default='', help='Optional PD One-authorized source excerpts')
    parser.add_argument('--smoke', action='store_true', help='Operator smoke test; skip employee auth')
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args(argv)
    if args.smoke:
        prompt = _build_smoke_prompt()
    else:
        requester = str(args.requester_user_id or '').strip()
        task = str(args.task or '').strip()
        if not requester or not task:
            print('requester-user-id and task are required unless --smoke', file=sys.stderr)
            return 2
        try:
            policy = _load_hr_lookup().authorize_requester(requester)
        except PermissionError as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            print(f'PD_HR_DENIED: {exc}', file=sys.stderr)
            return 3
        prompt = _build_prompt(task=task, requester_user_id=requester, policy=policy, excerpts=str(args.excerpts or ''))
    try:
        proc = _invoke_pd_hr(prompt, args.timeout)
    except subprocess.TimeoutExpired:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        print('PD_HR_TIMEOUT', file=sys.stderr)
        return 4
    if proc.stdout:
        sys.stdout.write(proc.stdout)
        if not proc.stdout.endswith('\n'):
            sys.stdout.write('\n')
    if proc.returncode != 0:
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        return proc.returncode
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

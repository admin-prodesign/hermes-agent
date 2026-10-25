#!/usr/bin/env python3
"""PD One -> pd-warehouse specialist call. Not employee-facing."""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

def HERMES():
    return Path(resolve_configured_path('~/.local/bin/hermes'))
SCHEMA = 'pd-one-pd-warehouse/v1'
PROFILE = 'pd-warehouse'
BRIDGE = 'call_pd_warehouse'
SMOKE_TOKEN = 'PD_WAREHOUSE_OK'

def _build_prompt(*, task: str, requester_user_id: str, policy: dict, excerpts: str) -> str:
    packet = {'schema': SCHEMA, 'origin': 'pdone', 'bridge': BRIDGE, 'requester_user_id': requester_user_id, 'verified_policy': policy, 'authorized_excerpts': excerpts, 'task': task}
    return 'PD One is invoking PD Warehouse. Honor SOUL.md call contract.\n\n' + json.dumps(packet, ensure_ascii=False, indent=2)

def _build_smoke_prompt() -> str:
    packet = {'schema': SCHEMA, 'origin': 'pdone', 'bridge': BRIDGE, 'smoke': True, 'task': f'Reply with exactly: {SMOKE_TOKEN}'}
    return 'PD One is invoking PD Warehouse. Honor SOUL.md call contract.\n\n' + json.dumps(packet, ensure_ascii=False, indent=2)

def _invoke(prompt: str, timeout: int) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env['PATH'] = resolve_configured_path('~/.local/bin:') + env.get('PATH', '')
    return subprocess.run([str(HERMES()), '--profile', PROFILE, 'chat', '-Q', '-q', prompt, '--max-turns', '8'], check=False, capture_output=True, text=True, timeout=timeout, env=env)

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description='Call the internal pd-warehouse bot from PD One only.')
    parser.add_argument('--requester-user-id', default='', help='Exact Mattermost user id')
    parser.add_argument('--task', default='', help='Warehouse / logistics question for pd-warehouse')
    parser.add_argument('--excerpts', default='', help='Optional PD One-authorized source excerpts')
    parser.add_argument('--policy-json', default='', help='Optional verified policy JSON object')
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
        policy: dict = {'found': True, 'note': 'pd-one-origin-packet'}
        raw = str(args.policy_json or '').strip()
        if raw:
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                print('policy-json must be an object', file=sys.stderr)
                return 2
            policy = loaded
        prompt = _build_prompt(task=task, requester_user_id=requester, policy=policy, excerpts=str(args.excerpts or ''))
    try:
        proc = _invoke(prompt, args.timeout)
    except subprocess.TimeoutExpired:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        print('PD_WAREHOUSE_TIMEOUT', file=sys.stderr)
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

#!/usr/bin/env python3
"""Small helper for secondary PD One -> PD Neo federation alerts.

Hermes-profile copy for PD One migrated governance tools. Primary human alert
paths should run first. This helper is intentionally best-effort: the bridge
script itself queues on webhook delivery failure, and callers must not fail their
original job only because Hermes/PD Neo is down.
"""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import os
import subprocess
import sys
from pathlib import Path

def WORKSPACE():
    return Path(resolve_configured_path('~/.openclaw/workspace'))

def BRIDGE():
    return WORKSPACE() / 'tools/pd_one_failure_to_hermes.py'

def emit_pd_one_event(*, source: str, summary: str, detail: str='', event_type: str='pd-one.failure', severity: str='error', command: str='', privacy_scope: str='admin-only', desired_response_mode: str='admin_triage', what_was_tried: list[str] | None=None, source_platform: str='', source_channel_id: str='', source_thread_id: str='', source_post_id: str='', run_id: str='', idempotency_key: str='', dry_run: bool=False, timeout: int=15) -> subprocess.CompletedProcess[str] | None:
    """Emit a best-effort federation event without breaking the primary path."""
    if not BRIDGE().exists():
        print(f'PD One federation bridge missing: {BRIDGE()}', file=sys.stderr)
        return None
    cmd = [sys.executable, str(BRIDGE()), '--source', source, '--summary', summary, '--detail', detail[-12000:], '--event-type', event_type, '--severity', severity, '--privacy-scope', privacy_scope, '--desired-response-mode', desired_response_mode, '--command', command]
    for item in what_was_tried or []:
        if item:
            cmd.extend(['--what-was-tried', item])
    optional_args = {'--source-platform': source_platform, '--source-channel-id': source_channel_id, '--source-thread-id': source_thread_id, '--source-post-id': source_post_id, '--run-id': run_id, '--idempotency-key': idempotency_key}
    for flag, value in optional_args.items():
        if value:
            cmd.extend([flag, value])
    if dry_run:
        cmd.append('--dry-run')
    try:
        cp = subprocess.run(cmd, cwd=str(WORKSPACE()), text=True, capture_output=True, timeout=timeout, check=False)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        print(f'PD One federation bridge invocation failed: {exc}', file=sys.stderr)
        return None
    if dry_run and cp.stdout:
        print(cp.stdout, end='' if cp.stdout.endswith('\n') else '\n')
    if cp.returncode != 0:
        detail_text = (cp.stderr or cp.stdout or '').strip()
        print(f'PD One federation bridge returned {cp.returncode}: {detail_text[:500]}', file=sys.stderr)
    return cp

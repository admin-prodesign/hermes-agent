from __future__ import annotations
__all__ = ['cmd_docx_exact_text_patch', '_load_pptx_exact_text_patch_module', 'cmd_pptx_exact_text_patch', '_load_pptx_from_template_module', 'cmd_pptx_from_template', '_load_sip_thread_index_module', 'cmd_sip_thread_index_build', '_sip_thread_index_input_paths', '_sip_thread_index_noise_marker', 'cmd_sip_thread_index_audit', '_load_typhoon_automation_module', '_summarize_typhoon_plan', '_run_typhoon_sweep_case', 'cmd_typhoon_automation', '_load_docs_api_module', 'cmd_drive_acl_authorize', 'cmd_portal_module_change_authorize', 'cmd_work_manual_change_authorize', 'cmd_google_docs_metadata_inspect', 'cmd_yammer_archive_search', 'main', 'build_parser']
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import argparse
import base64
import calendar
import contextlib
import collections
import csv
import difflib
import fnmatch
import importlib.util
import hashlib
import html
import math
import io
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import types
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from tools.pd_one_ops.pd_one_safe_ops_part0 import *
from tools.pd_one_ops.pd_one_safe_ops_part1 import *
from tools.pd_one_ops.pd_one_safe_ops_part2 import *
from tools.pd_one_ops.pd_one_safe_ops_part3 import *

def cmd_docx_exact_text_patch(args: argparse.Namespace) -> None:
    """Inspect or stage a bounded set of exact visible-text DOCX replacements."""
    try:
        result = _load_ecrn_docx_patch_module().inspect_or_stage_many(action=args.action, input_path=args.input, replacements=args.replace, output_path=args.out, source_sha256=args.source_sha256, overwrite=bool(args.overwrite))
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(str(exc))
    emit(result)
    if result.get('status') != 'ok':
        raise SystemExit(1)

def _load_pptx_exact_text_patch_module() -> Any:
    if not PPTX_EXACT_TEXT_PATCH_SCRIPT().is_file():
        fail(f'PPTX exact-text patch wrapper not found: {PPTX_EXACT_TEXT_PATCH_SCRIPT()}')
    spec = importlib.util.spec_from_file_location('pdone_pptx_ops', PPTX_EXACT_TEXT_PATCH_SCRIPT())
    if spec is None or spec.loader is None:
        fail(f'could not load PPTX exact-text patch wrapper: {PPTX_EXACT_TEXT_PATCH_SCRIPT()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def cmd_pptx_exact_text_patch(args: argparse.Namespace) -> None:
    """Inspect or stage a bounded set of exact visible-text PPTX replacements."""
    _pairs = args.replace or []
    try:
        result = _load_pptx_exact_text_patch_module().inspect_or_stage_many(action=args.action, input_path=args.input, replacements=args.replace, output_path=args.out, source_sha256=args.source_sha256, overwrite=bool(args.overwrite))
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(str(exc))
    emit(result)
    if result.get('status') != 'ok':
        raise SystemExit(1)

def _load_pptx_from_template_module() -> Any:
    if not PPTX_FROM_TEMPLATE_SCRIPT().is_file():
        fail(f'PPTX from-template wrapper not found: {PPTX_FROM_TEMPLATE_SCRIPT()}')
    tools_dir = str(ROOT() / 'tools')
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    spec = importlib.util.spec_from_file_location('pdone_pptx_from_template', PPTX_FROM_TEMPLATE_SCRIPT())
    if spec is None or spec.loader is None:
        fail(f'could not load PPTX from-template wrapper: {PPTX_FROM_TEMPLATE_SCRIPT()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def cmd_pptx_from_template(args: argparse.Namespace) -> None:
    """Inspect or stage a PPTX cloned from or restamped onto a POTX/PPTX template."""
    try:
        result = _load_pptx_from_template_module().inspect_or_stage(action=args.action, mode=args.mode, template_path=args.template, source_path=args.source, output_path=args.out, source_sha256=args.source_sha256, overwrite=bool(args.overwrite))
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(str(exc))
    emit(result)
    if result.get('status') != 'ok':
        raise SystemExit(1)

def _load_sip_thread_index_module() -> Any:
    if not SIP_THREAD_INDEX_SCRIPT().exists():
        fail(f'sip thread index builder not found: {SIP_THREAD_INDEX_SCRIPT()}')
    spec = importlib.util.spec_from_file_location('pdone_sip_thread_index_build', SIP_THREAD_INDEX_SCRIPT())
    if spec is None or spec.loader is None:
        fail(f'unable to load sip thread index builder: {SIP_THREAD_INDEX_SCRIPT()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def cmd_sip_thread_index_build(args: argparse.Namespace) -> None:
    """Build and verify the sanitized SIP討論串 index workbook from fixed JSON inputs."""
    try:
        module = _load_sip_thread_index_module()
        module.BASE = SIP_THREAD_INDEX_ROOT()
        module.INPUT_GLOBS = list(SIP_THREAD_INDEX_INPUT_GLOBS)
        module.OUTPUT = SIP_THREAD_INDEX_OUTPUT()
        SIP_THREAD_INDEX_OUTPUT().parent.mkdir(parents=True, exist_ok=True)
        rows = module.load_rows()
        built_path = Path(module.build(rows))
        verification = module.verify(built_path, len(rows))
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'sip thread index build failed: {exc!r}')
    emit({'status': 'ok', 'capability': 'pd_one_sip_thread_index_build', 'script': str(SIP_THREAD_INDEX_SCRIPT()), 'input_root': str(SIP_THREAD_INDEX_ROOT()), 'input_globs': list(SIP_THREAD_INDEX_INPUT_GLOBS), 'output': str(built_path), 'row_count': len(rows), 'verification': verification, 'safety': {'shell_used': False, 'local_file_write': True, 'fixed_input_root': True, 'openxml_verification_required': True}})

def _sip_thread_index_input_paths() -> list[Path]:
    paths: list[Path] = []
    for pattern in SIP_THREAD_INDEX_INPUT_GLOBS:
        paths.extend(sorted(SIP_THREAD_INDEX_ROOT().glob(pattern)))
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path not in seen:
            deduped.append(path)
            seen.add(path)
    return deduped

def _sip_thread_index_noise_marker(topic: str) -> str:
    text = topic or ''
    if '@' in text:
        return '@'
    low = text.lower()
    for marker in SIP_THREAD_INDEX_NOISE_MARKERS:
        if marker.lower() in low:
            return marker
    return ''

def cmd_sip_thread_index_audit(args: argparse.Namespace) -> None:
    conflict_count = _PdUnset
    conflict_samples = _PdUnset
    file_errors = _PdUnset
    malformed_count = _PdUnset
    malformed_samples = _PdUnset
    max_samples = _PdUnset
    noisy_count = _PdUnset
    noisy_samples = _PdUnset
    paths = _PdUnset
    per_file = _PdUnset
    row_count = _PdUnset
    seen = _PdUnset

    def _pd_phase_17():
        nonlocal conflict_count, conflict_samples, file_errors, malformed_count, malformed_samples, max_samples, noisy_count, noisy_samples, paths, per_file, row_count, seen
        'Audit the fixed SIP thread JSON inputs for malformed, noisy, and conflicting rows.'
        max_samples = max(1, min(int(getattr(args, 'max_samples', 25)), 100))
        paths = _sip_thread_index_input_paths()
        if not paths:
            fail(f'no SIP thread index inputs matched: {SIP_THREAD_INDEX_ROOT()} / {list(SIP_THREAD_INDEX_INPUT_GLOBS)}')
        per_file = {}
        file_errors = []
        malformed_samples = []
        noisy_samples = []
        conflict_samples = []
        malformed_count = 0
        noisy_count = 0
        conflict_count = 0
        row_count = 0
        seen = {}

    def _pd_phase_18():
        nonlocal conflict_count, malformed_count, noisy_count, row_count
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except Exception as exc:
                logging.getLogger('pd_one_ops').exception('pd one command failed')
                file_errors.append({'file': path.name, 'error': f'{type(exc).__name__}: {exc}'})
                continue
            if not isinstance(data, list):
                file_errors.append({'file': path.name, 'error': f'expected_json_array:{type(data).__name__}'})
                continue
            per_file[path.name] = len(data)
            for row_number, item in enumerate(data, start=1):
                row_count += 1
                if not isinstance(item, dict):
                    malformed_count += 1
                    if len(malformed_samples) < max_samples:
                        malformed_samples.append({'file': path.name, 'row_number': row_number, 'reason': 'non_object_row'})
                    continue
                oid = str(item.get('originalPostId') or item.get('postId') or item.get('post_id') or '').strip()
                topic = str(item.get('topic') or item.get('title') or item.get('excerpt') or '').strip()
                link = str(item.get('original_post_url') or item.get('link') or '').strip()
                pd_matches = [m.upper() for m in re.findall('PD-\\d{3}', topic, re.I)]
                reasons = []
                if not oid:
                    reasons.append('missing_post_id')
                if not pd_matches:
                    reasons.append('missing_pd_topic')
                if '/_redirect/pl/' not in link:
                    reasons.append('missing_redirect_link')
                if reasons:
                    malformed_count += 1
                    if len(malformed_samples) < max_samples:
                        malformed_samples.append({'file': path.name, 'row_number': row_number, 'originalPostId': oid, 'topic': topic[:240], 'link': link[:240], 'pd_matches': pd_matches[:5], 'reasons': reasons})
                marker = _sip_thread_index_noise_marker(topic)
                if marker:
                    noisy_count += 1
                    if len(noisy_samples) < max_samples:
                        noisy_samples.append({'file': path.name, 'row_number': row_number, 'originalPostId': oid, 'topic': topic[:240], 'link': link[:240], 'matched_noise_marker': marker})
                if oid:
                    current = {'file': path.name, 'row_number': row_number, 'topic': topic, 'link': link}
                    previous = seen.get(oid)
                    if previous and (previous['topic'] != topic or previous['link'] != link):
                        conflict_count += 1
                        if len(conflict_samples) < max_samples:
                            changed_fields = []
                            if previous['topic'] != topic:
                                changed_fields.append('topic')
                            if previous['link'] != link:
                                changed_fields.append('link')
                            conflict_samples.append({'originalPostId': oid, 'first_seen': {'file': previous['file'], 'row_number': previous['row_number'], 'topic': previous['topic'][:240], 'link': previous['link'][:240]}, 'conflict': {'file': path.name, 'row_number': row_number, 'topic': topic[:240], 'link': link[:240]}, 'changed_fields': changed_fields})
                    if oid not in seen:
                        seen[oid] = current
        status = 'partial' if file_errors else 'ok'
        emit({'status': status, 'capability': 'pd_one_sip_thread_index_audit', 'input_root': str(SIP_THREAD_INDEX_ROOT()), 'input_globs': list(SIP_THREAD_INDEX_INPUT_GLOBS), 'file_count': len(paths), 'row_count': row_count, 'unique_post_id_count': len(seen), 'per_file': per_file, 'file_errors': file_errors[:max_samples], 'malformed_count': malformed_count, 'noisy_count': noisy_count, 'conflict_count': conflict_count, 'malformed_samples': malformed_samples, 'noisy_samples': noisy_samples, 'conflict_samples': conflict_samples, 'safety': {'read_only': True, 'fixed_input_root': True, 'bounded_samples': max_samples, 'shell_used': False, 'source_system_writes': False}})
    _pd_result = _pd_phase_17()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
    _pd_result = _pd_phase_18()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value

def _load_typhoon_automation_module() -> Any:
    if not TYPHOON_AUTOMATION_SCRIPT().exists():
        fail(f'typhoon automation script not found: {TYPHOON_AUTOMATION_SCRIPT()}')
    spec = importlib.util.spec_from_file_location('pdone_typhoon_automation_safe_ops', TYPHOON_AUTOMATION_SCRIPT())
    if spec is None or spec.loader is None:
        fail(f'could not load typhoon automation helper: {TYPHOON_AUTOMATION_SCRIPT()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def _summarize_typhoon_plan(case_name: str, fixture: Path, now: str, plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return {'case': case_name, 'fixture': str(fixture), 'now': now, 'status': 'error', 'error': f'unexpected plan type: {type(plan).__name__}'}
    observation = plan.get('observation') if isinstance(plan.get('observation'), dict) else {}
    actions = plan.get('actions') if isinstance(plan.get('actions'), list) else []
    return {'case': case_name, 'fixture': str(fixture), 'now': now, 'status': 'ok', 'mode': plan.get('mode'), 'activate': plan.get('activate'), 'actions': actions, 'risk_tier': observation.get('risk_tier'), 'risk_score': observation.get('risk_score'), 'activation_reason': observation.get('activation_reason')}

def _run_typhoon_sweep_case(module: Any, case: dict[str, Any]) -> dict[str, Any]:
    fixture = require_under_roots(str(case['fixture']), '--fixture', TYPHOON_AUTOMATION_FIXTURE_ROOTS())
    args = argparse.Namespace(live=False, fixture=str(fixture), now=str(case['now']), state_file=str(TYPHOON_AUTOMATION_SWEEP_STATE_FILE()))
    try:
        plan = module.run_once(args)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'case': case['case'], 'fixture': str(fixture), 'now': str(case['now']), 'status': 'error', 'error': f'{type(exc).__name__}: {exc}'}
    return _summarize_typhoon_plan(str(case['case']), fixture, str(case['now']), plan)

def cmd_typhoon_automation(args: argparse.Namespace) -> None:
    """Compile/test, preview, sweep fixed fixtures, or run the PD One typhoon readiness automation.

    `check` runs the helper's syntax and unit tests. `preview` runs the fixed
    typhoon script in dry-run mode. `sweep` runs the canonical fixture matrix in
    dry-run mode without ad hoc Python. `live` runs the live workflow and requires the
    exact live confirmation phrase.
    """
    if not TYPHOON_AUTOMATION_SCRIPT().exists():
        fail(f'typhoon automation script not found: {TYPHOON_AUTOMATION_SCRIPT()}')
    if not TYPHOON_AUTOMATION_TEST().exists():
        fail(f'typhoon automation test not found: {TYPHOON_AUTOMATION_TEST()}')
    action = (args.action or 'preview').strip()
    if action not in {'check', 'preview', 'sweep', 'live'}:
        fail('action must be one of: check, preview, sweep, live')
    fixture = None
    if getattr(args, 'fixture', None):
        if action == 'sweep':
            fail('sweep typhoon automation does not accept --fixture')
        if action == 'live':
            fail('live typhoon automation does not accept --fixture')
        fixture = require_under_roots(args.fixture, '--fixture', TYPHOON_AUTOMATION_FIXTURE_ROOTS())
        if not fixture.is_file():
            fail(f'--fixture not found: {fixture}')
    if getattr(args, 'confirm_live_write', None) and action != 'live':
        fail('--confirm-live-write is only valid for live typhoon automation')
    if action == 'check':
        compile_cmd = [sys.executable, '-m', 'py_compile', str(TYPHOON_AUTOMATION_SCRIPT()), str(TYPHOON_AUTOMATION_TEST())]
        compile_proc = run_capture(compile_cmd, timeout=120)
        unit_proc = run_capture([sys.executable, str(TYPHOON_AUTOMATION_TEST())], timeout=300)
        result = {'status': 'ok' if compile_proc.returncode == 0 and unit_proc.returncode == 0 else 'error', 'capability': 'pd_one_typhoon_automation', 'action': 'check', 'script': str(TYPHOON_AUTOMATION_SCRIPT()), 'unit_test': str(TYPHOON_AUTOMATION_TEST()), 'compile': {'returncode': compile_proc.returncode, 'stdout_tail': tail_text(compile_proc.stdout), 'stderr_tail': tail_text(compile_proc.stderr)}, 'unit': {'returncode': unit_proc.returncode, 'stdout_tail': tail_text(unit_proc.stdout), 'stderr_tail': tail_text(unit_proc.stderr)}, 'safety': {'shell_used': False, 'read_only': True, 'fixture_used': False, 'live_write_requested': False}}
        emit(result)
        if result['status'] != 'ok':
            raise SystemExit(1)
        return
    if action == 'sweep':
        module = _load_typhoon_automation_module()
        cases = []
        failures = []
        for case in TYPHOON_AUTOMATION_SWEEP_CASES():
            case_result = _run_typhoon_sweep_case(module, case)
            cases.append(case_result)
            if case_result.get('status') != 'ok':
                failures.append(case_result.get('case'))
        result = {'status': 'ok' if not failures else 'error', 'capability': 'pd_one_typhoon_automation', 'action': 'sweep', 'cases': cases, 'summary': {'case_count': len(cases), 'failure_count': len(failures), 'failed_cases': failures}, 'safety': {'shell_used': False, 'subprocess_used': False, 'read_only': True, 'fixture_used': True, 'fixed_case_matrix': True, 'live_write_requested': False}}
        emit(result)
        if failures:
            raise SystemExit(1)
        return
    cmd = [sys.executable, str(TYPHOON_AUTOMATION_SCRIPT()), '--json']
    if fixture:
        cmd += ['--fixture', str(fixture)]
    live = action == 'live'
    if live:
        if args.confirm_live_write != TYPHOON_AUTOMATION_LIVE_CONFIRMATION:
            fail(f'live typhoon automation requires --confirm-live-write {TYPHOON_AUTOMATION_LIVE_CONFIRMATION!r}')
        cmd.append('--live')
    result = run_json(cmd, timeout=900 if live else 300)
    if isinstance(result, dict):
        result.setdefault('status', 'ok')
        result.setdefault('capability', 'pd_one_typhoon_automation')
        result.setdefault('action', action)
        safety = result.get('safety') if isinstance(result.get('safety'), dict) else {}
        safety = {**safety, 'shell_used': False, 'fixture_used': bool(fixture), 'fixture': str(fixture) if fixture else '', 'read_only': not live, 'live_write_requested': live}
        result['safety'] = safety
    emit(result)

def _load_docs_api_module() -> Any:
    if not DOCS_API().exists():
        fail(f'docs_api helper not found: {DOCS_API()}')
    spec = importlib.util.spec_from_file_location('pdone_docs_api', DOCS_API())
    if spec is None or spec.loader is None:
        fail(f'could not load docs_api helper: {DOCS_API()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def cmd_drive_acl_authorize(args: argparse.Namespace) -> None:
    tools_dir = str(ROOT() / 'tools')
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    from drive_acl_authorize import authorize, public_view, refuse_individual_share
    if str(getattr(args, 'refuse_share', '') or '') == 'yes':
        emit(refuse_individual_share())
        raise SystemExit(2)
    result = authorize(args.file_id, mattermost_user_id=getattr(args, 'requester_user_id', '') or '', mattermost_username=getattr(args, 'username', '') or '', account=getattr(args, 'account', DEFAULT_ACCOUNT()))
    emit(public_view(result, redact=True))
    return

def cmd_portal_module_change_authorize(args: argparse.Namespace) -> None:
    tools_dir = str(ROOT() / 'tools')
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    from portal_module_change_authorize import authorize, public_view
    result = authorize(mattermost_user_id=getattr(args, 'requester_user_id', '') or '', channel_id=getattr(args, 'channel_id', '') or '', module_id=getattr(args, 'module_id', '') or '', path=getattr(args, 'path', '') or '', change_class=getattr(args, 'change_class', '') or 'in_scope_module_product')
    emit(public_view(result))
    return

def cmd_work_manual_change_authorize(args: argparse.Namespace) -> None:
    tools_dir = str(ROOT() / 'tools')
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    from work_manual_change_authorize import authorize, public_view
    result = authorize(mattermost_user_id=getattr(args, 'requester_user_id', '') or '', channel_id=getattr(args, 'channel_id', '') or '', chat_type=getattr(args, 'chat_type', '') or '', document_key=getattr(args, 'document_key', '') or 'it_manual', document_id=getattr(args, 'document_id', '') or '', change_class=getattr(args, 'change_class', '') or 'secret_free_content_add')
    emit(public_view(result))
    return

def cmd_google_docs_metadata_inspect(args: argparse.Namespace) -> None:
    """Inspect Google Docs header metadata and recent changelog entries.

    This is the read-only wrapper for the execute_code shape that imported
    docs_api.py directly to print header ids, header text, recent changelog
    entries, and revision metadata.
    """
    module = _load_docs_api_module()
    doc_id = (args.doc_id or '').strip()
    if not doc_id or len(doc_id) > 200 or (not re.match('^[A-Za-z0-9_-]+$', doc_id)):
        fail('--doc-id is required and must contain only Google Docs id-safe characters')
    changelog_heading = (args.changelog_heading or '變更日誌 Changelog').strip()
    if not changelog_heading or len(changelog_heading) > 240:
        fail('--changelog-heading is required and must be <= 240 characters')
    limit = max(1, min(int(args.limit), 20))
    tab_id = (args.tab_id or '').strip() or None
    client = module.DocsClient(args.account)
    doc = client.get_document(doc_id, 'PREVIEW_WITHOUT_SUGGESTIONS')
    document_style, resolved_tab_id = module.document_style(doc, tab_id)
    headers = []
    for header_type in module.HEADER_TYPE_CHOICES:
        header_id = document_style.get(module.HEADER_TYPE_TO_STYLE_KEY[header_type])
        if not header_id:
            continue
        headers.append({'type': header_type, 'headerId': header_id, 'tabId': resolved_tab_id, 'text': module.header_text(doc, header_id, tab_id=resolved_tab_id).rstrip('\n')})
    result: dict[str, Any] = {'status': 'ok', 'capability': 'pd_one_google_docs_metadata_inspect', 'docId': doc_id, 'documentTitle': doc.get('title'), 'revisionId': doc.get('revisionId'), 'documentUrl': module.build_doc_url(doc_id, resolved_tab_id), 'tabId': resolved_tab_id, 'documentStyle': {key: document_style.get(key) for key in module.HEADER_TYPE_TO_STYLE_KEY.values() if document_style.get(key)}, 'headers': headers, 'changelogHeading': changelog_heading, 'recentChangelogEntries': module.recent_changelog_entries(doc, changelog_heading, resolved_tab_id, limit=limit), 'safety': {'read_only': True, 'shell_used': False, 'preview_without_suggestions': True, 'recent_changelog_limit': limit}}
    try:
        changelog_heading_obj = module.find_heading(doc, changelog_heading, resolved_tab_id)
    except module.DocsApiError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        changelog_heading_obj = None
    if changelog_heading_obj:
        result['changelogHeadingMatch'] = {'text': changelog_heading_obj.text, 'headingId': changelog_heading_obj.heading_id, 'startIndex': changelog_heading_obj.start_index, 'endIndex': changelog_heading_obj.end_index, 'tabId': changelog_heading_obj.tab_id, 'headingUrl': module.build_heading_url(doc_id, changelog_heading_obj.heading_id, changelog_heading_obj.tab_id)}
    emit(result)

def cmd_yammer_archive_search(args: argparse.Namespace) -> None:
    """Read-only scoped Yammer/Viva Engage archive search."""
    import importlib.util
    import sys
    mod_path = ROOT() / 'tools/yammer_archive_scoped_search.py'
    spec = importlib.util.spec_from_file_location('yammer_archive_scoped_search', mod_path)
    if spec is None or spec.loader is None:
        fail(f'Unable to load {mod_path}')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    out = mod.search_yammer_archive(sender_id=args.sender_id, query=args.query, origin_channel_id=args.origin_channel_id or None, max_results=int(args.max_results), db_path=Path(args.db) if args.db else mod.YAMMER_DB)
    emit(out)

def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

def build_parser():
    ap = _PdUnset
    p = _PdUnset
    sub = _PdUnset

    def _pd_phase_19():
        nonlocal ap, p, sub
        ap = argparse.ArgumentParser(description=__doc__)
        sub = ap.add_subparsers(dest='cmd', required=True)
        p = sub.add_parser('registry-list')
        p.set_defaults(func=cmd_registry_list)
        p = sub.add_parser('legacy-xls-inspect')
        p.add_argument('--input', required=True)
        p.add_argument('--sheet')
        p.add_argument('--max-sheets', type=int, default=10)
        p.add_argument('--preview-rows', type=int, default=25)
        p.add_argument('--preview-cols', type=int, default=25)
        p.add_argument('--max-nonempty-cells', type=int, default=400)
        p.add_argument('--max-merged-cells', type=int, default=20)
        p.set_defaults(func=cmd_legacy_xls_inspect)
        p = sub.add_parser('xlsx-workbook-inspect')
        p.add_argument('--input', action='append', required=True, help='XLSX/XLSM path under approved PD One document roots; repeat for multiple workbooks')
        p.add_argument('--sheet', help='Optional sheet name for a bounded preview')
        p.add_argument('--preview-input', help='Only preview this input workbook; must match one repeated --input path')
        p.add_argument('--row-start', type=int, default=1)
        p.add_argument('--row-end', type=int, default=25)
        p.add_argument('--max-columns', type=int, default=25)
        p.add_argument('--include-values', action='store_true', help='Include bounded cell values for the selected sheet')
        p.set_defaults(func=cmd_xlsx_workbook_inspect)
        p = sub.add_parser('equipment-workbook-build')
        p.add_argument('--action', choices=['check', 'stage'], default='check')
        p.set_defaults(func=cmd_equipment_workbook)
        p = sub.add_parser('item-number-xlsx-compiler')
        p.add_argument('--action', choices=['check', 'smoke'], default='smoke')
        p.set_defaults(func=cmd_item_number_xlsx_compiler)
        p = sub.add_parser('item-number-render-qa-status')
        p.set_defaults(func=cmd_item_number_render_qa_status)
        p = sub.add_parser('item-number-historical-sample-summary')
        p.set_defaults(func=cmd_item_number_historical_sample_summary)
        p = sub.add_parser('item-number-local-fixture-copy')
        p.set_defaults(func=cmd_item_number_local_fixture_copy)
        p = sub.add_parser('item-number-windows-excel-qa')
        p.add_argument('--confirm', help='Exact confirmation required to run the remote Excel/COM lane')
        p.set_defaults(func=cmd_item_number_windows_excel_qa)
        p = sub.add_parser('office-docprops-inspect', help='Inspect allowlisted Office Open XML core/app properties')
        p.add_argument('--input', required=True, help='Approved .pptx/.docx/.xlsx package under PD One document roots')
        p.set_defaults(func=cmd_office_docprops_inspect)
        p = sub.add_parser('office-visual-qa')
        p.add_argument('--input', required=True, help='DOCX/PPTX input under approved PD One document roots')
        p.add_argument('--out-dir', required=True, help='QA artifact directory under approved PD One document roots')
        p.set_defaults(func=cmd_office_visual_qa)
        p = sub.add_parser('ecrn-approval-pilot-status')
        p.add_argument('--root-id', help='Optional thread root id to inspect')
        p.add_argument('--max-threads', type=int, default=20, help='Bound the number of threads returned when no root id is supplied')
        p.add_argument('--max-previews', type=int, default=5, help='Bound the preview receipts returned per thread')
        p.set_defaults(func=cmd_ecrn_approval_pilot_status)
        p = sub.add_parser('ecrn-approval-pilot-check')
        p.set_defaults(func=cmd_ecrn_approval_pilot_check)
        p = sub.add_parser('sheets-get-range')
        p.add_argument('--spreadsheet-id', required=True)
        p.add_argument('--range', required=True)
        p.add_argument('--account', default=DEFAULT_ACCOUNT())
        p.add_argument('--include-values', action='store_true', help='Include cell values in the JSON result')
        p.add_argument('--render', choices=list(SHEETS_GET_RENDER_OPTIONS), help='Value render option: FORMATTED_VALUE, UNFORMATTED_VALUE, or FORMULA')
        p.add_argument('--retries', type=int, default=3, help='Retry transient read failures only; capped at 5')
        p.add_argument('--requester-user-id', default='', help='Exact Mattermost user id; live Drive ACL is checked when set')
        p.set_defaults(func=cmd_sheets_get_range)
        p = sub.add_parser('cached-sheet-json-search', help='Search a cached Sheets values JSON dump')
        p.add_argument('--input', required=True, help='Cached Sheets JSON under PD One tmp/artifacts/cache')
        p.add_argument('--term', action='append', default=[], help='Literal case-insensitive search term; repeat up to 8')
        p.add_argument('--column', action='append', default=[], help='Optional header name to project; repeat up to 12')
        p.add_argument('--header-row', type=int, default=3, help='1-based sheet row containing headers')
        p.add_argument('--max-matches', type=int, default=30, help='Match cap, maximum 30')
        p.set_defaults(func=cmd_cached_sheet_json_search)
        p = sub.add_parser('cached-dest-rest-count', help='Count dest rest markers for named workers in a cached Sheets dump')
        p.add_argument('--input', required=True, help='Cached Sheets JSON under PD One tmp/artifacts/cache')
        p.add_argument('--term', action='append', default=[], help='Worker name fragment; repeat up to 8')
        p.add_argument('--marker', action='append', default=[], help='Rest marker to count; default V; repeat up to 8')
        p.add_argument('--header-row', type=int, default=3, help='1-based row containing day numbers')
        p.add_argument('--name-index', type=int, default=0, help='0-based name column in the dump')
        p.add_argument('--date-start-index', type=int, default=-1, help='0-based first date column; -1 auto-detects 1-31 headers')
        p.add_argument('--window-start', type=int, default=None, help='Optional inclusive day-number window start')
        p.add_argument('--window-end', type=int, default=None, help='Optional inclusive day-number window end')
        p.set_defaults(func=cmd_cached_dest_rest_count)
        p = sub.add_parser('sheets-batch-update')
        p.add_argument('--spreadsheet-id', required=True)
        p.add_argument('--data-json', required=True, help='JSON array file under PD One tmp/artifacts/cache')
        p.add_argument('--account', default=DEFAULT_ACCOUNT())
        p.add_argument('--input', default='USER_ENTERED', choices=['RAW', 'USER_ENTERED'])
        p.add_argument('--live', action='store_true')
        p.add_argument('--confirm-live-write')
        p.add_argument('--readback', action='append', default=[])
        p.add_argument('--receipt')
        p.add_argument('--retries', type=int, default=3)
        p.add_argument('--requester-user-id', default='')
        p.set_defaults(func=cmd_sheets_batch_update)
        p = sub.add_parser('sheets-append')
        p.add_argument('--spreadsheet-id', required=True)
        p.add_argument('--range', required=True)
        p.add_argument('--values-json', required=True, help='2D values JSON file under PD One tmp/artifacts/cache')
        p.add_argument('--account', default=DEFAULT_ACCOUNT())
        p.add_argument('--chunk-size', type=int, default=50)
        p.add_argument('--input', default='USER_ENTERED', choices=['RAW', 'USER_ENTERED'])
        p.add_argument('--insert', default='INSERT_ROWS', choices=['INSERT_ROWS', 'OVERWRITE'])
        p.add_argument('--live', action='store_true')
        p.add_argument('--confirm-live-write')
        p.add_argument('--receipt')
        p.add_argument('--requester-user-id', default='')
        p.set_defaults(func=cmd_sheets_append)
        p = sub.add_parser('sheets-header-update-row')
        p.add_argument('--spreadsheet-id', required=True)
        p.add_argument('--sheet', required=True)
        p.add_argument('--key-header', required=True)
        p.add_argument('--key-value', required=True)
        p.add_argument('--values-json', required=True, help='JSON object under PD One tmp/artifacts/cache')
        p.add_argument('--account', default=DEFAULT_ACCOUNT())
        p.add_argument('--max-column', default='ZZ')
        p.add_argument('--max-rows', type=int, default=5000)
        p.add_argument('--input', default='USER_ENTERED', choices=['RAW', 'USER_ENTERED'])
        p.add_argument('--live', action='store_true')
        p.add_argument('--confirm-live-write')
        p.add_argument('--receipt')
        p.add_argument('--retries', type=int, default=3)
        p.add_argument('--requester-user-id', default='')
        p.set_defaults(func=cmd_sheets_header_update_row)
        p = sub.add_parser('bounded-sheet-cell-write')
        p.add_argument('--bind-json', required=True, help='Bound sheet/tab/cells/values JSON under PD One tmp')
        p.add_argument('--expected-binding', default='', help='Optional sha256: digest that must match the bind envelope')
        p.add_argument('--account', default=DEFAULT_ACCOUNT())
        p.add_argument('--verify-live-read', action='store_true', help='Read vendor/grade freeze cells before dry-run')
        p.add_argument('--live', action='store_true')
        p.add_argument('--confirm-live-write')
        p.add_argument('--ticket-id', default='')
        p.add_argument('--receipt')
        p.set_defaults(func=cmd_bounded_sheet_cell_write)
        p = sub.add_parser('appsheet-table-probe')
        p.add_argument('--table', required=True)
        p.add_argument('--selector', required=True)
        p.add_argument('--env', choices=sorted(APPSHEET_ENV_FILES()), default='prototype')
        p.set_defaults(func=cmd_appsheet_table_probe)
        p = sub.add_parser('appsheet-incident-morning-briefing-qa')
        p.set_defaults(func=cmd_appsheet_incident_morning_briefing_qa)
        p = sub.add_parser('google-group-members')
        p.add_argument('--group', required=True)
        p.add_argument('--filter-email')
        p.add_argument('--account', default=DEFAULT_ACCOUNT())
        p.add_argument('--timeout', type=int, default=120)
        p.add_argument('--include-members', action='store_true', help='include full raw member objects')
        p.set_defaults(func=cmd_google_group_members)
        p = sub.add_parser('google-drive-parent-chain')
        p.add_argument('--file-id', required=True)
        p.add_argument('--stop-at-id')
        p.add_argument('--max-hops', type=int, default=12)
        p.add_argument('--account', default=DEFAULT_ACCOUNT())
        p.set_defaults(func=cmd_google_drive_parent_chain)
        p = sub.add_parser('google-drive-search-files')
        p.add_argument('--parent-id', required=True)
        p.add_argument('--window-start-utc', required=True)
        p.add_argument('--name-contains', required=True)
        p.add_argument('--mime-type', default='application/vnd.ms-excel')
        p.add_argument('--max-files', type=int, default=100)
        p.add_argument('--timeout', type=int, default=90)
        p.add_argument('--account', default=DEFAULT_ACCOUNT())
        p.set_defaults(func=cmd_google_drive_search_files)
        p = sub.add_parser('google-group-change')
        p.add_argument('--group', required=True)
        p.add_argument('--action', required=True, choices=['create-group', 'add-member', 'remove-member'])
        p.add_argument('--member')
        p.add_argument('--role', default='MEMBER')
        p.add_argument('--name')
        p.add_argument('--account', default=DEFAULT_ACCOUNT())
        p.add_argument('--dry-run', action='store_true', default=True)
        p.add_argument('--live', dest='dry_run', action='store_false')
        p.add_argument('--ticket-id')
        p.add_argument('--confirm-live-write')
        p.set_defaults(func=cmd_google_group_change)
        p = sub.add_parser('auth-browser-status')
        p.add_argument('--container', default='pdone-gog-auth-browser')
        p.add_argument('--include-tailscale-url', help='optional explicit status URL, e.g. http://100.x.x.x:6081/vnc.html')
        p.set_defaults(func=cmd_auth_browser_status)
        p = sub.add_parser('sysstat-summary')
        p.add_argument('--hours', type=int, default=SYSSTAT_SUMMARY_DEFAULT_HOURS, help='Window size in hours, capped at 72')
        p.set_defaults(func=cmd_sysstat_summary)
        p = sub.add_parser('numeric-summary')
        p.add_argument('--values-json', required=True, help='JSON array of finite numeric values')
        p.add_argument('--label', default='samples', help='Human-readable metric label')
        p.add_argument('--units', default='', help='Optional units label such as pct or ms')
        p.set_defaults(func=cmd_numeric_summary)
        p = sub.add_parser('text-metrics')
        p.add_argument('--text', required=True, help='Caller-supplied text, capped at 20000 Unicode code points')
        p.set_defaults(func=cmd_text_metrics)
        p = sub.add_parser('disk-space-summary')
        p.add_argument('--low-risk-bytes', type=int, default=0)
        p.add_argument('--medium-risk-bytes', type=int, default=0)
        p.add_argument('--additional-bytes', type=int, default=0)
        p.set_defaults(func=cmd_disk_space_summary)
        p = sub.add_parser('user-process-snapshot')
        p.set_defaults(func=cmd_user_process_snapshot)
        p = sub.add_parser('local-process-listener-inspect')
        p.add_argument('--ports', nargs='*', type=int, default=None, help='Allowlisted ports; defaults to 8646 and 8766')
        p.add_argument('--pids', nargs='*', type=int, default=None, help='Optional bounded PID list')
        p.set_defaults(func=cmd_local_process_listener_inspect)
        p = sub.add_parser('python-package-dry-run')
        p.add_argument('--package', required=True)
        p.add_argument('--version', required=True)
        p.add_argument('--python', required=True)
        p.set_defaults(func=cmd_python_package_dry_run)
        p = sub.add_parser('python-media-stack-status')
        p.set_defaults(func=cmd_python_media_stack_status)
        p = sub.add_parser('python-cad-stack-status')
        p.add_argument('--input', action='append', default=[], help='Optional cached CAD document under cache/documents (.stp/.step/.3mf)')
        p.set_defaults(func=cmd_python_cad_stack_status)
        p = sub.add_parser('cad-runtime-status')
        p.set_defaults(func=cmd_cad_runtime_status)
        p = sub.add_parser('step-geometry-inspect')
        p.add_argument('--action', choices=['check', 'inspect', 'summarize'], default='check')
        p.add_argument('--input', required=True, help='Approved .stp/.step, or inspect.json for --action summarize')
        p.set_defaults(func=cmd_step_geometry_inspect)
        p = sub.add_parser('step-printability-analyze')
        p.add_argument('--action', choices=['check', 'analyze', 'summarize'], default='check')
        p.add_argument('--input', required=True, help='Approved .stp/.step, or official printability JSON for --action summarize')
        p.set_defaults(func=cmd_step_printability_analyze)
        p = sub.add_parser('python-docx-dependency-repair')
        p.add_argument('--ticket-id', required=True)
        p.add_argument('--action', choices=['inspect', 'install'], default='inspect')
        p.add_argument('--confirm-live-write')
        p.set_defaults(func=cmd_python_docx_dependency_repair)
        p = sub.add_parser('hermes-result-messages-summary')
        p.add_argument('--input', required=True, help='JSON result artifact under /tmp/hermes-results')
        p.add_argument('--max-messages', type=int, default=HERMES_RESULT_SUMMARY_MAX_MESSAGES)
        p.set_defaults(func=cmd_hermes_result_messages_summary)
        p = sub.add_parser('json-artifact-inspect', help='Inspect bounded local JSON structure without dumping values')
        p.add_argument('--input', action='append', required=True, help='JSON artifact under an approved PD One root; repeat up to 4 times')
        p.set_defaults(func=cmd_json_artifact_inspect)
        p = sub.add_parser('local-file-search', help='Bounded approved-root path identity and filename-glob search without dumping contents')
        p.add_argument('--path', action='append', help='Approved PD One path to identity-check; repeat up to 8 times')
        p.add_argument('--pattern', action='append', help='Filename glob under approved PD One roots; repeat up to 8 times')
        p.set_defaults(func=cmd_local_file_search)
        p = sub.add_parser('timezone-snapshot')
        p.set_defaults(func=cmd_timezone_snapshot)
        p = sub.add_parser('protected-portal-origin-probe')
        p.add_argument('--path', action='append', help='Extra allowlisted portal path to probe')
        p.add_argument('--email', action='append', help='Identity email; omit for anonymous. Repeat with --path.')
        p.set_defaults(func=cmd_protected_portal_origin_probe)
        p = sub.add_parser('timestamp-to-epoch')
        p.add_argument('--timestamp', required=True, help='One timezone-aware ISO-8601 timestamp')
        p.set_defaults(func=cmd_timestamp_to_epoch)
        p = sub.add_parser('epoch-milliseconds-to-iso')
        p.add_argument('--epoch-milliseconds', required=True, nargs='+', type=int, help='One to 20 UTC epoch-millisecond values')
        p.set_defaults(func=cmd_epoch_milliseconds_to_iso)
        p = sub.add_parser('sheets-serial-column-convert')
        p.add_argument('--serials', nargs='*', type=int, default=[], help='Up to 20 Google Sheets serial day numbers')
        p.add_argument('--columns', nargs='*', default=[], help='Up to 20 A1 column letters')
        p.add_argument('--ranges', nargs='*', default=[], help='Up to 8 inclusive A1 column ranges such as W:BC')
        p.set_defaults(func=cmd_sheets_serial_column_convert)
        p = sub.add_parser('ollama-embedding-triage')
        p.add_argument('--unit', default=OLLAMA_EMBEDDING_UNIT)
        p.add_argument('--container', default=OLLAMA_EMBEDDING_CONTAINER)
        p.add_argument('--peer-container', default=OLLAMA_EMBEDDING_PEER_CONTAINER)
        p.add_argument('--port', type=int, default=OLLAMA_EMBEDDING_PORT)
        p.add_argument('--lookback-hours', type=int, default=12)
        p.add_argument('--container-tail-lines', type=int, default=OLLAMA_EMBEDDING_MAX_CONTAINER_TAIL_LINES)
        p.add_argument('--journal-tail-lines', type=int, default=200)
        p.set_defaults(func=cmd_ollama_embedding_triage)
        p = sub.add_parser('ollama-embedding-watchdog-triage')
        p.add_argument('--unit', default=OLLAMA_EMBEDDING_WATCHDOG_UNIT)
        p.add_argument('--lookback-hours', type=int, default=12)

    def _pd_phase_20():
        nonlocal p
        p.add_argument('--journal-tail-lines', type=int, default=OLLAMA_EMBEDDING_WATCHDOG_MAX_JOURNAL_TAIL_LINES)
        p.set_defaults(func=cmd_ollama_embedding_watchdog_triage)
        p = sub.add_parser('mattermost-channel-setup')
        p.add_argument('--channel-id', required=True)
        p.add_argument('--action', choices=['inspect', 'dry_run_update', 'apply_metadata'], default='inspect')
        p.add_argument('--target-display-name')
        p.add_argument('--target-purpose')
        p.add_argument('--max-posts', type=int, default=1200)
        p.add_argument('--include-members', action='store_true')
        p.add_argument('--confirm-live-write')
        p.set_defaults(func=cmd_mattermost_channel_setup)
        p = sub.add_parser('mattermost-channel-lookup')
        p.add_argument('--team-name', required=True)
        p.add_argument('--channel-name', required=True)
        p.set_defaults(func=cmd_mattermost_channel_lookup)
        p = sub.add_parser('mattermost-channel-post-audit')
        p.add_argument('--channel-id', required=True)
        p.add_argument('--lookback-days', type=int, default=7)
        p.add_argument('--max-pages', type=int, default=10)
        p.set_defaults(func=cmd_mattermost_channel_post_audit)
        p = sub.add_parser('admin-alert-source-audit')
        p.set_defaults(func=cmd_admin_alert_source_audit)
        p = sub.add_parser('admin-approval-request')
        p.add_argument('--requester-user-id', required=True, help='Exact Mattermost requester user id')
        p.add_argument('--requester-label')
        p.add_argument('--origin-channel-id', required=True)
        p.add_argument('--origin-channel-name')
        p.add_argument('--origin-root-id')
        p.add_argument('--origin-post-id')
        p.add_argument('--admin-channel-id', default=DEFAULT_ADMIN_CHANNEL_ID())
        p.add_argument('--request-type', choices=['generic_handoff_v1', 'google_sheet_channel_sync_v1', 'hr_policy_lookup_v1', 'work_manual_edit_v1'], default='generic_handoff_v1')
        p.add_argument('--requested-action', required=True)
        p.add_argument('--requested-scope')
        p.add_argument('--risk-summary')
        p.add_argument('--acceptance-criteria', help='Comma/newline separated acceptance criteria')
        p.add_argument('--required-capabilities', help='Comma/newline separated capability labels')
        p.add_argument('--allowed-document-ids', help='Comma/newline separated immutable document ids')
        p.add_argument('--allowed-write-targets', help='Comma/newline separated write target ids, if already known')
        p.add_argument('--unresolved-assumptions', help='Comma/newline separated assumptions/questions')
        p.add_argument('--request-original')
        p.add_argument('--request-english')
        p.add_argument('--idempotency-key')
        p.add_argument('--allow-deployment', action='store_true', help='Bind deployment authorization; verified Owner sources must explicitly say deploy/go live')
        p.add_argument('--dry-run', action='store_true')
        p.set_defaults(func=cmd_admin_approval_request)
        p = sub.add_parser('admin-approval-list-open')
        p.add_argument('--max-results', type=int, default=100)
        p.set_defaults(func=cmd_admin_approval_list_open)
        p = sub.add_parser('admin-approval-decide')
        p.add_argument('--ticket-id', required=True)
        p.add_argument('--decision-post-id', required=True, help='Exact Mattermost decision post id; sender/text/thread are re-fetched and verified')
        p.add_argument('--dry-run', action='store_true', default=True)
        p.add_argument('--live', dest='dry_run', action='store_false')
        p.add_argument('--confirm-live-write')
        p.set_defaults(func=cmd_admin_approval_decide)
        p = sub.add_parser('approval-ticket-status')
        p.add_argument('--ticket-id', required=True)
        p.add_argument('--field', action='append', help='Optional top-level receipt field to return; may be repeated')
        p.add_argument('--include-details', action='store_true', help='Include bounded implementation_plan/capability_scope/bound_resources/approval_grant fields')
        p.set_defaults(func=cmd_approval_ticket_status)
        p = sub.add_parser('approval-ticket-cancel')
        p.add_argument('--ticket-id', required=True)
        p.add_argument('--reason', required=True)
        p.add_argument('--dry-run', action='store_true', default=True)
        p.add_argument('--live', dest='dry_run', action='store_false')
        p.add_argument('--confirm-live-write')
        p.set_defaults(func=cmd_approval_ticket_cancel)
        p = sub.add_parser('admin-approval-kanban-status')
        p.add_argument('--ticket-id', required=True)
        p.set_defaults(func=cmd_admin_approval_kanban_status)
        p = sub.add_parser('mattermost-member-search')
        p.add_argument('--sender-id', required=True, help="Exact Mattermost requester user id; authorization is based on this user's live channel membership")
        p.add_argument('--query', required=True, help='Search term(s). Separate multiple terms with commas or newlines.')
        p.add_argument('--channel-id', action='append', help='Optional channel id to search; may be repeated. If omitted, searches joined team channels up to --max-channels.')
        p.add_argument('--since', help='Only include posts on/after YYYY-MM-DD')
        p.add_argument('--max-results', type=int, default=20)
        p.add_argument('--max-channels', type=int, default=100)
        p.add_argument('--max-fallback-posts', type=int, default=1200, help='For explicit channels, bounded direct scan fallback after Mattermost search')
        p.set_defaults(func=cmd_mattermost_member_search)
        p = sub.add_parser('yammer-archive-search')
        p.add_argument('--sender-id', required=True, help='Exact Mattermost requester user id')
        p.add_argument('--query', required=True, help='Historical search query')
        p.add_argument('--origin-channel-id', default='', help='Optional origin channel for Inter-Dept pre-approved historical lookups')
        p.add_argument('--max-results', type=int, default=15)
        p.add_argument('--db', default='', help='Optional override path to yammer_archive.sqlite')
        p.set_defaults(func=cmd_yammer_archive_search)
        p = sub.add_parser('policy-change-dry-run')
        p.add_argument('--user-id', required=True)
        p.add_argument('--add-role')
        p.add_argument('--add-dm-scope')
        p.add_argument('--set-active', choices=['true', 'false'])
        p.add_argument('--receipt')
        p.add_argument('--include-proposed-data', action='store_true')
        p.set_defaults(func=cmd_policy_change_dry_run)
        p = sub.add_parser('policy-change-apply')
        p.add_argument('--ticket-id', required=True)
        p.add_argument('--user-id', required=True)
        p.add_argument('--add-role')
        p.add_argument('--add-dm-scope')
        p.add_argument('--set-active', choices=['true', 'false'])
        p.set_defaults(func=cmd_policy_change_apply)
        p = sub.add_parser('doc-extract')
        p.add_argument('--input', required=True)
        p.add_argument('--out')
        p.set_defaults(func=cmd_doc_extract)
        p = sub.add_parser('pptx-ooxml-text-inspect', help='Inspect bounded DrawingML a:t text from allowlisted PPTX members')
        p.add_argument('--input', required=True)
        p.add_argument('--member', action='append', required=True, help='Allowlisted ppt/slides|notesSlides|diagrams|charts member; repeat 1-12 times')
        p.set_defaults(func=cmd_pptx_ooxml_text_inspect)
        p = sub.add_parser('artifact-base64-encode', help='Base64-encode one bounded local media artifact')
        p.add_argument('--input', required=True, help='Media artifact under an approved PD One artifact root')
        p.set_defaults(func=cmd_artifact_base64_encode)
        p = sub.add_parser('local-artifact-copy', help='Copy one legacy employee artifact to its matching canonical path')
        p.add_argument('--input', required=True)
        p.add_argument('--out', required=True)
        p.add_argument('--source-sha256')
        p.set_defaults(func=cmd_local_artifact_copy)
        p = sub.add_parser('video-frame-sample', help='Probe one cached video and stage three fixed JPEG frames')
        p.add_argument('--input', required=True, help='Video under the approved PD One document cache')
        p.set_defaults(func=cmd_video_frame_sample)
        p = sub.add_parser('svg-artifact-inspect', help='Validate bounded structural/text invariants for one SVG')
        p.add_argument('--input', required=True, help='SVG artifact under an approved PD One artifact root')
        p.add_argument('--required-text', action='append', help='Required visible text; may be repeated')
        p.add_argument('--expected-embedded-png-count', type=int)
        p.add_argument('--max-text-y-exclusive', type=float)
        p.add_argument('--expected-image-box', help='Expected embedded PNG image box as x,y,width,height')
        p.set_defaults(func=cmd_svg_artifact_inspect)
        p = sub.add_parser('svg-embed-image', help='Inspect or stage an SVG with the fixed Pro-Design logo embedded')
        p.add_argument('--action', choices=['inspect', 'stage'], default='inspect')
        p.add_argument('--input', required=True, help='SVG artifact under an approved PD One artifact root')
        p.add_argument('--required-text', action='append', help='Optional visible text that must be preserved; may be repeated')
        p.add_argument('--expected-embedded-png-count', type=int)
        p.add_argument('--expected-logo-box', nargs=4, metavar=('X', 'Y', 'WIDTH', 'HEIGHT'))
        p.set_defaults(func=cmd_svg_embed_image)
        p = sub.add_parser('artifact-identity-inventory', help='List bounded artifact identities and peek one file magic')
        p.add_argument('--root', required=True, help='Approved PD One artifact directory')
        p.add_argument('--glob', action='append', help='Single-directory glob; may be repeated up to 8 times')
        p.add_argument('--peek', help='Optional file under --root whose magic bytes should be peeked')
        p.add_argument('--peek-bytes', type=int, default=8, help='Magic peek length from 1 to 16')
        p.set_defaults(func=cmd_artifact_identity_inventory)
        p = sub.add_parser('3mf-slicer-inspect', help='Inspect or stage allowlisted PrusaSlicer metadata from one 3MF')
        p.add_argument('--action', choices=['inspect', 'stage'], default='inspect')
        p.add_argument('--input', required=True, help='3MF under approved PD One cache/artifact/tmp roots')
        p.set_defaults(func=cmd_3mf_slicer_inspect)
        p = sub.add_parser('pptx-inspect', help='Inspect bounded PPTX slide/shape/run text')
        p.add_argument('--input', required=True, help='PPTX under an approved PD One document root')
        p.add_argument('--no-text', dest='include_text', action='store_false', help='Omit shape/run text')
        p.set_defaults(func=cmd_pptx_inspect, include_text=True)
        p = sub.add_parser('docx-inspect')
        p.add_argument('--input', required=True)
        p.add_argument('--table-index', type=int, required=True)
        p.add_argument('--row-index', type=int, required=True)
        p.add_argument('--cell-index', type=int, required=True)
        p.add_argument('--paragraph-index', type=int, default=0)
        p.add_argument('--no-runs', dest='include_runs', action='store_false', help='Omit paragraph run text')
        p.set_defaults(func=cmd_docx_inspect, include_runs=True)
        p = sub.add_parser('docx-body-xml-inspect', help='Inspect selected body-wide DOCX paragraph XML')
        p.add_argument('--input', required=True)
        p.add_argument('--paragraph-index', type=int, action='append', required=True)
        p.set_defaults(func=cmd_docx_body_xml_inspect)
        p = sub.add_parser('docx-table-structure', help='Inspect bounded DOCX table geometry and visible cell text')
        p.add_argument('--input', required=True)
        p.set_defaults(func=cmd_docx_table_structure)
        p = sub.add_parser('docx-layout-patch', help='Inspect or stage one exact DOCX section-start layout adjustment')
        p.add_argument('--action', choices=['inspect', 'stage'], default='inspect')
        p.add_argument('--input', required=True, help='Source DOCX under an approved PD One document root')
        p.add_argument('--target-text', required=True, help='Exact visible paragraph to mark as a kept section start')
        p.add_argument('--out', help='Separate staged DOCX path; required for action=stage')
        p.add_argument('--source-sha256', help='Optional current source SHA-256 guard')
        p.add_argument('--overwrite', action='store_true', help='Allow replacement of an existing staged output; source overwrite remains forbidden')
        p.set_defaults(func=cmd_docx_layout_patch)
        p = sub.add_parser('docx-table-search', help='Find terms in bounded DOCX table cells')
        p.add_argument('--input', required=True)
        p.add_argument('--term', action='append', required=True, help='Case-insensitive term; may be repeated up to 8 times')
        p.set_defaults(func=cmd_docx_table_search)
        p = sub.add_parser('doc-detect-format')
        p.add_argument('--input', required=True)
        p.add_argument('--include-text', action='store_true')
        p.set_defaults(func=cmd_doc_detect_format)
        p = sub.add_parser('doc-build')
        p.add_argument('--spec', required=True, help='JSON spec path under approved PD One document roots')
        p.add_argument('--out', required=True, help='Output .docx path under approved PD One document roots')
        p.add_argument('--visual-qa', action='store_true', help='Run render/visual QA after building')
        p.set_defaults(func=cmd_doc_build)
        p = sub.add_parser('json-html-artifact', help='Render a bounded JSON paragraphs spec to local HTML')
        p.add_argument('--spec', required=True, help='JSON paragraphs spec under approved PD One document roots')
        p.add_argument('--out', required=True, help='Output HTML path under approved PD One document roots')
        p.set_defaults(func=cmd_json_html_artifact)
        p = sub.add_parser('office-html-to-docx', help='Convert approved HTML to DOCX through isolated LibreOffice')
        p.add_argument('--input', required=True, help='HTML input under approved PD One document roots')
        p.add_argument('--out', required=True, help='Output DOCX under approved PD One document roots')
        p.set_defaults(func=cmd_office_html_to_docx)
        p = sub.add_parser('ecrn-docx-unique-text-patch', help='Inspect or stage one exact visible-text replacement in an ECRN DOCX')
        p.add_argument('--action', choices=['inspect', 'stage'], default='inspect')
        p.add_argument('--input', required=True, help='Source DOCX under the approved ECRN cache/artifact roots')
        p.add_argument('--old-text', required=True, help='One exact visible text value to locate')
        p.add_argument('--new-text', required=True, help='Replacement visible text value')
        p.add_argument('--out', help='Separate staged DOCX path; required for action=stage')
        p.add_argument('--source-sha256', help='Optional current source SHA-256 guard')
        p.add_argument('--overwrite', action='store_true', help='Allow replacement of an existing staged output; source overwrite remains forbidden')
        p.set_defaults(func=cmd_ecrn_docx_unique_text_patch)
        p = sub.add_parser('docx-exact-text-patch', help='Inspect or stage 1-8 exact visible-text replacements in a DOCX')
        p.add_argument('--action', choices=['inspect', 'stage'], default='inspect')
        p.add_argument('--input', required=True, help='Source DOCX under an approved PD One document root')
        p.add_argument('--replace', nargs=2, action='append', required=True, metavar=('OLD_TEXT', 'NEW_TEXT'))
        p.add_argument('--out', help='Separate staged DOCX path; required for action=stage')
        p.add_argument('--source-sha256', help='Optional current source SHA-256 guard')
        p.add_argument('--overwrite', action='store_true', help='Allow replacing an existing staged output; source overwrite remains forbidden')
        p.set_defaults(func=cmd_docx_exact_text_patch)
        p = sub.add_parser('pptx-exact-text-patch', help='Inspect or stage 1-8 exact visible-text replacements in a PPTX')
        p.add_argument('--action', choices=['inspect', 'stage'], default='inspect')
        p.add_argument('--input', required=True, help='Source PPTX under an approved PD One document root')
        p.add_argument('--replace', nargs=2, action='append', required=True, metavar=('OLD_TEXT', 'NEW_TEXT'))
        p.add_argument('--out', help='Separate staged PPTX path; required for action=stage')
        p.add_argument('--source-sha256', help='Optional current source SHA-256 guard')
        p.add_argument('--overwrite', action='store_true', help='Allow replacing an existing staged output; source overwrite remains forbidden')
        p.set_defaults(func=cmd_pptx_exact_text_patch)
        p = sub.add_parser('pptx-from-template', help='Clone a POTX/PPTX or apply its theme/masters onto a source PPTX')
        p.add_argument('--action', choices=['inspect', 'stage'], default='inspect')
        p.add_argument('--mode', choices=['apply', 'clone'], default='apply')
        p.add_argument('--template', required=True, help='Source POTX/PPTX template under an approved root')
        p.add_argument('--source', help='Source PPTX for mode=apply')
        p.add_argument('--out', help='Separate staged PPTX path; required for action=stage')
        p.add_argument('--source-sha256', help='Optional current source SHA-256 guard')
        p.add_argument('--overwrite', action='store_true', help='Allow replacing an existing staged output; sources stay read-only')
        p.set_defaults(func=cmd_pptx_from_template)
        p = sub.add_parser('sip-thread-index-build', help='Build the sanitized SIP discussion-thread workbook')
        p.set_defaults(func=cmd_sip_thread_index_build)
        p = sub.add_parser('sip-thread-index-audit', help='Audit the fixed SIP thread JSON inputs for malformed, noisy, and conflicting rows')
        p.add_argument('--max-samples', type=int, default=25, help='Maximum sample rows to retain for each issue category')
        p.set_defaults(func=cmd_sip_thread_index_audit)
        p = sub.add_parser('office-toolchain-status')
        p.set_defaults(func=cmd_office_toolchain_status)
        p = sub.add_parser('office-deb-contents', help='Inspect bounded Office Debian-package contents')
        p.add_argument('--package', required=True)
        p.set_defaults(func=cmd_office_deb_contents)
        p = sub.add_parser('item-number-workflow-check')
        p.add_argument('--component', choices=['engine', 'compiler', 'runner'], default='engine')
        p.set_defaults(func=cmd_item_number_workflow_check)
        p = sub.add_parser('office-convert-pdf')
        p.add_argument('--input', required=True, help='Office input file under approved PD One document roots')
        p.add_argument('--out', required=True, help='Output .pdf path under approved PD One document roots')
        p.set_defaults(func=cmd_office_convert_pdf)
        p = sub.add_parser('typhoon-automation')
        p.add_argument('--action', choices=['check', 'preview', 'sweep', 'live'], default='preview')
        p.add_argument('--fixture', help='Optional fixture JSON under approved typhoon fixture roots')
        p.add_argument('--confirm-live-write')
        p.set_defaults(func=cmd_typhoon_automation)
        p = sub.add_parser('drive-acl-authorize')
        p.add_argument('--file-id', required=True)
        p.add_argument('--requester-user-id', default='')
        p.add_argument('--username', default='')
        p.add_argument('--account', default=DEFAULT_ACCOUNT())
        p.add_argument('--refuse-share', choices=['yes', 'no'], default='no')
        p.set_defaults(func=cmd_drive_acl_authorize)
        p = sub.add_parser('portal-module-change-authorize')
        p.add_argument('--requester-user-id', required=True)
        p.add_argument('--channel-id', default='')
        p.add_argument('--module-id', default='')
        p.add_argument('--path', default='')

    def _pd_phase_21():
        nonlocal p
        p.add_argument('--change-class', default='in_scope_module_product')
        p.set_defaults(func=cmd_portal_module_change_authorize)
        p = sub.add_parser('work-manual-change-authorize')
        p.add_argument('--requester-user-id', required=True)
        p.add_argument('--channel-id', default='')
        p.add_argument('--chat-type', default='')
        p.add_argument('--document-key', default='it_manual')
        p.add_argument('--document-id', default='')
        p.add_argument('--change-class', default='secret_free_content_add')
        p.set_defaults(func=cmd_work_manual_change_authorize)
        p = sub.add_parser('google-docs-metadata-inspect')
        p.add_argument('--doc-id', required=True)
        p.add_argument('--changelog-heading', default='變更日誌 Changelog')
        p.add_argument('--limit', type=int, default=3)
        p.add_argument('--tab-id')
        p.add_argument('--account', default=DEFAULT_ACCOUNT())
        p.set_defaults(func=cmd_google_docs_metadata_inspect)
        return _PdReturn(ap)
    _pd_result = _pd_phase_19()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
    _pd_result = _pd_phase_20()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
    _pd_result = _pd_phase_21()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value

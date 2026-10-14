from __future__ import annotations
__all__ = ['worker_scheduling_setup_rules', '_push_apps_script_content', '_apps_script_project', '_apps_script_file', '_apps_script_syntax_check', '_apps_script_registered_projects', '_safe_staged_source_path', '_apps_script_patch_plan', '_apps_script_stage_file_plan', '_apps_script_verify', 'apps_script_project_ops', 'worker_scheduling_apps_script_patch', '_load_appsheet_record_ops_module', '_appsheet_quote', '_appsheet_hr_employee_compare_value', '_case_payload', '_validate_bulk_case_payload', '_plan_bulk_create_cases', '_find_case_by_id', '_find_case_by_parent_and_title', '_execute_bulk_create_cases', 'appsheet_record_ops', '_appsheet_hr_employee_subset', '_appsheet_hr_employee_plan', 'pd_one_appsheet_hr_employee_patch', 'pd_one_appsheet_table_probe', 'pd_one_appsheet_incident_morning_briefing_qa', 'pd_one_legacy_xls_inspect', 'pd_one_xlsx_workbook_inspect', 'pd_one_equipment_workbook_build', 'pd_one_item_number_xlsx_compiler', 'pd_one_item_number_render_qa_status', 'pd_one_item_number_historical_sample_summary', 'pd_one_item_number_local_fixture_copy', 'pd_one_doc_extract', 'pd_one_pptx_inspect', 'pd_one_pptx_ooxml_text_inspect', 'pd_one_artifact_base64_encode', 'pd_one_video_frame_sample', 'pd_one_local_video_compose', 'pd_one_origin_thread_media_deliver', 'pd_one_artifact_identity_inventory', 'pd_one_3mf_slicer_inspect', 'pd_one_svg_artifact_inspect', 'pd_one_svg_embed_image', 'pd_one_docx_inspect', 'pd_one_docx_body_xml_inspect', 'pd_one_docx_table_structure', 'pd_one_docx_layout_patch', 'pd_one_docx_table_search', 'pd_one_doc_detect_format', 'pd_one_sip_thread_index_build', 'pd_one_sip_thread_index_audit', 'pd_one_doc_build_artifact', 'pd_one_local_artifact_copy', 'pd_one_json_html_artifact_build', 'pd_one_office_html_to_docx', 'pd_one_ecrn_docx_unique_text_patch', 'pd_one_docx_exact_text_patch', 'pd_one_pptx_exact_text_patch', 'pd_one_pptx_from_template', 'pd_one_office_docprops_inspect', 'pd_one_office_visual_qa', 'pd_one_office_toolchain_status', 'pd_one_office_deb_contents', 'pd_one_item_number_workflow_check', 'pd_one_item_number_windows_excel_qa', 'pd_one_employee_watch', 'pd_one_office_convert_to_pdf', 'pd_one_drive_acl_authorize', 'pd_one_portal_module_change_authorize', 'pd_one_work_manual_change_authorize', 'pd_one_typhoon_automation', 'call_function_twin']
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union
from tools.pd_one_ops.pd_one_safe_ops_mcp_part0 import *

def worker_scheduling_setup_rules(*, dry_run: bool=True, confirm_live_write: Optional[str]=None, output_dir: Optional[str]=None) -> str:
    """Create and seed the one fixed Scheduling Rules tab with verified readback."""
    out_dir = _approved_output_dir(output_dir, 'setup-scheduling-rules')
    account = site_text('PDONE_EMAIL_ADMIN')
    token = _google_access_token(account)
    metadata_url = f'https://sheets.googleapis.com/v4/spreadsheets/{SOURCE_SPREADSHEET_ID()}?fields=spreadsheetId,properties.title,sheets.properties(sheetId,title,gridProperties)'
    metadata_before = _google_api_json(metadata_url, token=token)
    matching_sheets = [sheet.get('properties', {}) for sheet in metadata_before.get('sheets', []) if sheet.get('properties', {}).get('title') == SCHEDULING_RULES_SHEET]
    if len(matching_sheets) > 1:
        receipt = {'status': 'error', 'error': 'duplicate_scheduling_rules_tabs', 'sheet_name': SCHEDULING_RULES_SHEET, 'match_count': len(matching_sheets), 'dry_run': dry_run, 'safety': {'shell_used': False, 'spreadsheet_id_bound': True, 'readback_required': True}}
        _write_receipt(out_dir, 'setup-scheduling-rules-receipt.json', receipt)
        return _json_result(receipt)
    quoted_range = urllib.parse.quote(f"'{SCHEDULING_RULES_SHEET}'!A1:O2", safe='')
    existing_values: list[list[Any]] = []
    if matching_sheets:
        existing = _gog_get(SOURCE_SPREADSHEET_ID(), f"'{SCHEDULING_RULES_SHEET}'!A1:O2", account=account)
        if existing.get('status') != 'ok':
            receipt = {'status': 'error', 'error': 'scheduling_rules_existing_read_failed', 'detail': existing.get('stderr_tail') or existing.get('error'), 'dry_run': dry_run}
            _write_receipt(out_dir, 'setup-scheduling-rules-receipt.json', receipt)
            return _json_result(receipt)
        existing_values = _extract_values(existing)
    expected_values = [[str(cell) for cell in row] for row in SCHEDULING_RULES_VALUES()]
    normalized_existing = [[str(cell) for cell in row] for row in existing_values]
    if normalized_existing and normalized_existing != expected_values:
        receipt = {'status': 'error', 'error': 'scheduling_rules_existing_content_conflict', 'sheet_name': SCHEDULING_RULES_SHEET, 'existing_row_count': len(normalized_existing), 'expected_row_count': len(expected_values), 'dry_run': dry_run, 'safety': {'shell_used': False, 'overwrite_conflicts': False, 'readback_required': True}}
        _write_receipt(out_dir, 'setup-scheduling-rules-receipt.json', receipt)
        return _json_result(receipt)
    plan = {'status': 'ok', 'dry_run': dry_run, 'spreadsheet_id': SOURCE_SPREADSHEET_ID(), 'spreadsheet_title': metadata_before.get('properties', {}).get('title'), 'sheet_name': SCHEDULING_RULES_SHEET, 'sheet_exists_before': bool(matching_sheets), 'planned_actions': [*([] if matching_sheets else ['add_fixed_sheet']), 'write_fixed_headers_and_single_seed_row', 'freeze_and_style_header', 'verify_metadata_and_A1_O2_readback'], 'expected_values': expected_values, 'output_dir': str(out_dir), 'safety': {'shell_used': False, 'spreadsheet_id_bound': True, 'sheet_name_bound': True, 'payload_is_fixed': True, 'overwrite_conflicts': False, 'readback_required': True}}
    if dry_run:
        _write_receipt(out_dir, 'setup-scheduling-rules-receipt.json', plan)
        return _json_result(plan)
    if confirm_live_write != WORKER_SCHEDULING_SOURCE_CONFIRMATION:
        receipt = {**plan, 'status': 'error', 'error': 'live_confirmation_required'}
        _write_receipt(out_dir, 'setup-scheduling-rules-receipt.json', receipt)
        return _json_result(receipt)
    batch_url = f'https://sheets.googleapis.com/v4/spreadsheets/{SOURCE_SPREADSHEET_ID()}:batchUpdate'
    if not matching_sheets:
        add_result = _google_api_json(batch_url, token=token, method='POST', body={'requests': [{'addSheet': {'properties': {'title': SCHEDULING_RULES_SHEET, 'gridProperties': {'rowCount': 100, 'columnCount': len(SCHEDULING_RULES_VALUES()[0])}}}}]})
        replies = add_result.get('replies') or []
        if not replies or not replies[0].get('addSheet', {}).get('properties', {}).get('sheetId'):
            raise RuntimeError('Google Sheets addSheet response did not include the created sheetId')
    metadata_after_add = _google_api_json(metadata_url, token=token)
    created_matches = [sheet.get('properties', {}) for sheet in metadata_after_add.get('sheets', []) if sheet.get('properties', {}).get('title') == SCHEDULING_RULES_SHEET]
    if len(created_matches) != 1:
        raise RuntimeError(f'Expected one Scheduling Rules tab after add; found {len(created_matches)}')
    sheet_id = int(created_matches[0]['sheetId'])
    values_url = f'https://sheets.googleapis.com/v4/spreadsheets/{SOURCE_SPREADSHEET_ID()}/values/{quoted_range}?valueInputOption=RAW'
    _google_api_json(values_url, token=token, method='PUT', body={'range': f"'{SCHEDULING_RULES_SHEET}'!A1:O2", 'majorDimension': 'ROWS', 'values': expected_values})
    _google_api_json(batch_url, token=token, method='POST', body={'requests': [{'updateSheetProperties': {'properties': {'sheetId': sheet_id, 'gridProperties': {'frozenRowCount': 1}}, 'fields': 'gridProperties.frozenRowCount'}}, {'repeatCell': {'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 15}, 'cell': {'userEnteredFormat': {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.85, 'green': 0.93, 'blue': 0.85}}}, 'fields': 'userEnteredFormat(textFormat,backgroundColor)'}}, {'autoResizeDimensions': {'dimensions': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 15}}}]})
    metadata_verified = _google_api_json(metadata_url, token=token)
    verified_matches = [sheet.get('properties', {}) for sheet in metadata_verified.get('sheets', []) if sheet.get('properties', {}).get('title') == SCHEDULING_RULES_SHEET]
    readback = _gog_get(SOURCE_SPREADSHEET_ID(), f"'{SCHEDULING_RULES_SHEET}'!A1:O2", account=account)
    observed_values = [[str(cell) for cell in row] for row in _extract_values(readback)]
    verified = readback.get('status') == 'ok' and len(verified_matches) == 1 and (observed_values == expected_values) and (int(verified_matches[0].get('gridProperties', {}).get('frozenRowCount', 0)) == 1)
    receipt = {**plan, 'status': 'ok' if verified else 'error', 'dry_run': False, 'sheet_id': sheet_id, 'sheet_exists_after': len(verified_matches) == 1, 'frozen_row_count': verified_matches[0].get('gridProperties', {}).get('frozenRowCount') if verified_matches else None, 'observed_values': observed_values, 'readback_verified': verified}
    _write_receipt(out_dir, 'setup-scheduling-rules-receipt.json', receipt)
    return _json_result(receipt)

def _push_apps_script_content(project: dict[str, str], files: list[dict[str, Any]]) -> dict[str, Any]:
    token = _google_access_token(project['account'])
    req = urllib.request.Request(f'https://script.googleapis.com/v1/projects/{project['script_id']}/content', data=json.dumps({'files': files}).encode('utf-8'), headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'Accept': 'application/json'}, method='PUT')
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Apps Script updateContent HTTP {exc.code}: {body[:1000]}') from exc

def _apps_script_project(key: str, action: str | None=None) -> dict[str, Any]:
    from tools.pd_one_ops.apps_script_registry import assert_project_visible, visible_project_keys
    project_key = str(key or '').strip()
    projects = APPS_SCRIPT_ALLOWED_PROJECTS()
    project = projects.get(project_key)
    if project is None:
        raise ValueError(f'project_key must be one of: {visible_project_keys(projects)}')
    assert_project_visible(project)
    if action and action not in set(project.get('allowed_actions') or []):
        raise ValueError(f'action {action!r} is not allowed for project_key={project_key!r}')
    return project

def _apps_script_file(content: dict[str, Any], file_name: str) -> dict[str, Any]:
    for item in content.get('files') or []:
        if item.get('name') == file_name:
            return item
    raise ValueError(f'file_name {file_name!r} not found in registered Apps Script project')

def _apps_script_syntax_check(file_name: str, source: str, file_type: str | None=None) -> dict[str, Any]:
    ftype = str(file_type or '').upper()
    lower_name = str(file_name or '').lower()
    if ftype in {'JSON', 'HTML'} or lower_name in {'appsscript', 'appsscript.json'}:
        return {'skipped': True, 'reason': f'non_server_js_file:{ftype or lower_name}'}
    if ftype and ftype not in {'SERVER_JS', 'JAVASCRIPT', 'JS'}:
        return {'skipped': True, 'reason': f'unsupported_file_type:{ftype}'}
    APPS_SCRIPT_RECEIPTS().mkdir(parents=True, exist_ok=True)
    check_path = APPS_SCRIPT_RECEIPTS() / f'syntax-check-{_utc_stamp()}.js'
    check_path.write_text(source, encoding='utf-8')
    proc = subprocess.run(['node', '--check', str(check_path)], text=True, capture_output=True, timeout=60, shell=False)
    result = {'skipped': False, 'returncode': proc.returncode, 'stderr_tail': proc.stderr[-1000:], 'path': str(check_path), 'file_type': ftype or None}
    if proc.returncode != 0:
        raise ValueError(f'patched Apps Script file failed syntax check: {proc.stderr[-1000:]}')
    return result

def _apps_script_registered_projects() -> list[dict[str, Any]]:
    from tools.pd_one_ops.apps_script_registry import project_is_visible
    projects = []
    for key, project in sorted(APPS_SCRIPT_ALLOWED_PROJECTS().items()):
        if not project_is_visible(project):
            continue
        item = {'project_key': key, 'script_id': project['script_id'], 'account': project['account'], 'title': project['title'], 'spreadsheet_id': project.get('spreadsheet_id'), 'system': project.get('system'), 'allowed_actions': project.get('allowed_actions') or []}
        if project.get('registered_by'):
            item['registered_by'] = project['registered_by']
        if project.get('parent_file_id'):
            item['parent_file_id'] = project['parent_file_id']
        projects.append(item)
    return projects

def _safe_staged_source_path(path: str) -> Path:
    if not path:
        raise ValueError('staged_source_path is required for staged_file_replace')
    p = Path(path).expanduser().resolve()
    allowed_roots = [Path(resolve_configured_path('~/.hermes/profiles/pdone/tmp')), Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/tmp')), Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/projects')), Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/integrations'))]
    if not any((str(p).startswith(str(root.resolve()) + os.sep) or p == root.resolve() for root in allowed_roots)):
        raise ValueError('staged_source_path must be under an approved PD One tmp/project/integration root')
    if not p.is_file():
        raise FileNotFoundError(str(p))
    if p.stat().st_size > 300000:
        raise ValueError('staged source file exceeds MCP bounded size limit')
    return p

def _apps_script_patch_plan(project_key: str, file_name: str, old_string: str, new_string: str) -> tuple[dict[str, str], dict[str, Any], dict[str, Any], str]:
    key = str(project_key or '').strip()
    project = _apps_script_project(key, 'unique_text_patch')
    if not old_string:
        raise ValueError('old_string is required')
    if len(old_string) > 20000 or len(new_string) > 30000:
        raise ValueError('patch strings exceed bounded MCP limits')
    content = _load_apps_script_content(project)
    target = _apps_script_file(content, file_name)
    source = target.get('source') or ''
    count = source.count(old_string)
    if count != 1:
        raise ValueError(f'old_string must match exactly once; matched {count} times')
    patched = source.replace(old_string, new_string, 1)
    syntax = _apps_script_syntax_check(file_name, patched, target.get('type'))
    plan = {'project_key': key, 'script_id': project['script_id'], 'title': project['title'], 'file_name': file_name, 'patch_mode': 'unique_text_patch', 'matched_occurrences': count, 'old_length': len(source), 'new_length': len(patched), 'old_sha256': hashlib.sha256(source.encode('utf-8')).hexdigest(), 'new_sha256': hashlib.sha256(patched.encode('utf-8')).hexdigest(), 'syntax_check': syntax}
    target['source'] = patched
    return (project, content, plan, patched)

def _apps_script_stage_file_plan(project_key: str, file_name: str, staged_source_path: str) -> tuple[dict[str, str], dict[str, Any], dict[str, Any], str]:
    key = str(project_key or '').strip()
    project = _apps_script_project(key, 'staged_file_replace')
    content = _load_apps_script_content(project)
    target = _apps_script_file(content, file_name)
    old_source = target.get('source') or ''
    source_path = _safe_staged_source_path(staged_source_path)
    new_source = source_path.read_text(encoding='utf-8')
    syntax = _apps_script_syntax_check(file_name, new_source, target.get('type'))
    plan = {'project_key': key, 'script_id': project['script_id'], 'title': project['title'], 'file_name': file_name, 'patch_mode': 'staged_file_replace', 'staged_source_path': str(source_path), 'old_length': len(old_source), 'new_length': len(new_source), 'old_sha256': hashlib.sha256(old_source.encode('utf-8')).hexdigest(), 'new_sha256': hashlib.sha256(new_source.encode('utf-8')).hexdigest(), 'syntax_check': syntax}
    target['source'] = new_source
    return (project, content, plan, new_source)

def _apps_script_verify(content: dict[str, Any], file_name: str, required_strings: Optional[list[str]], expected_sha256: Optional[str]) -> dict[str, Any]:
    target = _apps_script_file(content, file_name)
    source = target.get('source') or ''
    missing = [s for s in required_strings or [] if s not in source]
    sha = hashlib.sha256(source.encode('utf-8')).hexdigest()
    return {'file_name': file_name, 'source_len': len(source), 'source_sha256': sha, 'required_strings_count': len(required_strings or []), 'missing_required_strings': missing, 'expected_sha256': expected_sha256, 'sha256_matches_expected': sha == expected_sha256 if expected_sha256 else None, 'ok': not missing and (not expected_sha256 or sha == expected_sha256)}

def _apps_script_registry_action(action_key: str, project_key: str, script_id: str, parent_file_id: str, dry_run: bool, confirm_live_register: Optional[str]) -> str | None:
    """Register, scope check, and list. None means a content or patch action follows."""
    if action_key == 'check_gog_scopes':
        from tools.pd_one_ops.apps_script_registry import gog_token_scope_report
        return _json_result({'status': 'ok', 'action': action_key, **gog_token_scope_report()})
    if action_key == 'register_project':
        from tools.pd_one_ops.apps_script_registry import note_result, register_apps_script_project
        result = register_apps_script_project(project_key=project_key, script_id=script_id, parent_file_id=parent_file_id, dry_run=bool(dry_run), confirm_live_register=confirm_live_register)
        note_result(action_key, result)
        return _json_result(result)
    if action_key == 'list_registered_projects':
        return _json_result({'status': 'ok', 'action': action_key, 'projects': _apps_script_registered_projects()})
    return None

def apps_script_project_ops(action: str='list_registered_projects', project_key: str='', file_name: str='Code', old_string: str='', new_string: str='', staged_source_path: str='', include_source: bool=False, max_source_chars: int=12000, required_strings: Optional[list[str]]=None, expected_sha256: Optional[str]=None, dry_run: bool=True, confirm_live_patch: Optional[str]=None, script_id: str='', parent_file_id: str='', confirm_live_register: Optional[str]=None, **_model_supplied: Any) -> str:
    """Registry-backed Apps Script operations for approved PD One projects.

    Actions: list_registered_projects, register_project, check_gog_scopes,
    get_content, verify_readback, unique_text_patch, staged_file_replace.
    register_project is dry-run unless confirm_live_register is
    'RUN LIVE APPS SCRIPT REGISTER'. The requester is the bound session, not
    a tool argument. Live projects.updateContent writes require exact
    confirmation RUN LIVE APPS SCRIPT PATCH.
    """
    del _model_supplied
    action_key = ''
    try:
        action_key = str(action or 'list_registered_projects').strip().lower().replace('-', '_')
        early = _apps_script_registry_action(action_key, project_key, script_id, parent_file_id, bool(dry_run), confirm_live_register)
        if early is not None:
            return early
        if action_key not in {'get_content', 'verify_readback', 'unique_text_patch', 'staged_file_replace'}:
            raise ValueError('action must be one of: list_registered_projects, register_project, check_gog_scopes, get_content, verify_readback, unique_text_patch, staged_file_replace')
        project = _apps_script_project(project_key, action_key)
        live = not bool(dry_run)
        if live and action_key in {'unique_text_patch', 'staged_file_replace'} and (confirm_live_patch != APPS_SCRIPT_LIVE_CONFIRMATION):
            raise ValueError(f'live Apps Script patches require confirm_live_patch={APPS_SCRIPT_LIVE_CONFIRMATION!r}')
        APPS_SCRIPT_RECEIPTS().mkdir(parents=True, exist_ok=True)
        receipt_path = APPS_SCRIPT_RECEIPTS() / f'{_utc_stamp()}-{project_key}-{action_key}.json'
        result: dict[str, Any] = {'status': 'ok', 'action': action_key, 'dry_run': not live, 'project': {k: project.get(k) for k in ('script_id', 'account', 'title', 'spreadsheet_id', 'system')}, 'safety': {'registered_project_only': True, 'live_write_confirmation_required': APPS_SCRIPT_LIVE_CONFIRMATION, 'requires_chat_layer_authorization': True, 'use_instead_of': 'terminal/code_execution/clasp/raw script.googleapis.com updateContent'}, 'receipt_path': str(receipt_path)}
        if action_key == 'get_content':
            content = _load_apps_script_content(project)
            files = []
            for f in content.get('files') or []:
                src = f.get('source') or ''
                item = {'name': f.get('name'), 'type': f.get('type'), 'source_len': len(src), 'source_sha256': hashlib.sha256(src.encode('utf-8')).hexdigest()}
                if include_source and f.get('name') == file_name:
                    item['source_truncated'] = len(src) > max_source_chars
                    item['source'] = src[:max(0, min(int(max_source_chars), 50000))]
                files.append(item)
            result['files'] = files
        elif action_key == 'verify_readback':
            content = _load_apps_script_content(project)
            result['verification'] = _apps_script_verify(content, file_name, required_strings, expected_sha256)
            result['status'] = 'ok' if result['verification']['ok'] else 'error'
        else:
            if action_key == 'unique_text_patch':
                project, content, plan, _patched = _apps_script_patch_plan(project_key, file_name, old_string, new_string)
            else:
                project, content, plan, _patched = _apps_script_stage_file_plan(project_key, file_name, staged_source_path)
            result['plan'] = plan
            if live:
                response = _push_apps_script_content(project, content['files'])
                readback = _load_apps_script_content(project)
                result['execution'] = {'updated_files': [{'name': f.get('name'), 'type': f.get('type'), 'source_len': len(f.get('source') or '')} for f in response.get('files', [])], 'readback': _apps_script_verify(readback, file_name, required_strings or [new_string] if action_key == 'unique_text_patch' and new_string else required_strings, plan.get('new_sha256'))}
                if not result['execution']['readback']['ok']:
                    result['status'] = 'error'
                    result['error'] = 'readback_verification_failed'
        receipt_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        from tools.pd_one_ops.apps_script_registry import note_result
        note_result(action_key, result)
        return _json_result(result)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        from tools.pd_one_ops.apps_script_registry import note_error
        note_error(action_key, project_key, script_id, exc)
        return _json_result({'status': 'error', 'error': 'invalid_request', 'detail': str(exc)})

def worker_scheduling_apps_script_patch(file_name: str='Code', old_string: str='', new_string: str='', dry_run: bool=True, confirm_live_patch: Optional[str]=None) -> str:
    """Patch the registered worker-scheduling bound Apps Script project with a unique text replacement.

    Dry-run is default. Live patching is limited to the registered Injection Molding
    worker-scheduling Apps Script project and requires confirm_live_patch='RUN LIVE APPS SCRIPT PATCH'.
    Use this instead of terminal/code_execution for Apps Script edits from PD One channels.
    """
    try:
        live = not bool(dry_run)
        if live and confirm_live_patch != APPS_SCRIPT_LIVE_CONFIRMATION:
            raise ValueError(f'live Apps Script patches require confirm_live_patch={APPS_SCRIPT_LIVE_CONFIRMATION!r}')
        project, content, plan, _patched = _apps_script_patch_plan('worker_scheduling', file_name, old_string, new_string)
        APPS_SCRIPT_RECEIPTS().mkdir(parents=True, exist_ok=True)
        receipt_path = APPS_SCRIPT_RECEIPTS() / f'{_utc_stamp()}-worker-scheduling-apps-script-patch.json'
        result: dict[str, Any] = {'status': 'ok', 'dry_run': not live, 'action': 'worker_scheduling_apps_script_patch', 'safety': {'registered_project_only': True, 'live_write_confirmation_required': APPS_SCRIPT_LIVE_CONFIRMATION, 'requires_chat_layer_authorization': True, 'use_instead_of': 'terminal/code_execution Apps Script updateContent'}, 'plan': plan, 'receipt_path': str(receipt_path)}
        if live:
            response = _push_apps_script_content(project, content['files'])
            result['execution'] = {'updated_files': [{'name': f.get('name'), 'type': f.get('type'), 'source_len': len(f.get('source') or '')} for f in response.get('files', [])]}
        receipt_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        from tools.pd_one_ops.apps_script_registry import note_result
        note_result('worker_scheduling_apps_script_patch', result)
        return _json_result(result)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        from tools.pd_one_ops.apps_script_registry import note_error
        note_error('worker_scheduling_apps_script_patch', 'worker_scheduling', '', exc)
        return _json_result({'status': 'error', 'error': 'invalid_request', 'detail': str(exc)})

def _load_appsheet_record_ops_module() -> Any:
    spec = importlib.util.spec_from_file_location('pdone_appsheet_record_ops', APPSHEET_RECORD_OPS())
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load AppSheet record ops module: {APPSHEET_RECORD_OPS()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def _appsheet_quote(value: str) -> str:
    return str(value).replace('"', '\\"')

def _appsheet_hr_employee_compare_value(field: str, value: Any) -> str:
    text = str(value).strip()
    return text.lower() if 'email' in field.lower() else text

def _case_payload(src: dict[str, Any], defaults: dict[str, Any], *, parent_case_id: str | None=None) -> dict[str, Any]:
    merged = {**defaults, **src}
    fields = dict(defaults.get('fields') or {})
    fields.update(src.get('fields') or {})
    row: dict[str, Any] = {}
    aliases = {'title': 'Title', 'description': 'Description', 'type': 'Type', 'sub_type': 'Sub-Type', 'subtype': 'Sub-Type', 'status': 'Status', 'responsible': 'Next Step Responsible Person', 'next_step_responsible': 'Next Step Responsible Person', 'created_by': 'Created By', 'deadline': 'Deadline', 'mattermost_link': 'Mattermost Link', 'other_link': 'Other Link', 'sqlsrv_link': 'sql-srv Link', 'customers': 'Customers', 'products': 'Products', 'molds': 'Molds', 'equipment': 'Equipment'}
    for key, column in aliases.items():
        value = merged.get(key)
        if value not in (None, '', []):
            row[column] = value
    if 'Status' not in row:
        row['Status'] = 'Not Started'
    if parent_case_id:
        row['Parent Case ID'] = parent_case_id
    row.update({k: v for k, v in fields.items() if v not in (None, '')})
    return row

def _validate_bulk_case_payload(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None, list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError('payload must be an object')
    parent = payload.get('parent')
    parent_case_id = (payload.get('parent_case_id') or '').strip() or None
    if parent is not None and (not isinstance(parent, dict)):
        raise ValueError('payload.parent must be an object when provided')
    cases = payload.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('payload.cases must be a non-empty list')
    if len(cases) > APPSHEET_BULK_MAX_ROWS:
        raise ValueError(f'bulk_create_cases supports at most {APPSHEET_BULK_MAX_ROWS} child cases per call')
    clean_cases: list[dict[str, Any]] = []
    seen_external: set[str] = set()
    for idx, item in enumerate(cases):
        if not isinstance(item, dict):
            raise ValueError(f'payload.cases[{idx}] must be an object')
        external = str(item.get('external_key') or '').strip()
        if external:
            if external in seen_external:
                raise ValueError(f'duplicate external_key in payload.cases: {external}')
            seen_external.add(external)
        clean_cases.append(item)
    if not parent_case_id and (not parent):
        raise ValueError('bulk_create_cases requires either parent_case_id or parent')
    defaults = payload.get('defaults') or {}
    if not isinstance(defaults, dict):
        raise ValueError('payload.defaults must be an object when provided')
    return (parent, parent_case_id, clean_cases, defaults)

def _plan_bulk_create_cases(payload: dict[str, Any]) -> dict[str, Any]:
    parent, parent_case_id, cases, defaults = _validate_bulk_case_payload(payload)
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    parent_ref = parent_case_id or '<created parent CaseID>'
    if parent:
        parent_row = _case_payload(parent, defaults)
        rows.append({'role': 'parent', 'external_key': parent.get('external_key'), 'row_payload': parent_row})
        if not parent_row.get('Title'):
            missing.append({'row': 'parent', 'field': 'title'})
    for idx, case in enumerate(cases):
        row = _case_payload(case, defaults, parent_case_id=parent_ref)
        rows.append({'role': 'child', 'index': idx, 'external_key': case.get('external_key'), 'row_payload': row})
        if not row.get('Title'):
            missing.append({'row': f'cases[{idx}]', 'field': 'title'})
    return {'action': 'bulk_create_cases', 'table': 'Case', 'will_create_parent': bool(parent), 'parent_case_id': parent_case_id, 'idempotency': payload.get('idempotency') or 'skip_existing_by_parent_and_title', 'total_rows': len(rows), 'child_count': len(cases), 'rows': rows, 'missing_required': missing, 'expected_side_effects': ['Case add automations may enqueue translation/notification work.']}

def _find_case_by_id(client: Any, case_id: str) -> list[dict[str, Any]]:
    return client.find('Case', f'Filter(Case, [CaseID] = "{_appsheet_quote(case_id)}")')

def _find_case_by_parent_and_title(client: Any, parent_case_id: str | None, title: str) -> list[dict[str, Any]]:
    parent_expr = 'ISBLANK([Parent Case ID])' if not parent_case_id else f'[Parent Case ID] = "{_appsheet_quote(parent_case_id)}"'
    return client.find('Case', f'Filter(Case, AND({parent_expr}, [Title] = "{_appsheet_quote(title)}"))')

def _execute_bulk_create_cases(payload: dict[str, Any], env_key: str) -> dict[str, Any]:
    plan = _plan_bulk_create_cases(payload)
    if plan['missing_required']:
        return {'status': 'error', 'error': 'missing_required', 'plan': plan}
    module = _load_appsheet_record_ops_module()
    client = module.AppSheetClient(str(APPSHEET_ENV_FILES()[env_key]), str(APPSHEET_SCHEMA_MAP()))
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    readback: list[dict[str, Any]] = []
    parent_case_id = plan.get('parent_case_id')
    if parent_case_id:
        matches = _find_case_by_id(client, parent_case_id)
        if len(matches) != 1:
            return {'status': 'error', 'error': 'parent_case_not_found_or_ambiguous', 'parent_case_id': parent_case_id, 'match_count': len(matches), 'plan': plan}
        readback.append({'role': 'parent', 'row': matches[0]})
    elif plan['will_create_parent']:
        parent_row = plan['rows'][0]['row_payload']
        existing = _find_case_by_parent_and_title(client, None, str(parent_row.get('Title', '')))
        if existing and (payload.get('idempotency') or 'skip_existing_by_parent_and_title') == 'skip_existing_by_parent_and_title':
            parent_case_id = existing[0].get('CaseID')
            skipped.append({'role': 'parent', 'reason': 'existing_title', 'CaseID': parent_case_id, 'Title': parent_row.get('Title')})
            readback.append({'role': 'parent', 'row': existing[0]})
        else:
            added = client.add('Case', parent_row)
            parent_case_id = (added[0] if added else {}).get('CaseID')
            if not parent_case_id:
                return {'status': 'error', 'error': 'parent_created_without_caseid', 'created_parent_rows': added, 'plan': plan}
            created.append({'role': 'parent', 'rows': added})
            rb = _find_case_by_id(client, str(parent_case_id))
            readback.extend(({'role': 'parent', 'row': row} for row in rb))
    for row_plan in [r for r in plan['rows'] if r['role'] == 'child']:
        row = dict(row_plan['row_payload'])
        row['Parent Case ID'] = parent_case_id
        title = str(row.get('Title', ''))
        existing = _find_case_by_parent_and_title(client, str(parent_case_id), title)
        if existing and plan['idempotency'] == 'skip_existing_by_parent_and_title':
            skipped.append({'role': 'child', 'reason': 'existing_parent_title', 'CaseID': existing[0].get('CaseID'), 'Title': title})
            readback.append({'role': 'child', 'row': existing[0]})
            continue
        added = client.add('Case', row)
        created.append({'role': 'child', 'title': title, 'rows': added})
        for added_row in added:
            cid = added_row.get('CaseID')
            if cid:
                readback.extend(({'role': 'child', 'row': rb} for rb in _find_case_by_id(client, str(cid))))
    return {'status': 'ok', 'plan': plan, 'parent_case_id': parent_case_id, 'created': created, 'skipped': skipped, 'readback': readback}

def appsheet_record_ops(request: str='', dry_run: bool=True, live_lookup: bool=True, env: str='deployed', confirm_live_write: Optional[str]=None, timeout_seconds: int=300, action: str='nl_request', payload: Optional[dict[str, Any]]=None, requester_person_id: Optional[str]=None, requester_email: Optional[str]=None) -> str:
    """Plan or execute bounded AppSheet Case/ActivityLog/Case_Updates record operations.

    Actions:
    - nl_request: parse the natural-language request string with the seed record-op backend.
    - bulk_create_cases: create many Case rows under an existing or newly-created parent Case.

    Dry-runs are default. Live writes require
    confirm_live_write='RUN LIVE APPSHEET RECORD OPS' plus the chat-layer
    AppSheet write authorization/confirmation policy.

    For Case_Updates Add, pass requester_person_id (HR PersonID for Created By)
    and requester_email (company email for RunAsUserEmail). This wrapper does
    not perform AppSheet definition/saveapp writes.
    """
    try:
        action_key = str(action or 'nl_request').strip().lower().replace('-', '_')
        env_key = str(env or 'deployed').strip().lower()
        if env_key not in APPSHEET_ENV_FILES():
            raise ValueError(f'env must be one of: {sorted(APPSHEET_ENV_FILES())}')
        live = not bool(dry_run)
        if live and confirm_live_write != APPSHEET_LIVE_CONFIRMATION:
            raise ValueError(f'live AppSheet writes require confirm_live_write={APPSHEET_LIVE_CONFIRMATION!r}')
        safety = {'use_instead_of': 'execute_code/terminal AppSheet API scripts', 'live_write_requested': live, 'live_write_confirmation_required': APPSHEET_LIVE_CONFIRMATION, 'requires_chat_layer_authorization': True, 'shell_used': False}
        if action_key == 'bulk_create_cases':
            plan = _plan_bulk_create_cases(payload or {})
            result = plan if not live else _execute_bulk_create_cases(payload or {}, env_key)
            return _json_result({'status': result.get('status', 'ok') if isinstance(result, dict) else 'ok', 'dry_run': not live, 'env': env_key, 'action': action_key, 'safety': safety, 'plan': plan, 'execution': result if live else None})
        if action_key != 'nl_request':
            raise ValueError('action must be one of: nl_request, bulk_create_cases')
        text = str(request or '').strip()
        if not text:
            raise ValueError('request is required for action=nl_request')
        if len(text) > 3000:
            raise ValueError('request is too long for the bounded AppSheet record-ops wrapper')
        if not APPSHEET_RECORD_OPS().exists():
            raise FileNotFoundError(str(APPSHEET_RECORD_OPS()))
        cmd = [sys.executable, str(APPSHEET_RECORD_OPS()), text, '--env-file', str(APPSHEET_ENV_FILES()[env_key]), '--schema-map', str(APPSHEET_SCHEMA_MAP())]
        if live_lookup or live:
            cmd.append('--live-lookup')
        if live:
            cmd.append('--execute')
        person_id = str(requester_person_id or '').strip()
        email = str(requester_email or '').strip()
        if person_id:
            cmd.extend(['--created-by', person_id])
        if email:
            cmd.extend(['--run-as-email', email])
        result = _run_cmd(cmd, timeout=max(30, min(int(timeout_seconds), 900)))
        payload: dict[str, Any] = {'status': result.get('status'), 'dry_run': not live, 'env': env_key, 'safety': {'use_instead_of': 'execute_code/terminal AppSheet API scripts', 'live_write_requested': live, 'live_write_confirmation_required': APPSHEET_LIVE_CONFIRMATION, 'requires_chat_layer_authorization': True, 'shell_used': False}, 'result': result}
        if result.get('status') == 'ok':
            if isinstance(result.get('payload'), dict):
                payload['plan'] = result['payload']
            else:
                try:
                    payload['plan'] = json.loads(result.get('stdout') or result.get('stdout_tail') or '{}')
                except Exception:
                    logging.getLogger('pd_one_ops').exception('pd one command failed')
                    payload['plan_parse_error'] = True
        return _json_result(payload)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'error': 'invalid_request', 'detail': str(exc)})

def _appsheet_hr_employee_subset(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in APPSHEET_HR_EMPLOYEE_READBACK_FIELDS}

def _appsheet_hr_employee_plan(client: Any, person_id: str, updates: dict[str, Any], *, expected_name_zh: Optional[str]=None, expected_company_email: Optional[str]=None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    person_id = str(person_id or '').strip()
    if not person_id:
        raise ValueError('person_id is required')
    if not isinstance(updates, dict) or not updates:
        raise ValueError('updates must be a non-empty object')
    if len(updates) > len(APPSHEET_HR_EMPLOYEE_ALLOWED_FIELDS):
        raise ValueError(f'updates has too many fields; allowed at most {len(APPSHEET_HR_EMPLOYEE_ALLOWED_FIELDS)}')
    invalid = sorted((key for key in updates if key not in APPSHEET_HR_EMPLOYEE_ALLOWED_FIELDS or key == 'PersonID'))
    if invalid:
        raise ValueError(f'unsupported HR_Employees fields: {invalid}. Allowed: {sorted(APPSHEET_HR_EMPLOYEE_ALLOWED_FIELDS)}')
    normalized_updates: dict[str, Any] = {}
    for key, value in updates.items():
        if isinstance(value, (dict, list)):
            raise ValueError(f'update {key!r} must be a scalar value')
        if value is None:
            raise ValueError(f'update {key!r} cannot be null')
        if isinstance(value, str) and (not value.strip()):
            raise ValueError(f'update {key!r} cannot be empty')
        normalized_updates[key] = value
    selector = f'FILTER("HR_Employees", [PersonID] = "{_appsheet_quote(person_id)}")'
    rows = client.find('HR_Employees', selector)
    if len(rows) != 1:
        raise ValueError(f'expected exactly 1 HR_Employees row for PersonID={person_id}, got {len(rows)}')
    current = rows[0]
    expected_checks: dict[str, Any] = {}
    if expected_name_zh is not None and str(expected_name_zh).strip():
        expected_checks['Name_ZH'] = expected_name_zh
        if str(current.get('Name_ZH', '')).strip() != str(expected_name_zh).strip():
            raise ValueError(f'Name_ZH mismatch for PersonID={person_id}: expected {expected_name_zh!r}, got {current.get('Name_ZH')!r}')
    if expected_company_email is not None and str(expected_company_email).strip():
        expected_checks['Company Email'] = expected_company_email
        if _appsheet_hr_employee_compare_value('Company Email', current.get('Company Email', '')) != _appsheet_hr_employee_compare_value('Company Email', expected_company_email):
            raise ValueError(f'Company Email mismatch for PersonID={person_id}: expected {expected_company_email!r}, got {current.get('Company Email')!r}')
    changed_fields = [key for key, value in normalized_updates.items() if _appsheet_hr_employee_compare_value(key, current.get(key, '')) != _appsheet_hr_employee_compare_value(key, value)]
    plan = {'table': 'HR_Employees', 'person_id': person_id, 'selector': selector, 'matched_rows': len(rows), 'expected_checks': expected_checks, 'current_row': _appsheet_hr_employee_subset(current), 'requested_updates': normalized_updates, 'changed_fields': changed_fields, 'no_op': not changed_fields}
    return (plan, current, normalized_updates, changed_fields)

def pd_one_appsheet_hr_employee_patch(person_id: str, updates: dict[str, Any], dry_run: bool=True, env: str='deployed', expected_name_zh: Optional[str]=None, expected_company_email: Optional[str]=None, confirm_live_write: Optional[str]=None) -> str:
    """Dry-run or confirmed live patch of one HR_Employees row by exact PersonID with readback verification."""
    try:
        env_key = str(env or 'deployed').strip().lower()
        if env_key not in APPSHEET_ENV_FILES():
            raise ValueError(f'env must be one of: {sorted(APPSHEET_ENV_FILES())}')
        module = _load_appsheet_record_ops_module()
        client = module.AppSheetClient(str(APPSHEET_ENV_FILES()[env_key]), str(APPSHEET_SCHEMA_MAP()))
        plan, current, normalized_updates, changed_fields = _appsheet_hr_employee_plan(client, person_id, updates, expected_name_zh=expected_name_zh, expected_company_email=expected_company_email)
        live = not bool(dry_run)
        safety = {'use_instead_of': 'execute_code/terminal AppSheet API scripts', 'live_write_requested': live, 'live_write_confirmation_required': APPSHEET_LIVE_CONFIRMATION, 'requires_chat_layer_authorization': True, 'shell_used': False, 'selector_exact_person_id': True, 'allowed_update_fields_bounded': True, 'readback_verification_required': True}
        if not live:
            return _json_result({'status': 'ok', 'dry_run': True, 'env': env_key, 'capability': 'pd_one_appsheet_hr_employee_patch', 'safety': safety, 'plan': plan, 'execution': None})
        if confirm_live_write != APPSHEET_LIVE_CONFIRMATION:
            raise ValueError(f'live AppSheet HR_Employees writes require confirm_live_write={APPSHEET_LIVE_CONFIRMATION!r}')
        if not changed_fields:
            return _json_result({'status': 'ok', 'dry_run': False, 'env': env_key, 'capability': 'pd_one_appsheet_hr_employee_patch', 'safety': safety, 'plan': plan, 'execution': {'status': 'noop', 'api_rows_returned': 0, 'verified': True, 'mismatches': [], 'readback_subset': _appsheet_hr_employee_subset(current)}})
        payload = {'PersonID': plan['person_id']}
        for key in changed_fields:
            payload[key] = normalized_updates[key]
        api_rows = client.edit('HR_Employees', payload)
        readback_rows = client.find('HR_Employees', plan['selector'])
        if len(readback_rows) != 1:
            raise RuntimeError(f'expected exactly 1 HR_Employees row after edit, got {len(readback_rows)}')
        readback = readback_rows[0]
        mismatches = [f'{key}: expected {normalized_updates[key]!r}, got {readback.get(key)!r}' for key in changed_fields if _appsheet_hr_employee_compare_value(key, readback.get(key, '')) != _appsheet_hr_employee_compare_value(key, normalized_updates[key])]
        execution = {'api_rows_returned': len(api_rows), 'verified': not mismatches, 'mismatches': mismatches, 'readback_subset': _appsheet_hr_employee_subset(readback)}
        if mismatches:
            return _json_result({'status': 'error', 'error': 'readback_verification_failed', 'env': env_key, 'capability': 'pd_one_appsheet_hr_employee_patch', 'safety': safety, 'plan': plan, 'execution': execution})
        return _json_result({'status': 'ok', 'dry_run': False, 'env': env_key, 'capability': 'pd_one_appsheet_hr_employee_patch', 'safety': safety, 'plan': plan, 'execution': execution})
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'error': 'invalid_request', 'detail': str(exc)})

def pd_one_appsheet_table_probe(table: str, selector: str, env: str='prototype') -> str:
    """Read a bounded AppSheet table sample without execute_code or raw probe scripts."""
    table = str(table or '').strip()
    selector = str(selector or '').strip()
    env_key = str(env or 'prototype').strip().lower()
    if not table or len(table) > 120:
        raise ValueError('table must be non-empty and <= 120 characters')
    if not selector or len(selector) > 3000:
        raise ValueError('selector must be non-empty and <= 3000 characters')
    if env_key not in APPSHEET_ENV_FILES():
        raise ValueError(f'env must be one of: {sorted(APPSHEET_ENV_FILES())}')
    cmd = [sys.executable, str(SAFE_OPS()), 'appsheet-table-probe', '--table', table, '--selector', selector, '--env', env_key]
    return run_json(cmd, timeout=300)

def pd_one_appsheet_incident_morning_briefing_qa() -> str:
    """Run the fixed AppSheet incident morning briefing helper QA without execute_code."""
    return run_json([sys.executable, str(SAFE_OPS()), 'appsheet-incident-morning-briefing-qa'], timeout=180)

def pd_one_legacy_xls_inspect(input_path: str, sheet: Optional[str]=None, max_sheets: int=10, preview_rows: int=25, preview_cols: int=25, max_nonempty_cells: int=400, max_merged_cells: int=20) -> str:
    """Inspect a bounded legacy .xls workbook without execute_code or raw xlrd loops."""
    cmd = [sys.executable, str(SAFE_OPS()), 'legacy-xls-inspect', '--input', input_path, '--max-sheets', str(max(1, min(int(max_sheets), 50))), '--preview-rows', str(max(1, min(int(preview_rows), 100))), '--preview-cols', str(max(1, min(int(preview_cols), 100))), '--max-nonempty-cells', str(max(1, min(int(max_nonempty_cells), 2000))), '--max-merged-cells', str(max(0, min(int(max_merged_cells), 200)))]
    if sheet:
        cmd += ['--sheet', sheet]
    return run_json(cmd, timeout=180)

def pd_one_xlsx_workbook_inspect(input_paths: list[str], sheet: Optional[str]=None, preview_input: Optional[str]=None, row_start: int=1, row_end: int=25, max_columns: int=25, include_values: bool=False) -> str:
    """Read bounded XLSX/XLSM workbook metadata and optional sheet values in admin scope."""
    if not input_paths or len(input_paths) > 12:
        raise ValueError('input_paths must contain 1 to 12 approved workbook paths')
    if sheet is not None and len(str(sheet)) > 200:
        raise ValueError('sheet must be <= 200 characters')
    cmd = [sys.executable, str(SAFE_OPS()), 'xlsx-workbook-inspect']
    for input_path in input_paths:
        cmd += ['--input', str(input_path)]
    if sheet:
        cmd += ['--sheet', sheet]
    if preview_input:
        cmd += ['--preview-input', preview_input]
    cmd += ['--row-start', str(max(1, min(int(row_start), 500))), '--row-end', str(max(1, min(int(row_end), 500))), '--max-columns', str(max(1, min(int(max_columns), 100)))]
    if include_values:
        cmd.append('--include-values')
    return run_json(cmd, timeout=180)

def pd_one_equipment_workbook_build(action: str='check') -> str:
    """Check or stage the fixed three-source internal equipment workbook without execute_code."""
    action = str(action or 'check').strip().lower()
    if action not in {'check', 'stage'}:
        raise ValueError('action must be one of: check, stage')
    timeout = 300 if action == 'stage' else 180
    return run_json([sys.executable, str(SAFE_OPS()), 'equipment-workbook-build', '--action', action], timeout=timeout)

def pd_one_item_number_xlsx_compiler(action: str='smoke') -> str:
    """Smoke-check the item-number XLSX compiler without ad hoc execute_code."""
    action = str(action or 'smoke').strip()
    if action not in {'check', 'smoke'}:
        raise ValueError('action must be one of: check, smoke')
    cmd = [sys.executable, str(SAFE_OPS()), 'item-number-xlsx-compiler', '--action', action]
    timeout = 600 if action == 'smoke' else 900
    return run_json(cmd, timeout=timeout)

def pd_one_item_number_render_qa_status() -> str:
    """Inspect the fixed item-number workflow render QA receipts and blockers."""
    return run_json([sys.executable, str(SAFE_OPS()), 'item-number-render-qa-status'], timeout=60)

def pd_one_item_number_historical_sample_summary() -> str:
    """Summarize the fixed ten-file historical item-number XLS sample without execute_code."""
    return run_json([sys.executable, str(SAFE_OPS()), 'item-number-historical-sample-summary'], timeout=240)

def pd_one_item_number_local_fixture_copy() -> str:
    """Stage and locally render the fixed item-number XLS/XLSX QA fixture set."""
    return run_json([sys.executable, str(SAFE_OPS()), 'item-number-local-fixture-copy'], timeout=900)

def pd_one_doc_extract(input_path: str) -> str:
    """Extract bounded document text. DOCX receipts include indexed body paragraphs; PPTX receipts include package stats plus bounded slide text. The exact canonical company-announcement template is allowlisted read-only."""
    return run_json([sys.executable, str(SAFE_OPS()), 'doc-extract', '--input', input_path], timeout=120)

def pd_one_pptx_inspect(input_path: str, include_text: bool=True) -> str:
    """Inspect one bounded PPTX for slide dimensions and recursive shape/run text in admin scope."""
    cmd = [sys.executable, str(SAFE_OPS()), 'pptx-inspect', '--input', input_path]
    if not include_text:
        cmd.append('--no-text')
    return run_json(cmd, timeout=120)

def pd_one_pptx_ooxml_text_inspect(input_path: str, members: list[str]) -> str:
    """Inspect bounded DrawingML a:t text from allowlisted PPTX slide/diagram/notes/chart members in admin scope."""
    if not members or len(members) > 12:
        raise ValueError('members must contain 1-12 allowlisted PPTX package paths')
    if len(set(members)) != len(members):
        raise ValueError('members must be unique')
    cmd = [sys.executable, str(SAFE_OPS()), 'pptx-ooxml-text-inspect', '--input', input_path]
    for member in members:
        cmd.extend(['--member', str(member)])
    return run_json(cmd, timeout=120)

def pd_one_artifact_base64_encode(input_path: str) -> str:
    """Base64-encode one bounded SVG/image/PDF artifact from approved PD One roots in admin scope."""
    return run_json([sys.executable, str(SAFE_OPS()), 'artifact-base64-encode', '--input', input_path], timeout=30)

def pd_one_video_frame_sample(input_path: str) -> str:
    """Probe one cached video and stage fixed 15%/50%/85% JPEG frames in admin scope."""
    return run_json([sys.executable, str(SAFE_OPS()), 'video-frame-sample', '--input', input_path], timeout=240)

def pd_one_local_video_compose(inputs: list[str], output_path: str) -> str:
    """Compose one bounded H.264 MP4 from approved cached videos/images."""
    cmd = [sys.executable, str(MEDIA_OPS()), 'compose']
    for item in inputs:
        cmd.extend(['--input', item])
    cmd.extend(['--out', output_path])
    return run_json(cmd, timeout=300)

def pd_one_origin_thread_media_deliver(ticket_id: str, file_path: str, channel_id: str, root_id: str, message: str='') -> str:
    """Post one composed artifact back to the exact bound origin thread."""
    cmd = [sys.executable, str(MEDIA_OPS()), 'deliver-origin-thread', '--ticket-id', ticket_id, '--file', file_path, '--channel-id', channel_id, '--root-id', root_id]
    if message:
        cmd.extend(['--message', message])
    return run_json(cmd, timeout=120)

def pd_one_artifact_identity_inventory(root: str, globs: list[str] | None=None, peek: str | None=None, peek_bytes: int=8) -> str:
    """List bounded artifact identities and peek one file magic in admin scope."""
    cmd = [sys.executable, str(SAFE_OPS()), 'artifact-identity-inventory', '--root', root]
    for pattern in globs or []:
        cmd.extend(['--glob', pattern])
    if peek:
        cmd.extend(['--peek', peek])
    if peek_bytes != 8:
        cmd.extend(['--peek-bytes', str(peek_bytes)])
    return run_json(cmd, timeout=30)

def pd_one_3mf_slicer_inspect(input_path: str, action: str='inspect') -> str:
    """Inspect or stage allowlisted PrusaSlicer metadata from one approved 3MF."""
    if action not in {'inspect', 'stage'}:
        raise ValueError('action must be inspect or stage')
    return run_json([sys.executable, str(SAFE_OPS()), '3mf-slicer-inspect', '--action', action, '--input', input_path], timeout=45)

def pd_one_svg_artifact_inspect(input_path: str, required_texts: list[str] | None=None, expected_embedded_png_count: int | None=None, max_text_y_exclusive: float | None=None, expected_image_box: str | None=None) -> str:
    """Read-only bounded SVG XML/text/image/layout invariant inspection in admin scope."""
    cmd = [sys.executable, str(SAFE_OPS()), 'svg-artifact-inspect', '--input', input_path]
    for text in required_texts or []:
        cmd.extend(['--required-text', text])
    if expected_embedded_png_count is not None:
        cmd.extend(['--expected-embedded-png-count', str(expected_embedded_png_count)])
    if max_text_y_exclusive is not None:
        cmd.extend(['--max-text-y-exclusive', str(max_text_y_exclusive)])
    if expected_image_box:
        cmd.extend(['--expected-image-box', expected_image_box])
    return run_json(cmd, timeout=30)

def pd_one_svg_embed_image(input_path: str, action: str='inspect') -> str:
    """Inspect or stage an SVG with the fixed Pro-Design logo embedded; never overwrite the source."""
    if action not in {'inspect', 'stage'}:
        raise ValueError('action must be inspect or stage')
    return run_json([sys.executable, str(SAFE_OPS()), 'svg-embed-image', '--action', action, '--input', input_path], timeout=45)

def pd_one_docx_inspect(input_path: str, table_index: int, row_index: int, cell_index: int, paragraph_index: int=0, include_runs: bool=True) -> str:
    """Inspect one bounded DOCX table-cell paragraph and optional run text in admin scope."""
    indices = {'table_index': table_index, 'row_index': row_index, 'cell_index': cell_index, 'paragraph_index': paragraph_index}
    for name, value in indices.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or (value > 500):
            raise ValueError(f'{name} must be an integer from 0 through 500')
    cmd = [sys.executable, str(SAFE_OPS()), 'docx-inspect', '--input', input_path, '--table-index', str(table_index), '--row-index', str(row_index), '--cell-index', str(cell_index), '--paragraph-index', str(paragraph_index)]
    if not include_runs:
        cmd.append('--no-runs')
    return run_json(cmd, timeout=120)

def pd_one_docx_body_xml_inspect(input_path: str, paragraph_indices: list[int]) -> str:
    """Inspect bounded XML/text/run receipts for selected body-wide DOCX paragraphs in admin scope."""
    if not paragraph_indices or len(paragraph_indices) > 20:
        raise ValueError('paragraph_indices must contain 1-20 values')
    if any((isinstance(index, bool) or not isinstance(index, int) or index < 0 or (index > 5000) for index in paragraph_indices)):
        raise ValueError('paragraph_indices must be integers from 0 through 5000')
    if len(set(paragraph_indices)) != len(paragraph_indices):
        raise ValueError('paragraph_indices must be unique')
    cmd = [sys.executable, str(SAFE_OPS()), 'docx-body-xml-inspect', '--input', input_path]
    for index in paragraph_indices:
        cmd.extend(['--paragraph-index', str(index)])
    return run_json(cmd, timeout=120)

def pd_one_docx_table_structure(input_path: str) -> str:
    """Inspect bounded DOCX table grid widths, row/cell counts, and visible text in admin scope."""
    return run_json([sys.executable, str(SAFE_OPS()), 'docx-table-structure', '--input', input_path], timeout=120)

def pd_one_docx_layout_patch(input_path: str, target_text: str, action: str='inspect', output_path: Optional[str]=None, source_sha256: Optional[str]=None, overwrite: bool=False) -> str:
    """Inspect or stage a bounded DOCX section-start layout patch without overwriting the source."""
    action = str(action or 'inspect').strip().lower()
    if action not in {'inspect', 'stage'}:
        raise ValueError('action must be one of: inspect, stage')
    if action == 'stage' and (not output_path):
        raise ValueError('output_path is required for action=stage')
    cmd = [sys.executable, str(SAFE_OPS()), 'docx-layout-patch', '--action', action, '--input', input_path, '--target-text', target_text]
    if output_path:
        cmd += ['--out', output_path]
    if source_sha256:
        cmd += ['--source-sha256', source_sha256]
    if overwrite:
        cmd.append('--overwrite')
    return run_json(cmd, timeout=300)

def pd_one_docx_table_search(input_path: str, terms: list[str]) -> str:
    """Find terms in bounded DOCX table cells and return coordinates plus local cell structure."""
    if not isinstance(terms, list) or not terms:
        raise ValueError('terms must be a non-empty list')
    cleaned = [str(term).strip() for term in terms if str(term).strip()]
    if not cleaned or len(cleaned) > 8 or any((len(term) > 128 for term in cleaned)):
        raise ValueError('terms must contain 1-8 non-empty values of at most 128 characters')
    cmd = [sys.executable, str(SAFE_OPS()), 'docx-table-search', '--input', input_path]
    for term in cleaned:
        cmd.extend(['--term', term])
    return run_json(cmd, timeout=120)

def pd_one_doc_detect_format(input_path: str, include_text: bool=False) -> str:
    """Detect whether a requester-provided document should use the company announcement template."""
    cmd = [sys.executable, str(SAFE_OPS()), 'doc-detect-format', '--input', input_path]
    if include_text:
        cmd.append('--include-text')
    return run_json(cmd, timeout=120)

def pd_one_sip_thread_index_build() -> str:
    """Build the sanitized SIP討論串 workbook from fixed JSON inputs and return a verification receipt."""
    cmd = [sys.executable, str(SAFE_OPS()), 'sip-thread-index-build']
    return run_json(cmd, timeout=300)

def pd_one_sip_thread_index_audit(max_samples: int=25) -> str:
    """Audit the fixed SIP thread JSON inputs for malformed, noisy, and conflicting rows."""
    cmd = [sys.executable, str(SAFE_OPS()), 'sip-thread-index-audit', '--max-samples', str(max(1, min(int(max_samples), 100)))]
    return run_json(cmd, timeout=180)

def pd_one_doc_build_artifact(spec_path: str, output_path: str, visual_qa: bool=False) -> str:
    """Build bounded DOCX, including fixed company-announcement template replacement specs."""
    cmd = [sys.executable, str(SAFE_OPS()), 'doc-build', '--spec', spec_path, '--out', output_path]
    if visual_qa:
        cmd.append('--visual-qa')
    return run_json(cmd, timeout=300)

def pd_one_local_artifact_copy(input_path: str, output_path: str, source_sha256: Optional[str]=None) -> str:
    """Copy one bounded legacy employee artifact to its matching canonical artifact path."""
    cmd = [sys.executable, str(SAFE_OPS()), 'local-artifact-copy', '--input', input_path, '--out', output_path]
    if source_sha256:
        cmd += ['--source-sha256', source_sha256]
    return run_json(cmd, timeout=120)

def pd_one_json_html_artifact_build(spec_path: str, output_path: str) -> str:
    """Render one bounded JSON paragraphs spec to local HTML under approved PD One roots."""
    cmd = [sys.executable, str(SAFE_OPS()), 'json-html-artifact', '--spec', spec_path, '--out', output_path]
    return run_json(cmd, timeout=120)

def pd_one_office_html_to_docx(input_path: str, output_path: str) -> str:
    """Convert one approved HTML artifact to DOCX through isolated LibreOffice; source is read-only."""
    cmd = [sys.executable, str(SAFE_OPS()), 'office-html-to-docx', '--input', input_path, '--out', output_path]
    return run_json(cmd, timeout=300)

def pd_one_ecrn_docx_unique_text_patch(input_path: str, old_text: str, new_text: str, action: str='inspect', output_path: Optional[str]=None, source_sha256: Optional[str]=None, overwrite: bool=False) -> str:
    """Inspect or stage one exact visible-text replacement in an admin-only ECRN DOCX artifact.

    Inspection is the default. Staging writes a separate local artifact only; it
    never overwrites the source, sends the file, or treats prior approval/signature
    metadata as valid for the revised document.
    """
    action = str(action or 'inspect').strip().lower()
    if action not in {'inspect', 'stage'}:
        raise ValueError('action must be one of: inspect, stage')
    if action == 'stage' and (not output_path):
        raise ValueError('output_path is required for action=stage')
    cmd = [sys.executable, str(SAFE_OPS()), 'ecrn-docx-unique-text-patch', '--action', action, '--input', input_path, '--old-text', old_text, '--new-text', new_text]
    if output_path:
        cmd += ['--out', output_path]
    if source_sha256:
        cmd += ['--source-sha256', source_sha256]
    if overwrite:
        cmd.append('--overwrite')
    return run_json(cmd, timeout=300)

def pd_one_docx_exact_text_patch(input_path: str, replacements: list[list[str]], action: str='inspect', output_path: Optional[str]=None, source_sha256: Optional[str]=None, overwrite: bool=False) -> str:
    """Inspect or stage 1-8 exact visible-text replacements in a separate local DOCX.

    The source is never overwritten. Each old text must have exactly one visible,
    run-preserving match. Stage output stays local; this tool never sends files.
    """
    action = str(action or 'inspect').strip().lower()
    if action not in {'inspect', 'stage'}:
        raise ValueError('action must be one of: inspect, stage')
    if action == 'stage' and (not output_path):
        raise ValueError('output_path is required for action=stage')
    if not isinstance(replacements, list) or not 1 <= len(replacements) <= 8:
        raise ValueError('replacements must contain 1-8 old/new pairs')
    cmd = [sys.executable, str(SAFE_OPS()), 'docx-exact-text-patch', '--action', action, '--input', input_path]
    for pair in replacements:
        if not isinstance(pair, list) or len(pair) != 2 or (not all((isinstance(value, str) for value in pair))):
            raise ValueError('each replacement must be a two-string [old_text, new_text] pair')
        cmd += ['--replace', pair[0], pair[1]]
    if output_path:
        cmd += ['--out', output_path]
    if source_sha256:
        cmd += ['--source-sha256', source_sha256]
    if overwrite:
        cmd.append('--overwrite')
    return run_json(cmd, timeout=300)

def pd_one_pptx_exact_text_patch(input_path: str, replacements: list[list[str]], action: str='inspect', output_path: Optional[str]=None, source_sha256: Optional[str]=None, overwrite: bool=False) -> str:
    """Inspect or stage 1-8 exact visible-text replacements in a separate local PPTX.

    The source is never overwritten. Each old text must have exactly one visible,
    run-preserving match. Stage output stays local; this tool never sends files.
    """
    action = str(action or 'inspect').strip().lower()
    if action not in {'inspect', 'stage'}:
        raise ValueError('action must be one of: inspect, stage')
    if action == 'stage' and (not output_path):
        raise ValueError('output_path is required for action=stage')
    if not isinstance(replacements, list) or not 1 <= len(replacements) <= 8:
        raise ValueError('replacements must contain 1-8 old/new pairs')
    cmd = [sys.executable, str(SAFE_OPS()), 'pptx-exact-text-patch', '--action', action, '--input', input_path]
    for pair in replacements:
        if not isinstance(pair, list) or len(pair) != 2 or (not all((isinstance(value, str) for value in pair))):
            raise ValueError('each replacement must be a two-string [old_text, new_text] pair')
        cmd += ['--replace', pair[0], pair[1]]
    if output_path:
        cmd += ['--out', output_path]
    if source_sha256:
        cmd += ['--source-sha256', source_sha256]
    if overwrite:
        cmd.append('--overwrite')
    return run_json(cmd, timeout=300)

def pd_one_pptx_from_template(template_path: str, action: str='inspect', mode: str='apply', source_path: Optional[str]=None, output_path: Optional[str]=None, source_sha256: Optional[str]=None, overwrite: bool=False) -> str:
    """Inspect or stage a PPTX cloned from a POTX/PPTX, or apply that template onto a source deck.

    Sources are never overwritten. Stage output stays local; this tool never sends files.
    Same-thread requester-attachment restyles do not need a PDAPP ticket.
    """
    action = str(action or 'inspect').strip().lower()
    mode = str(mode or 'apply').strip().lower()
    if action not in {'inspect', 'stage'}:
        raise ValueError('action must be one of: inspect, stage')
    if mode not in {'apply', 'clone'}:
        raise ValueError('mode must be one of: apply, clone')
    if mode == 'apply' and (not source_path):
        raise ValueError('source_path is required for mode=apply')
    if action == 'stage' and (not output_path):
        raise ValueError('output_path is required for action=stage')
    cmd = [sys.executable, str(SAFE_OPS()), 'pptx-from-template', '--action', action, '--mode', mode, '--template', template_path]
    if source_path:
        cmd += ['--source', source_path]
    if output_path:
        cmd += ['--out', output_path]
    if source_sha256:
        cmd += ['--source-sha256', source_sha256]
    if overwrite:
        cmd.append('--overwrite')
    return run_json(cmd, timeout=300)

def pd_one_office_docprops_inspect(input_path: str) -> str:
    """Inspect allowlisted Office Open XML core/app properties from one approved package."""
    return run_json([sys.executable, str(SAFE_OPS()), 'office-docprops-inspect', '--input', input_path], timeout=30)

def pd_one_office_visual_qa(input_path: str, output_dir: str) -> str:
    """Render a bounded DOCX/PPTX into local visual-QA artifacts without execute_code."""
    return run_json([sys.executable, str(SAFE_OPS()), 'office-visual-qa', '--input', input_path, '--out-dir', output_dir], timeout=360)

def pd_one_office_toolchain_status() -> str:
    """Inspect available office toolchain binaries without execute_code or shell probes."""
    return run_json([sys.executable, str(SAFE_OPS()), 'office-toolchain-status'], timeout=30)

def pd_one_office_deb_contents(package_path: str) -> str:
    """Inspect bounded Office Debian-package contents without execute_code."""
    return run_json([sys.executable, str(SAFE_OPS()), 'office-deb-contents', '--package', package_path], timeout=45)

def pd_one_item_number_workflow_check(component: str='engine') -> str:
    """Compile and run the fixed item-number workflow unit tests for engine, compiler, or runner."""
    component = str(component or 'engine').strip().lower()
    if component not in {'engine', 'compiler', 'runner'}:
        raise ValueError('component must be one of: engine, compiler, runner')
    return run_json([sys.executable, str(SAFE_OPS()), 'item-number-workflow-check', '--component', component], timeout=300)

def pd_one_item_number_windows_excel_qa(confirm: Optional[str]=None) -> str:
    """Plan or run the fixed item-number Windows Excel/COM QA lane; run requires exact confirmation."""
    cmd = [sys.executable, str(SAFE_OPS()), 'item-number-windows-excel-qa']
    if confirm is not None:
        cmd += ['--confirm', confirm]
    return run_json(cmd, timeout=420)

def pd_one_employee_watch(action: str, query: str='', origin_channel_id: str='', origin_root_id: str='', sender_id: str='', watch_id: str='', expires_days: int=14) -> str:
    """Create, list, or cancel an owner-bound production-item watch. Not cron.

    First slice: production_item_on_schedule, one-shot, current Mattermost thread only.
    Resolve the item to one canonical product at create time. Employees cannot
    create Hermes cron jobs. Re-resolves the live sender when session env is set.
    """
    action_value = str(action or '').strip().lower()
    if action_value not in {'create', 'list', 'cancel'}:
        raise ValueError('action must be one of: create, list, cancel')
    cmd = [sys.executable, str(EMPLOYEE_WATCHES()), action_value]
    if action_value == 'create':
        cmd += ['--query', str(query or '').strip(), '--channel-id', str(origin_channel_id or '').strip(), '--root-id', str(origin_root_id or '').strip(), '--expires-days', str(int(expires_days))]
    if sender_id:
        cmd += ['--sender-id', str(sender_id).strip()]
    if action_value == 'cancel':
        cmd += ['--watch-id', str(watch_id or '').strip()]
    return run_json(cmd, timeout=90)

def pd_one_office_convert_to_pdf(input_path: str, output_path: str) -> str:
    """Convert a bounded office artifact to PDF under approved PD One document roots."""
    cmd = [sys.executable, str(SAFE_OPS()), 'office-convert-pdf', '--input', input_path, '--out', output_path]
    return run_json(cmd, timeout=300)

def pd_one_drive_acl_authorize(file_id: str, requester_user_id: str='', username: str='') -> str:
    """Authorize a Mattermost user against live Drive ACLs. Never creates permissions."""
    cmd = [sys.executable, str(SAFE_OPS()), 'drive-acl-authorize', '--file-id', file_id]
    if requester_user_id:
        cmd += ['--requester-user-id', requester_user_id]
    if username:
        cmd += ['--username', username]
    return run_json(cmd, timeout=120)

def pd_one_portal_module_change_authorize(requester_user_id: str, channel_id: str='', module_id: str='', path: str='', change_class: str='in_scope_module_product') -> str:
    """Authorize a Portal module-change request by group membership and department channel. Never prints emails. DM/other channels redirect and do not execute."""
    cmd = [sys.executable, str(SAFE_OPS()), 'portal-module-change-authorize', '--requester-user-id', requester_user_id, '--channel-id', channel_id or '', '--module-id', module_id or '', '--path', path or '', '--change-class', change_class or 'in_scope_module_product']
    return run_json(cmd, timeout=60)

def pd_one_work_manual_change_authorize(requester_user_id: str, channel_id: str='', chat_type: str='', document_key: str='it_manual', document_id: str='', change_class: str='secret_free_content_add') -> str:
    """Authorize an IT work-manual content-add request by it@ group membership and non-DM chat type. Never prints emails. DM requests redirect and do not execute."""
    cmd = [sys.executable, str(SAFE_OPS()), 'work-manual-change-authorize', '--requester-user-id', requester_user_id, '--channel-id', channel_id or '', '--chat-type', chat_type or '', '--document-key', document_key or 'it_manual', '--document-id', document_id or '', '--change-class', change_class or 'secret_free_content_add']
    return run_json(cmd, timeout=60)

def pd_one_typhoon_automation(action: str='preview', fixture: Optional[str]=None, confirm_live_write: Optional[str]=None) -> str:
    """Compile/test, preview, sweep, or run the PD One typhoon readiness automation."""
    if action not in {'check', 'preview', 'sweep', 'live'}:
        raise ValueError('action must be one of: check, preview, sweep, live')
    if action == 'sweep':
        if fixture:
            raise ValueError('sweep action does not accept fixture')
        if confirm_live_write:
            raise ValueError('sweep action does not accept confirm_live_write')
    if action == 'live':
        if confirm_live_write != TYPHOON_AUTOMATION_LIVE_CONFIRMATION:
            raise ValueError(f'live action requires confirm_live_write={TYPHOON_AUTOMATION_LIVE_CONFIRMATION!r}')
    elif confirm_live_write:
        raise ValueError('confirm_live_write is only valid with live action')
    cmd = [sys.executable, str(SAFE_OPS()), 'typhoon-automation', '--action', action]
    if fixture:
        cmd += ['--fixture', fixture]
    if confirm_live_write:
        cmd += ['--confirm-live-write', confirm_live_write]
    timeout = 600 if action == 'check' else 900 if action == 'live' else 300
    return run_json(cmd, timeout=timeout)

def call_function_twin(twin: str, requester_user_id: str, task: str, excerpts: str='') -> str:
    """Consult one internal PD One function twin. Employees never talk to twins. Fail closed without exact Mattermost requester id. Write class none. One twin per question."""
    name = str(twin or '').strip().lower()
    if name.startswith('pd-'):
        name = name[3:]
    if name not in FUNCTION_TWIN_NAMES:
        raise ValueError('unknown twin; pd-marketing is parked and is not a twin')
    requester = str(requester_user_id or '').strip()
    question = str(task or '').strip()
    if not requester or not question:
        return json.dumps({'ok': False, 'error': 'REFUSE_UNAUTHENTICATED_CALL', 'exit_code': 2, 'detail': 'requester_user_id and task are required'}, ensure_ascii=False)
    if not FUNCTION_TWIN_DISPATCHER().is_file():
        raise FileNotFoundError(f'dispatcher missing: {FUNCTION_TWIN_DISPATCHER()}')
    cmd = [sys.executable, str(FUNCTION_TWIN_DISPATCHER()), '--twin', name, '--requester-user-id', requester, '--task', question, '--json', '--timeout', '120']
    excerpts_value = str(excerpts or '')
    if excerpts_value.strip():
        cmd.extend(['--excerpts', excerpts_value])
    return run_json(cmd, timeout=150)

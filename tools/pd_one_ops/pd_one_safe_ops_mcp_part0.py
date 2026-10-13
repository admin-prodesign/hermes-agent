"""MCP server exposing PD One safe operations as typed tools."""
from __future__ import annotations
__all__ = ['_PdReturn', '_PdHandled', '_PdUnset', '_PdUnset', 'SAFE_OPS', 'FUNCTION_TWIN_DISPATCHER', 'FUNCTION_TWIN_NAMES', 'EMPLOYEE_WATCHES', 'MEDIA_OPS', 'GOOGLE_DOCS_DOCUMENT_OPS', 'GOOGLE_GROUP_OWNER_OPS', 'TYPHOON_AUTOMATION_LIVE_CONFIRMATION', 'ADMIN_APPROVAL_DECISION_LIVE_CONFIRMATION', 'PYTHON_DOCX_REPAIR_TICKET_ID', 'PYTHON_DOCX_REPAIR_CONFIRMATION', 'OLLAMA_EMBEDDING_UNIT', 'OLLAMA_EMBEDDING_PORT', 'OLLAMA_EMBEDDING_CONTAINER', 'OLLAMA_EMBEDDING_PEER_CONTAINER', 'OLLAMA_EMBEDDING_WATCHDOG_UNIT', 'OLLAMA_EMBEDDING_WATCHDOG_MAX_JOURNAL_TAIL_LINES', 'SYSSTAT_SUMMARY_MAX_HOURS', 'AUDIT', 'APPSHEET_RECORD_OPS', 'APPSHEET_SCHEMA_MAP', 'APPSHEET_ENV_FILES', 'APPSHEET_LIVE_CONFIRMATION', 'APPSHEET_BULK_MAX_ROWS', 'APPSHEET_HR_EMPLOYEE_ALLOWED_FIELDS', 'APPSHEET_HR_EMPLOYEE_READBACK_FIELDS', 'APPS_SCRIPT_LIVE_CONFIRMATION', 'APPS_SCRIPT_ALLOWED_PROJECTS', 'GOG_CREDS', 'APPS_SCRIPT_RECEIPTS', 'SCHEDULER_PROJECT', 'SCHEDULER_SCRIPT', 'SCHEDULER_PYTHON', 'WORKER_SCHEDULING_RECEIPTS', 'WORKER_SCHEDULING_GROUPS', 'WORKER_SCHEDULING_LIVE_CONFIRMATION', 'WORKER_SCHEDULING_LEGACY_LIVE_CONFIRMATION', 'WORKER_SCHEDULING_LIVE_CONFIRMATION_REQUIREMENT', 'WORKER_SCHEDULING_SOURCE_CONFIRMATION', 'SOURCE_SPREADSHEET_ID', 'DEST_SPREADSHEET_ID', 'RAW_REQUEST_SHEET', 'MONTHLY_SOURCE_SHEET', 'SCHEDULING_RULES_SHEET', 'SCHEDULING_RULES_VALUES', 'GOG', 'run_json', '_json_result', '_load_google_docs_document_ops_module', '_load_google_group_owner_ops_module', '_utc_stamp', '_validate_worker_scheduling_groups', '_worker_scheduling_command', '_tail_file', '_run_worker_scheduling_command', '_pid_is_running', '_start_worker_scheduling_job', '_poll_worker_scheduling_job', '_approved_existing_worker_path', '_load_shift_scheduler_module', '_resolve_generated_schedule_report', 'worker_scheduling_write_generated_schedule_from_report', '_approved_output_dir', '_gog_cmd', '_run_cmd', '_gog_get', '_gog_notes', '_extract_values', '_column_name', '_canonical_date', '_write_receipt', 'pd_one_capability_registry', 'pd_one_sheets_get_range', 'pd_one_cached_sheet_json_search', 'pd_one_cached_dest_rest_count', 'pd_one_google_drive_parent_chain', 'pd_one_google_drive_search_files', 'pd_one_sheets_batch_update', 'pd_one_bounded_sheet_cell_write', 'pd_one_sheets_append', 'pd_one_sheets_header_update_row', 'pd_one_dangerous_command_audit', 'pd_one_ecrn_approval_pilot_status', 'pd_one_ecrn_approval_pilot_check', 'pd_one_google_group_members', 'pd_one_google_group_owner_enforcement', 'pd_one_google_docs_metadata_inspect', 'pd_one_google_docs_document_ops', 'pd_one_google_group_change_apply', 'pd_one_smb_unc_content_search', 'pd_one_sqlsrv_windows_acl_read', 'pd_one_google_group_change_dry_run', 'pd_one_auth_browser_status', 'pd_one_sysstat_summary', 'pd_one_numeric_summary', 'pd_one_text_metrics', 'pd_one_disk_space_summary', 'pd_one_local_process_listener_inspect', 'pd_one_user_process_snapshot', 'pd_one_python_package_dry_run', 'pd_one_python_media_stack_status', 'pd_one_python_cad_stack_status', 'pd_one_step_geometry_inspect', 'pd_one_step_printability_analyze', 'pd_one_cad_runtime_status', 'pd_one_python_docx_dependency_repair', 'pd_one_timezone_snapshot', 'pd_one_protected_portal_origin_probe', 'pd_one_timestamp_to_epoch', 'pd_one_epoch_milliseconds_to_iso', 'pd_one_sheets_serial_column_convert', 'pd_one_ollama_embedding_triage', 'pd_one_ollama_embedding_watchdog_triage', 'pd_one_mattermost_channel_lookup', 'pd_one_mattermost_channel_post_audit', 'pd_one_admin_alert_source_audit', 'pd_one_mattermost_channel_setup', 'pd_one_admin_approval_request', 'pd_one_admin_approval_list_open', 'pd_one_admin_approval_decide', 'pd_one_approval_ticket_status', 'pd_one_admin_approval_kanban_status', 'pd_one_hermes_result_messages_summary', 'pd_one_json_artifact_inspect', 'pd_one_local_file_search', 'pd_one_mattermost_member_search', 'pd_one_yammer_archive_search', 'pd_one_policy_change_dry_run', 'worker_scheduling_execute', 'worker_scheduling_audit_rest_requests', 'worker_scheduling_correct_raw_request_dates', 'worker_scheduling_source_setup', 'worker_scheduling_sync_source_rollover', 'worker_scheduling_closeout_processed_requests', 'IM_SCHEDULING_GATES', 'IM_SCHEDULING_PROFILE', '_im_scheduling_receipt_path', 'worker_scheduling_review_im_scheduling', 'worker_scheduling', '_load_apps_script_content', '_export_gog_refresh_token', '_google_access_token', '_google_api_json']

class _PdReturn:
    __slots__ = ('value',)

    def __init__(self, value):
        self.value = value

class _PdHandled:
    pass

class _PdUnset:

    def __bool__(self):
        raise UnboundLocalError('pd one local used before assignment')

    def __repr__(self):
        raise UnboundLocalError('pd one local used before assignment')
_PdUnset = _PdUnset()
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

def SAFE_OPS():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/tools/pd_one_safe_ops.py'))

def FUNCTION_TWIN_DISPATCHER():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/tools/call_function_twin.py'))
FUNCTION_TWIN_NAMES = frozenset({'hr', 'finance', 'sales', 'it', 'molding', 'printing', 'moldrepair', 'engineering', 'qa', 'warehouse', 'procurement'})

def EMPLOYEE_WATCHES():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/tools/pd_one_employee_watches.py'))

def MEDIA_OPS():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/tools/pd_one_typed_media_ops.py'))

def GOOGLE_DOCS_DOCUMENT_OPS():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/tools/google_docs_document_ops.py'))

def GOOGLE_GROUP_OWNER_OPS():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/tools/google_group_owner_ops.py'))
TYPHOON_AUTOMATION_LIVE_CONFIRMATION = 'RUN LIVE TYPHOON AUTOMATION'
ADMIN_APPROVAL_DECISION_LIVE_CONFIRMATION = 'RUN LIVE ADMIN APPROVAL DECISION'

def PYTHON_DOCX_REPAIR_TICKET_ID():
    return site_text('PDONE_DOCX_REPAIR_TICKET_ID')

def PYTHON_DOCX_REPAIR_CONFIRMATION():
    return 'RUN LIVE PYTHON DOCX DEPENDENCY REPAIR ' + site_text('PDONE_DOCX_REPAIR_TICKET_ID')
OLLAMA_EMBEDDING_UNIT = 'pd-neo-ollama.service'
OLLAMA_EMBEDDING_PORT = 11434
OLLAMA_EMBEDDING_CONTAINER = 'honcho-pd-neo-api-1'
OLLAMA_EMBEDDING_PEER_CONTAINER = 'honcho-pd-neo-deriver-1'
OLLAMA_EMBEDDING_WATCHDOG_UNIT = 'pd-neo-embedding-endpoint-watchdog.service'
OLLAMA_EMBEDDING_WATCHDOG_MAX_JOURNAL_TAIL_LINES = 4000
SYSSTAT_SUMMARY_MAX_HOURS = 72

def AUDIT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/tools/pd_one_dangerous_command_audit.py'))

def APPSHEET_RECORD_OPS():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/skills/appsheet-copilot/scripts/appsheet_record_ops.py'))

def APPSHEET_SCHEMA_MAP():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/skills/appsheet-copilot/references/prodesign-schema-map.json'))

def APPSHEET_ENV_FILES():
    return {'deployed': Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/projects/AppSheet/keydrop/deployed-app.env')), 'prototype': Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/projects/AppSheet/keydrop/prototype-app.env'))}
APPSHEET_LIVE_CONFIRMATION = 'RUN LIVE APPSHEET RECORD OPS'
APPSHEET_BULK_MAX_ROWS = 25
APPSHEET_HR_EMPLOYEE_ALLOWED_FIELDS = {'Name_ZH', 'Name_EN', 'Cell Phone', 'LINE User ID', 'Appsheet Email', 'Microsoft Account', 'Name_PINYIN', 'Employee ID', 'Company Email', 'Transport Method', 'Moped License Plate', 'Car License Plate'}
APPSHEET_HR_EMPLOYEE_READBACK_FIELDS = ('PersonID', 'Name_ZH', 'Name_EN', 'Cell Phone', 'LINE User ID', 'Appsheet Email', 'Microsoft Account', 'Company Email', 'Employee ID', 'Name_PINYIN', 'Transport Method', 'Moped License Plate', 'Car License Plate')
APPS_SCRIPT_LIVE_CONFIRMATION = 'RUN LIVE APPS SCRIPT PATCH'

def APPS_SCRIPT_ALLOWED_PROJECTS():
    return {'worker_scheduling': {'script_id': site_text('PDONE_APPS_SCRIPT_WORKER_SCHEDULING'), 'account': site_text('PDONE_EMAIL_ADMIN'), 'title': '良器-成型部-排班表 Injection Molding Shift Schedule', 'spreadsheet_id': site_text('PDONE_GDOC_7'), 'system': 'injection_molding_worker_scheduling', 'allowed_actions': ['get_content', 'verify_readback', 'unique_text_patch', 'staged_file_replace']}, 'appsheet_helper': {'script_id': site_text('PDONE_APPS_SCRIPT_APPSHEET_HELPER'), 'account': site_text('PDONE_EMAIL_ADMIN'), 'title': 'AppSheet Helper / GoogleTranslate worker', 'spreadsheet_id': site_text('PDONE_GDOC_8'), 'system': 'appsheet_helper_translation_pushback', 'allowed_actions': ['get_content', 'verify_readback', 'unique_text_patch', 'staged_file_replace']}, 'appsheet_data_mirror': {'script_id': site_text('PDONE_APPS_SCRIPT_APPSHEET_DATA_MIRROR'), 'account': site_text('PDONE_EMAIL_ADMIN'), 'title': 'PD One - AppSheet Data Mirror sync', 'spreadsheet_id': site_text('PDONE_GDOC_9'), 'system': 'pd_one_appsheet_data_mirror', 'allowed_actions': ['get_content', 'verify_readback', 'unique_text_patch', 'staged_file_replace']}, 'finance_forex_notification': {'script_id': site_text('PDONE_APPS_SCRIPT_FINANCE_FOREX'), 'account': site_text('PDONE_EMAIL_ADMIN'), 'title': '良器-財務-匯率自動通知系統 Forex Notification', 'spreadsheet_id': site_text('PDONE_GDOC_10'), 'system': 'finance_forex_notification', 'allowed_actions': ['get_content', 'verify_readback', 'unique_text_patch', 'staged_file_replace']}}

def GOG_CREDS():
    return Path(resolve_configured_path('~/.config/gogcli/credentials-prodesign-admin.json'))

def APPS_SCRIPT_RECEIPTS():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/tmp/apps-script-mcp'))

def SCHEDULER_PROJECT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/projects/automatic-worker-scheduling'))

def SCHEDULER_SCRIPT():
    return SCHEDULER_PROJECT() / 'scripts/shift_scheduler_phase1.py'

def SCHEDULER_PYTHON():
    return SCHEDULER_PROJECT() / '.venv/bin/python'

def WORKER_SCHEDULING_RECEIPTS():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/tmp/worker-scheduling-mcp'))
WORKER_SCHEDULING_GROUPS = {'day', 'night', 'manager_day', 'manager_night'}
WORKER_SCHEDULING_LIVE_CONFIRMATION = True
WORKER_SCHEDULING_LEGACY_LIVE_CONFIRMATION = 'RUN LIVE WORKER SCHEDULING WRITE'
WORKER_SCHEDULING_LIVE_CONFIRMATION_REQUIREMENT = 'confirm_live_write=true after explicit, approved-user confirmation scoped to the verified primary-month schedule writeback'
WORKER_SCHEDULING_SOURCE_CONFIRMATION = 'RUN LIVE WORKER SCHEDULING SOURCE WRITE'

def SOURCE_SPREADSHEET_ID():
    return site_text('PDONE_SOURCE_SPREADSHEET_ID')

def DEST_SPREADSHEET_ID():
    return site_text('PDONE_GDOC_7')
RAW_REQUEST_SHEET = '原資料'
MONTHLY_SOURCE_SHEET = '申請日期-當月統計'
SCHEDULING_RULES_SHEET = '排班規則 Scheduling Rules'

def SCHEDULING_RULES_VALUES():
    return [['RuleID', 'Active', 'WorkerID', 'Name', 'JobTitle', 'EmploymentStatus', 'BusinessUnit', 'RunGroup', 'EffectiveFrom', 'WeekendBiasEnabled', 'PreferenceMode', 'RequestProtection', 'Weight', 'ExcludedDates', 'Notes'], ['manager_day_weekend_bias_W12', 'TRUE', 'W12', site_text('PDONE_SCHEDULING_RULE_W12_NAME'), '課長', 'Employed', '成型一課', 'manager_day', '2026-08', 'TRUE', 'Prefer', 'Conservative', '1500', '', 'Approved bounded weekend coverage preference; requests and explicit constraints remain protected.']]

def GOG():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/home/.local/bin/gog'))

def run_json(args: list[str], timeout: int=120) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, shell=False, timeout=timeout)
    if proc.returncode != 0:
        return json.dumps({'status': 'error', 'returncode': proc.returncode, 'stderr': proc.stderr[-2000:], 'stdout': proc.stdout[-2000:]}, ensure_ascii=False)
    out = proc.stdout.strip() or '{}'
    try:
        json.loads(out)
        return out
    except json.JSONDecodeError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return json.dumps({'status': 'ok', 'raw_stdout': out}, ensure_ascii=False)

def _json_result(payload: dict) -> str:
    from tools.pd_one_ops.hr_guard import guard_hr_payload
    payload = guard_hr_payload(payload)
    return json.dumps(payload, ensure_ascii=False, indent=2)

def _load_google_docs_document_ops_module() -> Any:
    """Load the bounded Google Docs operations implementation without shell execution."""
    if not GOOGLE_DOCS_DOCUMENT_OPS().is_file():
        raise FileNotFoundError(str(GOOGLE_DOCS_DOCUMENT_OPS()))
    spec = importlib.util.spec_from_file_location('pdone_google_docs_document_ops', GOOGLE_DOCS_DOCUMENT_OPS())
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load {GOOGLE_DOCS_DOCUMENT_OPS()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def _load_google_group_owner_ops_module() -> Any:
    """Load the fixed-domain, fixed-owner Google Groups implementation."""
    if not GOOGLE_GROUP_OWNER_OPS().is_file():
        raise FileNotFoundError(str(GOOGLE_GROUP_OWNER_OPS()))
    spec = importlib.util.spec_from_file_location('pdone_google_group_owner_ops', GOOGLE_GROUP_OWNER_OPS())
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load {GOOGLE_GROUP_OWNER_OPS()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

def _validate_worker_scheduling_groups(solve_groups: Optional[list[str]]) -> list[str]:
    groups = solve_groups or []
    if not isinstance(groups, list):
        raise ValueError('solve_groups must be a list of run-group names')
    invalid = sorted(set(groups) - WORKER_SCHEDULING_GROUPS)
    if invalid:
        raise ValueError(f'Invalid solve_groups: {invalid}; allowed={sorted(WORKER_SCHEDULING_GROUPS)}')
    return groups

def _worker_scheduling_command(*, action: str, solve_groups: Optional[list[str]], solver_max_time_seconds: Optional[int], solver_no_improvement_seconds: Optional[int], following_month_required_rest_days_count: Optional[int], stdout_summary_only: bool, output_dir: Optional[str], confirm_live_write: Optional[str]) -> tuple[list[str], Path, bool]:
    if action not in {'preflight', 'solve_preview', 'write_generated_schedule'}:
        raise ValueError('action must be one of: preflight, solve_preview, write_generated_schedule')
    groups = _validate_worker_scheduling_groups(solve_groups)
    live_write = action == 'write_generated_schedule'
    if live_write and confirm_live_write not in {WORKER_SCHEDULING_LIVE_CONFIRMATION, WORKER_SCHEDULING_LEGACY_LIVE_CONFIRMATION}:
        raise ValueError('write_generated_schedule requires confirm_live_write=true after explicit, scoped approved-user authorization')
    if solver_max_time_seconds is not None and (not 1 <= int(solver_max_time_seconds) <= 1800):
        raise ValueError('solver_max_time_seconds must be between 1 and 1800')
    if solver_no_improvement_seconds is not None and (not 0 <= int(solver_no_improvement_seconds) <= 1800):
        raise ValueError('solver_no_improvement_seconds must be between 0 and 1800')
    if action in {'solve_preview', 'write_generated_schedule'}:
        if following_month_required_rest_days_count is None:
            raise ValueError('following_month_required_rest_days_count is required for every solve')
        if not 0 <= int(following_month_required_rest_days_count) <= 31:
            raise ValueError('following_month_required_rest_days_count must be between 0 and 31')
    if output_dir:
        out_dir = Path(output_dir)
        allowed_roots = [Path(resolve_configured_path('~/.hermes/profiles/pdone/tmp')), SCHEDULER_PROJECT() / 'tmp', Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/tmp'))]
        resolved = out_dir.resolve()
        if not any((str(resolved).startswith(str(root.resolve()) + os.sep) or resolved == root.resolve() for root in allowed_roots)):
            raise ValueError('output_dir must be under the approved PD One tmp/scheduler receipt roots')
    else:
        WORKER_SCHEDULING_RECEIPTS().mkdir(parents=True, exist_ok=True)
        suffix = action if not groups else f'{action}_{'_'.join(groups)}'
        out_dir = WORKER_SCHEDULING_RECEIPTS() / f'{_utc_stamp()}_{suffix}'
    cmd = [str(SCHEDULER_PYTHON()), str(SCHEDULER_SCRIPT()), '--gog-account', site_text('PDONE_EMAIL_ADMIN'), '--output-dir', str(out_dir)]
    if stdout_summary_only:
        cmd.append('--stdout-summary-only')
    if action in {'solve_preview', 'write_generated_schedule'}:
        cmd.append('--solve')
    if live_write:
        cmd += ['--write-generated-schedule', '--yes']
    for group in groups:
        cmd += ['--solve-group', group]
    if solver_max_time_seconds is not None:
        cmd += ['--solver-max-time-seconds', str(int(solver_max_time_seconds))]
    if solver_no_improvement_seconds is not None:
        cmd += ['--solver-no-improvement-seconds', str(int(solver_no_improvement_seconds))]
    if following_month_required_rest_days_count is not None:
        cmd += ['--following-month-required-rest-days-count', str(int(following_month_required_rest_days_count))]
    return (cmd, out_dir, live_write)

def _tail_file(path: Path, limit: int=4000) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')[-limit:]
    except FileNotFoundError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return ''
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return f'<failed to read {path}: {exc}>'

def _run_worker_scheduling_command(cmd: list[str], out_dir: Path, timeout_seconds: int) -> str:
    if not SCHEDULER_PYTHON().exists() or not SCHEDULER_SCRIPT().exists():
        return _json_result({'status': 'error', 'error': 'scheduler_runtime_missing', 'scheduler_python_exists': SCHEDULER_PYTHON().exists(), 'scheduler_script_exists': SCHEDULER_SCRIPT().exists()})
    min_timeout_seconds = int(site_text('WORKER_SCHEDULING_MIN_TIMEOUT_SECONDS'))
    timeout_seconds = max(min_timeout_seconds, min(int(timeout_seconds), 2400))
    env = {**os.environ, 'HOME': resolve_configured_path('~')}
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / 'summary.json'
    stdout_path = out_dir / 'mcp-scheduler-stdout.log'
    stderr_path = out_dir / 'mcp-scheduler-stderr.log'
    with stdout_path.open('w', encoding='utf-8') as stdout_f, stderr_path.open('w', encoding='utf-8') as stderr_f:
        proc = subprocess.Popen(cmd, cwd=SCHEDULER_PROJECT(), env=env, text=True, stdout=stdout_f, stderr=stderr_f, shell=False, start_new_session=True)
        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                logging.getLogger('pd_one_ops').exception('pd one command failed')
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logging.getLogger('pd_one_ops').exception('pd one command failed')
            summary = None
            if summary_path.exists():
                try:
                    summary = json.loads(summary_path.read_text(encoding='utf-8'))
                except Exception as parse_exc:
                    logging.getLogger('pd_one_ops').exception('pd one command failed')
                    summary = {'parse_error': str(parse_exc)}
            receipt = {'status': 'error', 'error': 'scheduler_subprocess_timeout', 'timeout_seconds': timeout_seconds, 'output_dir': str(out_dir), 'summary_path': str(summary_path) if summary_path.exists() else None, 'summary': summary, 'stdout_path': str(stdout_path), 'stderr_path': str(stderr_path), 'stdout_tail': _tail_file(stdout_path), 'stderr_tail': _tail_file(stderr_path), 'command': cmd, 'process_group_killed': True}
            _write_receipt(out_dir, 'mcp-scheduler-subprocess-timeout-receipt.json', receipt)
            return _json_result(receipt)
    summary = None
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding='utf-8'))
        except Exception as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            summary = {'parse_error': str(exc)}
    return _json_result({'status': 'ok' if proc.returncode == 0 else 'error', 'returncode': proc.returncode, 'output_dir': str(out_dir), 'summary_path': str(summary_path) if summary_path.exists() else None, 'summary': summary, 'stdout_path': str(stdout_path), 'stderr_path': str(stderr_path), 'stdout_tail': _tail_file(stdout_path), 'stderr_tail': _tail_file(stderr_path), 'command': cmd})

def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return False
    except PermissionError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return True

def _start_worker_scheduling_job(cmd: list[str], out_dir: Path, timeout_seconds: int) -> str:
    if not SCHEDULER_PYTHON().exists() or not SCHEDULER_SCRIPT().exists():
        return _json_result({'status': 'error', 'error': 'scheduler_runtime_missing', 'scheduler_python_exists': SCHEDULER_PYTHON().exists(), 'scheduler_script_exists': SCHEDULER_SCRIPT().exists()})
    out_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = out_dir / 'mcp-scheduler-stdout.log'
    stderr_path = out_dir / 'mcp-scheduler-stderr.log'
    job_path = out_dir / 'mcp-scheduler-job.json'
    env = {**os.environ, 'HOME': resolve_configured_path('~')}
    stdout_f = stdout_path.open('w', encoding='utf-8')
    stderr_f = stderr_path.open('w', encoding='utf-8')
    try:
        proc = subprocess.Popen(cmd, cwd=SCHEDULER_PROJECT(), env=env, text=True, stdout=stdout_f, stderr=stderr_f, shell=False, start_new_session=True)
    finally:
        stdout_f.close()
        stderr_f.close()
    payload = {'status': 'running', 'mode': 'background_job', 'pid': proc.pid, 'output_dir': str(out_dir), 'job_path': str(job_path), 'summary_path': str(out_dir / 'summary.json'), 'stdout_path': str(stdout_path), 'stderr_path': str(stderr_path), 'command': cmd, 'timeout_seconds': int(timeout_seconds), 'next_action': 'poll_solve_preview', 'next_payload': {'output_dir': str(out_dir)}, 'safety': {'live_write_requested': False, 'shell_used': False}}
    _write_receipt(out_dir, 'mcp-scheduler-job.json', payload)
    return _json_result(payload)

def _poll_worker_scheduling_job(output_dir: str, wait_seconds: int=0) -> str:
    out_dir = _approved_existing_worker_path(output_dir)
    wait_seconds = max(0, min(int(wait_seconds), 30))
    job_path = out_dir / 'mcp-scheduler-job.json'
    summary_path = out_dir / 'summary.json'
    stdout_path = out_dir / 'mcp-scheduler-stdout.log'
    stderr_path = out_dir / 'mcp-scheduler-stderr.log'
    job = {}
    if job_path.exists():
        try:
            job = json.loads(job_path.read_text(encoding='utf-8'))
        except Exception as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            job = {'parse_error': str(exc)}
    pid = int(job.get('pid') or 0) if isinstance(job, dict) else 0
    deadline = time.time() + wait_seconds
    while wait_seconds and time.time() < deadline:
        if summary_path.exists() or (pid and (not _pid_is_running(pid))):
            break
        time.sleep(1)
    summary = None
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding='utf-8'))
        except Exception as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            summary = {'parse_error': str(exc)}
    running = bool(pid and _pid_is_running(pid))
    status = 'running' if running and summary is None else 'ok' if summary is not None else 'error'
    payload = {'status': status, 'mode': 'background_job_poll', 'pid': pid or None, 'output_dir': str(out_dir), 'summary_path': str(summary_path) if summary_path.exists() else None, 'summary': summary, 'stdout_path': str(stdout_path), 'stderr_path': str(stderr_path), 'stdout_tail': _tail_file(stdout_path), 'stderr_tail': _tail_file(stderr_path), 'next_action': 'poll_solve_preview' if status == 'running' else None, 'next_payload': {'output_dir': str(out_dir), 'wait_seconds': 30} if status == 'running' else None, 'job': job}
    _write_receipt(out_dir, 'mcp-scheduler-job-poll-receipt.json', payload)
    return _json_result(payload)

def _approved_existing_worker_path(path_text: str, *, required_name: str | None=None) -> Path:
    if not path_text:
        raise ValueError('path is required')
    path = Path(path_text).expanduser().resolve()
    allowed_roots = [Path(resolve_configured_path('~/.hermes/profiles/pdone/tmp')), SCHEDULER_PROJECT() / 'tmp', Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/tmp'))]
    if not any((str(path).startswith(str(root.resolve()) + os.sep) or path == root.resolve() for root in allowed_roots)):
        raise ValueError('path must be under an approved PD One tmp/scheduler receipt root')
    if required_name and path.name != required_name:
        raise ValueError(f'path must point to {required_name}')
    if not path.exists():
        raise FileNotFoundError(str(path))
    return path

def _load_shift_scheduler_module() -> Any:
    if not SCHEDULER_SCRIPT().exists():
        raise FileNotFoundError(str(SCHEDULER_SCRIPT()))
    scripts_dir = str(SCHEDULER_SCRIPT().parent)
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)
    spec = importlib.util.spec_from_file_location('pdone_shift_scheduler_phase1', SCHEDULER_SCRIPT())
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load scheduler script: {SCHEDULER_SCRIPT()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def _resolve_generated_schedule_report(payload: dict[str, Any], output_dir: Optional[str]) -> Path:
    explicit = payload.get('generated_schedule_report_path') or payload.get('report_path')
    if explicit:
        return _approved_existing_worker_path(str(explicit), required_name='generated-schedule-report.json')
    out = payload.get('source_output_dir') or payload.get('output_dir') or output_dir
    if not out:
        raise ValueError('generated_schedule_report_path or source_output_dir/output_dir is required')
    out_path = _approved_existing_worker_path(str(out))
    if not out_path.is_dir():
        raise ValueError('source_output_dir/output_dir must be a directory when report_path is omitted')
    return _approved_existing_worker_path(str(out_path / 'generated-schedule-report.json'), required_name='generated-schedule-report.json')

def worker_scheduling_write_generated_schedule_from_report(report_path: str, run_groups: Optional[list[str]]=None, dry_run: bool=True, output_dir: Optional[str]=None, confirm_live_write: Optional[str]=None, max_format_batches_per_call: int=25, max_value_batches_per_call: int=5) -> str:
    eligible_runs = _PdUnset
    generated_schedule_result = _PdUnset
    out_dir = _PdUnset
    plan = _PdUnset
    receipt = _PdUnset
    report = _PdUnset
    run = _PdUnset

    def _pd_phase_1():
        nonlocal eligible_runs, generated_schedule_result, max_format_batches_per_call, max_value_batches_per_call, out_dir, plan, receipt, report
        'Write an already-solved generated schedule report in resumable chunks; never runs OR-Tools.'
        try:
            report = _approved_existing_worker_path(report_path, required_name='generated-schedule-report.json')
            generated_schedule_result = json.loads(report.read_text(encoding='utf-8'))
            groups = _validate_worker_scheduling_groups(run_groups)
            live = not dry_run
            if live and confirm_live_write not in {WORKER_SCHEDULING_LIVE_CONFIRMATION, WORKER_SCHEDULING_LEGACY_LIVE_CONFIRMATION}:
                raise ValueError('live generated-schedule writes require confirm_live_write=true after explicit, scoped approved-user authorization')
            out_dir = _approved_output_dir(output_dir, 'write_generated_schedule_from_report')
            max_format_batches_per_call = max(1, min(int(max_format_batches_per_call or 25), 75))
            max_value_batches_per_call = max(1, min(int(max_value_batches_per_call or 5), 25))
        except Exception as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            return _PdReturn(_json_result({'status': 'error', 'error': 'invalid_request', 'detail': str(exc)}))
        runs = generated_schedule_result.get('runs') or []
        selected_runs = [run for run in runs if not groups or run.get('run_group') in groups]
        eligible_runs = [run for run in selected_runs if run.get('generated_schedule', {}).get('solver', {}).get('status') in {'OPTIMAL', 'FEASIBLE'}]
        plan = {'status': 'ok', 'dry_run': not live, 'source_report_path': str(report), 'selected_run_groups': [run.get('run_group') for run in selected_runs], 'eligible_run_groups': [run.get('run_group') for run in eligible_runs], 'ineligible_runs': [{'run_group': run.get('run_group'), 'status': run.get('status'), 'solver_status': run.get('generated_schedule', {}).get('solver', {}).get('status') if run.get('generated_schedule') else None} for run in selected_runs if run not in eligible_runs], 'candidate_schedule_cell_updates': sum((int(run.get('generated_schedule', {}).get('summary', {}).get('candidate_schedule_cell_updates') or 0) for run in eligible_runs)), 'safety': {'does_not_run_solver': True, 'live_write_requested': live, 'live_write_confirmation_required': WORKER_SCHEDULING_LIVE_CONFIRMATION_REQUIREMENT, 'shell_used': False, 'resumable_chunks': True}}
        _write_receipt(out_dir, 'mcp-write-generated-schedule-from-report-plan.json', plan)
        if not live:
            return _PdReturn(_json_result({**plan, 'output_dir': str(out_dir), 'max_format_batches_per_call': max_format_batches_per_call}))
        if not eligible_runs:
            receipt = {**plan, 'status': 'error', 'error': 'no_feasible_or_optimal_runs_to_write', 'output_dir': str(out_dir)}
            _write_receipt(out_dir, 'mcp-write-generated-schedule-from-report-receipt.json', receipt)
            return _PdReturn(_json_result(receipt))
        if len(eligible_runs) != 1:
            receipt = {**plan, 'status': 'error', 'error': 'one_group_per_write_call_required', 'detail': 'Pass one solve/run group per write_from_report call so writes can resume safely.', 'output_dir': str(out_dir)}
            _write_receipt(out_dir, 'mcp-write-generated-schedule-from-report-receipt.json', receipt)
            return _PdReturn(_json_result(receipt))

    def _pd_phase_2():
        nonlocal receipt, run
        try:
            module = _load_shift_scheduler_module()
            tool = module.ShiftSchedulerPhase1(gog_account=site_text('PDONE_EMAIL_ADMIN'))
            run = eligible_runs[0]
            generated = run['generated_schedule']
            state_path = out_dir / 'generated-schedule-write-state.json'

            def build_actions() -> list[dict[str, Any]]:
                actions: list[dict[str, Any]] = []
                for record in generated.get('plan_records', []):
                    for update in record.get('planned_updates', []):
                        if not update.get('a1'):
                            continue
                        actions.append({'source_row_number': record['source_row_number'], 'source_name': record['source_name'], 'target_tab': record['target_tab'], 'matched_row_number': record['matched_row_number'], 'kind': update['kind'], 'day': update.get('day'), 'a1': update['a1'], 'current_value': update.get('current_value', ''), 'intended_value': update.get('intended_value', ''), 'background_kind': update.get('background_kind', 'clear'), 'background_format': update.get('background_format') or module.SCHEDULER_BG_CLEAR})
                return actions
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding='utf-8'))
            else:
                actions = build_actions()
                indexed_actions = [{**action, '_action_index': i, '_value_changed': str(action['current_value']).strip() != str(action['intended_value']).strip()} for i, action in enumerate(actions)]
                changed_actions = [action for action in actions if str(action['current_value']).strip() != str(action['intended_value']).strip()]
                state = {'source_report_path': str(report), 'run_group': generated.get('run_group'), 'run_group_label': module.RUN_GROUP_LABELS.get(generated.get('run_group'), generated.get('run_group')), 'actions': actions, 'value_batches': module.build_generated_schedule_value_batches(indexed_actions), 'format_batches': module.build_generated_schedule_format_batches(changed_actions), 'value_results_by_index': {}, 'format_batch_results': [], 'values_complete': False, 'next_format_batch_index': 0, 'next_value_batch_index': 0, 'created_at': datetime.now().isoformat(timespec='seconds')}
                _write_receipt(out_dir, state_path.name, state)
            if not state.get('values_complete'):
                value_results_by_index = {int(k): v for k, v in (state.get('value_results_by_index') or {}).items()}
                value_batches = state.get('value_batches') or []
                value_start = int(state.get('next_value_batch_index') or 0)
                value_end = min(value_start + max_value_batches_per_call, len(value_batches))
                for idx in range(value_start, value_end):
                    batch = value_batches[idx]
                    target_range = f'{module.quote_sheet_title(batch['target_tab'])}!{batch['a1_range']}'
                    attempts = 0
                    while True:
                        attempts += 1
                        try:
                            value_response = None
                            if batch['has_changes']:
                                value_response = tool.gog.sheets_update(module.DEST_SPREADSHEET_ID, target_range, [batch['values']])
                            for action in batch['actions']:
                                status = 'written' if action['_value_changed'] else 'unchanged'
                                value_results_by_index[int(action['_action_index'])] = {**{k: v for k, v in action.items() if not k.startswith('_')}, 'status': status, 'response': {'value_update': value_response, 'value_batch': {'a1_range': batch['a1_range'], 'cell_count': batch['cell_count'], 'changed_cell_count': batch['changed_cell_count']}}, 'attempts': attempts}
                            break
                        except Exception as exc:
                            if module.is_google_write_rate_limit_error(exc) and attempts < module.GENERATED_WRITE_MAX_RETRIES:
                                time.sleep(module.GENERATED_WRITE_RETRY_BASE_SECONDS * attempts)
                                continue
                            for action in batch['actions']:
                                value_results_by_index[int(action['_action_index'])] = {**{k: v for k, v in action.items() if not k.startswith('_')}, 'status': 'failed', 'error': str(exc), 'attempts': attempts}
                            state['value_results_by_index'] = {str(k): v for k, v in value_results_by_index.items()}
                            state['next_value_batch_index'] = idx + 1
                            _write_receipt(out_dir, state_path.name, state)
                            raise
                    state['next_value_batch_index'] = idx + 1
                    state['value_results_by_index'] = {str(k): v for k, v in value_results_by_index.items()}
                    _write_receipt(out_dir, state_path.name, state)
                    time.sleep(module.GENERATED_WRITE_THROTTLE_SECONDS)
                if int(state.get('next_value_batch_index') or 0) < len(value_batches):
                    remaining_values = len(value_batches) - int(state.get('next_value_batch_index') or 0)
                    receipt = {**plan, 'status': 'partial', 'phase': 'value_batches', 'output_dir': str(out_dir), 'state_path': str(state_path), 'values_complete': False, 'value_batches_total': len(value_batches), 'value_batches_completed': int(state.get('next_value_batch_index') or 0), 'value_batches_remaining': remaining_values, 'format_batches_total': len(state.get('format_batches') or []), 'format_batches_completed': int(state.get('next_format_batch_index') or 0), 'next_payload': {'generated_schedule_report_path': str(report), 'run_groups': [generated.get('run_group')], 'output_dir': str(out_dir), 'max_value_batches_per_call': max_value_batches_per_call, 'max_format_batches_per_call': max_format_batches_per_call}}
                    _write_receipt(out_dir, 'mcp-write-generated-schedule-from-report-receipt.json', receipt)
                    return _PdReturn(_json_result(receipt))
                state['value_results_by_index'] = {str(k): v for k, v in value_results_by_index.items()}
                state['values_complete'] = True
                _write_receipt(out_dir, state_path.name, state)
            start = int(state.get('next_format_batch_index') or 0)
            end = min(start + max_format_batches_per_call, len(state.get('format_batches') or []))
            format_results = list(state.get('format_batch_results') or [])
            for idx in range(start, end):
                batch = state['format_batches'][idx]
                target_range = f'{module.quote_sheet_title(batch['target_tab'])}!{batch['a1_range']}'
                attempts = 0
                while True:
                    attempts += 1
                    try:
                        response = tool.gog.sheets_format(module.DEST_SPREADSHEET_ID, target_range, batch.get('background_format') or module.SCHEDULER_BG_CLEAR, module.SCHEDULER_BG_FIELD_MASK)
                        format_results.append({**batch, 'status': 'formatted', 'response': response, 'attempts': attempts})
                        break
                    except Exception as exc:
                        logging.getLogger('pd_one_ops').exception('pd one command failed')
                        if module.is_google_write_rate_limit_error(exc) and attempts < module.GENERATED_WRITE_MAX_RETRIES:
                            time.sleep(module.GENERATED_WRITE_RETRY_BASE_SECONDS * attempts)
                            continue
                        format_results.append({**batch, 'status': 'failed', 'error': str(exc), 'attempts': attempts})
                        break
                state['next_format_batch_index'] = idx + 1
                state['format_batch_results'] = format_results
                _write_receipt(out_dir, state_path.name, state)
                time.sleep(module.GENERATED_WRITE_THROTTLE_SECONDS)
            remaining = len(state.get('format_batches') or []) - int(state.get('next_format_batch_index') or 0)
            if remaining > 0:
                receipt = {**plan, 'status': 'partial', 'output_dir': str(out_dir), 'state_path': str(state_path), 'values_complete': bool(state.get('values_complete')), 'format_batches_total': len(state.get('format_batches') or []), 'format_batches_completed': int(state.get('next_format_batch_index') or 0), 'format_batches_remaining': remaining, 'value_batches_total': len(state.get('value_batches') or []), 'value_batches_completed': int(state.get('next_value_batch_index') or 0), 'next_payload': {'generated_schedule_report_path': str(report), 'run_groups': [generated.get('run_group')], 'output_dir': str(out_dir), 'max_value_batches_per_call': max_value_batches_per_call, 'max_format_batches_per_call': max_format_batches_per_call}}
                _write_receipt(out_dir, 'mcp-write-generated-schedule-from-report-receipt.json', receipt)
                return _PdReturn(_json_result(receipt))
            value_results = [state['value_results_by_index'][str(i)] for i in range(len(state.get('actions') or []))]
            format_failures = sum((1 for result in state.get('format_batch_results') or [] if result.get('status') == 'failed'))
            value_failures = sum((1 for result in value_results if result.get('status') == 'failed'))
            touched_rows = {(result.get('target_tab'), result.get('matched_row_number')) for result in value_results if result.get('status') == 'written'}
            write_result = {'generated_at': datetime.now().isoformat(timespec='seconds'), 'run_group': generated.get('run_group'), 'run_group_label': module.RUN_GROUP_LABELS.get(generated.get('run_group'), generated.get('run_group')), 'mode': 'generated_schedule_write_complete' if not (value_failures or format_failures) else 'generated_schedule_write_partial_with_failures', 'summary': {'candidate_write_action_count': len(value_results), 'value_write_batch_count': len(state.get('value_batches') or []), 'format_write_batch_count': len(state.get('format_batches') or []), 'cells_written': sum((1 for result in value_results if result.get('status') == 'written')), 'cells_unchanged': sum((1 for result in value_results if result.get('status') == 'unchanged')), 'rows_written': len(touched_rows), 'failed_updates': value_failures + format_failures}, 'actions': value_results, 'format_batches': state.get('format_batch_results') or []}
            write_runs = [{'run_group': run.get('run_group'), 'run_group_label': run.get('run_group_label'), 'status': 'written' if not write_result['summary']['failed_updates'] else 'write_failed', 'write': write_result}]
            generated_schedule_write_result = {'generated_at': datetime.now().isoformat(timespec='seconds'), 'mode': 'split_generated_schedule_write_from_existing_report_resumable', 'source_report_path': str(report), 'summary': {'groups_written': sum((1 for item in write_runs if item.get('status') == 'written')), 'groups_with_write_failures': sum((1 for item in write_runs if item.get('status') == 'write_failed')), 'groups_skipped': 0}, 'runs': write_runs}
            _write_receipt(out_dir, 'generated-schedule-write-report.json', generated_schedule_write_result)
            verification = module.verify_generated_schedule_write_report(tool, {**generated_schedule_result, 'runs': [run]}, generated_schedule_write_result, dest_spreadsheet_id=module.DEST_SPREADSHEET_ID)
            _write_receipt(out_dir, 'generated-schedule-write-verification-report.json', verification)
            receipt = {'status': 'ok' if not generated_schedule_write_result['summary']['groups_with_write_failures'] and (not verification.get('summary', {}).get('mismatched_actions', 0)) else 'error', 'dry_run': False, 'output_dir': str(out_dir), 'plan': plan, 'generated_schedule_write': generated_schedule_write_result, 'verification': verification, 'state_path': str(state_path), 'safety': plan['safety']}
        except Exception as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            receipt = {**plan, 'status': 'error', 'error': 'write_from_report_failed', 'detail': str(exc), 'output_dir': str(out_dir)}
        _write_receipt(out_dir, 'mcp-write-generated-schedule-from-report-receipt.json', receipt)
        return _PdReturn(_json_result(receipt))
    _pd_result = _pd_phase_1()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
    _pd_result = _pd_phase_2()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value

def _approved_output_dir(output_dir: Optional[str], suffix: str) -> Path:
    if output_dir:
        out_dir = Path(output_dir)
        allowed_roots = [Path(resolve_configured_path('~/.hermes/profiles/pdone/tmp')), SCHEDULER_PROJECT() / 'tmp', Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/tmp'))]
        resolved = out_dir.resolve()
        if not any((str(resolved).startswith(str(root.resolve()) + os.sep) or resolved == root.resolve() for root in allowed_roots)):
            raise ValueError('output_dir must be under the approved PD One tmp/scheduler receipt roots')
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir
    WORKER_SCHEDULING_RECEIPTS().mkdir(parents=True, exist_ok=True)
    out_dir = WORKER_SCHEDULING_RECEIPTS() / f'{_utc_stamp()}_{suffix}'
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir

def _gog_cmd(*parts: str, account: str=None, json_mode: bool=True, dry_run: bool=False) -> list[str]:
    if account is None:
        account = site_text('PDONE_EMAIL_ADMIN')
    cmd = [str(GOG() if GOG().exists() else 'gog')]
    if json_mode:
        cmd.append('-j')
    if dry_run:
        cmd.append('--dry-run')
    cmd += ['--account', account, '--no-input']
    cmd += list(parts)
    return cmd

def _run_cmd(args: list[str], timeout: int=120) -> dict[str, Any]:
    env = {**os.environ, 'HOME': resolve_configured_path('~')}
    try:
        proc = subprocess.run(args, env=env, text=True, capture_output=True, shell=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'status': 'error', 'error': 'timeout', 'timeout_seconds': timeout, 'stdout_tail': (exc.stdout or '')[-2000:], 'stderr_tail': (exc.stderr or '')[-2000:], 'command': args}
    payload: Any = None
    out = proc.stdout.strip()
    if out:
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            payload = {'raw_stdout': out[-4000:]}
    return {'status': 'ok' if proc.returncode == 0 else 'error', 'returncode': proc.returncode, 'payload': payload, 'stdout_tail': proc.stdout[-4000:], 'stderr_tail': proc.stderr[-4000:], 'command': args}

def _gog_get(spreadsheet_id: str, cell_range: str, account: str=None, timeout: int=120) -> dict[str, Any]:
    if account is None:
        account = site_text('PDONE_EMAIL_ADMIN')
    return _run_cmd(_gog_cmd('sheets', 'get', spreadsheet_id, cell_range, account=account), timeout=timeout)

def _gog_notes(spreadsheet_id: str, cell_range: str, account: str=None, timeout: int=120) -> dict[str, Any]:
    if account is None:
        account = site_text('PDONE_EMAIL_ADMIN')
    return _run_cmd(_gog_cmd('sheets', 'notes', spreadsheet_id, cell_range, account=account), timeout=timeout)

def _extract_values(result: dict[str, Any]) -> list[list[Any]]:
    payload = result.get('payload')
    if isinstance(payload, dict):
        values = payload.get('values')
        if isinstance(values, list):
            return values
    return []

def _column_name(index_1_based: int) -> str:
    letters = ''
    n = index_1_based
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters

def _canonical_date(value: Any) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(text, fmt).strftime('%Y-%m-%d')
        except Exception:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
    parts = text.replace('/', '-').split('-')
    if len(parts) == 3 and all((part.isdigit() for part in parts)):
        y, m, d = parts
        if len(y) == 4:
            return f'{int(y):04d}-{int(m):02d}-{int(d):02d}'
    return text

def _write_receipt(out_dir: Path, name: str, payload: dict[str, Any]) -> str:
    path = out_dir / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(path)

def pd_one_capability_registry() -> str:
    """Return the PD One safe capability registry."""
    return run_json([sys.executable, str(SAFE_OPS()), 'registry-list'])

def pd_one_sheets_get_range(spreadsheet_id: str, range: str, include_values: bool=False, retries: int=3, render: str='') -> str:
    """Read a bounded Google Sheets range through the PD One safe Sheets helper."""
    cmd = [sys.executable, str(SAFE_OPS()), 'sheets-get-range', '--spreadsheet-id', spreadsheet_id, '--range', range, '--retries', str(max(1, min(int(retries), 5)))]
    if include_values:
        cmd.append('--include-values')
    render_value = str(render or '').strip()
    if render_value:
        cmd.extend(['--render', render_value])
    return run_json(cmd, timeout=max(150, 135 * max(1, min(int(retries), 5))))

def pd_one_cached_sheet_json_search(input_path: str, terms: list[str], columns: Optional[list[str]]=None, header_row: int=3, max_matches: int=30) -> str:
    """Search one cached Sheets values JSON dump with literal terms. Admin-only, read-only."""
    cmd = [sys.executable, str(SAFE_OPS()), 'cached-sheet-json-search', '--input', input_path, '--header-row', str(max(1, min(int(header_row), 10000))), '--max-matches', str(max(1, min(int(max_matches), 30)))]
    for term in terms or []:
        cmd += ['--term', str(term)]
    for column in columns or []:
        cmd += ['--column', str(column)]
    return run_json(cmd, timeout=60)

def pd_one_cached_dest_rest_count(input_path: str, terms: list[str], markers: Optional[list[str]]=None, header_row: int=3, name_index: int=0, date_start_index: int=-1, window_start: Optional[int]=None, window_end: Optional[int]=None) -> str:
    """Count dest rest markers for named workers in one cached Sheets dump. Admin-only, read-only."""
    cmd = [sys.executable, str(SAFE_OPS()), 'cached-dest-rest-count', '--input', input_path, '--header-row', str(max(1, min(int(header_row), 10000))), '--name-index', str(max(0, min(int(name_index), 199))), '--date-start-index', str(int(date_start_index))]
    for term in terms or []:
        cmd += ['--term', str(term)]
    for marker in markers or []:
        cmd += ['--marker', str(marker)]
    if window_start is not None:
        cmd += ['--window-start', str(int(window_start))]
    if window_end is not None:
        cmd += ['--window-end', str(int(window_end))]
    return run_json(cmd, timeout=60)

def pd_one_google_drive_parent_chain(file_id: str, stop_at_id: Optional[str]=None, max_hops: int=12) -> str:
    """Read a bounded Google Drive file-parent chain without execute_code.

    Returns only id/name/mimeType/parents, performs at most 12 reads, and never
    changes Drive state or prints credentials.
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'google-drive-parent-chain', '--file-id', file_id, '--max-hops', str(max(1, min(int(max_hops), 12)))]
    if stop_at_id:
        cmd += ['--stop-at-id', stop_at_id]
    return run_json(cmd, timeout=45 * max(1, min(int(max_hops), 12)))

def pd_one_google_drive_search_files(parent_id: str, window_start_utc: str, name_contains: str, mime_type: str='application/vnd.ms-excel', max_files: int=100, timeout: int=90) -> str:
    """Search one bounded Drive folder/date window and filter file metadata read-only."""
    cmd = [sys.executable, str(SAFE_OPS()), 'google-drive-search-files', '--parent-id', parent_id, '--window-start-utc', window_start_utc, '--name-contains', name_contains, '--mime-type', mime_type, '--max-files', str(max(1, min(int(max_files), 100))), '--timeout', str(max(1, min(int(timeout), 120)))]
    return run_json(cmd, timeout=max(150, min(int(timeout), 120) + 30))

def pd_one_sheets_batch_update(spreadsheet_id: str, data_json: str, live: bool=False, confirm_live_write: Optional[str]=None, readback_ranges: Optional[list[str]]=None, receipt: Optional[str]=None, input_mode: str='USER_ENTERED', retries: int=3) -> str:
    """Dry-run or approved live file-backed Sheets batch update via PD One safe helper.

    `data_json` and optional `receipt` must be under approved PD One tmp/artifacts/cache roots.
    Live mode requires confirm_live_write='RUN LIVE SHEETS BATCH UPDATE' and at least one readback range.
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'sheets-batch-update', '--spreadsheet-id', spreadsheet_id, '--data-json', data_json, '--input', input_mode, '--retries', str(max(1, min(int(retries), 5)))]
    for rb in readback_ranges or []:
        cmd += ['--readback', rb]
    if receipt:
        cmd += ['--receipt', receipt]
    if live:
        cmd.append('--live')
    if confirm_live_write:
        cmd += ['--confirm-live-write', confirm_live_write]
    return run_json(cmd, timeout=max(180, 135 * max(1, min(int(retries), 5))))

def pd_one_bounded_sheet_cell_write(bind_json: str, expected_binding: Optional[str]=None, verify_live_read: bool=False, live: bool=False, confirm_live_write: Optional[str]=None, ticket_id: Optional[str]=None, receipt: Optional[str]=None) -> str:
    """Dry-run a SHA-256 bound Google Sheet cell write. Live stays ticket-gated and off by default."""
    cmd = [sys.executable, str(SAFE_OPS()), 'bounded-sheet-cell-write', '--bind-json', bind_json]
    if expected_binding:
        cmd += ['--expected-binding', expected_binding]
    if verify_live_read:
        cmd.append('--verify-live-read')
    if receipt:
        cmd += ['--receipt', receipt]
    if ticket_id:
        cmd += ['--ticket-id', ticket_id]
    if live:
        cmd.append('--live')
    if confirm_live_write:
        cmd += ['--confirm-live-write', confirm_live_write]
    return run_json(cmd, timeout=180)

def pd_one_sheets_append(spreadsheet_id: str, range: str, values_json: str, live: bool=False, confirm_live_write: Optional[str]=None, receipt: Optional[str]=None, chunk_size: int=50, input_mode: str='USER_ENTERED', insert_mode: str='INSERT_ROWS') -> str:
    """Dry-run or approved live chunked Sheets append via PD One safe helper.

    `values_json` and optional `receipt` must be under approved PD One tmp/artifacts/cache roots.
    Live mode requires confirm_live_write='RUN LIVE SHEETS APPEND'.
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'sheets-append', '--spreadsheet-id', spreadsheet_id, '--range', range, '--values-json', values_json, '--chunk-size', str(max(1, min(int(chunk_size), 200))), '--input', input_mode, '--insert', insert_mode]
    if receipt:
        cmd += ['--receipt', receipt]
    if live:
        cmd.append('--live')
    if confirm_live_write:
        cmd += ['--confirm-live-write', confirm_live_write]
    return run_json(cmd, timeout=300)

def pd_one_sheets_header_update_row(spreadsheet_id: str, sheet: str, key_header: str, key_value: str, values_json: str, live: bool=False, confirm_live_write: Optional[str]=None, receipt: Optional[str]=None, max_column: str='ZZ', max_rows: int=5000, input_mode: str='USER_ENTERED', retries: int=3) -> str:
    """Dry-run or approved live header-based Sheets row update via PD One safe helper.

    `values_json` and optional `receipt` must be under approved PD One tmp/artifacts/cache roots.
    Live mode requires confirm_live_write='RUN LIVE SHEETS HEADER UPDATE ROW'.
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'sheets-header-update-row', '--spreadsheet-id', spreadsheet_id, '--sheet', sheet, '--key-header', key_header, '--key-value', key_value, '--values-json', values_json, '--max-column', max_column, '--max-rows', str(max(1, min(int(max_rows), 50000))), '--input', input_mode, '--retries', str(max(1, min(int(retries), 5)))]
    if receipt:
        cmd += ['--receipt', receipt]
    if live:
        cmd.append('--live')
    if confirm_live_write:
        cmd += ['--confirm-live-write', confirm_live_write]
    return run_json(cmd, timeout=max(180, 135 * max(1, min(int(retries), 5))))

def pd_one_dangerous_command_audit(days: int=7, proposals_only: bool=False) -> str:
    """Audit PD One dangerous-command approvals and propose safe wrappers."""
    cmd = [sys.executable, str(AUDIT()), '--days', str(days), '--propose-capabilities' if proposals_only else '--json']
    return run_json(cmd, timeout=180)

def pd_one_ecrn_approval_pilot_status(root_id: Optional[str]=None, max_threads: int=20, max_previews: int=5) -> str:
    """Inspect bounded ECRN approval-pilot state and preview receipts without execute_code."""
    cmd = [sys.executable, str(SAFE_OPS()), 'ecrn-approval-pilot-status', '--max-threads', str(max(1, min(int(max_threads), 50))), '--max-previews', str(max(0, min(int(max_previews), 20)))]
    if root_id:
        cmd += ['--root-id', root_id]
    return run_json(cmd, timeout=120)

def pd_one_ecrn_approval_pilot_check() -> str:
    """Run fixed ECRN approval-pilot tests, lint, compile, and log-integrity checks."""
    return run_json([sys.executable, str(SAFE_OPS()), 'ecrn-approval-pilot-check'], timeout=420)

def pd_one_google_group_members(group: str, filter_email: Optional[str]=None, include_members: bool=False) -> str:
    """Read/filter Google group members without pipe-to-interpreter shell glue."""
    cmd = [sys.executable, str(SAFE_OPS()), 'google-group-members', '--group', group]
    if filter_email:
        cmd += ['--filter-email', filter_email]
    if include_members:
        cmd += ['--include-members']
    return run_json(cmd, timeout=180)

def pd_one_google_group_owner_enforcement(operation: str='ensure_owners', dry_run: bool=True, confirm_live_write: Optional[str]=None, approval_ticket_id: Optional[str]=None) -> str:
    """Run one of two fixed-scope Google Groups administrative continuity operations.

    operation='ensure_owners' ensures the two fixed continuity accounts are Owners
    of every accessible Pro-Design group. Its live mode requires the owner-enforcement
    confirmation phrase plus an unused action-bound approval ticket.

    operation='remove_admin_except_it' removes only ${PDONE_EMAIL_ADMIN} from
    accessible Pro-Design groups other than ${PDONE_EMAIL_IT}. It first verifies
    both continuity accounts are OWNER in every removal target, preserves IT exactly,
    cannot target arbitrary users/groups, and requires the exact live confirmation
    phrase 'RUN LIVE GOOGLE GROUP ADMIN REMOVAL EXCEPT IT'. Dry-run is always default.
    """
    try:
        module = _load_google_group_owner_ops_module()
        normalized_operation = str(operation or 'ensure_owners').strip().lower()
        if normalized_operation == 'ensure_owners':
            result = module.run_owner_enforcement(dry_run=bool(dry_run), confirm_live_write=confirm_live_write, approval_ticket_id=approval_ticket_id)
        elif normalized_operation == 'remove_admin_except_it':
            result = module.run_admin_removal_except_it(dry_run=bool(dry_run), confirm_live_write=confirm_live_write)
        else:
            raise ValueError('operation must be ensure_owners or remove_admin_except_it')
        return _json_result(result)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'capability': 'pd_one_google_group_owner_enforcement', 'detail': str(exc)[:500]})

def pd_one_google_docs_metadata_inspect(doc_id: str, changelog_heading: str='變更日誌 Changelog', limit: int=3, tab_id: Optional[str]=None) -> str:
    """Read Google Docs header metadata, revisionId, and bounded recent changelog entries without execute_code."""
    cmd = [sys.executable, str(SAFE_OPS()), 'google-docs-metadata-inspect', '--doc-id', doc_id, '--changelog-heading', changelog_heading, '--limit', str(max(1, min(int(limit), 20)))]
    if tab_id:
        cmd += ['--tab-id', tab_id]
    return run_json(cmd, timeout=180)

def pd_one_google_docs_document_ops(action: str='list_registered_documents', document_key: str='', requester_user_id: str='', channel_id: str='', chat_type: str='', old_text: str='', new_text: str='', anchor_heading: str='', parent_heading: str='', section_heading: str='', body_paragraphs: Optional[list[str]]=None, heading_style: str='HEADING_2', header_text: str='', header_types: Optional[list[str]]=None, changelog_date: str='', changelog_summary: str='', changelog_heading: str='變更日誌 Changelog', required_strings: Optional[list[str]]=None, required_toc_headings: Optional[list[str]]=None, expected_revision_id: Optional[str]=None, idempotency_key: Optional[str]=None, tab_id: Optional[str]=None, inspect_receipt_path: Optional[str]=None, heading_terms: Optional[list[str]]=None, dry_run: bool=True, confirm_live_write: Optional[str]=None) -> str:
    """Run registry-bounded, typed Google Docs operations for approved manuals.

    Actions: list_registered_documents, inspect, summarize_inspect_receipt,
    verify_readback, unique_text_patch, insert_section_before_heading,
    set_header_text, and append_changelog. Dry-run is the default. Live writes
    require an exact registered requester, a fresh expected_revision_id, a stable
    idempotency_key, and confirm_live_write='RUN LIVE GOOGLE DOCS DOCUMENT OPS'.
    summarize_inspect_receipt is read-only and summarizes headings from one
    existing inspect JSON under tmp/google-docs-document-ops; it does not call
    the Google Docs API.
    IT work-manual secret-free adds may also use an it@ group grant when
    channel_id/chat_type show a non-DM setting.
    For work manuals, verify_readback can enforce bilingual section structure,
    yellow header-date styling, and native TOC membership by supplying
    section_heading and required_toc_headings. Raw Google API request arrays,
    sharing/permissions, Drive moves, document
    deletion, comments, and suggestion resolution are not accepted.
    """
    try:
        module = _load_google_docs_document_ops_module()
        result = module.execute_document_ops(action=action, document_key=document_key, requester_user_id=requester_user_id, channel_id=channel_id, chat_type=chat_type, old_text=old_text, new_text=new_text, anchor_heading=anchor_heading, parent_heading=parent_heading, section_heading=section_heading, body_paragraphs=body_paragraphs, heading_style=heading_style, header_text=header_text, header_types=header_types, changelog_date=changelog_date, changelog_summary=changelog_summary, changelog_heading=changelog_heading, required_strings=required_strings, required_toc_headings=required_toc_headings, expected_revision_id=expected_revision_id, idempotency_key=idempotency_key, tab_id=tab_id, inspect_receipt_path=inspect_receipt_path, heading_terms=heading_terms, dry_run=dry_run, confirm_live_write=confirm_live_write)
        return _json_result(result)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'error': 'google_docs_document_ops_failed', 'detail': str(exc)})

def pd_one_google_group_change_apply(group: str, action: str, member: str, ticket_id: str, role: str='MEMBER', confirm_live_write: str='') -> str:
    """Apply a ticket-bound Google Group member add/remove with readback."""
    cmd = [sys.executable, str(Path(resolve_configured_path('~/.hermes/profiles/pdone/tools/pd_one_google_group_member_ops.py'))), '--group', group, '--action', action, '--member', member, '--role', role, '--live', '--ticket-id', ticket_id, '--confirm-live-write', confirm_live_write]
    return run_json(cmd, timeout=90)

def pd_one_smb_unc_content_search(root: str, terms: list[str], match_mode: str='OR', ticket_id: Optional[str]=None, requester_user_id: Optional[str]=None) -> str:
    """Read-only recursive UNC content search of a named sql-srv root via vm01.

    Authorize with the exact Mattermost requester id (live NTFS Read/Write or the
    Finance AOP standing grant) or an executable ticket. PD One still does not write.
    """
    cmd = [str(Path(resolve_configured_path('~/.hermes/venvs/winrm/bin/python'))), str(Path(resolve_configured_path('~/.hermes/profiles/pdone/tools/pd_one_smb_unc_content_search.py'))), '--root', root, '--match-mode', match_mode]
    for term in terms:
        cmd.extend(['--term', term])
    if ticket_id:
        cmd.extend(['--ticket-id', ticket_id])
    if requester_user_id:
        cmd.extend(['--requester-user-id', requester_user_id])
    return run_json(cmd, timeout=240)

def pd_one_sqlsrv_windows_acl_read(requester_user_id: str, path: str, action: str='authorize', max_items: int=50, max_bytes: int=1000000) -> str:
    """Authorize/list/stat/read a named sql-srv UNC using the requester's live NTFS Read or Write.

    Writes are not implemented. Use the exact Mattermost sender id. Payroll/credentials/HR-evaluation paths fail closed.
    """
    cmd = [str(Path(resolve_configured_path('~/.hermes/profiles/pdone/tools/pd_one_sqlsrv_windows_acl_read.py'))), '--requester-user-id', requester_user_id, '--path', path, '--action', action, '--max', str(max(1, min(int(max_items), 200))), '--max-bytes', str(max(1, min(int(max_bytes), 5000000)))]
    return run_json(cmd, timeout=180)

def pd_one_google_group_change_dry_run(group: str, action: str, member: Optional[str]=None, role: str='MEMBER', name: Optional[str]=None) -> str:
    """Preview Google group create/member add/remove. Does not write."""
    cmd = [sys.executable, str(SAFE_OPS()), 'google-group-change', '--group', group, '--action', action, '--dry-run', '--role', role]
    if member:
        cmd += ['--member', member]
    if name:
        cmd += ['--name', name]
    return run_json(cmd)

def pd_one_auth_browser_status(include_tailscale_url: Optional[str]=None) -> str:
    """Read auth-browser container/port/HTTP status without raw docker/curl/ss commands."""
    cmd = [sys.executable, str(SAFE_OPS()), 'auth-browser-status']
    if include_tailscale_url:
        cmd += ['--include-tailscale-url', include_tailscale_url]
    return run_json(cmd, timeout=30)

def pd_one_sysstat_summary(hours: int=12) -> str:
    """Summarize bounded sysstat CPU/load/PSI/memory samples without execute_code."""
    cmd = [sys.executable, str(SAFE_OPS()), 'sysstat-summary', '--hours', str(max(1, min(int(hours), SYSSTAT_SUMMARY_MAX_HOURS)))]
    return run_json(cmd, timeout=300)

def pd_one_numeric_summary(values: list[float], label: str='samples', units: str='') -> str:
    """Summarize bounded numeric samples without execute_code."""
    label = str(label or 'samples').strip() or 'samples'
    units = str(units or '').strip()
    if len(label) > 80:
        raise ValueError('label must be 80 characters or fewer')
    if len(units) > 32:
        raise ValueError('units must be 32 characters or fewer')
    if len(values) > 1000:
        raise ValueError('values must contain at most 1000 numbers')
    try:
        payload_values = [float(value) for value in values]
    except Exception as exc:
        raise ValueError(f'values must be numeric: {exc}') from exc
    cmd = [sys.executable, str(SAFE_OPS()), 'numeric-summary', '--values-json', json.dumps(payload_values, ensure_ascii=False), '--label', label]
    if units:
        cmd += ['--units', units]
    return run_json(cmd, timeout=30)

def pd_one_text_metrics(text: str) -> str:
    """Count bounded caller-supplied text without execute_code or echoing the text."""
    text = str(text or '')
    if len(text) > 20000:
        raise ValueError('text must contain at most 20000 Unicode code points')
    return run_json([sys.executable, str(SAFE_OPS()), 'text-metrics', '--text', text], timeout=30)

def pd_one_disk_space_summary(low_risk_bytes: int=0, medium_risk_bytes: int=0, additional_bytes: int=0) -> str:
    """Read root disk capacity and project bounded reclaim estimates without cleanup."""
    values = (int(low_risk_bytes), int(medium_risk_bytes), int(additional_bytes))
    if any((value < 0 or value > 50 * 1024 ** 3 for value in values)):
        raise ValueError('each reclaim estimate must be between 0 and 50 GiB')
    return run_json([sys.executable, str(SAFE_OPS()), 'disk-space-summary', '--low-risk-bytes', str(values[0]), '--medium-risk-bytes', str(values[1]), '--additional-bytes', str(values[2])], timeout=20)

def pd_one_local_process_listener_inspect(ports: Optional[list[int]]=None, pids: Optional[list[int]]=None) -> str:
    """Inspect allowlisted local listeners and a bounded PID list without execute_code."""
    selected_ports = list(ports or [])
    selected_pids = list(pids or [])
    if len(selected_ports) > 3:
        raise ValueError('at most 3 ports are allowed')
    if len(selected_pids) > 8:
        raise ValueError('at most 8 pids are allowed')
    cmd = [sys.executable, str(SAFE_OPS()), 'local-process-listener-inspect']
    if selected_ports:
        cmd += ['--ports', *[str(int(port)) for port in selected_ports]]
    if selected_pids:
        cmd += ['--pids', *[str(int(pid)) for pid in selected_pids]]
    return run_json(cmd, timeout=40)

def pd_one_user_process_snapshot() -> str:
    """Read a bounded, redacted snapshot of the fixed host service user's processes."""
    return run_json([sys.executable, str(SAFE_OPS()), 'user-process-snapshot'], timeout=20)

def pd_one_python_package_dry_run(package: str, version: str, python: str) -> str:
    """Resolve one pinned PyPI package against an approved PD One interpreter without installing it."""
    if not str(package or '').strip() or not str(version or '').strip() or (not str(python or '').strip()):
        raise ValueError('package, version, and python are required')
    return run_json([sys.executable, str(SAFE_OPS()), 'python-package-dry-run', '--package', str(package), '--version', str(version), '--python', str(python)], timeout=150)

def pd_one_python_media_stack_status() -> str:
    """Inspect the fixed PD One Python media module stack without importing or installing modules."""
    return run_json([sys.executable, str(SAFE_OPS()), 'python-media-stack-status'], timeout=30)

def pd_one_python_cad_stack_status(input_path: Optional[str]=None, second_input_path: Optional[str]=None) -> str:
    """Inspect the fixed PD One Python CAD module stack and optional cached STEP/3MF identity without importing modules."""
    cmd = [sys.executable, str(SAFE_OPS()), 'python-cad-stack-status']
    for raw in (input_path, second_input_path):
        value = str(raw or '').strip()
        if value:
            cmd.extend(['--input', value])
    return run_json(cmd, timeout=30)

def pd_one_step_geometry_inspect(input_path: str, action: str='check') -> str:
    """Inspect one approved STEP/STP file, check the source header, or summarize an existing inspect.json."""
    action = str(action or 'check').strip().lower()
    if action not in {'check', 'inspect', 'summarize'}:
        raise ValueError('action must be one of: check, inspect, summarize')
    input_path = str(input_path or '').strip()
    if not input_path:
        raise ValueError('input_path is required')
    timeout = 210 if action == 'inspect' else 30
    return run_json([sys.executable, str(SAFE_OPS()), 'step-geometry-inspect', '--action', action, '--input', input_path], timeout=timeout)

def pd_one_step_printability_analyze(input_path: str, action: str='check') -> str:
    """Check, analyze, or summarize one approved STEP with the official printability analyzer."""
    action = str(action or 'check').strip().lower()
    if action not in {'check', 'analyze', 'summarize'}:
        raise ValueError('action must be one of: check, analyze, summarize')
    input_path = str(input_path or '').strip()
    if not input_path:
        raise ValueError('input_path is required')
    timeout = 170 if action == 'analyze' else 30
    return run_json([sys.executable, str(SAFE_OPS()), 'step-printability-analyze', '--action', action, '--input', input_path], timeout=timeout)

def pd_one_cad_runtime_status() -> str:
    """Inspect fixed FreeCAD binaries and lib directories without executing FreeCAD."""
    return run_json([sys.executable, str(SAFE_OPS()), 'cad-runtime-status'], timeout=30)

def pd_one_python_docx_dependency_repair(ticket_id: str, action: str='inspect', confirm_live_write: Optional[str]=None) -> str:
    """Inspect or install python-docx==1.2.0 in the exact ticket-bound PD One release virtualenv."""
    ticket_id = str(ticket_id or '').strip()
    action = str(action or 'inspect').strip().lower()
    if ticket_id != PYTHON_DOCX_REPAIR_TICKET_ID():
        raise ValueError('ticket_id is not authorized for this exact dependency repair')
    if action not in {'inspect', 'install'}:
        raise ValueError('action must be one of: inspect, install')
    if action == 'install':
        if confirm_live_write != PYTHON_DOCX_REPAIR_CONFIRMATION():
            raise ValueError(f'install requires confirm_live_write={PYTHON_DOCX_REPAIR_CONFIRMATION()!r}')
    elif confirm_live_write:
        raise ValueError('confirm_live_write is only valid with action=install')
    cmd = [sys.executable, str(SAFE_OPS()), 'python-docx-dependency-repair', '--ticket-id', ticket_id, '--action', action]
    if confirm_live_write:
        cmd += ['--confirm-live-write', confirm_live_write]
    return run_json(cmd, timeout=240)

def pd_one_timezone_snapshot() -> str:
    """Capture a bounded UTC and Asia/Taipei current-time snapshot without execute_code."""
    return run_json([sys.executable, str(SAFE_OPS()), 'timezone-snapshot'], timeout=20)

def pd_one_protected_portal_origin_probe() -> str:
    """Probe the loopback PD One protected portal origin with fixed Access-identity GETs."""
    return run_json([sys.executable, str(SAFE_OPS()), 'protected-portal-origin-probe'], timeout=90)

def pd_one_timestamp_to_epoch(timestamp: str) -> str:
    """Convert one timezone-aware ISO-8601 timestamp to epoch seconds and milliseconds."""
    timestamp = str(timestamp or '').strip()
    if not timestamp:
        raise ValueError('timestamp is required')
    if len(timestamp) > 120:
        raise ValueError('timestamp must be 120 characters or fewer')
    return run_json([sys.executable, str(SAFE_OPS()), 'timestamp-to-epoch', '--timestamp', timestamp], timeout=20)

def pd_one_epoch_milliseconds_to_iso(epoch_milliseconds: list[int]) -> str:
    """Convert 1-20 UTC epoch-millisecond values to ISO-8601 strings without execute_code."""
    values = list(epoch_milliseconds or [])
    if not values:
        raise ValueError('epoch_milliseconds must contain at least one value')
    if len(values) > 20:
        raise ValueError('epoch_milliseconds must contain no more than 20 values')
    return run_json([sys.executable, str(SAFE_OPS()), 'epoch-milliseconds-to-iso', '--epoch-milliseconds', *[str(value) for value in values]], timeout=20)

def pd_one_sheets_serial_column_convert(serials: Optional[list[int]]=None, columns: Optional[list[str]]=None, ranges: Optional[list[str]]=None) -> str:
    """Convert bounded Google Sheets serial dates and A1 column letters without execute_code."""
    serial_values = list(serials or [])
    column_values = [str(value).strip() for value in columns or [] if str(value).strip()]
    range_values = [str(value).strip() for value in ranges or [] if str(value).strip()]
    if not serial_values and (not column_values) and (not range_values):
        raise ValueError('provide at least one serial, column, or A1 range')
    if len(serial_values) > 20:
        raise ValueError('serials must contain no more than 20 values')
    if len(column_values) > 20:
        raise ValueError('columns must contain no more than 20 values')
    if len(range_values) > 8:
        raise ValueError('ranges must contain no more than 8 values')
    cmd = [sys.executable, str(SAFE_OPS()), 'sheets-serial-column-convert']
    if serial_values:
        cmd += ['--serials', *[str(value) for value in serial_values]]
    if column_values:
        cmd += ['--columns', *column_values]
    if range_values:
        cmd += ['--ranges', *range_values]
    return run_json(cmd, timeout=20)

def pd_one_ollama_embedding_triage(lookback_hours: int=12, container_tail_lines: int=20000, journal_tail_lines: int=200, unit: str=OLLAMA_EMBEDDING_UNIT, container: str=OLLAMA_EMBEDDING_CONTAINER, peer_container: Optional[str]=OLLAMA_EMBEDDING_PEER_CONTAINER, port: int=OLLAMA_EMBEDDING_PORT) -> str:
    """Inspect Ollama embedding runtime health through typed unit, port, and bounded log probes."""
    cmd = [sys.executable, str(SAFE_OPS()), 'ollama-embedding-triage', '--lookback-hours', str(max(1, min(int(lookback_hours), 48))), '--container-tail-lines', str(max(100, min(int(container_tail_lines), 20000))), '--journal-tail-lines', str(max(20, min(int(journal_tail_lines), 2000))), '--unit', unit, '--container', container, '--port', str(max(1, min(int(port), 65535)))]
    if peer_container:
        cmd += ['--peer-container', peer_container]
    return run_json(cmd, timeout=300)

def pd_one_ollama_embedding_watchdog_triage(lookback_hours: int=12, journal_tail_lines: int=OLLAMA_EMBEDDING_WATCHDOG_MAX_JOURNAL_TAIL_LINES, unit: str=OLLAMA_EMBEDDING_WATCHDOG_UNIT) -> str:
    """Summarize the watchdog journal for remote/local embedding transitions.

    Use this instead of ad hoc execute_code journal-scanning heredocs when the
    question is only whether the embedding watchdog logged remote_ok, mode,
    switch, or failure transitions.
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'ollama-embedding-watchdog-triage', '--lookback-hours', str(max(1, min(int(lookback_hours), 48))), '--journal-tail-lines', str(max(20, min(int(journal_tail_lines), OLLAMA_EMBEDDING_WATCHDOG_MAX_JOURNAL_TAIL_LINES))), '--unit', unit]
    return run_json(cmd, timeout=180)

def pd_one_mattermost_channel_lookup(team_name: str, channel_name: str) -> str:
    """Read bot identity, an exact Mattermost team, and a channel by name.

    This is a bounded read-only replacement for ad hoc Mattermost API
    execute_code probes. It performs at most three GET requests, prints no
    credentials, and never changes channel metadata, permissions, or policy.
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'mattermost-channel-lookup', '--team-name', team_name, '--channel-name', channel_name]
    return run_json(cmd, timeout=90)

def pd_one_mattermost_channel_post_audit(channel_id: str, lookback_days: int=7, max_pages: int=10) -> str:
    """Read one bounded Mattermost channel's post metadata, including soft-deleted posts."""
    cmd = [sys.executable, str(SAFE_OPS()), 'mattermost-channel-post-audit', '--channel-id', channel_id, '--lookback-days', str(max(1, min(int(lookback_days), 30))), '--max-pages', str(max(1, min(int(max_pages), 10)))]
    return run_json(cmd, timeout=90)

def pd_one_admin_alert_source_audit() -> str:
    """Audit fixed PD One Python roots for bounded admin-alert delivery markers.

    This admin-only read-only tool returns paths and marker booleans, never file
    contents, credentials, source-system writes, or external sends.
    """
    return run_json([sys.executable, str(SAFE_OPS()), 'admin-alert-source-audit'], timeout=90)

def pd_one_mattermost_channel_setup(channel_id: str, action: str='inspect', target_display_name: Optional[str]=None, target_purpose: Optional[str]=None, max_posts: int=1200, include_members: bool=True, confirm_live_write: Optional[str]=None) -> str:
    """Inspect/setup a Mattermost channel without execute_code.

    Actions:
    - inspect: read channel metadata/history/member policy summary; no writes.
    - dry_run_update: return exact display-name/purpose patch plan; no writes.
    - apply_metadata: patch channel display_name/purpose and read back; requires
      confirm_live_write='RUN LIVE MATTERMOST CHANNEL SETUP'. Does not grant
      permissions or edit policy files.
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'mattermost-channel-setup', '--channel-id', channel_id, '--action', action, '--max-posts', str(int(max_posts))]
    if target_display_name:
        cmd += ['--target-display-name', target_display_name]
    if target_purpose:
        cmd += ['--target-purpose', target_purpose]
    if include_members:
        cmd += ['--include-members']
    if confirm_live_write:
        cmd += ['--confirm-live-write', confirm_live_write]
    return run_json(cmd, timeout=180)

def pd_one_admin_approval_request(requester_user_id: str, origin_channel_id: str, requested_action: str, request_type: str='generic_handoff_v1', requester_label: Optional[str]=None, origin_channel_name: Optional[str]=None, origin_root_id: Optional[str]=None, origin_post_id: Optional[str]=None, requested_scope: Optional[str]=None, risk_summary: Optional[str]=None, acceptance_criteria: Optional[str]=None, required_capabilities: Optional[str]=None, allowed_document_ids: Optional[str]=None, allowed_write_targets: Optional[str]=None, unresolved_assumptions: Optional[str]=None, request_original: Optional[str]=None, request_english: Optional[str]=None, dry_run: bool=False) -> str:
    """Create a bounded admin-approval handoff ticket and notify PD One Admin.

    Use whenever a Mattermost channel/DM request needs Owner/admin approval rather
    than telling the user escalation is unavailable. This tool only packages the
    request and posts an approval card; it does not execute privileged work.
    Preserve the source channel/thread/post ids so completion can return to the
    requester thread.

    Do not use this tool when the exact requester is Owner/admin and the origin
    post is his: that post is authorization. Execute in-session. If called anyway,
    the backend returns `already_authorized_no_ticket` and must not create a PDAPP
    card or queue the oneshot executor.

    Do not use this tool for a non-destructive in-place Google Sheet/Doc edit when
    live Drive ACL already grants the exact requester writer/editor (direct or via
    a writer group) on that exact file. That class is already authorized: execute
    and read back. If called anyway with `allowed_document_ids` set, the backend
    returns `already_authorized_no_ticket` and must not create a PDAPP card.
    Still ticket deletes, sharing/permission changes, Drive moves, unrelated files,
    credentials/config/gateway, and other red lines.
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'admin-approval-request', '--requester-user-id', requester_user_id, '--origin-channel-id', origin_channel_id, '--request-type', request_type, '--requested-action', requested_action]
    optional = {'--requester-label': requester_label, '--origin-channel-name': origin_channel_name, '--origin-root-id': origin_root_id, '--origin-post-id': origin_post_id, '--requested-scope': requested_scope, '--risk-summary': risk_summary, '--acceptance-criteria': acceptance_criteria, '--required-capabilities': required_capabilities, '--allowed-document-ids': allowed_document_ids, '--allowed-write-targets': allowed_write_targets, '--unresolved-assumptions': unresolved_assumptions, '--request-original': request_original, '--request-english': request_english}
    for flag, value in optional.items():
        if value:
            cmd.extend([flag, str(value)])
    if dry_run:
        cmd.append('--dry-run')
    return run_json(cmd, timeout=90)

def pd_one_admin_approval_list_open(max_results: int=100) -> str:
    """List open approval tickets from the deterministic ledger.

    This is the safe read-only alternative to raw `admin_approval_tickets.py list-open`
    subprocess glue. It returns bounded ticket metadata only and never executes
    privileged work.
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'admin-approval-list-open', '--max-results', str(max(1, min(int(max_results), 500)))]
    return run_json(cmd, timeout=60)

def pd_one_admin_approval_decide(ticket_id: str, decision_post_id: str, dry_run: bool=True, confirm_live_write: Optional[str]=None) -> str:
    """Validate and record an admin decision from an exact Mattermost post.

    The server re-fetches the post and derives sender, decision, instructions,
    channel, and thread itself. Preview is the default. Live mode records the
    decision, enqueues approved work, and kicks the oneshot executor. It does
    not execute the bound action in-process.
    """
    if not dry_run and confirm_live_write != ADMIN_APPROVAL_DECISION_LIVE_CONFIRMATION:
        raise ValueError(f'live admin approval decisions require confirm_live_write={ADMIN_APPROVAL_DECISION_LIVE_CONFIRMATION!r}')
    cmd = [sys.executable, str(SAFE_OPS()), 'admin-approval-decide', '--ticket-id', ticket_id, '--decision-post-id', decision_post_id]
    if dry_run:
        cmd.append('--dry-run')
    else:
        cmd.append('--live')
        cmd += ['--confirm-live-write', confirm_live_write or ADMIN_APPROVAL_DECISION_LIVE_CONFIRMATION]
    return run_json(cmd, timeout=60)

def pd_one_approval_ticket_status(ticket_id: str, fields: Optional[list[str]]=None, include_details: bool=False) -> str:
    """Read structured status for one PD One approval ticket.

    Safe read-only replacement for `admin_approval_tickets.py get | python/json.tool
    | grep/sed` shell pipelines. Pass `fields` to return only ready-to-consume
    values such as `ticket_status`, `requested_action`, or `employee_visible_summary`.
    Does not approve, enqueue, execute, mutate, or perform privileged work.
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'approval-ticket-status', '--ticket-id', ticket_id]
    for field in fields or []:
        if field:
            cmd.extend(['--field', str(field)])
    if include_details:
        cmd.append('--include-details')
    return run_json(cmd, timeout=60)

def pd_one_admin_approval_kanban_status(ticket_id: str) -> str:
    """Read bounded PDAPP Kanban mapping/result/workspace existence for one ticket.

    Admin-only replacement for execute_code probes that check
    state/admin-approval-kanban mappings or results, or whether a
    pdapp-approvals workspace directory exists. Returns existence and
    selected status fields only. Never lists workspace files, reads MCP
    sources, inspects systemd runtime, or returns result summaries.
    """
    ticket_id = str(ticket_id or '').strip()
    if not ticket_id:
        raise ValueError('ticket_id is required')
    return run_json([sys.executable, str(SAFE_OPS()), 'admin-approval-kanban-status', '--ticket-id', ticket_id], timeout=30)

def pd_one_hermes_result_messages_summary(result_path: str, max_messages: int=200) -> str:
    """Summarize one bounded Hermes result artifact's message metadata/content shapes.

    This is an admin-only, read-only replacement for ad hoc JSON-loading
    execute_code against /tmp/hermes-results. The backing safe-op restricts the
    path, file size, message count, and receipt content; it never executes the
    inspected result or delivers it externally.
    """
    result_path = str(result_path or '').strip()
    if not result_path or len(result_path) > 500:
        raise ValueError('result_path is required and must be at most 500 characters')
    cmd = [sys.executable, str(SAFE_OPS()), 'hermes-result-messages-summary', '--input', result_path, '--max-messages', str(max(1, min(int(max_messages), 200)))]
    return run_json(cmd, timeout=60)

def pd_one_json_artifact_inspect(input_paths: list[str]) -> str:
    """Inspect structure of 1-4 approved local JSON artifacts without dumping values.

    Admin-only replacement for execute_code that json.load()s cached JSON dumps
    and prints types/keys/sample0 keys. Returns path/size/SHA-256 plus bounded
    structure receipts. Never returns cell/row values, writes files, or delivers
    externally.
    """
    paths = [str(item or '').strip() for item in input_paths or [] if str(item or '').strip()]
    if not paths:
        raise ValueError('input_paths is required')
    if len(paths) > 4:
        raise ValueError('input_paths accepts at most 4 files')
    cmd = [sys.executable, str(SAFE_OPS()), 'json-artifact-inspect']
    for path in paths:
        if len(path) > 500:
            raise ValueError('each input path must be at most 500 characters')
        cmd.extend(['--input', path])
    return run_json(cmd, timeout=60)

def pd_one_local_file_search(paths: Optional[list[str]]=None, patterns: Optional[list[str]]=None) -> str:
    """Identity-check approved local paths and search filename globs without dumping contents.

    Admin-only replacement for execute_code that imports hermes_tools
    search_files/read_file and prints file bodies. Returns path existence,
    size, suffix, and bounded glob matches under approved PD One roots.
    Never searches ~, never returns file contents, and never
    writes or delivers artifacts. Use native read_file for explicit content.
    """
    clean_paths = [str(item or '').strip() for item in paths or [] if str(item or '').strip()]
    clean_patterns = [str(item or '').strip() for item in patterns or [] if str(item or '').strip()]
    if not clean_paths and (not clean_patterns):
        raise ValueError('provide at least one path or pattern')
    if len(clean_paths) > 8:
        raise ValueError('paths accepts at most 8 values')
    if len(clean_patterns) > 8:
        raise ValueError('patterns accepts at most 8 values')
    cmd = [sys.executable, str(SAFE_OPS()), 'local-file-search']
    for path in clean_paths:
        if len(path) > 500:
            raise ValueError('each path must be at most 500 characters')
        cmd.extend(['--path', path])
    for pattern in clean_patterns:
        if len(pattern) > 120:
            raise ValueError('each pattern must be at most 120 characters')
        cmd.extend(['--pattern', pattern])
    return run_json(cmd, timeout=60)

def pd_one_mattermost_member_search(sender_id: str, query: str, channel_ids: Optional[list[str]]=None, since: Optional[str]=None, max_results: int=20, max_channels: int=100, max_fallback_posts: int=1200) -> str:
    """Read-only Mattermost search scoped to channels where sender_id is a live member.

    Use for employee requests to search/summarize their own visible Mattermost
    channels. The wrapper verifies exact requester id + live channel membership,
    ignores the bot's broader visibility as an authorization basis, and returns
    bounded excerpts/post links only (no raw transcript dumps or writes).
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'mattermost-member-search', '--sender-id', sender_id, '--query', query, '--max-results', str(int(max_results)), '--max-channels', str(int(max_channels)), '--max-fallback-posts', str(int(max_fallback_posts))]
    for cid in channel_ids or []:
        cmd += ['--channel-id', cid]
    if since:
        cmd += ['--since', since]
    return run_json(cmd, timeout=180)

def pd_one_yammer_archive_search(sender_id: str, query: str, origin_channel_id: Optional[str]=None, max_results: int=15) -> str:
    """Read-only scoped Yammer/Viva Engage historical archive search.

    Authorize by exact Mattermost sender_id + PD One policy. Blocks finance/payroll/
    HR-private/credentials domains when the requester dataAccess denies them (e.g. QA
    cannot search finance). Returns bounded excerpts and a sources_searched receipt.
    Always report sources_searched in the user-facing reply.
    """
    cmd = [sys.executable, str(SAFE_OPS()), 'yammer-archive-search', '--sender-id', sender_id, '--query', query, '--max-results', str(int(max_results))]
    if origin_channel_id:
        cmd += ['--origin-channel-id', origin_channel_id]
    return run_json(cmd, timeout=120)

def pd_one_policy_change_dry_run(user_id: str, add_role: Optional[str]=None, add_dm_scope: Optional[str]=None, set_active: Optional[str]=None) -> str:
    """Preview Mattermost policy role/scope/active changes with unified diff. Does not write."""
    cmd = [sys.executable, str(SAFE_OPS()), 'policy-change-dry-run', '--user-id', user_id]
    if add_role:
        cmd += ['--add-role', add_role]
    if add_dm_scope:
        cmd += ['--add-dm-scope', add_dm_scope]
    if set_active:
        cmd += ['--set-active', set_active]
    return run_json(cmd)

def worker_scheduling_execute(action: str, solve_groups: Optional[list[str]]=None, solver_max_time_seconds: Optional[int]=None, solver_no_improvement_seconds: Optional[int]=None, following_month_required_rest_days_count: Optional[int]=None, stdout_summary_only: bool=True, timeout_seconds: int=420, output_dir: Optional[str]=None, confirm_live_write: Optional[bool]=None) -> str:
    """Run the PD One monthly worker scheduling playbook through a narrow typed wrapper.

    Actions:
    - preflight: parse source + destination dry-run only; never writes.
    - solve_preview: run a joint primary/following-month OR-Tools preview; never writes. Requires following_month_required_rest_days_count.
    - write_generated_schedule: live generated-schedule writeback; requires
      confirm_live_write=true after explicit, scoped approved-user authorization.
    """
    try:
        cmd, out_dir, live_write = _worker_scheduling_command(action=action, solve_groups=solve_groups, solver_max_time_seconds=solver_max_time_seconds, solver_no_improvement_seconds=solver_no_improvement_seconds, following_month_required_rest_days_count=following_month_required_rest_days_count, stdout_summary_only=stdout_summary_only, output_dir=output_dir, confirm_live_write=confirm_live_write)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'error': 'invalid_request', 'detail': str(exc)})
    result = _run_worker_scheduling_command(cmd, out_dir, timeout_seconds=timeout_seconds)
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return result
    payload.setdefault('safety', {})
    payload['safety'].update({'live_write_requested': live_write, 'live_write_confirmation_required': WORKER_SCHEDULING_LIVE_CONFIRMATION_REQUIREMENT, 'shell_used': False, 'allowed_actions': ['preflight', 'solve_preview', 'write_generated_schedule']})
    return _json_result(payload)

def worker_scheduling_audit_rest_requests(output_dir: Optional[str]=None, timeout_seconds: int=180) -> str:
    """Audit raw 原資料 rest requests before scheduling. Read-only; never writes."""
    out_dir = _approved_output_dir(output_dir, 'audit_rest_requests')
    script = SCHEDULER_PROJECT() / 'scripts/audit_rest_requests.py'
    cmd = [sys.executable, str(script), '--gog-account', site_text('PDONE_EMAIL_ADMIN'), '--output-dir', str(out_dir), '--stdout-json']
    result = _run_cmd(cmd, timeout=max(30, min(int(timeout_seconds), 600)))
    receipt = {'status': result.get('status'), 'output_dir': str(out_dir), 'report_path': str(out_dir / 'rest-request-audit.json'), 'result': result, 'safety': {'read_only': True, 'shell_used': False}}
    _write_receipt(out_dir, 'mcp-audit-rest-requests-receipt.json', receipt)
    return _json_result(receipt)

def worker_scheduling_correct_raw_request_dates(row_number: int, old_dates: list[str], new_dates: list[str], worker_name: Optional[str]=None, dry_run: bool=True, note_text: Optional[str]=None, output_dir: Optional[str]=None, confirm_live_write: Optional[str]=None) -> str:
    """Correct confirmed raw 原資料 request-date cells K:O with old-value match, notes, and readback.

    Replaces each old_dates[i] with new_dates[i] in the specified raw row's K:O cells.
    Live writes require confirm_live_write='RUN LIVE WORKER SCHEDULING SOURCE WRITE'.
    """
    try:
        row = int(row_number)
        if row < 2:
            raise ValueError('row_number must point to a data row (>=2)')
        if not isinstance(old_dates, list) or not isinstance(new_dates, list) or len(old_dates) != len(new_dates) or (not old_dates):
            raise ValueError('old_dates and new_dates must be non-empty lists of equal length')
        if len(old_dates) > 5:
            raise ValueError('At most five request-date replacements are allowed (K:O)')
        old_canon = [_canonical_date(d) for d in old_dates]
        new_canon = [_canonical_date(d) for d in new_dates]
        if len(set(old_canon)) != len(old_canon):
            raise ValueError('old_dates must be unique')
        live = not dry_run
        if live and confirm_live_write != WORKER_SCHEDULING_SOURCE_CONFIRMATION:
            raise ValueError(f'live source correction requires confirm_live_write={WORKER_SCHEDULING_SOURCE_CONFIRMATION!r}')
        out_dir = _approved_output_dir(output_dir, f'correct_raw_request_row_{row}')
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'error': 'invalid_request', 'detail': str(exc)})
    row_range = f"'{RAW_REQUEST_SHEET}'!A{row}:AD{row}"
    before = _gog_get(SOURCE_SPREADSHEET_ID(), row_range)
    values = _extract_values(before)
    padded = (values[0] if values else []) + [''] * 30
    current_name = str(padded[1]).strip()
    if worker_name and worker_name.strip() not in current_name:
        receipt = {'status': 'error', 'error': 'worker_name_mismatch', 'expected_contains': worker_name, 'actual': current_name, 'before': before}
        _write_receipt(out_dir, 'mcp-correct-raw-request-dates-receipt.json', receipt)
        return _json_result(receipt)
    date_cells = []
    for col_index in range(11, 16):
        raw_value = padded[col_index - 1]
        col = _column_name(col_index)
        date_cells.append({'column': col, 'range': f"'{RAW_REQUEST_SHEET}'!{col}{row}", 'value': str(raw_value).strip(), 'canonical': _canonical_date(raw_value)})
    remaining = {old: new for old, new in zip(old_canon, new_canon)}
    updates = []
    for cell in date_cells:
        old = cell['canonical']
        if old in remaining:
            updates.append({**cell, 'old_value': old, 'new_value': remaining.pop(old)})
    if remaining:
        receipt = {'status': 'error', 'error': 'old_dates_not_found', 'missing_old_dates': sorted(remaining), 'row_name': current_name, 'date_cells': date_cells, 'before': before}
        _write_receipt(out_dir, 'mcp-correct-raw-request-dates-receipt.json', receipt)
        return _json_result(receipt)
    note = note_text or f'Changed after coordinating with {worker_name or current_name}: requested dates moved from {', '.join(old_canon)} to {', '.join(new_canon)}.'
    write_results = []
    note_results = []
    if live:
        for update in updates:
            write_results.append(_run_cmd(_gog_cmd('sheets', 'update', SOURCE_SPREADSHEET_ID(), update['range'], '--input', 'USER_ENTERED', '--values-json', json.dumps([[update['new_value']]], ensure_ascii=False), account=site_text('PDONE_EMAIL_ADMIN')), timeout=120))
            note_results.append(_run_cmd(_gog_cmd('sheets', 'update-note', SOURCE_SPREADSHEET_ID(), update['range'], '--note', note, account=site_text('PDONE_EMAIL_ADMIN')), timeout=120))
    edited_range = f"'{RAW_REQUEST_SHEET}'!K{row}:O{row}"
    after_values = _gog_get(SOURCE_SPREADSHEET_ID(), edited_range) if live else None
    after_notes = _gog_notes(SOURCE_SPREADSHEET_ID(), edited_range) if live else None
    formula_check = _gog_get(SOURCE_SPREADSHEET_ID(), f"'{RAW_REQUEST_SHEET}'!U{row}:V{row}") if live else None
    formula_values = _extract_values(formula_check or {}) if formula_check else []
    formula_regression = any(('#VALUE' in str(v) or '#REF' in str(v) for r in formula_values for v in r))
    receipt = {'status': 'ok' if not formula_regression and all((r.get('status') == 'ok' for r in write_results + note_results)) else 'error', 'dry_run': not live, 'row_number': row, 'row_name': current_name, 'updates_planned': updates, 'note_text': note, 'before': before, 'write_results': write_results, 'note_results': note_results, 'after_values': after_values, 'after_notes': after_notes, 'formula_check': formula_check, 'formula_regression_detected': formula_regression, 'receipt_path': str(out_dir / 'mcp-correct-raw-request-dates-receipt.json'), 'safety': {'live_write_requested': live, 'live_write_confirmation_required': WORKER_SCHEDULING_SOURCE_CONFIRMATION, 'old_value_match_required': True, 'notes_required': True, 'shell_used': False}}
    _write_receipt(out_dir, 'mcp-correct-raw-request-dates-receipt.json', receipt)
    return _json_result(receipt)

def worker_scheduling_source_setup(a2_value: str, a4_value: str, required_rest_days_count: int, dry_run: bool=True, output_dir: Optional[str]=None, confirm_live_write: Optional[str]=None) -> str:
    """Set/verify 申請日期-當月統計!A2, A4, A10 before solve. Live writes require source confirmation."""
    try:
        required = int(required_rest_days_count)
        if required < 0 or required > 31:
            raise ValueError('required_rest_days_count must be between 0 and 31')
        live = not dry_run
        if live and confirm_live_write != WORKER_SCHEDULING_SOURCE_CONFIRMATION:
            raise ValueError(f'live source setup requires confirm_live_write={WORKER_SCHEDULING_SOURCE_CONFIRMATION!r}')
        out_dir = _approved_output_dir(output_dir, 'source_setup')
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'error': 'invalid_request', 'detail': str(exc)})
    data = [{'range': f"'{MONTHLY_SOURCE_SHEET}'!A2", 'values': [[a2_value]]}, {'range': f"'{MONTHLY_SOURCE_SHEET}'!A4", 'values': [[a4_value]]}, {'range': f"'{MONTHLY_SOURCE_SHEET}'!A10", 'values': [[str(required)]]}]
    before = _gog_get(SOURCE_SPREADSHEET_ID(), f"'{MONTHLY_SOURCE_SHEET}'!A2:A10")
    before_values = _extract_values(before)

    def control_value(values: list[list[Any]], row_number: int) -> str:
        index = row_number - 2
        if index < 0 or index >= len(values) or (not values[index]):
            return ''
        return str(values[index][0]).strip()
    expected_labels = {'A3': 'Month', 'A5': 'Shift', 'A9': 'Required Rest Days'}
    observed_labels = {cell: control_value(before_values, int(cell[1:])) for cell in expected_labels}
    layout_mismatches = {cell: {'expected': expected, 'observed': observed_labels.get(cell, '')} for cell, expected in expected_labels.items() if observed_labels.get(cell, '') != expected}
    if before.get('status') != 'ok' or layout_mismatches:
        receipt = {'status': 'error', 'error': 'source_control_layout_mismatch', 'detail': 'Refusing source setup because the live control labels do not match A3=Month, A5=Shift, A9=Required Rest Days.', 'dry_run': not live, 'updates_planned': data, 'before': before, 'expected_labels': expected_labels, 'observed_labels': observed_labels, 'layout_mismatches': layout_mismatches, 'write_result': None, 'after': None, 'safety': {'live_write_requested': live, 'write_blocked': True, 'live_write_confirmation_required': WORKER_SCHEDULING_SOURCE_CONFIRMATION, 'shell_used': False}}
        _write_receipt(out_dir, 'mcp-source-setup-receipt.json', receipt)
        return _json_result(receipt)
    write_result = None
    if live:
        write_result = _run_cmd(_gog_cmd('sheets', 'batch-update', SOURCE_SPREADSHEET_ID(), '--data-json', json.dumps(data, ensure_ascii=False), '--input', 'USER_ENTERED', account=site_text('PDONE_EMAIL_ADMIN')), timeout=120)
    after = _gog_get(SOURCE_SPREADSHEET_ID(), f"'{MONTHLY_SOURCE_SHEET}'!A2:A10") if live else None
    after_values = _extract_values(after or {})
    expected_after = {'A2': str(a2_value), 'A3': 'Month', 'A4': str(a4_value), 'A5': 'Shift', 'A9': 'Required Rest Days', 'A10': str(required)}
    observed_after = {cell: control_value(after_values, int(cell[1:])) for cell in expected_after} if live else {}
    after_mismatches = {cell: {'expected': expected, 'observed': observed_after.get(cell, '')} for cell, expected in expected_after.items() if live and observed_after.get(cell, '') != expected}
    av_check = _gog_get(SOURCE_SPREADSHEET_ID(), f"'{MONTHLY_SOURCE_SHEET}'!AV2:AV80") if live else None
    av_check_status_ok = (av_check or {}).get('status') == 'ok' if live else None
    av_values = [str(v).strip() for row in _extract_values(av_check or {}) for v in row if str(v).strip()]
    av_mismatches = sorted({v for v in av_values if v != str(required)})[:20]
    receipt = {'status': 'ok' if not live or ((write_result or {}).get('status') == 'ok' and (after or {}).get('status') == 'ok' and av_check_status_ok and (not av_mismatches) and (not after_mismatches)) else 'error', 'dry_run': not live, 'updates_planned': data, 'before': before, 'expected_labels': expected_labels, 'observed_labels': observed_labels, 'layout_mismatches': layout_mismatches, 'write_result': write_result, 'after': after, 'expected_after': expected_after, 'observed_after': observed_after, 'after_mismatches': after_mismatches, 'required_rest_days_count': required, 'required_rest_days_av_mismatches_sample': av_mismatches, 'av_check_status_ok': av_check_status_ok, 'av_check': av_check, 'safety': {'live_write_requested': live, 'live_write_confirmation_required': WORKER_SCHEDULING_SOURCE_CONFIRMATION, 'shell_used': False}}
    _write_receipt(out_dir, 'mcp-source-setup-receipt.json', receipt)
    return _json_result(receipt)

def worker_scheduling_sync_source_rollover(dry_run: bool=True, output_dir: Optional[str]=None, timeout_seconds: int=420, confirm_live_write: Optional[str]=None) -> str:
    """Run the separate source rollover/sync step. Never combines with solve/writeback."""
    try:
        live = not dry_run
        if live and confirm_live_write != WORKER_SCHEDULING_SOURCE_CONFIRMATION:
            raise ValueError(f'live source rollover requires confirm_live_write={WORKER_SCHEDULING_SOURCE_CONFIRMATION!r}')
        out_dir = _approved_output_dir(output_dir, 'sync_source_rollover')
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'error': 'invalid_request', 'detail': str(exc)})
    cmd = [str(SCHEDULER_PYTHON()), str(SCHEDULER_SCRIPT()), '--gog-account', site_text('PDONE_EMAIL_ADMIN'), '--output-dir', str(out_dir), '--stdout-summary-only']
    if live:
        cmd += ['--sync-source-rollover', '--yes']
    result = _run_worker_scheduling_command(cmd, out_dir, timeout_seconds=max(60, min(int(timeout_seconds), 1200)))
    payload = json.loads(result)
    payload.setdefault('safety', {})
    payload['safety'].update({'live_write_requested': live, 'live_write_confirmation_required': WORKER_SCHEDULING_SOURCE_CONFIRMATION, 'separate_from_solve_writeback': True, 'shell_used': False})
    _write_receipt(out_dir, 'mcp-sync-source-rollover-receipt.json', payload)
    return _json_result(payload)

def worker_scheduling_closeout_processed_requests(scheduled_month: str, dry_run: bool=True, output_dir: Optional[str]=None, timeout_seconds: int=180, confirm_live_write: Optional[str]=None) -> str:
    """Dry-run or close out processed raw requests in 原資料!AD after HR MAX acceptance and announcement."""
    try:
        if not isinstance(scheduled_month, str) or len(scheduled_month) != 7 or scheduled_month[4] != '-':
            raise ValueError('scheduled_month must be YYYY-MM')
        live = not dry_run
        if live and confirm_live_write != WORKER_SCHEDULING_SOURCE_CONFIRMATION:
            raise ValueError(f'live closeout requires confirm_live_write={WORKER_SCHEDULING_SOURCE_CONFIRMATION!r}')
        out_dir = _approved_output_dir(output_dir, f'closeout_{scheduled_month}')
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'error': 'invalid_request', 'detail': str(exc)})
    script = SCHEDULER_PROJECT() / 'scripts/closeout_processed_requests.py'
    cmd = [sys.executable, str(script), '--gog-account', site_text('PDONE_EMAIL_ADMIN'), '--scheduled-month', scheduled_month, '--output-dir', str(out_dir), '--stdout-json']
    if live:
        cmd += ['--write', '--yes']
    result = _run_cmd(cmd, timeout=max(30, min(int(timeout_seconds), 600)))
    receipt = {'status': result.get('status'), 'dry_run': not live, 'output_dir': str(out_dir), 'result': result, 'safety': {'live_write_requested': live, 'live_write_confirmation_required': WORKER_SCHEDULING_SOURCE_CONFIRMATION, 'hr_max_acceptance_required_before_live': True, 'announcement_required_before_live': True, 'shell_used': False}}
    _write_receipt(out_dir, 'mcp-closeout-processed-requests-receipt.json', receipt)
    return _json_result(receipt)
IM_SCHEDULING_GATES = {'audit_rest_requests': 'Gate A — raw rest-request audit', 'preflight': 'Gate B — preflight', 'solve_preview': 'Gate C — solve preview', 'writeback': 'Gate D — before generated-schedule writeback', 'hrmax': 'Gate E — HR MAX import artifact', 'mcp_failure': 'Gate F — failed/partial MCP call'}
IM_SCHEDULING_PROFILE = 'im-scheduling'

def _im_scheduling_receipt_path(receipt_path: Optional[str], output_dir: Optional[str]) -> Path:
    allowed_roots = [WORKER_SCHEDULING_RECEIPTS(), Path(resolve_configured_path('~/.hermes/profiles/pdone/tmp')), SCHEDULER_PROJECT() / 'tmp', Path(resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/tmp'))]
    candidates: list[Path] = []
    if receipt_path:
        candidates.append(Path(str(receipt_path)))
    if output_dir:
        out = Path(str(output_dir))
        for name in ('generated-schedule-report.json', 'rest-request-audit.json', 'preflight-summary.json', 'mcp-audit-rest-requests-receipt.json'):
            maybe = out / name
            if maybe.is_file():
                candidates.append(maybe)
                break
        else:
            candidates.append(out)
    if not candidates:
        raise ValueError('receipt_path or output_dir is required')
    resolved = candidates[0].resolve()
    if not any((resolved == root.resolve() or str(resolved).startswith(str(root.resolve()) + os.sep) for root in allowed_roots)):
        raise ValueError('receipt_path/output_dir must be under approved worker-scheduling receipt roots')
    if not resolved.exists():
        raise FileNotFoundError(f'receipt not found: {resolved}')
    return resolved

def worker_scheduling_review_im_scheduling(gate: str, target_month: str, receipt_path: Optional[str]=None, output_dir: Optional[str]=None, solve_group: Optional[str]=None, notes: Optional[str]=None, timeout_seconds: int=180) -> str:
    """Read-only review handoff to the im-scheduling profile. Never writes sheets."""
    gate_key = str(gate or '').strip().lower().replace('-', '_')
    if gate_key not in IM_SCHEDULING_GATES:
        return _json_result({'status': 'error', 'error': 'invalid_review_gate', 'gate': gate_key, 'allowed_gates': sorted(IM_SCHEDULING_GATES), 'safety': {'read_only': True, 'live_write_requested': False, 'shell_used': False}})
    month = str(target_month or '').strip()
    if not month:
        return _json_result({'status': 'error', 'error': 'missing_payload_field', 'field': 'target_month', 'safety': {'read_only': True, 'shell_used': False}})
    try:
        receipt = _im_scheduling_receipt_path(receipt_path, output_dir)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'error': 'invalid_receipt', 'detail': str(exc), 'safety': {'read_only': True, 'shell_used': False}})
    group = str(solve_group or '').strip()
    if group and group not in WORKER_SCHEDULING_GROUPS:
        return _json_result({'status': 'error', 'error': 'invalid_solve_group', 'solve_group': group, 'allowed_groups': sorted(WORKER_SCHEDULING_GROUPS), 'safety': {'read_only': True, 'shell_used': False}})
    note_text = str(notes or '').strip()[:1000]
    prompt = f'Read-only worker-scheduling review. {IM_SCHEDULING_GATES[gate_key]}.\nTarget month: {month}\nGroup: {group or 'n/a'}\nReceipt path: {receipt}\nCaller notes: {note_text or 'n/a'}\nRead the receipt if it is a file. Do not write Google Sheets, run solvers, upload HR MAX, send Mattermost, or change Hermes config.\nReturn PASS, WARN, or BLOCK first, then concise evidence and the smallest next action for PD One.'
    hermes_bin = 'hermes'
    cmd = [hermes_bin, '-p', IM_SCHEDULING_PROFILE, '-z', prompt]
    result = _run_cmd(cmd, timeout=max(30, min(int(timeout_seconds), 180)))
    out_dir = _approved_output_dir(output_dir, 'review_im_scheduling')
    receipt_payload = {'status': result.get('status'), 'action': 'review_im_scheduling', 'gate': gate_key, 'target_month': month, 'solve_group': group or None, 'receipt_path': str(receipt), 'reviewer_profile': IM_SCHEDULING_PROFILE, 'review_text': (result.get('stdout_tail') or '')[-4000:], 'result': {k: result.get(k) for k in ('status', 'returncode', 'error', 'timeout_seconds', 'stderr_tail')}, 'safety': {'read_only': True, 'live_write_requested': False, 'shell_used': False, 'does_not_write_sheets': True, 'actor_of_record': 'pdone'}}
    _write_receipt(out_dir, 'mcp-review-im-scheduling-receipt.json', receipt_payload)
    receipt_payload['output_dir'] = str(out_dir)
    return _json_result(receipt_payload)

def worker_scheduling(action: str, payload: Optional[dict[str, Any]]=None, dry_run: bool=True, timeout_seconds: int=420, output_dir: Optional[str]=None, confirm_live_write: Optional[Union[str, bool]]=None) -> str:
    """Run the monthly worker-scheduling playbook through one stable action dispatcher.

    Use this tool instead of adding one MCP tool per playbook step. Supported actions:
    - audit_rest_requests
    - correct_raw_request_dates
    - source_setup
    - setup_scheduling_rules
    - sync_source_rollover
    - preflight
    - solve_preview (solve only; solver_max_time_seconds is capped at 180)
    - write_generated_schedule_from_report (write only from an existing feasible/optimal generated-schedule-report.json)
    - closeout_processed_requests
    - review_im_scheduling (read-only handoff to profile im-scheduling; never writes sheets)

    Put action-specific arguments in payload. Live source writes require
    confirm_live_write='RUN LIVE WORKER SCHEDULING SOURCE WRITE'. Generated
    schedule writeback requires confirm_live_write=true after explicit, scoped approved-user authorization.
    """
    from tools.pd_one_ops.pd_one_safe_ops_mcp_part1 import worker_scheduling_setup_rules
    payload = payload or {}
    if not isinstance(payload, dict):
        return _json_result({'status': 'error', 'error': 'invalid_request', 'detail': 'payload must be an object'})
    action_key = str(action or '').strip().lower().replace('-', '_')
    try:
        if action_key == 'poll_solve_preview':
            return _poll_worker_scheduling_job(output_dir=str(payload.get('output_dir') or output_dir or ''), wait_seconds=int(payload.get('wait_seconds', 0)))
        if action_key in {'preflight', 'solve_preview'}:
            solver_max = payload.get('solver_max_time_seconds')
            solver_no_improvement = payload.get('solver_no_improvement_seconds')
            if action_key == 'solve_preview':
                solver_max = min(int(solver_max or 180), 180)
                if solver_no_improvement is None:
                    solver_no_improvement = 45
            cmd, out_dir, _live_write = _worker_scheduling_command(action=action_key, solve_groups=payload.get('solve_groups'), solver_max_time_seconds=solver_max, solver_no_improvement_seconds=solver_no_improvement, following_month_required_rest_days_count=payload.get('following_month_required_rest_days_count'), stdout_summary_only=bool(payload.get('stdout_summary_only', True)), output_dir=payload.get('output_dir', output_dir), confirm_live_write=confirm_live_write or payload.get('confirm_live_write'))
            wrapper_timeout = max(60, min(int(payload.get('timeout_seconds', 300)), 300)) if action_key == 'solve_preview' else max(30, min(int(payload.get('timeout_seconds', timeout_seconds)), 180))
            if action_key == 'solve_preview' and (not bool(payload.get('wait_for_completion', False))):
                return _start_worker_scheduling_job(cmd, out_dir, wrapper_timeout)
            return _run_worker_scheduling_command(cmd, out_dir, wrapper_timeout)
        if action_key == 'write_generated_schedule':
            return _json_result({'status': 'error', 'error': 'split_required', 'detail': "Combined solve+write is disabled. Run action='solve_preview' first with solver_max_time_seconds<=180, verify the generated-schedule-report.json is FEASIBLE/OPTIMAL, then run action='write_generated_schedule_from_report'.", 'allowed_replacement_actions': ['solve_preview', 'write_generated_schedule_from_report'], 'safety': {'does_not_run_solver': True, 'live_write_requested': False, 'shell_used': False}})
        if action_key == 'write_generated_schedule_from_report':
            report = _resolve_generated_schedule_report(payload, output_dir)
            return worker_scheduling_write_generated_schedule_from_report(report_path=str(report), run_groups=payload.get('solve_groups') or payload.get('run_groups'), dry_run=bool(payload.get('dry_run', dry_run)), output_dir=payload.get('output_dir') or payload.get('write_output_dir') or payload.get('receipt_output_dir'), confirm_live_write=confirm_live_write or payload.get('confirm_live_write'), max_format_batches_per_call=int(payload.get('max_format_batches_per_call', 25)), max_value_batches_per_call=int(payload.get('max_value_batches_per_call', 5)))
        if action_key == 'audit_rest_requests':
            return worker_scheduling_audit_rest_requests(output_dir=payload.get('output_dir', output_dir), timeout_seconds=int(payload.get('timeout_seconds', timeout_seconds if timeout_seconds != 420 else 180)))
        if action_key == 'correct_raw_request_dates':
            return worker_scheduling_correct_raw_request_dates(row_number=int(payload['row_number']), old_dates=list(payload['old_dates']), new_dates=list(payload['new_dates']), worker_name=payload.get('worker_name'), dry_run=bool(payload.get('dry_run', dry_run)), note_text=payload.get('note_text'), output_dir=payload.get('output_dir', output_dir), confirm_live_write=confirm_live_write or payload.get('confirm_live_write'))
        if action_key == 'source_setup':
            return worker_scheduling_source_setup(a2_value=str(payload['a2_value']), a4_value=str(payload['a4_value']), required_rest_days_count=int(payload['required_rest_days_count']), dry_run=bool(payload.get('dry_run', dry_run)), output_dir=payload.get('output_dir', output_dir), confirm_live_write=confirm_live_write or payload.get('confirm_live_write'))
        if action_key == 'setup_scheduling_rules':
            if payload:
                return _json_result({'status': 'error', 'error': 'setup_scheduling_rules_payload_not_allowed', 'detail': 'This action uses one fixed, reviewed spreadsheet/tab/schema/seed row and accepts no payload overrides.', 'safety': {'shell_used': False, 'payload_is_fixed': True}})
            return worker_scheduling_setup_rules(dry_run=dry_run, confirm_live_write=confirm_live_write, output_dir=output_dir)
        if action_key == 'sync_source_rollover':
            return worker_scheduling_sync_source_rollover(dry_run=bool(payload.get('dry_run', dry_run)), output_dir=payload.get('output_dir', output_dir), timeout_seconds=int(payload.get('timeout_seconds', timeout_seconds)), confirm_live_write=confirm_live_write or payload.get('confirm_live_write'))
        if action_key == 'closeout_processed_requests':
            return worker_scheduling_closeout_processed_requests(scheduled_month=str(payload['scheduled_month']), dry_run=bool(payload.get('dry_run', dry_run)), output_dir=payload.get('output_dir', output_dir), timeout_seconds=int(payload.get('timeout_seconds', timeout_seconds if timeout_seconds != 420 else 180)), confirm_live_write=confirm_live_write or payload.get('confirm_live_write'))
        if action_key == 'review_im_scheduling':
            return worker_scheduling_review_im_scheduling(gate=str(payload.get('gate') or ''), target_month=str(payload.get('target_month') or ''), receipt_path=payload.get('receipt_path'), output_dir=payload.get('output_dir', output_dir), solve_group=payload.get('solve_group'), notes=payload.get('notes'), timeout_seconds=int(payload.get('timeout_seconds', 180)))
    except KeyError as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'error': 'missing_payload_field', 'field': str(exc), 'action': action_key})
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return _json_result({'status': 'error', 'error': 'invalid_request', 'detail': str(exc), 'action': action_key})
    return _json_result({'status': 'error', 'error': 'unknown_action', 'action': action_key, 'allowed_actions': ['audit_rest_requests', 'correct_raw_request_dates', 'source_setup', 'setup_scheduling_rules', 'sync_source_rollover', 'preflight', 'solve_preview', 'write_generated_schedule_from_report', 'closeout_processed_requests', 'review_im_scheduling']})

def _load_apps_script_content(project: dict[str, str]) -> dict[str, Any]:
    proc = subprocess.run([str(GOG()), '-j', '--account', project['account'], 'appscript', 'content', project['script_id']], text=True, capture_output=True, timeout=120, shell=False)
    if proc.returncode != 0:
        raise RuntimeError(f'gog appscript content failed: {proc.stderr[-1000:]}')
    data = json.loads(proc.stdout or '{}')
    if 'files' in data:
        return data
    if isinstance(data.get('content'), dict) and 'files' in data['content']:
        return data['content']
    raise RuntimeError(f'unexpected Apps Script content shape: {sorted(data.keys())}')

def _export_gog_refresh_token(account: str) -> str:
    fd, tmp = tempfile.mkstemp(prefix='pdone-gog-token-', suffix='.json')
    os.close(fd)
    try:
        proc = subprocess.run([str(GOG()), 'auth', 'tokens', 'export', account, '--out', tmp, '--overwrite'], text=True, capture_output=True, timeout=60, shell=False)
        if proc.returncode != 0:
            raise RuntimeError(f'gog token export failed: {proc.stderr[-1000:]}')
        data = json.loads(Path(tmp).read_text(encoding='utf-8'))
        token = data.get('refresh_token') or data.get('token') or data.get('RefreshToken')
        if not token:
            raise RuntimeError('refresh token missing from gog export')
        return str(token)
    finally:
        try:
            os.remove(tmp)
        except FileNotFoundError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')

def _google_access_token(account: str) -> str:
    creds = json.loads(GOG_CREDS().read_text(encoding='utf-8'))
    client = creds.get('installed') or creds.get('web') or creds
    body = urllib.parse.urlencode({'client_id': client['client_id'], 'client_secret': client['client_secret'], 'refresh_token': _export_gog_refresh_token(account), 'grant_type': 'refresh_token'}).encode('utf-8')
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=body, method='POST')
    with urllib.request.urlopen(req, timeout=60) as resp:
        return str(json.loads(resp.read().decode('utf-8'))['access_token'])

def _google_api_json(url: str, *, token: str, method: str='GET', body: Optional[dict[str, Any]]=None, timeout: int=120) -> dict[str, Any]:
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json', **({'Content-Type': 'application/json'} if data is not None else {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Google API HTTP {exc.code}: {detail[:1000]}') from exc

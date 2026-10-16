#!/usr/bin/env python3
"""Audit PD One dangerous-command approvals and propose safe wrapper gaps.

Reads the active PD One Hermes profile session DB and reports actual terminal /
execute_code tool outputs that were blocked, approved, or auto-approved by the
approval guard. This is read-only and intentionally uses sqlite/json only.
"""
from __future__ import annotations

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
import os
import argparse
import collections
import datetime as dt
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

def DEFAULT_DB():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/state.db'))

def DEFAULT_REGISTRY():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/capabilities/registry.yaml'))

def utc_ts(days: int) -> float:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).timestamp()

def load_tool_call_map(con: sqlite3.Connection, since: float) -> dict[str, dict[str, Any]]:
    callmap: dict[str, dict[str, Any]] = {}
    for row in con.execute("select id, session_id, tool_calls from messages where timestamp >= ? and tool_calls is not null and tool_calls != ''", (since,)):
        try:
            calls = json.loads(row['tool_calls'])
        except Exception:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            continue
        for call in calls or []:
            cid = call.get('id') or call.get('call_id')
            fn = call.get('function') or {}
            if cid:
                callmap[cid] = {'assistant_msg_id': row['id'], 'session_id': row['session_id'], 'name': fn.get('name'), 'args': fn.get('arguments') or ''}
    return callmap

def recover_command(args: str) -> str:
    if not args:
        return ''
    try:
        data = json.loads(args)
        return data.get('command') or data.get('code') or json.dumps(data, ensure_ascii=False)[:2000]
    except Exception:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return args[:2000]

def redact(text: str) -> str:
    text = re.sub('(?i)(token|password|secret|api[_-]?key|authorization)\\s*[:=]\\s*[^\\s;]{6,}', '\\1=[REDACTED]', text)
    text = re.sub('(?i)(Bearer\\s+)[A-Za-z0-9._~+/=-]{8,}', '\\1[REDACTED]', text)
    return text

def _looks_like_mattermost_channel_setup(command: str) -> bool:
    text = command.lower()
    return any((marker in text for marker in ('item master data', 'item-master-data-requests', '品號資料申請'))) and any((marker in text for marker in ('name_chars', 'display_name_chars', 'purpose_chars', 'purpose_utf8_bytes', 'len(name)', 'len(display_name)', 'len(purpose)', 'lengths')))

def _looks_like_mattermost_channel_activity_summary(command: str) -> bool:
    text = command.lower()
    return 'mattermost' in text and any((marker in text for marker in ('activity summary', 'participant summary', 'post summary', 'posts_by_user'))) and any((marker in text for marker in ('/api/v4/posts', 'channel_id', 'user_id')))

def _looks_like_mattermost_channel_lookup(command: str) -> bool:
    text = command.lower()
    return any((marker in text for marker in ('mattermost_url', 'mattermost_bot_token', 'mm_bot_token'))) and '/api/v4/users/me' in text and ('/api/v4/teams/name/' in text) and ("/api/v4/teams/{team['id']}/channels/name/" in text)

def _looks_like_mattermost_channel_post_audit(command: str) -> bool:
    text = command.lower()
    return any((marker in text for marker in ('mattermost_url', 'mattermost_bot_token', 'mm_bot_token'))) and '/api/v4/channels/' in text and ('/posts' in text) and ('include_deleted' in text) and any((marker in text for marker in ('timedelta(days=7)', 'cutoff_ms', 'cutoff.timestamp', 'page in range')))

def _looks_like_admin_alert_source_audit(command: str) -> bool:
    text = command.lower()
    channel = site_text('PDONE_ADMIN_ALERT_CHANNEL_ID')
    return bool(channel) and channel in text and 'search_files' in text and ('read_file' in text) and ('*.py' in text) and any((marker in text for marker in ('ensure_pd_one_admin_mention', 'send_hermes_message'))) and any((marker in text for marker in ('api/v4/posts', 'openclaw_send', 'literal_mention')))

def _looks_like_google_drive_parent_chain(command: str) -> bool:
    text = command.lower()
    admin = site_text('PDONE_EMAIL_ADMIN')
    return 'gog drive get' in text and 'parents' in text and any((marker in text for marker in ('for _ in range', 'while', 'chain.append', 'mimetype'))) and bool(admin) and admin in text

def _looks_like_google_group_owner_enforcement(command: str) -> bool:
    text = (command or '').lower()
    gmail = site_text('PDONE_EMAIL_ANDYLIN_GMAIL')
    group_mail = site_text('PDONE_EMAIL_PRO_DESIGN_GROUP_TW_GMAIL')
    return bool(gmail) and gmail in text and bool(group_mail) and group_mail in text and ('owner' in text) and ('group' in text) and any((marker in text for marker in ('admin sdk', 'gog admin', 'directory/v1', 'admin.googleapis.com')))

def _looks_like_google_drive_search_files(command: str) -> bool:
    text = command.lower()
    admin = site_text('PDONE_EMAIL_ADMIN')
    return 'gog drive search' in text and '--raw-query' in text and ('--parent' in text or ' in parents' in text) and ('application/vnd.ms-excel' in text) and ('modifiedtime >=' in text) and bool(admin) and admin in text and any((marker in text for marker in ('name_contains', '品號資料申請表', 'eligible_count', 'modifiedtime')))

def _looks_like_sheets_get_range(command: str) -> bool:
    """Recognize live Sheets range reads via sheets_safe_ops.py get or gog sheets get."""
    text = (command or '').lower()
    if any((marker in text for marker in ('batch-update', 'header-update-row', 'sheets_safe_ops.py append', 'gog sheets append', 'gog sheets batch-update', 'gog drive '))):
        return False
    if _looks_like_cached_sheet_json_search(command):
        return False
    quoted = text.replace("'", '"')
    helper_get = 'sheets_safe_ops.py' in text and '"get"' in quoted and any((marker in text for marker in ('subprocess', 'subprocess.run', '--gog-bin', '--out')))
    raw_gog_get = 'gog sheets get' in text
    argv_gog_get = any((marker in text for marker in ('subprocess', 'subprocess.run'))) and any((marker in text for marker in ('/bin/gog', 'gog =', 'gog='))) and ('"sheets"' in quoted) and ('"get"' in quoted) and any((marker in text for marker in ('--render', 'formula', '--no-input', 'sid =', 'sid=', 'spreadsheet', '!')))
    return helper_get or raw_gog_get or argv_gog_get

def _looks_like_appsheet_incident_morning_briefing_qa(command: str) -> bool:
    text = command.lower()
    return any((marker in text for marker in ('send_appsheet_incident_morning_briefing.py', 'run_scheduled_morning_briefing.py'))) and any((marker in text for marker in ('add_dashboard_link_near_top', 'split_at_intelligent_boundaries', 'split_once_at_intelligent_boundary', 'mattermost_safe_text_limit', 'briefing helper qa')))

def _looks_like_timezone_snapshot(command: str) -> bool:
    text = command.lower()
    return 'datetime.now' in text and 'timezone.utc' in text and any((marker in text for marker in ('asia/taipei', 'timedelta(hours=8)', 'zoneinfo')))

def _looks_like_protected_portal_origin_probe(command: str) -> bool:
    text = (command or '').lower()
    return '127.0.0.1:8766' in text and 'cf-access-authenticated-user-email' in text and any((marker in text for marker in ('urllib.request', 'urlopen', 'urllib.error'))) and text_excludes_configured_hosts(text) and text_excludes_configured_hosts(text)

def _looks_like_timestamp_to_epoch(command: str) -> bool:
    text = command.lower().replace(' ', '')
    return 'datetime.fromisoformat' in text and '.timestamp()' in text and any((marker in text for marker in ('*1000', '*1000.0', 'epoch_milliseconds', 'epoch_ms')))

def _looks_like_epoch_milliseconds_to_iso(command: str) -> bool:
    text = command.lower().replace(' ', '')
    return 'datetime.fromtimestamp' in text and '/1000' in text and ('timezone.utc' in text) and ('isoformat()' in text)

def _looks_like_sheets_serial_column_convert(command: str) -> bool:
    text = command.lower()
    compact = text.replace(' ', '')
    if any((marker in compact for marker in ('datetime.now', 'fromisoformat', 'fromtimestamp'))):
        return False
    serial_shape = ('date(1899,12,30)' in compact or '1899-12-30' in compact) and 'timedelta' in compact and ('days=' in compact)
    column_shape = 'n*26' in compact and 'ord(' in compact and ('-64' in compact) or 'col_to_num' in compact
    return serial_shape or column_shape

def _looks_like_disk_space_summary(command: str) -> bool:
    text = command.lower().replace(' ', '')
    return 'df-b1' in text and '--output=size,used,avail,pcent' in text and any((marker in text for marker in ('avail_gib', 'avail_pct', 'after_low_risk', 'after_low_plus_medium')))

def _looks_like_local_process_listener_inspect(command: str) -> bool:
    text = (command or '').lower()
    if any((marker in text for marker in ('pd-neo-ollama', ':11434', 'honcho-pd-neo', 'kill ', 'pkill', 'killall'))):
        return False
    has_ps = 'ps -p' in text and any((marker in text for marker in ('etime', 'pid,etime', '-o pid')))
    has_ss = 'ss -' in text and 'ltnp' in text
    has_allowlisted_port = any((port in text for port in (':8766', ':8646', ':8765', "'8766'", "'8646'", "'8765'")))
    if has_ss and has_allowlisted_port:
        return True
    return bool(has_ps and has_ss)

def _looks_like_user_process_snapshot(command: str) -> bool:
    text = (command or '').lower()
    if any((marker in text for marker in ('kill ', 'kill(', 'pkill', 'killall', 'os.kill', 'signal.'))):
        return False
    normalized = re.sub('[\'\\",\\s]+', ' ', text)
    if 'ps -p' in normalized or ('ss -' in normalized and 'ltnp' in normalized):
        return False
    has_user_ps = 'ps -u prodesign' in normalized or 'ps -u' in normalized
    has_cols = 'pid' in normalized and 'etime' in normalized and any((marker in normalized for marker in ('cmd', 'args')))
    return has_user_ps and has_cols

def _looks_like_mixed_host_terminal_inspect(command: str) -> bool:
    """Fail-closed mixed date/X11/ps-p/systemd/ls terminal loops; not a typed wrapper."""
    text = (command or '').lower()
    if _looks_like_local_process_listener_inspect(command) or _looks_like_user_process_snapshot(command):
        return False
    if any((marker in text for marker in ('kill ', 'kill(', 'pkill', 'killall', 'os.kill', 'signal.'))):
        return False
    has_terminal = 'hermes_tools' in text and 'terminal' in text
    has_x11 = '/tmp/.x11-unix' in text
    has_ps_p = 'ps -p' in text
    has_systemd_ls = '.config/systemd/user' in text or 'profiles/pdone/systemd' in text
    has_date = 'date -u' in text
    has_profile_ls = 'profiles/pdone' in text and 'head' in text and ('ls ' in text)
    mixed_count = sum((has_x11, has_ps_p, has_systemd_ls, has_date, has_profile_ls))
    return bool(has_terminal and mixed_count >= 3)

def _looks_like_text_metrics(command: str) -> bool:
    text = (command or '').lower()
    return 'len(' in text and any((marker in text for marker in ('characters_including_punctuation', 'character_count', 'char_count', '字數', '字元數'))) and (not any((marker in text for marker in ('read_text(', 'open(', 'write_text(', 'write_bytes('))))

def _looks_like_cached_sheet_json_search(command: str) -> bool:
    text = (command or '').lower()
    if any((marker in text for marker in ('inspect.json', 'structural-summary.json', '/tmp/hermes-results', 'html.escape', 'official_preflight'))):
        return False
    json_touch = any((marker in text for marker in ('json.load(', 'json.loads(', 'json.dumps(')))
    values = any((marker in text for marker in ('["values"]', "['values']", '.get("values"', ".get('values'")))
    extract_records = 'extract_records' in text and any((name in text for name in ('appsheet-history.json', 'appsheet-current.json', 'appsheet-send-list.json', 'appsheet-requests.json')))
    path_ok = '.json' in text and any((marker in text for marker in ('/tmp/', '/cache/', '/artifacts/', 'profiles/pdone/', 'mold-repair-sheet')))
    search_ok = any((marker in text for marker in ('re.search', 're.compile', 'match_count', 'colmap', 'headers', 'dump_hits', 'header_row', '維修單號', '模具編號', '品名')))
    count_ok = '.join(' in text and ' in t' in text
    return json_touch and path_ok and (values or extract_records) and (search_ok or count_ok)

def _looks_like_cached_dest_rest_count(command: str) -> bool:
    text = (command or '').lower()
    if any((marker in text for marker in ('inspect.json', 'structural-summary.json', '/tmp/hermes-results', 'html.escape', 'official_preflight', '維修單號', '模具編號', 'extract_records'))):
        return False
    json_touch = any((marker in text for marker in ('json.load(', 'json.loads(')))
    values = any((marker in text for marker in ('["values"]', "['values']", '.get("values"', ".get('values'")))
    path_ok = '.json' in text and any((marker in text for marker in ('worker-scheduling', 'profiles/pdone/tmp', '/tmp/', '/cache/', '/artifacts/')))
    rest_shape = any((marker in text for marker in ('r[6:]', 'days = r[', 'days=r[', 'rest_days', 'rest count', 'marked ='))) or ('"v"' in text and any((marker in text for marker in ('休息', 'centeno', '森特諾', '來斯特', '雷恩', 'last days'))))
    return json_touch and values and path_ok and rest_shape

def _looks_like_yammer_archive_search(command: str) -> bool:
    """Recognize raw Yammer archive JSONL scans that belong on the scoped search wrapper."""
    text = (command or '').lower()
    archive = any((marker in text for marker in ('messages.jsonl', 'yammer-migration', 'yammer_archive', 'archive/messages', 'yammer-archive-search')))
    scan = any((marker in text for marker in ('json.loads(line', 'for line in', '.jsonl')))
    return archive and scan

def _has_pip_token(command: str) -> bool:
    """True for a pip token, not the letters pip inside pipe."""
    return re.search('(?<![a-z0-9_])pip(?![a-z0-9_])', (command or '').lower()) is not None

def _looks_like_pdone_dependency_install(command: str) -> bool:
    """Classify package-manager mutation/setup into a gated manual path."""
    text = command.lower()
    python_install = 'uv' in text and _has_pip_token(text) and ('install' in text) and any((marker in text for marker in ('/profiles/pdone/', 'releases/pdone-current', '--python')))
    apt_install = any((marker in text for marker in ('apt-get', 'apt '))) and any((marker in text for marker in (' install', ' download'))) and any((marker in text for marker in ('--simulate', '--download-only', 'apt-get download', 'apt download')))
    return python_install or apt_install

def _looks_like_item_number_render_qa(command: str) -> bool:
    text = command.lower()
    return 'item-number-workflow' in text and 'qa-artifacts-final' in text and ('render-results.json' in text or 'production_qualified' in text or 'certify-render' in text or ('golden_comparison_sha256' in text) or ('office_environment_id' in text) or ('certified_at' in text) or ('page_count' in text) or ('soffice' in text and 'pdftoppm' in text and ('pdfinfo' in text)))

def _looks_like_item_number_local_fixture_copy(command: str) -> bool:
    text = command.lower()
    return 'item-number-workflow' in text and 'qa-artifacts-final/special' in text and ('item-number-local-lo' in text) and ('shutil.copyfile' in text) and ('.xlsx' in text)

def _looks_like_item_number_local_lo_builder(command: str) -> bool:
    """Recognize the legacy local-LibreOffice QA builder or its truncated CJK render."""
    text = command.lower()
    if 'item-number-workflow' not in text:
        return False
    builder_path = 'build_local_libreoffice_qa.py' in text and (all((marker in text for marker in ('migrate_xls_to_xlsx', 'compile_signed_xlsx', 'qa-artifacts-local-lo'))) or 'runpy.run_path' in text)
    inline_cjk_render = 'qa-artifacts-local-lo' in text and '.xlsx' in text and any((marker in text for marker in ('libreoffice', 'soffice'))) and ('pdfinfo' in text) and ('pdftoppm' in text) and any((marker in text for marker in ('renders-cjk', 'libreoffice-cjk-fontconfig', 'qa-artifacts-local-lo-v2'))) and any((marker in text for marker in ('procurement', 'production', 'special')))
    return builder_path or inline_cjk_render

def _looks_like_ecrn_approval_pilot_status(command: str) -> bool:
    text = command.lower()
    return any((marker in text for marker in ('ecrn-approval-pilot.json', 'state/ecrn-approval-pilot.json', 'ecrn_approval_pilot.py'))) and any((marker in text for marker in ("stage != 'complete'", 'stage != "complete"', 'preview_pdfs', 'signed_document_posted', 'deletion_verification_pending', 'deletion_last_readback', 'routing_checked_from_form', 'all_required_complete_posted')))

def _looks_like_ecrn_channel_header_test(command: str) -> bool:
    text = command.lower()
    return 'test_ecrn_channel_header.py' in text and 'pytest' in text and any((marker in text for marker in ('channel_header', 'ecrn', 'update_daily_ecrn_channel_header', 'header-only')))

def _looks_like_ecrn_approval_pilot_check(command: str) -> bool:
    text = command.lower()
    return 'ecrn_approval_pilot.py' in text and 'test_ecrn_' in text and any((marker in text for marker in ('pytest', 'py_compile', 'ruff'))) and any((marker in text for marker in ('hermes-backup', 'shutil.copyfile', 'run(cmd', 'subprocess.run')))

def _looks_like_hermes_backup_sync_copy(command: str) -> bool:
    text = command.lower()
    return resolve_configured_path('~/.hermes/profiles/pdone/legacy-openclaw/workspace/tools') in text and resolve_configured_path('~/hermes-backup/hermes/profiles/pdone/legacy-openclaw/workspace/tools') in text and any((marker in text for marker in ('hermes_tools', 'read_file(', 'write_file('))) and any((marker in text for marker in ('rels=', 'rels =', 'for rel in rels', 'copied=')))

def _looks_like_docx_exact_text_patch(command: str) -> bool:
    text = command.lower()
    common = 'docx' in text and 'zipfile' in text and any((marker in text for marker in ('cache/documents', '/profiles/pdone/artifacts', '/profiles/pdone/tmp')))
    document_xml = any((marker in text for marker in ('word/document.xml', "'word'/'document.xml'", '"word"/"document.xml"', 'document.xml')))
    replacement_map = any((marker in text for marker in ('repls', 'replacements', 'repl={', 'repl ={', 'for old,new', 'for old, new')))
    replacement_loop = document_xml and replacement_map and ('.replace(' in text) and any((marker in text for marker in ('writestr', 'zipfile(tmp', 'os.replace', '.tmp')))
    bilingual_named_replacements = all((marker in text for marker in ('old_zh', 'old_en', 'new_zh', 'new_en'))) and any((marker in text for marker in ('.replace(', 'writestr', 'os.replace', 'xml.sax.saxutils', 'w:br')))
    minidom_repl_prefix = 'minidom' in text and replacement_map and document_xml and any((marker in text for marker in ('getelementsbytagnamens', 'ptext('))) and any((marker in text for marker in ('extractall', 'temporarydirectory'))) and (not any((marker in text for marker in ('pagebreakbefore', 'keepnext', 'tblgrid'))))
    return common and (replacement_loop or bilingual_named_replacements or minidom_repl_prefix)

def _looks_like_ecrn_docx_unique_text_patch(command: str) -> bool:
    text = command.lower()
    return 'docx' in text and 'document(' in text and ('old_line' in text) and ('new_line' in text) and ('doc.tables' in text) and ('cell.paragraphs' in text) and any((marker in text for marker in ('artifacts/ecrn', '電子簽核', 'ecrn')))

def _looks_like_docx_table_structure(command: str) -> bool:
    text = command.lower()
    return 'zipfile' in text and 'word/document.xml' in text and any((marker in text for marker in ('minidom', 'getelementsbytagnamens'))) and (sum((marker in text for marker in ('tblgrid', 'gridcol', "'tbl'", "'tr'", "'tc'"))) >= 3) and any((marker in text for marker in ('.docx', 'artifacts/typhoon'))) and (not any((marker in text for marker in ('.write(', '.writestr(', '.replace('))))

def _looks_like_docx_body_xml_inspection(command: str) -> bool:
    text = command.lower()
    return 'zipfile' in text and 'word/document.xml' in text and any((marker in text for marker in ('elementtree', 'et.fromstring', 'etree.fromstring', 'fromstring('))) and any((marker in text for marker in ('.//w:p', "findall('.//w:p'", 'findall(".//w:p"', "xpath('.//w:p'", 'xpath(".//w:p"'))) and any((marker in text for marker in ('et.tostring', 'etree.tostring', 'elementtree.tostring'))) and any((marker in text for marker in ('.docx', 'cache/documents'))) and (not any((marker in text for marker in ('.write(', '.writestr(', '.replace('))))

def _looks_like_docx_layout_patch(command: str) -> bool:
    text = command.lower()
    return 'zipfile' in text and 'word/document.xml' in text and any((marker in text for marker in ('minidom', 'getelementsbytagnamens'))) and any((marker in text for marker in ('pagebreakbefore', 'keepnext', 'keep_with_next', 'page_break_before'))) and any((marker in text for marker in ('ppr', 'createelementns', 'createelementn'))) and any((marker in text for marker in ('.docx', 'artifacts/typhoon')))

def _looks_like_equipment_workbook_builder(command: str) -> bool:
    text = command.lower()
    source_markers = ('doc_fafbca05b172', 'doc_d33fde0d9970', 'doc_01691e27f673', '良器現有射出機履歷', '色母機設備盤點量測參數', '機台設備總覽表')
    return 'openpyxl' in text and 'load_workbook' in text and (sum((marker in text for marker in source_markers)) >= 2) and any((marker in text for marker in ('設備管理', 'equipment_specifications', 'src_inj', 'src_ov', 'out_dir', 'masterbatch_history_rows', "'injection'", "'masterbatch'", "'overview'"))) and any((marker in text for marker in ('workbook', 'patternfill', 'tablestyleinfo', 'table', 'freeze_panes', 'masterbatch_history_rows', 'report')))

def _looks_like_xlsx_workbook_inspection(command: str) -> bool:
    text = command.lower()
    if any((marker in text for marker in ('item-number-workflow', 'item_number_xlsx_compiler', 'sip_threads_pd'))):
        return False
    return 'openpyxl' in text and 'load_workbook' in text and any((marker in text for marker in ('.xlsx', '.xlsm', 'max_row', 'max_column', '.worksheets', 'sheetnames'))) and any((marker in text for marker in ('path(', 'cache/documents', 'read_only', 'workbook')))

def _looks_like_office_visual_qa(command: str) -> bool:
    text = command.lower()
    return ('office_visual_qa.py' in text or 'visual-office-qa' in text) and '--out-dir' in text and any((marker in text for marker in ('.docx', '.pptx')))

def _looks_like_office_doc_build(command: str) -> bool:
    text = command.lower()
    json_spec_build = any((marker in text for marker in ('json.loads', 'json.load('))) and 'html' in text and ('.docx' in text) and any((marker in text for marker in ('read_file(', 'hermes_tools.read_file', 'open(', 'spec_path'))) and any((marker in text for marker in ('write_file(', 'docx_path', 'document('))) and any((marker in text for marker in ('artifacts/documents', 'cache/documents', '/profiles/pdone/')))
    company_announcement_template_build = 'pro-design-company-announcement-template.docx' in text and 'replacements' in text and ('word/document.xml' in text) and any((marker in text for marker in ('zipfile', 'zipfile.zipfile', 'minidom'))) and any((marker in text for marker in ('artifacts/typhoon', 'workspace-employee/artifacts', 'workspace-employee/out')))
    return json_spec_build or company_announcement_template_build

def _looks_like_json_html_artifact_build(command: str) -> bool:
    text = command.lower()
    return any((marker in text for marker in ('json.loads', 'json.load(', 'read_text('))) and 'paragraphs' in text and ('html.escape' in text) and any((marker in text for marker in ('.html', '.htm'))) and any((marker in text for marker in ('write_text(', 'write_file(', 'open(', 'out='))) and any((marker in text for marker in ('artifacts/', 'cache/documents', '/profiles/pdone/')))

def _looks_like_google_docs_inspect_receipt_summary(command: str) -> bool:
    text = (command or '').lower()
    if _looks_like_json_html_artifact_build(command):
        return False
    json_load = any((marker in text for marker in ('json.load(', 'json.loads(', 'json.load(open(')))
    if not json_load or '.json' not in text:
        return False
    if 'google-docs-document-ops' not in text:
        return False
    if 'headings' not in text:
        return False
    return any((marker in text for marker in ('heading_count', 'start_index', 'inspect.json', '-inspect.json', "h['text']", 'h["text"]')))

def _looks_like_json_artifact_inspect(command: str) -> bool:
    text = command.lower()
    if _looks_like_json_html_artifact_build(command):
        return False
    if _looks_like_google_docs_inspect_receipt_summary(command):
        return False
    if _looks_like_cached_sheet_json_search(command):
        return False
    if _looks_like_hermes_result_messages_summary(command):
        return False
    if _looks_like_office_doc_build(command):
        return False
    if _looks_like_step_inspect_json_summary(command) or _looks_like_step_geometry_inspect_json_summary(command):
        return False
    if 'structural-summary.json' in text:
        return False
    json_load = any((marker in text for marker in ('json.load(', 'json.loads(', 'json.load(open(')))
    if not json_load or '.json' not in text:
        return False
    if not any((marker in text for marker in ('os.stat', '.stat()', 'st_size'))):
        return False
    structure_hits = sum((marker in text for marker in ('top type', 'print("keys"', "print('keys'", 'list(data.keys())', 'list(data.keys()', 'sample0', 'type(data)', 'isinstance(data, dict)', 'isinstance(data,dict)')))
    if structure_hits < 2:
        return False
    if any((marker in text for marker in ('write_text(', 'write_bytes(', 'json.dump(', 'html.escape'))):
        return False
    return True

def _looks_like_local_file_search(command: str) -> bool:
    if _looks_like_admin_alert_source_audit(command):
        return False
    if _looks_like_json_artifact_inspect(command):
        return False
    if _looks_like_hermes_result_messages_summary(command):
        return False
    if _looks_like_cached_sheet_json_search(command):
        return False
    text = (command or '').lower()
    if 'search_files' not in text or 'read_file' not in text:
        return False
    if 'hermes_tools' not in text and 'from hermes_tools import' not in text:
        return False
    return any((marker in text for marker in ('target="files"', "target='files'", 'target=files', 'target = "files"', "target = 'files'")))

def _looks_like_office_html_to_docx(command: str) -> bool:
    text = command.lower()
    return ('libreoffice' in text or 'soffice' in text) and '--convert-to' in text and ('docx' in text) and any((marker in text for marker in ('.html', '.htm', 'html_path'))) and any((marker in text for marker in ('--outdir', 'out_dir', 'docx_path'))) and any((marker in text for marker in ('artifacts/documents', '/profiles/pdone/', 'cache/documents')))

def _looks_like_office_deb_contents(command: str) -> bool:
    text = command.lower()
    return 'dpkg-deb' in text and '--contents' in text and ('.deb' in text) and ('apt-debs' in text) and any((marker in text for marker in ('registry', '.xcd', 'calc')))

def _looks_like_docx_targeted_inspection(command: str) -> bool:
    text = command.lower()
    structure_markers = ('doc.tables[', 'doc.tables', '.rows[', 'table.rows', '.cells[', '.paragraphs[', '.runs')
    return 'docx' in text and 'document(' in text and any((marker in text for marker in ('.docx', 'cache/documents', 'from docx import document'))) and (sum((marker in text for marker in structure_markers)) >= 2)

def _looks_like_docx_table_search(command: str) -> bool:
    text = command.lower()
    return ('from docx import document' in text or 'python-docx' in text) and 'doc.tables' in text and ('table.rows' in text) and any((marker in text for marker in ('cell.text', 'cell.paragraphs'))) and any((marker in text for marker in ('cell.tables', 'nested_tables', 'found.append', 'matches.append', 'seen_cells')))

def _looks_like_docx_xml_text_extraction(command: str) -> bool:
    text = command.lower()
    return 'zipfile' in text and 'word/document.xml' in text and any((marker in text for marker in ('minidom', 'getelementsbytagnamens', 'w:t'))) and any((marker in text for marker in ('.docx', 'company-announcement-template'))) and (not any((marker in text for marker in ('.write(', '.writestr(', '.replace(', '.3mf'))))

def _looks_like_pptx_xml_inspect(command: str) -> bool:
    text = command.lower()
    if any((marker in text for marker in ('.write(', '.writestr(', '.extract(', '.replace(', '.3mf'))):
        return False
    return 'zipfile' in text and '.pptx' in text and any((marker in text for marker in ('drawingml', 'presentationml', 'a:t', '<a:t', 'ppt/slides', 'ppt/presentation.xml', 'namelist', 'slide_xml_count'))) and any((marker in text for marker in ('elementtree', 'xml.etree', 'et.fromstring', 'minidom', 'getelementsbytagnamens', 'w:t', 'a:t', 'namelist()')))
_PPTX_OOXML_NAMED_MEMBER_RE = re.compile('ppt/(?:slides/slide|notesslides/notesslide|diagrams/data|charts/chart)\\d+\\.xml')

def _looks_like_pptx_ooxml_text_inspect(command: str) -> bool:
    text = command.lower()
    if any((marker in text for marker in ('.write(', '.writestr(', '.extract(', '.replace(', '.3mf'))):
        return False
    if _PPTX_OOXML_NAMED_MEMBER_RE.search(text) is None:
        return False
    return 'zipfile' in text and '.pptx' in text and any((marker in text for marker in ('a:t', '<a:t', 're.finditer', 'findall', '== "t"', "== 't'", 'root.iter', '.iter()', 'et.fromstring', 'elementtree', 'xml.etree')))

def _looks_like_office_docprops_inspect(command: str) -> bool:
    text = (command or '').lower()
    if any((marker in text for marker in ('.write(', '.writestr(', '.3mf', 'slic3r'))):
        return False
    if any((marker in text for marker in ('word/document.xml', 'ppt/slides', 'ppt/presentation.xml', 'drawingml', 'a:t', '<a:t'))):
        return False
    office_suffix = any((marker in text for marker in ('.pptx', '.pptm', '.potx', '.docx', '.docm', '.xlsx', '.xlsm', '.xltx')))
    docprops_member = 'docprops' in text and 'core.xml' in text or ('docprops' in text and 'app.xml' in text)
    return 'zipfile' in text and office_suffix and docprops_member

def _looks_like_pptx_from_template(command: str) -> bool:
    text = command.lower()
    in_roots = any((marker in text for marker in ('cache/documents', '/profiles/pdone/artifacts', '/profiles/pdone/tmp', 'workspace-employee/out', '/profiles/pdone/templates')))
    writes = any((marker in text for marker in ('prs.save', '.save(', 'add_slide', 'zipfile')))
    template_marker = any((marker in text for marker in ('.potx', 'slide_layouts', 'load_firm_presentation', 'slidemaster', 'apply_template')))
    return in_roots and writes and template_marker and any((marker in text for marker in ('from pptx import', 'presentation(', '.pptx')))

def _looks_like_pptx_inspect(command: str) -> bool:
    text = command.lower()
    if any((marker in text for marker in ('prs.save', 'add_slide', 'add_picture', '.save('))):
        return False
    return ('from pptx import presentation' in text or 'presentation(' in text) and any((marker in text for marker in ('.pptx', 'cache/documents'))) and any((marker in text for marker in ('mso_shape_type', 'has_text_frame', 'text_frame'))) and any((marker in text for marker in ('slide_width', 'slide_height', 'group', 'prs.slides')))

def _looks_like_office_docprops_inspect(command: str) -> bool:
    text = command.lower()
    if any((marker in text for marker in ('.write(', '.writestr(', '.3mf', 'slic3r'))):
        return False
    if any((marker in text for marker in ('word/document.xml', 'ppt/slides', 'ppt/presentation.xml', 'drawingml', 'a:t', '<a:t'))):
        return False
    office_suffix = any((marker in text for marker in ('.pptx', '.pptm', '.potx', '.docx', '.docm', '.xlsx', '.xlsm', '.xltx')))
    docprops_member = 'docprops' in text and 'core.xml' in text or ('docprops' in text and 'app.xml' in text)
    return 'zipfile' in text and office_suffix and docprops_member

def _looks_like_pptx_exact_text_patch(command: str) -> bool:
    text = command.lower()
    common = 'zipfile' in text and '.pptx' in text and any((marker in text for marker in ('workspace-employee/out', 'cache/documents', '/profiles/pdone/artifacts', '/profiles/pdone/tmp', 'legacy-openclaw/workspace-employee')))
    replacement_map = any((marker in text for marker in ('fixes', 'repls', 'replacements', 'pairs =', 'pairs=[', 'map = {', 'map={', 'for old, new', 'for old,new')))
    replacement_loop = replacement_map and '.replace(' in text and any((marker in text for marker in ('endswith(".xml")', "endswith('.xml')", 'ppt/slides', 'a:t', 'filename.endswith'))) and any((marker in text for marker in ('zipfile(tmp', 'with_suffix', '.tmp', 'zipinfo', 'os.replace', 'shutil')))
    truncated_at_map = replacement_map and any((marker in text for marker in ('a:t', '<a:t', 'inner-text', 'exact xml', 'translation-compare', 'keep brand'))) and any((marker in text for marker in ('elementtree', 'xml.etree', 'xml.sax.saxutils', 'escape('))) and any((marker in text for marker in ('dst =', 'dst=', 'out_dir', 'workspace-employee/out')))
    return common and (replacement_loop or truncated_at_map)

def _looks_like_admin_approval_kanban_status(command: str) -> bool:
    text = command.lower()
    ticketish = 'pdapp-' in text
    mapping_or_result = 'admin-approval-kanban/mappings' in text or 'admin-approval-kanban/results' in text or ('admin-approval-kanban' in text and any((marker in text for marker in ('mapping_exists', 'result_exists', 'mappings/', 'results/'))))
    workspace = 'kanban/boards/pdapp-approvals' in text
    return ticketish and (mapping_or_result or workspace)

def _looks_like_hermes_result_messages_summary(command: str) -> bool:
    text = command.lower()
    return '/tmp/hermes-results' in text and any((marker in text for marker in ['json.load(', 'json.loads(', 'json.load(open('])) and any((marker in text for marker in ["get('messages'", 'get("messages")', 'messages =', 'messages='])) and any((marker in text for marker in ["m.get('role'", 'm.get("role")', "m.get('content'", 'm.get("content")', 'content_summary', 'message_count'])) and any((marker in text for marker in ['tool_name', "m.get('name'", 'm.get("name")', 'isinstance(content, list)', 'isinstance(content,list)']))

def _looks_like_python_package_dry_run(command: str) -> bool:
    text = command.lower()
    return _has_pip_token(text) and 'install' in text and ('--dry-run' in text) and ('--python' in text) and any((marker in text for marker in ('subprocess.run', 'cmd=[', 'cmd = [')))

def _looks_like_python_media_stack_status(command: str) -> bool:
    text = command.lower()
    media_markers = ('cv2', 'pil', 'numpy', 'av', 'moviepy', 'imageio', 'imageio_ffmpeg', 'scipy')
    return 'importlib' in text and 'find_spec' in text and (sum((marker in text for marker in media_markers)) >= 4)

def _looks_like_python_cad_stack_status(command: str) -> bool:
    text = command.lower()
    cad_markers = ('cadquery', 'ocp', 'occ.core', 'freecad', 'build123d', 'ezdxf', 'trimesh', 'gmsh')
    return 'importlib' in text and any((marker in text for marker in ('import_module', 'find_spec'))) and (sum((marker in text for marker in cad_markers)) >= 3)

def _looks_like_legacy_xls_hash(command: str) -> bool:
    text = (command or '').lower()
    return 'hashlib.sha256' in text and 'pathlib.path' in text and ('.read_bytes()' in text) and ('.stat().st_size' in text) and ('.xls' in text)

def _looks_like_artifact_base64_encode(command: str) -> bool:
    text = (command or '').lower()
    return 'base64' in text and 'b64encode' in text and any((marker in text for marker in ('open(', '.read_bytes()', '.read()'))) and any((marker in text for marker in ('.svg', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.pdf'))) and any((marker in text for marker in ('/artifacts/', '/tmp/', '/cache/documents/', '/workspace-employee/exports/', '/workspace-employee/out/')))

def _looks_like_local_artifact_copy(command: str) -> bool:
    text = (command or '').lower()
    return any((marker in text for marker in ('shutil.copy2', 'shutil.copyfile'))) and 'legacy-openclaw/workspace-employee/artifacts/' in text and ('/profiles/pdone/artifacts/' in text) and any((marker in text for marker in ('.docx', '.xlsx', '.pptx', '.pdf', '.png', '.svg')))

def _looks_like_artifact_identity_inventory(command: str) -> bool:
    text = (command or '').lower()
    if any((marker in text for marker in ('zipfile', 'shutil.copy', 'importlib', 'freecadcmd', 'subprocess'))):
        return False
    return '.glob(' in text and any((marker in text for marker in ('workspace-employee/artifacts', '/profiles/pdone/artifacts/', 'cache/documents'))) and any((marker in text for marker in ('.stat()', 'st_size', '.exists()'))) and any((marker in text for marker in ('read_bytes()[:', 'magic', '.suffix'))) and any((marker in text for marker in ('.3mf', '.png', '.stp', '.step', '.stl')))

def _looks_like_video_frame_sample(command: str) -> bool:
    text = (command or '').lower()
    return 'ffprobe' in text and 'ffmpeg' in text and any((marker in text for marker in ('-show_entries', 'format=duration', 'r_frame_rate'))) and any((marker in text for marker in ('-frames:v', 'frame_1.jpg', 'video-frames'))) and any((marker in text for marker in ('.mp4', '.mov', '.mkv', '.webm'))) and ('/cache/documents/' in text)

def _looks_like_step_geometry_inspect_json_summary(command: str) -> bool:
    text = (command or '').lower()
    if any((marker in text for marker in ('freecadcmd', 'subprocess.run', 'importlib'))):
        return False
    return 'inspect.json' in text and any((marker in text for marker in ('json.loads', 'json.load('))) and any((marker in text for marker in ('summarize_solid', "s['faces']", 's["faces"]', "['faces']", '["faces"]'))) and any((marker in text for marker in ('volume', 'bbox', 'counter'))) and any((marker in text for marker in ('workspace-employee/artifacts', '/artifacts/', 'tmp/step-geometry-inspect', 'slope_from_horizontal', 'unknown edges', 'unknown_edges')))

def _looks_like_step_inspect_json_summary(command: str) -> bool:
    text = (command or '').lower()
    if any((marker in text for marker in ('freecadcmd', '--pass', 'zipfile', 'importlib'))):
        return False
    return 'inspect.json' in text and 'json.loads' in text and ('solids' in text) and any((marker in text for marker in ('slope_from_horizontal_deg', 'brief_face', 'semi_angle_deg', 'cylinder_radii'))) and any((marker in text for marker in ('workspace-employee/artifacts', '/artifacts/', 'tmp/step-geometry-inspect', 'cache/documents')))

def _looks_like_step_geometry_inspect(command: str) -> bool:
    if _looks_like_caller_supplied_freecad_mutation(command):
        return False
    if _looks_like_step_inspect_json_summary(command) or _looks_like_step_geometry_inspect_json_summary(command):
        return True
    text = (command or '').lower()
    freecad_shape = any((marker in text for marker in ('freecadcmd', 'freecadcmd)', 'freecad'))) and '--pass' in text and any((marker in text for marker in ('.stp', '.step'))) and any((marker in text for marker in ('subprocess.run', 'subprocess.popen', 'cmd = [', 'cmd=['))) and any((marker in text for marker in ('inspect_handle.py', 'inspect_step_geometry.py', 'probe_profile.py', 'inspect.json', 'probe.json')))
    copy_shape = any((marker in text for marker in ('shutil.copy2', 'shutil.copyfile'))) and any((marker in text for marker in ('.stp', '.step'))) and ('inspect_handle.py' in text) and ('inspect.json' in text) and ('subprocess' in text) and any((marker in text for marker in ('cache/documents', 'workspace-employee/artifacts')))
    return freecad_shape or copy_shape

def _looks_like_step_printability_json_summary(command: str) -> bool:
    text = (command or '').lower()
    if any((marker in text for marker in ('freecadcmd', 'subprocess.run', 'importlib', 'zipfile'))):
        return False
    return any((marker in text for marker in ('official_preflight.json', 'official_preflight_', 'printability.json', 'analyze.json', 'analysis.json'))) and any((marker in text for marker in ('json.loads', 'json.load('))) and any((marker in text for marker in ('flagged_area_mm2', 'flagged_face_count', 'flagged_triangle_count', 'top_findings', 'error_class'))) and any((marker in text for marker in ('workspace-employee/artifacts', '/artifacts/', 'tmp/step-printability', '3d-printing-step-preflight')))

def _looks_like_caller_supplied_freecad_mutation(command: str) -> bool:
    text = (command or '').lower()
    if not any((marker in text for marker in ('freecadcmd', 'freecadcmd)', 'freecad', 'import part', 'part.shape', 'circ_chamfer', 'tune_angle', 'replace_chead'))):
        return False
    if '.py' not in text:
        return False
    named = any((marker in text for marker in ('rebuild_60chamfer.py', 'rebuild2.py', 'rebuild3.py', 'rebuild4.py', 'rebuild_b.py', 'rebuild_c.py', 'rebuild_d.py', 'rebuild_e.py', 'rev_e.py', 'rev_e2.py', 'rev_f.py', 'rev_f2.py', 'rev_f3.py', 'rebuild_f.py', 'rebuild_g.py', 'rebuild_h.py', 'clip_b.py', 'clip_x.py', 'clip_x2.py', 'clip_chead.py', 'replace_chead.py', 'fuse_test.py', 'measure_rev1.py', 'chamfer_curve.py', 'probe_curve.py', 'chamfer_revolve.py', 'chamfer_revolve2.py', 'chamfer_pipe.py', 'test_pipe.py', 'test_fill_pipe.py', 'test_circ_chamfer.py', 'test_circ_chamfer2.py', 'tune_angle.py', 'tune_angle2.py'))) or 'rebuild_' in text or 'clip_' in text or ('chamfer_revolve' in text) or ('chamfer_pipe' in text) or ('_pipe.py' in text) or ('circ_chamfer' in text) or ('tune_angle' in text) or ('replace_chead' in text)
    write_mutation = 'write_text' in text and '--pass' in text and any((marker in text for marker in ('workspace-employee/artifacts', '/artifacts/', 'cache/documents'))) and any((marker in text for marker in ('.fuse(', 'makebox', 'part.shape', '.common(')))
    return named or write_mutation

def _looks_like_step_printability_analyze(command: str) -> bool:
    if _looks_like_caller_supplied_freecad_mutation(command):
        return False
    if _looks_like_step_printability_json_summary(command):
        return True
    text = (command or '').lower()
    return 'analyze_step_printability.py' in text and any((marker in text for marker in ('.stp', '.step'))) and any((marker in text for marker in ('freecadcmd', 'freecadcmd)', 'freecad', '--pass', 'official_preflight.json', 'json-out', '--json-out'))) and any((marker in text for marker in ('subprocess.run', 'subprocess.popen', 'cmd = [', 'cmd=[', 'shutil.copy2', 'shutil.copyfile'))) and any((marker in text for marker in ('workspace-employee/artifacts', '/artifacts/', 'cache/documents', 'tmp/step-printability-analyze')))

def _looks_like_arbitrary_freecad_script(command: str) -> bool:
    if _looks_like_step_geometry_inspect(command):
        return False
    if _looks_like_caller_supplied_freecad_mutation(command):
        return True
    if _looks_like_step_printability_analyze(command):
        return False
    text = (command or '').lower()
    if any((marker in text for marker in ('inspect_handle.py', 'inspect_step_geometry.py', 'probe_profile.py', 'analyze_step_printability.py'))):
        return False
    if '.py' not in text:
        return False
    truncated_write_mutation = 'import subprocess' in text and '--pass' in text and any((marker in text for marker in ('workspace-employee/artifacts', '/artifacts/', 'cache/documents'))) and any((marker in text for marker in ('write_text', 'fuse_test.py', 'clip_b.py', 'clip_x.py', 'clip_chead.py', 'replace_chead.py', 'test_circ_chamfer.py', 'test_pipe.py', 'test_fill_pipe.py', '_pipe.py', 'circ_chamfer', 'tune_angle.py', 'tune_angle2.py', 'tune_angle'))) and any((marker in text for marker in ('.fuse(', 'makebox', 'part.shape', '.common(')))
    if truncated_write_mutation:
        return True
    if not any((marker in text for marker in ('freecadcmd', 'freecadcmd)', 'freecad'))):
        return False
    classic_launch = '--pass' in text and any((marker in text for marker in ('.stp', '.step'))) and any((marker in text for marker in ('subprocess.run', 'subprocess.popen', 'cmd = [', 'cmd=[')))
    return classic_launch

def _looks_like_3mf_slicer_inspect(command: str) -> bool:
    text = (command or '').lower()
    if 'importlib' in text and any((marker in text for marker in ('import_module', 'find_spec'))) and ('zipfile' not in text):
        return False
    return 'zipfile' in text and '.3mf' in text and any((marker in text for marker in ('cache/documents', '/artifacts/', 'workspace-employee'))) and any((marker in text for marker in ('slic3r', 'slicer_pe', 'metadata/slic3r', 'metadata/thumbnail', 'namelist', 'filament_type', 'layer_height', 'fill_density', 'endswith', '.model', '.config')))

def _looks_like_cad_runtime_status(command: str) -> bool:
    text = (command or '').lower()
    if 'importlib' in text and any((marker in text for marker in ('import_module', 'find_spec'))):
        return False
    runtime = any((marker in text for marker in ('freecadcmd', '/usr/lib/freecad', '/usr/lib/freecad-python3', '/opt/freecad')))
    probe = any((marker in text for marker in ('os.path.exists', 'os.stat', 'os.listdir', 'path.exists', 'oct(os.stat')))
    return runtime and probe

def _looks_like_svg_artifact_inspection(command: str) -> bool:
    text = (command or '').lower()
    return '.svg' in text and any((marker in text for marker in ('xml.etree.elementtree', 'et.parse(', 'et.fromstring('))) and any((marker in text for marker in ('itertext', 'findall(', 'data:image/png;base64', "attrib['y']", 'attrib["y"]'))) and any((marker in text for marker in ('/artifacts/', '/tmp/', '/cache/documents/', '/workspace-employee/exports/', '/workspace-employee/out/')))

def _looks_like_svg_embed_image(command: str) -> bool:
    text = (command or '').lower()
    return 'base64' in text and 'b64encode' in text and ('.svg' in text) and ('tw.prodesign-group.com/img/logo.png' in text) and any((marker in text for marker in ('urlopen', 'urllib.request', 'request('))) and any((marker in text for marker in ('.replace(', '.write_text(', '.write_bytes('))) and ('data:image/png;base64,' in text)

def _looks_like_drive_individual_share(command: str) -> bool:
    text = (command or '').lower()
    return 'gog drive share' in text or 'permissions.create' in text or ('drive.permissions' in text and 'create' in text) or ('gog drive' in text and ' --role ' in text and any((token in text for token in ('writer', 'reader', 'commenter', 'editor'))))

def classify(tool: str, approval: str, error: str, command: str) -> tuple[str, str | None, str]:
    text = ' '.join([approval or '', error or '', command or ''])
    low = text.lower()

    def _pd_phase_1():
        nonlocal _pd_result

        def _pd_phase_2():
            if _looks_like_drive_individual_share(command):
                return _PdReturn(('drive_individual_share_forbidden', 'pd_one_drive_acl_authorize', 'Do not add type=user Drive contributors because an employee asked PD One to edit or view. Authorize with pd_one_drive_acl_authorize / drive-acl-authorize. Never call gog drive share or permissions.create for that grant.'))
            if _looks_like_local_artifact_copy(command):
                return _PdReturn(('local_artifact_copy_execute_code', 'pd_one_local_artifact_copy', 'Use the bounded admin-only local artifact copy wrapper; it preserves the relative path, refuses overwrite, verifies SHA-256 readback, and performs no external delivery.'))
            if _looks_like_artifact_identity_inventory(command):
                return _PdReturn(('artifact_identity_inventory_execute_code', 'pd_one_artifact_identity_inventory', 'Use the bounded admin-only artifact identity inventory wrapper instead of directory glob and magic-byte peeks in execute_code.'))
            if _looks_like_step_printability_analyze(command):
                return _PdReturn(('step_printability_analyze_execute_code', 'pd_one_step_printability_analyze', 'Use the bounded admin-only official STEP printability analyzer wrapper instead of launching analyze_step_printability.py or summarizing official_preflight.json in execute_code; do not copy the source STEP or reuse pd_one_step_geometry_inspect.'))
            if _looks_like_step_geometry_inspect(command):
                return _PdReturn(('step_geometry_inspect_execute_code', 'pd_one_step_geometry_inspect', 'Use the bounded admin-only STEP geometry inspect wrapper instead of launching freecadcmd or summarizing inspect.json in execute_code.'))
            if _looks_like_arbitrary_freecad_script(command):
                return _PdReturn(('arbitrary_freecad_script_execute_code', None, 'Do not approve caller-supplied FreeCAD rebuild/mutation scripts through execute_code; pd_one_step_geometry_inspect is inspect-only and runs a fixed analyzer.'))
            if _looks_like_python_cad_stack_status(command):
                return _PdReturn(('python_cad_stack_status_execute_code', 'pd_one_python_cad_stack_status', 'Use the bounded read-only Python CAD-stack status wrapper instead of ad hoc importlib CAD probes in execute_code.'))
            if _looks_like_python_media_stack_status(command):
                return _PdReturn(('python_media_stack_status_execute_code', 'pd_one_python_media_stack_status', 'Use the bounded read-only Python media-stack status wrapper instead of ad hoc importlib probes in execute_code.'))
            if _looks_like_video_frame_sample(command):
                return _PdReturn(('video_frame_sample_execute_code', 'pd_one_video_frame_sample', 'Use the bounded admin-only video-frame sampling wrapper instead of ad hoc ffprobe/ffmpeg subprocesses in execute_code.'))
            if _looks_like_3mf_slicer_inspect(command):
                return _PdReturn(('threemf_slicer_inspect_execute_code', 'pd_one_3mf_slicer_inspect', 'Use the bounded admin-only 3MF slicer inspect/stage wrapper instead of zipfile extraction in execute_code; it never overwrites the source or delivers artifacts.'))
            if _looks_like_cad_runtime_status(command):
                return _PdReturn(('cad_runtime_status_execute_code', 'pd_one_cad_runtime_status', 'Use the bounded read-only CAD runtime status wrapper instead of probing FreeCAD binaries or lib directories in execute_code.'))
            if _looks_like_svg_artifact_inspection(command):
                return _PdReturn(('svg_artifact_inspection_execute_code', 'pd_one_svg_artifact_inspect', 'Use the bounded admin-only read-only SVG XML/text/image/layout inspection wrapper instead of ElementTree in execute_code.'))
            if _looks_like_svg_embed_image(command):
                return _PdReturn(('svg_embed_image_execute_code', 'pd_one_svg_embed_image', 'Use the admin-only fixed-logo SVG inspect/stage wrapper; it restricts the remote URL and never overwrites the source SVG.'))
            if _looks_like_artifact_base64_encode(command):
                return _PdReturn(('artifact_base64_encode_execute_code', 'pd_one_artifact_base64_encode', 'Use the bounded admin-only artifact base64 wrapper instead of reading and encoding arbitrary local files in execute_code.'))
            if _looks_like_python_package_dry_run(command):
                return _PdReturn(('python_package_dry_run_execute_code', 'pd_one_python_package_dry_run', 'Use the bounded package-resolution dry-run wrapper; never approve the arbitrary execute_code subprocess.'))
            if _looks_like_legacy_xls_hash(command):
                return _PdReturn(('legacy_xls_inspect_execute_code', 'pd_one_legacy_xls_inspect', 'Use the bounded legacy-xls-inspect wrapper for read-only file metadata and digest receipts instead of ad hoc hashing code.'))
            if _looks_like_pdone_dependency_install(command):
                return _PdReturn(('pdone_dependency_install_execute_code', None, 'Do not install packages into the active PD One release through execute_code; use the approved dependency-management/release process with source/lockfile review and rollback evidence.'))
            if _looks_like_disk_space_summary(command):
                return _PdReturn(('disk_space_summary_execute_code', 'pd_one_disk_space_summary', 'Use the bounded read-only disk-space summary wrapper; it performs no cleanup.'))
            if _looks_like_user_process_snapshot(command):
                return _PdReturn(('user_process_snapshot_execute_code', 'pd_one_user_process_snapshot', 'Use the bounded admin-only user process snapshot wrapper instead of ad hoc ps execute_code probes.'))

        def _pd_phase_3():
            if _looks_like_local_process_listener_inspect(command):
                return _PdReturn(('local_process_listener_inspect_execute_code', 'pd_one_local_process_listener_inspect', 'Use the bounded read-only local process/listener inspect wrapper instead of ad hoc ps/ss execute_code probes.'))
            if _looks_like_mixed_host_terminal_inspect(command):
                return _PdReturn(('mixed_host_terminal_inspect_execute_code', None, 'Do not approve mixed date/X11/ps-p/systemd/ls terminal loops through execute_code; split onto existing typed wrappers or keep fail-closed. Do not reuse pd_one_user_process_snapshot or pd_one_local_process_listener_inspect for this class.'))
            if _looks_like_text_metrics(command):
                return _PdReturn(('text_metrics_execute_code', 'pd_one_text_metrics', 'Use the bounded read-only text-metrics wrapper instead of evaluating len(text) in execute_code; the wrapper does not echo the supplied text.'))
            if _looks_like_cached_dest_rest_count(command):
                return _PdReturn(('cached_dest_rest_count_execute_code', 'pd_one_cached_dest_rest_count', 'Use the bounded admin-only cached dest rest-count wrapper instead of json.load/r[6:] rest-mark loops in execute_code; it is read-only and does not return full rows.'))
            if _looks_like_cached_sheet_json_search(command):
                guidance = 'Use the bounded admin-only cached Sheets JSON search wrapper instead of json.load/join-row count loops in execute_code; it is read-only, literal-term only, and does not return full rows.'
                if _looks_like_yammer_archive_search(command):
                    guidance += ' Split the Yammer JSONL half onto pd_one_yammer_archive_search; do not approve a combined execute_code snippet.'
                return _PdReturn(('cached_sheet_json_search_execute_code', 'pd_one_cached_sheet_json_search', guidance))
            if _looks_like_yammer_archive_search(command):
                return _PdReturn(('yammer_archive_search_execute_code', 'pd_one_yammer_archive_search', 'Use the scoped Yammer/Viva Engage archive search wrapper instead of scanning messages.jsonl in execute_code.'))
            if _looks_like_appsheet_incident_morning_briefing_qa(command):
                return _PdReturn(('appsheet_incident_morning_briefing_qa_execute_code', 'pd_one_appsheet_incident_morning_briefing_qa', 'Use the typed AppSheet incident morning briefing QA wrapper instead of ad hoc py_compile/importlib helper checks.'))
            if _looks_like_mattermost_channel_lookup(command):
                return _PdReturn(('mattermost_channel_lookup_execute_code', 'pd_one_mattermost_channel_lookup', 'Use the typed Mattermost channel lookup wrapper instead of an ad hoc bot/team/channel API probe.'))
            if _looks_like_mattermost_channel_post_audit(command):
                return _PdReturn(('mattermost_channel_post_audit_execute_code', 'pd_one_mattermost_channel_post_audit', 'Use the typed read-only Mattermost channel post audit wrapper instead of an ad hoc deleted-post scan.'))
            if _looks_like_admin_alert_source_audit(command):
                return _PdReturn(('admin_alert_source_audit_execute_code', 'pd_one_admin_alert_source_audit', 'Use the fixed-root admin-only source audit wrapper instead of ad hoc search_files/read_file loops.'))
            if _looks_like_local_file_search(command):
                return _PdReturn(('local_file_search_execute_code', 'pd_one_local_file_search', 'Use the bounded admin-only local file search wrapper instead of hermes_tools search_files/read_file loops in execute_code; it returns identities only and never dumps contents.'))
            if _looks_like_mattermost_channel_activity_summary(command):
                return _PdReturn(('mattermost_channel_activity_summary_execute_code', 'pd_one_mattermost_channel_setup', 'Use the read-only Mattermost channel setup/inspection wrapper for bounded post and participant summaries instead of ad hoc API/Python code.'))
            if _looks_like_google_drive_parent_chain(command):
                return _PdReturn(('google_drive_parent_chain_execute_code', 'pd_one_google_drive_parent_chain', 'Use the bounded Google Drive parent-chain wrapper instead of an execute_code gog loop.'))
            if _looks_like_google_group_owner_enforcement(command):
                return _PdReturn(('google_group_owner_enforcement_execute_code', 'pd_one_google_group_owner_enforcement', 'Use the fixed-domain, fixed-owner typed MCP tool instead of exporting tokens or running ad hoc Admin SDK code.'))
            if _looks_like_google_drive_search_files(command):
                return _PdReturn(('google_drive_search_files_execute_code', 'pd_one_google_drive_search_files', 'Use the bounded Google Drive file-search wrapper instead of an execute_code gog search/filter loop.'))
            if _looks_like_sheets_get_range(command):
                return _PdReturn(('sheets_get_range_execute_code', 'pd_one_sheets_get_range', 'Use pd_one_sheets_get_range / sheets-get-range instead of execute_code subprocess loops around sheets_safe_ops.py get or gog sheets get.'))
            if _looks_like_mattermost_channel_setup(command):
                return _PdReturn(('mattermost_channel_setup_execute_code', 'pd_one_mattermost_channel_setup', 'Use the typed Mattermost channel setup wrapper instead of ad hoc Item Master Data Requests length checks.'))
            if _looks_like_protected_portal_origin_probe(command):
                return _PdReturn(('protected_portal_origin_probe_execute_code', 'pd_one_protected_portal_origin_probe', 'Use the bounded read-only loopback portal origin-probe wrapper instead of ad hoc urllib GETs to 127.0.0.1:8766.'))

        def _pd_phase_4():
            if _looks_like_timezone_snapshot(command):
                return _PdReturn(('timezone_snapshot_execute_code', 'pd_one_timezone_snapshot', 'Use the bounded timezone-snapshot wrapper instead of ad hoc current-time Python for UTC and Asia/Taipei.'))
            if _looks_like_timestamp_to_epoch(command):
                return _PdReturn(('timestamp_to_epoch_execute_code', 'pd_one_timestamp_to_epoch', 'Use the bounded timestamp-to-epoch wrapper instead of ad hoc ISO-8601 timestamp conversion in execute_code.'))
            if _looks_like_epoch_milliseconds_to_iso(command):
                return _PdReturn(('epoch_milliseconds_to_iso_execute_code', 'pd_one_epoch_milliseconds_to_iso', 'Use the bounded epoch-milliseconds-to-ISO wrapper instead of ad hoc datetime conversion in execute_code.'))
            if _looks_like_sheets_serial_column_convert(command):
                return _PdReturn(('sheets_serial_column_convert_execute_code', 'pd_one_sheets_serial_column_convert', 'Use the bounded Sheets serial/A1 convert wrapper instead of ad hoc datetime.date(1899,12,30)+timedelta or n*26+(ord(ch)-64) conversion in execute_code.'))
            if _looks_like_item_number_local_lo_builder(command) or _looks_like_item_number_local_fixture_copy(command):
                return _PdReturn(('item_number_local_fixture_copy_execute_code', 'pd_one_item_number_local_fixture_copy', 'Use the fixed local item-number LibreOffice QA fixture wrapper instead of ad hoc execute_code render/copy glue.'))
            if _looks_like_item_number_render_qa(command):
                return _PdReturn(('item_number_render_qa_status_execute_code', 'pd_one_item_number_render_qa_status', 'Use the typed item-number render QA status wrapper instead of ad hoc LibreOffice/receipt inspection in execute_code; actual certification still requires the approved Windows Excel/COM lane.'))
            if _looks_like_ecrn_approval_pilot_status(command):
                return _PdReturn(('ecrn_approval_pilot_status_execute_code', 'pd_one_ecrn_approval_pilot_status', 'Use the typed ECRN approval-pilot status wrapper instead of ad hoc importlib/state preview inspection in execute_code.'))
            if _looks_like_ecrn_approval_pilot_check(command):
                return _PdReturn(('ecrn_approval_pilot_check_execute_code', 'pd_one_ecrn_approval_pilot_check', 'Use the fixed ECRN approval-pilot QA wrapper instead of ad hoc execute_code subprocess checks.'))
            if _looks_like_hermes_backup_sync_copy(command):
                return _PdReturn(('hermes_backup_sync_execute_code', resolve_configured_path('~/hermes-backup/scripts/commit-hermes-backup.sh'), 'Use the configured admin-only canonical Hermes backup process; do not add or approve a broad MCP filesystem-copy writer.'))
            if _looks_like_docx_exact_text_patch(command):
                return _PdReturn(('docx_exact_text_patch_execute_code', 'pd_one_docx_exact_text_patch', 'Use the admin-only exact-text DOCX inspect/stage wrapper; require unique visible matches, preserve the source, and keep delivery separate.'))
            if _looks_like_ecrn_channel_header_test(command):
                return _PdReturn(('ecrn_approval_pilot_check_execute_code', 'pd_one_ecrn_approval_pilot_check', 'Use the existing fixed read-only ECRN approval-pilot QA wrapper instead of arbitrary execute_code pytest glue.'))
            if _looks_like_ecrn_docx_unique_text_patch(command):
                return _PdReturn(('ecrn_docx_unique_text_patch_execute_code', 'pd_one_ecrn_docx_unique_text_patch', 'Use the admin-only inspect/stage ECRN DOCX unique-text wrapper; never overwrite the source or deliver the revised artifact without re-approval.'))
            if _looks_like_docx_table_search(command):
                return _PdReturn(('docx_table_search_execute_code', 'pd_one_docx_table_search', 'Use the bounded DOCX table-search wrapper instead of ad hoc python-docx cell loops in execute_code.'))
            if _looks_like_docx_layout_patch(command):
                return _PdReturn(('docx_layout_patch_execute_code', 'pd_one_docx_layout_patch', 'Use the admin-only inspect/stage DOCX layout wrapper; it applies one fixed section-start pagination adjustment and never overwrites the source.'))
            if _looks_like_docx_table_structure(command):
                return _PdReturn(('docx_table_structure_execute_code', 'pd_one_docx_table_structure', 'Use the bounded read-only DOCX table structure wrapper instead of parsing table geometry and cell text in execute_code.'))
            if _looks_like_docx_body_xml_inspection(command):
                return _PdReturn(('docx_body_xml_inspection_execute_code', 'pd_one_docx_body_xml_inspect', 'Use the bounded admin-only DOCX body paragraph XML inspection wrapper instead of serializing WordprocessingML in execute_code.'))
            if _looks_like_pptx_exact_text_patch(command):
                return _PdReturn(('pptx_exact_text_patch_execute_code', 'pd_one_pptx_exact_text_patch', 'Use the admin-only exact-text PPTX inspect/stage wrapper; require unique visible matches, preserve the source, and keep delivery separate.'))
            if _looks_like_pptx_from_template(command):
                return _PdReturn(('pptx_from_template_execute_code', 'pd_one_pptx_from_template', 'Use the bounded PPTX-from-template wrapper to clone a POTX/PPTX or apply its theme/masters onto a source deck; never overwrite sources and keep Mattermost delivery separate.'))
            if _looks_like_pptx_inspect(command):
                return _PdReturn(('pptx_inspect_execute_code', 'pd_one_pptx_inspect', 'Use the bounded admin-only PPTX shape/run inspect wrapper instead of recursive python-pptx traversal in execute_code.'))

        def _pd_phase_5():
            if _looks_like_pptx_ooxml_text_inspect(command):
                return _PdReturn(('pptx_ooxml_text_inspect_execute_code', 'pd_one_pptx_ooxml_text_inspect', 'Use the bounded admin-only PPTX OOXML a:t inspect wrapper instead of parsing selected slide/diagram XML in execute_code.'))
            if _looks_like_pptx_xml_inspect(command):
                return _PdReturn(('pptx_xml_inspect_execute_code', 'pd_one_doc_extract', 'Use the bounded read-only PPTX extract wrapper instead of parsing PresentationML zip/XML in execute_code.'))
            if _looks_like_docx_xml_text_extraction(command):
                return _PdReturn(('docx_xml_text_extraction_execute_code', 'pd_one_doc_extract', 'Use the bounded read-only DOCX/PPTX text extraction wrapper instead of parsing WordprocessingML or DrawingML in execute_code.'))
            if _looks_like_equipment_workbook_builder(command):
                return _PdReturn(('equipment_workbook_execute_code', 'pd_one_equipment_workbook_build', 'Use the fixed three-source equipment workbook check/stage wrapper instead of ad hoc openpyxl consolidation code.'))
            if _looks_like_xlsx_workbook_inspection(command):
                return _PdReturn(('xlsx_workbook_inspection_execute_code', 'pd_one_xlsx_workbook_inspect', 'Use the bounded admin-only XLSX workbook inspection wrapper instead of openpyxl loops in execute_code.'))
            if _looks_like_docx_targeted_inspection(command):
                return _PdReturn(('docx_targeted_inspection_execute_code', 'pd_one_docx_inspect', 'Use the bounded admin-only DOCX paragraph/run inspection wrapper instead of python-docx table traversal in execute_code.'))
            if _looks_like_office_docprops_inspect(command):
                return _PdReturn(('office_docprops_inspect_execute_code', 'pd_one_office_docprops_inspect', 'Use the bounded admin-only Office Open XML docProps inspect wrapper instead of dumping core.xml/app.xml through execute_code.'))
            if _looks_like_office_visual_qa(command):
                return _PdReturn(('office_visual_qa_execute_code', 'pd_one_office_visual_qa', 'Use the bounded Office visual-QA wrapper instead of running office_visual_qa.py through execute_code.'))
            if _looks_like_office_html_to_docx(command):
                return _PdReturn(('office_html_to_docx_execute_code', 'pd_one_office_html_to_docx', 'Use the bounded HTML-to-DOCX wrapper with isolated LibreOffice instead of execute_code subprocess glue.'))
            if _looks_like_json_html_artifact_build(command):
                return _PdReturn(('json_html_artifact_build_execute_code', 'pd_one_json_html_artifact_build', 'Use the bounded JSON-to-HTML artifact wrapper instead of inline HTML generation in execute_code.'))
            if _looks_like_google_docs_inspect_receipt_summary(command):
                return _PdReturn(('google_docs_inspect_receipt_summary_execute_code', 'pd_one_google_docs_document_ops', 'Use pd_one_google_docs_document_ops action=summarize_inspect_receipt for bounded headings from an existing inspect JSON; do not dump inspect receipts through execute_code.'))
            if _looks_like_json_artifact_inspect(command):
                return _PdReturn(('json_artifact_inspect_execute_code', 'pd_one_json_artifact_inspect', 'Use the bounded admin-only JSON artifact structure inspect wrapper instead of json.load/os.stat loops in execute_code; it returns types/keys/lengths only and never dumps values.'))
            if _looks_like_office_doc_build(command):
                return _PdReturn(('office_doc_build_execute_code', 'pd_one_doc_build_artifact', 'Use the bounded JSON-spec DOCX build wrapper, including its fixed company-announcement template mode, instead of inline DOCX/XML generation in execute_code.'))
            if _looks_like_office_deb_contents(command):
                return _PdReturn(('office_deb_contents_execute_code', 'pd_one_office_deb_contents', 'Use the bounded Office Debian-package contents wrapper instead of ad hoc dpkg-deb subprocess code.'))
            if _looks_like_admin_approval_kanban_status(command):
                return _PdReturn(('admin_approval_kanban_status_execute_code', 'pd_one_admin_approval_kanban_status', 'Use the bounded read-only PDAPP Kanban status wrapper instead of listing workspaces or probing mapping/result files in execute_code.'))
            if _looks_like_hermes_result_messages_summary(command):
                return _PdReturn(('hermes_result_messages_summary_execute_code', 'pd_one_hermes_result_messages_summary', 'Use the admin-only Hermes result-message summary wrapper instead of ad hoc JSON inspection in execute_code.'))
            if any((x in low for x in ('hermes_tools.read_file', 'read_file(', '/tmp/hermes-results'))) and any((x in low for x in ("inner.get('tickets'", 'inner.get("tickets"'))) and ('ticket_id' in low):
                return _PdReturn(('approval_ticket_status_execute_code', 'pd_one_approval_ticket_status', 'Use the typed approval-ticket-status wrapper instead of reading temp result files and scanning ticket lists in execute_code.'))
            if 'mattermost-users.json' in low or 'mattermost-roles.json' in low or '/policies/' in low:
                return _PdReturn(('policy_config_mutation_execute_code', 'pd_one_policy_change_dry_run', 'Replace JSON mutation script with policy diff/apply wrapper.'))
            historical_summary_shape = 'item-number-workflow' in low and 'structural-summary.json' in low and ('json.load' in low) and ('approval_label_cells' in low and ('historical-inspection' in low or ('finance_nearby' in low and 'biff_objects' in low) or ('merged_count' in low and 'finance_observations' in low)) or ("['files'][0]['sheets'][0]" in low and 'keys()' in low))
            if historical_summary_shape:
                return _PdReturn(('item_number_historical_sample_summary_execute_code', 'pd_one_item_number_historical_sample_summary', 'Use the fixed historical item-number sample summary wrapper instead of ad hoc structural-summary JSON inspection in execute_code.'))

        def _pd_phase_6():
            if _looks_like_item_number_local_lo_builder(command):
                return _PdReturn(('item_number_local_fixture_copy_execute_code', 'pd_one_item_number_local_fixture_copy', 'Use the fixed local item-number LibreOffice QA fixture wrapper instead of executing the legacy builder through execute_code.'))
            if 'gog' in low or 'google' in low or 'groups' in low or ('sheets' in low) or ('appscript' in low):
                return _PdReturn(('google_admin_or_sheets_execute_code', 'pd_one_sheets_get_range', 'Use existing Sheets safe ops or build Google group/AppScript wrapper.'))
            if ('libreoffice' in low or 'soffice' in low) and '--convert-to' in low and ('pdf' in low):
                return _PdReturn(('office_convert_to_pdf_execute_code', 'pd_one_office_convert_to_pdf', 'Use the bounded office-to-PDF wrapper with isolated profile and receipt-backed validation.'))
            if 'shutil.which' in low and any((x in low for x in ['ssconvert', 'gnumeric', 'soffice', 'libreoffice', 'pdftoppm', 'pdfinfo'])):
                return _PdReturn(('office_toolchain_status_execute_code', 'pd_one_office_toolchain_status', 'Use the bounded office-toolchain-status wrapper instead of ad hoc binary availability probes.'))
            workflow_engine_compile = 'item-number-workflow' in low and 'py_compile' in low and any((x in low for x in ['workflow_engine.py', 'test_workflow_engine.py']))
            workflow_unit_discovery = 'item-number-workflow' in low and 'unittest' in low and ('discover' in low) and any((x in low for x in ['tests', 'workflow_engine.py', 'test_workflow_engine.py']))
            if 'item-number-workflow' in low and 'summarize_historical_sample.py' in low:
                return _PdReturn(('item_number_historical_sample_summary_execute_code', 'pd_one_item_number_historical_sample_summary', 'Use the fixed historical item-number sample summary wrapper instead of execute_code subprocess glue.'))
            if workflow_engine_compile or workflow_unit_discovery:
                return _PdReturn(('item_number_workflow_check_execute_code', 'pd_one_item_number_workflow_check', 'Use the bounded item-number workflow check wrapper instead of ad hoc Python compilation or unittest discovery in execute_code.'))
            if 'run_windows_excel_qa.py' in low and 'item-number-workflow' in low:
                return _PdReturn(('item_number_windows_excel_qa_execute_code', 'pd_one_item_number_windows_excel_qa', 'Use the confirmation-gated Windows Excel/COM QA wrapper instead of execute_code subprocess glue.'))
            if any((x in low for x in ['pd_one_item_number_xlsx_compiler', 'item-number-xlsx-compiler', 'item_number_xlsx_compiler', 'migrate_xls_to_xlsx', 'compile_signed_xlsx', 'prequalify_xlsx_template', 'verify_prequalified_template', 'test_item_number_xlsx_compiler.py'])):
                return _PdReturn(('item_number_xlsx_compiler_execute_code', 'pd_one_item_number_xlsx_compiler', 'Use the bounded item-number-xlsx-compiler smoke wrapper with canonical source/template paths and a fixed dummy approval.'))
            if any((x in low for x in ['olefile', 'xlrd', 'legacy-xls-inspect', 'open_workbook', 'merged_cells', 'sheet_by_index', 'cellname', 'name_obj_list'])):
                return _PdReturn(('legacy_xls_inspect_execute_code', 'pd_one_legacy_xls_inspect', 'Use the bounded legacy-xls-inspect wrapper with workbook stream, merged-cell, and preview receipts.'))
            if 'sip_threads_pd' in low and 'noisy' in low:
                return _PdReturn(('sip_thread_index_audit_execute_code', 'pd_one_sip_thread_index_audit', 'Use the bounded SIP thread-index audit wrapper with fixed input root and bounded sample receipts.'))
            if 'build_sip_thread_index.py' in low or 'sip_threads_pd' in low or 'sip thread index' in low or ('sip製作溝通' in low):
                return _PdReturn(('sip_thread_index_build_execute_code', 'pd_one_sip_thread_index_build', 'Use the bounded SIP workbook builder with fixed input root and OpenXML verification.'))
            if any((x in low for x in ['pptx', 'docx', 'pdf', 'presentation', 'document', 'fitz'])):
                return _PdReturn(('document_media_execute_code', 'pd_one_doc_extract', 'Use bounded document extraction/build wrappers plus Office QA.'))
            return _PdReturn(('arbitrary_execute_code', None, 'Avoid execute_code in PD One lanes; promote bounded operation to typed wrapper.'))
        _pd_result = _pd_phase_2()
        if isinstance(_pd_result, _PdReturn):
            return _pd_result.value
        _pd_result = _pd_phase_3()
        if isinstance(_pd_result, _PdReturn):
            return _pd_result.value
        _pd_result = _pd_phase_4()
        if isinstance(_pd_result, _PdReturn):
            return _pd_result.value
        _pd_result = _pd_phase_5()
        if isinstance(_pd_result, _PdReturn):
            return _pd_result.value
        _pd_result = _pd_phase_6()
        if isinstance(_pd_result, _PdReturn):
            return _pd_result.value
    if tool == 'execute_code':
        _pd_result = _pd_phase_1()
        if isinstance(_pd_result, _PdReturn):
            return _pd_result.value
    if 'rm -rf' in low or 'recursive delete' in low or 'rm -f /tmp' in low:
        return ('cleanup_delete_command', 'pd_one_disk_cleanup_dry_run', 'Use bounded safe prune/cleanup wrapper with manifest/readback.')
    if 'docker' in low or 'curl http' in low or 'ss -' in low or ('systemctl' in low):
        return ('service_container_network_probe', 'pd_one_auth_browser_status', 'Use read-only status probe wrapper; keep lifecycle changes gated.')
    if '| python' in low or 'python3 -c' in low or 'python -c' in low or ('python3 - <<' in low) or ('bash -c' in low) or ('sh -c' in low):
        if 'groups' in low and 'gog admin' in low:
            return ('google_group_pipe_to_python', 'pd_one_google_group_members', 'Use Google group membership wrapper.')
        if 'sheets' in low or 'review_log' in low or 'project_registry' in low:
            return ('sheets_pipe_to_python', 'pd_one_sheets_get_range', 'Use sheets_safe_ops.py / typed Sheets capability.')
        return ('terminal_inline_script_or_pipe', None, 'Replace heredoc/pipe glue with a checked-in typed helper.')
    if 'gog admin groups' in low:
        return ('google_group_raw_gog', 'pd_one_google_group_members', 'Use Google group membership/change wrapper.')
    if 'gog' in low and 'sheets' in low:
        return ('sheets_raw_gog', 'pd_one_sheets_get_range', 'Use sheets_safe_ops.py / typed Sheets capability.')
    return ('other_flagged_terminal', None, 'Review for wrapper promotion or keep approval-gated if genuinely risky.')

def outcome(approval: str | None, error: str | None) -> str:
    s = ' '.join([approval or '', error or ''])
    if 'auto-approved' in s:
        return 'auto_approved'
    if 'approved by the user' in s:
        return 'user_approved'
    return 'blocked_timeout_denied'

def collect(db: Path, days: int) -> dict[str, Any]:
    since = utc_ts(days)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    session_rows = list(con.execute('select id, source, title from sessions where started_at >= ? order by started_at', (since - 2 * 86400,)))
    session_meta = {r['id']: {'source': r['source'], 'title': r['title']} for r in session_rows}
    candidate_rows = []
    for sid in session_meta:
        candidate_rows.extend(con.execute("\n            select id, session_id, datetime(timestamp,'unixepoch') ts, timestamp,\n                   tool_name, tool_call_id, content\n            from messages\n            where session_id = ? and timestamp >= ? and role='tool' and tool_name in ('terminal','execute_code')\n            order by timestamp\n            ", (sid, since)).fetchall())
    needed_call_ids = {r['tool_call_id'] for r in candidate_rows if r['tool_call_id']}
    callmap: dict[str, dict[str, Any]] = {}
    if needed_call_ids:
        for sid in session_meta:
            for r in con.execute("select id, session_id, tool_calls from messages where session_id = ? and timestamp >= ? and tool_calls is not null and tool_calls != ''", (sid, since)):
                try:
                    calls = json.loads(r['tool_calls'])
                except Exception:
                    logging.getLogger('pd_one_ops').exception('pd one command failed')
                    continue
                for call in calls or []:
                    cid = call.get('id') or call.get('call_id')
                    if cid in needed_call_ids:
                        fn = call.get('function') or {}
                        callmap[cid] = {'assistant_msg_id': r['id'], 'session_id': r['session_id'], 'name': fn.get('name'), 'args': fn.get('arguments') or ''}
                if len(callmap) >= len(needed_call_ids):
                    break
    cases = []
    for row in candidate_rows:
        content = row['content'] or ''
        try:
            data = json.loads(content)
        except Exception:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            data = {}
        approval = data.get('approval')
        err = data.get('error') or ''
        if not approval and 'BLOCKED' not in err and ('smart approval' not in err):
            continue
        cm = callmap.get(row['tool_call_id'] or '', {})
        cmd = recover_command(cm.get('args', ''))
        cls, suggested, mitigation = classify(row['tool_name'], approval or '', err, cmd)
        meta = session_meta.get(row['session_id'], {})
        cases.append({'message_id': row['id'], 'session_id': row['session_id'], 'source': meta.get('source'), 'title': meta.get('title'), 'timestamp': row['ts'], 'tool': row['tool_name'], 'outcome': outcome(approval, err), 'class': cls, 'suggested_capability': suggested, 'mitigation': mitigation, 'approval': redact((approval or err or '')[:500]), 'command_excerpt': redact(re.sub('\\s+', ' ', cmd).strip()[:800])})
    class_counts = collections.Counter((c['class'] for c in cases))
    outcome_counts = collections.Counter((c['outcome'] for c in cases))
    cap_counts = collections.Counter((c['suggested_capability'] for c in cases if c['suggested_capability']))
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for c in cases:
        groups[c['session_id']].append(c)
    proposals = []
    for cls, count in class_counts.most_common():
        examples = [c for c in cases if c['class'] == cls][:3]
        cap = next((c['suggested_capability'] for c in examples if c['suggested_capability']), None)
        proposals.append({'pattern': cls, 'count': count, 'suggested_capability': cap, 'mitigation': examples[0]['mitigation'] if examples else '', 'example_sessions': sorted({e['session_id'] for e in examples}), 'priority': 'high' if count >= 3 else 'medium' if count >= 2 else 'low'})
    return {'db': str(db), 'window_days': days, 'since_utc': dt.datetime.fromtimestamp(since, dt.timezone.utc).isoformat(), 'case_count': len(cases), 'session_count': len(groups), 'outcome_counts': dict(outcome_counts), 'class_counts': dict(class_counts), 'suggested_capability_counts': dict(cap_counts), 'proposals': proposals, 'cases': cases}

def markdown(report: dict[str, Any]) -> str:
    lines = []
    lines.append('# PD One dangerous-command audit')
    lines.append('')
    lines.append(f'- DB: `{report['db']}`')
    lines.append(f'- Window: {report['window_days']} days since {report['since_utc']}')
    lines.append(f'- Cases: **{report['case_count']}** across **{report['session_count']}** sessions')
    lines.append('')
    lines.append('## Outcomes')
    for k, v in report['outcome_counts'].items():
        lines.append(f'- {k}: {v}')
    lines.append('')
    lines.append('## Top patterns / wrapper proposals')
    for p in report['proposals']:
        cap = p.get('suggested_capability') or 'TBD'
        lines.append(f'- **{p['pattern']}** ({p['count']}, {p['priority']}): `{cap}` — {p['mitigation']}')
    lines.append('')
    lines.append('## Recent examples')
    for c in report['cases'][-20:]:
        lines.append(f'- `{c['timestamp']}` `{c['session_id']}` {c['tool']} {c['outcome']} `{c['class']}` → `{c.get('suggested_capability') or 'TBD'}`')
    return '\n'.join(lines) + '\n'

def cmd_audit(args: argparse.Namespace) -> None:
    report = collect(Path(args.db), args.days)
    if args.propose_capabilities:
        keys = ('db', 'window_days', 'since_utc', 'case_count', 'session_count', 'suggested_capability_counts', 'proposals')
        print(json.dumps({key: report[key] for key in keys}, ensure_ascii=False, indent=2))
    elif args.markdown:
        print(markdown(report), end='')
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0

def build_parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', default=str(DEFAULT_DB()))
    ap.add_argument('--days', type=int, default=7)
    ap.add_argument('--json', action='store_true', help='emit full JSON report')
    ap.add_argument('--markdown', action='store_true', help='emit Markdown summary')
    ap.add_argument('--propose-capabilities', action='store_true', help='emit proposal JSON only')
    ap.set_defaults(func=cmd_audit)
    return ap
if __name__ == '__main__':
    raise SystemExit(main())

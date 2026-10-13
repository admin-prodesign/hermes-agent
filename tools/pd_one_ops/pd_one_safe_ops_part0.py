"""PD One safe operations dispatcher.

Small typed wrappers for repeated operations that previously appeared as raw
terminal heredocs/pipelines. This is a bridge toward first-class MCP/plugin tools:
it uses shell=False, validates inputs, avoids token printing, emits JSON receipts,
and defaults to read-only/dry-run behavior.
"""
from __future__ import annotations
__all__ = ['_PdReturn', '_PdHandled', '_PdUnset', '_PdUnset', '_PdLazyMod', '_PdLazyAttr', 'requests', 'ROOT', 'PYTHON_MEDIA_STACK_MODULES', 'PYTHON_CAD_STACK_MODULES', 'CAD_DOCUMENT_ROOTS', 'CAD_DOCUMENT_SUFFIXES', 'CAD_DOCUMENT_MAX_INPUTS', 'CAD_DOCUMENT_PATH_MAX_CHARS', 'STEP_GEOMETRY_SCRIPT', 'STEP_GEOMETRY_FREECADCMD', 'STEP_GEOMETRY_INPUT_ROOTS', 'STEP_GEOMETRY_OUTPUT_ROOT', 'STEP_GEOMETRY_SUFFIXES', 'STEP_GEOMETRY_JSON_SUFFIXES', 'STEP_GEOMETRY_JSON_MAX_BYTES', 'STEP_GEOMETRY_MAX_SOLIDS', 'STEP_GEOMETRY_MAX_UNKNOWN_EDGES', 'STEP_GEOMETRY_MAX_FACE_EXTRAS', 'STEP_GEOMETRY_FACE_EXTRA_KEYS', 'STEP_GEOMETRY_UNKNOWN_EDGE_KINDS', 'STEP_GEOMETRY_MAX_SOURCE_BYTES', 'STEP_GEOMETRY_TIMEOUT_SECONDS', 'STEP_GEOMETRY_HEADER_BYTES', 'STEP_PRINTABILITY_SCRIPT', 'STEP_PRINTABILITY_OUTPUT_ROOT', 'STEP_PRINTABILITY_TIMEOUT_SECONDS', 'STEP_PRINTABILITY_JSON_MAX_BYTES', 'STEP_PRINTABILITY_MAX_FINDINGS', 'STEP_PRINTABILITY_JSON_NAMES', 'USER_PROCESS_SNAPSHOT_USER', 'USER_PROCESS_SNAPSHOT_MAX_ROWS', 'USER_PROCESS_SNAPSHOT_CMD_CHARS', 'USER_PROCESS_SNAPSHOT_SECRET_KV_RE', 'POLICY_USERS', 'POLICY_ROLES', 'REGISTRY', 'DEFAULT_ACCOUNT', 'APPROVAL_LEDGER', 'MATTERMOST_REVIEW_LOG', 'SHEETS_SAFE_OPS', 'DRIVE_ACL_AUTHORIZE', 'APPSHEET_TABLE_PROBE', 'APPSHEET_ENV_FILES', 'APPSHEET_INCIDENT_MORNING_BRIEFING_SENDER', 'APPSHEET_INCIDENT_MORNING_BRIEFING_RETRY', 'APPSHEET_INCIDENT_MORNING_BRIEFING_SCRIPT', 'DOCS_API', 'ADMIN_APPROVAL_TOOLS', 'ADMIN_APPROVAL_NOTIFY', 'ADMIN_APPROVAL_LISTENER', 'ADMIN_APPROVAL_EXECUTOR', 'ADMIN_APPROVAL_EXECUTOR_CONFIG', 'ADMIN_APPROVAL_KANBAN_STATE', 'KANBAN_BOARDS_ROOT', 'ADMIN_APPROVAL_KANBAN_BOARD', 'ADMIN_APPROVAL_KANBAN_MAPPING_SCHEMA', 'ADMIN_APPROVAL_EXECUTION_RESULT_SCHEMA', 'PDAPP_TICKET_ID_RE', 'KANBAN_TASK_ID_RE', 'ADMIN_APPROVAL_KANBAN_JSON_MAX_BYTES', 'MATTERMOST_POLICY_LOOKUP', 'DEFAULT_ADMIN_CHANNEL_ID', 'DEFAULT_ANDY_USER_ID', 'ADMIN_ALERT_SOURCE_AUDIT_ROOTS', 'ADMIN_ALERT_SOURCE_AUDIT_MAX_FILES', 'ADMIN_ALERT_SOURCE_AUDIT_MAX_FILE_BYTES', 'HR_POLICY_DOCUMENT_IDS', 'MATTERMOST_CHANNEL_SETUP_CONFIRMATION', 'ADMIN_APPROVAL_DECISION_CONFIRMATION', 'ADMIN_APPROVAL_CANCEL_CONFIRMATION', 'CANCELLABLE_TICKET_STATUSES', 'DOC_ALLOWED_ROOTS', 'COMPANY_ANNOUNCEMENT_TEMPLATE', 'COMPANY_ANNOUNCEMENT_MAX_REPLACEMENTS', 'COMPANY_ANNOUNCEMENT_MAX_REPLACEMENT_CHARS', 'DOC_ALLOWED_FILES', 'LOCAL_ARTIFACT_COPY_SOURCE_ROOT', 'LOCAL_ARTIFACT_COPY_DEST_ROOT', 'LOCAL_ARTIFACT_COPY_ALLOWED_SUFFIXES', 'LOCAL_ARTIFACT_COPY_MAX_BYTES', 'ARTIFACT_BASE64_ALLOWED_ROOTS', 'ARTIFACT_BASE64_ALLOWED_SUFFIXES', 'ARTIFACT_BASE64_MAX_BYTES', 'SVG_INSPECT_MAX_BYTES', 'SVG_INSPECT_MAX_ELEMENTS', 'SVG_INSPECT_MAX_IMAGES', 'SVG_INSPECT_MAX_REQUIRED_TEXTS', 'SVG_INSPECT_MAX_REQUIRED_TEXT_CHARS', 'SVG_INSPECT_MAX_ATTR_CHARS', 'PPTX_INSPECT_MAX_BYTES', 'PPTX_INSPECT_MAX_SLIDES', 'PPTX_INSPECT_MAX_SHAPES', 'PPTX_INSPECT_MAX_PARAS', 'PPTX_INSPECT_MAX_RUNS', 'PPTX_INSPECT_MAX_TEXT', 'PPTX_INSPECT_MAX_DEPTH', 'ARTIFACT_BASE64_MIME_TYPES', 'VIDEO_FRAME_INPUT_ROOT', 'VIDEO_FRAME_OUTPUT_ROOT', 'VIDEO_FRAME_ALLOWED_SUFFIXES', 'VIDEO_FRAME_MAX_SOURCE_BYTES', 'VIDEO_FRAME_MAX_DURATION_SECONDS', 'VIDEO_FRAME_DEFAULT_FRACTIONS', 'THREEMF_SLICER_INPUT_ROOTS', 'ARTIFACT_IDENTITY_INPUT_ROOTS', 'ARTIFACT_IDENTITY_ALLOWED_SUFFIXES', 'ARTIFACT_IDENTITY_MAX_GLOBS', 'ARTIFACT_IDENTITY_MAX_GLOB_CHARS', 'ARTIFACT_IDENTITY_MAX_MATCHES', 'ARTIFACT_IDENTITY_MAX_PEEK_BYTES', 'ARTIFACT_IDENTITY_DEFAULT_PEEK_BYTES', 'THREEMF_SLICER_OUTPUT_ROOT', 'THREEMF_SLICER_MAX_SOURCE_BYTES', 'THREEMF_SLICER_MAX_MEMBER_BYTES', 'THREEMF_SLICER_MAX_NAMELIST', 'THREEMF_SLICER_MAX_VALUE_CHARS', 'THREEMF_SLICER_MAX_SETTINGS', 'THREEMF_SLICER_MEMBERS', 'THREEMF_SLICER_SETTING_KEYS', 'CAD_RUNTIME_CANDIDATE_BINS', 'CAD_RUNTIME_WHICH_NAMES', 'CAD_RUNTIME_LIB_DIRS', 'CAD_RUNTIME_DIR_SAMPLE', 'CAD_3MF_PEEK_SUFFIXES', 'CAD_3MF_MAX_PEEK_FILES', 'CAD_3MF_PEEK_BYTES', 'CAD_3MF_NAMELIST_SAMPLE', 'SVG_EMBED_IMAGE_OUTPUT_ROOT', 'SVG_EMBED_IMAGE_ALLOWED_URL', 'SVG_EMBED_IMAGE_MAX_SVG_BYTES', 'SVG_EMBED_IMAGE_MAX_REMOTE_BYTES', 'HERMES_RESULTS_ROOT', 'HERMES_RESULT_SUMMARY_MAX_BYTES', 'HERMES_RESULT_SUMMARY_MAX_MESSAGES', 'HERMES_RESULT_SUMMARY_MAX_CONTENT_ITEMS', 'HERMES_RESULT_SUMMARY_MAX_TEXT_CHARS', 'JSON_ARTIFACT_INSPECT_ROOTS', 'JSON_ARTIFACT_INSPECT_MAX_FILES', 'JSON_ARTIFACT_INSPECT_MAX_BYTES', 'JSON_ARTIFACT_INSPECT_MAX_KEYS', 'JSON_ARTIFACT_INSPECT_MAX_SAMPLE_KEYS', 'JSON_ARTIFACT_INSPECT_KEY_CHARS', 'LOCAL_FILE_SEARCH_ROOTS', 'LOCAL_FILE_SEARCH_MAX_PATHS', 'LOCAL_FILE_SEARCH_MAX_PATTERNS', 'LOCAL_FILE_SEARCH_MAX_MATCHES', 'LOCAL_FILE_SEARCH_MAX_WALK_FILES', 'LOCAL_FILE_SEARCH_MAX_PATTERN_CHARS', 'DOCX_INSPECT_MAX_BYTES', 'DOCX_INSPECT_MAX_TEXT_CHARS', 'DOCX_INSPECT_MAX_RUNS', 'PPTX_OOXML_TEXT_INSPECT_MAX_BYTES', 'PPTX_OOXML_TEXT_INSPECT_MAX_MEMBER_BYTES', 'PPTX_OOXML_TEXT_INSPECT_MAX_MEMBERS', 'PPTX_OOXML_TEXT_INSPECT_MAX_TEXTS', 'PPTX_OOXML_TEXT_INSPECT_MAX_TEXT_CHARS', 'PPTX_OOXML_TEXT_INSPECT_MEMBER_RE', 'PPTX_OOXML_DRAWINGML_T', 'DOCX_LAYOUT_TARGET_MAX_CHARS', 'XLSX_WORKBOOK_INSPECT_SUFFIXES', 'XLSX_WORKBOOK_INSPECT_MAX_FILES', 'XLSX_WORKBOOK_INSPECT_MAX_BYTES', 'XLSX_WORKBOOK_INSPECT_MAX_SHEETS', 'XLSX_WORKBOOK_INSPECT_MAX_ROWS', 'XLSX_WORKBOOK_INSPECT_MAX_COLUMNS', 'XLSX_WORKBOOK_INSPECT_MAX_CELL_CHARS', 'SIP_THREAD_INDEX_ROOT', 'SIP_THREAD_INDEX_SCRIPT', 'SIP_THREAD_INDEX_OUTPUT', 'ITEM_NUMBER_WORKFLOW_ROOT', 'ITEM_NUMBER_COMPILER_ROOT', 'ITEM_NUMBER_COMPILER_SCRIPT', 'ITEM_NUMBER_COMPILER_TEST', 'ITEM_NUMBER_SOURCE_XLS', 'ITEM_NUMBER_WORKFLOW_TMP_ROOT', 'EQUIPMENT_WORKBOOK_SCRIPT', 'EQUIPMENT_WORKBOOK_TMP_ROOT', 'ITEM_NUMBER_SMOKE_TEMPLATE_NAME', 'ITEM_NUMBER_SMOKE_DISPLAY_NAME', 'ITEM_NUMBER_SMOKE_CREATE_AT', 'ITEM_NUMBER_SMOKE_USER_ID', 'ITEM_NUMBER_SMOKE_POST_ID', 'ITEM_NUMBER_SMOKE_ROUTE', 'ITEM_NUMBER_SMOKE_FULFILLMENT_LINK', 'ITEM_NUMBER_SMOKE_ROOT_POST_ID', 'ITEM_NUMBER_SMOKE_REVISION_HASH', 'ITEM_NUMBER_SMOKE_COMMENTS', 'SIP_THREAD_INDEX_INPUT_GLOBS', 'SIP_THREAD_INDEX_NOISE_MARKERS', 'ITEM_NUMBER_WORKFLOW_ROOT', 'ITEM_NUMBER_WORKFLOW_ENGINE', 'ITEM_NUMBER_WORKFLOW_SCRIPT', 'ITEM_NUMBER_WORKFLOW_TEST', 'ITEM_NUMBER_WORKFLOW_RUNNER', 'ITEM_NUMBER_WORKFLOW_RUNNER_SCRIPT', 'ITEM_NUMBER_WORKFLOW_RUNNER_TEST', 'ITEM_NUMBER_RENDER_QA_ROOT', 'ITEM_NUMBER_RENDER_QA_ARTIFACTS', 'ITEM_NUMBER_RENDER_QA_RESULTS', 'ITEM_NUMBER_RENDER_QA_TEST_REPORT', 'ITEM_NUMBER_RENDER_QA_ADMIN_PACKET', 'ITEM_NUMBER_RENDER_QA_TEMPLATE', 'ITEM_NUMBER_HISTORICAL_ROOT', 'ITEM_NUMBER_HISTORICAL_SCRIPT', 'ITEM_NUMBER_HISTORICAL_RECEIPT', 'ITEM_NUMBER_HISTORICAL_OUTPUT', 'ITEM_NUMBER_LOCAL_QA_ROOT', 'ITEM_NUMBER_LOCAL_QA_RECEIPT', 'ITEM_NUMBER_LOCAL_QA_INPUTS', 'ECRN_APPROVAL_PILOT_STATE', 'ECRN_APPROVAL_PILOT_SCRIPT', 'ECRN_CHANNEL_HEADER_TEST_ROOT', 'ECRN_CHANNEL_HEADER_SCRIPT', 'ECRN_CHANNEL_HEADER_TEST', 'ECRN_DOCX_PATCH_SCRIPT', 'PPTX_EXACT_TEXT_PATCH_SCRIPT', 'PPTX_FROM_TEMPLATE_SCRIPT', 'OFFICE_TO_PDF_INPUT_SUFFIXES', 'HTML_TO_DOCX_INPUT_SUFFIXES', 'OFFICE_VISUAL_QA_INPUT_SUFFIXES', 'OFFICE_HTML_TO_DOCX_INPUT_SUFFIXES', 'OFFICE_HTML_TO_DOCX_MAX_BYTES', 'JSON_HTML_ARTIFACT_MAX_BYTES', 'JSON_HTML_ARTIFACT_MAX_PARAGRAPHS', 'OFFICE_VISUAL_QA_MAX_BYTES', 'OFFICE_VISUAL_QA_MAX_FILES', 'OFFICE_VISUAL_QA_SCRIPT', 'OFFICE_DOCPROPS_INPUT_SUFFIXES', 'OFFICE_DOCPROPS_MAX_SOURCE_BYTES', 'OFFICE_DOCPROPS_MAX_MEMBER_BYTES', 'OFFICE_DOCPROPS_MAX_FIELD_CHARS', 'OFFICE_DOCPROPS_MAX_NAMELIST', 'OFFICE_DOCPROPS_MEMBERS', 'OFFICE_DOCPROPS_CORE_FIELDS', 'OFFICE_DOCPROPS_APP_FIELDS', 'OFFICE_DOCPROPS_INT_FIELDS', 'OFFICE_DEB_ALLOWED_ROOT', 'OFFICE_DEB_CONTENT_MAX_LINES', 'OFFICE_TOOLCHAIN_BINARIES', 'PATH_BASE', 'TYPHOON_AUTOMATION_SCRIPT', 'TYPHOON_AUTOMATION_TEST', 'TYPHOON_AUTOMATION_FIXTURE_ROOTS', 'TYPHOON_AUTOMATION_LIVE_CONFIRMATION', 'TYPHOON_AUTOMATION_SWEEP_STATE_FILE', 'PYTHON_DOCX_REPAIR_TICKET_ID', 'PYTHON_DOCX_REPAIR_PACKAGE', 'PYTHON_DOCX_REPAIR_VERSION', 'PYTHON_DOCX_REPAIR_PYTHON', 'PYTHON_DOCX_REPAIR_CONFIRMATION', 'TYPHOON_AUTOMATION_SWEEP_CASES', 'SYSSTAT_LOG_ROOT', 'SYSSTAT_SUMMARY_DEFAULT_HOURS', 'SYSSTAT_SUMMARY_MAX_HOURS', 'SYSSTAT_SUMMARY_METRIC_SPECS', 'OLLAMA_EMBEDDING_UNIT', 'OLLAMA_EMBEDDING_PORT', 'OLLAMA_EMBEDDING_CONTAINER', 'OLLAMA_EMBEDDING_PEER_CONTAINER', 'OLLAMA_EMBEDDING_MAX_CONTAINER_TAIL_LINES', 'OLLAMA_EMBEDDING_MAX_JOURNAL_TAIL_LINES', 'OLLAMA_EMBEDDING_LOG_PATTERNS', 'OLLAMA_EMBEDDING_WATCHDOG_UNIT', 'OLLAMA_EMBEDDING_WATCHDOG_MAX_JOURNAL_TAIL_LINES', 'OLLAMA_EMBEDDING_WATCHDOG_LOG_PATTERNS', 'LOCAL_PROCESS_LISTENER_PORTS', 'LOCAL_PROCESS_LISTENER_DEFAULT_PORTS', 'LOCAL_PROCESS_LISTENER_MAX_PORTS', 'LOCAL_PROCESS_LISTENER_MAX_PIDS', 'LOCAL_PROCESS_LISTENER_CMD_CAP', 'LOCAL_PROCESS_LISTENER_SS_PID_RE', 'LOCAL_PROCESS_LISTENER_SS_COMM_RE', 'PROTECTED_PORTAL_ORIGIN_HOST', 'PROTECTED_PORTAL_ORIGIN_PORT', 'PROTECTED_PORTAL_ORIGIN_TIMEOUT_SEC', 'PROTECTED_PORTAL_ORIGIN_BODY_CAP', 'PROTECTED_PORTAL_ORIGIN_TITLE_CAP', 'PROTECTED_PORTAL_MANIFEST', 'PROTECTED_PORTAL_UNKNOWN_EMAIL', 'PROTECTED_PORTAL_ADMIN_EMAIL', 'PROTECTED_PORTAL_DEFAULT_PROBES', 'fail', 'emit', 'enforce_drive_acl', 'safe_env', 'find_bin', 'run_json', 'run_capture', 'tail_text', 'normalize_email', 'cmd_registry_list', 'SHEETS_GET_RENDER_OPTIONS', 'cmd_sheets_get_range', 'CACHED_SHEET_JSON_MAX_BYTES', 'CACHED_SHEET_JSON_MAX_ROWS', 'CACHED_SHEET_JSON_MAX_COLS', 'CACHED_SHEET_JSON_MAX_TERMS', 'CACHED_SHEET_JSON_MAX_COLUMNS', 'CACHED_SHEET_JSON_MAX_MATCHES', 'CACHED_SHEET_JSON_CELL_CHARS', 'CACHED_SHEET_JSON_TERM_CHARS', 'DEST_REST_COUNT_MAX_WORKERS', 'DEST_REST_COUNT_NAME_CHARS', 'DEST_REST_COUNT_MAX_DAYS', 'DEST_REST_COUNT_DEFAULT_MARKERS', 'cmd_cached_sheet_json_search', '_dest_rest_day_number', 'cmd_cached_dest_rest_count', 'require_pdone_tmp_path', 'require_under_roots', 'cmd_sheets_batch_update', 'cmd_sheets_append', 'cmd_sheets_header_update_row', 'BOUNDED_SHEET_CELL_A1_RE', 'BOUNDED_SHEET_CELL_WRITE_MAX_CELLS', 'BOUNDED_SHEET_CELL_WRITE_LIVE_CONFIRM', 'bounded_sheet_cell_a1', 'load_bounded_sheet_cell_write_payload', 'cmd_bounded_sheet_cell_write', 'cmd_appsheet_table_probe', '_load_appsheet_incident_morning_briefing_module', '_appsheet_incident_morning_briefing_qa_samples', 'cmd_appsheet_incident_morning_briefing_qa', 'cmd_google_group_members', 'cmd_google_drive_parent_chain', 'cmd_google_drive_search_files', 'cmd_google_group_change', 'http_status', 'port_open', '_bounded_int', '_validated_probe_name', '_parse_key_value_lines', '_scan_embedding_log_text', '_scan_embedding_watchdog_log_text', '_probe_text', 'cmd_auth_browser_status', '_sysstat_percentile', '_sysstat_series_summary', '_sysstat_numeric', '_sysstat_select_log_files', '_sysstat_parse_sadf_output', '_sysstat_emit_row', '_sysstat_metric_report', '_sysstat_state_high', '_sysstat_state_low', 'cmd_numeric_summary', 'cmd_text_metrics', 'cmd_disk_space_summary', '_format_ps_etime', 'redact_process_cmd', '_proc_start_ticks']

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
requests = _PdLazyMod('requests')

def ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))
PYTHON_MEDIA_STACK_MODULES = ('cv2', 'PIL', 'numpy', 'av', 'moviepy', 'imageio', 'imageio_ffmpeg', 'scipy')
PYTHON_CAD_STACK_MODULES = ('cadquery', 'OCP', 'OCC', 'OCC.Core', 'OCC.Core.STEPControl', 'trimesh', 'numpy', 'PIL', 'ezdxf', 'build123d', 'gmsh', 'FreeCAD', 'Part')

def CAD_DOCUMENT_ROOTS():
    return (ROOT() / 'cache/documents',)
CAD_DOCUMENT_SUFFIXES = {'.stp', '.step', '.3mf'}
CAD_DOCUMENT_MAX_INPUTS = 2
CAD_DOCUMENT_PATH_MAX_CHARS = 500

def STEP_GEOMETRY_SCRIPT():
    return ROOT() / 'scripts/inspect_step_geometry.py'

def STEP_GEOMETRY_FREECADCMD():
    return Path(resolve_configured_path('~/.local/bin/freecadcmd'))

def STEP_GEOMETRY_INPUT_ROOTS():
    return (ROOT() / 'cache/documents', ROOT() / 'artifacts', ROOT() / 'tmp', ROOT() / 'legacy-openclaw/workspace-employee/artifacts')

def STEP_GEOMETRY_OUTPUT_ROOT():
    return ROOT() / 'tmp/step-geometry-inspect'
STEP_GEOMETRY_SUFFIXES = {'.stp', '.step'}
STEP_GEOMETRY_JSON_SUFFIXES = {'.json'}
STEP_GEOMETRY_JSON_MAX_BYTES = 5 * 1024 * 1024
STEP_GEOMETRY_MAX_SOLIDS = 20
STEP_GEOMETRY_MAX_UNKNOWN_EDGES = 8
STEP_GEOMETRY_MAX_FACE_EXTRAS = 40
STEP_GEOMETRY_FACE_EXTRA_KEYS = ('radius', 'radius1', 'radius2', 'semi_angle_deg', 'normal', 'slope_from_horizontal_deg', 'downward', 'axis', 'center', 'area', 'kind', 'index')
STEP_GEOMETRY_UNKNOWN_EDGE_KINDS = {None, 'unknown', 'edge_error'}
STEP_GEOMETRY_MAX_SOURCE_BYTES = 80 * 1024 * 1024
STEP_GEOMETRY_TIMEOUT_SECONDS = 180
STEP_GEOMETRY_HEADER_BYTES = 1000000

def STEP_PRINTABILITY_SCRIPT():
    return ROOT() / 'scripts/analyze_step_printability.py'

def STEP_PRINTABILITY_OUTPUT_ROOT():
    return ROOT() / 'tmp/step-printability-analyze'
STEP_PRINTABILITY_TIMEOUT_SECONDS = 180
STEP_PRINTABILITY_JSON_MAX_BYTES = 5 * 1024 * 1024
STEP_PRINTABILITY_MAX_FINDINGS = 12
STEP_PRINTABILITY_JSON_NAMES = {'official_preflight.json', 'printability.json', 'analyze.json'}
USER_PROCESS_SNAPSHOT_USER = 'prodesign'
USER_PROCESS_SNAPSHOT_MAX_ROWS = 80
USER_PROCESS_SNAPSHOT_CMD_CHARS = 160
USER_PROCESS_SNAPSHOT_SECRET_KV_RE = re.compile('(?i)((?:--)?(?:access[_-]?token|api[_-]?key|auth(?:orization)?|bearer|password|passwd|secret|token)[=:\\s]+)(\\S+)')

def POLICY_USERS():
    return ROOT() / 'policies/mattermost-users.json'

def POLICY_ROLES():
    return ROOT() / 'policies/mattermost-roles.json'

def REGISTRY():
    return ROOT() / 'capabilities/registry.yaml'

def DEFAULT_ACCOUNT():
    return site_text('PDONE_EMAIL_ADMIN')

def APPROVAL_LEDGER():
    return ROOT() / 'legacy-openclaw/workspace/state/admin-approval-tickets.jsonl'

def MATTERMOST_REVIEW_LOG():
    return ROOT() / 'tools/mattermost_review_log.py'

def SHEETS_SAFE_OPS():
    return ROOT() / 'scripts/sheets_safe_ops.py'

def DRIVE_ACL_AUTHORIZE():
    return ROOT() / 'tools/drive_acl_authorize.py'

def APPSHEET_TABLE_PROBE():
    return ROOT() / 'skills/appsheet-copilot/scripts/appsheet_table_probe.py'

def APPSHEET_ENV_FILES():
    return {'deployed': ROOT() / 'legacy-openclaw/workspace/projects/AppSheet/keydrop/deployed-app.env', 'prototype': ROOT() / 'legacy-openclaw/workspace/projects/AppSheet/keydrop/prototype-app.env'}

def APPSHEET_INCIDENT_MORNING_BRIEFING_SENDER():
    return ROOT() / 'legacy-openclaw/workspace/tools/send_appsheet_incident_morning_briefing.py'

def APPSHEET_INCIDENT_MORNING_BRIEFING_RETRY():
    return ROOT() / 'legacy-openclaw/workspace/tools/retry_appsheet_incident_morning_briefing.py'

def APPSHEET_INCIDENT_MORNING_BRIEFING_SCRIPT():
    return ROOT() / 'legacy-openclaw/workspace/tools/send_appsheet_incident_morning_briefing.py'

def DOCS_API():
    return ROOT() / 'legacy-openclaw/workspace/scripts/google/docs_api.py'

def ADMIN_APPROVAL_TOOLS():
    return ROOT() / 'legacy-openclaw/workspace/tools'

def ADMIN_APPROVAL_NOTIFY():
    return ADMIN_APPROVAL_TOOLS() / 'admin_approval_notify.py'

def ADMIN_APPROVAL_LISTENER():
    return ROOT() / 'tools/pd_one_admin_approval_listener.py'

def ADMIN_APPROVAL_EXECUTOR():
    return ROOT() / 'scripts/pd_one_admin_approval_executor.py'

def ADMIN_APPROVAL_EXECUTOR_CONFIG():
    return ROOT() / 'config/admin-approval-executor.json'

def ADMIN_APPROVAL_KANBAN_STATE():
    return ROOT() / 'state/admin-approval-kanban'

def KANBAN_BOARDS_ROOT():
    return Path(resolve_configured_path('~/.hermes/kanban/boards'))
ADMIN_APPROVAL_KANBAN_BOARD = 'pdapp-approvals'
ADMIN_APPROVAL_KANBAN_MAPPING_SCHEMA = 'pd-one.admin-approval-kanban-mapping.v1'
ADMIN_APPROVAL_EXECUTION_RESULT_SCHEMA = 'pd-one.admin-approval-execution-result.v1'
PDAPP_TICKET_ID_RE = re.compile('^PDAPP-\\d{8}-[A-F0-9]{8}$')
KANBAN_TASK_ID_RE = re.compile('^t_[a-z0-9]+$')
ADMIN_APPROVAL_KANBAN_JSON_MAX_BYTES = 256 * 1024

def MATTERMOST_POLICY_LOOKUP():
    return ROOT() / 'tools/mattermost_policy_lookup.py'

def DEFAULT_ADMIN_CHANNEL_ID():
    return site_text('PDONE_ADMIN_ALERT_CHANNEL_ID')

def DEFAULT_ANDY_USER_ID():
    return site_text('PDONE_OWNER_MM_USER_ID')

def ADMIN_ALERT_SOURCE_AUDIT_ROOTS():
    return (ROOT() / 'scripts', ROOT() / 'legacy-openclaw/workspace/tools')
ADMIN_ALERT_SOURCE_AUDIT_MAX_FILES = 300
ADMIN_ALERT_SOURCE_AUDIT_MAX_FILE_BYTES = 512 * 1024

def HR_POLICY_DOCUMENT_IDS():
    return {site_text('PDONE_GDOC_5'), site_text('PDONE_GDOC_6')}
MATTERMOST_CHANNEL_SETUP_CONFIRMATION = 'RUN LIVE MATTERMOST CHANNEL SETUP'
ADMIN_APPROVAL_DECISION_CONFIRMATION = 'RUN LIVE ADMIN APPROVAL DECISION'
ADMIN_APPROVAL_CANCEL_CONFIRMATION = 'CANCEL PDAPP TICKET'
CANCELLABLE_TICKET_STATUSES = frozenset({'queued', 'in_progress', 'approved'})

def DOC_ALLOWED_ROOTS():
    return [ROOT() / 'cache/documents', ROOT() / 'artifacts', ROOT() / 'tmp', ROOT() / 'legacy-openclaw/workspace/tmp', ROOT() / 'legacy-openclaw/workspace-employee/out']

def COMPANY_ANNOUNCEMENT_TEMPLATE():
    return ROOT() / 'skills/company-announcement-writer/references/pro-design-company-announcement-template.docx'
COMPANY_ANNOUNCEMENT_MAX_REPLACEMENTS = 40
COMPANY_ANNOUNCEMENT_MAX_REPLACEMENT_CHARS = 4000

def DOC_ALLOWED_FILES():
    return {ROOT() / 'skills/company-announcement-writer/references/pro-design-company-announcement-template.docx'}

def LOCAL_ARTIFACT_COPY_SOURCE_ROOT():
    return ROOT() / 'legacy-openclaw/workspace-employee/artifacts'

def LOCAL_ARTIFACT_COPY_DEST_ROOT():
    return ROOT() / 'artifacts'
LOCAL_ARTIFACT_COPY_ALLOWED_SUFFIXES = {'.doc', '.docx', '.gif', '.html', '.htm', '.jpeg', '.jpg', '.pdf', '.png', '.ppt', '.pptx', '.svg', '.webp', '.xls', '.xlsm', '.xlsx'}
LOCAL_ARTIFACT_COPY_MAX_BYTES = 50 * 1024 * 1024

def ARTIFACT_BASE64_ALLOWED_ROOTS():
    return [*DOC_ALLOWED_ROOTS(), ROOT() / 'legacy-openclaw/workspace-employee/exports']
ARTIFACT_BASE64_ALLOWED_SUFFIXES = {'.gif', '.jpeg', '.jpg', '.pdf', '.png', '.svg', '.webp'}
ARTIFACT_BASE64_MAX_BYTES = 2 * 1024 * 1024
SVG_INSPECT_MAX_BYTES = 2 * 1024 * 1024
SVG_INSPECT_MAX_ELEMENTS = 50000
SVG_INSPECT_MAX_IMAGES = 500
SVG_INSPECT_MAX_REQUIRED_TEXTS = 16
SVG_INSPECT_MAX_REQUIRED_TEXT_CHARS = 200
SVG_INSPECT_MAX_ATTR_CHARS = 256
PPTX_INSPECT_MAX_BYTES = 40 * 1024 * 1024
PPTX_INSPECT_MAX_SLIDES = 50
PPTX_INSPECT_MAX_SHAPES = 250
PPTX_INSPECT_MAX_PARAS = 12
PPTX_INSPECT_MAX_RUNS = 12
PPTX_INSPECT_MAX_TEXT = 240
PPTX_INSPECT_MAX_DEPTH = 8
ARTIFACT_BASE64_MIME_TYPES = {'.gif': 'image/gif', '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg', '.pdf': 'application/pdf', '.png': 'image/png', '.svg': 'image/svg+xml', '.webp': 'image/webp'}

def VIDEO_FRAME_INPUT_ROOT():
    return ROOT() / 'cache/documents'

def VIDEO_FRAME_OUTPUT_ROOT():
    return ROOT() / 'tmp/video-frame-sample'
VIDEO_FRAME_ALLOWED_SUFFIXES = {'.mp4', '.mov', '.mkv', '.webm'}
VIDEO_FRAME_MAX_SOURCE_BYTES = 2 * 1024 * 1024 * 1024
VIDEO_FRAME_MAX_DURATION_SECONDS = 8 * 60 * 60
VIDEO_FRAME_DEFAULT_FRACTIONS = (0.15, 0.5, 0.85)

def THREEMF_SLICER_INPUT_ROOTS():
    return [ROOT() / 'cache/documents', ROOT() / 'artifacts', ROOT() / 'tmp', ROOT() / 'legacy-openclaw/workspace-employee/artifacts']

def ARTIFACT_IDENTITY_INPUT_ROOTS():
    return list(THREEMF_SLICER_INPUT_ROOTS())
ARTIFACT_IDENTITY_ALLOWED_SUFFIXES = {'.3mf', '.gif', '.jpeg', '.jpg', '.png', '.step', '.stl', '.stp', '.svg', '.webp'}
ARTIFACT_IDENTITY_MAX_GLOBS = 8
ARTIFACT_IDENTITY_MAX_GLOB_CHARS = 80
ARTIFACT_IDENTITY_MAX_MATCHES = 40
ARTIFACT_IDENTITY_MAX_PEEK_BYTES = 16
ARTIFACT_IDENTITY_DEFAULT_PEEK_BYTES = 8

def THREEMF_SLICER_OUTPUT_ROOT():
    return ROOT() / 'tmp/3mf-slicer-inspect'
THREEMF_SLICER_MAX_SOURCE_BYTES = 80 * 1024 * 1024
THREEMF_SLICER_MAX_MEMBER_BYTES = 2 * 1024 * 1024
THREEMF_SLICER_MAX_NAMELIST = 200
THREEMF_SLICER_MAX_VALUE_CHARS = 200
THREEMF_SLICER_MAX_SETTINGS = 40
THREEMF_SLICER_MEMBERS = {'Metadata/Slic3r_PE.config': 'slicer_pe.config', 'Metadata/Slic3r_PE_model.config': 'slicer_pe_model.config', 'Metadata/thumbnail.png': 'thumbnail.png'}
THREEMF_SLICER_SETTING_KEYS = ('filament_type', 'layer_height', 'fill_density', 'perimeters', 'support_material', 'support_material_style', 'support_material_pattern', 'brim', 'brim_width', 'brim_type', 'printer_model', 'nozzle_diameter', 'first_layer_height', 'first_layer_temperature', 'first_layer_bed_temperature', 'fill_pattern', 'temperature', 'bed_temperature')

def CAD_RUNTIME_CANDIDATE_BINS():
    return (Path(resolve_configured_path('~/.local/bin/freecadcmd')), Path(resolve_configured_path('~/.local/bin/FreeCADCmd')), Path('/usr/bin/freecadcmd'), Path('/usr/bin/FreeCADCmd'))
CAD_RUNTIME_WHICH_NAMES = ('freecadcmd', 'FreeCADCmd', 'freecad', 'FreeCAD')

def CAD_RUNTIME_LIB_DIRS():
    return (Path('/usr/lib/freecad/lib'), Path('/usr/lib/freecad-python3/lib'), Path(resolve_configured_path('~/.local/lib')), Path('/opt/freecad'))
CAD_RUNTIME_DIR_SAMPLE = 8
CAD_3MF_PEEK_SUFFIXES = ('.model', '.json', '.xml', '.config')
CAD_3MF_MAX_PEEK_FILES = 8
CAD_3MF_PEEK_BYTES = 2048
CAD_3MF_NAMELIST_SAMPLE = 30

def SVG_EMBED_IMAGE_OUTPUT_ROOT():
    return ROOT() / 'tmp/svg-embed-image'
SVG_EMBED_IMAGE_ALLOWED_URL = 'https://tw.prodesign-group.com/img/logo.png'
SVG_EMBED_IMAGE_MAX_SVG_BYTES = 2 * 1024 * 1024
SVG_EMBED_IMAGE_MAX_REMOTE_BYTES = 512 * 1024
HERMES_RESULTS_ROOT = Path('/tmp/hermes-results')
HERMES_RESULT_SUMMARY_MAX_BYTES = 5 * 1024 * 1024
HERMES_RESULT_SUMMARY_MAX_MESSAGES = 200
HERMES_RESULT_SUMMARY_MAX_CONTENT_ITEMS = 32
HERMES_RESULT_SUMMARY_MAX_TEXT_CHARS = 240

def JSON_ARTIFACT_INSPECT_ROOTS():
    return (ROOT() / 'tmp', ROOT() / 'artifacts', ROOT() / 'cache/documents', ROOT() / 'legacy-openclaw/workspace/reports', ROOT() / 'legacy-openclaw/workspace/tmp')
JSON_ARTIFACT_INSPECT_MAX_FILES = 4
JSON_ARTIFACT_INSPECT_MAX_BYTES = 8 * 1024 * 1024
JSON_ARTIFACT_INSPECT_MAX_KEYS = 30
JSON_ARTIFACT_INSPECT_MAX_SAMPLE_KEYS = 20
JSON_ARTIFACT_INSPECT_KEY_CHARS = 80

def LOCAL_FILE_SEARCH_ROOTS():
    return (ROOT() / 'tests', ROOT() / 'tmp', ROOT() / 'artifacts', ROOT() / 'cache', ROOT() / 'scripts', ROOT() / 'docs', ROOT() / 'config', ROOT() / 'public', ROOT() / 'legacy-openclaw/workspace/reports', ROOT() / 'legacy-openclaw/workspace/tmp')
LOCAL_FILE_SEARCH_MAX_PATHS = 8
LOCAL_FILE_SEARCH_MAX_PATTERNS = 8
LOCAL_FILE_SEARCH_MAX_MATCHES = 30
LOCAL_FILE_SEARCH_MAX_WALK_FILES = 20000
LOCAL_FILE_SEARCH_MAX_PATTERN_CHARS = 120
DOCX_INSPECT_MAX_BYTES = 25 * 1024 * 1024
DOCX_INSPECT_MAX_TEXT_CHARS = 8000
DOCX_INSPECT_MAX_RUNS = 200
PPTX_OOXML_TEXT_INSPECT_MAX_BYTES = 50 * 1024 * 1024
PPTX_OOXML_TEXT_INSPECT_MAX_MEMBER_BYTES = 8 * 1024 * 1024
PPTX_OOXML_TEXT_INSPECT_MAX_MEMBERS = 12
PPTX_OOXML_TEXT_INSPECT_MAX_TEXTS = 80
PPTX_OOXML_TEXT_INSPECT_MAX_TEXT_CHARS = 200
PPTX_OOXML_TEXT_INSPECT_MEMBER_RE = re.compile('^ppt/(?:slides/slide|notesSlides/notesSlide|diagrams/data|charts/chart)([1-9]\\d{0,2})\\.xml$')
PPTX_OOXML_DRAWINGML_T = '{http://schemas.openxmlformats.org/drawingml/2006/main}t'
DOCX_LAYOUT_TARGET_MAX_CHARS = 500
XLSX_WORKBOOK_INSPECT_SUFFIXES = {'.xlsx', '.xlsm'}
XLSX_WORKBOOK_INSPECT_MAX_FILES = 12
XLSX_WORKBOOK_INSPECT_MAX_BYTES = 50 * 1024 * 1024
XLSX_WORKBOOK_INSPECT_MAX_SHEETS = 50
XLSX_WORKBOOK_INSPECT_MAX_ROWS = 500
XLSX_WORKBOOK_INSPECT_MAX_COLUMNS = 100
XLSX_WORKBOOK_INSPECT_MAX_CELL_CHARS = 2000

def SIP_THREAD_INDEX_ROOT():
    return ROOT() / 'legacy-openclaw/workspace-employee'

def SIP_THREAD_INDEX_SCRIPT():
    return SIP_THREAD_INDEX_ROOT() / 'build_sip_thread_index.py'

def SIP_THREAD_INDEX_OUTPUT():
    return SIP_THREAD_INDEX_ROOT() / 'SIP製作溝通_主題與連結.xlsx'

def ITEM_NUMBER_WORKFLOW_ROOT():
    return ROOT() / 'legacy-openclaw/workspace-employee/item-number-workflow'

def ITEM_NUMBER_COMPILER_ROOT():
    return ITEM_NUMBER_WORKFLOW_ROOT() / 'compiler'

def ITEM_NUMBER_COMPILER_SCRIPT():
    return ITEM_NUMBER_COMPILER_ROOT() / 'item_number_xlsx_compiler.py'

def ITEM_NUMBER_COMPILER_TEST():
    return ITEM_NUMBER_COMPILER_ROOT() / 'tests/test_item_number_xlsx_compiler.py'

def ITEM_NUMBER_SOURCE_XLS():
    return ITEM_NUMBER_WORKFLOW_ROOT() / 'historical-inspection/sample/10_2025_current_aip293_42.xls'

def ITEM_NUMBER_WORKFLOW_TMP_ROOT():
    return ROOT() / 'tmp/item-number-xlsx-compiler'

def EQUIPMENT_WORKBOOK_SCRIPT():
    return ROOT() / 'tools/pd_one_equipment_workbook.py'

def EQUIPMENT_WORKBOOK_TMP_ROOT():
    return ROOT() / 'tmp/equipment-workbook'
ITEM_NUMBER_SMOKE_TEMPLATE_NAME = '品號資料申請表20230306更新版發佈.xlsx'
ITEM_NUMBER_SMOKE_DISPLAY_NAME = '測試主管'
ITEM_NUMBER_SMOKE_CREATE_AT = 1784253600000
ITEM_NUMBER_SMOKE_USER_ID = 'a' * 26
ITEM_NUMBER_SMOKE_POST_ID = 'b' * 26
ITEM_NUMBER_SMOKE_ROUTE = 'special'
ITEM_NUMBER_SMOKE_FULFILLMENT_LINK = 'header_fulfills_step1'
ITEM_NUMBER_SMOKE_ROOT_POST_ID = 'c' * 26
ITEM_NUMBER_SMOKE_REVISION_HASH = hashlib.sha256(b'revision-1').hexdigest()
ITEM_NUMBER_SMOKE_COMMENTS = 'TEST FIXTURE ONLY'
SIP_THREAD_INDEX_INPUT_GLOBS = ('sip_threads_pd0_*.json', 'sip_threads_pd1_*.json', 'sip_threads_pd2_*.json')
SIP_THREAD_INDEX_NOISE_MARKERS = ('請協助', '發行', '謝謝', '異常回報', '修改', '新增', '增加', '刪除')

def ITEM_NUMBER_WORKFLOW_ENGINE():
    return ITEM_NUMBER_WORKFLOW_ROOT() / 'engine'

def ITEM_NUMBER_WORKFLOW_SCRIPT():
    return ITEM_NUMBER_WORKFLOW_ENGINE() / 'workflow_engine.py'

def ITEM_NUMBER_WORKFLOW_TEST():
    return ITEM_NUMBER_WORKFLOW_ENGINE() / 'tests/test_workflow_engine.py'

def ITEM_NUMBER_WORKFLOW_RUNNER():
    return ITEM_NUMBER_WORKFLOW_ROOT() / 'runner'

def ITEM_NUMBER_WORKFLOW_RUNNER_SCRIPT():
    return ITEM_NUMBER_WORKFLOW_RUNNER() / 'item_number_runner.py'

def ITEM_NUMBER_WORKFLOW_RUNNER_TEST():
    return ITEM_NUMBER_WORKFLOW_RUNNER() / 'tests/test_item_number_runner.py'

def ITEM_NUMBER_RENDER_QA_ROOT():
    return ITEM_NUMBER_WORKFLOW_ROOT() / 'qa-artifacts-final'

def ITEM_NUMBER_RENDER_QA_ARTIFACTS():
    return ITEM_NUMBER_RENDER_QA_ROOT() / 'qa-artifacts.json'

def ITEM_NUMBER_RENDER_QA_RESULTS():
    return ITEM_NUMBER_RENDER_QA_ROOT() / 'render-results.json'

def ITEM_NUMBER_RENDER_QA_TEST_REPORT():
    return ITEM_NUMBER_WORKFLOW_ROOT() / 'TEST_REPORT.md'

def ITEM_NUMBER_RENDER_QA_ADMIN_PACKET():
    return ITEM_NUMBER_WORKFLOW_ROOT() / 'ADMIN_EXECUTION_PACKET.md'

def ITEM_NUMBER_RENDER_QA_TEMPLATE():
    return ITEM_NUMBER_RENDER_QA_ROOT() / ITEM_NUMBER_SMOKE_TEMPLATE_NAME

def ITEM_NUMBER_HISTORICAL_ROOT():
    return ITEM_NUMBER_WORKFLOW_ROOT() / 'historical-inspection'

def ITEM_NUMBER_HISTORICAL_SCRIPT():
    return ITEM_NUMBER_WORKFLOW_ROOT() / 'tools/summarize_historical_sample.py'

def ITEM_NUMBER_HISTORICAL_RECEIPT():
    return ITEM_NUMBER_HISTORICAL_ROOT() / 'copyout-receipt.json'

def ITEM_NUMBER_HISTORICAL_OUTPUT():
    return ITEM_NUMBER_HISTORICAL_ROOT() / 'structural-summary.json'

def ITEM_NUMBER_LOCAL_QA_ROOT():
    return ROOT() / 'tmp/item-number-local-lo'

def ITEM_NUMBER_LOCAL_QA_RECEIPT():
    return ITEM_NUMBER_LOCAL_QA_ROOT() / 'local-libreoffice-render-qa.json'

def ITEM_NUMBER_LOCAL_QA_INPUTS():
    return {'source_xls': ITEM_NUMBER_SOURCE_XLS(), 'template': ITEM_NUMBER_RENDER_QA_TEMPLATE(), 'procurement': ITEM_NUMBER_RENDER_QA_ROOT() / 'procurement/品號資料申請表20230306更新版發佈-電子簽核.xlsx', 'production': ITEM_NUMBER_RENDER_QA_ROOT() / 'production/品號資料申請表20230306更新版發佈-電子簽核.xlsx', 'special': ITEM_NUMBER_RENDER_QA_ROOT() / 'special/品號資料申請表20230306更新版發佈-電子簽核.xlsx'}

def ECRN_APPROVAL_PILOT_STATE():
    return ROOT() / 'legacy-openclaw/workspace/state/ecrn-approval-pilot.json'

def ECRN_APPROVAL_PILOT_SCRIPT():
    return ROOT() / 'legacy-openclaw/workspace/tools/ecrn_approval_pilot.py'

def ECRN_CHANNEL_HEADER_TEST_ROOT():
    return ROOT() / 'legacy-openclaw/workspace'

def ECRN_CHANNEL_HEADER_SCRIPT():
    return ECRN_CHANNEL_HEADER_TEST_ROOT() / 'tools/ecrn_approval_pilot.py'

def ECRN_CHANNEL_HEADER_TEST():
    return ECRN_CHANNEL_HEADER_TEST_ROOT() / 'tests/test_ecrn_channel_header.py'

def ECRN_DOCX_PATCH_SCRIPT():
    return ROOT() / 'tools/pd_one_ecrn_docx_ops.py'

def PPTX_EXACT_TEXT_PATCH_SCRIPT():
    return ROOT() / 'tools/pd_one_pptx_ops.py'

def PPTX_FROM_TEMPLATE_SCRIPT():
    return ROOT() / 'tools/pd_one_pptx_from_template.py'
OFFICE_TO_PDF_INPUT_SUFFIXES = {'.csv', '.doc', '.docx', '.odp', '.ods', '.odt', '.ppt', '.pptx', '.rtf', '.xls', '.xlsm', '.xlsx'}
HTML_TO_DOCX_INPUT_SUFFIXES = {'.html', '.htm'}
OFFICE_VISUAL_QA_INPUT_SUFFIXES = {'.docx', '.pptx'}
OFFICE_HTML_TO_DOCX_INPUT_SUFFIXES = {'.html', '.htm'}
OFFICE_HTML_TO_DOCX_MAX_BYTES = 5 * 1024 * 1024
JSON_HTML_ARTIFACT_MAX_BYTES = 5 * 1024 * 1024
JSON_HTML_ARTIFACT_MAX_PARAGRAPHS = 2000
OFFICE_VISUAL_QA_MAX_BYTES = 50 * 1024 * 1024
OFFICE_VISUAL_QA_MAX_FILES = 200

def OFFICE_VISUAL_QA_SCRIPT():
    return ROOT() / 'skills/visual-office-qa/scripts/office_visual_qa.py'
OFFICE_DOCPROPS_INPUT_SUFFIXES = {'.docm', '.docx', '.potx', '.pptm', '.pptx', '.xlsm', '.xlsx', '.xltx'}
OFFICE_DOCPROPS_MAX_SOURCE_BYTES = 50 * 1024 * 1024
OFFICE_DOCPROPS_MAX_MEMBER_BYTES = 64 * 1024
OFFICE_DOCPROPS_MAX_FIELD_CHARS = 200
OFFICE_DOCPROPS_MAX_NAMELIST = 400
OFFICE_DOCPROPS_MEMBERS = ('docProps/core.xml', 'docProps/app.xml')
OFFICE_DOCPROPS_CORE_FIELDS = ('title', 'subject', 'creator', 'description', 'lastModifiedBy', 'revision', 'created', 'modified', 'language', 'category', 'keywords', 'identifier', 'version', 'contentStatus')
OFFICE_DOCPROPS_APP_FIELDS = ('Application', 'AppVersion', 'PresentationFormat', 'Slides', 'Notes', 'HiddenSlides', 'Words', 'Paragraphs', 'Pages', 'Company', 'Template', 'TotalTime', 'Lines', 'Characters', 'CharactersWithSpaces', 'DocSecurity', 'ScaleCrop', 'LinksUpToDate', 'SharedDoc', 'HyperlinksChanged')
OFFICE_DOCPROPS_INT_FIELDS = {'Characters', 'CharactersWithSpaces', 'DocSecurity', 'HiddenSlides', 'Lines', 'Notes', 'Pages', 'Paragraphs', 'Slides', 'TotalTime', 'Words', 'revision'}

def OFFICE_DEB_ALLOWED_ROOT():
    return Path(resolve_configured_path('~/.local/office-visual-qa/apt-debs'))
OFFICE_DEB_CONTENT_MAX_LINES = 2000
OFFICE_TOOLCHAIN_BINARIES = ('ssconvert', 'gnumeric', 'soffice', 'libreoffice', 'pdftoppm', 'pdfinfo', 'python3')

def _path_text(value: object) -> str:
    """Coerce a path entry to str. ``resolve_configured_path`` returns a Path."""
    if value is None:
        return ''
    if isinstance(value, os.PathLike):
        return os.fspath(value)
    return str(value)

def PATH_BASE():
    entries = (ROOT() / 'home/.local/bin', resolve_configured_path('~/.local/bin'), '/usr/local/bin', '/usr/bin', '/bin')
    return os.pathsep.join(_path_text(entry) for entry in entries)

def TYPHOON_AUTOMATION_SCRIPT():
    return ROOT() / 'scripts/pd_one_typhoon_automation.py'

def TYPHOON_AUTOMATION_TEST():
    return ROOT() / 'tests/test_pd_one_typhoon_automation.py'

def TYPHOON_AUTOMATION_FIXTURE_ROOTS():
    return [ROOT() / 'tests/fixtures', ROOT() / 'tmp/typhoon-automation']
TYPHOON_AUTOMATION_LIVE_CONFIRMATION = 'RUN LIVE TYPHOON AUTOMATION'

def TYPHOON_AUTOMATION_SWEEP_STATE_FILE():
    return ROOT() / 'tmp/typhoon-automation/sweep-state.json'

def PYTHON_DOCX_REPAIR_TICKET_ID():
    return site_text('PDONE_DOCX_REPAIR_TICKET_ID')
PYTHON_DOCX_REPAIR_PACKAGE = 'python-docx'
PYTHON_DOCX_REPAIR_VERSION = '1.2.0'

def PYTHON_DOCX_REPAIR_PYTHON():
    return Path(resolve_configured_path('~/.hermes/releases/pdone-current/.venv/bin/python'))

def PYTHON_DOCX_REPAIR_CONFIRMATION():
    return 'RUN LIVE PYTHON DOCX DEPENDENCY REPAIR ' + site_text('PDONE_DOCX_REPAIR_TICKET_ID')

def TYPHOON_AUTOMATION_SWEEP_CASES():
    return [{'case': 'low', 'fixture': ROOT() / 'tests/fixtures/typhoon_low.json', 'now': '2026-07-13T08:00:00+08:00'}, {'case': 'high-first', 'fixture': ROOT() / 'tests/fixtures/typhoon_high_first.json', 'now': '2026-07-13T08:00:00+08:00'}, {'case': 'high-second', 'fixture': ROOT() / 'tests/fixtures/typhoon_high_second.json', 'now': '2026-07-13T10:00:00+08:00'}, {'case': 'land-warning', 'fixture': ROOT() / 'tests/fixtures/typhoon_land_warning.json', 'now': '2026-07-13T10:00:00+08:00'}, {'case': 'dgpa-merit', 'fixture': ROOT() / 'tests/fixtures/typhoon_dgpa_merit.json', 'now': '2026-07-13T10:00:00+08:00'}]
SYSSTAT_LOG_ROOT = Path('/var/log/sysstat')
SYSSTAT_SUMMARY_DEFAULT_HOURS = 12
SYSSTAT_SUMMARY_MAX_HOURS = 72
SYSSTAT_SUMMARY_METRIC_SPECS = (('cpu', ['-u'], ['%user', '%nice', '%system', '%iowait', '%steal', '%idle']), ('load', ['-q'], ['runq-sz', 'plist-sz', 'ldavg-1', 'ldavg-5', 'ldavg-15', 'blocked']), ('cpu_pressure', ['-q', 'CPU'], ['%scpu-10', '%scpu-60', '%scpu-300', '%scpu']), ('io_pressure', ['-q', 'IO'], ['%sio-10', '%sio-60', '%sio-300', '%sio', '%fio-10', '%fio-60', '%fio-300', '%fio']), ('memory_pressure', ['-q', 'MEM'], ['%smem-10', '%smem-60', '%smem-300', '%smem', '%fmem-10', '%fmem-60', '%fmem-300', '%fmem']), ('memory', ['-r'], ['kbmemfree', 'kbavail', 'kbmemused', '%memused', 'kbcommit', '%commit']), ('swap', ['-S'], ['kbswpfree', 'kbswpused', '%swpused', 'kbswpcad', '%swpcad']), ('swap_activity', ['-W'], ['pswpin/s', 'pswpout/s']))
OLLAMA_EMBEDDING_UNIT = 'pd-neo-ollama.service'
OLLAMA_EMBEDDING_PORT = 11434
OLLAMA_EMBEDDING_CONTAINER = 'honcho-pd-neo-api-1'
OLLAMA_EMBEDDING_PEER_CONTAINER = 'honcho-pd-neo-deriver-1'
OLLAMA_EMBEDDING_MAX_CONTAINER_TAIL_LINES = 20000
OLLAMA_EMBEDDING_MAX_JOURNAL_TAIL_LINES = 2000
OLLAMA_EMBEDDING_LOG_PATTERNS = {'embedding_mentions': re.compile('embedd', re.I), 'connection_refused': re.compile('connection refused|errno 111', re.I), 'connection_timeout': re.compile('timed? ?out|timeout', re.I), 'authentication_error': re.compile('authenticationerror|401|unauthorized', re.I), 'retrying_requests': re.compile('retrying request', re.I), 'ollama_mentions': re.compile('ollama|bge-m3', re.I), 'successful_http_200': re.compile('HTTP/1\\.[01].* 200\\b', re.I), 'httpx_connect_error': re.compile('httpx\\.ConnectError|All connection attempts failed', re.I), 'api_connection_error': re.compile('openai\\.APIConnectionError|Connection error\\.', re.I)}
OLLAMA_EMBEDDING_WATCHDOG_UNIT = 'pd-neo-embedding-endpoint-watchdog.service'
OLLAMA_EMBEDDING_WATCHDOG_MAX_JOURNAL_TAIL_LINES = 4000
OLLAMA_EMBEDDING_WATCHDOG_LOG_PATTERNS = {'remote_ok_true': re.compile('\\bremote_ok=True\\b'), 'remote_ok_false': re.compile('\\bremote_ok=False\\b'), 'mode_remote': re.compile('\\bmode=remote\\b'), 'mode_local': re.compile('\\bmode=local\\b'), 'switch_events': re.compile('switched Honcho embeddings', re.I), 'service_failures': re.compile('Failed with result|status=1/FAILURE', re.I)}
LOCAL_PROCESS_LISTENER_PORTS = {8646: 'pdone_line_gateway', 8766: 'pdone_protected_portal', 8765: 'hermes_dashboard'}
LOCAL_PROCESS_LISTENER_DEFAULT_PORTS = (8646, 8766)
LOCAL_PROCESS_LISTENER_MAX_PORTS = 3
LOCAL_PROCESS_LISTENER_MAX_PIDS = 8
LOCAL_PROCESS_LISTENER_CMD_CAP = 200
LOCAL_PROCESS_LISTENER_SS_PID_RE = re.compile('pid=(\\d+)')
LOCAL_PROCESS_LISTENER_SS_COMM_RE = re.compile('users:\\(\\("([^"]+)"')
PROTECTED_PORTAL_ORIGIN_HOST = '127.0.0.1'
PROTECTED_PORTAL_ORIGIN_PORT = 8766
PROTECTED_PORTAL_ORIGIN_TIMEOUT_SEC = 15
PROTECTED_PORTAL_ORIGIN_BODY_CAP = 256 * 1024
PROTECTED_PORTAL_ORIGIN_TITLE_CAP = 80

def PROTECTED_PORTAL_MANIFEST():
    return ROOT() / 'config/public_portal_pages.json'
PROTECTED_PORTAL_UNKNOWN_EMAIL = 'nobody@example.com'

def PROTECTED_PORTAL_ADMIN_EMAIL():
    return site_text('PDONE_EMAIL_ADMIN')

def PROTECTED_PORTAL_DEFAULT_PROBES():
    return ({'label': 'anon_/', 'path': '/', 'email': None}, {'label': 'anon_/qa/', 'path': '/qa/', 'email': None}, {'label': 'unknown_/qa/', 'path': '/qa/', 'email': PROTECTED_PORTAL_UNKNOWN_EMAIL}, {'label': 'admin_/', 'path': '/', 'email': PROTECTED_PORTAL_ADMIN_EMAIL()}, {'label': 'admin_/qa/', 'path': '/qa/', 'email': PROTECTED_PORTAL_ADMIN_EMAIL()})

def fail(msg: str, code: int=2) -> None:
    print(json.dumps({'status': 'error', 'error': msg}, ensure_ascii=False, indent=2))
    raise SystemExit(code)

def emit(data: Any) -> None:
    from tools.pd_one_ops.hr_guard import guard_hr_payload
    data = guard_hr_payload(data)
    print(json.dumps(data, ensure_ascii=False, indent=2))

def enforce_drive_acl(file_id: str, requester_user_id: str | None, *, need: str) -> dict[str, Any] | None:
    """Fail closed for employee Docs/Sheets paths when a Mattermost user id is supplied."""
    user_id = str(requester_user_id or '').strip()
    if not user_id:
        return None
    if not DRIVE_ACL_AUTHORIZE().is_file():
        fail('drive ACL helper missing')
    data = run_json([sys.executable, str(DRIVE_ACL_AUTHORIZE()), '--file-id', file_id, '--mattermost-user-id', user_id, '--redact'], timeout=120)
    if not isinstance(data, dict):
        fail('drive ACL helper returned invalid receipt')
    if need == 'write' and (not data.get('canWrite')):
        fail(f'drive ACL denied write via={data.get('via') or 'none'} reason={data.get('reason') or 'denied'}')
    if need == 'read' and (not data.get('canRead')):
        fail(f'drive ACL denied read via={data.get('via') or 'none'} reason={data.get('reason') or 'denied'}')
    return data

def safe_env() -> dict[str, str]:
    env = os.environ.copy()
    env['PATH'] = _path_text(PATH_BASE()) + os.pathsep + _path_text(env.get('PATH', ''))
    env.setdefault('HOME', str(ROOT() / 'home'))
    return env

def find_bin(name: str, extra: list[str] | None=None) -> str | None:
    for c in extra or []:
        candidate = _path_text(c)
        if candidate and Path(candidate).exists() and os.access(candidate, os.X_OK):
            return candidate
    return shutil.which(name, path=_path_text(PATH_BASE()) + os.pathsep + _path_text(site_text('PATH')))

def run_json(cmd: list[str], timeout: int=120) -> Any:
    proc = subprocess.run(cmd, text=True, capture_output=True, env=safe_env(), shell=False, timeout=timeout)
    if proc.returncode != 0:
        fail(f'command failed rc={proc.returncode}: {proc.stderr.strip()[:800] or proc.stdout.strip()[:800]}', proc.returncode)
    out = proc.stdout.strip()
    if not out:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'raw_stdout': out}

def run_capture(cmd: list[str], timeout: int=120, cwd: str | None=None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=safe_env(), shell=False, timeout=timeout)

def tail_text(text: str, limit: int=1200) -> str:
    return (text or '')[-limit:]

def normalize_email(v: str) -> str:
    s = (v or '').strip().lower()
    if not re.match('^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$', s):
        fail(f'invalid email: {v!r}')
    return s

def cmd_registry_list(args: argparse.Namespace) -> None:
    if not REGISTRY().exists():
        fail(f'registry not found: {REGISTRY()}')
    emit({'status': 'ok', 'registry': str(REGISTRY()), 'content': REGISTRY().read_text(encoding='utf-8')})
SHEETS_GET_RENDER_OPTIONS = ('FORMATTED_VALUE', 'UNFORMATTED_VALUE', 'FORMULA')

def cmd_sheets_get_range(args: argparse.Namespace) -> None:
    """Read a bounded Google Sheets range through the shared safe helper."""
    enforce_drive_acl(args.spreadsheet_id, getattr(args, 'requester_user_id', None), need='read')
    if not SHEETS_SAFE_OPS().exists():
        fail(f'sheets safe-op helper not found: {SHEETS_SAFE_OPS()}')
    cell_range = (args.range or '').strip()
    if not cell_range or len(cell_range) > 240:
        fail('--range is required and must be <= 240 characters')
    retries = max(1, min(int(args.retries), 5))
    render = str(getattr(args, 'render', '') or '').strip()
    if render and render not in SHEETS_GET_RENDER_OPTIONS:
        fail('--render must be FORMATTED_VALUE, UNFORMATTED_VALUE, or FORMULA')
    cmd = [sys.executable, str(SHEETS_SAFE_OPS()), 'get', args.spreadsheet_id, cell_range, '--account', args.account, '--retries', str(retries)]
    if args.include_values:
        cmd.append('--print-values')
    if render:
        cmd.extend(['--render', render])
    data = run_json(cmd, timeout=max(150, 135 * retries))
    if isinstance(data, dict):
        data.setdefault('capability', 'pd_one_sheets_get_range')
        data.setdefault('safety', {'read_only': True, 'shell_used': False, 'transient_retry_attempts': retries})
        if render:
            data['render'] = render
    emit(data)
CACHED_SHEET_JSON_MAX_BYTES = 20 * 1024 * 1024
CACHED_SHEET_JSON_MAX_ROWS = 10000
CACHED_SHEET_JSON_MAX_COLS = 200
CACHED_SHEET_JSON_MAX_TERMS = 8
CACHED_SHEET_JSON_MAX_COLUMNS = 12
CACHED_SHEET_JSON_MAX_MATCHES = 30
CACHED_SHEET_JSON_CELL_CHARS = 200
CACHED_SHEET_JSON_TERM_CHARS = 128
DEST_REST_COUNT_MAX_WORKERS = 8
DEST_REST_COUNT_NAME_CHARS = 80
DEST_REST_COUNT_MAX_DAYS = 31
DEST_REST_COUNT_DEFAULT_MARKERS = ('V',)

def cmd_cached_sheet_json_search(args: argparse.Namespace) -> None:
    cell = _PdUnset
    column = _PdUnset
    columns_used = _PdUnset
    folded_terms = _PdUnset
    header_idx = _PdUnset
    header_row = _PdUnset
    headers = _PdUnset
    matches = _PdUnset
    matches_truncated = _PdUnset
    max_matches = _PdUnset
    missing_columns = _PdUnset
    path = _PdUnset
    payload = _PdUnset
    size = _PdUnset
    term = _PdUnset
    term_counts = _PdUnset
    terms = _PdUnset
    values = _PdUnset

    def _pd_phase_1():
        nonlocal columns_used, folded_terms, header_idx, header_row, headers, matches, matches_truncated, max_matches, missing_columns, path, payload, size, term_counts, terms, values
        'Search one cached Sheets values JSON dump without execute_code.'
        raw_input = Path(str(args.input or '')).expanduser()
        if raw_input.is_symlink():
            fail('cached-sheet-json-search refuses symlinks')
        path = require_pdone_tmp_path(str(raw_input), '--input')
        if path.suffix.lower() != '.json':
            fail('cached-sheet-json-search input must be .json')
        if not path.is_file() or path.is_symlink():
            fail('cached-sheet-json-search input must be a regular file')
        size = int(path.stat().st_size)
        if size > CACHED_SHEET_JSON_MAX_BYTES:
            fail('cached-sheet-json-search input exceeds 20 MiB')
        terms = [str(term).strip() for term in args.term or [] if str(term).strip()]
        if not terms:
            fail('cached-sheet-json-search requires at least one --term')
        if len(terms) > CACHED_SHEET_JSON_MAX_TERMS:
            fail('cached-sheet-json-search accepts at most 8 terms')
        if any((len(term) > CACHED_SHEET_JSON_TERM_CHARS for term in terms)):
            fail('cached-sheet-json-search terms must be at most 128 characters')
        requested_columns = [str(column).strip() for column in args.column or [] if str(column).strip()]
        if len(requested_columns) > CACHED_SHEET_JSON_MAX_COLUMNS:
            fail('cached-sheet-json-search accepts at most 12 columns')
        if any((len(column) > 64 for column in requested_columns)):
            fail('cached-sheet-json-search column names must be at most 64 characters')
        header_row = int(args.header_row)
        if header_row < 1 or header_row > CACHED_SHEET_JSON_MAX_ROWS:
            fail('header-row must be a 1-based sheet row between 1 and 10000')
        max_matches = max(1, min(int(args.max_matches), CACHED_SHEET_JSON_MAX_MATCHES))
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            fail(f'cached-sheet-json-search could not parse JSON: {exc}')
        if not isinstance(payload, dict):
            fail('cached-sheet-json-search input must be a JSON object')
        values = payload.get('values')
        if not isinstance(values, list):
            fail('cached-sheet-json-search input must contain a values array')
        if len(values) > CACHED_SHEET_JSON_MAX_ROWS:
            fail('cached-sheet-json-search values exceed 10000 rows')
        header_idx = header_row - 1
        if header_idx >= len(values):
            fail('header-row is past the last cached row')
        headers_raw = values[header_idx]
        if not isinstance(headers_raw, list):
            fail('header row must be a list')
        headers = ['' if cell is None else str(cell) for cell in headers_raw[:CACHED_SHEET_JSON_MAX_COLS]]
        colmap = {name: index for index, name in enumerate(headers) if name}
        missing_columns = [name for name in requested_columns if name not in colmap]
        columns_used = [{'name': name, 'index': colmap[name]} for name in requested_columns if name in colmap]
        folded_terms = [(term, term.casefold()) for term in terms]
        matches = []
        matches_truncated = False
        term_counts = {term: 0 for term in terms}

    def _pd_phase_2():
        nonlocal cell, column, matches_truncated, term
        for offset, row in enumerate(values[header_idx + 1:]):
            if not isinstance(row, list):
                continue
            bounded_row = row[:CACHED_SHEET_JSON_MAX_COLS]
            haystack = ' '.join(('' if cell is None else str(cell) for cell in bounded_row)).casefold()
            matched_terms = [term for term, folded in folded_terms if folded in haystack]
            if not matched_terms:
                continue
            for term in matched_terms:
                term_counts[term] += 1
            if len(matches) >= max_matches:
                matches_truncated = True
                continue
            fields: dict[str, str] = {}
            for column in columns_used:
                idx = int(column['index'])
                cell = bounded_row[idx] if idx < len(bounded_row) else ''
                text = '' if cell is None else str(cell)
                fields[str(column['name'])] = text[:CACHED_SHEET_JSON_CELL_CHARS]
            matches.append({'sheet_row': header_row + 1 + offset, 'matched_terms': matched_terms, 'fields': fields})
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sheet_range = payload.get('range')
        emit({'status': 'ok', 'capability': 'pd_one_cached_sheet_json_search', 'input': {'path': str(path), 'size_bytes': size, 'sha256': digest}, 'range': sheet_range if isinstance(sheet_range, str) else None, 'nrows': len(values), 'header_row': header_row, 'header_count': len(headers), 'columns_used': columns_used, 'missing_columns': missing_columns, 'term_count': len(terms), 'term_counts': term_counts, 'match_count': len(matches), 'matches_truncated': matches_truncated, 'matches': matches, 'safety': {'read_only': True, 'admin_only': True, 'shell_used': False, 'bounded_inputs': True, 'full_rows_returned': False, 'arbitrary_regex_forbidden': True, 'source_system_writes_forbidden': True, 'external_delivery_forbidden': True}})
    _pd_result = _pd_phase_1()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
    _pd_result = _pd_phase_2()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value

def _dest_rest_day_number(cell: Any) -> int | None:
    text = str(cell or '').strip()
    if not text.isdigit():
        return None
    number = int(text)
    if 1 <= number <= DEST_REST_COUNT_MAX_DAYS:
        return number
    return None

def cmd_cached_dest_rest_count(args: argparse.Namespace) -> None:
    header_idx = _PdUnset
    header_row = _PdUnset
    headers_raw = _PdUnset
    marker = _PdUnset
    marker_set = _PdUnset
    markers = _PdUnset
    name_index = _PdUnset
    path = _PdUnset
    payload = _PdUnset
    size = _PdUnset
    terms = _PdUnset
    values = _PdUnset
    window_end = _PdUnset
    window_start = _PdUnset

    def _pd_phase_3():
        nonlocal header_idx, header_row, headers_raw, marker_set, markers, name_index, path, payload, size, terms, values, window_end, window_start
        'Count dest rest markers for named workers in one cached Sheets dump.'
        raw_input = Path(str(args.input or '')).expanduser()
        if raw_input.is_symlink():
            fail('cached-dest-rest-count refuses symlinks')
        path = require_pdone_tmp_path(str(raw_input), '--input')
        if path.suffix.lower() != '.json':
            fail('cached-dest-rest-count input must be .json')
        if not path.is_file() or path.is_symlink():
            fail('cached-dest-rest-count input must be a regular file')
        size = int(path.stat().st_size)
        if size > CACHED_SHEET_JSON_MAX_BYTES:
            fail('cached-dest-rest-count input exceeds 20 MiB')
        terms = [str(term).strip() for term in args.term or [] if str(term).strip()]
        if not terms:
            fail('cached-dest-rest-count requires at least one --term')
        if len(terms) > CACHED_SHEET_JSON_MAX_TERMS:
            fail('cached-dest-rest-count accepts at most 8 terms')
        if any((len(term) > CACHED_SHEET_JSON_TERM_CHARS for term in terms)):
            fail('cached-dest-rest-count terms must be at most 128 characters')
        markers = [str(marker).strip() for marker in args.marker or [] if str(marker).strip()]
        if not markers:
            markers = list(DEST_REST_COUNT_DEFAULT_MARKERS)
        if len(markers) > 8:
            fail('cached-dest-rest-count accepts at most 8 markers')
        marker_set = {marker.casefold() for marker in markers}
        header_row = int(args.header_row)
        if header_row < 1 or header_row > CACHED_SHEET_JSON_MAX_ROWS:
            fail('header-row must be a 1-based sheet row between 1 and 10000')
        name_index = int(args.name_index)
        if name_index < 0 or name_index >= CACHED_SHEET_JSON_MAX_COLS:
            fail('name-index must be between 0 and 199')
        window_start = int(args.window_start) if args.window_start is not None else None
        window_end = int(args.window_end) if args.window_end is not None else None
        if window_start is not None and (window_start < 1 or window_start > DEST_REST_COUNT_MAX_DAYS):
            fail('window-start must be 1-31')
        if window_end is not None and (window_end < 1 or window_end > DEST_REST_COUNT_MAX_DAYS):
            fail('window-end must be 1-31')
        if window_start is not None and window_end is not None and (window_start > window_end):
            fail('window-start must be <= window-end')
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            fail(f'cached-dest-rest-count could not parse JSON: {exc}')
        if not isinstance(payload, dict):
            fail('cached-dest-rest-count input must be a JSON object')
        values = payload.get('values')
        if not isinstance(values, list):
            fail('cached-dest-rest-count input must contain a values array')
        if len(values) > CACHED_SHEET_JSON_MAX_ROWS:
            fail('cached-dest-rest-count values exceed 10000 rows')
        header_idx = header_row - 1
        if header_idx >= len(values):
            fail('header-row is past the last cached row')
        headers_raw = values[header_idx]

    def _pd_phase_4():
        nonlocal marker
        if not isinstance(headers_raw, list):
            fail('header row must be a list')
        headers = ['' if cell is None else str(cell) for cell in headers_raw[:CACHED_SHEET_JSON_MAX_COLS]]
        date_start_index = int(args.date_start_index)
        detected = False
        if date_start_index < 0:
            detected = True
            date_start_index = next((idx for idx, cell in enumerate(headers) if _dest_rest_day_number(cell) is not None), -1)
        if date_start_index < 0 or date_start_index >= CACHED_SHEET_JSON_MAX_COLS:
            fail('could not detect a 1-31 day-number header; pass --date-start-index')
        date_headers: list[int | None] = []
        for offset, cell in enumerate(headers[date_start_index:]):
            number = _dest_rest_day_number(cell)
            date_headers.append(number if number is not None else offset + 1)
            if len(date_headers) >= DEST_REST_COUNT_MAX_DAYS:
                break
        folded_terms = [(term, term.casefold()) for term in terms]
        workers: list[dict[str, Any]] = []
        truncated = False
        for offset, row in enumerate(values[header_idx + 1:]):
            if not isinstance(row, list):
                continue
            bounded_row = row[:CACHED_SHEET_JSON_MAX_COLS]
            name_cell = bounded_row[name_index] if name_index < len(bounded_row) else ''
            name_text = '' if name_cell is None else str(name_cell)
            haystack = name_text.casefold()
            matched_terms = [term for term, folded in folded_terms if folded and folded in haystack]
            if not matched_terms:
                continue
            if len(workers) >= DEST_REST_COUNT_MAX_WORKERS:
                truncated = True
                continue
            rest_days: list[int] = []
            for col_offset, day_number in enumerate(date_headers):
                if day_number is None:
                    continue
                if window_start is not None and day_number < window_start:
                    continue
                if window_end is not None and day_number > window_end:
                    continue
                idx = date_start_index + col_offset
                cell = bounded_row[idx] if idx < len(bounded_row) else ''
                marker = ('' if cell is None else str(cell)).strip().casefold()
                if marker in marker_set:
                    rest_days.append(int(day_number))
            workers.append({'sheet_row': header_row + 1 + offset, 'name': name_text[:DEST_REST_COUNT_NAME_CHARS], 'matched_terms': matched_terms, 'rest_count': len(rest_days), 'rest_days': rest_days})
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sheet_range = payload.get('range')
        emit({'status': 'ok', 'capability': 'pd_one_cached_dest_rest_count', 'input': {'path': str(path), 'size_bytes': size, 'sha256': digest}, 'range': sheet_range if isinstance(sheet_range, str) else None, 'nrows': len(values), 'header_row': header_row, 'name_index': name_index, 'date_start_index': date_start_index, 'date_start_detected': detected, 'markers': markers, 'window_start': window_start, 'window_end': window_end, 'worker_count': len(workers), 'workers_truncated': truncated, 'workers': workers, 'safety': {'read_only': True, 'admin_only': True, 'shell_used': False, 'bounded_inputs': True, 'full_rows_returned': False, 'arbitrary_regex_forbidden': True, 'source_system_writes_forbidden': True, 'external_delivery_forbidden': True}})
    _pd_result = _pd_phase_3()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
    _pd_result = _pd_phase_4()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value

def require_pdone_tmp_path(path_text: str, label: str) -> Path:
    path = Path(path_text).expanduser().resolve(strict=False)
    allowed = [ROOT() / 'tmp', ROOT() / 'artifacts', ROOT() / 'cache']
    if not any((str(path).startswith(str(root.resolve()) + os.sep) or path == root.resolve() for root in allowed)):
        fail(f'{label} must be under an approved PD One tmp/artifacts/cache root: {path}')
    return path

def require_under_roots(path_text: str, label: str, roots: list[Path]) -> Path:
    path = Path(path_text).expanduser().resolve(strict=False)
    resolved_roots = [root.resolve() for root in roots]
    if not any((str(path).startswith(str(root) + os.sep) or path == root for root in resolved_roots)):
        fail(f'{label} must be under an approved PD One root: {path}')
    return path

def cmd_sheets_batch_update(args: argparse.Namespace) -> None:
    """Run file-backed Sheets batch update through the shared helper."""
    if args.live:
        enforce_drive_acl(args.spreadsheet_id, getattr(args, 'requester_user_id', None), need='write')
    if not SHEETS_SAFE_OPS().exists():
        fail(f'sheets safe-op helper not found: {SHEETS_SAFE_OPS()}')
    data_json = require_pdone_tmp_path(args.data_json, '--data-json')
    if not data_json.is_file():
        fail(f'--data-json not found: {data_json}')
    receipt = require_pdone_tmp_path(args.receipt, '--receipt') if args.receipt else None
    retries = max(1, min(int(args.retries), 5))
    cmd = [sys.executable, str(SHEETS_SAFE_OPS()), 'batch-update', args.spreadsheet_id, '--data-json', str(data_json), '--account', args.account, '--input', args.input, '--retries', str(retries)]
    for readback in args.readback or []:
        if not readback or len(readback) > 240:
            fail('--readback ranges must be non-empty and <= 240 characters')
        cmd += ['--readback', readback]
    if args.live:
        if args.confirm_live_write != 'RUN LIVE SHEETS BATCH UPDATE':
            fail("live Sheets batch update requires --confirm-live-write 'RUN LIVE SHEETS BATCH UPDATE'")
        cmd.append('--live')
        if not args.readback:
            fail('live Sheets batch update requires at least one --readback range')
    if receipt:
        cmd += ['--receipt', str(receipt)]
    data = run_json(cmd, timeout=max(180, 135 * retries))
    if isinstance(data, dict):
        data.setdefault('capability', 'pd_one_sheets_batch_update_live' if args.live else 'pd_one_sheets_batch_update_dry_run')
        data.setdefault('safety', {'shell_used': False, 'live_write_requested': bool(args.live), 'readback_required_for_live': True})
    emit(data)

def cmd_sheets_append(args: argparse.Namespace) -> None:
    """Run chunked Sheets append through the shared safe helper."""
    if args.live:
        enforce_drive_acl(args.spreadsheet_id, getattr(args, 'requester_user_id', None), need='write')
    if not SHEETS_SAFE_OPS().exists():
        fail(f'sheets safe-op helper not found: {SHEETS_SAFE_OPS()}')
    values_json = require_pdone_tmp_path(args.values_json, '--values-json')
    if not values_json.is_file():
        fail(f'--values-json not found: {values_json}')
    receipt = require_pdone_tmp_path(args.receipt, '--receipt') if args.receipt else None
    if not args.range or len(args.range) > 240:
        fail('--range is required and must be <= 240 characters')
    cmd = [sys.executable, str(SHEETS_SAFE_OPS()), 'append', args.spreadsheet_id, args.range, '--values-json', str(values_json), '--account', args.account, '--chunk-size', str(max(1, min(int(args.chunk_size), 200))), '--input', args.input, '--insert', args.insert]
    if args.live:
        if args.confirm_live_write != 'RUN LIVE SHEETS APPEND':
            fail("live Sheets append requires --confirm-live-write 'RUN LIVE SHEETS APPEND'")
        cmd.append('--live')
    if receipt:
        cmd += ['--receipt', str(receipt)]
    data = run_json(cmd, timeout=300)
    if isinstance(data, dict):
        data.setdefault('capability', 'pd_one_sheets_append_live' if args.live else 'pd_one_sheets_append_dry_run')
        data.setdefault('safety', {'shell_used': False, 'live_write_requested': bool(args.live), 'chunked': True})
    emit(data)

def cmd_sheets_header_update_row(args: argparse.Namespace) -> None:
    """Resolve a row by header/key and update by header names through the safe helper."""
    if args.live:
        enforce_drive_acl(args.spreadsheet_id, getattr(args, 'requester_user_id', None), need='write')
    if not SHEETS_SAFE_OPS().exists():
        fail(f'sheets safe-op helper not found: {SHEETS_SAFE_OPS()}')
    values_json = require_pdone_tmp_path(args.values_json, '--values-json')
    if not values_json.is_file():
        fail(f'--values-json not found: {values_json}')
    receipt = require_pdone_tmp_path(args.receipt, '--receipt') if args.receipt else None
    retries = max(1, min(int(args.retries), 5))
    cmd = [sys.executable, str(SHEETS_SAFE_OPS()), 'header-update-row', args.spreadsheet_id, '--sheet', args.sheet, '--key-header', args.key_header, '--key-value', args.key_value, '--values-json', str(values_json), '--account', args.account, '--max-column', args.max_column, '--max-rows', str(max(1, min(int(args.max_rows), 50000))), '--input', args.input, '--retries', str(retries)]
    if args.live:
        if args.confirm_live_write != 'RUN LIVE SHEETS HEADER UPDATE ROW':
            fail("live Sheets header update row requires --confirm-live-write 'RUN LIVE SHEETS HEADER UPDATE ROW'")
        cmd.append('--live')
    if receipt:
        cmd += ['--receipt', str(receipt)]
    data = run_json(cmd, timeout=max(180, 135 * retries))
    if isinstance(data, dict):
        data.setdefault('capability', 'pd_one_sheets_header_update_row_live' if args.live else 'pd_one_sheets_header_update_row_dry_run')
        data.setdefault('safety', {'shell_used': False, 'live_write_requested': bool(args.live), 'header_based': True})
    emit(data)
BOUNDED_SHEET_CELL_A1_RE = re.compile('^([A-Z]{1,3})([1-9][0-9]{0,4})$')
BOUNDED_SHEET_CELL_WRITE_MAX_CELLS = 20
BOUNDED_SHEET_CELL_WRITE_LIVE_CONFIRM = 'RUN LIVE BOUNDED SHEET CELL WRITE'

def bounded_sheet_cell_a1(raw: str, tab: str) -> str:
    text = str(raw or '').strip()
    quoted = f"'{tab}'!"
    bare = f'{tab}!'
    if text.startswith(quoted):
        text = text[len(quoted):]
    elif text.startswith(bare):
        text = text[len(bare):]
    text = text.replace('$', '').upper()
    if not BOUNDED_SHEET_CELL_A1_RE.fullmatch(text):
        fail(f'invalid bounded sheet cell A1: {raw!r}')
    return text

def load_bounded_sheet_cell_write_payload(path_text: str) -> dict[str, Any]:
    from tools.pd_one_ops.pd_one_safe_ops_part1 import load_admin_approval_modules
    bind_path = require_pdone_tmp_path(path_text, '--bind-json')
    if not bind_path.is_file():
        fail(f'--bind-json not found: {bind_path}')
    try:
        raw = json.loads(bind_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'--bind-json is not valid JSON: {exc}')
    if not isinstance(raw, dict):
        fail('--bind-json must be an object')
    tickets_mod, _ = load_admin_approval_modules()
    spreadsheet_id = str(raw.get('spreadsheet_id') or '').strip()
    tab = str(raw.get('tab') or '').strip()
    if not spreadsheet_id or len(spreadsheet_id) < 25:
        fail('spreadsheet_id is required')
    if not tab or len(tab) > 120:
        fail('tab is required and must be <= 120 characters')

    def normalize_cells(key: str) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        rows = raw.get(key)
        if not isinstance(rows, list):
            fail(f'{key} must be a list')
        for row in rows:
            if not isinstance(row, dict):
                fail(f'{key} entries must be objects')
            a1 = bounded_sheet_cell_a1(str(row.get('a1') or row.get('cell') or row.get('range') or ''), tab)
            value = row.get('value')
            if value is None and isinstance(row.get('values'), list):
                values = row.get('values') or []
                first = values[0] if values else []
                if isinstance(first, list) and first:
                    value = first[0]
            items.append({'a1': a1, 'value': '' if value is None else str(value)})
        return items
    cells = normalize_cells('cells')
    do_not_change = normalize_cells('do_not_change')
    if not cells or len(cells) > BOUNDED_SHEET_CELL_WRITE_MAX_CELLS:
        fail(f'cells must contain 1..{BOUNDED_SHEET_CELL_WRITE_MAX_CELLS} entries')
    if len(do_not_change) < 2:
        fail('do_not_change must include vendor and grade cells')
    write_a1 = {item['a1'] for item in cells}
    freeze_a1 = {item['a1'] for item in do_not_change}
    if write_a1 & freeze_a1:
        fail('write cells intersect do_not_change vendor/grade cells')
    payload = {'spreadsheet_id': spreadsheet_id, 'tab': tab, 'cells': cells, 'do_not_change': do_not_change, 'do_not_change_vendor_grade': True}
    envelope = tickets_mod.canonical_bounded_sheet_cell_write_envelope(payload)
    binding = tickets_mod.compute_bounded_sheet_cell_write_binding(payload)
    return {'payload': payload, 'envelope': envelope, 'binding': binding, 'bind_json': str(bind_path)}

def cmd_bounded_sheet_cell_write(args: argparse.Namespace) -> None:
    """Dry-run a SHA-256 bound Google Sheet cell write; live remains ticket-gated."""
    from tools.pd_one_ops.pd_one_safe_ops_part1 import load_admin_approval_modules
    loaded = load_bounded_sheet_cell_write_payload(args.bind_json)
    payload = loaded['payload']
    binding = loaded['binding']
    expected = str(getattr(args, 'expected_binding', '') or '').strip()
    if expected and expected != binding:
        fail('expected binding does not match SHA-256 sheet/tab/cells/values digest')
    spreadsheet_id = payload['spreadsheet_id']
    tab = payload['tab']
    quoted_tab = "'" + tab.replace("'", "''") + "'"
    freeze_ranges = [f'{quoted_tab}!{item['a1']}' for item in payload['do_not_change']]
    write_ranges = [f'{quoted_tab}!{item['a1']}' for item in payload['cells']]
    if args.verify_live_read:
        for item in payload['do_not_change']:
            cell_range = f'{quoted_tab}!{item['a1']}'
            live = run_json([sys.executable, str(SHEETS_SAFE_OPS()), 'get', spreadsheet_id, cell_range, '--account', args.account, '--print-values', '--retries', '3'], timeout=150)
            values = live.get('values') if isinstance(live, dict) else None
            current = ''
            if isinstance(values, list) and values and isinstance(values[0], list) and values[0]:
                current = str(values[0][0])
            if current != item['value']:
                fail(f'vendor/grade freeze mismatch at {item['a1']}: live {current!r} != bound {item['value']!r}')
    if args.live:
        if args.confirm_live_write != BOUNDED_SHEET_CELL_WRITE_LIVE_CONFIRM:
            fail(f"live bounded sheet cell write requires --confirm-live-write '{BOUNDED_SHEET_CELL_WRITE_LIVE_CONFIRM}'")
        ticket_id = str(getattr(args, 'ticket_id', '') or '').strip()
        if not ticket_id:
            fail('live bounded sheet cell write requires --ticket-id')
        tickets_mod, _ = load_admin_approval_modules()
        ledger = tickets_mod.ApprovalLedger(str(APPROVAL_LEDGER()))
        ticket = ledger.get(ticket_id)
        status = str(ticket.get('status') or '')
        if status not in {'approved', 'queued'}:
            fail(f'ticket {ticket_id} is {status}; live write requires Owner-approved PDAPP')
        grant = ticket.get('approval_grant') or {}
        caps = [str(cap) for cap in grant.get('allowed_capabilities') or []]
        if 'bounded_sheet_cell_write' not in caps:
            fail(f'ticket {ticket_id} grant does not include bounded_sheet_cell_write')
        scope = ticket.get('capability_scope') or {}
        bound = scope.get('bounded_sheet_cell_write') or {}
        ticket_binding = str(bound.get('binding') or '')
        if ticket_binding != binding:
            fail('ticket sheet-cell binding does not match --bind-json digest')
        fail('live bounded sheet cell write halted: this slice forbids cell writes')
    tmp_dir = ROOT() / 'tmp' / 'bounded-sheet-cell-write'
    tmp_dir.mkdir(parents=True, exist_ok=True)
    data_json = tmp_dir / 'dry-run-ranges.json'
    ranges = [{'range': cell_range, 'values': [[item['value']]]} for cell_range, item in zip(write_ranges, payload['cells'])]
    data_json.write_text(json.dumps(ranges, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    receipt = require_pdone_tmp_path(args.receipt, '--receipt') if args.receipt else None
    cmd = [sys.executable, str(SHEETS_SAFE_OPS()), 'batch-update', spreadsheet_id, '--data-json', str(data_json), '--account', args.account, '--input', 'USER_ENTERED', '--retries', '3']
    if receipt:
        cmd += ['--receipt', str(receipt)]
    data = run_json(cmd, timeout=180)
    if not isinstance(data, dict):
        fail('bounded sheet cell write helper returned non-JSON')
    data['capability'] = 'pd_one_bounded_sheet_cell_write_dry_run'
    data['binding'] = binding
    data['envelope'] = loaded['envelope']
    data['freeze_ranges'] = freeze_ranges
    data['write_ranges'] = write_ranges
    data['live_write_requested'] = False
    data['safety'] = {'shell_used': False, 'live_write_requested': False, 'vendor_grade_frozen': True, 'source_system_writes_forbidden': True, 'andy_ticket_required_for_live': True}
    emit(data)

def cmd_appsheet_table_probe(args: argparse.Namespace) -> None:
    """Read a bounded AppSheet table sample through the shared probe helper."""
    if not APPSHEET_TABLE_PROBE().exists():
        fail(f'AppSheet table probe helper not found: {APPSHEET_TABLE_PROBE()}')
    table = (args.table or '').strip()
    if not table or len(table) > 120:
        fail('--table is required and must be <= 120 characters')
    selector = (args.selector or '').strip()
    if not selector or len(selector) > 3000:
        fail('--selector is required and must be <= 3000 characters')
    env_key = str(args.env or 'prototype').strip().lower()
    env_file = APPSHEET_ENV_FILES().get(env_key)
    if env_file is None:
        fail(f'--env must be one of: {sorted(APPSHEET_ENV_FILES())}')
    if not env_file.exists():
        fail(f'AppSheet env file not found: {env_file}')
    data = run_json([sys.executable, str(APPSHEET_TABLE_PROBE()), table, selector, '--env-file', str(env_file)], timeout=300)
    if isinstance(data, dict):
        rows = data.get('rows') if isinstance(data.get('rows'), list) else []
        data.setdefault('capability', 'pd_one_appsheet_table_probe')
        data.setdefault('sample_limit', 20)
        data.setdefault('rows_returned', len(rows))
        if isinstance(data.get('row_count'), int):
            data.setdefault('truncated', data['row_count'] > len(rows))
        data['table'] = table
        data.setdefault('safety', {'read_only': True, 'shell_used': False, 'env': env_key, 'sample_rows_bounded': True})
    emit(data)

def _load_appsheet_incident_morning_briefing_module() -> Any:
    if not APPSHEET_INCIDENT_MORNING_BRIEFING_SCRIPT().exists():
        fail(f'AppSheet incident morning briefing helper not found: {APPSHEET_INCIDENT_MORNING_BRIEFING_SCRIPT()}')
    for module_name, attr_name in (('pd_one_federation_bridge', 'emit_pd_one_event'), ('pd_one_hermes_notify', 'send_hermes_message')):
        if module_name in sys.modules:
            continue
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')

            def _load_appsheet_incident_morning_briefing_module() -> Any:
                if not APPSHEET_INCIDENT_MORNING_BRIEFING_SCRIPT().exists():
                    fail(f'AppSheet incident morning briefing helper not found: {APPSHEET_INCIDENT_MORNING_BRIEFING_SCRIPT()}')
                module_dir = str(APPSHEET_INCIDENT_MORNING_BRIEFING_SCRIPT().parent)
                inserted = False
                if module_dir not in sys.path:
                    sys.path.append(module_dir)
                    inserted = True
                previous_dont_write_bytecode = sys.dont_write_bytecode
                sys.dont_write_bytecode = True
                try:
                    spec = importlib.util.spec_from_file_location('pdone_appsheet_incident_morning_briefing', APPSHEET_INCIDENT_MORNING_BRIEFING_SCRIPT())
                    if spec is None or spec.loader is None:
                        fail(f'Unable to load AppSheet incident morning briefing helper: {APPSHEET_INCIDENT_MORNING_BRIEFING_SCRIPT()}')
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[spec.name] = module
                    spec.loader.exec_module(module)
                    return module
                finally:
                    sys.dont_write_bytecode = previous_dont_write_bytecode
                    if inserted:
                        try:
                            sys.path.remove(module_dir)
                        except ValueError:
                            logging.getLogger('pd_one_ops').exception('pd one command failed')

def _appsheet_incident_morning_briefing_qa_samples() -> dict[str, str]:
    title = '晨會事件簡報 2026-07-17 / Morning Incident Briefing 2026-07-17'
    short = f"# {title}\n\n## 今日優先關注 / Today's focus\n\nbody"
    long_brief = f"# {title}\n\n## 今日優先關注 / Today's focus\n\n" + ('第一段重複內容。 ' * 28).strip() + '\n\n## Notable closures / 已結案\n\n' + ('第二段重複內容。 ' * 28).strip() + '\n\n## Watchlist / 觀察清單\n\n' + ('第三段重複內容。 ' * 20).strip()
    return {'short': short, 'long': long_brief}

def cmd_appsheet_incident_morning_briefing_qa(args: argparse.Namespace) -> None:
    """Read-only helper QA for the AppSheet incident morning briefing sender."""
    safety = {'read_only': True, 'shell_used': False, 'network_used': False, 'fixed_script': True, 'uses_execute_code_replacement': True}
    script = APPSHEET_INCIDENT_MORNING_BRIEFING_SCRIPT()
    try:
        source_text = script.read_text(encoding='utf-8')
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        emit({'status': 'error', 'capability': 'pd_one_appsheet_incident_morning_briefing_qa', 'error': 'script_read_failed', 'detail': str(exc), 'script': str(script), 'safety': safety})
        return
    try:
        compile(source_text, str(script), 'exec')
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        emit({'status': 'error', 'capability': 'pd_one_appsheet_incident_morning_briefing_qa', 'error': 'syntax_check_failed', 'detail': str(exc), 'script': str(script), 'source_sha256': hashlib.sha256(source_text.encode('utf-8')).hexdigest(), 'safety': safety})
        return
    try:
        module = _load_appsheet_incident_morning_briefing_module()
        samples = _appsheet_incident_morning_briefing_qa_samples()
        short_sample = samples['short']
        long_sample = samples['long']
        dashboard_linked = module.add_dashboard_link_near_top(short_sample)
        dashboard_relinked = module.add_dashboard_link_near_top(dashboard_linked)
        short_current, short_remaining = module.split_once_at_intelligent_boundary(short_sample, limit=500, first_part=True)
        long_current, long_remaining = module.split_once_at_intelligent_boundary(long_sample, limit=420, first_part=True)
        split_parts = module.split_at_intelligent_boundaries(long_sample, limit=420)
        dashboard_url = str(getattr(module, 'DASHBOARD_URL', ''))
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        emit({'status': 'error', 'capability': 'pd_one_appsheet_incident_morning_briefing_qa', 'error': 'helper_qa_failed', 'detail': str(exc), 'script': str(script), 'source_sha256': hashlib.sha256(source_text.encode('utf-8')).hexdigest(), 'safety': safety})
        return
    emit({'status': 'ok', 'capability': 'pd_one_appsheet_incident_morning_briefing_qa', 'script': str(script), 'source_sha256': hashlib.sha256(source_text.encode('utf-8')).hexdigest(), 'module': {'name': getattr(module, '__name__', ''), 'loaded': True}, 'checks': {'dashboard_link_idempotent': dashboard_linked == dashboard_relinked, 'dashboard_link_count': dashboard_linked.count(dashboard_url) if dashboard_url else 0, 'short_split_kept_whole': short_current == short_sample and short_remaining is None, 'long_split_has_continuation': bool(long_remaining), 'long_split_current_within_limit': len(long_current) <= 420, 'split_part_count': len(split_parts), 'split_parts_within_limit': all((len(part) <= 420 for part in split_parts)), 'split_first_part_has_suffix': bool(split_parts and split_parts[0].endswith('_Continued in reply / 下方回覆續上。_')), 'split_later_parts_have_prefix': all((part.startswith('_Continuation / 續上。_\n\n') for part in split_parts[1:])), 'long_split_current_has_suffix': long_current.endswith('_Continued in reply / 下方回覆續上。_')}, 'samples': {'short_length': len(short_sample), 'long_length': len(long_sample)}, 'safety': safety})

def cmd_google_group_members(args: argparse.Namespace) -> None:
    group = normalize_email(args.group)
    filter_email = normalize_email(args.filter_email) if args.filter_email else None
    gog = find_bin('gog', [str(ROOT() / 'home/.local/bin/gog'), resolve_configured_path('~/.local/bin/gog')])
    if not gog:
        fail('gog binary not found')
    data = run_json([gog, 'admin', 'groups', 'members', 'list', group, '--all', '--json', '--no-input', '--gmail-no-send', '--account', args.account], timeout=args.timeout)
    members = data.get('members') or data.get('items') or data.get('data') or ([] if isinstance(data, dict) else data)
    if not isinstance(members, list):
        members = []

    def member_email(m: Any) -> str:
        if not isinstance(m, dict):
            return ''
        return str(m.get('email') or m.get('Email') or m.get('primaryEmail') or '').lower()
    if filter_email:
        members = [m for m in members if member_email(m) == filter_email]
    emit({'status': 'ok', 'capability': 'pd_one_google_group_members', 'group': group, 'filter_email': filter_email, 'member_count': len(members), 'members': members if args.include_members else [{'email': member_email(m), 'role': m.get('role') if isinstance(m, dict) else None} for m in members]})

def cmd_google_drive_parent_chain(args: argparse.Namespace) -> None:
    """Read a bounded Google Drive file-parent chain without execute_code glue."""
    file_id = (args.file_id or '').strip()
    stop_id = (args.stop_at_id or '').strip()
    account = (args.account or DEFAULT_ACCOUNT()).strip()
    if not re.fullmatch('[A-Za-z0-9_-]{10,200}', file_id):
        fail('--file-id must be a Google Drive file id')
    if stop_id and (not re.fullmatch('[A-Za-z0-9_-]{10,200}', stop_id)):
        fail('--stop-at-id must be a Google Drive file id')
    if not re.fullmatch('[^@\\s]+@[^@\\s]+\\.[^@\\s]+', account):
        fail('invalid Google account')
    hops = max(1, min(int(args.max_hops), 12))
    gog = find_bin('gog', [str(ROOT() / 'home/.local/bin/gog'), resolve_configured_path('~/.local/bin/gog')])
    if not gog:
        fail('gog binary not found')
    chain: list[dict[str, Any]] = []
    current = file_id
    for _ in range(hops):
        proc = subprocess.run([gog, 'drive', 'get', current, '--account', account, '--json', '--no-input'], cwd=resolve_configured_path('~'), env={**os.environ, 'HOME': resolve_configured_path('~')}, text=True, capture_output=True, shell=False, timeout=30)
        if proc.returncode != 0:
            chain.append({'id': current, 'error': proc.stderr[-500:] or proc.stdout[-500:]})
            break
        try:
            obj = json.loads(proc.stdout)
        except json.JSONDecodeError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            chain.append({'id': current, 'error': 'invalid_json_response'})
            break
        f = obj.get('file', obj) if isinstance(obj, dict) else {}
        if not isinstance(f, dict):
            chain.append({'id': current, 'error': 'unexpected_file_response'})
            break
        item = {'id': f.get('id') or current, 'name': f.get('name'), 'mimeType': f.get('mimeType'), 'parents': f.get('parents') or []}
        chain.append(item)
        if item['id'] == stop_id or not item['parents']:
            break
        current = item['parents'][0]
    emit({'status': 'ok' if chain and (not chain[-1].get('error')) else 'error', 'capability': 'pd_one_google_drive_parent_chain', 'chain': chain, 'hops': len(chain), 'max_hops': hops, 'safety': {'read_only': True, 'source_system_writes': False, 'credentials_printed': False, 'bounded_requests': hops, 'shell_used': False}})

def cmd_google_drive_search_files(args: argparse.Namespace) -> None:
    """Search a bounded Drive folder/date window and return filtered file metadata."""
    parent_id = (args.parent_id or '').strip()
    name_contains = (args.name_contains or '').strip()
    mime_type = (args.mime_type or '').strip()
    window_start = (args.window_start_utc or '').strip()
    account = (args.account or DEFAULT_ACCOUNT()).strip()
    if not re.fullmatch('[A-Za-z0-9_-]{10,200}', parent_id):
        fail('--parent-id must be a Google Drive folder id')
    if not name_contains or len(name_contains) > 160:
        fail('--name-contains must be 1-160 characters')
    if not re.fullmatch('application/[A-Za-z0-9.+_-]+', mime_type):
        fail('invalid MIME type')
    if not re.fullmatch('20\\d{2}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z', window_start):
        fail('--window-start-utc must be an ISO-8601 UTC timestamp ending in Z')
    if not re.fullmatch('[^@\\s]+@[^@\\s]+\\.[^@\\s]+', account):
        fail('invalid Google account')
    max_files = max(1, min(int(args.max_files), 100))
    gog = find_bin('gog', [str(ROOT() / 'home/.local/bin/gog'), resolve_configured_path('~/.local/bin/gog')])
    if not gog:
        fail('gog binary not found')
    query = f"modifiedTime >= '{window_start}' and '{parent_id}' in parents"
    proc = subprocess.run([gog, 'drive', 'search', query, '--raw-query', '--account', account, '--json', '--no-input', '--max', str(max_files)], cwd=resolve_configured_path('~'), env=safe_env(), text=True, capture_output=True, shell=False, timeout=min(int(args.timeout), 120))
    if proc.returncode != 0:
        fail(proc.stderr[-500:] or proc.stdout[-500:] or 'Drive search failed')
    try:
        obj = json.loads(proc.stdout)
    except json.JSONDecodeError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail('invalid_json_response')
    raw_files = obj.get('files', []) if isinstance(obj, dict) else []
    if not isinstance(raw_files, list):
        raw_files = []
    files = []
    for f in raw_files:
        if not isinstance(f, dict) or name_contains not in str(f.get('name') or '') or f.get('mimeType') != mime_type:
            continue
        files.append({k: f.get(k) for k in ('id', 'name', 'modifiedTime', 'size', 'mimeType', 'parents')})
    files.sort(key=lambda x: str(x.get('modifiedTime') or ''), reverse=True)
    emit({'status': 'ok', 'capability': 'pd_one_google_drive_search_files', 'parent_id': parent_id, 'window_start_utc': window_start, 'name_contains': name_contains, 'mime_type': mime_type, 'eligible_count': len(files), 'files': files[:max_files], 'safety': {'read_only': True, 'source_system_writes': False, 'credentials_printed': False, 'bounded_requests': 1, 'shell_used': False}})

def cmd_google_group_change(args: argparse.Namespace) -> None:
    group = normalize_email(args.group)
    member = normalize_email(args.member) if args.member else None
    action = args.action
    plan = {'status': 'ok', 'capability': 'pd_one_google_group_change_dry_run' if args.dry_run else 'pd_one_google_group_change_apply_approved', 'mode': 'dry-run' if args.dry_run else 'live', 'group': group, 'action': action, 'member': member, 'role': args.role, 'account': args.account, 'commands': [], 'readback_required': True}
    if action == 'create-group':
        plan['commands'].append({'operation': 'create_group', 'group': group, 'name': args.name or group.split('@', 1)[0]})
    elif action in {'add-member', 'remove-member'}:
        if not member:
            fail('--member is required for add-member/remove-member')
        plan['commands'].append({'operation': action.replace('-', '_'), 'group': group, 'member': member, 'role': args.role})
    else:
        fail(f'unsupported group change action: {action}')
    if args.dry_run:
        emit(plan)
        return
    if action == 'create-group':
        fail('live create-group is not enabled; use add-member/remove-member with a typed ticket')
    from pd_one_google_group_member_ops import LIVE_CONFIRMATION, apply_member_change
    emit(apply_member_change(action=action, group=group, member=member or '', role=args.role, dry_run=False, ticket_id=args.ticket_id, confirm_live_write=getattr(args, 'confirm_live_write', None)))
    return

def http_status(url: str, timeout: float=3.0) -> dict[str, Any]:
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {'url': url, 'ok': True, 'status_code': resp.status, 'reason': resp.reason}
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'url': url, 'ok': False, 'error': str(exc)[:300]}

def port_open(host: str, port: int, timeout: float=1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return False

def _bounded_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'invalid {label}: {value!r}')
    if parsed < minimum or parsed > maximum:
        fail(f'{label} must be between {minimum} and {maximum}')
    return parsed

def _validated_probe_name(value: str, label: str) -> str:
    text = (value or '').strip()
    if not text or len(text) > 128 or (not re.match('^[A-Za-z0-9][A-Za-z0-9_.:-]*$', text)):
        fail(f'invalid {label}: {value!r}')
    return text

def _parse_key_value_lines(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (text or '').splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key:
            data[key] = value
    return data

def _scan_embedding_log_text(source: str, text: str, sample_limit: int=20) -> dict[str, Any]:
    counts = {name: 0 for name in OLLAMA_EMBEDDING_LOG_PATTERNS}
    samples: list[dict[str, Any]] = []
    matching_line_count = 0
    for line_number, line in enumerate((text or '').splitlines(), start=1):
        hits = [name for name, pattern in OLLAMA_EMBEDDING_LOG_PATTERNS.items() if pattern.search(line)]
        if not hits:
            continue
        matching_line_count += 1
        for name in hits:
            counts[name] += 1
        if len(samples) < sample_limit:
            samples.append({'line_number': line_number, 'patterns': hits, 'excerpt': tail_text(line.strip(), 320)})
    return {'source': source, 'matching_line_count': matching_line_count, 'pattern_counts': counts, 'sample_matches': samples}

def _scan_embedding_watchdog_log_text(source: str, text: str, sample_limit: int=20) -> dict[str, Any]:
    lines = (text or '').splitlines()
    counts = {name: 0 for name in OLLAMA_EMBEDDING_WATCHDOG_LOG_PATTERNS}
    samples: list[dict[str, Any]] = []
    first_event: dict[str, Any] | None = None
    last_event: dict[str, Any] | None = None
    matching_line_count = 0
    for line_number, line in enumerate(lines, start=1):
        hits = [name for name, pattern in OLLAMA_EMBEDDING_WATCHDOG_LOG_PATTERNS.items() if pattern.search(line)]
        if not hits:
            continue
        matching_line_count += 1
        for name in hits:
            counts[name] += 1
        event = {'line_number': line_number, 'patterns': hits, 'excerpt': tail_text(line.strip(), 320)}
        if first_event is None:
            first_event = event
        last_event = event
        if len(samples) < sample_limit:
            samples.append(event)
    return {'source': source, 'log_lines': len(lines), 'matching_line_count': matching_line_count, 'pattern_counts': counts, 'remote_ok_true': counts['remote_ok_true'], 'remote_ok_false': counts['remote_ok_false'], 'mode_remote': counts['mode_remote'], 'mode_local': counts['mode_local'], 'switch_events': counts['switch_events'], 'service_failures': counts['service_failures'], 'first_event': first_event, 'last_event': last_event, 'sample_matches': samples}

def _probe_text(cmd: list[str], timeout: int) -> dict[str, Any]:
    try:
        proc = run_capture(cmd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'command': cmd, 'status': 'error', 'error': 'timeout', 'timeout_seconds': timeout, 'returncode': 124, 'stdout': exc.stdout or '', 'stderr': exc.stderr or ''}
    except FileNotFoundError as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'command': cmd, 'status': 'error', 'error': 'binary_not_found', 'detail': str(exc), 'returncode': 127, 'stdout': '', 'stderr': ''}
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'command': cmd, 'status': 'error', 'error': 'probe_failed', 'detail': repr(exc), 'returncode': 1, 'stdout': '', 'stderr': ''}
    return {'command': cmd, 'status': 'ok' if proc.returncode == 0 else 'error', 'returncode': proc.returncode, 'stdout': proc.stdout or '', 'stderr': proc.stderr or ''}

def cmd_auth_browser_status(args: argparse.Namespace) -> None:
    docker = find_bin('docker')
    container = args.container
    info: dict[str, Any] = {'status': 'ok', 'capability': 'pd_one_auth_browser_status', 'container': container}
    if docker:
        proc = subprocess.run([docker, 'ps', '--filter', f'name={container}', '--format', '{{json .}}'], text=True, capture_output=True, env=safe_env(), shell=False, timeout=10)
        rows = []
        for line in proc.stdout.splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                logging.getLogger('pd_one_ops').exception('pd one command failed')
        info['docker_available'] = True
        info['container_matches'] = rows
        info['running'] = bool(rows)
    else:
        info['docker_available'] = False
        info['running'] = None
    urls = ['http://127.0.0.1:6081/vnc.html']
    if args.include_tailscale_url:
        urls.append(args.include_tailscale_url)
    info['http_checks'] = [http_status(u) for u in urls]
    info['ports'] = {'6081': port_open('127.0.0.1', 6081), '5901': port_open('127.0.0.1', 5901), '9223': port_open('127.0.0.1', 9223)}
    emit(info)

def _sysstat_percentile(values: list[float], p: float) -> float | None:
    clean = sorted((v for v in values if isinstance(v, (int, float))))
    if not clean:
        return None
    k = (len(clean) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(clean) - 1)
    if lo == hi:
        return clean[lo]
    return clean[lo] + (clean[hi] - clean[lo]) * (k - lo)

def _sysstat_series_summary(values: list[float]) -> dict[str, Any]:
    clean = [float(v) for v in values if isinstance(v, (int, float))]
    if not clean:
        return {'count': 0}
    p95 = _sysstat_percentile(clean, 95)
    return {'count': len(clean), 'mean': round(mean(clean), 3), 'median': round(median(clean), 3), 'p95': round(p95, 3) if p95 is not None else None, 'min': round(min(clean), 3), 'max': round(max(clean), 3)}

def _sysstat_numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return None

def _sysstat_select_log_files(hours: int, now: datetime | None=None) -> list[Path]:
    window_hours = max(1, min(int(hours), SYSSTAT_SUMMARY_MAX_HOURS))
    days_back = max(1, min((window_hours + 23) // 24 + 1, SYSSTAT_SUMMARY_MAX_HOURS // 24 + 1))
    current = now or datetime.now()
    files: list[Path] = []
    for offset in range(days_back):
        candidate = SYSSTAT_LOG_ROOT / f'sa{(current - timedelta(days=offset)).day:02d}'
        if candidate.is_file():
            files.append(candidate)
    return list(dict.fromkeys(files))

def _sysstat_parse_sadf_output(stdout: str, window_start: datetime, window_end: datetime) -> list[dict[str, Any]]:
    cleaned: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('#'):
            line = line[1:].strip()
        cleaned.append(line)
    if len(cleaned) < 2:
        return []
    reader = csv.DictReader(io.StringIO('\n'.join(cleaned)), delimiter=';')
    rows: list[dict[str, Any]] = []
    for row in reader:
        ts_text = (row.get('timestamp') or '').strip()
        try:
            ts = datetime.strptime(ts_text, '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc)
        except ValueError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            continue
        if ts < window_start or ts > window_end:
            continue
        parsed: dict[str, Any] = {'timestamp': ts}
        for key, value in row.items():
            if key == 'timestamp':
                continue
            text_value = (value or '').strip()
            if key == 'hostname':
                parsed[key] = text_value
                continue
            numeric = _sysstat_numeric(text_value)
            parsed[key] = numeric if numeric is not None else text_value
        rows.append(parsed)
    rows.sort(key=lambda item: item['timestamp'])
    return rows

def _sysstat_emit_row(row: dict[str, Any]) -> dict[str, Any]:
    emitted: dict[str, Any] = {}
    for key, value in row.items():
        if key == 'timestamp' and hasattr(value, 'isoformat'):
            emitted['timestamp_utc'] = value.isoformat().replace('+00:00', 'Z')
            continue
        if isinstance(value, float) and value.is_integer():
            emitted[key] = int(value)
        else:
            emitted[key] = value
    return emitted

def _sysstat_metric_report(*, sadf: str, metric_name: str, sadf_args: list[str], focus_columns: list[str], files: list[Path], window_start: datetime, window_end: datetime) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    files_used: list[str] = []
    errors: list[dict[str, Any]] = []
    for path in files:
        proc = run_capture([sadf, '-d', str(path), '--', *sadf_args], timeout=30)
        if proc.returncode != 0:
            errors.append({'file': str(path), 'returncode': proc.returncode, 'stderr_tail': tail_text(proc.stderr), 'stdout_tail': tail_text(proc.stdout)})
            continue
        parsed = _sysstat_parse_sadf_output(proc.stdout, window_start, window_end)
        if parsed:
            files_used.append(str(path))
            rows.extend(parsed)
    rows.sort(key=lambda item: item['timestamp'])
    focus: dict[str, dict[str, Any]] = {}
    for column in focus_columns:
        values = [float(row[column]) for row in rows if isinstance(row.get(column), (int, float))]
        focus[column] = _sysstat_series_summary(values)
    latest = _sysstat_emit_row(rows[-1]) if rows else None
    return {'metric': metric_name, 'samples': len(rows), 'time_range_utc': {'start': rows[0]['timestamp'].isoformat().replace('+00:00', 'Z') if rows else None, 'end': rows[-1]['timestamp'].isoformat().replace('+00:00', 'Z') if rows else None}, 'latest': latest, 'focus': focus, 'files_used': files_used, 'errors': errors}

def _sysstat_state_high(value: float | None, watch: float, high: float) -> str:
    if value is None:
        return 'unknown'
    if value >= high:
        return 'high'
    if value >= watch:
        return 'watch'
    return 'ok'

def _sysstat_state_low(value: float | None, watch: float, high: float) -> str:
    if value is None:
        return 'unknown'
    if value <= high:
        return 'high'
    if value <= watch:
        return 'watch'
    return 'ok'

def cmd_numeric_summary(args: argparse.Namespace) -> None:
    label = str(args.label or 'samples').strip() or 'samples'
    units = str(args.units or '').strip()
    if len(label) > 80:
        fail('label must be 80 characters or fewer')
    if len(units) > 32:
        fail('units must be 32 characters or fewer')
    try:
        raw_values = json.loads(str(args.values_json or ''))
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'values_json must be a JSON array of numbers: {exc}')
    if not isinstance(raw_values, list):
        fail('values_json must decode to a JSON array')
    if len(raw_values) > 1000:
        fail('values_json must contain at most 1000 numbers')
    values: list[float] = []
    for raw_value in raw_values:
        numeric = _sysstat_numeric(raw_value)
        if numeric is None or not math.isfinite(numeric):
            fail('values_json must contain only finite numeric values')
        values.append(numeric)
    summary = _sysstat_series_summary(values)
    emit({'status': 'ok', 'capability': 'pd_one_numeric_summary', 'label': label, 'units': units or None, 'sample_count': len(values), 'summary': summary, 'safety': {'read_only': True, 'shell_used': False, 'bounded_inputs': True, 'source_system_writes_forbidden': True}})

def cmd_text_metrics(args: argparse.Namespace) -> None:
    """Count one bounded caller-supplied text without executing interpreter code."""
    text = str(args.text or '')
    if len(text) > 20000:
        fail('text must contain at most 20000 Unicode code points')
    emit({'status': 'ok', 'capability': 'pd_one_text_metrics', 'characters_including_punctuation': len(text), 'utf8_bytes': len(text.encode('utf-8')), 'non_whitespace_characters': sum((1 for character in text if not character.isspace())), 'line_count': 0 if not text else text.count('\n') + 1, 'safety': {'read_only': True, 'shell_used': False, 'bounded_inputs': True, 'text_returned': False, 'source_system_writes_forbidden': True}})

def cmd_disk_space_summary(args: argparse.Namespace) -> None:
    """Read root capacity and project bounded reclaim estimates without cleanup."""
    values = (int(args.low_risk_bytes), int(args.medium_risk_bytes), int(args.additional_bytes))
    if any((value < 0 for value in values)):
        fail('reclaim byte estimates must be non-negative')
    usage = shutil.disk_usage('/')
    size = int(usage.total)
    current = int(usage.free)

    def snapshot(available: int) -> dict[str, float]:
        return {'size_gib': round(size / 1073741824, 2), 'used_gib': round((size - available) / 1073741824, 2), 'avail_gib': round(available / 1073741824, 2), 'avail_pct': round(available / size * 100, 1) if size else 0.0}
    low, medium, additional = values
    emit({'status': 'ok', 'capability': 'pd_one_disk_space_summary', 'filesystem': '/', 'current': snapshot(current), 'projections': {'after_low_risk': snapshot(current + low), 'after_low_plus_medium': snapshot(current + low + medium), 'after_all_plus_additional': snapshot(current + low + medium + additional)}, 'reclaim_estimates_bytes': {'low_risk': low, 'medium_risk': medium, 'additional': additional}, 'safety': {'read_only': True, 'shell_used': False, 'bounded_inputs': True, 'cleanup_performed': False, 'source_system_writes_forbidden': True}})

def _format_ps_etime(total_seconds: int) -> str:
    elapsed = max(0, int(total_seconds))
    days, rem = divmod(elapsed, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    if days:
        return f'{days}-{hours:02d}:{minutes:02d}:{seconds:02d}'
    if hours:
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}'
    return f'{minutes:02d}:{seconds:02d}'

def redact_process_cmd(cmd: str) -> str:
    redacted = USER_PROCESS_SNAPSHOT_SECRET_KV_RE.sub('\\1[REDACTED]', str(cmd or ''))
    redacted = ' '.join(redacted.split())
    if len(redacted) > USER_PROCESS_SNAPSHOT_CMD_CHARS:
        return redacted[:USER_PROCESS_SNAPSHOT_CMD_CHARS - 1] + '…'
    return redacted

def _proc_start_ticks(stat_text: str) -> int | None:
    rparen = stat_text.rfind(')')
    if rparen < 0:
        return None
    fields = stat_text[rparen + 2:].split()
    if len(fields) < 20:
        return None
    try:
        return int(fields[19])
    except ValueError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return None

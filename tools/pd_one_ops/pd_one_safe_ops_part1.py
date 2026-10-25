from __future__ import annotations
__all__ = ['inspect_user_process_snapshot', 'cmd_user_process_snapshot', '_parse_local_process_listener_ports', '_parse_local_process_listener_pids', '_truncate_process_cmd', '_parse_ps_process_rows', '_parse_ss_listener_row', 'cmd_local_process_listener_inspect', 'cmd_python_package_dry_run', 'cmd_python_media_stack_status', '_cad_document_identity', '_module_spec_available', 'cmd_python_cad_stack_status', 'inspect_cad_runtime', 'cmd_cad_runtime_status', '_step_geometry_header', '_step_geometry_json_input', '_step_geometry_kind_counts', '_step_geometry_face_extra', '_summarize_step_inspect_payload', '_step_geometry_input', 'cmd_step_geometry_inspect', '_step_printability_json_input', '_summarize_step_printability_payload', 'cmd_step_printability_analyze', '_python_docx_runtime_readback', 'cmd_python_docx_dependency_repair', '_approved_hermes_result_path', '_result_summary_text', '_result_content_summary', 'cmd_hermes_result_messages_summary', '_json_artifact_type_name', '_json_artifact_length', '_json_artifact_key_list', '_summarize_json_artifact', '_approved_json_artifact_inspect_path', 'cmd_json_artifact_inspect', '_approved_local_file_search_path', '_validate_local_file_search_pattern', '_iter_local_file_search_files', 'cmd_local_file_search', 'cmd_sysstat_summary', 'cmd_ollama_embedding_triage', 'cmd_ollama_embedding_watchdog_triage', 'validate_mattermost_id', 'validate_mattermost_name', 'load_mattermost_review_log_module', 'mattermost_context', 'mm_request', '_mattermost_lookup_get', 'lookup_mattermost_channel', 'cmd_mattermost_channel_lookup', 'cmd_mattermost_channel_post_audit', 'cmd_admin_alert_source_audit', 'inspect_mattermost_deleted_posts', 'cmd_mattermost_deleted_posts_audit', 'MM_TITLE_TRANSLATIONS', 'MM_CATEGORY_KEYWORDS', 'propose_channel_display_name', 'fetch_channel_posts', 'mm_users_by_id', 'fetch_channel_members', 'summarize_channel', 'propose_channel_purpose', 'parse_since_ms', 'mattermost_user_membership', 'post_link', 'compact_excerpt', 'load_admin_approval_modules', 'load_admin_approval_listener_module', 'load_admin_approval_executor_module', 'kick_pdapp_direct_executor', 'load_current_mattermost_policy', 'split_csv_lines', 'verified_admin_request_source', 'andy_origin_skips_admin_ticket', 'source_explicitly_authorizes_deployment', 'DRIVE_WRITER_NO_TICKET_TYPES', 'DRIVE_WRITER_NO_TICKET_ACTION_RE', 'DRIVE_WRITER_NO_TICKET_CAP_RE', 'GOOGLE_FILE_ID_RE', 'GOOGLE_BARE_FILE_ID_RE', 'harvest_google_file_ids', '_authorize_drive_writer', 'employee_live_drive_writer_skips_admin_ticket', 'cmd_admin_approval_request', 'cmd_admin_approval_list_open', 'cmd_admin_approval_decide', 'cmd_approval_ticket_status']
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

def inspect_user_process_snapshot() -> dict[str, Any]:
    """Read a bounded, redacted snapshot of the fixed host service user's processes."""
    import pwd
    try:
        pw = pwd.getpwnam(USER_PROCESS_SNAPSHOT_USER)
    except KeyError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'fixed process-snapshot user is unavailable: {USER_PROCESS_SNAPSHOT_USER}')
    uid = int(pw.pw_uid)
    try:
        ticks = int(os.sysconf('SC_CLK_TCK'))
        uptime = float(Path('/proc/uptime').read_text(encoding='utf-8').split()[0])
    except (OSError, ValueError, IndexError) as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'unable to read process clock/uptime: {exc}')
    if ticks <= 0:
        fail('invalid SC_CLK_TCK')
    rows: list[dict[str, Any]] = []
    try:
        entries = list(Path('/proc').iterdir())
    except OSError as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'unable to list /proc: {exc}')
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            status_text = (entry / 'status').read_text(encoding='utf-8', errors='replace')
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            continue
        uid_line = next((line for line in status_text.splitlines() if line.startswith('Uid:')), '')
        parts = uid_line.split()
        if len(parts) < 2:
            continue
        try:
            real_uid = int(parts[1])
        except ValueError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            continue
        if real_uid != uid:
            continue
        try:
            raw_cmd = (entry / 'cmdline').read_bytes().replace(b'\x00', b' ').decode('utf-8', 'replace').strip()
            if not raw_cmd:
                comm = next((line.split(':', 1)[1].strip() for line in status_text.splitlines() if line.startswith('Name:')), '')
                raw_cmd = f'[{comm}]' if comm else ''
            stat_text = (entry / 'stat').read_text(encoding='utf-8', errors='replace')
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            continue
        start_ticks = _proc_start_ticks(stat_text)
        if start_ticks is None:
            continue
        etime_seconds = int(uptime - start_ticks / ticks)
        rows.append({'pid': int(entry.name), 'etime': _format_ps_etime(etime_seconds), 'etime_seconds': max(0, etime_seconds), 'cmd': redact_process_cmd(raw_cmd)})
    rows.sort(key=lambda item: item['pid'])
    returned = rows[:USER_PROCESS_SNAPSHOT_MAX_ROWS]
    return {'status': 'ok', 'capability': 'pd_one_user_process_snapshot', 'user': USER_PROCESS_SNAPSHOT_USER, 'uid': uid, 'columns': ['pid', 'etime', 'cmd'], 'process_count': len(rows), 'processes_returned': len(returned), 'truncated': len(rows) > len(returned), 'processes': returned, 'safety': {'admin_only': True, 'read_only': True, 'shell_used': False, 'fixed_user': True, 'bounded_rows': True, 'command_lines_redacted': True, 'process_signals_forbidden': True, 'source_system_writes_forbidden': True, 'external_sends_forbidden': True}}

def cmd_user_process_snapshot(args: argparse.Namespace) -> None:
    emit(inspect_user_process_snapshot())

def _parse_local_process_listener_ports(raw: Any) -> list[int]:
    values = list(raw or [])
    if not values:
        values = list(LOCAL_PROCESS_LISTENER_DEFAULT_PORTS)
    if len(values) > LOCAL_PROCESS_LISTENER_MAX_PORTS:
        fail(f'at most {LOCAL_PROCESS_LISTENER_MAX_PORTS} ports are allowed')
    ports: list[int] = []
    for value in values:
        port = _bounded_int(value, 'port', 1, 65535)
        if port not in LOCAL_PROCESS_LISTENER_PORTS:
            allowed = ', '.join((str(item) for item in sorted(LOCAL_PROCESS_LISTENER_PORTS)))
            fail(f'port {port} is not in the allowlist ({allowed})')
        if port not in ports:
            ports.append(port)
    return ports

def _parse_local_process_listener_pids(raw: Any) -> list[int]:
    values = list(raw or [])
    if len(values) > LOCAL_PROCESS_LISTENER_MAX_PIDS:
        fail(f'at most {LOCAL_PROCESS_LISTENER_MAX_PIDS} pids are allowed')
    pids: list[int] = []
    for value in values:
        pid = _bounded_int(value, 'pid', 1, 4000000000)
        if pid not in pids:
            pids.append(pid)
    return pids

def _truncate_process_cmd(text: str) -> str:
    compact = ' '.join(str(text or '').split())
    if len(compact) <= LOCAL_PROCESS_LISTENER_CMD_CAP:
        return compact
    return compact[:LOCAL_PROCESS_LISTENER_CMD_CAP - 3] + '...'

def _parse_ps_process_rows(stdout: str, requested_pids: list[int]) -> list[dict[str, Any]]:
    found: dict[int, dict[str, Any]] = {}
    for line in (stdout or '').splitlines():
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            continue
        found[pid] = {'pid': pid, 'exists': True, 'etime': parts[1], 'cmd': _truncate_process_cmd(parts[2] if len(parts) > 2 else '')}
    return [found.get(pid, {'pid': pid, 'exists': False, 'etime': '', 'cmd': ''}) for pid in requested_pids]

def _parse_ss_listener_row(stdout: str, port: int) -> dict[str, Any]:
    lines = [line for line in (stdout or '').splitlines() if line.strip()]
    selected = ''
    for line in lines:
        if f':{port}' in line:
            selected = line
            break
    if not selected and lines:
        selected = lines[0]
    pid_match = LOCAL_PROCESS_LISTENER_SS_PID_RE.search(selected)
    comm_match = LOCAL_PROCESS_LISTENER_SS_COMM_RE.search(selected)
    local_address = ''
    for token in selected.split():
        if token.endswith(f':{port}'):
            local_address = token
            break
    return {'listening': bool(selected), 'local_address': local_address, 'pid': int(pid_match.group(1)) if pid_match else None, 'comm': comm_match.group(1) if comm_match else '', 'line_count': len(lines)}

def cmd_local_process_listener_inspect(args: argparse.Namespace) -> None:
    """Inspect allowlisted local listeners and a bounded PID list without shell glue."""
    ports = _parse_local_process_listener_ports(getattr(args, 'ports', None))
    pids = _parse_local_process_listener_pids(getattr(args, 'pids', None))
    warnings: list[str] = []
    ss_bin = find_bin('ss')
    ps_bin = find_bin('ps')
    listeners: list[dict[str, Any]] = []
    for port in ports:
        if not ss_bin:
            listeners.append({'port': port, 'role': LOCAL_PROCESS_LISTENER_PORTS[port], 'command': ['ss', '-H', '-ltnp', f'sport = :{port}'], 'status': 'error', 'error': 'binary_not_found', 'listening': False, 'local_address': '', 'pid': None, 'comm': ''})
            continue
        probe = _probe_text([ss_bin, '-H', '-ltnp', f'sport = :{port}'], timeout=20)
        parsed = _parse_ss_listener_row(str(probe.get('stdout') or ''), port)
        if probe.get('status') != 'ok':
            warnings.append(f'ss_listen_probe_failed:{port}')
        listeners.append({'port': port, 'role': LOCAL_PROCESS_LISTENER_PORTS[port], 'command': probe.get('command'), 'status': probe.get('status'), 'error': probe.get('error'), 'returncode': probe.get('returncode'), **parsed})
    if not ss_bin:
        warnings.append('ss_missing')
    processes: list[dict[str, Any]] = []
    process_probe: dict[str, Any] | None = None
    if pids:
        if not ps_bin:
            warnings.append('ps_missing')
            processes = [{'pid': pid, 'exists': False, 'etime': '', 'cmd': '', 'status': 'error', 'error': 'binary_not_found'} for pid in pids]
        else:
            process_probe = _probe_text([ps_bin, '-p', ','.join((str(pid) for pid in pids)), '-o', 'pid=,etime=,args='], timeout=20)
            processes = _parse_ps_process_rows(str(process_probe.get('stdout') or ''), pids)
            if process_probe.get('returncode') not in {0, 1}:
                warnings.append('ps_probe_failed')
    overall = 'ok' if not warnings else 'partial'
    emit({'status': overall, 'capability': 'pd_one_local_process_listener_inspect', 'ports': ports, 'pids': pids, 'listeners': listeners, 'processes': processes, 'summary': {'listener_count': len(listeners), 'listening_count': sum((1 for item in listeners if item.get('listening'))), 'missing_listener_ports': [item['port'] for item in listeners if not item.get('listening')], 'process_count': len(processes), 'running_process_count': sum((1 for item in processes if item.get('exists'))), 'missing_pids': [item['pid'] for item in processes if not item.get('exists')]}, 'warnings': warnings, 'safety': {'read_only': True, 'shell_used': False, 'bounded_inputs': True, 'allowlisted_ports_only': True, 'no_privileged_action_executed': True, 'lifecycle_changes_forbidden': True, 'source_system_writes_forbidden': True}, 'process_probe_returncode': None if process_probe is None else process_probe.get('returncode')})

def cmd_python_package_dry_run(args: argparse.Namespace) -> None:
    """Resolve one pinned package against an approved interpreter without installing it."""
    from tools.pd_one_ops.pd_one_safe_ops_part2 import is_within
    package = str(args.package or '').strip()
    version = str(args.version or '').strip()
    python_path = Path(str(args.python or '')).expanduser()
    resolved_python_path = python_path.resolve(strict=False)
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', package):
        fail('--package must be one simple PyPI package name')
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.!+<>=,*-]{0,79}', version):
        fail('--version must be a bounded package version/specifier')
    approved_python_roots = [Path(resolve_configured_path('~/.hermes/releases')), Path(resolve_configured_path('~/.local/share/uv/python')), ROOT() / 'releases', ROOT() / '.venv', ROOT() / 'legacy-openclaw/workspace/ops/venvs']
    if not python_path.is_absolute():
        fail('--python must be an absolute path under an approved PD One runtime root')
    lexical_python_path = Path(os.path.normpath(str(python_path)))
    if not any((lexical_python_path == root or root in lexical_python_path.parents for root in approved_python_roots)):
        fail('--python path must be under an approved PD One runtime root')
    if not any((is_within(resolved_python_path, root) for root in approved_python_roots)):
        fail('--python must resolve under an approved PD One runtime root')
    if not python_path.is_file() or not os.access(python_path, os.X_OK):
        fail(f'approved Python interpreter is not executable: {python_path}')
    uv_path = shutil.which('uv', path=str(PATH_BASE()) + os.pathsep + str(site_text('PATH')))
    if not uv_path:
        fail('uv executable is unavailable')
    proc = run_capture([uv_path, 'pip', 'install', '--dry-run', '--python', str(python_path), f'{package}=={version}'], timeout=120)
    result = {'status': 'ok' if proc.returncode == 0 else 'error', 'capability': 'pd_one_python_package_dry_run', 'package': package, 'version': version, 'python': str(python_path), 'resolver': 'uv', 'returncode': proc.returncode, 'stdout_tail': tail_text(proc.stdout), 'stderr_tail': tail_text(proc.stderr), 'safety': {'read_only': True, 'dry_run': True, 'shell_used': False, 'bounded_inputs': True, 'installation_performed': False, 'source_system_writes_forbidden': True}}
    emit(result)
    if proc.returncode != 0:
        raise SystemExit(1)

def cmd_python_media_stack_status(args: argparse.Namespace) -> None:
    """Report availability of the fixed PD One Python media module stack."""
    modules = {name: bool(importlib.util.find_spec(name)) for name in PYTHON_MEDIA_STACK_MODULES}
    available = [name for name, present in modules.items() if present]
    missing = [name for name, present in modules.items() if not present]
    emit({'status': 'ok', 'capability': 'pd_one_python_media_stack_status', 'python': sys.executable, 'modules': modules, 'available': available, 'missing': missing, 'available_count': len(available), 'missing_count': len(missing), 'safety': {'read_only': True, 'shell_used': False, 'bounded_inputs': True, 'modules_imported': False, 'installation_performed': False, 'source_system_writes_forbidden': True}})

def _cad_document_identity(raw_path: str) -> dict[str, Any]:
    from tools.pd_one_ops.pd_one_safe_ops_part2 import is_within
    text = str(raw_path or '').strip()
    if not text or len(text) > CAD_DOCUMENT_PATH_MAX_CHARS:
        fail('CAD document path is missing or too long')
    candidate = Path(text)
    if candidate.is_symlink():
        fail('CAD document path must not be a symlink')
    resolved = candidate.resolve(strict=False)
    if not any((is_within(resolved, root) for root in CAD_DOCUMENT_ROOTS())):
        fail('CAD document path is outside approved cache/documents')
    suffix = resolved.suffix.lower()
    if suffix not in CAD_DOCUMENT_SUFFIXES:
        fail(f'CAD document suffix is not allowed: {suffix}')
    exists = resolved.is_file() and (not resolved.is_symlink())
    return {'name': resolved.name, 'suffix': suffix, 'exists': exists, 'size': resolved.stat().st_size if exists else None, 'under_cache_documents': True}

def _module_spec_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ModuleNotFoundError, ImportError, ValueError):
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return False

def cmd_python_cad_stack_status(args: argparse.Namespace) -> None:
    """Report availability of the fixed PD One Python CAD module stack."""
    raw_inputs = [str(item).strip() for item in getattr(args, 'input', None) or [] if str(item).strip()]
    if len(raw_inputs) > CAD_DOCUMENT_MAX_INPUTS:
        fail(f'at most {CAD_DOCUMENT_MAX_INPUTS} cached CAD documents may be inspected')
    modules = {name: _module_spec_available(name) for name in PYTHON_CAD_STACK_MODULES}
    available = [name for name, present in modules.items() if present]
    missing = [name for name, present in modules.items() if not present]
    emit({'status': 'ok', 'capability': 'pd_one_python_cad_stack_status', 'python': sys.executable, 'python_version': sys.version.split()[0], 'modules': modules, 'available': available, 'missing': missing, 'available_count': len(available), 'missing_count': len(missing), 'documents': [_cad_document_identity(item) for item in raw_inputs], 'safety': {'read_only': True, 'shell_used': False, 'bounded_inputs': True, 'modules_imported': False, 'installation_performed': False, 'conversion_performed': False, 'source_system_writes_forbidden': True}})

def inspect_cad_runtime() -> dict[str, Any]:
    """Report fixed FreeCAD binary/lib presence without executing FreeCAD."""
    binaries = []
    for path in CAD_RUNTIME_CANDIDATE_BINS():
        exists = path.is_file()
        mode = None
        if exists:
            try:
                mode = oct(path.stat().st_mode)
            except OSError:
                logging.getLogger('pd_one_ops').exception('pd one command failed')
                mode = None
        binaries.append({'path': str(path), 'exists': exists, 'mode': mode})
    which = {name: shutil.which(name) for name in CAD_RUNTIME_WHICH_NAMES}
    lib_dirs = []
    for path in CAD_RUNTIME_LIB_DIRS():
        is_dir = path.is_dir()
        sample: list[str] = []
        truncated = False
        if is_dir:
            try:
                names = sorted(os.listdir(path))
            except OSError:
                logging.getLogger('pd_one_ops').exception('pd one command failed')
                names = []
            sample = names[:CAD_RUNTIME_DIR_SAMPLE]
            truncated = len(names) > CAD_RUNTIME_DIR_SAMPLE
        lib_dirs.append({'path': str(path), 'is_dir': is_dir, 'sample_names': sample, 'sample_truncated': truncated})
    return {'status': 'ok', 'capability': 'pd_one_cad_runtime_status', 'binaries': binaries, 'which': which, 'lib_dirs': lib_dirs, 'safety': {'read_only': True, 'shell_used': False, 'freecad_executed': False, 'source_system_writes_forbidden': True}}

def cmd_cad_runtime_status(args: argparse.Namespace) -> None:
    emit(inspect_cad_runtime())

def _step_geometry_header(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()[:STEP_GEOMETRY_HEADER_BYTES].decode('latin-1', errors='replace')
    if 'ISO-10303-21' not in raw or 'HEADER;' not in raw:
        fail('input does not contain an ISO-10303-21 STEP header')
    schema = ''
    match = re.search('FILE_SCHEMA\\s*\\(\\s*\\((.*?)\\)\\s*\\)\\s*;', raw, re.I | re.S)
    if match:
        schema = ' '.join(match.group(1).split())[:300]
    internal_name = ''
    match = re.search("FILE_NAME\\s*\\(\\s*'([^']*)'", raw, re.I | re.S)
    if match:
        internal_name = match.group(1)[:500]
    return {'signature_present': True, 'schema': schema, 'internal_name': internal_name}

def _step_geometry_json_input(raw_path: str) -> tuple[Path, dict[str, Any]]:
    from tools.pd_one_ops.pd_one_safe_ops_part2 import is_within
    text = str(raw_path or '').strip()
    if not text or len(text) > CAD_DOCUMENT_PATH_MAX_CHARS:
        fail('inspect JSON path is missing or too long')
    candidate = Path(text)
    if candidate.is_symlink():
        fail('inspect JSON path must not be a symlink')
    resolved = candidate.resolve(strict=False)
    if not any((is_within(resolved, root) for root in STEP_GEOMETRY_INPUT_ROOTS())):
        fail(f'inspect JSON is outside approved PD One document roots: {resolved}')
    suffix = resolved.suffix.lower()
    if suffix not in STEP_GEOMETRY_JSON_SUFFIXES:
        fail(f'inspect JSON suffix is not allowed: {suffix}')
    if not resolved.name.lower().endswith('inspect.json'):
        fail('input must be a bounded inspect.json artifact')
    if not resolved.is_file() or resolved.is_symlink():
        fail('inspect JSON input must be a regular, non-symlink file')
    size = resolved.stat().st_size
    if size <= 0 or size > STEP_GEOMETRY_JSON_MAX_BYTES:
        fail(f'inspect JSON size must be 1-{STEP_GEOMETRY_JSON_MAX_BYTES} bytes: {size}')
    return (resolved, {'path': str(resolved), 'name': resolved.name, 'suffix': suffix, 'size': size, 'sha256': hashlib.sha256(resolved.read_bytes()).hexdigest()})

def _step_geometry_kind_counts(items: list[Any]) -> dict[str, int]:
    counts: collections.Counter[str] = collections.Counter()
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get('kind')
        counts['None' if kind is None else str(kind)] += 1
    return dict(counts.most_common())

def _step_geometry_face_extra(face: dict[str, Any]) -> dict[str, Any] | None:
    kind = face.get('kind')
    slope = face.get('slope_from_horizontal_deg')
    include = kind not in {'Plane'}
    if isinstance(slope, (int, float)) and abs(float(slope)) >= 0.5:
        include = True
    if face.get('downward') is True:
        include = True
    if not include:
        return None
    return {key: face[key] for key in STEP_GEOMETRY_FACE_EXTRA_KEYS if key in face}

def _summarize_step_inspect_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        fail('inspect JSON must be an object')
    solids = payload.get('solids')
    if not isinstance(solids, list):
        fail('inspect JSON is missing a solids list')
    summarized: list[dict[str, Any]] = []
    for solid in solids[:STEP_GEOMETRY_MAX_SOLIDS]:
        if not isinstance(solid, dict):
            continue
        faces = solid.get('faces') if isinstance(solid.get('faces'), list) else []
        edges = solid.get('edges') if isinstance(solid.get('edges'), list) else []
        unknown: list[dict[str, Any]] = []
        unknown_count = 0
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            if edge.get('kind') not in STEP_GEOMETRY_UNKNOWN_EDGE_KINDS:
                continue
            unknown_count += 1
            if len(unknown) < STEP_GEOMETRY_MAX_UNKNOWN_EDGES:
                unknown.append({key: edge.get(key) for key in ('index', 'kind', 'length', 'closed') if key in edge})
        extras: list[dict[str, Any]] = []
        extras_truncated = False
        for face in faces:
            if not isinstance(face, dict):
                continue
            extra = _step_geometry_face_extra(face)
            if extra is None:
                continue
            extras.append(extra)
            if len(extras) >= STEP_GEOMETRY_MAX_FACE_EXTRAS:
                extras_truncated = True
                break
        bbox = solid.get('bbox') if isinstance(solid.get('bbox'), dict) else {}
        summarized.append({'index': solid.get('index'), 'volume': solid.get('volume'), 'size': bbox.get('size'), 'counts': solid.get('counts'), 'cylinder_radii': solid.get('cylinder_radii'), 'face_kinds': _step_geometry_kind_counts(faces), 'edge_kinds': _step_geometry_kind_counts(edges), 'unknown_edges': unknown, 'unknown_edge_count': unknown_count, 'face_extras': extras, 'face_extras_truncated': extras_truncated})
    return {'ok': bool(payload.get('ok')) if 'ok' in payload else None, 'valid': payload.get('valid'), 'solid_count': payload.get('solid_count', len(solids)), 'face_count': payload.get('face_count'), 'edge_count': payload.get('edge_count'), 'solids_truncated': bool(payload.get('solids_truncated')) or len(solids) > STEP_GEOMETRY_MAX_SOLIDS, 'solids': summarized}

def _step_geometry_input(raw_path: str) -> tuple[Path, dict[str, Any]]:
    from tools.pd_one_ops.pd_one_safe_ops_part2 import is_within
    text = str(raw_path or '').strip()
    if not text or len(text) > CAD_DOCUMENT_PATH_MAX_CHARS:
        fail('STEP path is missing or too long')
    candidate = Path(text)
    if candidate.is_symlink():
        fail('STEP path must not be a symlink')
    resolved = candidate.resolve(strict=False)
    if not any((is_within(resolved, root) for root in STEP_GEOMETRY_INPUT_ROOTS())):
        fail(f'STEP path is outside approved PD One document roots: {resolved}')
    suffix = resolved.suffix.lower()
    if suffix not in STEP_GEOMETRY_SUFFIXES:
        fail(f'STEP suffix is not allowed: {suffix}; input must be a regular .stp/.step file')
    if not resolved.is_file() or resolved.is_symlink():
        fail('STEP input must be a regular, non-symlink file')
    size = resolved.stat().st_size
    if size <= 0 or size > STEP_GEOMETRY_MAX_SOURCE_BYTES:
        fail(f'STEP size must be 1-{STEP_GEOMETRY_MAX_SOURCE_BYTES} bytes: {size}')
    header = _step_geometry_header(resolved)
    return (resolved, {'path': str(resolved), 'name': resolved.name, 'suffix': suffix, 'size': size, 'sha256': hashlib.sha256(resolved.read_bytes()).hexdigest(), 'step_header': header})

def cmd_step_geometry_inspect(args: argparse.Namespace) -> None:
    """Inspect one approved STEP/STP file, or summarize an existing inspect.json."""
    from tools.pd_one_ops.pd_one_safe_ops_part2 import is_within
    action = str(getattr(args, 'action', 'check') or 'check').strip().lower()
    if action not in {'check', 'inspect', 'summarize'}:
        fail('--action must be check, inspect, or summarize')
    if action == 'summarize':
        source, identity = _step_geometry_json_input(args.input)
        try:
            payload = json.loads(source.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            fail(f'inspect JSON is not valid: {exc}')
        emit({'status': 'ok', 'capability': 'pd_one_step_geometry_inspect', 'action': action, 'input': identity, 'script': None, 'freecadcmd': None, 'output': None, 'summary': _summarize_step_inspect_payload(payload), 'returncode': None, 'stdout_tail': '', 'stderr_tail': '', 'safety': {'admin_only': True, 'source_read_only': True, 'shell_used': False, 'freecad_invoked': False, 'fixed_script': False, 'arbitrary_script_forbidden': True, 'source_overwrite_forbidden': True, 'source_system_writes_forbidden': True, 'external_delivery': False, 'full_face_edge_dump': False}})
        return
    source, identity = _step_geometry_input(args.input)
    script = STEP_GEOMETRY_SCRIPT().resolve(strict=False)
    if not script.is_file() or script.is_symlink():
        fail(f'fixed STEP inspect script is missing: {script}')
    freecadcmd = find_bin('freecadcmd', extra=[str(STEP_GEOMETRY_FREECADCMD())])
    if not freecadcmd:
        fail('freecadcmd is not available')
    safety = {'admin_only': True, 'source_read_only': True, 'shell_used': False, 'fixed_script': True, 'arbitrary_script_forbidden': True, 'source_overwrite_forbidden': True, 'source_system_writes_forbidden': True, 'external_delivery': False, 'staged_output_root': str(STEP_GEOMETRY_OUTPUT_ROOT())}
    receipt: dict[str, Any] = {'status': 'ok', 'capability': 'pd_one_step_geometry_inspect', 'action': action, 'input': identity, 'script': str(script), 'freecadcmd': freecadcmd, 'output': None, 'summary': None, 'returncode': None, 'stdout_tail': '', 'stderr_tail': '', 'safety': safety}
    if action == 'check':
        emit(receipt)
        return
    source_key = hashlib.sha256(str(source).encode('utf-8')).hexdigest()[:12]
    safe_stem = re.sub('[^A-Za-z0-9._-]+', '_', source.stem)[:48] or 'step'
    output_dir = (STEP_GEOMETRY_OUTPUT_ROOT() / f'{safe_stem}-{source_key}').resolve(strict=False)
    if not is_within(output_dir, STEP_GEOMETRY_OUTPUT_ROOT()):
        fail('resolved output directory escaped the approved STEP inspect root')
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / 'inspect.json'
    command = [str(freecadcmd), str(script), '--pass', shlex.join([str(source), str(output)])]
    try:
        proc = run_capture(command, timeout=STEP_GEOMETRY_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'freecadcmd timed out after {STEP_GEOMETRY_TIMEOUT_SECONDS} seconds')
    receipt['returncode'] = proc.returncode
    receipt['stdout_tail'] = tail_text(proc.stdout, 1200)
    receipt['stderr_tail'] = tail_text(proc.stderr, 1200)
    if proc.returncode != 0:
        fail(f'freecadcmd inspect failed with exit {proc.returncode}: {tail_text(proc.stderr or proc.stdout, 800)}')
    if not output.is_file() or output.is_symlink():
        fail('inspect did not produce a regular output JSON')
    output_size = output.stat().st_size
    if output_size <= 0:
        fail('inspect output is empty')
    try:
        payload = json.loads(output.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'inspect output is not valid JSON: {exc}')
    receipt['output'] = {'path': str(output), 'size': output_size, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    receipt['summary'] = _summarize_step_inspect_payload(payload)
    emit(receipt)

def _step_printability_json_input(raw_path: str) -> tuple[Path, dict[str, Any]]:
    from tools.pd_one_ops.pd_one_safe_ops_part2 import is_within
    text = str(raw_path or '').strip()
    if not text or len(text) > CAD_DOCUMENT_PATH_MAX_CHARS:
        fail('printability JSON path is missing or too long')
    candidate = Path(text)
    if candidate.is_symlink():
        fail('printability JSON path must not be a symlink')
    resolved = candidate.resolve(strict=False)
    if not any((is_within(resolved, root) for root in STEP_GEOMETRY_INPUT_ROOTS())):
        fail(f'printability JSON is outside approved PD One document roots: {resolved}')
    suffix = resolved.suffix.lower()
    if suffix not in STEP_GEOMETRY_JSON_SUFFIXES:
        fail(f'printability JSON suffix is not allowed: {suffix}')
    name = resolved.name.lower()
    if name not in STEP_PRINTABILITY_JSON_NAMES and 'printability' not in name and ('preflight' not in name):
        fail('input must be a bounded official printability/preflight JSON artifact')
    if not resolved.is_file() or resolved.is_symlink():
        fail('printability JSON input must be a regular, non-symlink file')
    size = resolved.stat().st_size
    if size <= 0 or size > STEP_PRINTABILITY_JSON_MAX_BYTES:
        fail(f'printability JSON size must be 1-{STEP_PRINTABILITY_JSON_MAX_BYTES} bytes: {size}')
    return (resolved, {'path': str(resolved), 'name': resolved.name, 'suffix': suffix, 'size': size, 'sha256': hashlib.sha256(resolved.read_bytes()).hexdigest()})

def _summarize_step_printability_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        fail('printability JSON must be an object')
    geometry = payload.get('geometry') if isinstance(payload.get('geometry'), dict) else {}
    findings = payload.get('top_findings') if isinstance(payload.get('top_findings'), list) else []
    bounded_findings: list[dict[str, Any]] = []
    for item in findings[:STEP_PRINTABILITY_MAX_FINDINGS]:
        if not isinstance(item, dict):
            continue
        bounded_findings.append({key: item.get(key) for key in ('face_index', 'classification', 'minimum_slope_from_horizontal_deg', 'flagged_area_mm2', 'flagged_triangle_count', 'bbox_mm') if key in item})
    limitations = payload.get('limitations') if isinstance(payload.get('limitations'), list) else []
    return {'ok': payload.get('ok'), 'status': payload.get('status'), 'assumed_print_axis': payload.get('assumed_print_axis'), 'print_axis_source': payload.get('print_axis_source'), 'print_axis_reason': payload.get('print_axis_reason'), 'print_height_mm': payload.get('print_height_mm'), 'bed_area_mm2': payload.get('bed_area_mm2'), 'file_plus_z_preview': payload.get('file_plus_z_preview') if isinstance(payload.get('file_plus_z_preview'), dict) else None, 'threshold_slope_from_horizontal_deg': payload.get('threshold_slope_from_horizontal_deg'), 'orientation_reliable': payload.get('orientation_reliable'), 'flagged_triangle_count': payload.get('flagged_triangle_count'), 'flagged_area_mm2': payload.get('flagged_area_mm2'), 'flagged_face_count': payload.get('flagged_face_count'), 'raw_candidate_area_mm2': payload.get('raw_candidate_area_mm2'), 'suppressed_area_mm2': payload.get('suppressed_area_mm2'), 'suppressed_face_count': payload.get('suppressed_face_count'), 'suppression_counts': payload.get('suppression_counts') if isinstance(payload.get('suppression_counts'), dict) else None, 'geometry': {key: geometry.get(key) for key in ('valid', 'solid_count', 'shell_count', 'face_count', 'edge_count', 'bbox_mm') if key in geometry}, 'top_findings': bounded_findings, 'findings_truncated': len(findings) > STEP_PRINTABILITY_MAX_FINDINGS, 'limitations': [str(item)[:240] for item in limitations[:8]], 'error_class': payload.get('error_class'), 'error': str(payload.get('error') or '')[:400] or None}

def cmd_step_printability_analyze(args: argparse.Namespace) -> None:
    """Check, analyze, or summarize one approved STEP with the official printability analyzer."""
    from tools.pd_one_ops.pd_one_safe_ops_part2 import is_within
    action = str(getattr(args, 'action', 'check') or 'check').strip().lower()
    if action not in {'check', 'analyze', 'summarize'}:
        fail('--action must be check, analyze, or summarize')
    if action == 'summarize':
        source, identity = _step_printability_json_input(args.input)
        try:
            payload = json.loads(source.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            fail(f'printability JSON is not valid: {exc}')
        emit({'status': 'ok', 'capability': 'pd_one_step_printability_analyze', 'action': action, 'input': identity, 'script': None, 'freecadcmd': None, 'output': None, 'summary': _summarize_step_printability_payload(payload), 'returncode': None, 'stdout_tail': '', 'stderr_tail': '', 'safety': {'admin_only': True, 'source_read_only': True, 'shell_used': False, 'freecad_invoked': False, 'fixed_script': False, 'arbitrary_script_forbidden': True, 'source_overwrite_forbidden': True, 'source_copy_forbidden': True, 'source_system_writes_forbidden': True, 'external_delivery': False}})
        return
    source, identity = _step_geometry_input(args.input)
    script = STEP_PRINTABILITY_SCRIPT().resolve(strict=False)
    if not script.is_file() or script.is_symlink():
        fail(f'fixed STEP printability analyzer is missing: {script}')
    freecadcmd = find_bin('freecadcmd', extra=[str(STEP_GEOMETRY_FREECADCMD())])
    if not freecadcmd:
        fail('freecadcmd is not available')
    safety = {'admin_only': True, 'source_read_only': True, 'shell_used': False, 'fixed_script': True, 'arbitrary_script_forbidden': True, 'source_overwrite_forbidden': True, 'source_copy_forbidden': True, 'source_system_writes_forbidden': True, 'external_delivery': False, 'staged_output_root': str(STEP_PRINTABILITY_OUTPUT_ROOT())}
    receipt: dict[str, Any] = {'status': 'ok', 'capability': 'pd_one_step_printability_analyze', 'action': action, 'input': identity, 'script': str(script), 'freecadcmd': freecadcmd, 'output': None, 'summary': None, 'returncode': None, 'stdout_tail': '', 'stderr_tail': '', 'safety': safety}
    if action == 'check':
        emit(receipt)
        return
    source_key = hashlib.sha256(str(source).encode('utf-8')).hexdigest()[:12]
    safe_stem = re.sub('[^A-Za-z0-9._-]+', '_', source.stem)[:48] or 'step'
    output_dir = (STEP_PRINTABILITY_OUTPUT_ROOT() / f'{safe_stem}-{source_key}').resolve(strict=False)
    if not is_within(output_dir, STEP_PRINTABILITY_OUTPUT_ROOT()):
        fail('resolved output directory escaped the approved STEP printability root')
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / 'official_preflight.json'
    command = [str(freecadcmd), str(script), '--pass', shlex.join([str(source), '--json-out', str(output)])]
    try:
        proc = run_capture(command, timeout=STEP_PRINTABILITY_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'freecadcmd timed out after {STEP_PRINTABILITY_TIMEOUT_SECONDS} seconds')
    receipt['returncode'] = proc.returncode
    receipt['stdout_tail'] = tail_text(proc.stdout, 1200)
    receipt['stderr_tail'] = tail_text(proc.stderr, 1200)
    if not output.is_file() or output.is_symlink():
        fail(f'printability analyzer did not produce a regular output JSON: {tail_text(proc.stderr or proc.stdout, 800)}')
    output_size = output.stat().st_size
    if output_size <= 0:
        fail('printability output is empty')
    try:
        payload = json.loads(output.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'printability output is not valid JSON: {exc}')
    receipt['output'] = {'path': str(output), 'size': output_size, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    receipt['summary'] = _summarize_step_printability_payload(payload)
    receipt['status'] = 'ok' if payload.get('ok') else 'error'
    receipt['safety']['freecad_invoked'] = True
    emit(receipt)

def _python_docx_runtime_readback(python_path: Path) -> dict[str, Any]:
    probe = "import importlib.metadata,json,sys\ntry:\n import docx\n version=importlib.metadata.version('python-docx')\n import_ok=True\n module_version=getattr(docx,'__version__',None)\nexcept (ImportError, importlib.metadata.PackageNotFoundError):\n version=None\n import_ok=False\n module_version=None\nprint(json.dumps({'executable':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,'version':version,'module_version':module_version,'import_ok':import_ok}))\n"
    proc = run_capture([str(python_path), '-c', probe], timeout=30)
    if proc.returncode != 0:
        fail(f'target interpreter readback failed: {tail_text(proc.stderr, 800)}')
    try:
        readback = json.loads(proc.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'target interpreter returned invalid readback JSON: {exc}')
    expected_prefix = str(python_path.parent.parent)
    if readback.get('prefix') != expected_prefix or readback.get('prefix') == readback.get('base_prefix'):
        fail('target interpreter is not running with the approved release virtualenv prefix')
    return readback

def cmd_python_docx_dependency_repair(args: argparse.Namespace) -> None:
    """Inspect or install one ticket-bound dependency in the exact PD One release virtualenv."""
    ticket_id = str(args.ticket_id or '').strip()
    action = str(args.action or 'inspect').strip().lower()
    if ticket_id != PYTHON_DOCX_REPAIR_TICKET_ID():
        fail('ticket_id is not authorized for this exact dependency repair')
    if action not in {'inspect', 'install'}:
        fail('--action must be inspect or install')
    python_path = PYTHON_DOCX_REPAIR_PYTHON()
    if not python_path.is_absolute() or str(python_path) != resolve_configured_path('~/.hermes/releases/pdone-current/.venv/bin/python'):
        fail('configured dependency-repair interpreter path is invalid')
    if not python_path.is_file() or not os.access(python_path, os.X_OK):
        fail(f'approved release virtualenv interpreter is not executable: {python_path}')
    before = _python_docx_runtime_readback(python_path)
    already_satisfied = before.get('import_ok') is True and before.get('version') == PYTHON_DOCX_REPAIR_VERSION
    installation_performed = False
    install_returncode = None
    if action == 'install' and (not already_satisfied):
        if args.confirm_live_write != PYTHON_DOCX_REPAIR_CONFIRMATION():
            fail(f'install requires --confirm-live-write={PYTHON_DOCX_REPAIR_CONFIRMATION()!r}')
        uv_path = shutil.which('uv', path=str(PATH_BASE()) + os.pathsep + str(site_text('PATH')))
        if not uv_path:
            fail('uv executable is unavailable')
        proc = run_capture([uv_path, 'pip', 'install', '--python', str(python_path), f'{PYTHON_DOCX_REPAIR_PACKAGE}=={PYTHON_DOCX_REPAIR_VERSION}'], timeout=180)
        install_returncode = proc.returncode
        if proc.returncode != 0:
            fail(f'bounded dependency install failed: {tail_text(proc.stderr, 1200)}')
        installation_performed = True
    elif action != 'install' and args.confirm_live_write:
        fail('--confirm-live-write is only valid with --action install')
    after = _python_docx_runtime_readback(python_path)
    satisfied = after.get('import_ok') is True and after.get('version') == PYTHON_DOCX_REPAIR_VERSION
    if action == 'install' and (not satisfied):
        fail('post-install readback did not verify python-docx==1.2.0 in the approved release virtualenv')
    emit({'status': 'ok', 'capability': 'pd_one_python_docx_dependency_repair', 'ticket_id': ticket_id, 'action': action, 'package': PYTHON_DOCX_REPAIR_PACKAGE, 'version': PYTHON_DOCX_REPAIR_VERSION, 'python': str(python_path), 'before': before, 'after': after, 'satisfied': satisfied, 'installation_performed': installation_performed, 'install_returncode': install_returncode, 'safety': {'shell_used': False, 'exact_ticket_bound': True, 'exact_package_bound': True, 'exact_virtualenv_bound': True, 'global_python_modification_forbidden': True, 'source_system_writes_forbidden': True}})

def _approved_hermes_result_path(raw_path: str) -> Path:
    from tools.pd_one_ops.pd_one_safe_ops_part2 import is_within
    value = str(raw_path or '').strip()
    if not value or len(value) > 500:
        fail('--input is required and must be at most 500 characters')
    path = Path(value).resolve(strict=False)
    if not is_within(path, HERMES_RESULTS_ROOT) or path == HERMES_RESULTS_ROOT.resolve(strict=False):
        fail(f'input must be an artifact under {HERMES_RESULTS_ROOT}')
    if path.suffix.lower() not in {'.json', '.txt'}:
        fail('hermes-result-messages-summary only supports .json and .txt result artifacts')
    if not path.is_file():
        fail(f'result artifact does not exist or is not a regular file: {path}')
    try:
        size_bytes = path.stat().st_size
    except OSError as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'unable to stat result artifact: {exc}')
    if size_bytes > HERMES_RESULT_SUMMARY_MAX_BYTES:
        fail(f'result artifact exceeds {HERMES_RESULT_SUMMARY_MAX_BYTES} bytes')
    return path

def _result_summary_text(value: Any) -> str:
    text = re.sub('\\s+', ' ', str(value or '')).strip()
    if len(text) > HERMES_RESULT_SUMMARY_MAX_TEXT_CHARS:
        return text[:HERMES_RESULT_SUMMARY_MAX_TEXT_CHARS] + '…'
    return text

def _result_content_summary(content: Any) -> str:
    if isinstance(content, list):
        kinds: list[str] = []
        for item in content[:HERMES_RESULT_SUMMARY_MAX_CONTENT_ITEMS]:
            if isinstance(item, dict):
                kind = item.get('type') or item.get('name') or item.get('tool_name') or 'dict'
                kinds.append(_result_summary_text(kind) or 'dict')
            else:
                kinds.append(type(item).__name__)
        if len(content) > HERMES_RESULT_SUMMARY_MAX_CONTENT_ITEMS:
            kinds.append('…')
        return 'list:' + ','.join(kinds)
    return _result_summary_text(content)

def cmd_hermes_result_messages_summary(args: argparse.Namespace) -> None:
    """Summarize message metadata/content shapes from one bounded local result artifact."""
    path = _approved_hermes_result_path(args.input)
    max_messages = _bounded_int(args.max_messages, '--max-messages', 1, HERMES_RESULT_SUMMARY_MAX_MESSAGES)
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'result artifact is not valid JSON: {exc}')
    if not isinstance(obj, dict):
        fail('result artifact must contain a JSON object')
    messages = obj.get('messages')
    if not isinstance(messages, list):
        fail('result artifact must contain a messages array')
    summaries: list[dict[str, Any]] = []
    invalid_messages = 0
    for index, message in enumerate(messages[:max_messages]):
        if not isinstance(message, dict):
            invalid_messages += 1
            summaries.append({'index': index, 'invalid_message': True, 'content_summary': _result_content_summary(message)})
            continue
        summaries.append({'index': index, 'id': _result_summary_text(message.get('id')), 'role': _result_summary_text(message.get('role')), 'tool': _result_summary_text(message.get('tool_name') or message.get('name')), 'content_summary': _result_content_summary(message.get('content'))})
    emit({'status': 'partial' if invalid_messages else 'ok', 'capability': 'pd_one_hermes_result_messages_summary', 'input': str(path), 'file': {'size_bytes': path.stat().st_size, 'suffix': path.suffix.lower()}, 'message_count': len(messages), 'messages_inspected': len(summaries), 'messages_truncated': len(messages) > max_messages, 'max_messages': max_messages, 'invalid_message_count': invalid_messages, 'messages': summaries, 'safety': {'read_only': True, 'admin_only': True, 'approved_temp_root_only': True, 'bounded_file_size': True, 'bounded_message_receipt': True, 'shell_used': False, 'source_system_writes_forbidden': True, 'external_delivery_forbidden': True}})

def _json_artifact_type_name(value: Any) -> str:
    if value is None:
        return 'NoneType'
    return type(value).__name__

def _json_artifact_length(value: Any) -> int | None:
    if isinstance(value, (str, bytes, bytearray, dict, list, tuple, set)):
        return len(value)
    return None

def _json_artifact_key_list(mapping: dict[str, Any], limit: int) -> list[str]:
    keys: list[str] = []
    for key in mapping.keys():
        text = str(key)
        if len(text) > JSON_ARTIFACT_INSPECT_KEY_CHARS:
            text = text[:JSON_ARTIFACT_INSPECT_KEY_CHARS] + '…'
        keys.append(text)
        if len(keys) >= limit:
            break
    return keys

def _summarize_json_artifact(data: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {'top_type': _json_artifact_type_name(data), 'length': _json_artifact_length(data)}
    if isinstance(data, dict):
        key_count = len(data)
        keys = _json_artifact_key_list(data, JSON_ARTIFACT_INSPECT_MAX_KEYS)
        summary['key_count'] = key_count
        summary['keys'] = keys
        summary['keys_truncated'] = key_count > JSON_ARTIFACT_INSPECT_MAX_KEYS
        fields: list[dict[str, Any]] = []
        for raw_key in list(data.keys())[:JSON_ARTIFACT_INSPECT_MAX_KEYS]:
            value = data[raw_key]
            field: dict[str, Any] = {'key': str(raw_key)[:JSON_ARTIFACT_INSPECT_KEY_CHARS], 'type': _json_artifact_type_name(value), 'length': _json_artifact_length(value)}
            if isinstance(value, list) and value:
                sample = value[0]
                field['sample0_type'] = _json_artifact_type_name(sample)
                if isinstance(sample, dict):
                    field['sample0_key_count'] = len(sample)
                    field['sample0_keys'] = _json_artifact_key_list(sample, JSON_ARTIFACT_INSPECT_MAX_SAMPLE_KEYS)
                    field['sample0_keys_truncated'] = len(sample) > JSON_ARTIFACT_INSPECT_MAX_SAMPLE_KEYS
                elif isinstance(sample, list):
                    field['sample0_length'] = len(sample)
                    if sample:
                        field['sample0_item_type'] = _json_artifact_type_name(sample[0])
            fields.append(field)
        summary['fields'] = fields
    elif isinstance(data, list) and data:
        sample = data[0]
        summary['sample0_type'] = _json_artifact_type_name(sample)
        if isinstance(sample, dict):
            summary['sample0_key_count'] = len(sample)
            summary['sample0_keys'] = _json_artifact_key_list(sample, JSON_ARTIFACT_INSPECT_MAX_SAMPLE_KEYS)
            summary['sample0_keys_truncated'] = len(sample) > JSON_ARTIFACT_INSPECT_MAX_SAMPLE_KEYS
    return summary

def _approved_json_artifact_inspect_path(raw_path: str) -> Path:
    from tools.pd_one_ops.pd_one_safe_ops_part2 import is_within
    value = str(raw_path or '').strip()
    if not value or len(value) > 500:
        fail('--input is required and must be at most 500 characters')
    path = Path(value).expanduser()
    if path.is_symlink():
        fail('symlinks are not allowed')
    resolved = path.resolve(strict=False)
    if resolved.suffix.lower() != '.json':
        fail('json-artifact-inspect only supports .json files')
    if not any((is_within(resolved, root) for root in JSON_ARTIFACT_INSPECT_ROOTS())):
        fail('input must be a JSON file under an approved PD One artifact root')
    if resolved.is_symlink() or not resolved.is_file():
        fail(f'input does not exist or is not a regular file: {resolved}')
    try:
        size_bytes = resolved.stat().st_size
    except OSError as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail(f'unable to stat JSON artifact: {exc}')
    if size_bytes > JSON_ARTIFACT_INSPECT_MAX_BYTES:
        fail(f'JSON artifact exceeds {JSON_ARTIFACT_INSPECT_MAX_BYTES} bytes')
    return resolved

def cmd_json_artifact_inspect(args: argparse.Namespace) -> None:
    """Return bounded JSON structure receipts without dumping values."""
    raw_inputs = [str(item).strip() for item in args.input or [] if str(item).strip()]
    if not raw_inputs:
        fail('at least one --input is required')
    if len(raw_inputs) > JSON_ARTIFACT_INSPECT_MAX_FILES:
        fail(f'json-artifact-inspect accepts at most {JSON_ARTIFACT_INSPECT_MAX_FILES} files')
    files: list[dict[str, Any]] = []
    for raw in raw_inputs:
        path = _approved_json_artifact_inspect_path(raw)
        size_bytes = path.stat().st_size
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            fail(f'invalid JSON in {path}: {exc}')
        files.append({'path': str(path), 'size_bytes': size_bytes, 'sha256': digest, 'structure': _summarize_json_artifact(data)})
    emit({'status': 'ok', 'capability': 'pd_one_json_artifact_inspect', 'file_count': len(files), 'files': files, 'safety': {'read_only': True, 'admin_only': True, 'approved_roots_only': True, 'values_omitted': True, 'shell_used': False, 'source_system_writes_forbidden': True, 'external_delivery_forbidden': True}})

def _approved_local_file_search_path(raw_path: str) -> Path:
    from tools.pd_one_ops.pd_one_safe_ops_part2 import is_within
    value = str(raw_path or '').strip()
    if not value or len(value) > 500:
        fail('--path is required and must be at most 500 characters')
    path = Path(value).expanduser()
    if path.is_symlink():
        fail('symlinks are not allowed')
    resolved = path.resolve(strict=False)
    if not any((is_within(resolved, root) for root in LOCAL_FILE_SEARCH_ROOTS())):
        fail('path must stay under an approved PD One root; home-directory searches are forbidden')
    if resolved.is_symlink():
        fail('symlinks are not allowed')
    return resolved

def _validate_local_file_search_pattern(raw_pattern: str) -> str:
    text = str(raw_pattern or '').strip()
    if not text or len(text) > LOCAL_FILE_SEARCH_MAX_PATTERN_CHARS:
        fail(f'--pattern is required and must be at most {LOCAL_FILE_SEARCH_MAX_PATTERN_CHARS} characters')
    if any((marker in text for marker in ('/', '\\', '..', '\x00'))):
        fail('pattern must be a filename glob without path separators')
    if '**' in text:
        fail('recursive ** globs are not allowed')
    return text

def _iter_local_file_search_files(root: Path):
    stack = [root]
    seen = 0
    while stack:
        current = stack.pop()
        if current.is_symlink() or not current.is_dir():
            continue
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        _pd_is_dir = entry.is_dir(follow_symlinks=False)
                        if _pd_is_dir and (entry.name.startswith('.') or entry.name in {'__pycache__', 'node_modules'}):
                            continue
                        if _pd_is_dir:
                            stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        seen += 1
                        if seen > LOCAL_FILE_SEARCH_MAX_WALK_FILES:
                            return
                        yield Path(entry.path)
                    except OSError:
                        logging.getLogger('pd_one_ops').exception('pd one command failed')
                        continue
        except OSError:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            continue

def cmd_local_file_search(args: argparse.Namespace) -> None:
    """Return bounded local path/glob identities without dumping contents."""
    raw_paths = [str(item).strip() for item in getattr(args, 'path', None) or [] if str(item).strip()]
    raw_patterns = [str(item).strip() for item in getattr(args, 'pattern', None) or [] if str(item).strip()]
    if not raw_paths and (not raw_patterns):
        fail('provide at least one --path or --pattern')
    if len(raw_paths) > LOCAL_FILE_SEARCH_MAX_PATHS:
        fail(f'local-file-search accepts at most {LOCAL_FILE_SEARCH_MAX_PATHS} --path values')
    if len(raw_patterns) > LOCAL_FILE_SEARCH_MAX_PATTERNS:
        fail(f'local-file-search accepts at most {LOCAL_FILE_SEARCH_MAX_PATTERNS} --pattern values')
    path_checks: list[dict[str, Any]] = []
    for raw in raw_paths:
        resolved = _approved_local_file_search_path(raw)
        exists = resolved.is_file() and (not resolved.is_symlink())
        size_bytes = None
        mtime_utc = None
        if exists:
            stat = resolved.stat()
            size_bytes = stat.st_size
            mtime_utc = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        path_checks.append({'path': str(resolved), 'exists': exists, 'suffix': resolved.suffix.lower(), 'size_bytes': size_bytes, 'mtime_utc': mtime_utc})
    searches: list[dict[str, Any]] = []
    walk_truncated = False
    for pattern in (_validate_local_file_search_pattern(item) for item in raw_patterns):
        matches: list[dict[str, Any]] = []
        truncated = False
        seen: set[str] = set()
        walked = 0
        for root in LOCAL_FILE_SEARCH_ROOTS():
            if not root.exists() or root.is_symlink() or (not root.is_dir()):
                continue
            for candidate in _iter_local_file_search_files(root):
                walked += 1
                if walked > LOCAL_FILE_SEARCH_MAX_WALK_FILES:
                    walk_truncated = True
                    truncated = True
                    break
                name = candidate.name
                try:
                    relative = str(candidate.relative_to(root))
                except ValueError:
                    logging.getLogger('pd_one_ops').exception('pd one command failed')
                    continue
                if not (fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(relative, pattern)):
                    continue
                key = str(candidate)
                if key in seen:
                    continue
                seen.add(key)
                if len(matches) >= LOCAL_FILE_SEARCH_MAX_MATCHES:
                    truncated = True
                    break
                matches.append({'name': name, 'relative_path': relative, 'root': str(root), 'suffix': candidate.suffix.lower(), 'size_bytes': candidate.stat().st_size})
            if truncated:
                break
        searches.append({'pattern': pattern, 'match_count': len(matches), 'truncated': truncated, 'matches': matches})
    emit({'status': 'ok', 'capability': 'pd_one_local_file_search', 'path_count': len(path_checks), 'search_count': len(searches), 'path_checks': path_checks, 'searches': searches, 'walk_truncated': walk_truncated, 'guidance': 'Use native read_file for explicit approved-path content. This wrapper never dumps file contents.', 'safety': {'read_only': True, 'admin_only': True, 'approved_roots_only': True, 'contents_returned': False, 'home_root_search_forbidden': True, 'shell_used': False, 'source_system_writes_forbidden': True, 'external_delivery_forbidden': True}})

def cmd_sysstat_summary(args: argparse.Namespace) -> None:
    requested_hours = max(1, int(args.hours))
    window_hours = min(requested_hours, SYSSTAT_SUMMARY_MAX_HOURS)
    sadf = find_bin('sadf')
    if not sadf:
        fail('sadf not found on PATH')
    files = _sysstat_select_log_files(window_hours)
    if not files:
        fail(f'no sysstat log files found under {SYSSTAT_LOG_ROOT}')
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)
    reports: dict[str, dict[str, Any]] = {}
    notes: list[str] = []
    for metric_name, sadf_args, focus_columns in SYSSTAT_SUMMARY_METRIC_SPECS:
        report = _sysstat_metric_report(sadf=sadf, metric_name=metric_name, sadf_args=list(sadf_args), focus_columns=list(focus_columns), files=files, window_start=window_start, window_end=now)
        reports[metric_name] = report
        if report['errors']:
            notes.append(f'{metric_name}: {len(report['errors'])} sadf read error(s)')
        if not report['samples']:
            notes.append(f'{metric_name}: no samples in window')
    cpu_pressure_p95 = (reports['cpu_pressure']['focus'].get('%scpu-300') or {}).get('p95')
    io_pressure_p95 = (reports['io_pressure']['focus'].get('%sio-300') or {}).get('p95')
    mem_pressure_p95 = (reports['memory_pressure']['focus'].get('%smem-300') or {}).get('p95')
    load15_p95 = (reports['load']['focus'].get('ldavg-15') or {}).get('p95')
    mem_used_p95 = (reports['memory']['focus'].get('%memused') or {}).get('p95')
    swap_used_p95 = (reports['swap']['focus'].get('%swpused') or {}).get('p95')
    cpu_count = max(1, os.cpu_count() or 1)
    load15_per_cpu_p95 = load15_p95 / cpu_count if isinstance(load15_p95, (int, float)) else None
    memory_available_pct_p95 = 100.0 - mem_used_p95 if isinstance(mem_used_p95, (int, float)) else None
    checks = [{'name': 'cpu_pressure_p95', 'value': round(cpu_pressure_p95, 3) if isinstance(cpu_pressure_p95, (int, float)) else None, 'threshold': 20.0, 'state': _sysstat_state_high(cpu_pressure_p95 if isinstance(cpu_pressure_p95, (int, float)) else None, 10.0, 20.0)}, {'name': 'load15_per_cpu_p95', 'value': round(load15_per_cpu_p95, 3) if isinstance(load15_per_cpu_p95, (int, float)) else None, 'threshold': 1.75, 'state': _sysstat_state_high(load15_per_cpu_p95 if isinstance(load15_per_cpu_p95, (int, float)) else None, 1.0, 1.75)}, {'name': 'io_pressure_p95', 'value': round(io_pressure_p95, 3) if isinstance(io_pressure_p95, (int, float)) else None, 'threshold': 20.0, 'state': _sysstat_state_high(io_pressure_p95 if isinstance(io_pressure_p95, (int, float)) else None, 10.0, 20.0)}, {'name': 'memory_pressure_p95', 'value': round(mem_pressure_p95, 3) if isinstance(mem_pressure_p95, (int, float)) else None, 'threshold': 15.0, 'state': _sysstat_state_high(mem_pressure_p95 if isinstance(mem_pressure_p95, (int, float)) else None, 10.0, 15.0)}, {'name': 'memory_available_pct_p95', 'value': round(memory_available_pct_p95, 3) if isinstance(memory_available_pct_p95, (int, float)) else None, 'threshold': 15.0, 'state': _sysstat_state_low(memory_available_pct_p95 if isinstance(memory_available_pct_p95, (int, float)) else None, 25.0, 15.0)}, {'name': 'swap_used_pct_p95', 'value': round(swap_used_p95, 3) if isinstance(swap_used_p95, (int, float)) else None, 'threshold': 40.0, 'state': _sysstat_state_high(swap_used_p95 if isinstance(swap_used_p95, (int, float)) else None, 25.0, 40.0)}]
    if any((check['state'] == 'high' for check in checks)):
        overall_state = 'high'
    elif any((check['state'] == 'watch' for check in checks)):
        overall_state = 'watch'
    else:
        overall_state = 'ok'
    if overall_state == 'ok':
        overall_summary = 'CPU, load, PSI, memory, and swap stay within expected bounds over the selected window.'
    elif overall_state == 'watch':
        overall_summary = 'One or more metrics are approaching the warning threshold; review the watch items before the next escalation window.'
    else:
        overall_summary = 'One or more metrics are above threshold; investigate the high-severity checks and associated pressure sources.'
    emit({'status': 'ok', 'capability': 'pd_one_sysstat_summary', 'requested_hours': requested_hours, 'window_hours': window_hours, 'window_start_utc': window_start.isoformat().replace('+00:00', 'Z'), 'window_end_utc': now.isoformat().replace('+00:00', 'Z'), 'host': os.uname().nodename, 'files_considered': [str(path) for path in files], 'metrics': reports, 'assessment': {'overall_state': overall_state, 'summary': overall_summary, 'cpu_count': cpu_count, 'checks': checks}, 'notes': notes, 'safety': {'read_only': True, 'shell_used': False, 'sadf_used': True, 'window_bounded_hours': window_hours, 'source_system_writes_forbidden': True}})

def cmd_ollama_embedding_triage(args: argparse.Namespace) -> None:
    unit = _validated_probe_name(args.unit, 'unit')
    container = _validated_probe_name(args.container, 'container')
    peer_container = (args.peer_container or '').strip()
    peer_container = _validated_probe_name(peer_container, 'peer-container') if peer_container else ''
    port = _bounded_int(args.port, 'port', 1, 65535)
    lookback_hours = _bounded_int(args.lookback_hours, 'lookback-hours', 1, 48)
    container_tail_lines = _bounded_int(args.container_tail_lines, 'container-tail-lines', 100, OLLAMA_EMBEDDING_MAX_CONTAINER_TAIL_LINES)
    journal_tail_lines = _bounded_int(args.journal_tail_lines, 'journal-tail-lines', 20, OLLAMA_EMBEDDING_MAX_JOURNAL_TAIL_LINES)
    systemctl = find_bin('systemctl')
    journalctl = find_bin('journalctl')
    docker = find_bin('docker')
    ss_bin = find_bin('ss')
    warnings: list[str] = []
    sources: list[dict[str, Any]] = []
    unit_probe: dict[str, Any]
    if systemctl:
        unit_probe = _probe_text([systemctl, '--user', 'show', unit, '-p', 'Id', '-p', 'LoadState', '-p', 'ActiveState', '-p', 'SubState', '-p', 'Result', '-p', 'ExecMainStatus', '-p', 'MainPID', '-p', 'UnitFileState', '-p', 'FragmentPath'], timeout=20)
        unit_probe['stdout_tail'] = tail_text(unit_probe.pop('stdout', ''), 4000)
        unit_probe['stderr_tail'] = tail_text(unit_probe.pop('stderr', ''), 2000)
        unit_probe['properties'] = _parse_key_value_lines(unit_probe['stdout_tail'])
        if unit_probe['status'] != 'ok':
            warnings.append('systemctl_show_failed')
    else:
        unit_probe = {'command': ['systemctl', '--user', 'show', unit], 'status': 'error', 'error': 'binary_not_found', 'returncode': 127, 'stdout_tail': '', 'stderr_tail': '', 'properties': {}}
        warnings.append('systemctl_missing')
    journal_probe: dict[str, Any]
    if journalctl:
        journal_probe = _probe_text([journalctl, '--user', '-u', unit, '--since', f'{lookback_hours} hours ago', '--no-pager', '-n', str(journal_tail_lines)], timeout=60)
        journal_text = journal_probe.pop('stdout', '')
        journal_probe['stdout_tail'] = tail_text(journal_text, 4000)
        journal_probe['stderr_tail'] = tail_text(journal_probe.pop('stderr', ''), 2000)
        journal_probe['line_count'] = len(journal_text.splitlines())
        journal_probe.update(_scan_embedding_log_text('journalctl', journal_text))
        sources.append(journal_probe)
        if journal_probe['status'] != 'ok':
            warnings.append('journalctl_failed')
    else:
        journal_probe = {'command': ['journalctl', '--user', '-u', unit], 'status': 'error', 'error': 'binary_not_found', 'returncode': 127, 'stdout_tail': '', 'stderr_tail': '', 'line_count': 0, **_scan_embedding_log_text('journalctl', '')}
        warnings.append('journalctl_missing')
    listener_probe: dict[str, Any]
    if ss_bin:
        listener_probe = _probe_text([ss_bin, '-H', '-ltnp', f'sport = :{port}'], timeout=20)
        listener_text = listener_probe.pop('stdout', '')
        listener_probe['stdout_tail'] = tail_text(listener_text, 2000)
        listener_probe['stderr_tail'] = tail_text(listener_probe.pop('stderr', ''), 2000)
        listener_probe['lines'] = [line for line in listener_text.splitlines() if line.strip()]
        listener_probe['listening'] = bool(listener_probe['lines'])
        if listener_probe['status'] != 'ok':
            warnings.append('ss_listen_probe_failed')
    else:
        listener_probe = {'command': ['ss', '-H', '-ltnp', f'sport = :{port}'], 'status': 'error', 'error': 'binary_not_found', 'returncode': 127, 'stdout_tail': '', 'stderr_tail': '', 'lines': [], 'listening': False}
        warnings.append('ss_missing')
    container_probes: list[dict[str, Any]] = []
    container_names = [container] + ([peer_container] if peer_container else [])
    if docker:
        for name in container_names:
            probe = _probe_text([docker, 'logs', '--since', f'{lookback_hours}h', '--tail', str(container_tail_lines), name], timeout=90)
            text = probe.pop('stdout', '')
            probe['stdout_tail'] = tail_text(text, 4000)
            probe['stderr_tail'] = tail_text(probe.pop('stderr', ''), 2000)
            probe['line_count'] = len(text.splitlines())
            probe.update(_scan_embedding_log_text(name, text))
            probe['name'] = name
            container_probes.append(probe)
            if probe['status'] != 'ok':
                warnings.append(f'docker_logs_failed:{name}')
    else:
        warnings.append('docker_missing')
        for name in container_names:
            container_probes.append({'name': name, 'command': ['docker', 'logs', '--since', f'{lookback_hours}h', '--tail', str(container_tail_lines), name], 'status': 'error', 'error': 'binary_not_found', 'returncode': 127, 'stdout_tail': '', 'stderr_tail': '', 'line_count': 0, **_scan_embedding_log_text(name, '')})
    aggregate_counts = {name: 0 for name in OLLAMA_EMBEDDING_LOG_PATTERNS}
    aggregate_matching_lines = 0
    for probe in sources + container_probes:
        for name, count in probe.get('pattern_counts', {}).items():
            aggregate_counts[name] = aggregate_counts.get(name, 0) + int(count)
        aggregate_matching_lines += int(probe.get('matching_line_count', 0))
    unit_properties = unit_probe.get('properties', {}) if isinstance(unit_probe.get('properties'), dict) else {}
    unit_active_state = str(unit_properties.get('ActiveState', ''))
    unit_result = str(unit_properties.get('Result', ''))
    overall_status = 'ok' if not warnings else 'partial'
    payload = {'status': overall_status, 'capability': 'pd_one_ollama_embedding_triage', 'unit': {'name': unit, 'probe': unit_probe, 'active_state': unit_active_state, 'result': unit_result}, 'listener': {'port': port, 'probe': listener_probe, 'listening': bool(listener_probe.get('listening'))}, 'journal': journal_probe, 'containers': container_probes, 'summary': {'lookback_hours': lookback_hours, 'container_tail_lines': container_tail_lines, 'journal_tail_lines': journal_tail_lines, 'unit_active_state': unit_active_state, 'unit_result': unit_result, 'listener_present': bool(listener_probe.get('listening')), 'container_names': container_names, 'pattern_counts': aggregate_counts, 'matching_line_count': aggregate_matching_lines, 'sample_total': sum((len(probe.get('sample_matches', [])) for probe in sources + container_probes))}, 'signals': {'unit_failed': unit_active_state == 'failed' or unit_result in {'timeout', 'exit-code'}, 'listener_missing': not bool(listener_probe.get('listening')), 'container_errors': [probe['name'] for probe in container_probes if probe.get('status') != 'ok']}, 'warnings': warnings, 'safety': {'read_only': True, 'shell_used': False, 'bounded_calls_required': True, 'bounded_logs': True, 'no_privileged_action_executed': True, 'source_system_writes_forbidden': True}}
    emit(payload)

def cmd_ollama_embedding_watchdog_triage(args: argparse.Namespace) -> None:
    unit = _validated_probe_name(args.unit, 'unit')
    lookback_hours = _bounded_int(args.lookback_hours, 'lookback-hours', 1, 48)
    journal_tail_lines = _bounded_int(args.journal_tail_lines, 'journal-tail-lines', 20, OLLAMA_EMBEDDING_WATCHDOG_MAX_JOURNAL_TAIL_LINES)
    journalctl = find_bin('journalctl')
    warnings: list[str] = []
    journal_probe: dict[str, Any]
    if journalctl:
        journal_probe = _probe_text([journalctl, '--user', '-u', unit, '--since', f'{lookback_hours} hours ago', '--no-pager', '-n', str(journal_tail_lines)], timeout=60)
        journal_text = journal_probe.pop('stdout', '')
        journal_probe['stdout_tail'] = tail_text(journal_text, 4000)
        journal_probe['stderr_tail'] = tail_text(journal_probe.pop('stderr', ''), 2000)
        journal_probe.update(_scan_embedding_watchdog_log_text(unit, journal_text))
        if journal_probe['status'] != 'ok':
            warnings.append('journalctl_failed')
    else:
        journal_probe = {'command': ['journalctl', '--user', '-u', unit], 'status': 'error', 'error': 'binary_not_found', 'returncode': 127, 'stdout_tail': '', 'stderr_tail': '', **_scan_embedding_watchdog_log_text(unit, '')}
        warnings.append('journalctl_missing')
    matching_line_count = int(journal_probe.get('matching_line_count', 0))
    remote_ok_true = int(journal_probe.get('remote_ok_true', 0))
    remote_ok_false = int(journal_probe.get('remote_ok_false', 0))
    mode_remote = int(journal_probe.get('mode_remote', 0))
    mode_local = int(journal_probe.get('mode_local', 0))
    switch_events = int(journal_probe.get('switch_events', 0))
    service_failures = int(journal_probe.get('service_failures', 0))
    if warnings:
        overall_state = 'partial'
    elif service_failures > 0 or remote_ok_false > remote_ok_true:
        overall_state = 'high'
    elif remote_ok_false > 0 or mode_local > 0 or switch_events > 0:
        overall_state = 'watch'
    elif matching_line_count > 0:
        overall_state = 'ok'
    else:
        overall_state = 'watch'
    summary = {'log_lines': int(journal_probe.get('log_lines', 0)), 'matching_line_count': matching_line_count, 'remote_ok_true': remote_ok_true, 'remote_ok_false': remote_ok_false, 'mode_remote': mode_remote, 'mode_local': mode_local, 'switch_events': switch_events, 'service_failures': service_failures}
    summary_text = f'Observed {summary['log_lines']} log lines; remote_ok=True {remote_ok_true}, remote_ok=False {remote_ok_false}; mode=remote {mode_remote}, mode=local {mode_local}; switched Honcho embeddings {switch_events}; service failures {service_failures}.'
    emit({'status': 'ok' if not warnings else 'partial', 'capability': 'pd_one_ollama_embedding_watchdog_triage', 'unit': {'name': unit, 'journal_probe': journal_probe}, 'summary': summary, 'assessment': {'overall_state': overall_state, 'summary': summary_text}, 'warnings': warnings, 'safety': {'read_only': True, 'journalctl_used': True, 'bounded_window_hours': lookback_hours, 'bounded_journal_tail_lines': journal_tail_lines, 'source_system_writes_forbidden': True}})

def validate_mattermost_id(value: str, label: str='id') -> str:
    value = (value or '').strip()
    if not re.match('^[a-z0-9]{26}$', value):
        fail(f'invalid Mattermost {label}: {value!r}')
    return value

def validate_mattermost_name(value: str, label: str) -> str:
    value = (value or '').strip()
    if not re.match('^[a-z0-9][a-z0-9_-]{0,63}$', value):
        fail(f'invalid Mattermost {label}: {value!r}')
    return value

def load_mattermost_review_log_module() -> Any:
    if not MATTERMOST_REVIEW_LOG().exists():
        fail(f'Mattermost helper not found: {MATTERMOST_REVIEW_LOG()}')
    sys.path.append(str(MATTERMOST_REVIEW_LOG().parent))
    spec = importlib.util.spec_from_file_location('pdone_mattermost_review_log', MATTERMOST_REVIEW_LOG())
    if spec is None or spec.loader is None:
        fail('could not load Mattermost helper')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def mattermost_context() -> tuple[str, dict[str, str], dict[str, Any]]:
    module = load_mattermost_review_log_module()
    base, _token, headers, me = module.mattermost_context()
    return (base, headers, me)

def mm_request(method: str, base: str, headers: dict[str, str], path: str, **kwargs: Any) -> Any:
    resp = requests.request(method, f'{base}{path}', headers=headers, timeout=kwargs.pop('timeout', 30), **kwargs)
    if not resp.ok:
        fail(f'Mattermost API {method} {path} failed status={resp.status_code}: {resp.text[:500]}', 3)
    return resp.json() if resp.content else {}

def _mattermost_lookup_get(base: str, headers: dict[str, str], path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        response = requests.get(f'{base}{path}', headers=headers, timeout=20)
    except requests.RequestException:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return ({'status': 'request_error'}, {})
    receipt: dict[str, Any] = {'status': int(response.status_code)}
    if not response.ok:
        receipt['error'] = f'http_{response.status_code}'
        return (receipt, {})
    try:
        body = response.json()
    except ValueError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        receipt['error'] = 'invalid_json'
        return (receipt, {})
    return (receipt, body if isinstance(body, dict) else {})

def lookup_mattermost_channel(team_name: str, channel_name: str, base: str, headers: dict[str, str]) -> dict[str, Any]:
    team_path = f'/api/v4/teams/name/{team_name}'
    bot_receipt, bot = _mattermost_lookup_get(base, headers, '/api/v4/users/me')
    team_receipt, team = _mattermost_lookup_get(base, headers, team_path)
    channel_receipt: dict[str, Any] = {'status': 'not_attempted'}
    channel: dict[str, Any] = {}
    if team_receipt.get('status') == 200 and team.get('id'):
        channel_path = f'/api/v4/teams/{team['id']}/channels/name/{channel_name}'
        channel_receipt, channel = _mattermost_lookup_get(base, headers, channel_path)
    statuses = [bot_receipt.get('status'), team_receipt.get('status'), channel_receipt.get('status')]
    result_status = 'ok' if statuses == [200, 200, 200] else 'partial'
    return {'status': result_status, 'capability': 'pd_one_mattermost_channel_lookup', 'credentials_available': True, 'bot_identity': {'status': bot_receipt.get('status'), 'user_id': bot.get('id'), 'username': bot.get('username')}, 'team': {'status': team_receipt.get('status'), 'id': team.get('id'), 'name': team.get('name')}, 'channel_lookup': {'status': channel_receipt.get('status'), 'id': channel.get('id'), 'name': channel.get('name'), 'type': channel.get('type'), 'display_name': channel.get('display_name'), 'purpose': channel.get('purpose')}, 'requested': {'team_name': team_name, 'channel_name': channel_name}, 'safety': {'read_only': True, 'shell_used': False, 'source_system_writes_forbidden': True, 'external_sends_forbidden': True, 'bounded_api_calls': 3, 'token_printed': False}}

def cmd_mattermost_channel_lookup(args: argparse.Namespace) -> None:
    team_name = validate_mattermost_name(args.team_name, 'team_name')
    channel_name = validate_mattermost_name(args.channel_name, 'channel_name')
    module = load_mattermost_review_log_module()
    env = module.gateway_env()
    base = (env.get('MATTERMOST_URL') or '').rstrip('/')
    token = env.get('MATTERMOST_BOT_TOKEN') or ''
    if not base or not token:
        emit({'status': 'unavailable', 'capability': 'pd_one_mattermost_channel_lookup', 'credentials_available': False, 'requested': {'team_name': team_name, 'channel_name': channel_name}, 'safety': {'read_only': True, 'shell_used': False, 'source_system_writes_forbidden': True, 'external_sends_forbidden': True, 'bounded_api_calls': 0, 'token_printed': False}})
        return
    emit(lookup_mattermost_channel(team_name, channel_name, base, {'Authorization': f'Bearer {token}'}))

def cmd_mattermost_channel_post_audit(args: argparse.Namespace) -> None:
    """Read bounded recent channel post metadata, including soft-deleted posts."""
    channel_id = validate_mattermost_id(args.channel_id, 'channel_id')
    lookback_days = max(1, min(int(args.lookback_days), 30))
    max_pages = max(1, min(int(args.max_pages), 10))
    base, headers, me = mattermost_context()
    now = datetime.now(timezone.utc)
    cutoff_ms = int((now - timedelta(days=lookback_days)).timestamp() * 1000)
    statuses, pages_read = ([], 0)
    posts_seen = posts_in_window = deleted_in_window = active_in_window = 0
    order_ids: list[str] = []
    oldest_ms = newest_ms = None
    for page in range(max_pages):
        response = requests.get(f'{base}/api/v4/channels/{channel_id}/posts', headers=headers, params={'page': page, 'per_page': 200, 'include_deleted': 'true'}, timeout=30)
        statuses.append(int(response.status_code))
        if not response.ok:
            fail(f'Mattermost channel post audit failed status={response.status_code}', 3)
        payload = response.json() if response.content else {}
        order = payload.get('order') or [] if isinstance(payload, dict) else []
        post_map = payload.get('posts') or {} if isinstance(payload, dict) else {}
        pages_read += 1
        if not order:
            break
        order_ids.extend((str(post_id) for post_id in order))
        page_times = []
        for post_id in order:
            post = post_map.get(post_id) or {}
            posts_seen += 1
            created_ms = int(post.get('create_at') or 0)
            page_times.append(created_ms)
            if created_ms < cutoff_ms:
                continue
            posts_in_window += 1
            if post.get('delete_at'):
                deleted_in_window += 1
            else:
                active_in_window += 1
        valid_times = [value for value in page_times if value]
        if valid_times:
            oldest_ms = min(valid_times) if oldest_ms is None else min(oldest_ms, min(valid_times))
            newest_ms = max(valid_times) if newest_ms is None else max(newest_ms, max(valid_times))
        if len(order) < 200 or (valid_times and min(valid_times) < cutoff_ms):
            break
    order_counts = collections.Counter(order_ids)
    emit({'status': 'ok', 'capability': 'pd_one_mattermost_channel_post_audit', 'channel_id': channel_id, 'window': {'lookback_days': lookback_days, 'cutoff_epoch_ms': cutoff_ms, 'observed_at_utc': now.isoformat().replace('+00:00', 'Z')}, 'pages_read': pages_read, 'http_statuses': statuses, 'posts_seen': posts_seen, 'posts_in_window': posts_in_window, 'active_in_window': active_in_window, 'deleted_in_window': deleted_in_window, 'order_total': len(order_ids), 'unique_ids': len(order_counts), 'duplicate_ids_count': sum((1 for value in order_counts.values() if value > 1)), 'max_duplicate': max(order_counts.values(), default=0), 'observed_post_time_bounds_ms': {'oldest': oldest_ms, 'newest': newest_ms}, 'bot': {'id': me.get('id'), 'username': me.get('username')}, 'safety': {'read_only': True, 'include_deleted_requested': True, 'credentials_returned': False, 'source_system_write': False, 'external_send': False, 'message_bodies_returned': False}})

def cmd_admin_alert_source_audit(_args: argparse.Namespace) -> None:
    """Inventory fixed PD One Python roots for admin-alert delivery markers."""
    matched: list[tuple[Path, str]] = []
    files_considered = unreadable_files = oversized_files = 0
    for root in ADMIN_ALERT_SOURCE_AUDIT_ROOTS():
        if not root.is_dir():
            continue
        for path in sorted(root.rglob('*.py')):
            if files_considered >= ADMIN_ALERT_SOURCE_AUDIT_MAX_FILES:
                break
            files_considered += 1
            try:
                if not path.is_file():
                    continue
                if path.stat().st_size > ADMIN_ALERT_SOURCE_AUDIT_MAX_FILE_BYTES:
                    oversized_files += 1
                    continue
                content = path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                logging.getLogger('pd_one_ops').exception('pd one command failed')
                unreadable_files += 1
                continue
            if DEFAULT_ADMIN_CHANNEL_ID() in content:
                matched.append((path, content))
        if files_considered >= ADMIN_ALERT_SOURCE_AUDIT_MAX_FILES:
            break
    rows = [{'path': str(path), 'helper': 'ensure_pd_one_admin_mention' in content or 'send_hermes_message' in content, 'literal_mention': '@' + site_text('PDONE_OWNER_MM_USERNAME') in content, 'posts_api': 'api/v4/posts' in content, 'openclaw_send': '"message", "send"' in content or "'message', 'send'" in content} for path, content in matched]
    emit({'status': 'ok', 'capability': 'pd_one_admin_alert_source_audit', 'admin_channel_id': DEFAULT_ADMIN_CHANNEL_ID(), 'roots': [str(root) for root in ADMIN_ALERT_SOURCE_AUDIT_ROOTS()], 'files_considered': files_considered, 'matched_files': len(rows), 'rows': rows, 'limits': {'max_files': ADMIN_ALERT_SOURCE_AUDIT_MAX_FILES, 'max_file_bytes': ADMIN_ALERT_SOURCE_AUDIT_MAX_FILE_BYTES}, 'skipped': {'unreadable_files': unreadable_files, 'oversized_files': oversized_files}, 'safety': {'admin_only': True, 'read_only': True, 'fixed_roots': True, 'source_system_writes_forbidden': True, 'external_sends_forbidden': True, 'file_contents_returned': False, 'credentials_returned': False, 'shell_used': False}})

def inspect_mattermost_deleted_posts(channel_id: str, lookback_days: int, max_posts: int) -> dict[str, Any]:
    """Read one channel's recent posts and summarize deleted-post evidence."""
    channel_id = validate_mattermost_id(channel_id, 'channel_id')
    lookback_days = max(1, min(int(lookback_days), 30))
    max_posts = max(1, min(int(max_posts), 200))
    module = load_mattermost_review_log_module()
    env = module.gateway_env()
    base = (env.get('MATTERMOST_URL') or '').rstrip('/')
    token = env.get('MATTERMOST_BOT_TOKEN') or ''
    capability = 'pd_one_mattermost_deleted_posts_audit'
    requested = {'channel_id': channel_id, 'lookback_days': lookback_days, 'max_posts': max_posts}
    safety = {'read_only': True, 'shell_used': False, 'source_system_writes_forbidden': True, 'external_sends_forbidden': True, 'bounded_api_calls': 1, 'token_printed': False}
    if not base or not token:
        return {'status': 'unavailable', 'capability': capability, 'credentials_available': False, 'requested': requested, 'safety': safety}
    cutoff_ms = int((datetime.now(timezone.utc) - timedelta(days=lookback_days)).timestamp() * 1000)
    try:
        response = requests.get(f'{base}/api/v4/channels/{channel_id}/posts', headers={'Authorization': f'Bearer {token}'}, params={'page': 0, 'per_page': max_posts, 'include_deleted': 'true'}, timeout=30)
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'status': 'source_error', 'capability': capability, 'credentials_available': True, 'requested': requested, 'error_type': type(exc).__name__, 'safety': safety}
    posts_by_id = body.get('posts') if isinstance(body, dict) else {}
    order = body.get('order') if isinstance(body, dict) else []
    posts_by_id = posts_by_id if isinstance(posts_by_id, dict) else {}
    order = order if isinstance(order, list) else list(posts_by_id)
    posts = [posts_by_id[post_id] for post_id in order if post_id in posts_by_id and isinstance(posts_by_id[post_id], dict)]
    deleted = [post for post in posts if int(post.get('delete_at') or 0) >= cutoff_ms]
    evidence = [{'post_id': post.get('id'), 'user_id': post.get('user_id'), 'create_at': post.get('create_at'), 'delete_at': post.get('delete_at')} for post in deleted[:50]]
    return {'status': 'ok', 'capability': capability, 'credentials_available': True, 'requested': requested, 'cutoff_epoch_ms': cutoff_ms, 'posts_received': len(posts), 'deleted_posts': evidence, 'deleted_count': len(deleted), 'deleted_truncated': len(deleted) > len(evidence), 'safety': safety}

def cmd_mattermost_deleted_posts_audit(args: argparse.Namespace) -> None:
    emit(inspect_mattermost_deleted_posts(args.channel_id, args.lookback_days, args.max_posts))
MM_TITLE_TRANSLATIONS = {'生管': 'Production Control', '資材': 'Materials', '採購': 'Purchasing', '品保': 'QA', '品管': 'QC', '業務': 'Sales', '成型': 'Injection Molding', '模具': 'Mold', '研發': 'R&D', '倉庫': 'Warehouse', '出貨': 'Shipping'}
MM_CATEGORY_KEYWORDS = {'production_schedule': ['生管', '排程', '生產', '排產', '開機', '機台', '交期', '產能', '急單', '派工', '插單'], 'materials_inventory': ['資材', '庫存', '缺料', '備料', '入庫', '領料', '材料', '包材', '料號', '倉庫'], 'purchasing_supplier': ['採購', '下單', '供應商', '廠商', '到貨', '交貨', '訂單', '請購', '採買'], 'quality_incoming': ['品保', '品質', '進料', '檢驗', '異常', '不良', '客訴', '退貨', 'IQC', 'QA', 'QC'], 'shipping_timing': ['出貨', '交期', '客戶', '數量', '不足', '短缺', '不能出', '安排']}

def propose_channel_display_name(display_name: str) -> str:
    current = (display_name or '').strip()
    if '/' in current or not current:
        return current
    parts = [p.strip() for p in re.split('[+＋/／,，、\\s]+', current) if p.strip()]
    translated = [MM_TITLE_TRANSLATIONS[p] for p in parts if p in MM_TITLE_TRANSLATIONS]
    if not translated:
        translated = [en for zh, en in MM_TITLE_TRANSLATIONS.items() if zh in current]
    if not translated:
        return current
    return f'{current} / {' + '.join(dict.fromkeys(translated))}'

def fetch_channel_posts(base: str, headers: dict[str, str], channel_id: str, max_posts: int) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    max_posts = max(0, min(int(max_posts), 2000))
    page = 0
    while len(posts) < max_posts:
        data = mm_request('GET', base, headers, f'/api/v4/channels/{channel_id}/posts', params={'page': page, 'per_page': 200}, timeout=35)
        order = data.get('order') or []
        if not order:
            break
        for pid in order:
            post = data.get('posts', {}).get(pid) or {}
            if not post.get('delete_at'):
                posts.append(post)
                if len(posts) >= max_posts:
                    break
        if len(order) < 200:
            break
        page += 1
    posts.sort(key=lambda p: p.get('create_at', 0))
    return posts

def mm_users_by_id(base: str, headers: dict[str, str], ids: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    unique = sorted({i for i in ids if i})
    for idx in range(0, len(unique), 50):
        users = mm_request('POST', base, {**headers, 'Content-Type': 'application/json'}, '/api/v4/users/ids', json=unique[idx:idx + 50], timeout=35)
        if isinstance(users, list):
            out.update({u.get('id'): u for u in users if isinstance(u, dict) and u.get('id')})
    return out

def fetch_channel_members(base: str, headers: dict[str, str], channel_id: str) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    page = 0
    while len(members) < 1000:
        chunk = mm_request('GET', base, headers, f'/api/v4/channels/{channel_id}/members', params={'page': page, 'per_page': 200}, timeout=35)
        if not chunk:
            break
        members.extend([m for m in chunk if isinstance(m, dict)])
        if len(chunk) < 200:
            break
        page += 1
    return members

def summarize_channel(posts: list[dict[str, Any]], users: dict[str, dict[str, Any]]) -> dict[str, Any]:
    text = '\n'.join((str(p.get('message') or '') for p in posts))
    category_counts = {name: sum((text.count(kw) for kw in keywords)) for name, keywords in MM_CATEGORY_KEYWORDS.items()}
    participant_counts = collections.Counter((str(p.get('user_id') or '') for p in posts if p.get('user_id')))
    top_participants = []
    for uid, count in participant_counts.most_common(12):
        u = users.get(uid, {})
        top_participants.append({'user_id': uid, 'username': u.get('username') or uid, 'count': count})
    months = collections.Counter()
    for p in posts:
        ts = int(p.get('create_at') or 0) / 1000
        if ts:
            months[time.strftime('%Y-%m', time.gmtime(ts))] += 1
    return {'posts_scanned': len(posts), 'date_range_utc': [time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(int(posts[0].get('create_at') or 0) / 1000)) if posts else None, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(int(posts[-1].get('create_at') or 0) / 1000)) if posts else None], 'top_participants': top_participants, 'active_months': months.most_common(12), 'keyword_category_counts': category_counts}

def propose_channel_purpose(summary: dict[str, Any]) -> str:
    counts = summary.get('keyword_category_counts') or {}
    active = {k for k, v in counts.items() if int(v or 0) > 0}
    if {'production_schedule', 'materials_inventory', 'purchasing_supplier', 'quality_incoming'} & active:
        return '跨部門協調生產排程、物料/庫存、採購/供應商到貨、品質/進料異常與出貨交期追蹤。 / Cross-functional coordination for production schedules, materials/inventory, purchasing/supplier deliveries, quality/incoming issues, and shipment timing.'
    return '跨部門協調作業事項、狀態追蹤、例外處理與交期/責任確認。 / Cross-functional coordination for operational updates, exception handling, timing, and ownership follow-up.'

def parse_since_ms(value: str | None) -> int:
    if not value:
        return 0
    if not re.match('^\\d{4}-\\d{2}-\\d{2}$', value):
        fail('--since must use YYYY-MM-DD')
    try:
        return int(calendar.timegm(time.strptime(value + ' 00:00:00', '%Y-%m-%d %H:%M:%S')) * 1000)
    except ValueError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        fail('invalid --since date')
    return 0

def mattermost_user_membership(base: str, headers: dict[str, str], user_id: str) -> dict[str, dict[str, Any]]:
    """Return team channels where Mattermost says the requester is an active member."""
    user_id = validate_mattermost_id(user_id, 'user_id')
    teams = mm_request('GET', base, headers, f'/api/v4/users/{user_id}/teams', timeout=35)
    allowed: dict[str, dict[str, Any]] = {}
    for team in teams if isinstance(teams, list) else []:
        team_id = team.get('id')
        if not team_id:
            continue
        try:
            channels = mm_request('GET', base, headers, f'/api/v4/users/{user_id}/teams/{team_id}/channels', timeout=35)
        except SystemExit:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            continue
        for ch in channels if isinstance(channels, list) else []:
            cid = ch.get('id')
            if cid and (not ch.get('delete_at')):
                allowed[cid] = ch
    return allowed

def post_link(base: str, post_id: str) -> str:
    """Return a Mattermost permalink that works without knowing the team slug.

    Mattermost's canonical visible links are usually /<team>/pl/<post_id>.
    The safe wrapper does not always know the requester's current team slug, so
    using /pl/<post_id> can produce links that fail for some users/teams. The
    server-supported redirect endpoint resolves the post id to the right team.
    """
    return f'{base.rstrip('/')}/_redirect/pl/{post_id}' if post_id else ''

def compact_excerpt(message: str, term: str='', limit: int=420) -> str:
    text = re.sub('\\s+', ' ', message or '').strip()
    if not text:
        return ''
    low = text.lower()
    marker = (term or '').lower().strip()
    if marker and marker in low and (len(text) > limit):
        idx = low.index(marker)
        start = max(0, idx - limit // 3)
        end = min(len(text), start + limit)
        return ('…' if start else '') + text[start:end] + ('…' if end < len(text) else '')
    return text[:limit] + ('…' if len(text) > limit else '')

def load_admin_approval_modules():
    """Load legacy approval-ticket modules without exposing broad legacy tools."""
    if str(ADMIN_APPROVAL_TOOLS()) not in sys.path:
        sys.path.append(str(ADMIN_APPROVAL_TOOLS()))
    import admin_approval_tickets
    import admin_approval_notify
    return (admin_approval_tickets, admin_approval_notify)

def load_admin_approval_listener_module():
    """Load the Hermes-native decision parser/validator shared by MCP and hooks."""
    module_name = 'pd_one_admin_approval_listener'
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, ADMIN_APPROVAL_LISTENER())
    if spec is None or spec.loader is None:
        raise RuntimeError(f'unable to load admin approval listener: {ADMIN_APPROVAL_LISTENER()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def load_admin_approval_executor_module():
    """Load the PDAPP oneshot executor without adding scripts/ to sys.path."""
    module_name = 'pd_one_admin_approval_executor'
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, ADMIN_APPROVAL_EXECUTOR())
    if spec is None or spec.loader is None:
        raise RuntimeError(f'unable to load admin approval executor: {ADMIN_APPROVAL_EXECUTOR()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def kick_pdapp_direct_executor(ticket: dict[str, Any] | None) -> dict[str, Any]:
    """Kick the oneshot executor after a ticket is queued. Never raises."""
    try:
        executor_mod = load_admin_approval_executor_module()
        config = executor_mod.load_config(ADMIN_APPROVAL_EXECUTOR_CONFIG())
        return executor_mod.kick_direct_executor(config=config, ticket=ticket, dry_run=False)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'status': 'start_failed', 'error': str(exc)[:400]}

def load_current_mattermost_policy(user_id: str) -> dict[str, Any]:
    """Resolve one exact sender from current canonical policy files."""
    from tools.pd_one_ops.pd_one_safe_ops_part2 import load_json
    module_name = 'pd_one_mattermost_policy_lookup'
    module = sys.modules.get(module_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(module_name, MATTERMOST_POLICY_LOOKUP())
        if spec is None or spec.loader is None:
            raise RuntimeError(f'unable to load Mattermost policy lookup: {MATTERMOST_POLICY_LOOKUP()}')
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return module.resolve_user(user_id, load_json(POLICY_USERS()), load_json(POLICY_ROLES()), None)

def split_csv_lines(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split('[,\\n]', value)
    return [p.strip() for p in parts if p.strip()]

def verified_admin_request_source(requester_user_id: str, origin_channel_id: str, origin_root_id: str, origin_post_id: str) -> dict[str, Any]:
    """Verify an Owner-originated request from immutable Mattermost source data.

    The caller-supplied requester id is never enough to bypass approval. Auto-approval
    is allowed only when the exact source post is live, belongs to Owner's immutable
    user id, and matches the supplied channel/thread coordinates.
    """
    if requester_user_id != DEFAULT_ANDY_USER_ID():
        return {'verified': False, 'eligible': False, 'reason': 'requester_is_not_admin'}
    base, headers, _me = mattermost_context()
    receipt, post = _mattermost_lookup_get(base, headers, f'/api/v4/posts/{origin_post_id}')
    if receipt.get('status') != 200:
        fail(f'Owner requester identity could not be verified from the exact Mattermost source post {origin_post_id}; no ticket was created')
    expected_root_id = str(post.get('root_id') or post.get('id') or '')
    checks = {'post_id': str(post.get('id') or '') == origin_post_id, 'requester_user_id': str(post.get('user_id') or '') == requester_user_id == DEFAULT_ANDY_USER_ID(), 'channel_id': str(post.get('channel_id') or '') == origin_channel_id, 'root_id': expected_root_id == origin_root_id, 'not_deleted': not int(post.get('delete_at') or 0)}
    if not all(checks.values()):
        failed_checks = sorted((name for name, ok in checks.items() if not ok))
        fail(f'Owner requester identity/source binding verification failed for post {origin_post_id}: {failed_checks}; no ticket was created')
    return {'verified': True, 'eligible': True, 'reason': 'exact_mattermost_admin_source_verified', 'post_id': origin_post_id, 'channel_id': origin_channel_id, 'root_id': origin_root_id, 'user_id': requester_user_id, 'message': str(post.get('message') or '')}

def andy_origin_skips_admin_ticket(*, dry_run: bool, admin_source: dict[str, Any], requester_user_id: str, allow_deployment: bool=False) -> dict[str, Any]:
    """Skip PDAPP cards when Owner's exact origin post already authorizes the work.

    Owner 2026-10-01: if the exact sender is Owner/admin and the live source post
    matches, that post is the authorization. Do not create a self-approval ticket
    or queue the oneshot executor. The in-session agent must execute with
    dry-run/readback. Employee rooms without Owner still ticket.
    """
    return {'status': 'dry_run_already_authorized_no_ticket' if dry_run else 'already_authorized_no_ticket', 'capability': 'pd_one_admin_approval_request', 'ticket_id': None, 'requester_user_id': requester_user_id, 'requester_verification': admin_source, 'deployment_authorized': bool(allow_deployment), 'employee_message': "Verified Owner's exact Mattermost source post. Do not create a PDAPP ticket. Execute the bound action in-session with dry-run/readback.", 'safety': {'exact_admin_source_verified': True, 'no_ticket_created': True, 'no_privileged_action_executed': True, 'execute_in_session': True, 'second_approval_bypassed': True}}

def source_explicitly_authorizes_deployment(message: str) -> bool:
    """Require deployment language in the exact verified admin source post."""
    return bool(re.search('\\b(?:deploy(?:ment|ed|ing)?|go live|live on|publish(?:ed|ing)?)\\b|上線|部署|發布', str(message or ''), flags=re.IGNORECASE))
DRIVE_WRITER_NO_TICKET_TYPES = frozenset({'generic_handoff_v1', 'google_sheet_channel_sync_v1'})
DRIVE_WRITER_NO_TICKET_ACTION_RE = re.compile('(?i)(?<!non-)(?<!non )(?<!not a )(?<!a )\\b(delete|purge|destroy|share|gateway|credential|deploy|restart)\\b|(?:grant|change|expand)\\s+(?:drive\\s+)?permissions?|(?<!非)刪除|(?:變更|開放|授予)權限|分享|憑證|重啟|部署')
DRIVE_WRITER_NO_TICKET_CAP_RE = re.compile('(?i)destructive|permission|gateway|credential|external_send|deploy|bounded_sheet_cell_write')
GOOGLE_FILE_ID_RE = re.compile('(?:(?:docs|drive)\\.google\\.com/(?:spreadsheets|document|file)/d/|Google Sheet )([A-Za-z0-9_-]{25,})')
GOOGLE_BARE_FILE_ID_RE = re.compile('(?<![A-Za-z0-9_-])(1[A-Za-z0-9_-]{32,43})(?![A-Za-z0-9_-])')

def harvest_google_file_ids(*blobs: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for blob in blobs:
        text = blob or ''
        for match in GOOGLE_FILE_ID_RE.finditer(text):
            file_id = match.group(1)
            if file_id in seen:
                continue
            seen.add(file_id)
            found.append(file_id)
        for match in GOOGLE_BARE_FILE_ID_RE.finditer(text):
            file_id = match.group(1)
            if file_id in seen:
                continue
            seen.add(file_id)
            found.append(file_id)
    return found

def _authorize_drive_writer(file_id: str, requester_user_id: str) -> dict[str, Any]:
    tools_dir = str(ROOT() / 'tools')
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    from drive_acl_authorize import authorize, public_view
    result = authorize(file_id, mattermost_user_id=requester_user_id, mattermost_username='', account=DEFAULT_ACCOUNT())
    return public_view(result, redact=True)

def employee_live_drive_writer_skips_admin_ticket(*, requester_user_id: str, request_type: str, requested_action: str, allowed_document_ids: list[str], required_capabilities: list[str], allow_deployment: bool, dry_run: bool, extra_id_text: list[str] | None=None, authorize_fn: Any | None=None) -> dict[str, Any] | None:
    """Skip PDAPP cards when live Drive already grants writer on the exact files.

    Owner 2026-09-08: a requester who already has writer/editor (direct or via a
    writer group) on the named Google Sheet/Doc does not need an Owner ticket for
    non-destructive in-place edits, including column insert/layout moves.
    Red-line actions still ticket. File ids may come from allowed_document_ids
    or Google Sheet/Doc URLs and `Google Sheet <id>` write-target strings.
    """
    if requester_user_id == DEFAULT_ANDY_USER_ID():
        return None
    if request_type not in DRIVE_WRITER_NO_TICKET_TYPES:
        return None
    if allow_deployment:
        return None
    document_ids = list(allowed_document_ids or [])
    for file_id in harvest_google_file_ids(requested_action, *(extra_id_text or [])):
        if file_id not in document_ids:
            document_ids.append(file_id)
    if not document_ids:
        return None
    if DRIVE_WRITER_NO_TICKET_ACTION_RE.search(requested_action or ''):
        return None
    if any((DRIVE_WRITER_NO_TICKET_CAP_RE.search(cap or '') for cap in required_capabilities or [])):
        return None
    lookup = authorize_fn or _authorize_drive_writer
    evidence: list[dict[str, Any]] = []
    for file_id in document_ids:
        try:
            view = lookup(file_id, requester_user_id)
        except Exception:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            return None
        if not (isinstance(view, dict) and view.get('canWrite') is True):
            return None
        evidence.append({'file_id': file_id, 'via': view.get('via'), 'role': view.get('role')})
    return {'status': 'dry_run_already_authorized_no_ticket' if dry_run else 'already_authorized_no_ticket', 'capability': 'pd_one_admin_approval_request', 'ticket_id': None, 'requester_user_id': requester_user_id, 'document_write_evidence': evidence, 'employee_message': 'Live Drive writer/editor access already authorizes this non-destructive in-place Google file change. Do not create a PDAPP ticket; execute the bounded edit and read it back.', 'safety': {'no_ticket_created': True, 'no_privileged_action_executed': True, 'live_drive_writer_required': True, 'red_lines_still_ticketed': True}}

def cmd_admin_approval_request(args: argparse.Namespace) -> None:
    """Create a bounded approval and route it to the source thread or Admin.

    This is intentionally narrower than giving employee/channel agents admin tools:
    it packages the request and preserves source metadata. Normal channels get an
    inline @Owner approval card; inaccessible DMs fall back to the Admin channel.
    """
    requester_user_id = validate_mattermost_id(args.requester_user_id, 'requester_user_id')
    origin_channel_id = validate_mattermost_id(args.origin_channel_id, 'origin_channel_id')
    origin_root_id = validate_mattermost_id(args.origin_root_id, 'origin_root_id') if args.origin_root_id else ''
    origin_post_id = validate_mattermost_id(args.origin_post_id, 'origin_post_id') if args.origin_post_id else origin_root_id
    if not origin_root_id and (not origin_post_id):
        fail('a real Mattermost --origin-post-id or --origin-root-id is required; synthetic confirmation is forbidden')
    admin_channel_id = validate_mattermost_id(args.admin_channel_id, 'admin_channel_id')
    requested_action = (args.requested_action or '').strip()
    if not requested_action:
        fail('--requested-action is required')
    request_type = args.request_type
    requested_scope = (args.requested_scope or 'Current Mattermost thread/channel and requester-provided context only').strip()
    risk_summary = (args.risk_summary or 'Approval-gated request; admin must review before any privileged action.').strip()
    acceptance = split_csv_lines(args.acceptance_criteria) or ['Admin reviews the request and approves/rejects before any privileged action.', 'Employee-visible completion is posted back to the original Mattermost thread when done.']
    allowed_document_ids = split_csv_lines(args.allowed_document_ids)
    allowed_write_targets = split_csv_lines(args.allowed_write_targets)
    skip_ticket = employee_live_drive_writer_skips_admin_ticket(requester_user_id=requester_user_id, request_type=request_type, requested_action=requested_action, allowed_document_ids=allowed_document_ids, required_capabilities=split_csv_lines(args.required_capabilities), allow_deployment=bool(getattr(args, 'allow_deployment', False)), dry_run=bool(getattr(args, 'dry_run', False)), extra_id_text=[requested_scope, '\n'.join(allowed_write_targets), str(args.request_original or ''), str(args.request_english or '')])
    if skip_ticket:
        emit(skip_ticket)
        return
    if request_type == 'hr_policy_lookup_v1':
        if not allowed_document_ids:
            fail('--allowed-document-ids is required for hr_policy_lookup_v1')
        unknown_document_ids = sorted(set(allowed_document_ids) - HR_POLICY_DOCUMENT_IDS())
        if unknown_document_ids:
            fail(f'hr_policy_lookup_v1 only permits approved document ids; blocked: {unknown_document_ids}')
        if allowed_write_targets:
            fail('hr_policy_lookup_v1 is read-only; --allowed-write-targets must be empty')
        default_capabilities = ['hr_policy_document_read']
    elif request_type == 'google_sheet_channel_sync_v1':
        default_capabilities = ['mattermost_channel_read', 'google_sheet_create', 'google_sheet_write']
    else:
        default_capabilities = ['admin_review', 'approval_gated_handoff']
    required_capabilities = split_csv_lines(args.required_capabilities) or default_capabilities
    idempotency_key = args.idempotency_key or f'admin-approval:{requester_user_id}:{origin_channel_id}:{origin_root_id or origin_post_id}:{request_type}:{requested_action}'
    admin_source = verified_admin_request_source(requester_user_id, origin_channel_id, origin_root_id or origin_post_id, origin_post_id or origin_root_id)
    allow_deployment = bool(getattr(args, 'allow_deployment', False))
    if allow_deployment and admin_source.get('eligible') and (not source_explicitly_authorizes_deployment(admin_source.get('message', ''))):
        fail('The exact verified Owner source post does not explicitly authorize deployment; no ticket was created')
    if admin_source.get('eligible'):
        emit(andy_origin_skips_admin_ticket(dry_run=bool(getattr(args, 'dry_run', False)), admin_source=admin_source, requester_user_id=requester_user_id, allow_deployment=allow_deployment))
        return
    context = {'approval_request_type': request_type, 'requester_user_id': requester_user_id, 'requester_label': args.requester_label or requester_user_id, 'origin_provider': 'mattermost', 'origin_channel_id': origin_channel_id, 'origin_channel_name': args.origin_channel_name or origin_channel_id, 'origin_root_id': origin_root_id or origin_post_id, 'origin_post_id': origin_post_id or origin_root_id, 'admin_channel_id': admin_channel_id, 'request_original': args.request_original or requested_action, 'request_english': args.request_english or requested_action, 'requested_action': requested_action, 'admin_instruction': '', 'andy_user_id': '', 'approval_source': '', 'approval_verified_by': '', 'risk_summary': risk_summary, 'required_capabilities': required_capabilities, 'capability_scope': {'allowed_source_channel_ids': [origin_channel_id], 'allowed_document_ids': allowed_document_ids, 'allowed_write_targets': allowed_write_targets, 'allowed_external_recipients': [], 'destructive_allowed': False, 'external_send_allowed': False, 'gateway_restart_approved': False, 'credential_changes_allowed': False, 'permission_changes_allowed': False, 'deployment_allowed': allow_deployment}, 'implementation_plan': {'summary': requested_action, 'data_boundaries': requested_scope, 'acceptance_criteria': acceptance, 'unresolved_assumptions': split_csv_lines(args.unresolved_assumptions), 'readiness_status': 'pending_validation'}}
    readiness_fields = {'business_goal': requested_action, 'data_boundaries': requested_scope, 'acceptance_criteria': acceptance, 'summary': f'Admin approval requested: {requested_action}. Scope: {requested_scope}', 'unresolved_assumptions': split_csv_lines(args.unresolved_assumptions)}
    if request_type == 'google_sheet_channel_sync_v1':
        readiness_fields.update({'sheet_owner_audience': 'PD One Admin approval queue', 'columns_or_extraction_rules': 'Admin-approved implementation packet', 'schedule_requested': False})
    elif request_type == 'hr_policy_lookup_v1':
        readiness_fields['document_ids'] = allowed_document_ids
    tickets_mod, notify_mod = load_admin_approval_modules()
    ledger = tickets_mod.ApprovalLedger(str(APPROVAL_LEDGER()))
    if args.dry_run:
        draft_preview = {**context, 'ticket_id': tickets_mod.ticket_id_for(idempotency_key)}
        if request_type == 'google_sheet_channel_sync_v1':
            readiness_preview = tickets_mod.readiness_for_google_sheet_channel_sync(readiness_fields, draft_preview)
        elif request_type == 'hr_policy_lookup_v1':
            readiness_preview = tickets_mod.readiness_for_hr_policy_lookup(readiness_fields, draft_preview)
        else:
            readiness_preview = tickets_mod.readiness_for_generic_handoff(readiness_fields, draft_preview)
        draft_preview['implementation_plan'] = readiness_preview['implementation_plan']
        emit({'status': 'dry_run', 'capability': 'pd_one_admin_approval_request', 'approval_request_type': request_type, 'readiness_validator': draft_preview['implementation_plan']['readiness_validator'], 'required_capabilities': required_capabilities, 'capability_scope': context['capability_scope'], 'routing_policy': 'origin channel thread inline; Admin channel only for direct/group DMs', 'dm_fallback_admin_channel_id': admin_channel_id, 'ticket_id': draft_preview['ticket_id'], 'admin_card_preview': tickets_mod.render_admin_card(draft_preview), 'safety': {'no_privileged_action_executed': True, 'approval_handoff_only': True}})
        return
    ticket = ledger.create_draft(context, idempotency_key=idempotency_key)
    ticket = ledger.validate_readiness(ticket['ticket_id'], readiness_fields, validator=request_type)
    if ticket.get('status') != 'needs_employee_confirmation':
        emit({'status': 'needs_employee_info', 'ticket_id': ticket.get('ticket_id'), 'missing_required_fields': ticket.get('implementation_plan', {}).get('missing_required_fields', []), 'employee_message': 'I can escalate this to admin, but I need a little more detail first: requested action, scope, and acceptance criteria.'})
        return
    ticket = ledger.confirm_draft(ticket['ticket_id'], employee_confirmation_post_id=origin_post_id or origin_root_id)
    notify_result = notify_mod.notify_ticket(ledger, ticket['ticket_id'], admin_channel_id=admin_channel_id, dry_run=False)
    status = 'sent' if notify_result.get('ok') else 'notification_failed'
    route = notify_result.get('route')
    employee_message = (f'I asked @Owner for inline approval in this thread as {ticket['ticket_id']}. The approved action is cryptographically bound to this request.' if route == 'origin_inline' else f'This request came from a DM Owner cannot access, so I sent approval ticket {ticket['ticket_id']} to the PD One Admin channel.') if notify_result.get('ok') else f'I created approval ticket {ticket['ticket_id']}, but the admin notification failed and needs retry by admin. I will not take privileged action until it is approved.'
    emit({'status': status, 'capability': 'pd_one_admin_approval_request', 'ticket_id': ticket['ticket_id'], 'approval_route': route, 'approval_channel_id': notify_result.get('channel_id'), 'admin_channel_id': admin_channel_id, 'admin_post_id': notify_result.get('post_id'), 'employee_message': employee_message, 'notify_result_ok': bool(notify_result.get('ok')), 'safety': {'approval_handoff_only': True, 'no_privileged_action_executed': True, 'origin_preserved': bool(origin_channel_id and (origin_root_id or origin_post_id)), 'admin_decision_required': True}})

def cmd_admin_approval_list_open(args: argparse.Namespace) -> None:
    """List open admin approval tickets without shelling out to ad hoc Python.

    This is the read-only companion to the approval request flow. It uses the
    deterministic approval ledger directly and returns only bounded ticket
    metadata so callers can inspect pending/approved/in-progress items without
    parsing subprocess output.
    """
    tickets_mod, _ = load_admin_approval_modules()
    ledger = tickets_mod.ApprovalLedger(str(APPROVAL_LEDGER()))
    tickets = ledger.list_open()
    tickets.sort(key=lambda t: (str(t.get('created_at_utc') or ''), str(t.get('ticket_id') or '')))
    max_results = max(1, min(int(getattr(args, 'max_results', 100) or 100), 500))
    redacted = []
    for ticket in tickets[:max_results]:
        redacted.append({'ticket_id': ticket.get('ticket_id'), 'status': ticket.get('status'), 'created_at_utc': ticket.get('created_at_utc'), 'updated_at_utc': ticket.get('updated_at_utc'), 'requester_user_id': ticket.get('requester_user_id'), 'requester_label': ticket.get('requester_label'), 'origin_channel_id': ticket.get('origin_channel_id'), 'origin_channel_name': ticket.get('origin_channel_name'), 'origin_root_id': ticket.get('origin_root_id'), 'origin_post_id': ticket.get('origin_post_id'), 'admin_approval_post_id': ticket.get('admin_approval_post_id'), 'requested_action': ticket.get('requested_action'), 'risk_summary': ticket.get('risk_summary')})
    emit({'status': 'ok', 'capability': 'pd_one_admin_approval_list_open', 'count': len(redacted), 'total_open': len(tickets), 'max_results': max_results, 'tickets': redacted, 'safety': {'read_only': True, 'no_privileged_action_executed': True, 'no_shell_glue': True}})

def cmd_admin_approval_decide(args: argparse.Namespace) -> None:
    """Validate a real Mattermost decision post, then record/enqueue the ticket.

    The Mattermost post is the authorization source. Caller-supplied identity,
    decision text, instructions, channel, and thread are never trusted.
    """
    ticket_id = (args.ticket_id or '').strip().upper()
    if not re.match('^PDAPP-\\d{8}-[A-F0-9]{8}$', ticket_id):
        fail('--ticket-id must look like PDAPP-YYYYMMDD-XXXXXXXX')
    decision_post_id = validate_mattermost_id(args.decision_post_id, 'decision_post_id')
    dry_run = bool(getattr(args, 'dry_run', True))
    tickets_mod, _ = load_admin_approval_modules()
    listener_mod = load_admin_approval_listener_module()
    ledger = tickets_mod.ApprovalLedger(str(APPROVAL_LEDGER()))
    try:
        current = ledger.get(ticket_id)
    except KeyError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        emit({'status': 'not_found', 'capability': 'pd_one_admin_approval_decide', 'ticket_id': ticket_id, 'decision_post_id': decision_post_id, 'safety': {'dry_run_default': True, 'mattermost_post_refetch_required': True, 'exact_admin_sender_required': True, 'bound_origin_or_current_policy_surface_required': True, 'no_privileged_work_executed': True}})
        return
    try:
        base, headers, _me = mattermost_context()
        response = requests.get(f'{base.rstrip('/')}/api/v4/posts/{decision_post_id}', headers=headers, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f'Mattermost decision post lookup returned HTTP {response.status_code}')
        post = response.json()
        if not isinstance(post, dict) or not post.get('id'):
            raise RuntimeError('Mattermost decision post lookup returned an invalid payload')
        channel_response = requests.get(f'{base.rstrip('/')}/api/v4/channels/{post.get('channel_id') or ''}', headers=headers, timeout=30)
        if channel_response.status_code != 200:
            raise RuntimeError(f'Mattermost decision channel lookup returned HTTP {channel_response.status_code}')
        channel = channel_response.json()
        if not isinstance(channel, dict) or not channel.get('id') or (not channel.get('type')):
            raise RuntimeError('Mattermost decision channel lookup returned an invalid payload')
        admin_policy = load_current_mattermost_policy(DEFAULT_ANDY_USER_ID())
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        emit({'status': 'blocked', 'capability': 'pd_one_admin_approval_decide', 'ticket_id': ticket_id, 'decision_post_id': decision_post_id, 'reason': 'decision_post_read_failed', 'error': tickets_mod.sanitize_text(str(exc), 500), 'safety': {'fail_closed': True, 'ledger_mutated': False, 'no_privileged_work_executed': True}})
        return
    event = {'provider': 'mattermost', 'channel_id': post.get('channel_id') or '', 'user_id': post.get('user_id') or '', 'post_id': post.get('id') or decision_post_id, 'root_id': post.get('root_id') or post.get('id') or '', 'message': post.get('message') or '', 'channel_type': channel.get('type') or '', 'edited': bool(post.get('edit_at')), 'deleted': bool(post.get('delete_at'))}
    validated = listener_mod.validate_event(ledger, event, andy_user_id=DEFAULT_ANDY_USER_ID(), admin_channel_id=DEFAULT_ADMIN_CHANNEL_ID(), admin_policy=admin_policy)
    if validated.get('ticket_id') and validated.get('ticket_id') != ticket_id:
        validated = {'ok': False, 'status': 'ignored', 'reason': 'decision_post_ticket_mismatch', 'ticket_id': ticket_id}
    common = {'capability': 'pd_one_admin_approval_decide', 'ticket_id': ticket_id, 'ticket_status': current.get('status'), 'decision_post_id': decision_post_id, 'verified_actor_user_id': post.get('user_id') or '', 'verified_channel_id': post.get('channel_id') or '', 'verified_root_id': post.get('root_id') or post.get('id') or '', 'verified_binding': validated.get('binding'), 'derived_decision': validated.get('decision'), 'idempotent_replay': bool(validated.get('idempotent_replay')), 'safety': {'dry_run_default': True, 'mattermost_post_refetch_required': True, 'caller_identity_ignored': True, 'caller_decision_ignored': True, 'exact_admin_sender_required': True, 'bound_origin_or_current_policy_surface_required': True, 'decision_and_enqueue_only': True, 'approved_work_not_executed': True, 'arbitrary_shell_forbidden': True}}
    if dry_run:
        emit({'status': 'dry_run' if validated.get('ok') else 'blocked', **common, 'would_apply': bool(validated.get('ok') and (not validated.get('idempotent_replay'))), 'blocked_reason': None if validated.get('ok') else validated.get('reason'), 'ticket_status_after': 'queued' if validated.get('decision') == 'approved' and validated.get('ok') else 'rejected' if validated.get('decision') == 'rejected' and validated.get('ok') else current.get('status')})
        return
    if args.confirm_live_write != ADMIN_APPROVAL_DECISION_CONFIRMATION:
        fail(f'live admin approval decisions require --confirm-live-write {ADMIN_APPROVAL_DECISION_CONFIRMATION!r}')
    if not validated.get('ok'):
        emit({'status': 'blocked', **common, 'reason': validated.get('reason') or 'decision_post_validation_failed'})
        return
    result = listener_mod.handle_event(ledger, event, andy_user_id=DEFAULT_ANDY_USER_ID(), admin_channel_id=DEFAULT_ADMIN_CHANNEL_ID(), admin_policy=admin_policy)
    if not result.get('ok'):
        emit({'status': 'blocked', **common, 'reason': result.get('reason') or 'decision_transition_failed'})
        return
    ticket_after = result.get('ticket') or ledger.get(ticket_id)
    executor_kick = {'status': 'skipped', 'reason': 'not_queued'}
    if str(ticket_after.get('status') or '') == 'queued':
        executor_kick = kick_pdapp_direct_executor(ticket_after)
    emit({'status': 'ok', **common, 'derived_decision': result.get('status'), 'ticket_status_after': ticket_after.get('status'), 'idempotent_replay': bool(result.get('idempotent_replay')), 'andy_decision': ticket_after.get('andy_decision') or {}, 'continuation_policy': ticket_after.get('continuation_policy') or {}, 'approval_grant': ticket_after.get('approval_grant') or {}, 'executor_kick': executor_kick, 'safety': {**common['safety'], 'live_write_confirmation_required': ADMIN_APPROVAL_DECISION_CONFIRMATION, 'readback_verification_required': True, 'oneshot_executor_kicked': executor_kick.get('status') in {'started', 'would_start', 'busy', 'skipped'}, 'approved_work_not_executed_in_decide': True}})

def cmd_approval_ticket_status(args: argparse.Namespace) -> None:
    """Read one admin approval ticket without shell pipelines or JSON grep.

    This promotes the legacy `admin_approval_tickets.py get` readback into the
    safe-ops dispatcher so MCP callers can request structured fields directly.
    It is read-only and intentionally does not enqueue, approve, execute, or
    mutate ticket state.
    """
    ticket_id = (args.ticket_id or '').strip()
    if not re.match('^PDAPP-\\d{8}-[A-F0-9]{8}$', ticket_id):
        fail('--ticket-id must look like PDAPP-YYYYMMDD-XXXXXXXX')
    tickets_mod, _ = load_admin_approval_modules()
    ledger = tickets_mod.ApprovalLedger(str(APPROVAL_LEDGER()))
    try:
        ticket = ledger.get(ticket_id)
    except KeyError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        emit({'status': 'not_found', 'capability': 'pd_one_approval_ticket_status', 'ticket_id': ticket_id, 'safety': {'read_only': True, 'no_privileged_action_executed': True, 'no_shell_glue': True}})
        return
    safe_summary = {'ticket_id': ticket.get('ticket_id'), 'ticket_status': ticket.get('status'), 'created_at_utc': ticket.get('created_at_utc'), 'updated_at_utc': ticket.get('updated_at_utc'), 'requester_user_id': ticket.get('requester_user_id'), 'requester_label': ticket.get('requester_label'), 'origin_channel_id': ticket.get('origin_channel_id'), 'origin_channel_name': ticket.get('origin_channel_name'), 'origin_root_id': ticket.get('origin_root_id'), 'origin_post_id': ticket.get('origin_post_id'), 'admin_approval_post_id': ticket.get('admin_approval_post_id'), 'admin_root_id': ticket.get('admin_root_id'), 'requested_action': ticket.get('requested_action'), 'risk_summary': ticket.get('risk_summary'), 'implementation_readiness_status': (ticket.get('implementation_plan') or {}).get('readiness_status'), 'pending_expires_at_utc': ticket.get('pending_expires_at_utc'), 'queued_at_utc': ticket.get('queued_at_utc'), 'started_at_utc': ticket.get('started_at_utc'), 'completed_at_utc': ticket.get('completed_at_utc'), 'failure_reason': ticket.get('failure_reason'), 'employee_visible_summary': ticket.get('employee_visible_summary')}
    if args.include_details:
        safe_summary['implementation_plan'] = ticket.get('implementation_plan') or {}
        safe_summary['capability_scope'] = ticket.get('capability_scope') or {}
        safe_summary['bound_resources'] = ticket.get('bound_resources') or []
        safe_summary['approval_grant'] = ticket.get('approval_grant') or {}
    fields = [f.strip() for f in args.field or [] if f.strip()]
    if fields:
        selected = {field: safe_summary.get(field) for field in fields}
        missing = [field for field in fields if field not in safe_summary]
    else:
        selected = safe_summary
        missing = []
    emit({'status': 'ok', 'capability': 'pd_one_approval_ticket_status', 'ticket_id': ticket_id, 'fields': selected, 'missing_fields': missing, 'safety': {'read_only': True, 'bounded_ticket_lookup': True, 'no_privileged_action_executed': True, 'no_shell_glue': True, 'full_ticket_dump_default': False}})

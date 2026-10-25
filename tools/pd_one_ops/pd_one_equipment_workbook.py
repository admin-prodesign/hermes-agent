#!/usr/bin/env python3
"""Typed, bounded builder for the internal equipment workbook staging artifact.

This module replaces the recurring inline openpyxl consolidation script seen in
PD One execute_code approval requests. It is deliberately fixed to the three
requester-provided source workbooks, produces exactly fourteen normalized tabs,
and stages output only below the PD One temp root. It never writes source files,
Google Sheets, Drive permissions, or external messages.
"""
from __future__ import annotations
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
import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
Workbook = _PdLazyAttr('openpyxl', 'Workbook')
load_workbook = _PdLazyAttr('openpyxl', 'load_workbook')
Alignment = _PdLazyAttr('openpyxl.styles', 'Alignment')
Font = _PdLazyAttr('openpyxl.styles', 'Font')
PatternFill = _PdLazyAttr('openpyxl.styles', 'PatternFill')
get_column_letter = _PdLazyAttr('openpyxl.utils', 'get_column_letter')

def ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))

def SOURCE_ROOT():
    return ROOT() / 'cache/documents'

def STAGING_ROOT():
    return ROOT() / 'tmp/equipment-workbook'
DEFAULT_OUTPUT_NAME = '良器-設備管理-廠內設備規格查詢_In-house_Equipment_Specifications.xlsx'

def SOURCE_PATHS():
    return {'injection': SOURCE_ROOT() / 'doc_fafbca05b172_良器現有射出機履歷資料20260319.xlsx', 'masterbatch': SOURCE_ROOT() / 'doc_d33fde0d9970_色母機設備盤點量測參數.xlsx', 'overview': SOURCE_ROOT() / 'doc_01691e27f673_機台設備總覽表-20260319修改版.xlsx'}
EXPECTED_SHEET_NAMES = ['射出機查詢', '設備總覽', '射出機規格', '色母機履歷', '色母機量測', '機械手配置', '天車清單', '其他設備', '螺桿套桶間隙', '三家比較', '來源索引', '資料品質問題', '欄位字典', '使用說明']
EXPECTED_DATA_COUNTS = {'射出機查詢': 37, '設備總覽': 193, '射出機規格': 43, '色母機履歷': 35, '色母機量測': 162}
MAX_SCAN_ROWS = 5000
MAX_CELL_CHARS = 2000

def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    text = str(value).strip()
    return text[:MAX_CELL_CHARS] if len(text) > MAX_CELL_CHARS else text

def _text(value: Any) -> str:
    value = _safe_scalar(value)
    return '' if value is None else str(value).strip()

def _nonempty(row: Iterable[Any]) -> bool:
    return any((value not in (None, '') for value in row))

def _read_nonempty_rows(workbook: Any, sheet_name: str) -> list[list[Any]]:
    if sheet_name not in workbook.sheetnames:
        raise ValueError(f'required source sheet is missing: {sheet_name}')
    worksheet = workbook[sheet_name]
    max_row = min(int(worksheet.max_row or 0), MAX_SCAN_ROWS)
    max_col = min(int(worksheet.max_column or 0), 100)
    rows: list[list[Any]] = []
    for row in worksheet.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col, values_only=True):
        values = [_safe_scalar(value) for value in row]
        if _nonempty(values):
            rows.append(values)
    return rows

def _trim_row(row: Iterable[Any], width: int | None=None) -> list[Any]:
    values = list(row)
    if width is None:
        while values and values[-1] in (None, ''):
            values.pop()
    else:
        values = values[:width] + [None] * max(0, width - len(values))
    return values

def _unique_headers(values: Iterable[Any]) -> list[str]:
    seen: dict[str, int] = {}
    headers: list[str] = []
    for index, value in enumerate(values, start=1):
        base = _text(value) or f'欄位{index}'
        count = seen.get(base, 0) + 1
        seen[base] = count
        headers.append(base if count == 1 else f'{base}_{count}')
    return headers

def _with_provenance(headers: Iterable[Any], rows: Iterable[Iterable[Any]], source_name: str, source_sheet: str) -> tuple[list[str], list[list[Any]]]:
    header_values = list(headers)
    width = max(len(header_values), max((len(list(row)) for row in rows), default=0))
    row_values = [_trim_row(row, width) for row in rows]
    return (['資料來源檔案', '來源工作表', *_unique_headers(header_values)], [[source_name, source_sheet, *row] for row in row_values])

def _source_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def _load_sources() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    workbooks: dict[str, Any] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for key, path in SOURCE_PATHS().items():
        if not path.is_file():
            raise FileNotFoundError(f'required source workbook not found: {path}')
        workbooks[key] = load_workbook(path, read_only=True, data_only=False, keep_links=False)
        metadata[key] = {'path': str(path), 'name': path.name, 'size_bytes': path.stat().st_size, 'sha256': _source_hash(path), 'sheets': list(workbooks[key].sheetnames)}
    return (workbooks, metadata)

def _injection_tables(workbook: Any) -> dict[str, tuple[list[str], list[list[Any]]]]:
    rows = _read_nonempty_rows(workbook, '總表')
    if len(rows) < 5:
        raise ValueError('injection workbook does not contain index, header, unit, and data rows')
    headers = rows[1]
    units = rows[2]
    data = [_trim_row(row, max(len(headers), len(units))) for row in rows[3:]]
    width = max(len(headers), len(units), max((len(row) for row in data), default=0))
    headers = _trim_row(headers, width)
    units = _trim_row(units, width)
    spec_headers = [_text(header) if not _text(unit) else f'{_text(header)} ({_text(unit)})' for header, unit in zip(headers, units)]
    source_name = SOURCE_PATHS()['injection'].name
    active = [row for row in data if _text(row[0]) != '已報廢']
    return {'射出機查詢': _with_provenance(headers, active, source_name, '總表'), '射出機規格': _with_provenance(spec_headers, data, source_name, '總表')}

def _masterbatch_tables(workbook: Any) -> dict[str, tuple[list[str], list[list[Any]]]]:
    history_rows = _read_nonempty_rows(workbook, '履歷表')
    if len(history_rows) < 4:
        raise ValueError('masterbatch history sheet does not contain expected rows')
    history_headers = history_rows[0]
    history_data = history_rows[2:]
    source_name = SOURCE_PATHS()['masterbatch'].name
    measurement_rows: list[list[Any]] = []
    measurement_header: list[Any] | None = None
    measurement_source_sheet = 'T-series sheets'
    for sheet_name in workbook.sheetnames:
        if not re.fullmatch('T\\d+', sheet_name):
            continue
        rows = _read_nonempty_rows(workbook, sheet_name)
        header_index = next((index for index, row in enumerate(rows) if any((_text(value) == '顏色' for value in row))), None)
        if header_index is None:
            continue
        if measurement_header is None:
            measurement_header = rows[header_index]
        for row in rows[header_index + 1:header_index + 10]:
            values = _trim_row(row, max(len(measurement_header), len(row)))
            if _nonempty(values):
                measurement_rows.append([sheet_name, *values])
    if measurement_header is None:
        measurement_header = ['顏色', '組別', '實際重量', '標準用量', '備註', '百分比', '螺桿充填']
    measurement_headers = ['來源設備頁', *_trim_row(measurement_header)]
    return {'色母機履歷': _with_provenance(history_headers, history_data, source_name, '履歷表'), '色母機量測': _with_provenance(measurement_headers, measurement_rows, source_name, measurement_source_sheet)}

def _overview_tables(workbook: Any) -> dict[str, tuple[list[str], list[list[Any]]]]:
    source_name = SOURCE_PATHS()['overview'].name
    updated_rows = _read_nonempty_rows(workbook, '更新版-2026')
    mechanical_rows = _read_nonempty_rows(workbook, '機械手配置機台-2019')
    crane_rows = _read_nonempty_rows(workbook, '天車20230421')
    other_rows = _read_nonempty_rows(workbook, '001B')
    return {'設備總覽': _with_provenance(updated_rows[0], updated_rows[1:], source_name, '更新版-2026'), '機械手配置': _with_provenance(mechanical_rows[0], mechanical_rows[1:], source_name, '機械手配置機台-2019'), '天車清單': _with_provenance(crane_rows[0], crane_rows[1:], source_name, '天車20230421'), '其他設備': _with_provenance(other_rows[0], other_rows[1:], source_name, '001B')}

def _simple_source_table(workbook: Any, sheet_name: str, source_name: str, output_name: str) -> tuple[list[str], list[list[Any]]]:
    rows = _read_nonempty_rows(workbook, sheet_name)
    if not rows:
        return (['資料來源檔案', '來源工作表', '內容'], [])
    return _with_provenance(rows[0], rows[1:], source_name, sheet_name)

def _build_model(workbooks: dict[str, Any], metadata: dict[str, dict[str, Any]]) -> tuple[list[tuple[str, list[str], list[list[Any]]]], dict[str, Any]]:
    tables: dict[str, tuple[list[str], list[list[Any]]]] = {}
    tables.update(_injection_tables(workbooks['injection']))
    tables.update(_masterbatch_tables(workbooks['masterbatch']))
    tables.update(_overview_tables(workbooks['overview']))
    _overview_name = SOURCE_PATHS()['overview'].name
    masterbatch_name = SOURCE_PATHS()['masterbatch'].name
    tables['螺桿套桶間隙'] = _simple_source_table(workbooks['masterbatch'], '螺桿與套桶間隙', masterbatch_name, '螺桿套桶間隙')
    tables['三家比較'] = _simple_source_table(workbooks['masterbatch'], '3家比較', masterbatch_name, '三家比較')
    source_rows: list[list[Any]] = []
    for key, info in metadata.items():
        for sheet_name in info['sheets']:
            source_rows.append([info['name'], sheet_name, info['sha256'], info['size_bytes']])
    tables['來源索引'] = (['來源檔案', '來源工作表', '來源SHA256', '來源大小bytes'], source_rows)
    quality_rows: list[list[Any]] = []
    for sheet_name, expected in EXPECTED_DATA_COUNTS.items():
        observed = len(tables[sheet_name][1])
        if observed != expected:
            quality_rows.append([sheet_name, 'row_count_mismatch', expected, observed, '需人工確認來源版次或篩選規則'])
    quality_rows.extend([['射出機規格', 'status_values', '含已報廢與待識別設備', '', '查詢表已排除已報廢資料；規格表保留原始狀態'], ['設備總覽', 'date_values', '來源含混合日期格式', '', '匯入後保留原值，避免未經確認的日期轉換']])
    tables['資料品質問題'] = (['工作表', '問題類型', '期望/觀察', '觀察值', '處理建議'], quality_rows)
    tables['欄位字典'] = (['工作表', '欄位', '說明'], [[name, header, '由固定來源表整理；原始值保留'] for name, (headers, _rows) in tables.items() for header in headers])
    tables['使用說明'] = (['主題', '說明'], [['用途', '內部設備規格查詢暫存工作簿；來源資料由三個 requester-provided Excel 檔案整理。'], ['查詢入口', '射出機查詢、設備總覽、射出機規格、色母機履歷、色母機量測。'], ['資料邊界', '本 wrapper 不修改來源檔案、不建立 Google Sheet、不變更分享權限、不發送訊息。'], ['品質提醒', '請先檢查資料品質問題，再由核准的 Google Sheet 寫入流程處理來源系統寫入。']])
    ordered: list[tuple[str, list[str], list[list[Any]]]] = []
    for name in EXPECTED_SHEET_NAMES:
        headers, rows = tables.get(name, (['內容'], []))
        ordered.append((name, headers, rows))
    counts = {name: len(rows) for name, _headers, rows in ordered}
    return (ordered, {'sheet_count': len(ordered), 'sheet_names': [name for name, _headers, _rows in ordered], 'data_counts': counts, 'expected_data_counts': dict(EXPECTED_DATA_COUNTS), 'count_checks': {name: counts.get(name) == expected for name, expected in EXPECTED_DATA_COUNTS.items()}})

def _write_table(worksheet: Any, headers: list[str], rows: list[list[Any]]) -> None:
    headers = _unique_headers(headers)
    worksheet.append(headers)
    for row in rows:
        worksheet.append([_safe_scalar(value) for value in _trim_row(row, len(headers))])
    worksheet.freeze_panes = 'A2'
    worksheet.auto_filter.ref = f'A1:{get_column_letter(max(1, len(headers)))}{max(1, worksheet.max_row)}'
    header_fill = PatternFill(fill_type='solid', fgColor='1F4E78')
    for cell in worksheet[1]:
        cell.font = Font(color='FFFFFF', bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    for index in range(1, len(headers) + 1):
        values = [worksheet.cell(row=row, column=index).value for row in range(1, min(worksheet.max_row, 100) + 1)]
        width = min(36, max(10, max((len(_text(value)) for value in values), default=10) + 2))
        worksheet.column_dimensions[get_column_letter(index)].width = width
    worksheet.row_dimensions[1].height = 32

def build_workbook(output_path: Path) -> dict[str, Any]:
    if output_path.parent != STAGING_ROOT() and STAGING_ROOT() not in output_path.parents:
        raise ValueError(f'output must be under the fixed staging root: {STAGING_ROOT()}')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbooks, metadata = _load_sources()
    try:
        ordered, model = _build_model(workbooks, metadata)
        workbook = Workbook()
        default = workbook.active
        workbook.remove(default)
        for name, headers, rows in ordered:
            worksheet = workbook.create_sheet(title=name)
            _write_table(worksheet, headers, rows)
        temp_handle = tempfile.NamedTemporaryFile(prefix='equipment-workbook-', suffix='.xlsx', dir=output_path.parent, delete=False)
        temp_path = Path(temp_handle.name)
        temp_handle.close()
        try:
            workbook.save(temp_path)
        finally:
            workbook.close()
        os.replace(temp_path, output_path)
    finally:
        for workbook in workbooks.values():
            workbook.close()
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return {'status': 'ok', 'capability': 'pd_one_equipment_workbook_build', 'action': 'stage', 'output_path': str(output_path), 'output_sha256': digest, 'model': model, 'safety': {'read_only_sources': True, 'source_system_writes_forbidden': True, 'external_sends_forbidden': True, 'permission_changes_forbidden': True, 'fixed_source_paths': True, 'fixed_staging_root': True, 'atomic_output_replace': True}}

def check_sources() -> dict[str, Any]:
    workbooks, metadata = _load_sources()
    try:
        ordered, model = _build_model(workbooks, metadata)
    finally:
        for workbook in workbooks.values():
            workbook.close()
    return {'status': 'ok' if all(model['count_checks'].values()) else 'partial', 'capability': 'pd_one_equipment_workbook_build', 'action': 'check', 'sources': metadata, 'model': model, 'safety': {'read_only': True, 'source_system_writes_forbidden': True, 'external_sends_forbidden': True, 'permission_changes_forbidden': True, 'fixed_source_paths': True, 'output_written': False}}

def run(action: str='check') -> dict[str, Any]:
    action = str(action or 'check').strip().lower()
    if action == 'check':
        return check_sources()
    if action == 'stage':
        return build_workbook(STAGING_ROOT() / DEFAULT_OUTPUT_NAME)
    raise ValueError('action must be one of: check, stage')

def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=['check', 'stage'], default='check')
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

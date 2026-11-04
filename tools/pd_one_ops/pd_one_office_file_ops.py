"""Bounded read/write Office file operations for approved PD One document roots.

Employees may use this capability for drafting files under cache/documents,
artifacts, tmp, workspace out, employee exports, and employee artifacts.
No shell, network, or source-system writes.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

_OOXML_SPREADSHEET_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_OOXML_PACKAGE_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
_OOXML_CONTENT_TYPES_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
_OOXML_OFFICE_REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

from tools.pd_one_ops.pd_one_safe_ops_part0 import DOC_ALLOWED_ROOTS, ROOT
from tools.pd_one_ops.pd_one_safe_ops_part2 import is_within

OFFICE_FILE_OPS_READ_SUFFIXES = frozenset({
    '.xlsx', '.xlsm', '.xls', '.csv', '.tsv', '.docx', '.doc', '.pptx', '.ppt',
    '.pdf', '.odt', '.ods', '.odp', '.rtf',
})
OFFICE_FILE_OPS_WRITE_SUFFIXES = frozenset({'.xlsx', '.csv', '.tsv', '.docx', '.pptx'})
OFFICE_FILE_OPS_MAX_BYTES = 40 * 1024 * 1024
OFFICE_FILE_OPS_MAX_ROWS = 2000
OFFICE_FILE_OPS_MAX_COLS = 100
OFFICE_FILE_OPS_MAX_CELL_CHARS = 4000
OFFICE_FILE_OPS_MAX_TEXT_CHARS = 120_000
OFFICE_FILE_OPS_MAX_PARAGRAPHS = 200
OFFICE_FILE_OPS_MAX_SLIDES = 50
OFFICE_FILE_OPS_MAX_BULLETS_PER_SLIDE = 40
OFFICE_FILE_OPS_MAX_SHEETS = 20
OFFICE_FILE_OPS_SPEC_MAX_BYTES = 2 * 1024 * 1024


def office_file_ops_allowed_roots() -> list[Path]:
    return [
        *DOC_ALLOWED_ROOTS(),
        ROOT() / 'legacy-openclaw/workspace-employee/exports',
        ROOT() / 'legacy-openclaw/workspace-employee/artifacts',
    ]


def _require_allowed_path(path: Path, *, label: str, must_exist: bool) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if not any(is_within(resolved, root) for root in office_file_ops_allowed_roots()):
        raise ValueError(f'{label} is outside approved PD One document roots: {resolved}')
    if must_exist and not resolved.is_file():
        raise ValueError(f'{label} not found or not a regular file: {resolved}')
    return resolved


def _require_output_path(path: Path, *, input_path: Path | None) -> Path:
    resolved = _require_allowed_path(path, label='output_path', must_exist=False)
    if input_path is not None and resolved == input_path.resolve(strict=False):
        raise ValueError('output_path must not overwrite the input file')
    if resolved.exists() and input_path is not None and resolved.samefile(input_path):
        raise ValueError('output_path must not overwrite the input file')
    return resolved


def _safety(*, read_only: bool) -> dict[str, Any]:
    return {
        'read_only': read_only,
        'shell_used': False,
        'network_used': False,
        'source_system_writes_forbidden': True,
        'external_delivery': False,
        'approved_document_roots_only': True,
    }


def _trim_cell(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    if len(text) > OFFICE_FILE_OPS_MAX_CELL_CHARS:
        return text[:OFFICE_FILE_OPS_MAX_CELL_CHARS] + '…'
    return text


def _bound_table_rows(rows: list[list[Any]]) -> tuple[list[list[Any]], bool]:
    truncated = False
    if len(rows) > OFFICE_FILE_OPS_MAX_ROWS:
        rows = rows[:OFFICE_FILE_OPS_MAX_ROWS]
        truncated = True
    out: list[list[Any]] = []
    for row in rows:
        if len(row) > OFFICE_FILE_OPS_MAX_COLS:
            row = row[:OFFICE_FILE_OPS_MAX_COLS]
            truncated = True
        out.append([_trim_cell(cell) for cell in row])
    return out, truncated


def _read_csv_tsv(path: Path, *, delimiter: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > OFFICE_FILE_OPS_MAX_BYTES:
        raise ValueError(f'file exceeds {OFFICE_FILE_OPS_MAX_BYTES} byte limit')
    text = raw.decode('utf-8-sig')
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows: list[list[Any]] = []
    for row in reader:
        rows.append(row)
        if len(rows) > OFFICE_FILE_OPS_MAX_ROWS + 1:
            raise ValueError(f'row count exceeds limit of {OFFICE_FILE_OPS_MAX_ROWS}')
        if row and len(row) > OFFICE_FILE_OPS_MAX_COLS:
            raise ValueError(f'column count exceeds limit of {OFFICE_FILE_OPS_MAX_COLS}')
    bounded, truncated = _bound_table_rows(rows)
    return {
        'type': path.suffix.lower(),
        'rows': bounded,
        'row_count': len(bounded),
        'truncated': truncated,
    }


def _read_xlsx(path: Path, *, sheet: str | None, max_rows: int, max_cols: int) -> dict[str, Any]:
    from openpyxl import load_workbook

    if path.stat().st_size > OFFICE_FILE_OPS_MAX_BYTES:
        raise ValueError(f'workbook exceeds {OFFICE_FILE_OPS_MAX_BYTES} bytes')
    workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    try:
        sheet_names = list(workbook.sheetnames)
        if len(sheet_names) > OFFICE_FILE_OPS_MAX_SHEETS:
            raise ValueError(f'sheet count exceeds limit of {OFFICE_FILE_OPS_MAX_SHEETS}')
        target = sheet or (sheet_names[0] if sheet_names else None)
        if target is None:
            raise ValueError('workbook has no sheets')
        if target not in sheet_names:
            raise ValueError(f'sheet not found: {target!r}')
        worksheet = workbook[target]
        cap_rows = min(max_rows, OFFICE_FILE_OPS_MAX_ROWS)
        cap_cols = min(max_cols, OFFICE_FILE_OPS_MAX_COLS)
        rows: list[list[Any]] = []
        for row_idx, values in enumerate(
            worksheet.iter_rows(min_row=1, max_row=cap_rows, min_col=1, max_col=cap_cols, values_only=True),
            start=1,
        ):
            rows.append(list(values))
        truncated = bool(int(worksheet.max_row or 0) > cap_rows or int(worksheet.max_column or 0) > cap_cols)
        bounded, row_trunc = _bound_table_rows(rows)
        return {
            'type': path.suffix.lower(),
            'sheet_names': sheet_names[:OFFICE_FILE_OPS_MAX_SHEETS],
            'sheet': target,
            'rows': bounded,
            'row_count': len(bounded),
            'truncated': truncated or row_trunc,
        }
    finally:
        workbook.close()


def _read_xls(path: Path, *, sheet: str | None) -> dict[str, Any]:
    from tools.pd_one_ops.pd_one_safe_ops_part2 import inspect_legacy_xls

    report = inspect_legacy_xls(
        path,
        sheet=sheet,
        max_sheets=1,
        preview_rows=OFFICE_FILE_OPS_MAX_ROWS,
        preview_cols=OFFICE_FILE_OPS_MAX_COLS,
        max_nonempty_cells=OFFICE_FILE_OPS_MAX_ROWS * OFFICE_FILE_OPS_MAX_COLS,
        max_merged_cells=0,
    )
    if report.get('status') == 'blocked':
        raise ValueError(str(report.get('message') or report.get('error') or report.get('blocker')))
    sheets = report.get('sheets') or []
    if not sheets:
        raise ValueError('legacy XLS workbook has no readable sheets')
    first = sheets[0]
    rows = first.get('preview_rows') or []
    bounded, truncated = _bound_table_rows(rows)
    workbook = report.get('workbook') or {}
    return {
        'type': '.xls',
        'sheet_names': workbook.get('sheet_names') or [],
        'sheet': first.get('name'),
        'rows': bounded,
        'row_count': len(bounded),
        'truncated': bool(first.get('preview_truncated')) or truncated,
    }


def _read_structured_office(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in {'.csv', '.tsv'}:
        return _read_csv_tsv(path, delimiter='\t' if suffix == '.tsv' else ',')
    if suffix in {'.xlsx', '.xlsm'}:
        return _read_xlsx(path, sheet=None, max_rows=OFFICE_FILE_OPS_MAX_ROWS, max_cols=OFFICE_FILE_OPS_MAX_COLS)
    if suffix == '.xls':
        return _read_xls(path, sheet=None)
    if suffix in {'.ppt', '.odt', '.ods', '.odp', '.rtf'}:
        return _read_anydoc_text(path)
    from tools.pd_one_ops.pd_one_safe_ops_part2 import extract_by_suffix

    _, extracted = extract_by_suffix(path)
    text = json.dumps(extracted, ensure_ascii=False)
    if len(text) > OFFICE_FILE_OPS_MAX_TEXT_CHARS:
        text = text[:OFFICE_FILE_OPS_MAX_TEXT_CHARS] + '…'
    payload: dict[str, Any] = {'type': suffix, 'extracted': extracted, 'text_chars': len(text)}
    if suffix in {'.docx', '.doc'}:
        payload['paragraphs'] = (extracted.get('paragraphs') or [])[:OFFICE_FILE_OPS_MAX_PARAGRAPHS]
    if suffix == '.pptx':
        payload['slides'] = (extracted.get('slides') or [])[:OFFICE_FILE_OPS_MAX_SLIDES]
    if suffix == '.pdf':
        payload['pages'] = (extracted.get('pages') or [])[:50]
    return payload


def _read_anydoc_text(path: Path) -> dict[str, Any]:
    from tools.read_extract import ExtractionError, extract_document_text

    try:
        text = extract_document_text(str(path))
    except ExtractionError as exc:
        raise ValueError(str(exc)) from exc
    if len(text) > OFFICE_FILE_OPS_MAX_TEXT_CHARS:
        text = text[:OFFICE_FILE_OPS_MAX_TEXT_CHARS] + '…'
    return {'type': path.suffix.lower(), 'text': text, 'text_chars': len(text)}


def read_office_file(
    input_path: str | Path,
    *,
    sheet: str | None = None,
    max_rows: int = OFFICE_FILE_OPS_MAX_ROWS,
    max_cols: int = OFFICE_FILE_OPS_MAX_COLS,
) -> dict[str, Any]:
    path = _require_allowed_path(Path(input_path), label='input_path', must_exist=True)
    suffix = path.suffix.lower()
    if suffix not in OFFICE_FILE_OPS_READ_SUFFIXES:
        raise ValueError(f'unsupported read format: {suffix}')
    if path.stat().st_size > OFFICE_FILE_OPS_MAX_BYTES:
        raise ValueError(f'file exceeds {OFFICE_FILE_OPS_MAX_BYTES} byte limit')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if suffix in {'.odt', '.ods', '.odp', '.rtf'}:
        body = _read_anydoc_text(path)
    elif suffix in {'.xlsx', '.xlsm'} and sheet is not None:
        body = _read_xlsx(path, sheet=sheet, max_rows=max_rows, max_cols=max_cols)
    elif suffix in {'.xls'} and sheet is not None:
        from tools.pd_one_ops.pd_one_safe_ops_part2 import inspect_legacy_xls

        report = inspect_legacy_xls(
            path,
            sheet=sheet,
            max_sheets=1,
            preview_rows=max_rows,
            preview_cols=max_cols,
            max_nonempty_cells=max_rows * max_cols,
            max_merged_cells=0,
        )
        if report.get('status') == 'blocked':
            raise ValueError(str(report.get('message') or report.get('error') or report.get('blocker')))
        sheets = report.get('sheets') or []
        if not sheets:
            raise ValueError('legacy XLS workbook has no readable sheets')
        first = sheets[0]
        rows = first.get('preview_rows') or []
        bounded, truncated = _bound_table_rows(rows)
        body = {
            'type': '.xls',
            'sheet_names': (report.get('workbook') or {}).get('sheet_names') or [],
            'sheet': first.get('name'),
            'rows': bounded,
            'row_count': len(bounded),
            'truncated': bool(first.get('preview_truncated')) or truncated,
        }
    elif suffix in {'.csv', '.tsv'}:
        body = _read_csv_tsv(path, delimiter='\t' if suffix == '.tsv' else ',')
    else:
        body = _read_structured_office(path)
    return {
        'status': 'ok',
        'capability': 'pd_one_office_file_ops',
        'action': 'read',
        'input': str(path),
        'size_bytes': path.stat().st_size,
        'sha256': digest,
        **body,
        'safety': _safety(read_only=True),
    }


def _load_write_spec(spec_path: Path) -> dict[str, Any]:
    spec_file = _require_allowed_path(spec_path, label='spec_path', must_exist=True)
    if spec_file.stat().st_size > OFFICE_FILE_OPS_SPEC_MAX_BYTES:
        raise ValueError(f'spec exceeds {OFFICE_FILE_OPS_SPEC_MAX_BYTES} bytes')
    try:
        spec = json.loads(spec_file.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError(f'invalid JSON spec: {exc}') from exc
    if not isinstance(spec, dict):
        raise ValueError('spec must be a JSON object')
    return spec


def _collect_table_strings(rows: list[list[Any]]) -> set[str]:
    found: set[str] = set()
    for row in rows:
        for cell in row:
            if cell is None:
                continue
            found.add(str(cell))
    return found


def _ooxml_inline_string_text(cell: ET.Element) -> str:
    parts: list[str] = []
    for node in cell.iter(f'{{{_OOXML_SPREADSHEET_NS}}}t'):
        parts.append(node.text or '')
    return ''.join(parts)


def _promote_xlsx_inline_strings_to_shared(path: Path) -> None:
    """openpyxl 3.x writes string cells as inlineStr; Excel tooling expects shared strings."""
    with zipfile.ZipFile(path, 'r') as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}

    shared_index: dict[str, int] = {}
    shared_values: list[str] = []
    reference_count = 0

    def intern_string(text: str) -> int:
        if text not in shared_index:
            shared_index[text] = len(shared_values)
            shared_values.append(text)
        return shared_index[text]

    sheet_names = sorted(
        name for name in entries if name.startswith('xl/worksheets/sheet') and name.endswith('.xml')
    )
    for sheet_name in sheet_names:
        root = ET.fromstring(entries[sheet_name])
        for cell in root.iter(f'{{{_OOXML_SPREADSHEET_NS}}}c'):
            if cell.get('t') != 'inlineStr':
                continue
            text = _ooxml_inline_string_text(cell)
            idx = intern_string(text)
            reference_count += 1
            cell.attrib['t'] = 's'
            for child in list(cell):
                cell.remove(child)
            value = ET.SubElement(cell, f'{{{_OOXML_SPREADSHEET_NS}}}v')
            value.text = str(idx)
        entries[sheet_name] = ET.tostring(root, encoding='utf-8', xml_declaration=True)

    if not shared_values:
        return

    sst = ET.Element(
        f'{{{_OOXML_SPREADSHEET_NS}}}sst',
        count=str(reference_count),
        uniqueCount=str(len(shared_values)),
    )
    for text in shared_values:
        item = ET.SubElement(sst, f'{{{_OOXML_SPREADSHEET_NS}}}si')
        text_node = ET.SubElement(item, f'{{{_OOXML_SPREADSHEET_NS}}}t')
        text_node.text = text
    entries['xl/sharedStrings.xml'] = ET.tostring(sst, encoding='utf-8', xml_declaration=True)

    types_root = ET.fromstring(entries['[Content_Types].xml'])
    override_tag = f'{{{_OOXML_CONTENT_TYPES_NS}}}Override'
    shared_part = '/xl/sharedStrings.xml'
    if not any(element.get('PartName') == shared_part for element in types_root.findall(override_tag)):
        override = ET.SubElement(types_root, override_tag)
        override.set('PartName', shared_part)
        override.set(
            'ContentType',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml',
        )
    entries['[Content_Types].xml'] = ET.tostring(types_root, encoding='utf-8', xml_declaration=True)

    rels_path = 'xl/_rels/workbook.xml.rels'
    rels_root = ET.fromstring(entries[rels_path])
    rel_tag = f'{{{_OOXML_PACKAGE_REL_NS}}}Relationship'
    if not any(element.get('Target') == 'sharedStrings.xml' for element in rels_root.findall(rel_tag)):
        rel_ids = [
            element.get('Id', '')
            for element in rels_root.findall(rel_tag)
            if (element.get('Id') or '').startswith('rId')
        ]
        next_num = max((int(rel_id[3:]) for rel_id in rel_ids if rel_id[3:].isdigit()), default=0) + 1
        relationship = ET.SubElement(rels_root, rel_tag)
        relationship.set('Id', f'rId{next_num}')
        relationship.set('Type', f'{_OOXML_OFFICE_REL_NS}/sharedStrings')
        relationship.set('Target', 'sharedStrings.xml')
    entries[rels_path] = ET.tostring(rels_root, encoding='utf-8', xml_declaration=True)

    temp = path.with_name(f'.{path.name}.{os.getpid()}.shared.tmp')
    try:
        with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _verify_shared_strings(path: Path, expected: set[str]) -> bool:
    non_ascii = {value for value in expected if any(ord(ch) > 127 for ch in value)}
    if not non_ascii:
        return True
    with zipfile.ZipFile(path) as archive:
        try:
            xml = archive.read('xl/sharedStrings.xml').decode('utf-8')
        except KeyError:
            return False
    return all(item in xml for item in non_ascii)


def _write_xlsx(out: Path, spec: dict[str, Any]) -> dict[str, Any]:
    from openpyxl import Workbook

    sheets = spec.get('sheets')
    if not isinstance(sheets, list) or not sheets:
        raise ValueError('xlsx write spec requires a non-empty sheets list')
    if len(sheets) > OFFICE_FILE_OPS_MAX_SHEETS:
        raise ValueError(f'sheets exceeds limit of {OFFICE_FILE_OPS_MAX_SHEETS}')
    workbook = Workbook()
    default = workbook.active
    workbook.remove(default)
    has_formula = False
    all_strings: set[str] = set()
    for index, sheet_spec in enumerate(sheets):
        if not isinstance(sheet_spec, dict):
            raise ValueError(f'sheets[{index}] must be an object')
        name = str(sheet_spec.get('name') or f'Sheet{index + 1}')[:31]
        rows = sheet_spec.get('rows')
        if not isinstance(rows, list):
            raise ValueError(f'sheets[{index}].rows must be a list')
        if len(rows) > OFFICE_FILE_OPS_MAX_ROWS:
            raise ValueError(f'sheets[{index}].rows exceeds row limit')
        worksheet = workbook.create_sheet(title=name)
        for row in rows:
            if not isinstance(row, list):
                raise ValueError(f'sheets[{index}].rows entries must be lists')
            if len(row) > OFFICE_FILE_OPS_MAX_COLS:
                raise ValueError(f'sheets[{index}] row exceeds column limit')
            normalized: list[Any] = []
            for cell in row:
                if isinstance(cell, str) and cell.startswith('='):
                    has_formula = True
                    if len(cell) > OFFICE_FILE_OPS_MAX_CELL_CHARS:
                        raise ValueError('formula cell exceeds character limit')
                    normalized.append(cell)
                else:
                    if cell is not None and len(str(cell)) > OFFICE_FILE_OPS_MAX_CELL_CHARS:
                        raise ValueError('cell exceeds character limit')
                    normalized.append(cell)
            worksheet.append(normalized)
            all_strings.update(_collect_table_strings([normalized]))
    if has_formula:
        workbook.calculation.fullCalcOnLoad = True
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_name(f'.{out.name}.{os.getpid()}.tmp')
    try:
        workbook.save(temp)
        os.replace(temp, out)
        _promote_xlsx_inline_strings_to_shared(out)
    finally:
        workbook.close()
        temp.unlink(missing_ok=True)
    verified = _verify_shared_strings(out, all_strings)
    return {
        'format': 'xlsx',
        'sheet_count': len(sheets),
        'has_formulas': has_formula,
        'formula_cached_values_claimed': False,
        'shared_strings_verified': verified,
        'excel_windows_code_page_risk': False,
    }


def _write_csv_tsv(out: Path, spec: dict[str, Any], *, delimiter: str, suffix: str) -> dict[str, Any]:
    rows = spec.get('rows')
    if not isinstance(rows, list):
        raise ValueError('csv/tsv write spec requires rows list')
    if len(rows) > OFFICE_FILE_OPS_MAX_ROWS:
        raise ValueError('rows exceeds row limit')
    bounded, _ = _bound_table_rows(rows)
    non_ascii = False
    for row in bounded:
        if not isinstance(row, list):
            raise ValueError('rows entries must be lists')
        for cell in row:
            text = '' if cell is None else str(cell)
            if any(ord(ch) > 127 for ch in text):
                non_ascii = True
            if len(text) > OFFICE_FILE_OPS_MAX_CELL_CHARS:
                raise ValueError('cell exceeds character limit')
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_name(f'.{out.name}.{os.getpid()}.tmp')
    try:
        with temp.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle, delimiter=delimiter, lineterminator='\n')
            writer.writerows(bounded)
        os.replace(temp, out)
    finally:
        temp.unlink(missing_ok=True)
    return {
        'format': suffix.lstrip('.'),
        'row_count': len(bounded),
        'shared_strings_verified': False,
        'excel_windows_code_page_risk': non_ascii,
    }


def _write_docx(out: Path, spec: dict[str, Any]) -> dict[str, Any]:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    paragraphs = spec.get('paragraphs')
    if not isinstance(paragraphs, list) or not paragraphs:
        raise ValueError('docx write spec requires a non-empty paragraphs list')
    if len(paragraphs) > OFFICE_FILE_OPS_MAX_PARAGRAPHS:
        raise ValueError('paragraphs exceeds safe limit')
    document = Document()
    title = spec.get('title')
    if title is not None:
        if not isinstance(title, str) or not title.strip():
            raise ValueError('title must be a non-empty string when provided')
        if len(title) > 500:
            raise ValueError('title exceeds character limit')
        para = document.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(title.strip())
        run.bold = True
        run.font.size = Pt(16)
    for index, paragraph in enumerate(paragraphs):
        if not isinstance(paragraph, str):
            raise ValueError(f'paragraphs[{index}] must be a string')
        if len(paragraph) > 20_000:
            raise ValueError(f'paragraphs[{index}] exceeds character limit')
        document.add_paragraph(paragraph)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_name(f'.{out.name}.{os.getpid()}.tmp')
    try:
        document.save(temp)
        os.replace(temp, out)
    finally:
        temp.unlink(missing_ok=True)
    return {'format': 'docx', 'paragraph_count': len(paragraphs), 'shared_strings_verified': False, 'excel_windows_code_page_risk': False}


def _write_pptx(out: Path, spec: dict[str, Any]) -> dict[str, Any]:
    from pptx import Presentation
    from pptx.util import Pt

    slides = spec.get('slides')
    if not isinstance(slides, list) or not slides:
        raise ValueError('pptx write spec requires a non-empty slides list')
    if len(slides) > OFFICE_FILE_OPS_MAX_SLIDES:
        raise ValueError('slides exceeds safe limit')
    presentation = Presentation()
    title_text = spec.get('title')
    if title_text is not None:
        if not isinstance(title_text, str) or not title_text.strip():
            raise ValueError('title must be a non-empty string when provided')
        slide = presentation.slides.add_slide(presentation.slide_layouts[0])
        slide.shapes.title.text = title_text.strip()
    for index, slide_spec in enumerate(slides):
        if not isinstance(slide_spec, dict):
            raise ValueError(f'slides[{index}] must be an object')
        layout = presentation.slide_layouts[1]
        slide = presentation.slides.add_slide(layout)
        heading = str(slide_spec.get('title') or f'Slide {index + 1}')
        if len(heading) > 500:
            raise ValueError('slide title exceeds character limit')
        slide.shapes.title.text = heading
        bullets = slide_spec.get('bullets') or []
        if not isinstance(bullets, list):
            raise ValueError(f'slides[{index}].bullets must be a list')
        if len(bullets) > OFFICE_FILE_OPS_MAX_BULLETS_PER_SLIDE:
            raise ValueError('bullets exceeds safe limit')
        body = slide.shapes.placeholders[1].text_frame
        body.clear()
        for bullet_index, bullet in enumerate(bullets):
            if not isinstance(bullet, str):
                raise ValueError(f'slides[{index}].bullets[{bullet_index}] must be a string')
            if len(bullet) > 4000:
                raise ValueError('bullet text exceeds character limit')
            paragraph = body.add_paragraph() if bullet_index else body.paragraphs[0]
            paragraph.text = bullet
            paragraph.level = 0
            paragraph.font.size = Pt(18)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_name(f'.{out.name}.{os.getpid()}.tmp')
    try:
        presentation.save(temp)
        os.replace(temp, out)
    finally:
        temp.unlink(missing_ok=True)
    return {
        'format': 'pptx',
        'slide_count': len(slides) + (1 if title_text else 0),
        'shared_strings_verified': False,
        'excel_windows_code_page_risk': False,
    }


def write_office_file(
    output_path: str | Path,
    spec_path: str | Path,
    *,
    input_path: str | Path | None = None,
    format_hint: str | None = None,
) -> dict[str, Any]:
    resolved_input = None
    if input_path:
        resolved_input = _require_allowed_path(Path(input_path), label='input_path', must_exist=True)
    out = _require_output_path(Path(output_path), input_path=resolved_input)
    spec = _load_write_spec(Path(spec_path))
    suffix = out.suffix.lower()
    hinted = (format_hint or spec.get('format') or '').strip().lower()
    if hinted and not hinted.startswith('.'):
        hinted = f'.{hinted}'
    if suffix not in OFFICE_FILE_OPS_WRITE_SUFFIXES:
        raise ValueError(f'unsupported write output format: {suffix}')
    if hinted and hinted != suffix:
        raise ValueError(f'format hint {hinted!r} does not match output suffix {suffix!r}')
    writers = {
        '.xlsx': lambda: _write_xlsx(out, spec),
        '.csv': lambda: _write_csv_tsv(out, spec, delimiter=',', suffix='.csv'),
        '.tsv': lambda: _write_csv_tsv(out, spec, delimiter='\t', suffix='.tsv'),
        '.docx': lambda: _write_docx(out, spec),
        '.pptx': lambda: _write_pptx(out, spec),
    }
    build = writers[suffix]()
    data = out.read_bytes()
    return {
        'status': 'ok',
        'capability': 'pd_one_office_file_ops',
        'action': 'write',
        'output': str(out),
        'output_size_bytes': len(data),
        'output_sha256': hashlib.sha256(data).hexdigest(),
        'spec': str(Path(spec_path).expanduser().resolve(strict=False)),
        'build': build,
        'safety': _safety(read_only=False),
    }


def run(action: str, **kwargs: Any) -> dict[str, Any]:
    normalized = str(action or '').strip().lower()
    if normalized == 'read':
        return read_office_file(
            kwargs['input_path'],
            sheet=kwargs.get('sheet'),
            max_rows=int(kwargs.get('max_rows') or OFFICE_FILE_OPS_MAX_ROWS),
            max_cols=int(kwargs.get('max_cols') or OFFICE_FILE_OPS_MAX_COLS),
        )
    if normalized == 'write':
        return write_office_file(
            kwargs['output_path'],
            kwargs['spec_path'],
            input_path=kwargs.get('input_path'),
            format_hint=kwargs.get('format'),
        )
    raise ValueError('action must be read or write')

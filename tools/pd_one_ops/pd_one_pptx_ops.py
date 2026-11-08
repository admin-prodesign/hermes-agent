#!/usr/bin/env python3
"""Bounded PPTX exact-text inspection and staged revision helper.

Inspect an approved PPTX for 1-8 unique visible text matches, or stage a
separate PPTX with those matches replaced. Never overwrite the source, send
files, or treat a staged revision as a delivered artifact.
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
import difflib
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator

def ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))

def INPUT_ROOTS():
    return (ROOT() / 'cache/documents', ROOT() / 'artifacts', ROOT() / 'tmp', ROOT() / 'legacy-openclaw/workspace-employee/out')

def OUTPUT_ROOTS():
    return (ROOT() / 'artifacts', ROOT() / 'tmp', ROOT() / 'legacy-openclaw/workspace-employee/out')
MAX_BYTES = 50 * 1024 * 1024
MAX_TEXT_CHARS = 2000
MAX_REPLACEMENTS = 8

def GATE_SCRIPT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone/skills/pd-one/pd-one-admin/scripts/office_no_corruption_gate.py'))

def SANITIZE_SCRIPT():
    return ROOT() / 'scripts' / 'pptx_office_sanitize.py'

def FIRM_TEMPLATE():
    return ROOT() / 'templates' / 'firm-template.pptx'

def LAYOUTS_MD():
    return ROOT() / 'templates' / 'LAYOUTS.md'

def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return False

def _require_path(raw: str | Path, roots: tuple[Path, ...], label: str) -> Path:
    path = Path(raw).expanduser().resolve(strict=False)
    if not any((_is_within(path, root) for root in roots)):
        raise ValueError(f'{label} is outside approved PPTX document roots: {path}')
    if not path.is_file():
        raise FileNotFoundError(f'{label} not found: {path}')
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f'{label} exceeds {MAX_BYTES} bytes: {path}')
    return path

def _require_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f'{label} must be a non-empty string')
    if len(value) > MAX_TEXT_CHARS:
        raise ValueError(f'{label} exceeds {MAX_TEXT_CHARS} characters')
    return value

def _require_sha256(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    digest = str(value).strip().lower()
    if len(digest) != 64 or any((ch not in '0123456789abcdef' for ch in digest)):
        raise ValueError('source_sha256 must be a 64-character hexadecimal SHA-256 digest')
    return digest

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def resolve_firm_template() -> Path:
    """Absolute firm-template path (never CWD-relative alone)."""
    if not FIRM_TEMPLATE().is_file():
        raise FileNotFoundError(f'firm template missing: {FIRM_TEMPLATE()}')
    return FIRM_TEMPLATE()

def load_firm_presentation() -> Any:
    """Load the sealed firm template from the profile absolute path."""
    from pptx import Presentation
    return Presentation(str(resolve_firm_template()))

def _run_sanitize(path: Path, *, compat: bool=False) -> dict[str, Any]:
    """ALWAYS heal after prs.save — theme rel, dense rIds, cust/nonrect/idx, MS-DOS pack."""
    if not SANITIZE_SCRIPT().is_file():
        return {'status': 'blocked', 'detail': f'sanitize script not found: {SANITIZE_SCRIPT()}'}
    cmd = [sys.executable, str(SANITIZE_SCRIPT())]
    if compat:
        cmd.append('--compat')
    cmd.append(str(path))
    proc = subprocess.run(cmd, text=True, capture_output=True, shell=False, timeout=180)
    detail = (proc.stderr.strip() or proc.stdout.strip())[-1600:]
    return {'status': 'ok' if proc.returncode == 0 else 'error', 'returncode': proc.returncode, 'detail': detail}

def save_presentation(prs: Any, path: str | Path, *, run_gate: bool=True) -> dict[str, Any]:
    """Save then ALWAYS sanitize (and optionally gate). Models must not call prs.save alone.

    python-pptx prs.save() can drop presentation→theme rel / emit gapped rIds;
    sanitize restores those before delivery. Header/footer placeholders are
    applied here so a forgetful migration cannot ship blank date/footer/sldNum.
    """
    dest = Path(path).expanduser().resolve(strict=False)
    dest.parent.mkdir(parents=True, exist_ok=True)
    hf_result = apply_layout_header_footer(prs)
    source_strip = strip_empty_source_footnote_placeholders(prs)
    require_slide_header_footer(prs)
    prs.save(str(dest))
    sanitize_result = _run_sanitize(dest)
    if sanitize_result['status'] != 'ok':
        raise RuntimeError(f'pptx sanitize failed: {sanitize_result.get('detail', 'unknown error')}')
    receipt: dict[str, Any] = {'status': 'ok', 'path': str(dest), 'sha256': _sha256(dest), 'sanitize': sanitize_result, 'header_footer': hf_result, 'source_footnote_strip': source_strip, 'template': str(FIRM_TEMPLATE())}
    if run_gate:
        gate_result = _run_no_corruption_gate(dest)
        receipt['office_no_corruption_gate'] = gate_result
        if gate_result['status'] != 'ok':
            raise RuntimeError(f'Office no-corruption gate failed: {gate_result.get('detail', 'unknown error')}')
    return receipt
HF_PH_TYPES = frozenset({'dt', 'ftr', 'sldNum'})
DEFAULT_FOOTER_TEXT = 'Pro-Design Group · 良器集團'

def apply_layout_header_footer(prs: Any, *, date_text: str | None=None, footer_text: str=DEFAULT_FOOTER_TEXT) -> dict[str, Any]:
    """Clone layout dt/ftr/sldNum onto every slide.

    python-pptx `clone_layout_placeholders` skips latent date/footer/slide-number
    placeholders. PowerPoint then shows master rails/logo/hairline but blank
    Header/Footer fields. Copy the layout shapes (keep sldNum field) and set p:hf.
    """
    from copy import deepcopy
    from lxml import etree
    from pptx.oxml.ns import qn

    def _next_cNvPr_id(slide_elm) -> int:
        ids = []
        for el in slide_elm.iter(qn('p:cNvPr')):
            raw = el.get('id')
            if raw and str(raw).isdigit():
                ids.append(int(raw))
        return (max(ids) if ids else 1) + 1

    def _set_plain_text(sp, text: str) -> None:
        texts = list(sp.iter(qn('a:t')))
        if not texts:
            return
        texts[0].text = text
        for extra in texts[1:]:
            extra.text = ''
    cloned = 0
    skipped = 0
    for slide in prs.slides:
        sld = slide._element
        existing: set[str] = set()
        for ph in sld.iter(qn('p:ph')):
            typ = ph.get('type')
            if typ in HF_PH_TYPES:
                existing.add(typ)
        spTree = slide.shapes._spTree
        nid = _next_cNvPr_id(sld)
        layout_elm = slide.slide_layout._element
        for sp in layout_elm.iter(qn('p:sp')):
            ph = sp.find('.//' + qn('p:ph'))
            if ph is None:
                continue
            typ = ph.get('type')
            if typ not in HF_PH_TYPES:
                continue
            if typ in existing:
                skipped += 1
                continue
            clone = deepcopy(sp)
            cNvPr = clone.find('.//' + qn('p:cNvPr'))
            if cNvPr is not None:
                cNvPr.set('id', str(nid))
                nid += 1
            if typ == 'dt' and date_text:
                _set_plain_text(clone, date_text)
            elif typ == 'ftr' and footer_text:
                _set_plain_text(clone, footer_text)
            spTree.append(clone)
            existing.add(typ)
            cloned += 1
        if sld.find(qn('p:hf')) is None:
            hf = etree.SubElement(sld, qn('p:hf'))
            hf.set('sldNum', '1')
            hf.set('hdr', '0')
            hf.set('ftr', '1')
            hf.set('dt', '1')
    return {'cloned': cloned, 'skipped_existing': skipped, 'slides': len(prs.slides)}

def require_slide_header_footer(prs: Any) -> None:
    """Fail closed when a layout has dt/ftr/sldNum but the slide does not."""
    from pptx.oxml.ns import qn
    missing: list[str] = []
    for i, slide in enumerate(prs.slides, start=1):
        layout_types = {ph.get('type') for ph in slide.slide_layout._element.iter(qn('p:ph')) if ph.get('type') in HF_PH_TYPES}
        if not layout_types:
            continue
        slide_types = {ph.get('type') for ph in slide._element.iter(qn('p:ph')) if ph.get('type') in HF_PH_TYPES}
        lack = sorted(layout_types - slide_types)
        if lack or slide._element.find(qn('p:hf')) is None:
            missing.append(f'slide {i} missing {lack or ['p:hf']}')
    if missing:
        raise RuntimeError('slides missing header/footer placeholders: ' + '; '.join(missing[:12]))
_SOURCE_NAME_HINTS = ('source', 'footnote', 'footnotes', '資料來源', '來源', '註腳')
_KEEP_FOOTER = 'pro-design group'

def _is_boilerplate_source_footnote(text: str) -> bool:
    """True when the shape has no real citation — empty or SOURCE/FOOTNOTE SAMPLE."""
    blob = ' '.join((text or '').split())
    if not blob:
        return True
    low = blob.lower()
    if _KEEP_FOOTER in low:
        return False
    tokens = ('source', 'footnote', 'footnotes', '資料來源', '來源', '註腳')
    if low in tokens:
        return True
    if '請改為' in blob:
        return True
    if ('資料來源' in blob or low.startswith('source') or 'footnote' in low) and ('sample' in low or '示意' in blob or '…' in blob or ('...' in blob)):
        return True
    return False

def strip_empty_source_footnote_placeholders(prs: Any) -> dict[str, Any]:
    """Drop SOURCE/FOOTNOTE placeholders that have no real content on user slides.

    Does not touch native dt/ftr/sldNum or the company footer string.
    """
    from pptx.oxml.ns import qn
    removed = 0
    for slide in prs.slides:
        sp_tree = slide.shapes._spTree
        for sp in list(sp_tree.iter(qn('p:sp'))):
            ph = sp.find('.//' + qn('p:ph'))
            typ = ph.get('type') if ph is not None else ''
            if typ in HF_PH_TYPES:
                continue
            cnv = sp.find('.//' + qn('p:cNvPr'))
            name = (cnv.get('name') if cnv is not None else '') or ''
            blob = ' '.join((t.text or '' for t in sp.iter(qn('a:t'))))
            name_hit = any((h in name.lower() or h in name for h in _SOURCE_NAME_HINTS))
            text_hit = any((h in blob.lower() or h in blob for h in ('source', 'footnote', '資料來源', '註腳')))
            if not (name_hit or text_hit):
                continue
            if not _is_boilerplate_source_footnote(blob):
                continue
            parent = sp.getparent()
            if parent is not None:
                parent.remove(sp)
                removed += 1
    return {'removed': removed}

def _python_pptx_available() -> bool:
    try:
        import pptx
    except Exception:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return False
    return True

def _load_presentation(path: Path) -> Any:
    if path.suffix.lower() != '.pptx':
        raise ValueError(f'PPTX exact-text patch only supports .pptx input: {path}')
    from pptx import Presentation
    return Presentation(str(path))
ALLOWED_XML_PREFIXES = ('ppt/slides/', 'ppt/notesSlides/', 'ppt/charts/', 'ppt/diagrams/')
MAX_MEMBER_BYTES = 8 * 1024 * 1024

def _safe_zip_name(name: str) -> str:
    cleaned = name.replace('\\', '/')
    if not cleaned or cleaned.startswith('/') or '..' in Path(cleaned).parts:
        raise ValueError(f'unsafe PPTX member name: {name}')
    return cleaned

def _iter_text_xml_members(archive: Any) -> list[str]:
    names: list[str] = []
    for raw in archive.namelist():
        name = _safe_zip_name(raw)
        if name.endswith('.xml') and name.startswith(ALLOWED_XML_PREFIXES):
            names.append(name)
    return names

def _stdlib_find_matches(path: Path, old_text: str) -> list[dict[str, Any]]:
    import zipfile
    matches: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for name in _iter_text_xml_members(archive):
            info = archive.getinfo(name)
            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError(f'PPTX member exceeds {MAX_MEMBER_BYTES} bytes: {name}')
            text = archive.read(name).decode('utf-8')
            count = text.count(old_text)
            if not count:
                continue
            matches.append({'location': {'scope': 'pptx_xml_member', 'member': name}, 'occurrences': count, 'run_indexes': [], 'run_span': {'member': name} if count == 1 else None, 'patchable_without_rebuilding_runs': count == 1})
    return matches

def _stdlib_apply_replacements(source: Path, dest: Path, pairs: list[tuple[str, str]]) -> None:
    import zipfile
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(dest, 'w') as zout:
        text_members = set(_iter_text_xml_members(zin))
        remaining = {old: new for old, new in pairs}
        for item in zin.infolist():
            name = _safe_zip_name(item.filename)
            payload = zin.read(item.filename)
            if name in text_members:
                if item.file_size > MAX_MEMBER_BYTES:
                    raise ValueError(f'PPTX member exceeds {MAX_MEMBER_BYTES} bytes: {name}')
                text = payload.decode('utf-8')
                for old, new in list(remaining.items()):
                    count = text.count(old)
                    if count == 0:
                        continue
                    if count != 1:
                        raise RuntimeError(f'unique XML match no longer holds in {name}')
                    text = text.replace(old, new, 1)
                    remaining.pop(old)
                payload = text.encode('utf-8')
            info = zipfile.ZipInfo(filename=item.filename, date_time=item.date_time)
            info.compress_type = item.compress_type
            zout.writestr(info, payload)
        if remaining:
            raise RuntimeError('one or more replacements were not applied')

def _iter_group_shapes(shapes: Any) -> Iterator[Any]:
    try:
        from pptx.enum.shapes import MSO_SHAPE_TYPE
    except Exception:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        MSO_SHAPE_TYPE = None
    for shape in shapes:
        yield shape
        shape_type = getattr(shape, 'shape_type', None)
        if MSO_SHAPE_TYPE is not None and shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_group_shapes(shape.shapes)

def _iter_paragraphs(prs: Any) -> Iterator[tuple[Any, dict[str, Any]]]:
    seen: list[Any] = []

    def already_seen(paragraph: Any) -> bool:
        element = getattr(paragraph, '_p', paragraph)
        if any((element is previous for previous in seen)):
            return True
        seen.append(element)
        return False

    def emit(paragraph: Any, location: dict[str, Any]) -> Iterator[tuple[Any, dict[str, Any]]]:
        from tools.pd_one_ops.hr_guard import guard_hr_payload
        paragraph = guard_hr_payload(paragraph)
        if already_seen(paragraph):
            return
        yield (paragraph, location)
    for slide_index, slide in enumerate(prs.slides, 1):
        for shape in _iter_group_shapes(slide.shapes):
            shape_id = getattr(shape, 'shape_id', None)
            if getattr(shape, 'has_text_frame', False):
                for paragraph_index, paragraph in enumerate(shape.text_frame.paragraphs):
                    yield from emit(paragraph, {'scope': 'slide_shape', 'slide_index': slide_index, 'shape_id': shape_id, 'paragraph_index': paragraph_index})
            if getattr(shape, 'has_table', False):
                table = shape.table
                for row_index, row in enumerate(table.rows):
                    for cell_index, cell in enumerate(row.cells):
                        for paragraph_index, paragraph in enumerate(cell.text_frame.paragraphs):
                            yield from emit(paragraph, {'scope': 'slide_table_cell', 'slide_index': slide_index, 'shape_id': shape_id, 'row_index': row_index, 'cell_index': cell_index, 'paragraph_index': paragraph_index})
        if getattr(slide, 'has_notes_slide', False):
            notes = slide.notes_slide
            if getattr(notes, 'notes_text_frame', None) is not None:
                for paragraph_index, paragraph in enumerate(notes.notes_text_frame.paragraphs):
                    yield from emit(paragraph, {'scope': 'notes', 'slide_index': slide_index, 'paragraph_index': paragraph_index})

def _paragraph_text(paragraph: Any) -> str:
    return ''.join((run.text or '' for run in paragraph.runs)) or (paragraph.text or '')

def _find_run_span(paragraph: Any, old_text: str) -> dict[str, int] | None:
    run_texts = [run.text or '' for run in paragraph.runs]
    full_text = ''.join(run_texts)
    if full_text.count(old_text) != 1:
        return None
    start = full_text.index(old_text)
    end = start + len(old_text)
    cursor = 0
    start_index = end_index = None
    start_offset = end_offset = 0
    for index, text in enumerate(run_texts):
        next_cursor = cursor + len(text)
        if start_index is None and cursor <= start < next_cursor:
            start_index = index
            start_offset = start - cursor
        if cursor < end <= next_cursor:
            end_index = index
            end_offset = end - cursor
            break
        cursor = next_cursor
    if start_index is None or end_index is None:
        return None
    return {'start_index': start_index, 'end_index': end_index, 'start_offset': start_offset, 'end_offset': end_offset, 'global_start': start, 'global_end': end}

def _find_matches(prs: Any, old_text: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for paragraph, location in _iter_paragraphs(prs):
        count = _paragraph_text(paragraph).count(old_text)
        if not count:
            continue
        run_span = _find_run_span(paragraph, old_text) if count == 1 else None
        run_indexes = []
        if run_span is not None:
            run_indexes = list(range(run_span['start_index'], run_span['end_index'] + 1))
        matches.append({'location': location, 'occurrences': count, 'run_indexes': run_indexes, 'run_span': run_span, 'patchable_without_rebuilding_runs': run_span is not None and count == 1})
    return matches

def _replace_global_span(paragraph: Any, start: int, end: int, replacement: str) -> None:
    run_texts = [run.text or '' for run in paragraph.runs]
    if not run_texts:
        raise RuntimeError('target paragraph has no editable runs')

    def locate_start(position: int) -> tuple[int, int]:
        cursor = 0
        for index, text in enumerate(run_texts):
            next_cursor = cursor + len(text)
            if position < next_cursor or (position == cursor and bool(text)):
                return (index, position - cursor)
            cursor = next_cursor
        if position == cursor:
            return (len(run_texts) - 1, len(run_texts[-1]))
        raise RuntimeError('replacement start is outside paragraph text')

    def locate_end(position: int) -> tuple[int, int]:
        cursor = 0
        for index, text in enumerate(run_texts):
            next_cursor = cursor + len(text)
            if cursor < position <= next_cursor:
                return (index, position - cursor)
            cursor = next_cursor
        raise RuntimeError('replacement end is outside paragraph text')
    if start < 0 or end < start:
        raise RuntimeError('invalid replacement span')
    start_index, start_offset = locate_start(start)
    if start == end:
        paragraph.runs[start_index].text = run_texts[start_index][:start_offset] + replacement + run_texts[start_index][start_offset:]
        return
    end_index, end_offset = locate_end(end)
    if end_index < start_index:
        raise RuntimeError('replacement span run order is invalid')
    if start_index == end_index:
        paragraph.runs[start_index].text = run_texts[start_index][:start_offset] + replacement + run_texts[start_index][end_offset:]
        return
    paragraph.runs[start_index].text = run_texts[start_index][:start_offset] + replacement
    for index in range(start_index + 1, end_index):
        paragraph.runs[index].text = ''
    paragraph.runs[end_index].text = run_texts[end_index][end_offset:]

def _apply_minimal_run_patch(paragraph: Any, old_text: str, new_text: str, run_span: dict[str, int]) -> None:
    global_start = int(run_span['global_start'])
    matcher = difflib.SequenceMatcher(a=old_text, b=new_text, autojunk=False)
    for tag, old_start, old_end, new_start, new_end in reversed(matcher.get_opcodes()):
        if tag == 'equal':
            continue
        _replace_global_span(paragraph, global_start + old_start, global_start + old_end, new_text[new_start:new_end])

def _run_no_corruption_gate(path: Path) -> dict[str, Any]:
    if not GATE_SCRIPT().is_file():
        return {'status': 'blocked', 'detail': f'gate script not found: {GATE_SCRIPT()}'}
    proc = subprocess.run([sys.executable, str(GATE_SCRIPT()), str(path)], text=True, capture_output=True, shell=False, timeout=180)
    detail = (proc.stderr.strip() or proc.stdout.strip())[-1600:]
    return {'status': 'ok' if proc.returncode == 0 else 'error', 'returncode': proc.returncode, 'detail': detail}

def inspect_or_stage_many(*, action: str, input_path: str | Path, replacements: list[list[str]] | list[tuple[str, str]], output_path: str | Path | None=None, source_sha256: str | None=None, overwrite: bool=False) -> dict[str, Any]:
    actual_source_sha256 = _PdUnset
    match = _PdUnset
    new_text = _PdUnset
    old_text = _PdUnset
    output = _PdUnset
    pairs = _PdUnset
    receipt = _PdUnset
    source = _PdUnset
    temp_path = _PdUnset
    use_pptx = _PdUnset

    def _pd_phase_1():
        nonlocal action, actual_source_sha256, new_text, old_text, output, pairs, receipt, source, temp_path, use_pptx
        'Inspect or atomically stage 1-8 exact visible-text PPTX replacements.'
        action = str(action or 'inspect').strip().lower()
        if action not in {'inspect', 'stage'}:
            raise ValueError('action must be one of: inspect, stage')
        if not isinstance(replacements, list) or not 1 <= len(replacements) <= MAX_REPLACEMENTS:
            raise ValueError(f'replacements must contain 1-{MAX_REPLACEMENTS} old/new pairs')
        pairs = []
        for index, pair in enumerate(replacements):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError(f'replacement {index} must be an old/new pair')
            old_text = _require_text(pair[0], f'replacements[{index}].old_text')
            new_text = _require_text(pair[1], f'replacements[{index}].new_text')
            if old_text == new_text:
                raise ValueError(f'replacement {index} old_text and new_text must differ')
            pairs.append((old_text, new_text))
        old_texts = [pair[0] for pair in pairs]
        new_texts = [pair[1] for pair in pairs]
        if len(set(old_texts)) != len(old_texts) or len(set(new_texts)) != len(new_texts):
            raise ValueError('replacement old_text and new_text values must each be unique')
        for index, (old_text, new_text) in enumerate(pairs):
            for other_index, (other_old, other_new) in enumerate(pairs):
                if index == other_index:
                    continue
                if old_text in other_old or old_text in other_new or new_text in other_old:
                    raise ValueError('overlapping or chained replacement values are forbidden')
        source = _require_path(input_path, INPUT_ROOTS(), 'input')
        actual_source_sha256 = _sha256(source)
        expected_sha256 = _require_sha256(source_sha256)
        if expected_sha256 and expected_sha256 != actual_source_sha256:
            return _PdReturn({'status': 'blocked', 'capability': 'pd_one_pptx_exact_text_patch', 'action': action, 'input': str(source), 'source_sha256': actual_source_sha256, 'expected_source_sha256': expected_sha256, 'blocker': 'source_sha256_mismatch', 'safety': {'admin_only': True, 'read_only': True, 'source_never_overwritten': True, 'external_delivery': False}})
        use_pptx = _python_pptx_available()
        engine = 'python_pptx' if use_pptx else 'stdlib_presentationml'
        checks: list[dict[str, Any]] = []
        all_patchable = True
        for old_text, new_text in pairs:
            matches = _find_matches(_load_presentation(source), old_text) if use_pptx else _stdlib_find_matches(source, old_text)
            occurrence_count = sum((int(match['occurrences']) for match in matches))
            patchable = len(matches) == 1 and occurrence_count == 1 and bool(matches[0].get('patchable_without_rebuilding_runs'))
            all_patchable = all_patchable and patchable
            checks.append({'old_text_sha256': hashlib.sha256(old_text.encode('utf-8')).hexdigest(), 'new_text_sha256': hashlib.sha256(new_text.encode('utf-8')).hexdigest(), 'match_count': len(matches), 'occurrence_count': occurrence_count, 'patchable': patchable, 'locations': [match['location'] for match in matches[:2]]})
        receipt = {'status': 'ok' if all_patchable else 'blocked', 'capability': 'pd_one_pptx_exact_text_patch', 'action': action, 'input': str(source), 'source_sha256': actual_source_sha256, 'replacement_count': len(pairs), 'engine': engine, 'checks': checks, 'safety': {'admin_only': True, 'read_only': action == 'inspect', 'source_never_overwritten': True, 'separate_staged_output_required': True, 'source_system_writes_forbidden': True, 'external_delivery': False, 'arbitrary_shell_forbidden': True, 'unique_visible_match_required_per_replacement': True, 'office_integrity_gate_required_for_stage': True, 'arbitrary_openxml_zip_rewrite_forbidden': True}}
        if not all_patchable:
            receipt.update({'blocker': 'all_replacements_must_have_one_patchable_visible_match', 'next_step': 'Correct the exact visible replacement pairs and inspect again; do not run arbitrary PresentationML zip mutation.'})
            return _PdReturn(receipt)
        if action == 'inspect':
            return _PdReturn(receipt)
        if output_path is None:
            raise ValueError('output_path is required for action=stage')
        output = Path(output_path).expanduser().resolve(strict=False)
        if not any((_is_within(output, root) for root in OUTPUT_ROOTS())):
            raise ValueError(f'output is outside approved staged artifact roots: {output}')
        if output.suffix.lower() != '.pptx' or output == source:
            raise ValueError('output must be a separate .pptx under an approved staged artifact root')
        if output.exists() and (not overwrite):
            return _PdReturn({**receipt, 'status': 'blocked', 'blocker': 'output_exists', 'output': str(output)})
        output.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None

    def _pd_phase_2():
        nonlocal match, new_text, old_text, temp_path
        try:
            fd, temp_name = tempfile.mkstemp(prefix=f'.{output.stem}-', suffix='.pptx', dir=str(output.parent))
            os.close(fd)
            temp_path = Path(temp_name)
            if use_pptx:
                shutil.copy2(source, temp_path)
                staged = _load_presentation(temp_path)
                for old_text, new_text in pairs:
                    current_matches = _find_matches(staged, old_text)
                    if len(current_matches) != 1 or sum((int(match['occurrences']) for match in current_matches)) != 1:
                        raise RuntimeError('replacement set changed during staging; unique match no longer holds')
                    match = current_matches[0]
                    run_span = match.get('run_span')
                    if not run_span:
                        raise RuntimeError('staged match did not resolve to a safe run span')
                    target_paragraph = next((paragraph for paragraph, location in _iter_paragraphs(staged) if location == match['location']), None)
                    if target_paragraph is None:
                        raise RuntimeError('could not resolve an inspected paragraph in the staged copy')
                    _apply_minimal_run_patch(target_paragraph, old_text, new_text, run_span)
                staged.save(str(temp_path))
            else:
                _stdlib_apply_replacements(source, temp_path, pairs)
            sanitize_result = _run_sanitize(temp_path)
            if sanitize_result['status'] != 'ok':
                raise RuntimeError(f'pptx sanitize failed: {sanitize_result.get('detail', 'unknown error')}')
            gate_result = _run_no_corruption_gate(temp_path)
            if gate_result['status'] != 'ok':
                raise RuntimeError(f'Office no-corruption gate failed: {gate_result.get('detail', 'unknown error')}')
            os.replace(temp_path, output)
            temp_path = None
            readback_rows = []
            for old_text, new_text in pairs:
                if use_pptx:
                    readback = _load_presentation(output)
                    old_count = sum((int(match['occurrences']) for match in _find_matches(readback, old_text)))
                    new_count = sum((int(match['occurrences']) for match in _find_matches(readback, new_text)))
                else:
                    old_count = sum((int(match['occurrences']) for match in _stdlib_find_matches(output, old_text)))
                    new_count = sum((int(match['occurrences']) for match in _stdlib_find_matches(output, new_text)))
                if old_count != 0 or new_count != 1:
                    raise RuntimeError('staged artifact replacement readback failed')
                readback_rows.append({'old_occurrence_count': old_count, 'new_occurrence_count': new_count})
            receipt.update({'output': str(output), 'output_sha256': _sha256(output), 'changed': True, 'readback': readback_rows, 'source_sha256_unchanged': _sha256(source) == actual_source_sha256, 'office_no_corruption_gate': gate_result, 'pptx_office_sanitize': sanitize_result})
            return _PdReturn(receipt)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
    _pd_result = _pd_phase_1()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
    _pd_result = _pd_phase_2()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
__all__ = ['inspect_or_stage_many', 'load_firm_presentation', 'resolve_firm_template', 'save_presentation']

#!/usr/bin/env python3
"""Stage a PPTX from a POTX/PPTX template without overwriting sources.

clone  — copy a template package to a new .pptx (POTX content-type rewritten).
apply  — reflow source titles/pictures/text onto the template layouts (do not keep
         source xfrm). User templates use compat sanitize (no non-rect ph strip).

Never sends files. Delivery stays a separate Mattermost path.
"""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from pd_one_pptx_ops import INPUT_ROOTS, OUTPUT_ROOTS, _is_within, _require_path, _require_sha256, _run_no_corruption_gate, _run_sanitize, _sha256
PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
OFFICE_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
P_NS = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL_SLIDEMASTER = OFFICE_REL + 'slideMaster'
REL_THEME = OFFICE_REL + 'theme'
REL_LAYOUT = OFFICE_REL + 'slideLayout'
REL_IMAGE = OFFICE_REL + 'image'
REL_SLIDE = OFFICE_REL + 'slide'
TEMPLATE_PREFIXES = ('ppt/slideMasters/', 'ppt/slideLayouts/', 'ppt/theme/')
MAX_SLIDES = 80
POTX_MAIN = 'application/vnd.openxmlformats-officedocument.presentationml.template.main+xml'
PPTX_MAIN = 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'
ET.register_namespace('', PKG_REL_NS)
ET.register_namespace('p', P_NS)
ET.register_namespace('r', R_NS)
ET.register_namespace('ct', CT_NS)

def _zip_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return archive.namelist()

def _zip_read(path: Path, name: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name)

def _parse(xml_bytes: bytes) -> ET.Element:
    return ET.fromstring(xml_bytes)

def _tostring(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)

def _layout_name(xml_bytes: bytes) -> str:
    match = re.search(b'<p:cSld[^>]*name="([^"]*)"', xml_bytes)
    if not match:
        return ''
    return match.group(1).decode('utf-8', 'replace')

def _sldsz(xml_bytes: bytes) -> dict[str, str]:
    match = re.search(b'<p:sldSz[^>]*>', xml_bytes)
    if not match:
        return {}
    cx = re.search(b'cx="(\\d+)"', match.group(0))
    cy = re.search(b'cy="(\\d+)"', match.group(0))
    return {'cx': cx.group(1).decode() if cx else '', 'cy': cy.group(1).decode() if cy else ''}

def _rel_targets(xml_bytes: bytes, rel_type: str) -> list[str]:
    root = _parse(xml_bytes)
    out: list[str] = []
    for child in root:
        if child.get('Type') == rel_type:
            out.append(str(child.get('Target') or ''))
    return out

def _slide_count(path: Path) -> int:
    return sum((1 for name in _zip_names(path) if re.fullmatch('ppt/slides/slide\\d+\\.xml', name)))

def _require_template(path: str | Path) -> Path:
    template = _require_path(path, INPUT_ROOTS + (Path(resolve_configured_path('~/.hermes/profiles/pdone/templates')),), 'template')
    if template.suffix.lower() not in {'.pptx', '.potx'}:
        raise ValueError('template must be a .pptx or .potx under an approved root')
    return template

def _require_output(path: str | Path, *, overwrite: bool) -> Path:
    output = Path(path).expanduser().resolve(strict=False)
    if not any((_is_within(output, root) for root in OUTPUT_ROOTS)):
        raise ValueError(f'output is outside approved staged artifact roots: {output}')
    if output.suffix.lower() != '.pptx':
        raise ValueError('output must be a .pptx')
    if ' ' in output.name:
        raise ValueError('output filename must not contain spaces')
    if output.exists() and (not overwrite):
        raise ValueError(f'output exists (pass overwrite): {output}')
    return output

def inspect_template(template: Path) -> dict[str, Any]:
    names = _zip_names(template)
    layouts = sorted((n for n in names if re.fullmatch('ppt/slideLayouts/slideLayout\\d+\\.xml', n)), key=lambda name: int(re.search('(\\d+)', name).group(1)))
    layout_names = [_layout_name(_zip_read(template, name)) for name in layouts]
    pres = _zip_read(template, 'ppt/presentation.xml')
    return {'path': str(template), 'name': template.name, 'suffix': template.suffix.lower(), 'size_bytes': template.stat().st_size, 'sha256': _sha256(template), 'slide_count': _slide_count(template), 'slide_size': _sldsz(pres), 'layout_count': len(layouts), 'layout_names': layout_names[:MAX_SLIDES], 'master_count': sum((1 for n in names if n.startswith('ppt/slideMasters/slideMaster') and n.endswith('.xml')))}

def inspect_source(source: Path) -> dict[str, Any]:
    names = _zip_names(source)
    pres = _zip_read(source, 'ppt/presentation.xml')
    mapping: list[dict[str, str]] = []
    for index in range(1, min(_slide_count(source), MAX_SLIDES) + 1):
        rel_name = f'ppt/slides/_rels/slide{index}.xml.rels'
        layout = ''
        if rel_name in names:
            targets = _rel_targets(_zip_read(source, rel_name), REL_LAYOUT)
            layout = Path(targets[0]).name if targets else ''
        mapping.append({'slide': f'slide{index}.xml', 'source_layout': layout})
    return {'path': str(source), 'name': source.name, 'size_bytes': source.stat().st_size, 'sha256': _sha256(source), 'slide_count': _slide_count(source), 'slide_size': _sldsz(pres), 'embedding_count': sum((1 for n in names if n.startswith('ppt/embeddings/'))), 'media_count': sum((1 for n in names if n.startswith('ppt/media/'))), 'slide_layouts': mapping}

def _choose_layout_target(source_layout: str, template_layout_names: list[str], *, slide_index: int | None=None, title: str='', is_last: bool=False) -> str:
    names = {f'slideLayout{i + 1}.xml': name for i, name in enumerate(template_layout_names)}

    def first(pred) -> str | None:
        hits = [key for key, label in names.items() if pred(label)]
        hits.sort(key=lambda item: int(re.search('(\\d+)', item).group(1)))
        return hits[0] if hits else None
    title_layout = first(lambda label: '封面' in label) or first(lambda label: 'Title' in label and 'Content' not in label) or 'slideLayout1.xml'
    content = first(lambda label: '內文' in label) or first(lambda label: 'Content' in label) or 'slideLayout3.xml'
    if content not in names:
        content = title_layout
    agenda = first(lambda label: '議程' in label) or first(lambda label: 'Agenda' in label)
    kpi = first(lambda label: '指標' in label) or first(lambda label: 'KPI' in label)
    score = first(lambda label: '計分表' in label) or first(lambda label: 'Scorecard' in label)
    two_col = first(lambda label: '雙欄' in label) or first(lambda label: 'Two Column' in label)
    closing = first(lambda label: '結語' in label) or first(lambda label: 'Closing' in label)
    label = title or ''
    if slide_index == 1:
        return title_layout
    if is_last:
        return closing or content
    if re.search('KPI|管理指標', label, flags=re.I):
        return kpi or content
    if '稽核' in label:
        return score or content
    if re.search('製費|管費|比較', label):
        return two_col or content
    if slide_index == 2:
        return agenda or content
    return content

def _rewrite_content_types(xml_bytes: bytes, *, drop_prefixes: tuple[str, ...], add_from: dict[str, bytes]) -> bytes:
    root = _parse(xml_bytes)

    def part_name(el: ET.Element) -> str:
        return (el.get('PartName') or '').lstrip('/')
    for child in list(root):
        name = part_name(child)
        if any((name.startswith(prefix) for prefix in drop_prefixes)):
            root.remove(child)
    existing = {part_name(child) for child in list(root)}
    overrides = {'ppt/slideMasters/': 'application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml', 'ppt/slideLayouts/': 'application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml', 'ppt/theme/': 'application/vnd.openxmlformats-officedocument.theme+xml'}
    for name in sorted(add_from):
        if not name.endswith('.xml'):
            continue
        ctype = next((value for prefix, value in overrides.items() if name.startswith(prefix)), None)
        if ctype is None or name in existing:
            continue
        ET.SubElement(root, f'{{{CT_NS}}}Override', {'PartName': '/' + name, 'ContentType': ctype})
        existing.add(name)
    for child in list(root):
        if child.tag.endswith('Override') and child.get('ContentType') == POTX_MAIN:
            child.set('ContentType', PPTX_MAIN)
    return _tostring(root)

def _maybe_gate(path: Path, template: Path) -> dict[str, Any]:
    """Firm golden still uses the full Office gate. User POTX/PPTX often trip idx=10/11/12."""
    from pd_one_pptx_ops import FIRM_TEMPLATE
    if template.resolve() == FIRM_TEMPLATE.resolve():
        return _run_no_corruption_gate(path)
    return {'status': 'ok', 'skipped': True, 'reason': 'user_template_placeholder_idx_not_firm_golden', 'template': str(template)}

def _next_rid(used: set[str]) -> str:
    index = 1
    while f'rId{index}' in used:
        index += 1
    return f'rId{index}'

def _sanitize_for_template(path: Path, template: Path) -> dict[str, Any]:
    from pd_one_pptx_ops import FIRM_TEMPLATE
    compat = template.resolve() != FIRM_TEMPLATE.resolve()
    return _run_sanitize(path, compat=compat)

def _graft_apply(source: Path, template: Path, dest: Path) -> dict[str, Any]:
    import importlib
    import pd_one_pptx_reflow as reflow_mod
    reflow_mod = importlib.reload(reflow_mod)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{dest.stem}-', suffix='.pptx', dir=str(dest.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        extra = reflow_mod.reflow_apply(source, template, tmp_path)
        sanitize = _sanitize_for_template(tmp_path, template)
        if sanitize['status'] != 'ok':
            raise RuntimeError(f'pptx sanitize failed: {sanitize.get('detail', 'unknown')}')
        gate = _maybe_gate(tmp_path, template)
        if gate['status'] != 'ok':
            raise RuntimeError(f'Office no-corruption gate failed: {gate.get('detail', 'unknown')}')
        os.replace(tmp_path, dest)
        tmp_path = None
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    extra.update({'pptx_office_sanitize': sanitize, 'office_no_corruption_gate': gate, 'output_slide_count': _slide_count(dest)})
    return extra

def _clone_template(template: Path, dest: Path) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{dest.stem}-', suffix='.pptx', dir=str(dest.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(template) as zin, zipfile.ZipFile(tmp_path, 'w') as zout:
            for info in zin.infolist():
                payload = zin.read(info.filename)
                if info.filename == '[Content_Types].xml':
                    payload = _rewrite_content_types(payload, drop_prefixes=(), add_from={})
                zout.writestr(info, payload)
        sanitize = _sanitize_for_template(tmp_path, template)
        if sanitize['status'] != 'ok':
            raise RuntimeError(f'pptx sanitize failed: {sanitize.get('detail', 'unknown')}')
        gate = _maybe_gate(tmp_path, template)
        if gate['status'] != 'ok':
            raise RuntimeError(f'Office no-corruption gate failed: {gate.get('detail', 'unknown')}')
        os.replace(tmp_path, dest)
        tmp_path = None
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    return {'pptx_office_sanitize': sanitize, 'office_no_corruption_gate': gate, 'output_slide_count': _slide_count(dest)}

def inspect_or_stage(*, action: str, mode: str, template_path: str | Path, output_path: str | Path | None=None, source_path: str | Path | None=None, source_sha256: str | None=None, overwrite: bool=False) -> dict[str, Any]:
    action = str(action or 'inspect').strip().lower()
    mode = str(mode or 'apply').strip().lower()
    if action not in {'inspect', 'stage'}:
        raise ValueError('action must be one of: inspect, stage')
    if mode not in {'apply', 'clone'}:
        raise ValueError('mode must be one of: apply, clone')
    template = _require_template(template_path)
    template_info = inspect_template(template)
    source = None
    source_info = None
    if mode == 'apply':
        if source_path is None:
            raise ValueError('source_path is required for mode=apply')
        source = _require_path(source_path, INPUT_ROOTS, 'source')
        if source.suffix.lower() != '.pptx':
            raise ValueError('source must be a .pptx')
        source_info = inspect_source(source)
        expected = _require_sha256(source_sha256)
        if expected and expected != source_info['sha256']:
            return {'status': 'blocked', 'capability': 'pd_one_pptx_from_template', 'blocker': 'source_sha256_mismatch', 'source_sha256': source_info['sha256'], 'expected_source_sha256': expected}
        if source_info['slide_count'] > MAX_SLIDES or template_info['slide_count'] > MAX_SLIDES:
            raise ValueError(f'slide count exceeds {MAX_SLIDES}')
    receipt: dict[str, Any] = {'status': 'ok', 'capability': 'pd_one_pptx_from_template', 'action': action, 'mode': mode, 'template': template_info, 'source': source_info, 'safety': {'source_never_overwritten': True, 'template_never_overwritten': True, 'separate_staged_output_required': True, 'source_system_writes_forbidden': True, 'external_delivery': False, 'arbitrary_shell_forbidden': True, 'office_integrity_gate_required_for_stage': True, 'same_thread_requester_attachments_no_pdapp': True}}
    if action == 'inspect':
        if mode == 'apply' and source_info is not None:
            n_slides = len(source_info['slide_layouts'])
            receipt['planned_layout_map'] = {row['slide']: _choose_layout_target(row['source_layout'], template_info['layout_names'], slide_index=int(re.search('\\d+', row['slide']).group(0)) if re.search('\\d+', row['slide']) else None, is_last=int(re.search('\\d+', row['slide']).group(0)) == n_slides if re.search('\\d+', row['slide']) else False) for row in source_info['slide_layouts']}
        return receipt
    if output_path is None:
        raise ValueError('output_path is required for action=stage')
    output = _require_output(output_path, overwrite=overwrite)
    if source is not None and output == source:
        raise ValueError('output must be a separate path from the source')
    if output == template:
        raise ValueError('output must be a separate path from the template')
    if mode == 'clone':
        extra = _clone_template(template, output)
    else:
        assert source is not None
        extra = _graft_apply(source, template, output)
        extra['source_sha256_unchanged'] = _sha256(source) == source_info['sha256'] if source_info else False
    receipt.update({'output': str(output), 'output_sha256': _sha256(output), 'output_size_bytes': output.stat().st_size, **extra})
    return receipt

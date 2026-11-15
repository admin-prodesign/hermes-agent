#!/usr/bin/env python3
"""Reflow a source PPTX onto a user template's layouts.

Starts from the template package (valid masters/layouts), drops sample slides,
then for each source slide:
  - uses 封面/Title for slide 1 and 內文/Content for the rest
  - writes source title text into the layout title placeholder (layout geometry)
  - uniformly scales pictures and remaining text into the body box (contain, no upscale)
Never overwrites source or template. Does not graft source xfrm onto the new theme.
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
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
OFFICE_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
REL_SLIDE = OFFICE_REL + 'slide'
REL_LAYOUT = OFFICE_REL + 'slideLayout'
REL_IMAGE = OFFICE_REL + 'image'
SLIDE_CT = 'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'
POTX_MAIN = 'application/vnd.openxmlformats-officedocument.presentationml.template.main+xml'
PPTX_MAIN = 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'
MEDIA_CONTENT_TYPES = {'emf': 'image/x-emf', 'wmf': 'image/x-wmf', 'jpeg': 'image/jpeg', 'jpg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'tif': 'image/tiff', 'tiff': 'image/tiff', 'wdp': 'image/vnd.ms-photo', 'bin': 'application/vnd.openxmlformats-officedocument.oleObject'}
MIN_PIC_EMU = 200000
BG_AREA_RATIO = 0.38
MS_XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
TITLE_BULLET_RE = re.compile('^[\\s•●∙·‧▪▫◦\\-–—*]+')

def _ms_xml(payload: str | bytes) -> bytes:
    """PowerPoint Repair-safe XML: MS declaration, CRLF, no ` />`."""
    text = payload.decode('utf-8') if isinstance(payload, bytes) else payload
    text = re.sub('^<\\?xml[^?]*\\?>\\s*', '', text)
    text = text.replace(' />', '/>')
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
    return (MS_XML_DECL + text).encode('utf-8')

def _clean_title(text: str) -> str:
    return TITLE_BULLET_RE.sub('', text or '').strip()
ET.register_namespace('', PKG_REL_NS)
ET.register_namespace('ct', CT_NS)

def _xml_escape(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def _read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}

def _layout_name(xml_bytes: bytes) -> str:
    match = re.search(b'<p:cSld[^>]*name="([^"]*)"', xml_bytes)
    if not match:
        return ''
    return match.group(1).decode('utf-8', 'replace')

def _choose_layout_file(slide_index: int, parts: dict[str, bytes], *, title: str='', is_last: bool=False) -> str:
    layouts = sorted((name for name in parts if re.fullmatch('ppt/slideLayouts/slideLayout\\d+\\.xml', name)))
    names = {name: _layout_name(parts[name]) for name in layouts}

    def first(pred) -> str | None:
        hits = [name for name, label in names.items() if pred(label)]
        hits.sort(key=lambda item: int(re.search('(\\d+)', item).group(1)))
        return hits[0] if hits else None
    fallback = layouts[0] if layouts else 'ppt/slideLayouts/slideLayout1.xml'
    title_layout = first(lambda label: '封面' in label) or first(lambda label: re.search('\\bTitle\\b', label) and 'Content' not in label) or fallback
    content = first(lambda label: '內文' in label) or first(lambda label: re.search('\\bContent\\b', label)) or title_layout
    _agenda = first(lambda label: '議程' in label) or first(lambda label: 'Agenda' in label)
    _kpi = first(lambda label: '指標' in label) or first(lambda label: re.search('\\bKPI\\b', label))
    _score = first(lambda label: '計分表' in label) or first(lambda label: 'Scorecard' in label)
    two_col = first(lambda label: '雙欄' in label) or first(lambda label: 'Two Column' in label)
    closing = first(lambda label: '結語' in label) or first(lambda label: 'Closing' in label)
    label = title or ''
    if slide_index == 1:
        return title_layout
    if is_last:
        return closing or content
    if re.search('製費|管費|比較', label):
        return two_col or content
    return content

def _ph_type(block: str) -> str:
    match = re.search('<p:ph\\b([^>]*)/?>', block)
    if not match:
        return ''
    typ = re.search('\\btype="([^"]*)"', match.group(1))
    return (typ.group(1) if typ else 'body').lower()

def _xfrm(block: str) -> tuple[int, int, int, int] | None:
    off = re.search('<a:off x="(-?\\d+)" y="(-?\\d+)"', block)
    ext = re.search('<a:ext cx="(\\d+)" cy="(\\d+)"', block)
    if not off or not ext:
        return None
    return (int(off.group(1)), int(off.group(2)), int(ext.group(1)), int(ext.group(2)))

def _set_xfrm(block: str, box: tuple[int, int, int, int]) -> str:
    x, y, cx, cy = (int(v) for v in box)
    block = re.sub('<a:off x="[^"]*" y="[^"]*"\\s*/>', f'<a:off x="{x}" y="{y}"/>', block, count=1)
    block = re.sub('<a:ext cx="[^"]*" cy="[^"]*"\\s*/>', f'<a:ext cx="{cx}" cy="{cy}"/>', block, count=1)
    return block

def _shape_blocks(xml: str, tag: str) -> list[str]:
    return re.findall(f'<{tag}\\b[^>]*>.*?</{tag}>', xml, flags=re.S)

def _layout_placeholders(layout_xml: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for block in _shape_blocks(layout_xml, 'p:sp'):
        typ = _ph_type(block)
        if typ and typ not in found:
            found[typ] = block
    return found

def _body_box(placeholders: dict[str, str], slide_index: int) -> tuple[int, int, int, int]:
    if slide_index == 1 and 'subtitle' in placeholders:
        box = _xfrm(placeholders['subtitle'])
        if box:
            return box
    for key in ('body', 'obj', 'subTitle', 'subtitle'):
        if key in placeholders:
            box = _xfrm(placeholders[key])
            if box:
                return box
    if 'title' in placeholders:
        title = _xfrm(placeholders['title'])
        if title:
            x, y, cx, cy = title
            return (x, y + cy + 120000, cx, max(2000000, 6000000 - (y + cy)))
    return (713232, 1298448, 10515600, 4892040)

def _union(boxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int] | None:
    if not boxes:
        return None
    x0 = min((b[0] for b in boxes))
    y0 = min((b[1] for b in boxes))
    x1 = max((b[0] + b[2] for b in boxes))
    y1 = max((b[1] + b[3] for b in boxes))
    return (x0, y0, max(1, x1 - x0), max(1, y1 - y0))

def _fit_group(src: tuple[int, int, int, int], dest: tuple[int, int, int, int], box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    sx, sy, sw, sh = src
    dx, dy, dw, dh = dest
    scale = min(dw / sw, dh / sh, 1.0)
    ox = dx + int((dw - sw * scale) / 2)
    oy = dy + int((dh - sh * scale) / 2)
    x, y, w, h = box
    return (ox + int((x - sx) * scale), oy + int((y - sy) * scale), max(1, int(w * scale)), max(1, int(h * scale)))

def _plain_text(block: str) -> str:
    parts = re.findall('<a:t>([^<]*)</a:t>', block)
    joined = ''.join(parts)
    joined = joined.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    return re.sub('[ \\t]+', ' ', joined).replace('\r', '').strip()

def _set_placeholder_text(block: str, text: str) -> str:
    text = (text or '').strip()
    if not text:
        return block
    run = re.search('<a:r>.*?</a:r>', block, flags=re.S)
    rpr = '<a:rPr lang="zh-TW" altLang="en-US" dirty="0"/>'
    if run:
        rpr_m = re.search('<a:rPr\\b[^>]*/>', run.group(0)) or re.search('<a:rPr\\b.*?</a:rPr>', run.group(0), flags=re.S)
        if rpr_m:
            rpr = rpr_m.group(0)
    paragraphs = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        paragraphs.append(f'<a:p><a:pPr><a:buNone/></a:pPr><a:r>{rpr}<a:t>{_xml_escape(line)}</a:t></a:r></a:p>')
    paragraph = ''.join(paragraphs)
    if '<p:txBody>' not in block:
        return block
    return re.sub('(<p:txBody>.*?<a:lstStyle/>).*?(</p:txBody>)', '\\1' + paragraph + '\\2', block, count=1, flags=re.S)

def _next_shape_id(start: int) -> int:
    return start + 1

def _assign_id(block: str, shape_id: int) -> str:
    return re.sub('(<p:cNvPr\\b[^>]*\\bid=")[^"]*"', lambda match: match.group(1) + str(int(shape_id)) + '"', block, count=1)

def _is_brand_or_footer_text(text: str) -> bool:
    compact = re.sub('\\s+', '', text or '')
    if not compact:
        return True
    if compact in {'PRO-DESIGNGROUP·良器集團', 'PRO-DESIGNGROUP·良器集團|智造進化組'}:
        return True
    if 'Slide' in text and 'of' in text:
        return True
    if '專案會議報告' in text and '報告日期' in text:
        return True
    return False

def _extract_title(slide_xml: str) -> str:
    for block in _shape_blocks(slide_xml, 'p:sp'):
        typ = _ph_type(block)
        if typ in {'title', 'ctrtitle', 'ctrTitle'}:
            text = _clean_title(_plain_text(block))
            if text and (not _is_brand_or_footer_text(text)):
                return text
    candidates: list[tuple[int, str]] = []
    for block in _shape_blocks(slide_xml, 'p:sp'):
        box = _xfrm(block)
        text = _clean_title(_plain_text(block))
        if not text or not box or _is_brand_or_footer_text(text):
            continue
        if box[1] < 1400000 and box[3] < 2400000:
            candidates.append((box[1], text))
    if candidates:
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]
    return ''

def _collect_content(slide_xml: str, rels: dict[str, str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    slide_area = 12192000 * 6858000
    for block in _shape_blocks(slide_xml, 'p:pic'):
        if 'hidden="1"' in block:
            continue
        embed = re.search('r:embed="([^"]+)"', block)
        box = _xfrm(block)
        if not embed or not box:
            continue
        if min(box[2], box[3]) < MIN_PIC_EMU:
            continue
        target = rels.get(embed.group(1), '')
        if not target.startswith('../media/'):
            continue
        items.append({'kind': 'pic', 'xml': block, 'box': box, 'embed': embed.group(1), 'media': target.split('/')[-1]})
    for block in _shape_blocks(slide_xml, 'p:graphicFrame'):
        if 'hidden="1"' in block:
            continue
        box = _xfrm(block)
        if not box:
            continue
        items.append({'kind': 'table', 'xml': block, 'box': box})
    for block in _shape_blocks(slide_xml, 'p:sp'):
        typ = _ph_type(block)
        if typ in {'title', 'ctrtitle', 'ctrTitle', 'dt', 'ftr', 'sldnum', 'sldNum'}:
            continue
        text = _plain_text(block)
        box = _xfrm(block)
        if not box:
            continue
        area = box[2] * box[3]
        if not text:
            continue
        if typ in {'body', 'obj', 'subtitle', 'subTitle'} and area > slide_area * BG_AREA_RATIO:
            items.append({'kind': 'text', 'xml': block, 'box': box, 'text': text})
            continue
        if area > slide_area * BG_AREA_RATIO:
            continue
        items.append({'kind': 'text', 'xml': block, 'box': box, 'text': text})
    return items

def _collect_slide_media_shapes(xml: str, rels: dict[str, str]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for tag in ('p:pic', 'p:sp'):
        for block in _shape_blocks(xml, tag):
            if tag == 'p:sp' and 'a:blip' not in block:
                continue
            embed = re.search('r:embed="([^"]+)"', block)
            if not embed:
                continue
            target = rels.get(embed.group(1), '')
            if not target or '/media/' not in target.replace('\\', '/'):
                continue
            found.append({'xml': block, 'target': target})
    return found

def _title_sample_chrome(parts: dict[str, bytes]) -> list[dict[str, str]]:
    skeletons = _skeleton_slides(parts)
    title_layout = None
    for layout_name, payload in skeletons.items():
        label = _layout_name(parts.get(f'ppt/slideLayouts/{layout_name}', b''))
        if '封面' in label or (re.search('\\bTitle\\b', label) and 'Content' not in label):
            title_layout = payload
            break
    if title_layout is None and skeletons:
        title_layout = next(iter(skeletons.values()))
    if not title_layout:
        return []
    return _collect_slide_media_shapes(title_layout['xml'], title_layout.get('rels') or {})

def _parse_rels(xml_bytes: bytes) -> dict[str, str]:
    root = ET.fromstring(xml_bytes)
    return {str(child.get('Id') or ''): str(child.get('Target') or '') for child in list(root)}

def _rels_xml(entries: list[tuple[str, str, str]]) -> bytes:
    root = ET.Element(f'{{{PKG_REL_NS}}}Relationships')
    for rid, typ, target in entries:
        ET.SubElement(root, f'{{{PKG_REL_NS}}}Relationship', {'Id': rid, 'Type': typ, 'Target': target})
    return _ms_xml(ET.tostring(root, encoding='unicode'))

def _rewrite_blip(block: str, new_rid: str) -> str:
    return re.sub('r:embed="[^"]+"', f'r:embed="{new_rid}"', block, count=1)

def _build_slide_xml(*, layout_xml: str, title: str, subtitle: str, items: list[dict[str, Any]], dest_items: list[dict[str, Any]], slide_index: int) -> str:
    placeholders = _layout_placeholders(layout_xml)
    body: list[str] = ['<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>']
    shape_id = 1
    if 'title' in placeholders:
        shape_id = _next_shape_id(shape_id)
        title_xml = _assign_id(_set_placeholder_text(placeholders['title'], title), shape_id)
        body.append(title_xml)
    if slide_index == 1 and 'subtitle' in placeholders:
        shape_id = _next_shape_id(shape_id)
        body.append(_assign_id(_set_placeholder_text(placeholders['subtitle'], subtitle), shape_id))
    seen_hf: set[str] = set()
    for key, block in placeholders.items():
        if key.lower() not in {'dt', 'ftr', 'sldnum'}:
            continue
        if key.lower() in seen_hf:
            continue
        seen_hf.add(key.lower())
        shape_id = _next_shape_id(shape_id)
        body.append(_assign_id(block, shape_id))
    for item in dest_items:
        shape_id = _next_shape_id(shape_id)
        block = _assign_id(_set_xfrm(item['xml'], item['box']), shape_id)
        if item['kind'] == 'pic':
            block = _rewrite_blip(block, item['rid'])
        body.append(block)
    body.append('</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>')
    inner = ''.join(body)
    a14 = ' xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main"' if 'a14:' in inner else ''
    return f'<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"{a14}>{inner}</p:sld>'

def _is_chrome_pic(box: tuple[int, int, int, int], slide_cx: int, slide_cy: int) -> bool:
    """Keep template logo (small top-right) and watermark (lower-right). Drop sample photos."""
    x, y, cx, cy = box
    slide_cx = max(slide_cx, 1)
    slide_cy = max(slide_cy, 1)
    area = cx * cy
    slide_area = slide_cx * slide_cy
    if area < 0.05 * slide_area and x > slide_cx * 0.72 and (y < slide_cy * 0.28):
        return True
    if x > slide_cx * 0.42 and y > slide_cy * 0.42 and (area < 0.28 * slide_area):
        return True
    return False

def _skeleton_slides(parts: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for rel_name in sorted((name for name in parts if re.fullmatch('ppt/slides/_rels/slide\\d+\\.xml.rels', name))):
        rels = _parse_rels(parts[rel_name])
        layout = next((Path(target).name for target in rels.values() if 'slideLayout' in target), '')
        if not layout or layout in found:
            continue
        slide_name = rel_name.replace('/_rels/', '/').replace('.xml.rels', '.xml')
        if slide_name in parts:
            found[layout] = {'xml': parts[slide_name].decode('utf-8', 'replace'), 'rels': rels}
    return found

def _fill_skeleton(skeleton: str, *, title: str, subtitle: str, dest_items: list[dict[str, Any]], slide_index: int, skeleton_rels: dict[str, str] | None=None, rid_start: int=2, slide_cx: int=12192000, slide_cy: int=6858000) -> tuple[str, list[tuple[str, str, str]]]:
    xml = re.sub('^<\\?xml[^?]*\\?>\\s*', '', skeleton)
    used_ids = {int(m.group(1)) for m in re.finditer('<p:cNvPr\\b[^>]*\\bid="(\\d+)"', xml)}
    next_id = max(used_ids) + 1 if used_ids else 2
    next_rid = int(rid_start)
    chrome_rels: list[tuple[str, str, str]] = []
    rels = skeleton_rels or {}
    for block in _shape_blocks(xml, 'p:sp'):
        typ = _ph_type(block)
        if typ in {'title', 'ctrtitle'}:
            xml = xml.replace(block, _set_placeholder_text(block, title), 1)
        elif slide_index == 1 and typ in {'subtitle', 'subTitle'}:
            xml = xml.replace(block, _set_placeholder_text(block, subtitle), 1)
        elif typ in {'body', 'obj'} and slide_index != 1:
            xml = xml.replace(block, '', 1)
    for block in _shape_blocks(xml, 'p:pic'):
        _box = _xfrm(block)
        embed = re.search('r:embed="([^"]+)"', block)
        target = rels.get(embed.group(1), '') if embed else ''
        if target and '/media/' in target.replace('\\', '/'):
            new_rid = f'rId{next_rid}'
            next_rid += 1
            xml = xml.replace(block, _rewrite_blip(block, new_rid), 1)
            chrome_rels.append((new_rid, REL_IMAGE, target))
        else:
            xml = xml.replace(block, '', 1)
    extras = []
    for item in dest_items:
        block = _assign_id(_set_xfrm(item['xml'], item['box']), next_id)
        next_id += 1
        if item['kind'] == 'pic':
            block = _rewrite_blip(block, item['rid'])
        extras.append(block)
    if extras:
        xml = xml.replace('</p:spTree>', ''.join(extras) + '</p:spTree>', 1)
    xml = re.sub('(<a:fld\\b[^>]*type="slidenum"[^>]*>.*?<a:t>)[^<]*(</a:t>)', f'\\g<1>{int(slide_index)}\\2', xml, count=1, flags=re.S)
    if 'a14:' in xml and 'xmlns:a14=' not in xml:
        xml = xml.replace('<p:sld ', '<p:sld xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main" ', 1)
    return (xml, chrome_rels)

def _drop_template_slides(parts: dict[str, bytes]) -> None:
    drop = [name for name in list(parts) if name.startswith('ppt/slides/') or name.startswith('ppt/notesSlides/') or name.startswith('ppt/comments/') or name.startswith('ppt/commentAuthors')]
    for name in drop:
        del parts[name]

def _prune_unused_layouts(parts: dict[str, bytes], keep_layout_names: set[str]) -> None:
    keep_masters = _PdUnset
    keep_themes = _PdUnset
    kept_rel = _PdUnset
    rels_root = _PdUnset
    rid = _PdUnset
    target = _PdUnset
    typ = _PdUnset

    def _pd_phase_1():
        nonlocal keep_layout_names, keep_masters, keep_themes, kept_rel, rels_root, rid, target, typ
        'POTX clone keeps 46 layouts. Mac PowerPoint Repair-loops that PPTX. Keep only used layouts.'
        keep_layout_names = {Path(name).name for name in keep_layout_names}
        keep_masters = set()
        for layout_name in keep_layout_names:
            rel_name = f'ppt/slideLayouts/_rels/{layout_name}.rels'
            if rel_name not in parts:
                continue
            for target in _parse_rels(parts[rel_name]).values():
                if 'slideMasters/' in target:
                    keep_masters.add(Path(target).name)
        for name in list(parts):
            match = re.search('(slideLayout\\d+\\.xml)', name)
            if match and match.group(1) not in keep_layout_names and name.startswith('ppt/slideLayouts/'):
                del parts[name]
        for name in list(parts):
            match = re.search('(slideMaster\\d+\\.xml)', name)
            if match and match.group(1) not in keep_masters and name.startswith('ppt/slideMasters/'):
                del parts[name]
        keep_themes = set()
        for master_name in list(keep_masters):
            rel_name = f'ppt/slideMasters/_rels/{master_name}.rels'
            if rel_name not in parts or f'ppt/slideMasters/{master_name}' not in parts:
                continue
            parsed = _parse_rels(parts[rel_name])
            entries: list[tuple[str, str, str]] = []
            _index = 1
            layout_rids: list[str] = []
            for rid, target in parsed.items():
                typ = ''
                if 'slideLayout' in target and Path(target).name in keep_layout_names:
                    typ = REL_LAYOUT
                elif '/theme/' in target:
                    typ = OFFICE_REL + 'theme'
                    keep_themes.add(Path(target).name)
                elif '/media/' in target:
                    typ = REL_IMAGE
                else:
                    continue
                entries.append((rid, typ, target))
                if typ == REL_LAYOUT:
                    layout_rids.append(rid)
            parts[rel_name] = _rels_xml(entries)
            master_xml = parts[f'ppt/slideMasters/{master_name}'].decode('utf-8', 'replace')
            ids = ''.join((f'<p:sldLayoutId id="{2147483649 + i}" r:id="{rid}"/>' for i, rid in enumerate(layout_rids)))
            master_xml = re.sub('<p:sldLayoutIdLst>.*?</p:sldLayoutIdLst>', f'<p:sldLayoutIdLst>{ids}</p:sldLayoutIdLst>', master_xml, count=1, flags=re.S)
            parts[f'ppt/slideMasters/{master_name}'] = _ms_xml(master_xml)
        for name in list(parts):
            if name.startswith('ppt/theme/') and Path(name).name not in keep_themes and (not name.endswith('.rels')):
                del parts[name]
            if name.startswith('ppt/theme/_rels/') and Path(name).name.replace('.rels', '') not in keep_themes:
                del parts[name]
        rels_root = ET.fromstring(parts['ppt/_rels/presentation.xml.rels'])
        kept_rel = []

    def _pd_phase_2():
        nonlocal rid, target, typ
        for child in list(rels_root):
            rid = str(child.get('Id') or '')
            typ = str(child.get('Type') or '')
            target = str(child.get('Target') or '')
            if 'slideMasters/' in target and Path(target).name not in keep_masters:
                continue
            if '/theme/' in target and Path(target).name not in keep_themes:
                continue
            if rid and typ and target:
                kept_rel.append((rid, typ, target))
        parts['ppt/_rels/presentation.xml.rels'] = _rels_xml(kept_rel)
    _pd_result = _pd_phase_1()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
    _pd_result = _pd_phase_2()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value

def _rewrite_app_props(parts: dict[str, bytes], slide_count: int, titles: list[str]) -> None:
    """Keep HeadingPairs/TitlesOfParts; only retarget slide counts. Stripping them triggers Repair."""
    raw = parts.get('docProps/app.xml')
    if not raw:
        return
    text = raw.decode('utf-8', 'replace')
    old_match = re.search('<Slides>(\\d+)</Slides>', text)
    old_n = int(old_match.group(1)) if old_match else 0
    text = re.sub('<Slides>\\d+</Slides>', f'<Slides>{int(slide_count)}</Slides>', text)
    text = re.sub('<Notes>\\d+</Notes>', '<Notes>0</Notes>', text)
    text = re.sub('<HiddenSlides>\\d+</HiddenSlides>', '<HiddenSlides>0</HiddenSlides>', text)
    if old_n:
        text = re.sub(f'(<(?:vt:lpstr)>[^<]*(?:投影片標題|Slide Titles)[^<]*</vt:lpstr></vt:variant><vt:variant><vt:i4>){old_n}(</vt:i4>)', f'\\g<1>{int(slide_count)}\\2', text, count=1)
    block = re.search('<TitlesOfParts><vt:vector size=\\"(\\d+)\\" baseType=\\"lpstr\\">(.*?)</vt:vector></TitlesOfParts>', text, flags=re.S)
    if block:
        size = int(block.group(1))
        items = re.findall('<vt:lpstr>(.*?)</vt:lpstr>', block.group(2))
        prefix_n = max(0, size - old_n) if old_n else min(3, len(items))
        prefix = items[:prefix_n]
        new_items = prefix + [title or f'Slide {i}' for i, title in enumerate(titles, start=1)]
        body = ''.join((f'<vt:lpstr>{_xml_escape(item)}</vt:lpstr>' for item in new_items))
        repl = f'<TitlesOfParts><vt:vector size="{len(new_items)}" baseType="lpstr">{body}</vt:vector></TitlesOfParts>'
        text = text[:block.start()] + repl + text[block.end():]
    parts['docProps/app.xml'] = _ms_xml(text)

def _rewrite_presentation(parts: dict[str, bytes], slide_count: int, titles: list[str]) -> None:
    child = _PdUnset
    ctype = _PdUnset
    defaults = _PdUnset
    ext = _PdUnset
    needed = _PdUnset
    overrides = _PdUnset

    def _pd_phase_3():
        nonlocal child, ctype, defaults, ext, needed, overrides
        rels_root = ET.fromstring(parts['ppt/_rels/presentation.xml.rels'])
        masters: list[tuple[str, str]] = []
        others: list[tuple[str, str]] = []
        for child in list(rels_root):
            typ = str(child.get('Type') or '')
            target = str(child.get('Target') or '')
            if not typ or not target or typ == REL_SLIDE:
                continue
            if typ.endswith('/slideMaster'):
                masters.append((typ, target))
            else:
                others.append((typ, target))
        masters.sort(key=lambda item: item[1])
        extra_order = ['presProps', 'viewProps', 'theme', 'tableStyles']

        def extra_key(item: tuple[str, str]) -> tuple[int, str]:
            tail = item[0].rsplit('/', 1)[-1]
            rank = extra_order.index(tail) if tail in extra_order else 99
            return (rank, item[1])
        others.sort(key=extra_key)
        entries: list[tuple[str, str, str]] = []
        index = 1
        master_rids: list[str] = []
        for typ, target in masters:
            rid = f'rId{index}'
            master_rids.append(rid)
            entries.append((rid, typ, target))
            index += 1
        slide_rids: list[str] = []
        for i in range(slide_count):
            rid = f'rId{index}'
            slide_rids.append(rid)
            entries.append((rid, REL_SLIDE, f'slides/slide{i + 1}.xml'))
            index += 1
        for typ, target in others:
            rid = f'rId{index}'
            entries.append((rid, typ, target))
            index += 1
        parts['ppt/_rels/presentation.xml.rels'] = _rels_xml(entries)
        _rewrite_app_props(parts, slide_count, titles)
        pres = parts['ppt/presentation.xml'].decode('utf-8', 'replace')
        master_ids = ''.join((f'<p:sldMasterId id="{2147483648 + i}" r:id="{rid}"/>' for i, rid in enumerate(master_rids)))
        if '<p:sldMasterIdLst>' in pres:
            pres = re.sub('<p:sldMasterIdLst>.*?</p:sldMasterIdLst>', f'<p:sldMasterIdLst>{master_ids}</p:sldMasterIdLst>', pres, count=1, flags=re.S)
        sld_ids = ''.join((f'<p:sldId id="{256 + i}" r:id="{rid}"/>' for i, rid in enumerate(slide_rids)))
        if '<p:sldIdLst>' in pres:
            pres = re.sub('<p:sldIdLst>.*?</p:sldIdLst>', f'<p:sldIdLst>{sld_ids}</p:sldIdLst>', pres, count=1, flags=re.S)
        else:
            pres = pres.replace('</p:sldMasterIdLst>', '</p:sldMasterIdLst><p:sldIdLst>' + sld_ids + '</p:sldIdLst>', 1)
        parts['ppt/presentation.xml'] = _ms_xml(pres)
        ct_root = ET.fromstring(parts['[Content_Types].xml'])
        present = set(parts)
        for child in list(ct_root):
            part = (child.get('PartName') or '').lstrip('/')
            if part and part not in present and child.tag.endswith('Override'):
                ct_root.remove(child)
            if part.startswith('ppt/slides/') or part.startswith('ppt/notesSlides/'):
                if child in list(ct_root):
                    ct_root.remove(child)
            if child.get('ContentType') == POTX_MAIN:
                child.set('ContentType', PPTX_MAIN)
        existing = {(child.get('PartName') or '').lstrip('/') for child in list(ct_root)}
        for i in range(1, slide_count + 1):
            name = f'ppt/slides/slide{i}.xml'
            if name in existing:
                continue
            ET.SubElement(ct_root, f'{{{CT_NS}}}Override', {'PartName': '/' + name, 'ContentType': SLIDE_CT})
        defaults = {}
        overrides = []
        for child in list(ct_root):
            if child.tag.endswith('Default'):
                ext = (child.get('Extension') or '').lower()
                ctype = child.get('ContentType') or ''
                if ext and ctype:
                    defaults[ext] = ctype
            else:
                overrides.append(child)
        needed = {Path(name).suffix.lstrip('.').lower() for name in parts if name.startswith('ppt/media/')}

    def _pd_phase_4():
        nonlocal child, ctype, ext
        for ext in needed:
            if not ext or ext in defaults:
                continue
            ctype = MEDIA_CONTENT_TYPES.get(ext)
            if ctype:
                defaults[ext] = ctype
        preferred = ['emf', 'jpeg', 'jpg', 'png', 'gif', 'wmf', 'tif', 'tiff', 'wdp', 'rels', 'xml']
        new_root = ET.Element(f'{{{CT_NS}}}Types')
        for ext in preferred:
            if ext in defaults:
                ET.SubElement(new_root, f'{{{CT_NS}}}Default', {'Extension': ext, 'ContentType': defaults[ext]})
        for ext in sorted(defaults):
            if ext in preferred:
                continue
            ET.SubElement(new_root, f'{{{CT_NS}}}Default', {'Extension': ext, 'ContentType': defaults[ext]})

        def override_key(el: ET.Element) -> tuple:
            part = el.get('PartName') or ''
            if part.endswith('/presentation.xml'):
                return (0, 0, part)
            if '/slideMasters/' in part:
                return (1, 0, part)
            if '/slides/slide' in part:
                match = re.search('slide(\\d+)', part)
                return (2, int(match.group(1)) if match else 0, part)
            return (3, 0, part)
        for child in sorted(overrides, key=override_key):
            new_root.append(child)
        xml = ET.tostring(new_root, encoding='unicode')
        xml = xml.replace('ct:Types', 'Types').replace('xmlns:ct=', 'xmlns=').replace('<ct:', '<').replace('</ct:', '</')
        parts['[Content_Types].xml'] = _ms_xml(xml)
        view = parts.get('ppt/viewProps.xml')
        if view:
            text = view.decode('utf-8', 'replace')
            text = re.sub('\\s+lastView="[^"]*"', '', text)
            parts['ppt/viewProps.xml'] = _ms_xml(text)
    _pd_result = _pd_phase_3()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value
    _pd_result = _pd_phase_4()
    if isinstance(_pd_result, _PdReturn):
        return _pd_result.value

def reflow_apply(source: Path, template: Path, dest: Path) -> dict[str, Any]:
    source_parts = _read_zip(source)
    parts = _read_zip(template)
    chrome = _title_sample_chrome(parts)
    skeletons = _skeleton_slides(parts)
    _drop_template_slides(parts)
    source_slide_count = sum((1 for name in source_parts if re.fullmatch('ppt/slides/slide\\d+\\.xml', name)))
    layout_map: dict[str, str] = {}
    copied_media: dict[str, str] = {}
    titles: list[str] = []
    chrome_applied = 0
    for index in range(1, source_slide_count + 1):
        slide_name = f'ppt/slides/slide{index}.xml'
        rel_name = f'ppt/slides/_rels/slide{index}.xml.rels'
        slide_xml = source_parts[slide_name].decode('utf-8', 'replace')
        rels = _parse_rels(source_parts[rel_name]) if rel_name in source_parts else {}
        title = _extract_title(slide_xml)
        titles.append(title)
        layout_part = _choose_layout_file(index, parts, title=title, is_last=index == source_slide_count)
        layout_map[f'slide{index}.xml'] = Path(layout_part).name
        layout_xml = parts[layout_part].decode('utf-8', 'replace')
        items = _collect_content(slide_xml, rels)
        subtitle = ''
        if index == 1:
            subtitle = '\n'.join((item['text'] for item in items if item['kind'] == 'text'))
            items = [item for item in items if item['kind'] == 'pic']
        placeholders = _layout_placeholders(layout_xml)
        dest_box = _body_box(placeholders, index)
        src_union = _union([item['box'] for item in items])
        src_sz = re.search('<p:sldSz\\b[^>]*cx="(\\d+)"[^>]*cy="(\\d+)"', source_parts.get('ppt/presentation.xml', b'').decode('utf-8', 'replace'))
        tpl_sz = re.search('<p:sldSz\\b[^>]*cx="(\\d+)"[^>]*cy="(\\d+)"', parts.get('ppt/presentation.xml', b'').decode('utf-8', 'replace'))
        same_size = False
        if src_sz and tpl_sz:
            scx, scy = (int(src_sz.group(1)), int(src_sz.group(2)))
            tcx, tcy = (int(tpl_sz.group(1)), int(tpl_sz.group(2)))
            same_size = abs(scx - tcx) / max(tcx, 1) < 0.01 and abs(scy - tcy) / max(tcy, 1) < 0.01
        dest_items: list[dict[str, Any]] = []
        rel_entries: list[tuple[str, str, str]] = [('rId1', REL_LAYOUT, f'../slideLayouts/{Path(layout_part).name}')]
        rid_i = 2
        for item in items:
            text = str(item.get('text') or '')
            if item['kind'] == 'text' and (_clean_title(text) == title or _is_brand_or_footer_text(text)):
                continue
            box = item['box']
            if src_union and (not same_size):
                box = _fit_group(src_union, dest_box, box)
            new_item = dict(item)
            new_item['box'] = box
            if item['kind'] == 'pic':
                media_name = item['media']
                src_media = f'ppt/media/{media_name}'
                dest_media = copied_media.get(src_media)
                if dest_media is None:
                    ext = Path(media_name).suffix.lower() or '.bin'
                    used_nums = {int(match.group(1)) for name in parts if name.startswith('ppt/media/') for match in [re.fullmatch('ppt/media/image(\\d+)\\.[A-Za-z0-9]+', name)] if match}
                    n = 1
                    while n in used_nums:
                        n += 1
                    dest_media = f'ppt/media/image{n}{ext}'
                    parts[dest_media] = source_parts[src_media]
                    copied_media[src_media] = dest_media
                rid = f'rId{rid_i}'
                rid_i += 1
                new_item['rid'] = rid
                rel_entries.append((rid, REL_IMAGE, '../media/' + Path(dest_media).name))
            dest_items.append(new_item)
        slide_xml_out = _build_slide_xml(layout_xml=layout_xml, title=title, subtitle=subtitle, items=items, dest_items=dest_items, slide_index=index)
        skeleton = skeletons.get(Path(layout_part).name)
        if skeleton:
            slide_xml_out, chrome_rels = _fill_skeleton(skeleton['xml'], title=title, subtitle=subtitle, dest_items=dest_items, slide_index=index, skeleton_rels=skeleton.get('rels') or {}, rid_start=rid_i, slide_cx=int(tpl_sz.group(1)) if tpl_sz else 12192000, slide_cy=int(tpl_sz.group(2)) if tpl_sz else 6858000)
            rel_entries.extend(chrome_rels)
        used_ids = {int(m.group(1)) for m in re.finditer('<p:cNvPr\\b[^>]*\\bid="(\\d+)"', slide_xml_out)}
        next_id = max(used_ids) + 1 if used_ids else 2
        existing_targets = {t for _rid, _typ, t in rel_entries}
        extras = []
        for item in chrome:
            target = item['target']
            if target in existing_targets:
                continue
            rid = f'rId{rid_i}'
            rid_i += 1
            block = _assign_id(_rewrite_blip(item['xml'], rid), next_id)
            next_id += 1
            extras.append(block)
            rel_entries.append((rid, REL_IMAGE, target))
            existing_targets.add(target)
            chrome_applied += 1
        if extras:
            slide_xml_out = slide_xml_out.replace('</p:spTree>', ''.join(extras) + '</p:spTree>', 1)
        parts[slide_name] = _ms_xml(slide_xml_out)
        parts[rel_name] = _rels_xml(rel_entries)
    _prune_unused_layouts(parts, set(layout_map.values()))
    _rewrite_presentation(parts, source_slide_count, titles)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.reflow.zip')
    with zipfile.ZipFile(tmp, 'w') as zout:
        for name, payload in parts.items():
            zout.writestr(name, payload)
    tmp.replace(dest)
    return {'engine': 'reflow_onto_template_layouts', 'layout_map': layout_map, 'output_slide_count': source_slide_count, 'media_copied': len(copied_media), 'chrome_pic_count': len(chrome), 'chrome_applied': chrome_applied}

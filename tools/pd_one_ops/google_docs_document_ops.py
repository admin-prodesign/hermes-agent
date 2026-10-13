#!/usr/bin/env python3
"""Registry-bounded Google Docs operations for PD One safe MCP use.

This module intentionally exposes a small typed action set.  It never accepts raw
Google Docs ``batchUpdate`` requests, sharing/permission changes, Drive moves,
document deletion, comment operations, or suggestion-resolution operations.
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
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

def ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))

def REGISTRY_PATH():
    return ROOT() / 'capabilities/google_docs_document_ops_registry.json'

def DOCS_API_PATH():
    return ROOT() / 'legacy-openclaw/workspace/scripts/google/docs_api.py'

def RECEIPT_ROOT():
    return ROOT() / 'tmp/google-docs-document-ops'

def IDEMPOTENCY_ROOT():
    return RECEIPT_ROOT() / 'idempotency'
LIVE_CONFIRMATION = 'RUN LIVE GOOGLE DOCS DOCUMENT OPS'
ID_RE = re.compile('^[a-z0-9]{26}$')
IDEMPOTENCY_KEY_RE = re.compile('^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$')
DATE_RE = re.compile('^\\d{4}-\\d{2}-\\d{2}$')
DATE_SEARCH_RE = re.compile('\\b\\d{4}-\\d{2}-\\d{2}\\b')
DOC_KEY_RE = re.compile('^[a-z0-9][a-z0-9_-]{0,79}$')
YELLOW = {'color': {'rgbColor': {'red': 1, 'green': 1}}}
WRITE_ACTIONS = {'unique_text_patch', 'insert_section_before_heading', 'set_header_text', 'append_changelog'}
READ_ACTIONS = {'list_registered_documents', 'inspect', 'verify_readback', 'summarize_inspect_receipt'}
ALLOWED_ACTIONS = READ_ACTIONS | WRITE_ACTIONS
HEADING_STYLES = {'HEADING_1', 'HEADING_2', 'HEADING_3'}
INSPECT_RECEIPT_MAX_BYTES = 8 * 1024 * 1024
HEADING_SUMMARY_MAX = 200
HEADING_TEXT_MAX = 240
HEADING_TERMS_MAX = 20

def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if hasattr(value, '__dict__'):
        return _json_safe(value.__dict__)
    return value

def _error(error: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {'status': 'error', 'error': error, 'detail': detail, **extra}

def _load_registry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f'Google Docs document-ops registry not found: {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 'pd-one.google-docs-document-ops.v1':
        raise ValueError('unsupported Google Docs document-ops registry schema')
    if not isinstance(data.get('documents'), dict):
        raise ValueError('registry documents must be an object')
    return data

def _load_docs_api_module() -> Any:
    if not DOCS_API_PATH().is_file():
        raise FileNotFoundError(str(DOCS_API_PATH()))
    spec = importlib.util.spec_from_file_location('pdone_google_docs_document_ops_api', DOCS_API_PATH())
    if spec is None or spec.loader is None:
        raise RuntimeError(f'unable to load {DOCS_API_PATH()}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def _u16_len(text: str) -> int:
    return len(text.encode('utf-16-le')) // 2

def _sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def _normalize(text: str) -> str:
    return ' '.join(str(text or '').casefold().split())

def _is_work_manual(document: dict[str, Any]) -> bool:
    return 'work-manual' in str(document.get('scope') or '').casefold()

def _bilingual_paragraph_ok(text: str) -> bool:
    value = str(text or '').strip()
    if value.count('\x0b') != 1:
        return False
    chinese, english = value.split('\x0b', 1)
    chinese_for_language_check = re.sub('https?://\\S+', '', chinese)
    english_for_language_check = re.sub('https?://\\S+', '', english)
    identifier_pattern = '[^、，。；;\\s]+\\.(?:docx?|pdf|xlsx?|csv|png|jpe?g|webp|txt)\\b'
    chinese_for_language_check = re.sub(identifier_pattern, '', chinese_for_language_check, flags=re.IGNORECASE)
    english_for_language_check = re.sub(identifier_pattern, '', english_for_language_check, flags=re.IGNORECASE)
    chinese_latin_words = re.findall('[A-Za-z]+', chinese_for_language_check)
    return any(('一' <= char <= '鿿' for char in chinese)) and (not any((any((char.islower() for char in word)) for word in chinese_latin_words))) and any((char.isascii() and char.isalpha() for char in english)) and (not any(('一' <= char <= '鿿' for char in english_for_language_check)))

def _require_bilingual_paragraphs(values: Iterable[str], field_name: str) -> None:
    failures = [index + 1 for index, value in enumerate(values) if not _bilingual_paragraph_ok(value)]
    if failures:
        raise ValueError(f'{field_name} must use same-paragraph Chinese-first, Google Docs line break (\\v), English-second format for work manuals; noncompliant paragraph numbers={failures}')

def _manual_fragment_is_exempt(text: str) -> bool:
    """Allow only clearly non-prose identifiers/formulas/URLs as monolingual fragments."""
    value = str(text or '').strip()
    if not value:
        return False
    if re.fullmatch('https?://\\S+', value, flags=re.IGNORECASE):
        return True
    if value.startswith('=') and (not any(('一' <= char <= '鿿' for char in value))):
        return True
    if not re.fullmatch('[A-Za-z0-9_./:@#%+()\\[\\]-]+', value):
        return False
    return any((char.isdigit() for char in value)) or any((char in '_./:@#%+()[]-' for char in value)) or (value.isupper() and 2 <= len(value) <= 16)

def _require_bilingual_manual_fragment(text: str, field_name: str) -> None:
    value = str(text or '').strip()
    if _manual_fragment_is_exempt(value):
        return
    if not _bilingual_paragraph_ok(value):
        raise ValueError(f'{field_name} must be Chinese-first, contain exactly one same-paragraph line break, and then English; only identifiers, formulas, and URLs are exempt')

def _bilingual_heading_ok(text: str) -> bool:
    value = str(text or '').strip()
    han_positions = [index for index, char in enumerate(value) if '一' <= char <= '鿿']
    latin_positions = [index for index, char in enumerate(value) if char.isascii() and char.isalpha()]
    return '\x0b' not in value and bool(han_positions) and bool(latin_positions) and (han_positions[0] < latin_positions[0]) and (max(han_positions) < latin_positions[0])

def _google_translate_text(text: str, target_language: str) -> str:
    """Translate one bounded manual fragment without requiring another agent hop."""
    query = urllib.parse.urlencode({'client': 'gtx', 'sl': 'auto', 'tl': target_language, 'dt': 't', 'q': text})
    request = urllib.request.Request(f'https://translate.googleapis.com/translate_a/single?{query}', headers={'User-Agent': 'PD-One-bounded-manual-ops/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
        translated = ''.join((str(part[0]) for part in data[0] or [] if part and part[0])).strip().strip('"')
    except Exception:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return ''
    return translated

def _translate_checked(text: str, target_language: str, translator: Callable[[str, str], str]) -> str:
    chunks = [text[index:index + 1800] for index in range(0, len(text), 1800)] or ['']
    translated = ''.join((str(translator(chunk, target_language) or '') for chunk in chunks)).strip()
    has_han = any(('一' <= char <= '鿿' for char in translated))
    has_latin = any((char.isascii() and char.isalpha() for char in translated))
    if target_language == 'en' and (not has_latin or has_han):
        raise ValueError(f'automatic English translation failed for {text[:80]!r}')
    if target_language == 'zh-TW' and (not has_han):
        raise ValueError(f'automatic Traditional Chinese translation failed for {text[:80]!r}')
    return translated

def _split_bilingual_scripts(text: str) -> tuple[str, str] | None:
    value = str(text or '').strip()
    if value.count('\x0b') == 1:
        first, second = (part.strip() for part in value.split('\x0b', 1))
        first_han = any(('一' <= char <= '鿿' for char in first))
        second_han = any(('一' <= char <= '鿿' for char in second))
        if first_han and (not second_han):
            return (first, second)
        if second_han and (not first_han):
            return (second, first)
        return None
    han_positions = [i for i, char in enumerate(value) if '一' <= char <= '鿿']
    latin_positions = [i for i, char in enumerate(value) if char.isascii() and char.isalpha()]
    if not han_positions or not latin_positions:
        return None
    if han_positions[0] < latin_positions[0] and max(han_positions) < latin_positions[0]:
        return (value[:latin_positions[0]].strip(), value[latin_positions[0]:].strip())
    if latin_positions[0] < han_positions[0] and max(latin_positions) < han_positions[0]:
        return (value[han_positions[0]:].strip(), value[:han_positions[0]].strip())
    return None

def _repair_manual_text(text: str, *, field_name: str, heading: bool, translator: Callable[[str, str], str]) -> tuple[str, Optional[dict[str, Any]]]:
    raw_value = str(text or '')
    value = raw_value.strip()
    if _manual_fragment_is_exempt(value):
        return (raw_value, None)
    compliant = _bilingual_heading_ok(value) if heading else _bilingual_paragraph_ok(value)
    if compliant:
        return (raw_value, None)
    pair = _split_bilingual_scripts(value)
    method = 'reordered_existing_translation'
    if pair is None:
        has_han = any(('一' <= char <= '鿿' for char in value))
        has_latin = any((char.isascii() and char.isalpha() for char in value))
        if has_han and (not has_latin):
            pair = (value, _translate_checked(value, 'en', translator))
            method = 'added_english_translation'
        elif has_latin and (not has_han):
            pair = (_translate_checked(value, 'zh-TW', translator), value)
            method = 'added_traditional_chinese_translation'
        else:
            raise ValueError(f'{field_name} could not be normalized into an unambiguous bilingual pair')
    chinese, english = pair
    normalized = f'{chinese} {english}' if heading else f'{chinese}\x0b{english}'
    if not (_bilingual_heading_ok(normalized) if heading else _bilingual_paragraph_ok(normalized)):
        raise ValueError(f'{field_name} automatic translation repair did not pass bilingual validation')
    return (normalized, {'field': field_name, 'method': method, 'original_text': value, 'normalized_text': normalized})

def _paragraph_text(paragraph: dict[str, Any]) -> str:
    return ''.join((str(element.get('textRun', {}).get('content') or '') for element in paragraph.get('elements') or [] if element.get('textRun') is not None))

def _walk_structural_elements(content: Iterable[dict[str, Any]], *, include_toc: bool=True) -> Iterable[dict[str, Any]]:
    for block in content:
        if block.get('paragraph') is not None:
            yield block
        table = block.get('table')
        if table:
            for row in table.get('tableRows') or []:
                for cell in row.get('tableCells') or []:
                    yield from _walk_structural_elements(cell.get('content') or [], include_toc=include_toc)
        toc = block.get('tableOfContents')
        if toc and include_toc:
            yield from _walk_structural_elements(toc.get('content') or [], include_toc=include_toc)

def _body_content(docs_module: Any, doc: dict[str, Any], tab_id: Optional[str]) -> tuple[list[dict[str, Any]], str]:
    content, resolved_tab_id = docs_module.body_content(doc, tab_id)
    return (list(content or []), str(resolved_tab_id))

def _body_paragraphs(docs_module: Any, doc: dict[str, Any], tab_id: Optional[str]) -> tuple[list[dict[str, Any]], str]:
    content, resolved_tab_id = _body_content(docs_module, doc, tab_id)
    return (list(_walk_structural_elements(content)), resolved_tab_id)

def _body_text(docs_module: Any, doc: dict[str, Any], tab_id: Optional[str]) -> str:
    paragraphs, _ = _body_paragraphs(docs_module, doc, tab_id)
    return ''.join((_paragraph_text(block['paragraph']) for block in paragraphs))

def _selected_document_tab(doc: dict[str, Any], tab_id: Optional[str]) -> dict[str, Any]:
    tabs = doc.get('tabs') or []
    if tab_id:
        tabs = [tab for tab in tabs if tab.get('tabProperties', {}).get('tabId') == tab_id]
    if len(tabs) != 1:
        raise ValueError('unable to resolve exactly one document tab')
    return tabs[0].get('documentTab') or {}

def _is_yellow_background(style: dict[str, Any]) -> bool:
    rgb = (((style or {}).get('backgroundColor') or {}).get('color') or {}).get('rgbColor') or {}
    return float(rgb.get('red') or 0) >= 0.99 and float(rgb.get('green') or 0) >= 0.99 and (float(rgb.get('blue') or 0) <= 0.01)

def _header_date_highlight_ok(doc: dict[str, Any], header_id: str, header_text: str, tab_id: Optional[str]) -> bool:
    dates = list(DATE_SEARCH_RE.finditer(header_text))
    if len(dates) != 1:
        return False
    header = (_selected_document_tab(doc, tab_id).get('headers') or {}).get(header_id) or {}
    runs: list[tuple[int, int, dict[str, Any]]] = []
    first_start: Optional[int] = None
    for block in header.get('content') or []:
        for element in (block.get('paragraph') or {}).get('elements') or []:
            run = element.get('textRun')
            if not run:
                continue
            start = int(element.get('startIndex') or 0)
            end = int(element.get('endIndex') or start)
            if first_start is None:
                first_start = start
            runs.append((start, end, run.get('textStyle') or {}))
    if first_start is None:
        return False
    match = dates[0]
    date_start = first_start + _u16_len(header_text[:match.start()])
    date_end = date_start + _u16_len(match.group(0))
    covered = 0
    for start, end, style in runs:
        yellow = _is_yellow_background(style)
        overlap = max(0, min(end, date_end) - max(start, date_start))
        if overlap:
            if not yellow:
                return False
            covered += overlap
        if yellow and (start < date_start or end > date_end):
            return False
    return covered == date_end - date_start

def _text_run_occurrences(docs_module: Any, doc: dict[str, Any], needle: str, tab_id: Optional[str]) -> list[dict[str, Any]]:
    content, resolved_tab_id = _body_content(docs_module, doc, tab_id)
    paragraphs = list(_walk_structural_elements(content, include_toc=False))
    matches: list[dict[str, Any]] = []
    for block in paragraphs:
        paragraph = block['paragraph']
        pstyle = paragraph.get('paragraphStyle') or {}
        ptext = _paragraph_text(paragraph).rstrip('\n')
        for element in paragraph.get('elements') or []:
            run = element.get('textRun')
            if not run:
                continue
            content = str(run.get('content') or '')
            offset = 0
            while True:
                index = content.find(needle, offset)
                if index < 0:
                    break
                start = int(element.get('startIndex') or 0) + _u16_len(content[:index])
                matches.append({'start_index': start, 'end_index': start + _u16_len(needle), 'tab_id': resolved_tab_id, 'paragraph_style': pstyle.get('namedStyleType') or 'NORMAL_TEXT', 'paragraph_text': ptext[:500], 'run_style': copy.deepcopy(run.get('textStyle') or {})})
                offset = index + max(1, len(needle))
    return matches

def _paragraph_matches(docs_module: Any, doc: dict[str, Any], needle: str, tab_id: Optional[str]) -> list[dict[str, Any]]:
    paragraphs, resolved_tab_id = _body_paragraphs(docs_module, doc, tab_id)
    out: list[dict[str, Any]] = []
    for block in paragraphs:
        paragraph = block['paragraph']
        text = _paragraph_text(paragraph).rstrip('\n')
        if needle in text:
            pstyle = paragraph.get('paragraphStyle') or {}
            out.append({'text': text[:1000], 'named_style_type': pstyle.get('namedStyleType') or 'NORMAL_TEXT', 'heading_id': pstyle.get('headingId'), 'start_index': block.get('startIndex'), 'end_index': block.get('endIndex'), 'tab_id': resolved_tab_id})
    return out

def _heading_payload(heading: Any) -> dict[str, Any]:
    return {'text': getattr(heading, 'text', ''), 'heading_id': getattr(heading, 'heading_id', ''), 'level': getattr(heading, 'level', ''), 'start_index': getattr(heading, 'start_index', 0), 'end_index': getattr(heading, 'end_index', 0), 'tab_id': getattr(heading, 'tab_id', '')}

def _find_exact_heading(docs_module: Any, doc: dict[str, Any], query: str, tab_id: Optional[str]) -> Any:
    matches = [h for h in docs_module.collect_headings(doc, tab_id) if _normalize(getattr(h, 'text', '')) == _normalize(query)]
    if len(matches) != 1:
        raise ValueError(f'heading {query!r} must match exactly once; matched {len(matches)} times')
    return matches[0]

def _heading_rank(style: str) -> int:
    match = re.fullmatch('HEADING_(\\d+)', str(style or ''))
    return int(match.group(1)) if match else 999

def _section_placement_postcondition(docs_module: Any, doc: dict[str, Any], section_heading: str, body_paragraphs: Optional[list[str]], heading_style: str, anchor_heading: str, parent_heading: str, tab_id: Optional[str]) -> dict[str, Any]:
    try:
        target = _find_exact_heading(docs_module, doc, section_heading, tab_id)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'ok': False, 'detail': str(exc)}
    headings = sorted(docs_module.collect_headings(doc, tab_id), key=lambda item: int(getattr(item, 'start_index', 0)))
    target_start = int(getattr(target, 'start_index', 0))
    target_rank = _heading_rank(getattr(target, 'level', ''))
    following = [item for item in headings if int(getattr(item, 'start_index', 0)) > target_start]
    next_boundary = next((item for item in following if _heading_rank(getattr(item, 'level', '')) <= target_rank), None)
    actual_anchor = str(getattr(next_boundary, 'text', '') or '') if next_boundary else ''
    parent = None
    preceding_h1 = [item for item in headings if int(getattr(item, 'start_index', 0)) < target_start and getattr(item, 'level', '') == 'HEADING_1']
    if preceding_h1:
        parent = preceding_h1[-1]
    parent_ok = not parent_heading or (parent is not None and _normalize(getattr(parent, 'text', '')) == _normalize(parent_heading))
    anchor_ok = not anchor_heading or (next_boundary is not None and _normalize(actual_anchor) == _normalize(anchor_heading))
    content, _ = _body_content(docs_module, doc, tab_id)
    boundary_start = int(getattr(next_boundary, 'start_index', 2 ** 31 - 1)) if next_boundary else 2 ** 31 - 1
    scoped: list[dict[str, Any]] = []
    for block in content:
        start = int(block.get('startIndex') or 0)
        if start <= target_start or start >= boundary_start:
            continue
        paragraph = block.get('paragraph')
        if not paragraph:
            continue
        text = _paragraph_text(paragraph).rstrip('\n')
        if not text:
            continue
        scoped.append({'text': text, 'style': str((paragraph.get('paragraphStyle') or {}).get('namedStyleType') or 'NORMAL_TEXT')})
    expected_bodies = [str(value or '').strip('\n') for value in body_paragraphs or []]
    bodies_ok = [item['text'] for item in scoped] == expected_bodies and all((item['style'] == 'NORMAL_TEXT' for item in scoped))
    return {'ok': getattr(target, 'level', '') == heading_style and bodies_ok and anchor_ok and parent_ok, 'heading': _heading_payload(target), 'scoped_body_paragraphs': scoped, 'expected_body_paragraphs': expected_bodies, 'actual_anchor_heading': actual_anchor, 'expected_anchor_heading': anchor_heading, 'actual_parent_heading': str(getattr(parent, 'text', '') or '') if parent else '', 'expected_parent_heading': parent_heading, 'anchor_ok': anchor_ok, 'parent_ok': parent_ok, 'bodies_ok': bodies_ok}

def _registered_document(registry: dict[str, Any], document_key: str, action: str) -> dict[str, Any]:
    key = str(document_key or '').strip()
    if not DOC_KEY_RE.fullmatch(key):
        raise ValueError('document_key must be a registered lowercase slug')
    document = registry['documents'].get(key)
    if not isinstance(document, dict):
        raise ValueError(f'document_key is not registered; allowed={sorted(registry['documents'])}')
    allowed = set(document.get('allowed_actions') or [])
    if action not in allowed:
        raise ValueError(f'action {action!r} is not allowed for registered document {key!r}')
    return document

def _parse_requester_id(requester_user_id: str) -> str:
    requester = str(requester_user_id or '').strip()
    if not ID_RE.fullmatch(requester):
        raise ValueError('requester_user_id must be an exact 26-character Mattermost user id')
    return requester

def _global_requester_ids(registry: dict[str, Any]) -> set[str]:
    configured = registry.get('allowed_requester_ids')
    if configured is None:
        configured = registry.get('live_allowed_requester_ids') or []
    return {str(item).strip() for item in configured if str(item).strip()}

def _validate_requester(registry: dict[str, Any], requester_user_id: str, live: bool) -> None:
    requester = _parse_requester_id(requester_user_id)
    if requester not in _global_requester_ids(registry):
        mode = 'live writes' if live else 'Google Docs document operations'
        raise PermissionError(f'requester is not authorized for {mode}')

def _authorize_work_manual_grant(document: dict[str, Any], *, requester_user_id: str, channel_id: str='', chat_type: str='') -> bool:
    grant_key = str(document.get('work_manual_change_grant') or '').strip()
    if not grant_key:
        return False
    tools_dir = str(Path(__file__).resolve().parent)
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    from work_manual_change_authorize import authorize
    result = authorize(mattermost_user_id=requester_user_id, channel_id=channel_id, chat_type=chat_type, document_key=grant_key, document_id=str(document.get('document_id') or ''))
    return result.get('execute') is True

def _authorize_document_requester(registry: dict[str, Any], document: dict[str, Any] | None, *, requester_user_id: str, live: bool, channel_id: str='', chat_type: str='') -> None:
    requester = _parse_requester_id(requester_user_id)
    if requester in _global_requester_ids(registry):
        return
    if document is not None and _authorize_work_manual_grant(document, requester_user_id=requester, channel_id=channel_id, chat_type=chat_type):
        return
    mode = 'live writes' if live else 'Google Docs document operations'
    raise PermissionError(f'requester is not authorized for {mode}')

def _assert_registered_identity(document: dict[str, Any], doc: dict[str, Any]) -> None:
    expected_id = str(document.get('document_id') or '')
    expected_title = str(document.get('title') or '')
    if doc.get('documentId') != expected_id:
        raise RuntimeError('Google Docs readback document ID does not match the registry')
    if expected_title and doc.get('title') != expected_title:
        raise RuntimeError(f'Google Docs title mismatch: expected {expected_title!r}, got {doc.get('title')!r}')

def _check_revision(doc: dict[str, Any], expected_revision_id: Optional[str]) -> Optional[dict[str, Any]]:
    expected = str(expected_revision_id or '').strip()
    current = str(doc.get('revisionId') or '')
    if expected and expected != current:
        return _error('stale_revision', 'expected_revision_id does not match the current Google Docs revision', expected_revision_id=expected, current_revision_id=current)
    return None

def _normal_text_style(docs_module: Any, doc: dict[str, Any], tab_id: Optional[str]) -> tuple[dict[str, Any], str]:
    style: dict[str, Any] = {'bold': False}
    fields = ['bold']
    try:
        if hasattr(docs_module, 'document_tab'):
            doc_tab, _ = docs_module.document_tab(doc, tab_id)
        else:
            doc_tab = doc['tabs'][0]['documentTab']
        named = doc_tab.get('namedStyles') or doc.get('namedStyles') or {}
        for item in named.get('styles') or []:
            if item.get('namedStyleType') != 'NORMAL_TEXT':
                continue
            source = item.get('textStyle') or {}
            for key in ('bold', 'italic', 'underline', 'fontSize', 'weightedFontFamily', 'foregroundColor'):
                if key in source:
                    style[key] = copy.deepcopy(source[key])
                    fields.append(key)
            break
    except Exception:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
    return (style, ','.join(dict.fromkeys(fields)))

def _batch_update(client: Any, document_id: str, requests: list[dict[str, Any]], revision_id: str) -> dict[str, Any]:
    if not revision_id:
        raise ValueError('live writes require a non-empty expected_revision_id')
    url = f'https://docs.googleapis.com/v1/documents/{document_id}:batchUpdate'
    return client._request('POST', url, {'requests': requests, 'writeControl': {'requiredRevisionId': revision_id}})

def _write_receipt(document_key: str, action: str, result: dict[str, Any]) -> str:
    RECEIPT_ROOT().mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    path = RECEIPT_ROOT() / f'{stamp}-{document_key or 'registry'}-{action}.json'
    path.write_text(json.dumps(_json_safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
    return str(path)

def _normalize_heading_display(text: Any) -> str:
    return str(text or '').replace('\x0b', ' / ')[:HEADING_TEXT_MAX]

def _summarize_inspect_receipt(inspect_receipt_path: Optional[str], heading_terms: Optional[list[str]]=None) -> dict[str, Any]:
    raw = str(inspect_receipt_path or '').strip()
    if not raw:
        raise ValueError('inspect_receipt_path is required for summarize_inspect_receipt')
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = RECEIPT_ROOT() / candidate
    resolved = candidate.resolve()
    root = RECEIPT_ROOT().resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError('inspect receipt must be a file under tmp/google-docs-document-ops')
    if resolved.suffix.lower() != '.json':
        raise ValueError('inspect receipt must be a .json file')
    if resolved.is_symlink() or not resolved.is_file():
        raise ValueError('inspect receipt must be a regular file')
    size = resolved.stat().st_size
    if size > INSPECT_RECEIPT_MAX_BYTES:
        raise ValueError(f'inspect receipt exceeds {INSPECT_RECEIPT_MAX_BYTES} bytes')
    payload = json.loads(resolved.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('inspect receipt must be a JSON object')
    if payload.get('capability') != 'pd_one_google_docs_document_ops':
        raise ValueError('inspect receipt capability mismatch')
    if payload.get('action') != 'inspect':
        raise ValueError('inspect receipt action must be inspect')
    headings = payload.get('headings')
    if not isinstance(headings, list):
        raise ValueError('inspect receipt headings must be a list')
    terms: list[str] = []
    for term in heading_terms or []:
        cleaned = str(term or '').strip()
        if not cleaned:
            continue
        if len(cleaned) > 80:
            raise ValueError('heading terms must be <= 80 characters')
        terms.append(cleaned)
        if len(terms) > HEADING_TERMS_MAX:
            raise ValueError(f'heading terms are limited to {HEADING_TERMS_MAX}')
    displayed: list[dict[str, Any]] = []
    matched = 0
    for item in headings:
        if not isinstance(item, dict):
            continue
        text = _normalize_heading_display(item.get('text'))
        if terms:
            haystack = text.casefold()
            if not any((term.casefold() in haystack for term in terms)):
                continue
        matched += 1
        if len(displayed) < HEADING_SUMMARY_MAX:
            displayed.append({'level': item.get('level'), 'start_index': item.get('start_index'), 'text': text})
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return {'status': 'ok', 'capability': 'pd_one_google_docs_document_ops', 'action': 'summarize_inspect_receipt', 'document_key': payload.get('document_key'), 'heading_count': len(headings), 'matched_count': matched, 'headings': displayed, 'headings_truncated': matched > HEADING_SUMMARY_MAX, 'heading_terms': terms, 'source': {'path': str(resolved), 'size_bytes': size, 'sha256': digest}, 'safety': {'read_only': True, 'local_inspect_receipt_only': True, 'google_docs_api_used': False, 'source_system_writes_forbidden': True, 'external_delivery_forbidden': True, 'shell_used': False}}

def _idempotency_fingerprint(*, action: str, document_id: str, tab_id: str, expected_revision_id: str, old_text: str, new_text: str, anchor_heading: str, parent_heading: str, section_heading: str, body_paragraphs: Optional[list[str]], heading_style: str, header_text: str, header_types: Optional[list[str]], changelog_date: str, changelog_summary: str, changelog_heading: str) -> tuple[str, dict[str, Any]]:

    def digest(value: str) -> dict[str, Any]:
        text = str(value or '')
        return {'length': len(text), 'sha256': _sha(text)}
    intent = {'action': action, 'document_id': document_id, 'tab_id': tab_id, 'expected_revision_id': expected_revision_id, 'old_text': digest(old_text), 'new_text': digest(new_text), 'anchor_heading': digest(anchor_heading), 'parent_heading': digest(parent_heading), 'section_heading': digest(section_heading), 'body_paragraphs': [digest(value) for value in body_paragraphs or []], 'heading_style': heading_style, 'header_text': digest(header_text), 'header_types': list(header_types or []), 'changelog_date': changelog_date, 'changelog_summary': digest(changelog_summary), 'changelog_heading': digest(changelog_heading)}
    encoded = json.dumps(intent, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return (_sha(encoded), intent)

def _idempotency_path(key: str) -> Path:
    return IDEMPOTENCY_ROOT() / f'{_sha(key)}.json'

def _translation_cache_path(key: str) -> Path:
    return IDEMPOTENCY_ROOT() / f'{_sha(key)}.translation.json'

def _translation_request_sha256(*, action: str, document_id: str, new_text: str, section_heading: str, body_paragraphs: Optional[list[str]], changelog_summary: str) -> str:
    payload = {'action': action, 'document_id': document_id, 'new_text': new_text, 'section_heading': section_heading, 'body_paragraphs': list(body_paragraphs or []), 'changelog_summary': changelog_summary}
    return _sha(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')))

def _read_translation_cache(key: str) -> Optional[dict[str, Any]]:
    path = _translation_cache_path(key)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('idempotency_key') != key:
        raise RuntimeError('translation cache key hash collision or corrupted record')
    return data

def _write_translation_cache(*, key: str, request_sha256: str, normalized_inputs: dict[str, Any], translation_repairs: list[dict[str, Any]]) -> str:
    IDEMPOTENCY_ROOT().mkdir(parents=True, exist_ok=True)
    path = _translation_cache_path(key)
    record = {'schema': 'pd-one.google-docs-document-ops-translation-cache.v1', 'idempotency_key': key, 'request_sha256': request_sha256, 'normalized_inputs': normalized_inputs, 'translation_repairs': translation_repairs, 'recorded_at_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
    return str(path)

def _read_idempotency_record(key: str) -> Optional[dict[str, Any]]:
    path = _idempotency_path(key)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('idempotency_key') != key:
        raise RuntimeError('idempotency ledger key hash collision or corrupted record')
    return data

def _write_idempotency_record(*, key: str, fingerprint_sha256: str, fingerprint: dict[str, Any], result: dict[str, Any]) -> str:
    IDEMPOTENCY_ROOT().mkdir(parents=True, exist_ok=True)
    path = _idempotency_path(key)
    record = {'schema': 'pd-one.google-docs-document-ops-idempotency.v1', 'idempotency_key': key, 'fingerprint_sha256': fingerprint_sha256, 'fingerprint': fingerprint, 'status': result.get('status'), 'document_key': result.get('document_key'), 'document_id': result.get('document_id'), 'action': result.get('action'), 'receipt_path': result.get('receipt_path'), 'new_revision_id': (result.get('execution') or {}).get('new_revision_id'), 'recorded_at_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
    return str(path)

def _verify_intent_postcondition(*, docs_module: Any, doc: dict[str, Any], action: str, tab_id: str, old_text: str, new_text: str, anchor_heading: str, parent_heading: str, section_heading: str, body_paragraphs: Optional[list[str]], heading_style: str, header_text: str, header_types: Optional[list[str]], changelog_date: str, changelog_summary: str, changelog_heading: str) -> dict[str, Any]:
    if action == 'unique_text_patch':
        old_matches = _text_run_occurrences(docs_module, doc, old_text, tab_id)
        new_matches = _text_run_occurrences(docs_module, doc, new_text, tab_id)
        if old_text == new_text:
            return {'ok': len(new_matches) == 1, 'old_text_matches': len(old_matches), 'new_text_matches': len(new_matches), 'no_op_same_text': True}
        return {'ok': not old_matches and len(new_matches) == 1, 'old_text_matches': len(old_matches), 'new_text_matches': len(new_matches)}
    if action == 'insert_section_before_heading':
        return _section_placement_postcondition(docs_module, doc, section_heading, body_paragraphs, heading_style, anchor_heading, parent_heading, tab_id)
    if action == 'set_header_text':
        style, readback_tab = docs_module.document_style(doc, tab_id)
        headers = []
        for header_type in header_types or list(getattr(docs_module, 'HEADER_TYPE_CHOICES', [])):
            header_id = style.get(docs_module.HEADER_TYPE_TO_STYLE_KEY[header_type])
            if not header_id:
                continue
            value = docs_module.header_text(doc, header_id, readback_tab).rstrip('\n')
            headers.append({'type': header_type, 'header_id': header_id, 'text': value, 'date_highlight_ok': _header_date_highlight_ok(doc, header_id, value, readback_tab)})
        return {'ok': bool(headers) and all((item['text'] == header_text.strip('\n') and item['date_highlight_ok'] for item in headers)), 'headers': headers}
    if action == 'append_changelog':
        try:
            heading = _find_exact_heading(docs_module, doc, section_heading, tab_id)
            entries = docs_module.recent_changelog_entries(doc, changelog_heading, tab_id, limit=30)
        except Exception as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            return {'ok': False, 'detail': str(exc)}
        matched = [entry for entry in entries if _normalize(entry.get('text', '')).startswith(_normalize(changelog_date)) and (getattr(heading, 'heading_id', '') in (entry.get('linkHeadingIds') or []) or _normalize(section_heading) in _normalize(entry.get('text', '')))]
        return {'ok': bool(matched), 'matched_entries': matched, 'summary_present': any((_normalize(changelog_summary) in _normalize(entry.get('text', '')) for entry in matched))}
    return {'ok': False, 'detail': f'unsupported postcondition action {action!r}'}

def _base_result(action: str, document_key: str, document: dict[str, Any], doc: dict[str, Any], dry_run: bool, tab_id: str, docs_module: Any) -> dict[str, Any]:
    return {'status': 'ok', 'capability': 'pd_one_google_docs_document_ops', 'action': action, 'dry_run': dry_run, 'document_key': document_key, 'document_id': document['document_id'], 'document_title': doc.get('title'), 'document_url': docs_module.build_doc_url(document['document_id'], tab_id), 'scope': document.get('scope'), 'current_revision_id': doc.get('revisionId'), 'tab_id': tab_id, 'safety': {'registered_document_only': True, 'typed_actions_only': True, 'raw_batch_update_forbidden': True, 'preview_without_suggestions': True, 'live_write_confirmation_required': LIVE_CONFIRMATION, 'expected_revision_required_for_live_write': True, 'idempotency_key_required_for_live_write': True, 'readback_required_for_live_write': True, 'sharing_permissions_moves_document_deletion_forbidden': True, 'comments_and_suggestion_resolution_forbidden': True, 'requires_chat_layer_authorization': True}}

def _inspect(docs_module: Any, document_key: str, document: dict[str, Any], doc: dict[str, Any], tab_id: Optional[str], changelog_heading: str) -> dict[str, Any]:
    style, resolved_tab_id = docs_module.document_style(doc, tab_id)
    headers = []
    for header_type in getattr(docs_module, 'HEADER_TYPE_CHOICES', []):
        style_key = docs_module.HEADER_TYPE_TO_STYLE_KEY[header_type]
        header_id = style.get(style_key)
        if not header_id:
            continue
        headers.append({'type': header_type, 'header_id': header_id, 'text': docs_module.header_text(doc, header_id, resolved_tab_id).rstrip('\n')})
    all_headings = docs_module.collect_headings(doc, resolved_tab_id)
    headings = [_heading_payload(h) for h in all_headings[:200]]
    changelog_entries: list[dict[str, Any]] = []
    changelog_warning: Optional[str] = None
    if changelog_heading:
        try:
            changelog_entries = docs_module.recent_changelog_entries(doc, changelog_heading, resolved_tab_id, limit=10)
        except Exception as exc:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            changelog_warning = str(exc)[:500]
    result = _base_result('inspect', document_key, document, doc, True, resolved_tab_id, docs_module)
    tabs = [{'tab_id': tab.get('tabProperties', {}).get('tabId'), 'title': tab.get('tabProperties', {}).get('title'), 'index': tab.get('tabProperties', {}).get('index')} for tab in doc.get('tabs') or []]
    result.update({'tabs': tabs, 'selected_tab_id': resolved_tab_id, 'headers': headers, 'headings': headings, 'headings_truncated': len(all_headings) > 200, 'recent_changelog_entries': changelog_entries, 'changelog_warning': changelog_warning})
    return result

def _unique_text_patch_plan(docs_module: Any, doc: dict[str, Any], old_text: str, new_text: str, tab_id: Optional[str], expected_match_count: Optional[int]=None) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    if not old_text or len(old_text) > 12000:
        raise ValueError('old_text is required and must be <= 12000 characters')
    if not new_text or len(new_text) > 16000:
        raise ValueError('new_text is required, non-empty, and must be <= 16000 characters')
    if old_text == new_text:
        return ({'operation': 'unique_text_patch', 'request_count': 0, 'skipped_reason': 'old_text_equals_new_text'}, [], True)
    matches = _text_run_occurrences(docs_module, doc, old_text, tab_id)
    if expected_match_count is not None:
        matches = [item for item in matches if str(item.get('paragraph_text') or '') == old_text]
    if not matches:
        new_matches = _text_run_occurrences(docs_module, doc, new_text, tab_id)
        wanted = 1 if expected_match_count is None else int(expected_match_count)
        if len(new_matches) == wanted:
            return ({'operation': 'unique_text_patch', 'request_count': 0, 'matched_occurrences': 0, 'skipped_reason': 'replacement_already_present_once' if wanted == 1 else 'replacement_already_present', 'new_text_sha256': _sha(new_text)}, [], True)
    wanted = 1 if expected_match_count is None else int(expected_match_count)
    if wanted < 1:
        raise ValueError('expected_match_count must be >= 1')
    if len(matches) != wanted:
        raise ValueError(f'old_text must match exactly {wanted} time(s) in body text runs; matched {len(matches)} times')
    if any((str(match.get('paragraph_style') or '') == 'TITLE' for match in matches)):
        raise ValueError('unique_text_patch cannot modify title paragraphs')
    requests: list[dict[str, Any]] = []
    for match in sorted(matches, key=lambda item: int(item['start_index']), reverse=True):
        requests.extend([{'deleteContentRange': {'range': {'startIndex': match['start_index'], 'endIndex': match['end_index'], 'tabId': match['tab_id']}}}, {'insertText': {'location': {'index': match['start_index'], 'tabId': match['tab_id']}, 'text': new_text}}])
    plan = {'operation': 'unique_text_patch', 'matched_occurrences': len(matches), 'expected_match_count': wanted, 'request_count': len(requests), 'match': {key: matches[0].get(key) for key in ('start_index', 'end_index', 'tab_id', 'paragraph_style')} if wanted == 1 else {'count': len(matches), 'start_indexes': [int(item['start_index']) for item in matches]}, 'old_text_length': len(old_text), 'new_text_length': len(new_text), 'old_text_sha256': _sha(old_text), 'new_text_sha256': _sha(new_text)}
    return (plan, requests, False)

def _insert_section_plan(docs_module: Any, doc: dict[str, Any], anchor_heading: str, parent_heading: str, section_heading: str, body_paragraphs: Optional[list[str]], heading_style: str, tab_id: Optional[str]) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    anchor_heading = str(anchor_heading or '').strip()
    section_heading = str(section_heading or '').strip()
    if not anchor_heading or len(anchor_heading) > 240:
        raise ValueError('anchor_heading is required and must be <= 240 characters')
    if not section_heading or len(section_heading) > 240:
        raise ValueError('section_heading is required and must be <= 240 characters')
    if heading_style not in HEADING_STYLES:
        raise ValueError(f'heading_style must be one of {sorted(HEADING_STYLES)}')
    bodies = [str(value or '').strip('\n') for value in body_paragraphs or []]
    if not bodies or any((not value for value in bodies)):
        raise ValueError('body_paragraphs must contain at least one non-empty paragraph')
    if len(bodies) > 50 or any((len(value) > 4000 for value in bodies)) or sum((len(value) for value in bodies)) > 20000:
        raise ValueError('body_paragraphs exceed the bounded count/size limit')
    existing = [h for h in docs_module.collect_headings(doc, tab_id) if _normalize(getattr(h, 'text', '')) == _normalize(section_heading)]
    if existing:
        if len(existing) != 1:
            raise ValueError(f'section_heading already matches {len(existing)} headings')
        placement = _section_placement_postcondition(docs_module, doc, section_heading, bodies, heading_style, anchor_heading, parent_heading, tab_id)
        if placement.get('ok'):
            return ({'operation': 'insert_section_before_heading', 'request_count': 0, 'skipped_reason': 'section_heading_and_body_already_present', 'existing_heading': _heading_payload(existing[0]), 'placement_readback': placement}, [], True)
        raise ValueError('section_heading already exists but body/order/anchor/parent placement does not match; refusing duplicate/conflicting insertion')
    anchor = _find_exact_heading(docs_module, doc, anchor_heading, tab_id)
    if parent_heading:
        parent = _find_exact_heading(docs_module, doc, parent_heading, tab_id)
        if getattr(parent, 'level', '') != 'HEADING_1':
            raise ValueError('parent_heading must be HEADING_1')
        preceding_h1 = [item for item in docs_module.collect_headings(doc, tab_id) if getattr(item, 'level', '') == 'HEADING_1' and int(getattr(item, 'start_index', 0)) < int(getattr(anchor, 'start_index', 0))]
        if not preceding_h1 or _normalize(getattr(preceding_h1[-1], 'text', '')) != _normalize(parent_heading):
            raise ValueError('anchor_heading is not currently inside the requested Heading 1 parent section')
    resolved_tab_id = str(getattr(anchor, 'tab_id', '') or tab_id or '')
    insert_at = int(getattr(anchor, 'start_index', 0))
    text = section_heading + '\n' + ''.join((body + '\n' for body in bodies))
    heading_end = insert_at + _u16_len(section_heading + '\n')
    total_end = insert_at + _u16_len(text)
    normal_style, normal_fields = _normal_text_style(docs_module, doc, resolved_tab_id)
    requests = [{'insertText': {'location': {'index': insert_at, 'tabId': resolved_tab_id}, 'text': text}}, {'updateParagraphStyle': {'range': {'startIndex': insert_at, 'endIndex': heading_end, 'tabId': resolved_tab_id}, 'paragraphStyle': {'namedStyleType': heading_style}, 'fields': 'namedStyleType'}}, {'updateParagraphStyle': {'range': {'startIndex': heading_end, 'endIndex': total_end, 'tabId': resolved_tab_id}, 'paragraphStyle': {'namedStyleType': 'NORMAL_TEXT'}, 'fields': 'namedStyleType'}}, {'updateTextStyle': {'range': {'startIndex': heading_end, 'endIndex': total_end, 'tabId': resolved_tab_id}, 'textStyle': normal_style, 'fields': normal_fields}}]
    plan = {'operation': 'insert_section_before_heading', 'request_count': len(requests), 'anchor_heading': _heading_payload(anchor), 'parent_heading': parent_heading, 'section_heading': section_heading, 'heading_style': heading_style, 'body_paragraph_count': len(bodies), 'insert_index': insert_at, 'inserted_text_length': len(text), 'inserted_text_sha256': _sha(text), 'body_paragraphs': bodies}
    return (plan, requests, False)

def _set_header_plan(docs_module: Any, doc: dict[str, Any], header_text: str, header_types: Optional[list[str]], tab_id: Optional[str]) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    text = str(header_text or '').strip('\n')
    if not text or len(text) > 1000:
        raise ValueError('header_text is required and must be <= 1000 characters')
    dates = list(DATE_SEARCH_RE.finditer(text))
    if len(dates) != 1:
        raise ValueError('header_text must contain exactly one YYYY-MM-DD date for yellow highlighting')
    date_match = dates[0]
    choices = set(getattr(docs_module, 'HEADER_TYPE_CHOICES', []))
    selected = header_types or list(getattr(docs_module, 'HEADER_TYPE_CHOICES', []))
    if not selected or any((value not in choices for value in selected)):
        raise ValueError(f'header_types must be a non-empty subset of {sorted(choices)}')
    style, resolved_tab_id = docs_module.document_style(doc, tab_id)
    requests: list[dict[str, Any]] = []
    before: list[dict[str, Any]] = []
    text_replacements = 0
    date_highlight_repairs = 0
    for header_type in selected:
        header_id = style.get(docs_module.HEADER_TYPE_TO_STYLE_KEY[header_type])
        if not header_id:
            continue
        current = docs_module.header_text(doc, header_id, resolved_tab_id).rstrip('\n')
        highlight_ok = current == text and _header_date_highlight_ok(doc, header_id, text, resolved_tab_id)
        before.append({'type': header_type, 'header_id': header_id, 'text': current, 'date_highlight_ok': highlight_ok})
        if current != text:
            built = docs_module.build_set_header_text_requests(doc, header_id, text, resolved_tab_id)
            for request in built.get('requests') or []:
                normalized = copy.deepcopy(request)
                insert = normalized.get('insertText')
                if insert and 'location' not in insert and ('endOfSegmentLocation' not in insert) and ('index' in insert):
                    location = {key: insert.pop(key) for key in ('index', 'tabId', 'segmentId') if key in insert}
                    insert['location'] = location
                requests.append(normalized)
            text_replacements += 1
        if not highlight_ok:
            header_start = 0
            full_end = header_start + _u16_len(text)
            date_start = header_start + _u16_len(text[:date_match.start()])
            date_end = date_start + _u16_len(date_match.group(0))
            clear_end = full_end + 1
            requests.extend([{'updateTextStyle': {'range': {'startIndex': header_start, 'endIndex': clear_end, 'tabId': resolved_tab_id, 'segmentId': header_id}, 'textStyle': {'backgroundColor': {}}, 'fields': 'backgroundColor'}}, {'updateTextStyle': {'range': {'startIndex': date_start, 'endIndex': date_end, 'tabId': resolved_tab_id, 'segmentId': header_id}, 'textStyle': {'backgroundColor': YELLOW}, 'fields': 'backgroundColor'}}, {'updateTextStyle': {'range': {'startIndex': date_end, 'endIndex': date_end + 1, 'tabId': resolved_tab_id, 'segmentId': header_id}, 'textStyle': {'backgroundColor': {}}, 'fields': 'backgroundColor'}}])
            date_highlight_repairs += 1
    if not before:
        raise ValueError('none of the selected existing header types were found; this tool does not create new headers')
    plan = {'operation': 'set_header_text', 'request_count': len(requests), 'headers_before': before, 'header_text': text, 'header_text_sha256': _sha(text), 'selected_header_types': selected, 'text_replacements': text_replacements, 'date_highlight_repairs': date_highlight_repairs}
    return (plan, requests, not requests)

def _append_changelog_plan(docs_module: Any, doc: dict[str, Any], changelog_date: str, changelog_summary: str, section_heading: str, changelog_heading: str, tab_id: Optional[str]) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    date_text = str(changelog_date or '').strip()
    if not DATE_RE.fullmatch(date_text):
        raise ValueError('changelog_date must use YYYY-MM-DD')
    summary = str(changelog_summary or '').strip()
    if not summary or len(summary) > 500:
        raise ValueError('changelog_summary is required and must be <= 500 characters')
    section = str(section_heading or '').strip()
    changelog = str(changelog_heading or '').strip()
    if not section or len(section) > 240 or (not changelog) or (len(changelog) > 240):
        raise ValueError('section_heading and changelog_heading are required and must each be <= 240 characters')
    target = _find_exact_heading(docs_module, doc, section, tab_id)
    changelog_obj = _find_exact_heading(docs_module, doc, changelog, tab_id)
    resolved_tab_id = str(getattr(changelog_obj, 'tab_id', '') or tab_id or '')
    target_id = str(getattr(target, 'heading_id', '') or '')
    entries = docs_module.recent_changelog_entries(doc, changelog, resolved_tab_id, limit=30)
    date_entry = next((entry for entry in entries if _normalize(entry.get('text', '')).startswith(_normalize(date_text))), None)
    if date_entry and (target_id in (date_entry.get('linkHeadingIds') or []) or _normalize(section) in _normalize(date_entry.get('text', ''))):
        plan = {'operation': 'append_changelog', 'request_count': 0, 'date': date_text, 'summary': summary, 'section_heading': section, 'changelog_heading': changelog, 'target_heading': _heading_payload(target), 'target_heading_url': docs_module.build_doc_url(doc['documentId'], getattr(target, 'tab_id', resolved_tab_id)), 'skipped_duplicate': True, 'duplicate_reason': 'same date entry already links or names the changed section', 'merged_into_existing_date_entry': False}
        return (plan, [], True)
    yellow = {'color': {'rgbColor': {'red': 1, 'green': 1}}}
    if date_entry:
        insert_at = max(int(date_entry.get('startIndex') or 0), int(date_entry.get('endIndex') or 0) - 1)
        prefix = f' | {summary} | '
        inserted = prefix + section
        section_start = insert_at + _u16_len(prefix)
        requests = [{'insertText': {'location': {'index': insert_at, 'tabId': str(date_entry.get('tabId') or resolved_tab_id)}, 'text': inserted}}, {'updateTextStyle': {'range': {'startIndex': section_start, 'endIndex': section_start + _u16_len(section), 'tabId': str(date_entry.get('tabId') or resolved_tab_id)}, 'textStyle': {'link': {'heading': {'id': target_id, 'tabId': getattr(target, 'tab_id', resolved_tab_id)}}}, 'fields': 'link'}}]
        merged = True
    else:
        insert_at = int(getattr(changelog_obj, 'end_index', 0))
        prefix = f'{date_text}: {summary} | '
        inserted = prefix + section + '\n'
        date_end = insert_at + _u16_len(date_text)
        section_start = insert_at + _u16_len(prefix)
        line_end = insert_at + _u16_len(inserted)
        requests = [{'insertText': {'location': {'index': insert_at, 'tabId': resolved_tab_id}, 'text': inserted}}, {'createParagraphBullets': {'range': {'startIndex': insert_at, 'endIndex': line_end, 'tabId': resolved_tab_id}, 'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'}}, {'updateTextStyle': {'range': {'startIndex': insert_at, 'endIndex': line_end - 1, 'tabId': resolved_tab_id}, 'textStyle': {'backgroundColor': {}}, 'fields': 'backgroundColor'}}, {'updateTextStyle': {'range': {'startIndex': insert_at, 'endIndex': date_end, 'tabId': resolved_tab_id}, 'textStyle': {'backgroundColor': yellow}, 'fields': 'backgroundColor'}}, {'updateTextStyle': {'range': {'startIndex': section_start, 'endIndex': section_start + _u16_len(section), 'tabId': resolved_tab_id}, 'textStyle': {'link': {'heading': {'id': target_id, 'tabId': getattr(target, 'tab_id', resolved_tab_id)}}}, 'fields': 'link'}}]
        merged = False
    plan = {'operation': 'append_changelog', 'request_count': len(requests), 'date': date_text, 'summary': summary, 'section_heading': section, 'changelog_heading': changelog, 'target_heading': _heading_payload(target), 'target_heading_url': docs_module.build_doc_url(doc['documentId'], getattr(target, 'tab_id', resolved_tab_id)), 'insert_index': insert_at, 'inserted_text': inserted, 'skipped_duplicate': False, 'duplicate_reason': None, 'merged_into_existing_date_entry': merged}
    return (plan, requests, False)

def _verify_required_strings(docs_module: Any, doc: dict[str, Any], required_strings: Optional[list[str]], tab_id: Optional[str]) -> dict[str, Any]:
    strings = [str(value or '') for value in required_strings or []]
    if len(strings) > 50 or any((not value or len(value) > 4000 for value in strings)):
        raise ValueError('required_strings must contain 1-50 non-empty strings of <= 4000 characters')
    text = _body_text(docs_module, doc, tab_id)
    missing = [value for value in strings if value not in text]
    return {'ok': not missing, 'required_strings_count': len(strings), 'missing_required_strings': missing, 'body_text_sha256': _sha(text)}

def _verify_toc_headings(docs_module: Any, doc: dict[str, Any], required_toc_headings: Optional[list[str]], tab_id: Optional[str]) -> dict[str, Any]:
    required = [str(value or '').strip() for value in required_toc_headings or []]
    if len(required) > 50 or any((not value or len(value) > 240 for value in required)):
        raise ValueError('required_toc_headings must contain 1-50 non-empty headings of <= 240 characters')
    content, _ = _body_content(docs_module, doc, tab_id)
    entries: list[dict[str, Any]] = []
    for block in content:
        toc = block.get('tableOfContents')
        if not toc:
            continue
        for item in _walk_structural_elements(toc.get('content') or []):
            paragraph = item.get('paragraph')
            if not paragraph:
                continue
            text = _paragraph_text(paragraph).strip()
            heading_ids: list[str] = []
            for element in paragraph.get('elements') or []:
                link = ((element.get('textRun') or {}).get('textStyle') or {}).get('link') or {}
                heading = link.get('heading') or {}
                if heading.get('id'):
                    heading_ids.append(str(heading['id']))
            if text:
                entries.append({'text': text, 'heading_ids': heading_ids})
    missing: list[str] = []
    wrong_identity: list[str] = []
    duplicate_or_conflicting: list[str] = []
    for heading_text in required:
        target = _find_exact_heading(docs_module, doc, heading_text, tab_id)
        exact_entries = [entry for entry in entries if _normalize(entry['text']) == _normalize(heading_text)]
        if not exact_entries:
            missing.append(heading_text)
            continue
        if len(exact_entries) != 1:
            duplicate_or_conflicting.append(heading_text)
            continue
        target_id = str(getattr(target, 'heading_id', '') or '')
        entry_ids = set(exact_entries[0]['heading_ids'])
        if not target_id or entry_ids != {target_id}:
            wrong_identity.append(heading_text)
    encoded_entries = json.dumps(entries, ensure_ascii=False, sort_keys=True)
    return {'ok': bool(entries) and (not missing) and (not wrong_identity) and (not duplicate_or_conflicting), 'native_toc_count': sum((1 for block in content if block.get('tableOfContents'))), 'native_toc_entry_count': len(entries), 'required_toc_headings_count': len(required), 'missing_toc_headings': missing, 'wrong_identity_toc_headings': wrong_identity, 'duplicate_or_conflicting_toc_headings': duplicate_or_conflicting, 'toc_entries_sha256': _sha(encoded_entries)}

def _verify_work_manual_section(docs_module: Any, doc: dict[str, Any], section_heading: str, tab_id: Optional[str]) -> dict[str, Any]:
    target = str(section_heading or '').strip()
    if not target:
        raise ValueError('section_heading is required for work-manual compliance verification')
    content, resolved_tab_id = _body_content(docs_module, doc, tab_id)
    start_position: Optional[int] = None
    target_level = ''
    for position, block in enumerate(content):
        paragraph = block.get('paragraph') or {}
        text = _paragraph_text(paragraph).strip()
        style = str((paragraph.get('paragraphStyle') or {}).get('namedStyleType') or 'NORMAL_TEXT')
        if _normalize(text) == _normalize(target):
            if start_position is not None:
                raise ValueError(f'section_heading {target!r} must match exactly once')
            start_position = position
            target_level = style
    if start_position is None:
        raise ValueError(f'section_heading {target!r} was not found')
    if target_level != 'HEADING_1':
        return {'ok': False, 'detail': 'work-manual parent section must be HEADING_1', 'actual_style': target_level}
    if not _bilingual_heading_ok(target):
        return {'ok': False, 'detail': 'work-manual parent heading must be Chinese-first and English-second', 'actual_heading': target}
    body_failures: list[dict[str, Any]] = []
    heading_failures: list[dict[str, Any]] = []
    audited_body = 0
    child_headings = 0
    for block in content[start_position + 1:]:
        paragraph = block.get('paragraph')
        if paragraph:
            text = _paragraph_text(paragraph).strip()
            style = str((paragraph.get('paragraphStyle') or {}).get('namedStyleType') or 'NORMAL_TEXT')
            if style == 'HEADING_1':
                break
        for nested in _walk_structural_elements([block]):
            nested_paragraph = nested.get('paragraph') or {}
            text = _paragraph_text(nested_paragraph).strip()
            style = str((nested_paragraph.get('paragraphStyle') or {}).get('namedStyleType') or 'NORMAL_TEXT')
            if not text:
                continue
            if style.startswith('HEADING'):
                child_headings += 1
                if not (_bilingual_heading_ok(text) or _manual_fragment_is_exempt(text)):
                    heading_failures.append({'text': text[:300], 'style': style})
                continue
            audited_body += 1
            if not _bilingual_paragraph_ok(text):
                body_failures.append({'text': text[:300], 'style': style})
    style, _ = docs_module.document_style(doc, resolved_tab_id)
    header_checks = []
    for header_type in getattr(docs_module, 'HEADER_TYPE_CHOICES', []):
        header_id = style.get(docs_module.HEADER_TYPE_TO_STYLE_KEY[header_type])
        if not header_id:
            continue
        text = docs_module.header_text(doc, header_id, resolved_tab_id).rstrip('\n')
        header_checks.append({'type': header_type, 'text': text, 'date_highlight_ok': _header_date_highlight_ok(doc, header_id, text, resolved_tab_id)})
    return {'ok': audited_body > 0 and child_headings > 0 and (not body_failures) and (not heading_failures) and bool(header_checks) and all((item['date_highlight_ok'] for item in header_checks)), 'parent_heading': target, 'parent_style': target_level, 'audited_body_paragraphs': audited_body, 'child_headings': child_headings, 'non_bilingual_body_paragraphs': body_failures[:20], 'non_bilingual_child_headings': heading_failures[:20], 'headers': header_checks}

def execute_document_ops(*, action: str='list_registered_documents', document_key: str='', requester_user_id: str, channel_id: str='', chat_type: str='', old_text: str='', new_text: str='', anchor_heading: str='', parent_heading: str='', section_heading: str='', body_paragraphs: Optional[list[str]]=None, heading_style: str='HEADING_2', header_text: str='', header_types: Optional[list[str]]=None, changelog_date: str='', changelog_summary: str='', changelog_heading: str='變更日誌 Changelog', required_strings: Optional[list[str]]=None, required_toc_headings: Optional[list[str]]=None, expected_revision_id: Optional[str]=None, idempotency_key: Optional[str]=None, tab_id: Optional[str]=None, expected_match_count: Optional[int]=None, inspect_receipt_path: Optional[str]=None, heading_terms: Optional[list[str]]=None, dry_run: bool=True, confirm_live_write: Optional[str]=None, registry_path: Path=None, docs_module: Any=None, client: Any=None, translator: Optional[Callable[[str, str], str]]=None) -> dict[str, Any]:
    """Execute one bounded Google Docs action and return a structured receipt."""
    if registry_path is None:
        registry_path = REGISTRY_PATH()
    action_key = str(action or 'list_registered_documents').strip().lower().replace('-', '_')

    def _pd_phase_2():
        nonlocal _pd_result, result, section_heading
        doc = _PdUnset
        docs_client = _PdUnset
        document = _PdUnset
        live = _PdUnset
        module = _PdUnset
        resolved_tab_id = _PdUnset
        result = _PdUnset
        revision_error = _PdUnset
        section_heading = _PdUnset
        translation_repairs = _PdUnset

        def _pd_phase_5():
            nonlocal _pd_result, doc, docs_client, document, live, module, resolved_tab_id, result, revision_error, section_heading, translation_repairs
            section_heading = _PdUnset
            if action_key == 'bootstrap_erp_work_manual':
                import importlib.util
                bootstrap_path = ROOT() / 'tools/erp_work_manual_bootstrap.py'
                spec = importlib.util.spec_from_file_location('pdone_erp_work_manual_bootstrap', bootstrap_path)
                if spec is None or spec.loader is None:
                    raise RuntimeError(f'unable to load {bootstrap_path}')
                bootstrap = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(bootstrap)
                return _PdReturn(bootstrap.bootstrap_erp_work_manual(requester_user_id=requester_user_id, dry_run=bool(dry_run), confirm_live_write=confirm_live_write, idempotency_key=idempotency_key, docs_module=docs_module, client=client))
            if action_key not in ALLOWED_ACTIONS:
                raise ValueError(f'action must be one of: {sorted(ALLOWED_ACTIONS)}')
            registry = _load_registry(Path(registry_path))
            live = action_key in WRITE_ACTIONS and (not bool(dry_run))
            if live and confirm_live_write != registry.get('live_confirmation', LIVE_CONFIRMATION):
                raise ValueError(f'live Google Docs writes require confirm_live_write={LIVE_CONFIRMATION!r}')
            if action_key == 'summarize_inspect_receipt':
                _authorize_document_requester(registry, None, requester_user_id=requester_user_id, live=False, channel_id=channel_id, chat_type=chat_type)
                result = _summarize_inspect_receipt(inspect_receipt_path, heading_terms)
                result['receipt_path'] = _write_receipt(str(result.get('document_key') or ''), action_key, result)
                return _PdReturn(result)
            if action_key == 'list_registered_documents':
                _authorize_document_requester(registry, None, requester_user_id=requester_user_id, live=live, channel_id=channel_id, chat_type=chat_type)
                documents = []
                for key, document in sorted(registry['documents'].items()):
                    documents.append({'document_key': key, 'document_id': document.get('document_id'), 'title': document.get('title'), 'scope': document.get('scope'), 'live_enabled': bool(document.get('live_enabled')), 'allowed_actions': document.get('allowed_actions') or []})
                result = {'status': 'ok', 'capability': 'pd_one_google_docs_document_ops', 'action': action_key, 'documents': documents, 'safety': {'registered_documents_only': True, 'typed_actions_only': True, 'live_confirmation_required': registry.get('live_confirmation', LIVE_CONFIRMATION)}}
                result['receipt_path'] = _write_receipt('', action_key, result)
                return _PdReturn(result)
            document = _registered_document(registry, document_key, action_key)
            _authorize_document_requester(registry, document, requester_user_id=requester_user_id, live=live, channel_id=channel_id, chat_type=chat_type)
            if live and (not bool(document.get('live_enabled'))):
                raise PermissionError(f'live writes are not enabled for registered document {document_key!r}')
            module = docs_module or _load_docs_api_module()
            account = str(document.get('account') or registry.get('account') or site_text('PDONE_EMAIL_ADMIN'))
            docs_client = client or module.DocsClient(account)
            doc = docs_client.get_document(document['document_id'], 'PREVIEW_WITHOUT_SUGGESTIONS')
            _assert_registered_identity(document, doc)
            if live and len(doc.get('tabs') or []) > 1 and (not tab_id):
                raise ValueError('live writes to multi-tab documents require an explicit tab_id from inspect')
            _, resolved_tab_id = _body_content(module, doc, tab_id)
            translation_repairs = []

            def _pd_phase_1():
                nonlocal _pd_result, section_heading
                body_paragraphs = _PdUnset
                changelog_summary = _PdUnset
                new_text = _PdUnset
                section_heading = _PdUnset

                def _pd_phase_3():
                    nonlocal body_paragraphs, changelog_summary, new_text, section_heading
                    translate = translator or _google_translate_text
                    translatable_action = action_key in {'insert_section_before_heading', 'unique_text_patch', 'append_changelog'}
                    translation_cache = None
                    translation_request_sha256 = ''
                    normalized_idempotency_key = str(idempotency_key or '').strip()
                    if live and translatable_action:
                        if not IDEMPOTENCY_KEY_RE.fullmatch(normalized_idempotency_key):
                            raise ValueError('live Google Docs writes require idempotency_key matching [A-Za-z0-9][A-Za-z0-9._:-]{7,127}')
                        translation_request_sha256 = _translation_request_sha256(action=action_key, document_id=document['document_id'], new_text=new_text, section_heading=section_heading, body_paragraphs=body_paragraphs, changelog_summary=changelog_summary)
                        translation_cache = _read_translation_cache(normalized_idempotency_key)
                        if translation_cache:
                            if translation_cache.get('request_sha256') != translation_request_sha256:
                                raise ValueError('idempotency_key was already used with different pre-translation manual content')
                            normalized = translation_cache.get('normalized_inputs') or {}
                            new_text = str(normalized.get('new_text', new_text))
                            section_heading = str(normalized.get('section_heading', section_heading))
                            body_paragraphs = list(normalized.get('body_paragraphs', body_paragraphs or []))
                            changelog_summary = str(normalized.get('changelog_summary', changelog_summary))
                            translation_repairs = list(translation_cache.get('translation_repairs') or [])
                    if not translation_cache:
                        if action_key == 'insert_section_before_heading':
                            repaired_bodies: list[str] = []
                            for index, paragraph_text in enumerate(body_paragraphs or [], 1):
                                normalized, repair = _repair_manual_text(paragraph_text, field_name=f'body_paragraphs[{index}]', heading=False, translator=translate)
                                repaired_bodies.append(normalized)
                                if repair:
                                    translation_repairs.append(repair)
                            body_paragraphs = repaired_bodies
                            section_heading, heading_repair = _repair_manual_text(section_heading, field_name='section_heading', heading=True, translator=translate)
                            if heading_repair:
                                translation_repairs.append(heading_repair)
                        elif action_key == 'unique_text_patch':
                            new_text, repair = _repair_manual_text(new_text, field_name='new_text', heading=False, translator=translate)
                            if repair:
                                translation_repairs.append(repair)
                        elif action_key == 'append_changelog':
                            changelog_summary, repair = _repair_manual_text(changelog_summary, field_name='changelog_summary', heading=False, translator=translate)
                            if repair:
                                translation_repairs.append(repair)
                        if live and translatable_action:
                            _write_translation_cache(key=normalized_idempotency_key, request_sha256=translation_request_sha256, normalized_inputs={'new_text': new_text, 'section_heading': section_heading, 'body_paragraphs': list(body_paragraphs or []), 'changelog_summary': changelog_summary}, translation_repairs=translation_repairs)

                def _pd_phase_4():
                    if action_key == 'insert_section_before_heading':
                        _require_bilingual_paragraphs(body_paragraphs or [], 'body_paragraphs')
                        if heading_style != 'HEADING_1' and (not str(parent_heading or '').strip()):
                            raise ValueError('parent_heading is required for subordinate work-manual sections')
                        if not (_bilingual_heading_ok(section_heading) or _manual_fragment_is_exempt(section_heading)):
                            raise ValueError('section_heading automatic repair did not produce Chinese-first and English-second text')
                    elif action_key == 'unique_text_patch':
                        _require_bilingual_manual_fragment(new_text, 'new_text')
                    elif action_key == 'append_changelog':
                        _require_bilingual_manual_fragment(changelog_summary, 'changelog_summary')
                    elif action_key == 'verify_readback' and (not str(section_heading or '').strip()):
                        raise ValueError('section_heading is mandatory for work-manual verify_readback')
                _pd_result = _pd_phase_3()
                if isinstance(_pd_result, _PdReturn):
                    return _pd_result.value
                _pd_result = _pd_phase_4()
                if isinstance(_pd_result, _PdReturn):
                    return _pd_result.value
            if _is_work_manual(document):
                _pd_result = _pd_phase_1()
                if isinstance(_pd_result, _PdReturn):
                    return _PdReturn(_pd_result.value)
            if action_key in {'inspect', 'verify_readback'}:
                revision_error = _check_revision(doc, expected_revision_id)
                if revision_error:
                    revision_error.update({'capability': 'pd_one_google_docs_document_ops', 'action': action_key, 'document_key': document_key})
                    revision_error['receipt_path'] = _write_receipt(document_key, action_key, revision_error)
                    return _PdReturn(revision_error)
            if action_key == 'inspect':
                result = _inspect(module, document_key, document, doc, resolved_tab_id, changelog_heading)
                result['receipt_path'] = _write_receipt(document_key, action_key, result)
                return _PdReturn(result)
            if action_key == 'verify_readback':
                result = _base_result(action_key, document_key, document, doc, True, resolved_tab_id, module)
                result['translation_repairs'] = translation_repairs
                result['verification'] = _verify_required_strings(module, doc, required_strings, resolved_tab_id)
                checks = [result['verification']]
                if required_toc_headings:
                    result['toc_verification'] = _verify_toc_headings(module, doc, required_toc_headings, resolved_tab_id)
                    checks.append(result['toc_verification'])
                if _is_work_manual(document) and section_heading:
                    result['work_manual_compliance'] = _verify_work_manual_section(module, doc, section_heading, resolved_tab_id)
                    checks.append(result['work_manual_compliance'])
                result['status'] = 'ok' if all((check.get('ok') for check in checks)) else 'error'
                result['receipt_path'] = _write_receipt(document_key, action_key, result)
                return _PdReturn(result)

        def _pd_phase_6():
            nonlocal result, revision_error
            if action_key == 'unique_text_patch':
                plan, requests, skipped = _unique_text_patch_plan(module, doc, old_text, new_text, resolved_tab_id, expected_match_count=expected_match_count)
            elif action_key == 'insert_section_before_heading':
                plan, requests, skipped = _insert_section_plan(module, doc, anchor_heading, parent_heading, section_heading, body_paragraphs, heading_style, resolved_tab_id)
            elif action_key == 'set_header_text':
                plan, requests, skipped = _set_header_plan(module, doc, header_text, header_types, resolved_tab_id)
            elif action_key == 'append_changelog':
                plan, requests, skipped = _append_changelog_plan(module, doc, changelog_date, changelog_summary, section_heading, changelog_heading, resolved_tab_id)
            else:
                raise AssertionError(action_key)
            fingerprint_sha256: Optional[str] = None
            fingerprint: Optional[dict[str, Any]] = None
            postcondition: Optional[dict[str, Any]] = None
            normalized_idempotency_key = str(idempotency_key or '').strip()
            if live:
                if not expected_revision_id:
                    raise ValueError('live Google Docs writes require expected_revision_id from a fresh inspect/dry-run')
                if not IDEMPOTENCY_KEY_RE.fullmatch(normalized_idempotency_key):
                    raise ValueError('live Google Docs writes require idempotency_key matching [A-Za-z0-9][A-Za-z0-9._:-]{7,127}')
                fingerprint_sha256, fingerprint = _idempotency_fingerprint(action=action_key, document_id=document['document_id'], tab_id=resolved_tab_id, expected_revision_id=str(expected_revision_id), old_text=old_text, new_text=new_text, anchor_heading=anchor_heading, parent_heading=parent_heading, section_heading=section_heading, body_paragraphs=body_paragraphs, heading_style=heading_style, header_text=header_text, header_types=header_types, changelog_date=changelog_date, changelog_summary=changelog_summary, changelog_heading=changelog_heading)
                postcondition = _verify_intent_postcondition(docs_module=module, doc=doc, action=action_key, tab_id=resolved_tab_id, old_text=old_text, new_text=new_text, anchor_heading=anchor_heading, parent_heading=parent_heading, section_heading=section_heading, body_paragraphs=body_paragraphs, heading_style=heading_style, header_text=header_text, header_types=header_types, changelog_date=changelog_date, changelog_summary=changelog_summary, changelog_heading=changelog_heading)
                prior_record = _read_idempotency_record(normalized_idempotency_key)
                if prior_record:
                    if prior_record.get('fingerprint_sha256') != fingerprint_sha256:
                        result = _error('idempotency_conflict', 'idempotency_key was already used with a different operation fingerprint', capability='pd_one_google_docs_document_ops', action=action_key, document_key=document_key)
                        result['receipt_path'] = _write_receipt(document_key, action_key, result)
                        return _PdReturn(result)
                    if not postcondition.get('ok'):
                        result = _error('idempotency_postcondition_missing', 'idempotency record exists but the current document no longer satisfies the recorded postcondition', capability='pd_one_google_docs_document_ops', action=action_key, document_key=document_key, readback=postcondition)
                        result['receipt_path'] = _write_receipt(document_key, action_key, result)
                        return _PdReturn(result)
                    result = _base_result(action_key, document_key, document, doc, False, resolved_tab_id, module)
                    result['translation_repairs'] = translation_repairs
                    result['plan'] = {**plan, 'request_count': 0, 'skipped_reason': 'idempotent_replay'}
                    result['skipped_existing'] = True
                    result['execution'] = {'write_response': None, 'readback': postcondition, 'new_revision_id': doc.get('revisionId')}
                    result['idempotency'] = {'key': normalized_idempotency_key, 'fingerprint_sha256': fingerprint_sha256, 'replayed': True, 'recovered_after_write': False, 'ledger_path': str(_idempotency_path(normalized_idempotency_key))}
                    result['receipt_path'] = _write_receipt(document_key, action_key, result)
                    return _PdReturn(result)
            revision_error = _check_revision(doc, expected_revision_id)
            if revision_error:
                if live and postcondition and postcondition.get('ok') and fingerprint_sha256 and fingerprint:
                    result = _base_result(action_key, document_key, document, doc, False, resolved_tab_id, module)
                    result['translation_repairs'] = translation_repairs
                    result['plan'] = {**plan, 'request_count': 0, 'skipped_reason': 'postcondition_already_satisfied_after_revision_advance'}
                    result['skipped_existing'] = True
                    result['execution'] = {'write_response': None, 'readback': postcondition, 'new_revision_id': doc.get('revisionId')}
                    result['idempotency'] = {'key': normalized_idempotency_key, 'fingerprint_sha256': fingerprint_sha256, 'replayed': True, 'recovered_after_write': True}
                    result['receipt_path'] = _write_receipt(document_key, action_key, result)
                    result['idempotency']['ledger_path'] = _write_idempotency_record(key=normalized_idempotency_key, fingerprint_sha256=fingerprint_sha256, fingerprint=fingerprint, result=result)
                    return _PdReturn(result)
                revision_error.update({'capability': 'pd_one_google_docs_document_ops', 'action': action_key, 'document_key': document_key})
                revision_error['receipt_path'] = _write_receipt(document_key, action_key, revision_error)
                return _PdReturn(revision_error)
            result = _base_result(action_key, document_key, document, doc, bool(dry_run), resolved_tab_id, module)
            result['translation_repairs'] = translation_repairs
            result['plan'] = plan
            result['skipped_existing'] = bool(skipped)
            if dry_run:
                result['receipt_path'] = _write_receipt(document_key, action_key, result)
                return _PdReturn(result)
            if skipped:
                if not postcondition or not postcondition.get('ok'):
                    raise RuntimeError('write plan reported an idempotent no-op but readback postcondition was not satisfied')
                result['execution'] = {'write_response': None, 'readback': postcondition, 'new_revision_id': doc.get('revisionId')}
                result['idempotency'] = {'key': normalized_idempotency_key, 'fingerprint_sha256': fingerprint_sha256, 'replayed': False, 'recovered_after_write': False, 'no_op': True}
                result['receipt_path'] = _write_receipt(document_key, action_key, result)
                result['idempotency']['ledger_path'] = _write_idempotency_record(key=normalized_idempotency_key, fingerprint_sha256=str(fingerprint_sha256), fingerprint=fingerprint or {}, result=result)
                return _PdReturn(result)
            execution = _batch_update(docs_client, document['document_id'], requests, str(expected_revision_id))
            readback = docs_client.get_document(document['document_id'], 'PREVIEW_WITHOUT_SUGGESTIONS')
            _assert_registered_identity(document, readback)
            verification = _verify_intent_postcondition(docs_module=module, doc=readback, action=action_key, tab_id=resolved_tab_id, old_text=old_text, new_text=new_text, anchor_heading=anchor_heading, parent_heading=parent_heading, section_heading=section_heading, body_paragraphs=body_paragraphs, heading_style=heading_style, header_text=header_text, header_types=header_types, changelog_date=changelog_date, changelog_summary=changelog_summary, changelog_heading=changelog_heading)
            result['execution'] = {'write_response': _json_safe(execution), 'readback': verification, 'new_revision_id': readback.get('revisionId')}
            result['idempotency'] = {'key': normalized_idempotency_key, 'fingerprint_sha256': fingerprint_sha256, 'replayed': False, 'recovered_after_write': False}
            if not verification.get('ok'):
                result['status'] = 'error'
                result['error'] = 'readback_verification_failed'
            result['receipt_path'] = _write_receipt(document_key, action_key, result)
            if verification.get('ok'):
                result['idempotency']['ledger_path'] = _write_idempotency_record(key=normalized_idempotency_key, fingerprint_sha256=str(fingerprint_sha256), fingerprint=fingerprint or {}, result=result)
            return _PdReturn(result)
        _pd_result = _pd_phase_5()
        if isinstance(_pd_result, _PdReturn):
            return _pd_result.value
        _pd_result = _pd_phase_6()
        if isinstance(_pd_result, _PdReturn):
            return _pd_result.value
    try:
        _pd_result = _pd_phase_2()
        if isinstance(_pd_result, _PdReturn):
            return _pd_result.value
    except PermissionError as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        result = _error('not_authorized', str(exc), capability='pd_one_google_docs_document_ops', action=action_key)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        result = _error('invalid_request', str(exc), capability='pd_one_google_docs_document_ops', action=action_key)
    try:
        result['receipt_path'] = _write_receipt(document_key, action_key, result)
    except Exception:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
    return result
__all__ = ['execute_document_ops', 'LIVE_CONFIRMATION', 'REGISTRY_PATH']

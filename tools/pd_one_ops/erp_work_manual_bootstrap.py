#!/usr/bin/env python3
"""Create one barebones ERP work manual from a sibling shell.

This action is hardcoded. It does not accept caller document ids, share
targets, or raw Google API requests. Owner's exact Mattermost id is required.
"""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Optional

def ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))

def SOURCE_DOC_ID():
    return site_text('PDONE_SOURCE_DOC_ID')

def PARENT_FOLDER_ID():
    return site_text('PDONE_PARENT_FOLDER_ID')
DOC_TITLE = '良器-工作指南與程序手冊-ERP'

def ANDY_ID():
    return site_text('PDONE_OWNER_MM_USER_ID')
LIVE_CONFIRMATION = 'RUN LIVE GOOGLE DOCS DOCUMENT OPS'
HEADER_TEXT = '最近更新時間 Last updated: 2026-10-13'
HEADER_DATE = '2026-10-13'

def ACCOUNT():
    return site_text('PDONE_EMAIL_ADMIN')
YELLOW = {'color': {'rgbColor': {'red': 1, 'green': 1}}}

def WRITER_GROUPS():
    return (site_text('PDONE_EMAIL_FINANCE'), site_text('PDONE_EMAIL_PROCUREMENT'), site_text('PDONE_EMAIL_WAREHOUSE'), site_text('PDONE_EMAIL_PRODUCTION_SCHEDULER'), site_text('PDONE_EMAIL_SALES'), site_text('PDONE_EMAIL_QC'), site_text('PDONE_EMAIL_IT'), site_text('PDONE_EMAIL_SENIOR_STAFF'), site_text('PDONE_EMAIL_CXO'), site_text('PDONE_EMAIL_MOLD_REPAIR'), site_text('PDONE_EMAIL_RD'), site_text('PDONE_EMAIL_FACILITIES'), site_text('PDONE_EMAIL_HR'), site_text('PDONE_EMAIL_MOLDING_PROJECT_TEAM'))

def EXCLUDED_GROUPS():
    return (site_text('PDONE_EMAIL_OPERATORS'), site_text('PDONE_EMAIL_MOLDING_STAFF'), site_text('PDONE_EMAIL_PRINTING'), site_text('PDONE_EMAIL_INJECTION_MOLDING'), site_text('PDONE_EMAIL_INJECTION_MOLDING_STAFF'), site_text('PDONE_EMAIL_ALL_COMPANY'))
MOLDING_MARKERS = ('成型非作業員', '成型-非作業員', 'Molding Staff', 'Injection Molding Staff', '制服口袋', 'Loose Objects in Uniform Pockets', '作業員指南和程序手冊')

def LEGACY_MANIFEST():
    return ROOT() / 'legacy-openclaw/workspace/data/google-docs-index/manifest.json'

def PROFILE_MANIFEST():
    return ROOT() / 'data/google-docs-index/manifest.json'

def ROUTING_PATH():
    return ROOT() / 'legacy-openclaw/workspace/data/work-manual-watcher/notification-routing.json'

def REGISTRY_PATH():
    return ROOT() / 'capabilities/google_docs_document_ops_registry.json'

def WATCHER():
    return ROOT() / 'legacy-openclaw/workspace/tools/work_manual_watcher.py'

def WORK_MANUAL_CHANNEL():
    return site_text('PDONE_WORK_MANUAL_CHANNEL')

def _u16_len(text: str) -> int:
    return len(text.encode('utf-16-le')) // 2

def _paragraph_text(paragraph: dict[str, Any]) -> str:
    chunks = []
    for element in paragraph.get('elements') or []:
        text_run = element.get('textRun')
        if text_run:
            chunks.append(text_run.get('content') or '')
    return ''.join(chunks)

def _body(doc: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    tab = (doc.get('tabs') or [None])[0]
    if not tab:
        raise RuntimeError('source document has no tabs')
    tab_id = tab.get('tabProperties', {}).get('tabId') or 't.0'
    content = tab['documentTab']['body']['content']
    return (content, tab_id)

def _element_summary(block: dict[str, Any]) -> dict[str, Any]:
    start = block.get('startIndex')
    end = block.get('endIndex')
    if 'paragraph' in block:
        para = block['paragraph']
        style = (para.get('paragraphStyle') or {}).get('namedStyleType')
        text = _paragraph_text(para).replace('\n', '\\n').replace('\x0b', '\\v')
        return {'kind': 'paragraph', 'start': start, 'end': end, 'style': style, 'text': text[:180]}
    if 'tableOfContents' in block:
        return {'kind': 'tableOfContents', 'start': start, 'end': end}
    if 'sectionBreak' in block:
        return {'kind': 'sectionBreak', 'start': start, 'end': end}
    if 'table' in block:
        return {'kind': 'table', 'start': start, 'end': end}
    return {'kind': 'other', 'start': start, 'end': end, 'keys': sorted(block.keys())}

def _drive_get(client: Any, path: str) -> dict[str, Any]:
    return client._request('GET', 'https://www.googleapis.com/drive/v3/' + path)

def _drive_post(client: Any, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return client._request('POST', 'https://www.googleapis.com/drive/v3/' + path, payload)

def _find_existing(client: Any) -> list[dict[str, Any]]:
    query = f"name = '{DOC_TITLE}' and '{PARENT_FOLDER_ID()}' in parents and mimeType = 'application/vnd.google-apps.document' and trashed = false"
    params = urllib.parse.urlencode({'q': query, 'fields': 'files(id,name,mimeType,parents)', 'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true', 'pageSize': '10'})
    data = _drive_get(client, 'files?' + params)
    return list(data.get('files') or [])

def _permissions(client: Any, file_id: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({'supportsAllDrives': 'true', 'fields': 'permissions(id,type,role,emailAddress)', 'pageSize': '100'})
    data = _drive_get(client, f'files/{file_id}/permissions?{params}')
    out = []
    for item in data.get('permissions') or []:
        out.append({'email': item.get('emailAddress') or '', 'type': item.get('type') or '', 'role': item.get('role') or ''})
    return out

def _folder_excluded_note(perms: list[dict[str, Any]]) -> str:
    hits = []
    for item in perms:
        email = str(item.get('email') or '').casefold()
        if email in {value.casefold() for value in EXCLUDED_GROUPS()}:
            hits.append(f'{item.get('email')} {item.get('type')} {item.get('role')}')
    if not hits:
        return 'Parent folder permission list has none of the excluded groups.'
    return 'Parent folder already grants excluded groups: ' + '; '.join(hits) + '. Folder ACL was not changed.'

def _has_page_number(doc: dict[str, Any]) -> bool:
    blob = json.dumps(doc.get('tabs') or doc, ensure_ascii=False)
    return '"PAGE_NUMBER"' in blob or '"pageNumber"' in blob

def _headings(doc: dict[str, Any]) -> list[str]:
    content, _tab_id = _body(doc)
    names = []
    for block in content:
        para = block.get('paragraph')
        if not para:
            continue
        style = (para.get('paragraphStyle') or {}).get('namedStyleType') or ''
        if style.startswith('HEADING'):
            names.append(_paragraph_text(para).strip())
    return names

def _molding_left(doc: dict[str, Any]) -> bool:
    headings = '\n'.join(_headings(doc))
    body_bits = []
    content, _tab_id = _body(doc)
    for block in content:
        para = block.get('paragraph')
        if para:
            body_bits.append(_paragraph_text(para))
    text = headings + '\n' + '\n'.join(body_bits)
    return any((marker in text for marker in MOLDING_MARKERS))

def _source_outline(doc: dict[str, Any]) -> list[dict[str, Any]]:
    content, _tab_id = _body(doc)
    return [_element_summary(block) for block in content[:25]]

def _replace_title_requests(doc: dict[str, Any], tab_id: str) -> list[dict[str, Any]]:
    content, _resolved = _body(doc)
    pairs = []
    for block in content:
        para = block.get('paragraph')
        if not para:
            continue
        style = (para.get('paragraphStyle') or {}).get('namedStyleType') or ''
        if style.startswith('HEADING'):
            break
        text = _paragraph_text(para)
        if '成型-非作業員' not in text and 'Injection Molding Staff' not in text:
            continue
        start = int(block['startIndex'])
        end = int(block['endIndex'])
        pairs.append((start, end, 'ERP\x0bPro-Design Work Guidelines and Procedures Manual:\x0bERP'))
    requests = []
    for start, end, new_text in sorted(pairs, reverse=True):
        requests.append({'deleteContentRange': {'range': {'startIndex': start, 'endIndex': end - 1, 'tabId': tab_id}}})
        requests.append({'insertText': {'location': {'index': start, 'tabId': tab_id}, 'text': new_text}})
    return requests

def _template_text() -> str:
    return f'變更日誌 Changelog\n{HEADER_DATE}: 建立 ERP 工作手冊空白模板。\x0bCreated the barebones ERP work manual template.\n使用範圍 Scope\n本手冊供 ERP 使用者使用。本手冊不適用於作業員群組、molding-staff 群組與 printing 群組。目前沒有生效的操作規則。\x0bThis manual is for ERP users. This manual does not apply to the operator, molding-staff, or printing groups. No operating rule is in force yet.\n手冊狀態 Manual Status\n這是空白模板。曾立銘之後會提供程序。不要把此模板當成已發行的 ISO 規則。\x0bThis is a barebones template. Tseng Li-Ming will supply procedures later. Do not treat this template as an issued ISO rule.\n程序區 Procedure Area\n目前沒有寫入任何程序。只有在負責人提供內容後，才新增程序。\x0bNo procedure is written yet. Add a procedure only after the owner supplies it.\n待補資料 Open Items\n程序文字、畫面截圖與表單名稱尚未加入。\x0bProcedure text, screenshots, and form names are not added yet.\n'

def _cut_index(doc: dict[str, Any]) -> int:
    content, _tab_id = _body(doc)
    title_end = 1
    for block in content:
        if 'tableOfContents' in block:
            return int(block['startIndex'])
        para = block.get('paragraph')
        if not para:
            continue
        style = (para.get('paragraphStyle') or {}).get('namedStyleType') or ''
        text = _paragraph_text(para).strip()
        if style.startswith('HEADING') or text.startswith('變更日誌'):
            return int(block['startIndex'])
        if style == 'TITLE' or text:
            title_end = int(block['endIndex'])
    return title_end

def _body_end(doc: dict[str, Any]) -> int:
    content, _tab_id = _body(doc)
    if not content:
        raise RuntimeError('document body is empty')
    return int(content[-1]['endIndex'])

def _style_new_headings(doc: dict[str, Any], tab_id: str) -> list[dict[str, Any]]:
    wanted = {'變更日誌 Changelog', '使用範圍 Scope', '手冊狀態 Manual Status', '程序區 Procedure Area', '待補資料 Open Items'}
    content, _resolved = _body(doc)
    requests = []
    for block in content:
        para = block.get('paragraph')
        if not para:
            continue
        text = _paragraph_text(para).strip()
        if text not in wanted:
            continue
        requests.append({'updateParagraphStyle': {'range': {'startIndex': int(block['startIndex']), 'endIndex': int(block['endIndex']), 'tabId': tab_id}, 'paragraphStyle': {'namedStyleType': 'HEADING_1'}, 'fields': 'namedStyleType'}})
    return requests

def _header_requests(docs_module: Any, doc: dict[str, Any], tab_id: str) -> list[dict[str, Any]]:
    style, resolved_tab_id = docs_module.document_style(doc, tab_id)
    requests: list[dict[str, Any]] = []
    prefix = '最近更新時間 Last updated: '
    date_start = _u16_len(prefix)
    date_end = date_start + _u16_len(HEADER_DATE)
    for key in ('defaultHeaderId', 'firstPageHeaderId'):
        header_id = style.get(key)
        if not header_id:
            continue
        built = docs_module.build_set_header_text_requests(doc, header_id, HEADER_TEXT, resolved_tab_id)
        for request in built.get('requests') or []:
            insert = request.get('insertText')
            if insert and 'location' not in insert and ('endOfSegmentLocation' not in insert) and ('index' in insert):
                location = {key: insert.pop(key) for key in ('index', 'tabId', 'segmentId') if key in insert}
                insert['location'] = location
            requests.append(request)
        requests.extend([{'updateTextStyle': {'range': {'segmentId': header_id, 'startIndex': 0, 'endIndex': date_end + 1, 'tabId': resolved_tab_id}, 'textStyle': {'backgroundColor': {}}, 'fields': 'backgroundColor'}}, {'updateTextStyle': {'range': {'segmentId': header_id, 'startIndex': date_start, 'endIndex': date_end, 'tabId': resolved_tab_id}, 'textStyle': {'backgroundColor': YELLOW}, 'fields': 'backgroundColor'}}, {'updateTextStyle': {'range': {'segmentId': header_id, 'startIndex': date_end, 'endIndex': date_end + 1, 'tabId': resolved_tab_id}, 'textStyle': {'backgroundColor': {}}, 'fields': 'backgroundColor'}}])
    return requests

def _yellow_changelog_date(doc: dict[str, Any], tab_id: str) -> list[dict[str, Any]]:
    content, _resolved = _body(doc)
    prefix = f'{HEADER_DATE}: '
    for block in content:
        para = block.get('paragraph')
        if not para:
            continue
        text = _paragraph_text(para)
        if not text.startswith(prefix):
            continue
        start = int(block['startIndex'])
        date_end = start + _u16_len(HEADER_DATE)
        return [{'updateTextStyle': {'range': {'startIndex': start, 'endIndex': date_end, 'tabId': tab_id}, 'textStyle': {'backgroundColor': YELLOW}, 'fields': 'backgroundColor'}}]
    return []

def _register(doc_id: str) -> dict[str, Any]:
    updated = []
    manifest_entry = {'id': doc_id, 'name': DOC_TITLE, 'category': 'work-manual'}
    for path in (LEGACY_MANIFEST(), PROFILE_MANIFEST()):
        if not path.is_file():
            continue
        if PROFILE_MANIFEST() != LEGACY_MANIFEST() and path == PROFILE_MANIFEST():
            try:
                if os.path.samefile(LEGACY_MANIFEST(), PROFILE_MANIFEST()):
                    continue
            except OSError:
                logging.getLogger('pd_one_ops').exception('pd one command failed')
        data = json.loads(path.read_text(encoding='utf-8'))
        docs = data.setdefault('docs', [])
        if not any((item.get('id') == doc_id for item in docs)):
            docs.append(manifest_entry)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        updated.append(str(path))
    routing = json.loads(ROUTING_PATH().read_text(encoding='utf-8'))
    sibling = routing['documents'].get(site_text('PDONE_GDOC_3')) or next(iter(routing['documents'].values()))
    routing['documents'][doc_id] = {'name': DOC_TITLE, 'channel': sibling.get('channel', 'n8n'), 'enabled': True, 'note': 'Cross-department ERP manual. Notices go to the Work Manual channel until a dedicated ERP channel exists.', 'targets': [f'channel:{WORK_MANUAL_CHANNEL()}'], 'delivery': sibling.get('delivery', 'n8n_webhook'), 'webhookUrl': sibling.get('webhookUrl'), 'n8nWorkflowId': sibling.get('n8nWorkflowId')}
    ROUTING_PATH().write_text(json.dumps(routing, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    registry = json.loads(REGISTRY_PATH().read_text(encoding='utf-8'))
    registry['documents']['erp_manual'] = {'document_id': doc_id, 'title': DOC_TITLE, 'scope': 'work-manual', 'live_enabled': True, 'allowed_actions': ['inspect', 'verify_readback', 'unique_text_patch', 'insert_section_before_heading', 'set_header_text', 'append_changelog']}
    REGISTRY_PATH().write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'manifest_paths_updated': updated, 'routing_updated': True, 'registry_updated': True}

def _watcher_dry_run(doc_id: str) -> str:
    if not WATCHER().is_file():
        return 'watcher_script_missing'
    proc = subprocess.run([sys.executable, str(WATCHER()), '--dry-run', '--doc-id', doc_id], text=True, capture_output=True, timeout=180, check=False)
    text = (proc.stdout or '') + (proc.stderr or '')
    if 'unchanged' in text.casefold():
        return 'unchanged'
    if proc.returncode == 0:
        return 'dry_run_exit_0'
    return f'dry_run_exit_{proc.returncode}'

def bootstrap_erp_work_manual(*, requester_user_id: str, dry_run: bool, confirm_live_write: Optional[str], idempotency_key: Optional[str], docs_module: Any=None, client: Any=None) -> dict[str, Any]:
    if str(requester_user_id or '') != ANDY_ID():
        return {'status': 'error', 'error': 'not_authorized', 'detail': 'ERP manual bootstrap accepts only the exact Owner sender id'}
    if not dry_run and confirm_live_write != LIVE_CONFIRMATION:
        return {'status': 'error', 'error': 'confirmation_required', 'detail': 'live bootstrap requires the Google Docs live confirmation'}
    if not dry_run and (not str(idempotency_key or '').strip()):
        return {'status': 'error', 'error': 'idempotency_required', 'detail': 'live bootstrap requires an idempotency key'}
    if docs_module is None:
        docs_api = ROOT() / 'legacy-openclaw/workspace/scripts/google/docs_api.py'
        import importlib.util
        spec = importlib.util.spec_from_file_location('pdone_docs_api_for_erp_bootstrap', docs_api)
        if spec is None or spec.loader is None:
            raise RuntimeError('unable to load docs_api')
        docs_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs_module)
    docs_client = client or docs_module.DocsClient(ACCOUNT())
    existing = _find_existing(docs_client)
    folder_perms = _permissions(docs_client, PARENT_FOLDER_ID())
    source = docs_client.get_document(SOURCE_DOC_ID(), 'PREVIEW_WITHOUT_SUGGESTIONS')
    plan = {'status': 'ok', 'action': 'bootstrap_erp_work_manual', 'dry_run': True, 'title': DOC_TITLE, 'parent_id': PARENT_FOLDER_ID(), 'source_doc_id': SOURCE_DOC_ID(), 'existing_files': existing, 'source_outline': _source_outline(source), 'writer_groups': list(WRITER_GROUPS()), 'excluded_groups': list(EXCLUDED_GROUPS()), 'inherited_folder_acl_note': _folder_excluded_note(folder_perms), 'header_text': HEADER_TEXT, 'page_number_on_source': _has_page_number(source)}
    if dry_run:
        return plan
    if len(existing) > 1:
        return {'status': 'error', 'error': 'ambiguous_existing_doc', 'detail': 'more than one ERP manual title exists in the target folder', 'existing_files': existing}
    if existing:
        doc_id = existing[0]['id']
        created = False
    else:
        copied = _drive_post(docs_client, f'files/{SOURCE_DOC_ID()}/copy?supportsAllDrives=true', {'name': DOC_TITLE, 'parents': [PARENT_FOLDER_ID()]})
        doc_id = copied['id']
        created = True
    doc = docs_client.get_document(doc_id, 'PREVIEW_WITHOUT_SUGGESTIONS')
    content, tab_id = _body(doc)
    cut = _cut_index(doc)
    end = _body_end(doc)
    requests: list[dict[str, Any]] = []
    if end - 1 > cut:
        requests.append({'deleteContentRange': {'range': {'startIndex': cut, 'endIndex': end - 1, 'tabId': tab_id}}})
    requests.append({'insertText': {'location': {'index': cut, 'tabId': tab_id}, 'text': _template_text()}})
    docs_client.batch_update(doc_id, requests)
    doc = docs_client.get_document(doc_id, 'PREVIEW_WITHOUT_SUGGESTIONS')
    _content, tab_id = _body(doc)
    style_requests = _style_new_headings(doc, tab_id)
    title_requests = _replace_title_requests(doc, tab_id)
    follow_requests = title_requests + style_requests
    if follow_requests:
        docs_client.batch_update(doc_id, follow_requests)
    doc = docs_client.get_document(doc_id, 'PREVIEW_WITHOUT_SUGGESTIONS')
    _content, tab_id = _body(doc)
    header_requests = _header_requests(docs_module, doc, tab_id)
    yellow = _yellow_changelog_date(doc, tab_id)
    final_requests = header_requests + yellow
    if final_requests:
        docs_client.batch_update(doc_id, final_requests)
    doc = docs_client.get_document(doc_id, 'PREVIEW_WITHOUT_SUGGESTIONS')
    molding_left = _molding_left(doc)
    if molding_left:
        return {'status': 'error', 'error': 'molding_text_remains', 'detail': 'ERP manual still contains molding source text. Sharing was not run.', 'doc_id': doc_id, 'url': f'https://docs.google.com/document/d/{doc_id}/edit', 'created': created}
    share_results = []
    current_perms = _permissions(docs_client, doc_id)
    have = {(str(item.get('email') or '').casefold(), item.get('type'), item.get('role')) for item in current_perms}
    for email in WRITER_GROUPS():
        if (email.casefold(), 'group', 'writer') in have:
            share_results.append({'email': email, 'type': 'group', 'role': 'writer', 'action': 'already_present'})
            continue
        created_perm = _drive_post(docs_client, f'files/{doc_id}/permissions?supportsAllDrives=true&sendNotificationEmail=false', {'type': 'group', 'role': 'writer', 'emailAddress': email})
        share_results.append({'email': email, 'type': created_perm.get('type'), 'role': created_perm.get('role'), 'action': 'created'})
    readback = _permissions(docs_client, doc_id)
    group_writers = {str(item.get('email') or '').casefold() for item in readback if item.get('type') == 'group' and item.get('role') == 'writer'}
    missing = [email for email in WRITER_GROUPS() if email.casefold() not in group_writers]
    excluded_present = [item for item in readback if str(item.get('email') or '').casefold() in {value.casefold() for value in EXCLUDED_GROUPS()}]
    registration = _register(doc_id)
    watcher_status = _watcher_dry_run(doc_id)
    headers = []
    for header in (doc.get('headers') or {}).values():
        texts = []
        for block in header.get('content') or []:
            para = block.get('paragraph')
            if para:
                texts.append(_paragraph_text(para).strip())
        if texts:
            headers.append(' '.join(texts))
    return {'status': 'ok' if not missing and (not excluded_present) and (not molding_left) else 'error', 'action': 'bootstrap_erp_work_manual', 'dry_run': False, 'created': created, 'doc_id': doc_id, 'url': f'https://docs.google.com/document/d/{doc_id}/edit', 'title': DOC_TITLE, 'parent_id': PARENT_FOLDER_ID(), 'header_text': headers, 'page_number_autotext_present': _has_page_number(doc), 'body_has_molding_procedure_text': molding_left, 'headings': _headings(doc), 'share_results': share_results, 'share_readback': [item for item in readback if str(item.get('email') or '').casefold().endswith('@prodesign-group.com')], 'missing_writer_groups': missing, 'excluded_groups_on_file': excluded_present, 'excluded_groups_absent': not excluded_present, 'inherited_folder_acl_note': _folder_excluded_note(folder_perms), 'watcher_dry_run_status': watcher_status, **registration}

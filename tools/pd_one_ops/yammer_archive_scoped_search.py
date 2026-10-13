#!/usr/bin/env python3
"""Scoped read-only Yammer/Viva Engage archive search for PD One."""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import os
import argparse
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

def ROOT():
    return Path(resolve_configured_path('~/.hermes/profiles/pdone'))

def POLICY_USERS():
    return ROOT() / 'policies/mattermost-users.json'

def POLICY_CACHE_DIR():
    return ROOT() / 'policy-cache/mattermost/users'

def YAMMER_DB():
    return ROOT() / 'legacy-openclaw/workspace/projects/yammer-migration/archive/search/yammer_archive.sqlite'

def INTER_DEPT_CHANNEL_ID():
    return site_text('PDONE_INTER_DEPT_CHANNEL_ID')
DOMAIN_RULES: dict[str, dict[str, list[str]]] = {'finance': {'query': ['\\bfinance\\b', '\\bfinancial\\b', '\\baccounting\\b', '\\binvoice\\b', '\\btax\\b', '\\bforex\\b', '\\bbudget\\b', '財務', '會計', '帳務', '應收', '應付', '發票', '匯率', '預算'], 'group': ['財務', 'finance', 'accounting', 'forex', '匯率'], 'content': ['財務', '會計', '應收', '應付', '匯率', 'forex']}, 'payroll': {'query': ['\\bpayroll\\b', '\\bsalary\\b', '\\bwages?\\b', '\\bbonus\\b', '薪資', '薪水', '工資', '加班費', '獎金', '年終'], 'group': ['薪資', 'payroll'], 'content': ['薪資', '薪水', 'payroll', '加班費']}, 'hr_private': {'query': ['\\bperformance review\\b', '\\bdisciplinary\\b', '\\btermination\\b', '考績', '懲處', '解雇', '資遣', '個資', '隱私'], 'group': ['考績', 'hr private', 'performance'], 'content': ['考績', '懲處', '解雇', '資遣', '個資']}, 'credentials_admin': {'query': ['\\bpassword\\b', '\\bapi key\\b', '\\btoken\\b', '\\bsecret\\b', '\\bcredential\\b', '密碼', '金鑰', '憑證', '密鑰', '系統設定'], 'group': ['credential', 'admin secret'], 'content': ['password\\s*=', 'api[_-]?key', 'BEGIN (RSA |OPENSSH )?PRIVATE KEY']}, 'quality': {'query': ['\\bqa\\b', '\\bquality\\b', '\\bsip\\b', '\\bleak\\b', '測漏', '品保', '品質', '客訴', '稀釋', '\\bpg\\b', '酒精', '檢驗'], 'group': ['品質', 'quality', 'sip', '品保'], 'content': ['測漏', '品保', '品質', 'SIP', '客訴', '檢驗']}, 'production': {'query': ['production', 'schedule', 'mold', '成型', '生產', '排程', '模具', '產銷'], 'group': ['production', '產銷', '成型', '模具', 'mold'], 'content': ['生產', '排程', '模具', '成型', '產銷']}, 'rd': {'query': ['research', '工程', '技術發展', '試模', 'T0'], 'group': ['技術', '工程', 'mold', '研發'], 'content': ['技術發展', '試模', '工程', '研發']}, 'sales': {'query': ['\\bsales\\b', '業務', '出貨', '交期'], 'group': ['業務', 'sales'], 'content': ['業務', '出貨', '交期']}, 'operations': {'query': ['sop', 'work manual', '作業', '流程', '公告', '設施', '維修'], 'group': ['announcement', '設施', 'facilities', '公司'], 'content': ['作業指導', '流程', '公告']}}
DATAACCESS_DOMAIN_BLOCKS = {'financeRecords': ['finance'], 'payroll': ['payroll', 'finance'], 'bonusCompensation': ['payroll'], 'hrEvaluations': ['hr_private'], 'hrPrivateRecords': ['hr_private'], 'privatePersonnel': ['hr_private'], 'disciplineRecords': ['hr_private'], 'credentials': ['credentials_admin'], 'adminConfig': ['credentials_admin'], 'policyFiles': ['credentials_admin']}
ALWAYS_BLOCKED_FOR_NON_ADMIN = {'credentials_admin'}
ADMIN_ROLES = {'admin'}
YAMMER_BASE_ROLES = {'admin', 'executive_data_access', 'key_employee_operations', 'operational_employee_default', 'qa_lead', 'qa_engineer', 'product_quality_readonly', 'production_scheduler', 'production_schedule_lead', 'procurement_manager', 'mold_repair_head', 'facilities_logistics_lead', 'facilities_logistics_assistant', 'sales_member', 'research_development'}

def _is_denied(value: Any) -> bool:
    s = str(value or '').strip().lower()
    if not s:
        return False
    if s in {'deny', 'denied', 'false', 'never', 'no'}:
        return True
    return s.startswith('deny')

def _is_allowish(value: Any) -> bool:
    s = str(value or '').strip().lower()
    if not s or _is_denied(s):
        return False
    return any((tok in s for tok in ('read', 'allow', 'summar', 'search', 'draft', 'write', 'confirm', 'create')))

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))

def load_sender_policy(sender_id: str) -> dict[str, Any]:
    cache_path = POLICY_CACHE_DIR() / f'{sender_id}.json'
    if cache_path.exists():
        data = load_json(cache_path)
        data['_policySource'] = f'policy-cache:{cache_path.name}'
        return data
    users = load_json(POLICY_USERS()).get('users') or {} if POLICY_USERS().exists() else {}
    profile = users.get(sender_id) or {}
    if not profile:
        return {'found': False, 'active': False, 'roles': [], 'dataAccess': {}, '_policySource': 'missing'}
    return {'found': True, 'active': profile.get('status') == 'active', 'roles': profile.get('roles') or [], 'dataAccess': profile.get('dataAccess') or {}, 'channels': profile.get('channels') or {}, 'tools': profile.get('tools') or {}, '_policySource': 'mattermost-users.json'}

def detect_domains(text: str, field: str='query') -> list[str]:
    hits: list[str] = []
    for domain, rules in DOMAIN_RULES.items():
        for pat in rules.get(field) or []:
            if re.search(pat, text or '', re.I):
                hits.append(domain)
                break
    return hits

def compact_excerpt(text: str, limit: int=320) -> str:
    cleaned = re.sub('\\s+', ' ', (text or '').replace('\x00', ' ')).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit - 1].rstrip() + '…'

def sanitize_fts_query(query: str) -> str:
    q = (query or '').strip()
    if not q:
        return ''
    parts = re.findall('[\\u4e00-\\u9fff]{1,12}|[A-Za-z0-9][A-Za-z0-9._\\-/]{0,40}', q)
    seen: set[str] = set()
    tokens: list[str] = []
    stop = {'and', 'or', 'not', 'near'}
    for p in parts:
        key = p.lower()
        if key in stop:
            continue
        if key in seen:
            continue
        seen.add(key)
        tokens.append(p)
    if not tokens:
        safe = re.sub('[^\\w\\u4e00-\\u9fff\\s\\-:./]+', ' ', q, flags=re.U)
        safe = ' '.join(safe.split())
        return f'"{safe}"' if safe else ''
    tokens = tokens[:12]
    out: list[str] = []
    for t in tokens:
        if any((ch in t for ch in ' -./')):
            out.append(f'"{t}"')
        else:
            out.append(t)
    return ' OR '.join(out)

@dataclass
class ScopeDecision:
    allowed: bool
    reason: str
    roles: list[str]
    allowed_domains: list[str]
    blocked_domains: list[str]
    is_admin: bool
    policy_source: str
    authorization_basis: str

def resolve_scope(policy: dict[str, Any], origin_channel_id: str | None=None) -> ScopeDecision:
    roles = [str(r) for r in policy.get('roles') or []]
    data_access = policy.get('dataAccess') or {}
    is_admin = bool(ADMIN_ROLES.intersection(roles))
    active = True
    if policy.get('found') is False:
        active = False
    if 'active' in policy:
        active = bool(policy.get('active'))
    if policy.get('status') == 'inactive':
        active = False
    if not active:
        return ScopeDecision(False, 'sender_not_active_profiled_user', roles, [], sorted(DOMAIN_RULES.keys()), is_admin, str(policy.get('_policySource') or ''), 'exact sender id + policy profile')
    blocked: set[str] = set()
    for key, domains in DATAACCESS_DOMAIN_BLOCKS.items():
        if key in data_access and _is_denied(data_access.get(key)):
            blocked.update(domains)
    if not is_admin:
        blocked |= set(ALWAYS_BLOCKED_FOR_NON_ADMIN)
    base_allow = is_admin or bool(set(roles) & YAMMER_BASE_ROLES)
    if _is_allowish(data_access.get('companyKnowledge')) or _is_allowish(data_access.get('operationalDocs')):
        base_allow = True
    if _is_allowish(data_access.get('workManuals')) or _is_allowish(data_access.get('qualityStandards')):
        base_allow = True
    if origin_channel_id == INTER_DEPT_CHANNEL_ID() and (is_admin or 'key_employee_operations' in roles or 'operational_employee_default' in roles or ('qa_lead' in roles)):
        base_allow = True
    if is_admin or 'executive_data_access' in roles:
        if is_admin:
            blocked = set()
            allowed_domains = list(DOMAIN_RULES.keys())
        else:
            allowed_domains = [d for d in DOMAIN_RULES.keys() if d not in blocked]
        return ScopeDecision(True, 'admin_or_executive_broad_business_access', roles, allowed_domains, sorted(blocked), is_admin, str(policy.get('_policySource') or ''), 'admin/executive role + dataAccess denials')
    if not base_allow:
        return ScopeDecision(False, 'yammer_archive_not_in_requester_scope', roles, [], sorted(set(DOMAIN_RULES) | blocked), False, str(policy.get('_policySource') or ''), 'exact sender id + role/dataAccess scope')
    allowed = {'operations', 'quality', 'production', 'rd', 'sales'}
    allowed -= blocked
    if not _is_denied(data_access.get('financeRecords')) and _is_allowish(data_access.get('financeRecords')):
        allowed.add('finance')
    if 'product_quality_readonly' in roles or 'qa_lead' in roles or 'qa_engineer' in roles:
        allowed.update({'quality', 'operations', 'production'})
    if 'sales_member' in roles:
        allowed.add('sales')
    return ScopeDecision(True, 'scoped_company_knowledge_yammer_access', roles, sorted(allowed), sorted(blocked), False, str(policy.get('_policySource') or ''), 'exact sender id + role/dataAccess + optional Inter-Dept channel context')

def classify_hit(group_name: str, excerpt: str, filename: str='') -> list[str]:
    blob = f'{group_name}\n{filename}\n{excerpt}'
    domains = set(detect_domains(blob, 'group')) | set(detect_domains(blob, 'content'))
    if not domains:
        domains.add('operations')
    return sorted(domains)

def hit_allowed(hit_domains: list[str], scope: ScopeDecision) -> bool:
    if scope.is_admin:
        return True
    if any((d in scope.blocked_domains for d in hit_domains)):
        return False
    if not hit_domains:
        return 'operations' in scope.allowed_domains
    return any((d in scope.allowed_domains for d in hit_domains))

def open_db(db_path: Path=None) -> sqlite3.Connection:
    if db_path is None:
        db_path = YAMMER_DB()
    if not db_path.exists():
        raise FileNotFoundError(f'Yammer archive DB missing: {db_path}')
    con = sqlite3.connect(f'file:{db_path}?mode=ro&immutable=1', uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    con.execute('PRAGMA busy_timeout=5000')
    return con

def run_fts(con: sqlite3.Connection, fts_query: str, limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        rows = con.execute('SELECT message_id, thread_id, group_name, sender_name, title, body FROM messages_fts WHERE messages_fts MATCH ? LIMIT ?', (fts_query, limit)).fetchall()
    except sqlite3.OperationalError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        rows = []
    for r in rows:
        excerpt = compact_excerpt((r['title'] or '') + ' ' + (r['body'] or ''))
        results.append({'kind': 'message', 'messageId': r['message_id'], 'threadId': r['thread_id'], 'groupName': r['group_name'] or '', 'senderName': r['sender_name'] or '', 'title': r['title'] or '', 'fileName': '', 'excerpt': excerpt})
    try:
        rows = con.execute('SELECT file_id, version_id, message_id, thread_id, group_name, filename, description, text FROM attachments_fts WHERE attachments_fts MATCH ? LIMIT ?', (fts_query, limit)).fetchall()
    except sqlite3.OperationalError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        rows = []
    for r in rows:
        excerpt = compact_excerpt((r['filename'] or '') + ' ' + (r['description'] or '') + ' ' + (r['text'] or ''))
        results.append({'kind': 'attachment', 'messageId': r['message_id'] or '', 'threadId': r['thread_id'] or '', 'groupName': r['group_name'] or '', 'senderName': '', 'title': r['filename'] or '', 'fileName': r['filename'] or '', 'fileId': r['file_id'], 'versionId': r['version_id'], 'excerpt': excerpt})
    return results

def search_yammer_archive(sender_id: str, query: str, origin_channel_id: str | None=None, max_results: int=15, db_path: Path=None) -> dict[str, Any]:
    if db_path is None:
        db_path = YAMMER_DB()
    t0 = time.time()
    sender_id = (sender_id or '').strip()
    query = (query or '').strip()
    origin_channel_id = (origin_channel_id or '').strip() or None
    max_results = max(1, min(int(max_results), 30))
    sources_searched = [{'source': 'yammer_viva_engage_local_archive', 'dbPath': str(db_path), 'indexes': ['messages_fts', 'attachments_fts'], 'mode': 'read_only_immutable_sqlite_fts'}]
    if not re.fullmatch('[a-z0-9]{16,}', sender_id):
        return {'status': 'blocked', 'reason': 'invalid_sender_id', 'sources_searched': sources_searched, 'resultCount': 0, 'results': [], 'replyGuidance': 'State requester id invalid; no archive search ran.'}
    if not query:
        return {'status': 'blocked', 'reason': 'query_required', 'sources_searched': sources_searched, 'resultCount': 0, 'results': [], 'replyGuidance': 'Ask for a concrete search query.'}
    policy = load_sender_policy(sender_id)
    scope = resolve_scope(policy, origin_channel_id)
    query_domains = detect_domains(query, 'query') or ['operations']
    base_payload: dict[str, Any] = {'capability': 'pd_one_yammer_archive_search', 'senderId': sender_id, 'query': query, 'originChannelId': origin_channel_id or '', 'queryDomainsDetected': query_domains, 'scope': {'allowed': scope.allowed, 'reason': scope.reason, 'roles': scope.roles, 'allowedDomains': scope.allowed_domains, 'blockedDomains': scope.blocked_domains, 'isAdmin': scope.is_admin, 'policySource': scope.policy_source, 'authorizationBasis': scope.authorization_basis}, 'sources_searched': sources_searched, 'safety': {'readOnly': True, 'rawTranscriptDumps': 'denied; bounded excerpts only', 'sourceSystemWrites': 'denied', 'externalSends': 'denied', 'botAdminVisibilityIgnored': True, 'domainFilter': 'blocked domains removed even when base Yammer access is allowed'}, 'replyGuidance': 'In the user-facing bilingual reply, always include a concrete Sources checked / 已查來源 section listing every source actually searched, plus any blocked/out-of-scope domains. Do not claim a full historical check unless Yammer archive and relevant Mattermost scopes were searched.'}
    if not scope.allowed:
        return {**base_payload, 'status': 'blocked', 'reason': scope.reason, 'resultCount': 0, 'results': [], 'filteredOutCount': 0, 'elapsedMs': int((time.time() - t0) * 1000)}
    high_risk = {'finance', 'payroll', 'hr_private', 'credentials_admin'}
    if any((d in scope.blocked_domains for d in query_domains if d in high_risk)):
        blocked_hits = [d for d in query_domains if d in scope.blocked_domains]
        return {**base_payload, 'status': 'blocked', 'reason': 'query_domain_out_of_scope', 'blockedQueryDomains': blocked_hits, 'resultCount': 0, 'results': [], 'filteredOutCount': 0, 'elapsedMs': int((time.time() - t0) * 1000), 'userMessage': 'Search asks for out-of-scope domains (' + ', '.join(blocked_hits) + '). Refused without searching archive content.'}
    fts_query = sanitize_fts_query(query)
    sources_searched[0]['ftsQuery'] = fts_query
    sources_searched[0]['maxResultsPerIndex'] = max_results
    try:
        con = open_db(db_path)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {**base_payload, 'status': 'error', 'reason': 'db_open_failed', 'error': str(exc)[:300], 'resultCount': 0, 'results': [], 'elapsedMs': int((time.time() - t0) * 1000)}
    try:
        raw_hits = run_fts(con, fts_query, max_results)
    except Exception as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {**base_payload, 'status': 'error', 'reason': 'fts_failed', 'error': str(exc)[:300], 'resultCount': 0, 'results': [], 'elapsedMs': int((time.time() - t0) * 1000)}
    finally:
        con.close()
    kept: list[dict[str, Any]] = []
    filtered = 0
    for hit in raw_hits:
        domains = classify_hit(hit.get('groupName', ''), hit.get('excerpt', ''), hit.get('fileName', ''))
        if not hit_allowed(domains, scope):
            filtered += 1
            continue
        kept.append({**hit, 'domains': domains, 'provenance': {'archive': 'yammer_viva_engage_local_sqlite', 'groupName': hit.get('groupName') or '', 'messageId': hit.get('messageId') or '', 'threadId': hit.get('threadId') or '', 'fileName': hit.get('fileName') or ''}})
        if len(kept) >= max_results:
            break
    return {**base_payload, 'status': 'ok', 'reason': 'ok', 'ftsQuery': fts_query, 'rawHitCount': len(raw_hits), 'filteredOutCount': filtered, 'resultCount': len(kept), 'results': kept, 'elapsedMs': int((time.time() - t0) * 1000), 'sources_searched': sources_searched}

def main(argv: list[str] | None=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sender-id', required=True)
    ap.add_argument('--query', required=True)
    ap.add_argument('--origin-channel-id', default='')
    ap.add_argument('--max-results', type=int, default=15)
    ap.add_argument('--db', default=str(YAMMER_DB()))
    args = ap.parse_args(argv)
    out = search_yammer_archive(args.sender_id, args.query, args.origin_channel_id or None, args.max_results, Path(args.db))
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    return 0 if out.get('status') in {'ok', 'blocked'} else 2
if __name__ == '__main__':
    raise SystemExit(main())

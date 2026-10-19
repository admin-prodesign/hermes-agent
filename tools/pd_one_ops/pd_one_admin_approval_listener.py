#!/usr/bin/env python3
"""Deterministic Mattermost approval listener for bound PD One approval tickets."""
from __future__ import annotations
import logging
from tools.pd_one_ops.site_config import site_text, resolve_configured_path, external_path, profile_root, text_excludes_configured_hosts, ExternalModule, owner_display_name, repo_cli, package_file, kanban_boards_root
import os
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
try:
    from admin_approval_tickets import ApprovalLedger, DEFAULT_LEDGER_PATH, InvalidTransition
except ModuleNotFoundError:
    logging.getLogger('pd_one_ops').exception('pd one command failed')
    sys.path.append(str(Path(__file__).resolve().parent))
    from admin_approval_tickets import ApprovalLedger, DEFAULT_LEDGER_PATH, InvalidTransition

def DEFAULT_ANDY_USER_ID():
    return site_text('PDONE_OWNER_MM_USER_ID')

def DEFAULT_ADMIN_CHANNEL_ID():
    return site_text('PDONE_ADMIN_ALERT_CHANNEL_ID')
TICKET_ID_PATTERN = 'PDAPP-\\d{8}-[A-Z0-9]{8}'
STRICT_STANDALONE_ADMIN_DECISION_RE = re.compile(f'^admin\\s*[:：]\\s*(approve|reject)\\s+({TICKET_ID_PATTERN})$', re.I)
STRICT_BILINGUAL_ADMIN_DECISION_RE = re.compile(f'^管理員\\s*[:：]\\s*(核准|駁回)\\s+({TICKET_ID_PATTERN})$')
BILINGUAL_AUTOEDIT_MARKER = '<!-- bilingual-autoedit:v1 -->'
ALLOWED_EDIT_NORMALIZATIONS = {'bilingual-autoedit:v1', 'mention-translation:v1'}
MENTION_TOKEN_RE = re.compile('(?:^|\\s)@[A-Za-z0-9._-]+')
BOT_USERNAME_ALIASES = ('pdone', 'pd_one_bot')
BOT_MENTION_PATTERN = '@(?:' + '|'.join(re.escape(name) for name in BOT_USERNAME_ALIASES) + ')'
EXPLICIT_APPROVE_RE = re.compile(f'^(?:admin\\s*[:：]\\s*)?(?:approve|核准|批准|同意|通過)\\s+({TICKET_ID_PATTERN})(?:\\s+{BOT_MENTION_PATTERN})?(?:\\s+with:\\s+(.+))?$', re.I)
EXPLICIT_REJECT_RE = re.compile(f'^(?:admin\\s*[:：]\\s*)?(?:reject|駁回|拒絕|不同意|不核准|否決)\\s+({TICKET_ID_PATTERN})(?:\\s+{BOT_MENTION_PATTERN})?(?::\\s+(.+))?$', re.I)
BARE_RE = re.compile('^(approve|reject)$', re.I)
COMMENT_RE = re.compile('<!--.*?-->', re.S)
TRANSLATION_BLOCK_RE = re.compile('\\n\\s*---\\s*\\n\\s*\\*\\*Translation\\s*/\\s*翻譯(?:\\s*\\([^)]*\\))?\\s*:\\*\\*.*$', re.I | re.S)
APPROVAL_BARE_LINES = {'approve', 'approved', 'approval granted', 'i approve', 'yes approved', 'ok approved', 'okay approved', '已核准', '核准', '同意', '已同意', '批准', '已批准', '通過', '已通過', '准許', '已准許'}
REJECTION_BARE_LINES = {'reject', 'rejected', 'rejection denied', 'deny', 'denied', 'not approved', 'do not approve', 'i reject', 'no', '駁回', '拒絕', '不同意', '不核准', '未核准', '否決', '不批准'}

def as_string(value: Any) -> str:
    return str(value or '').strip()

def _raw_decision_lines(message: str) -> list[str]:
    text = COMMENT_RE.sub('', as_string(message))
    text = TRANSLATION_BLOCK_RE.sub('', text).strip()
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('>'):
            return []
        lines.append(line)
    return lines

def _decision_lines(message: str) -> list[str]:
    """Return meaningful bare-decision lines after removing harmless auto-edit markers."""
    lines = []
    for line in _raw_decision_lines(message):
        line = re.sub('[。.!！?？：:；;，,、]+$', '', line).strip()
        if line:
            lines.append(line)
    return lines

def _bare_line_decision(line: str) -> str | None:
    normalized = re.sub('\\s+', ' ', line.strip().lower())
    if normalized in REJECTION_BARE_LINES:
        return 'rejected'
    if normalized in APPROVAL_BARE_LINES:
        return 'approved'
    approval_patterns = ['^approved(?:\\s+by\\s+andy)?$', '^approval\\s+(?:is\\s+)?(?:granted|approved)$', '^andy\\s+approved$', '^i\\s+(?:approve|approved)\\s*(?:this|it)?$', '^(?:已)?(?:核准|批准|同意|通過|准許)(?:此|這個|這項)?(?:申請|請求|需求|事項)?$']
    rejection_patterns = ['^(?:not\\s+approved|approval\\s+denied|request\\s+denied)$', '^i\\s+(?:reject|rejected|deny|denied)\\s*(?:this|it)?$', '^(?:不|未)(?:核准|批准|同意|通過|准許)(?:此|這個|這項)?(?:申請|請求|需求|事項)?$', '^(?:已)?(?:駁回|拒絕|否決)(?:此|這個|這項)?(?:申請|請求|需求|事項)?$']
    if any((re.match(pattern, normalized, re.I) for pattern in rejection_patterns)):
        return 'rejected'
    if any((re.match(pattern, normalized, re.I) for pattern in approval_patterns)):
        return 'approved'
    return None

def parse_decision(message: str) -> dict[str, Any] | None:
    text = as_string(message)
    if not text:
        return None
    raw_lines = _raw_decision_lines(text)
    if not raw_lines:
        return None
    command_line = raw_lines[0]
    approve = EXPLICIT_APPROVE_RE.match(command_line)
    if approve:
        secondary = [(EXPLICIT_APPROVE_RE.match(line), EXPLICIT_REJECT_RE.match(line)) for line in raw_lines[1:]]
        if any((reject or (same and same.group(1).upper() != approve.group(1).upper()) for same, reject in secondary)):
            return None
        instruction_lines = [line for line, (same, reject) in zip(raw_lines[1:], secondary) if not same and (not reject)]
        instructions = as_string(approve.group(2)) or as_string('\n'.join(instruction_lines))
        return {'decision': 'approved', 'ticket_id': approve.group(1).upper(), 'instructions': instructions}
    reject = EXPLICIT_REJECT_RE.match(command_line)
    if reject:
        secondary = [(EXPLICIT_APPROVE_RE.match(line), EXPLICIT_REJECT_RE.match(line)) for line in raw_lines[1:]]
        if any((approve or (same and same.group(1).upper() != reject.group(1).upper()) for approve, same in secondary)):
            return None
        instruction_lines = [line for line, (approve, same) in zip(raw_lines[1:], secondary) if not approve and (not same)]
        instructions = as_string(reject.group(2)) or as_string('\n'.join(instruction_lines))
        return {'decision': 'rejected', 'ticket_id': reject.group(1).upper(), 'instructions': instructions}
    lines = _decision_lines(text)
    decisions = [_bare_line_decision(line) for line in lines]
    decisions = [decision for decision in decisions if decision]
    if decisions and len(decisions) == len(lines) and (len(set(decisions)) == 1):
        return {'decision': decisions[0], 'ticket_id': None, 'instructions': ''}
    return None

def _strip_mention_tokens(line: str) -> str:
    return ' '.join(MENTION_TOKEN_RE.sub(' ', as_string(line)).split())

def parse_strict_standalone_admin_decision(message: str) -> dict[str, str] | None:
    """Parse the only decision form allowed outside a ticket-bound thread."""
    original = as_string(message)
    had_mention_translation = bool(TRANSLATION_BLOCK_RE.search(original))
    stripped = TRANSLATION_BLOCK_RE.sub('', original).strip()
    lines = [_strip_mention_tokens(line) for line in stripped.splitlines() if _strip_mention_tokens(line)]
    if len(lines) == 1:
        match = STRICT_STANDALONE_ADMIN_DECISION_RE.fullmatch(lines[0])
        if not match:
            return None
        parsed = {'decision': 'approved' if match.group(1).lower() == 'approve' else 'rejected', 'ticket_id': match.group(2).upper(), 'instructions': ''}
        if had_mention_translation:
            parsed['normalization'] = 'mention-translation:v1'
        return parsed
    if len(lines) != 3 or lines[2] != BILINGUAL_AUTOEDIT_MARKER:
        return None
    zh_match = STRICT_BILINGUAL_ADMIN_DECISION_RE.fullmatch(lines[0])
    en_match = STRICT_STANDALONE_ADMIN_DECISION_RE.fullmatch(lines[1])
    if not zh_match or not en_match:
        return None
    zh_decision = 'approved' if zh_match.group(1) == '核准' else 'rejected'
    en_decision = 'approved' if en_match.group(1).lower() == 'approve' else 'rejected'
    zh_ticket = zh_match.group(2).upper()
    en_ticket = en_match.group(2).upper()
    if zh_decision != en_decision or zh_ticket != en_ticket:
        return None
    return {'decision': en_decision, 'ticket_id': en_ticket, 'instructions': '', 'normalization': 'bilingual-autoedit:v1'}

def _find_ticket_for_bare_decision(ledger: ApprovalLedger, event: dict[str, Any], admin_channel_id: str) -> str | None:
    root_id = as_string(event.get('root_id') or event.get('thread_id'))
    _post_id = as_string(event.get('post_id') or event.get('message_id'))
    if not root_id:
        return None
    matches = []
    for ticket in ledger.list_open():
        if ticket.get('status') != 'pending':
            continue
        admin_match = as_string(ticket.get('admin_channel_id')) == admin_channel_id and root_id in {as_string(ticket.get('admin_root_id')), as_string(ticket.get('admin_approval_post_id'))}
        inline_match = ticket.get('approval_route') == 'origin_inline' and as_string(event.get('channel_id')) == as_string(ticket.get('origin_channel_id')) and (root_id in {as_string(ticket.get('origin_root_id')), as_string(ticket.get('origin_post_id'))})
        if admin_match or inline_match:
            matches.append(ticket['ticket_id'])
    return matches[0] if len(matches) == 1 else None

def _decision_event_for_post(ledger: ApprovalLedger, post_id: str) -> dict[str, Any] | None:
    key = f'decision:{post_id}'
    for entry in ledger.read_events():
        if entry.get('idempotency_key') == key:
            return entry
    return None

def _event_binding(ticket: dict[str, Any], event: dict[str, Any], admin_channel_id: str) -> str | None:
    channel_id = as_string(event.get('channel_id'))
    post_id = as_string(event.get('post_id') or event.get('message_id'))
    root_id = as_string(event.get('root_id') or event.get('thread_id') or post_id)
    admin_roots = {as_string(ticket.get('admin_root_id')), as_string(ticket.get('admin_approval_post_id'))}
    origin_roots = {as_string(ticket.get('origin_root_id')), as_string(ticket.get('origin_post_id'))}
    admin_channels = {as_string(admin_channel_id), as_string(ticket.get('admin_channel_id')), as_string(ticket.get('approval_channel_id'))}
    admin_channels.discard('')
    admin_channels.discard(as_string(ticket.get('origin_channel_id')))
    if channel_id in admin_channels and root_id in {value for value in admin_roots if value}:
        return 'bound_admin_thread'
    if channel_id == as_string(ticket.get('origin_channel_id')) and root_id in {value for value in origin_roots if value}:
        return 'exact_origin_thread'
    return None

def _policy_surface_allowed(admin_policy: dict[str, Any] | None, event: dict[str, Any]) -> bool:
    """Fail-closed check for an exact admin's current DM/channel policy."""
    if not isinstance(admin_policy, dict):
        return False
    if not admin_policy.get('found') or not admin_policy.get('active'):
        return False
    if (admin_policy.get('approval') or {}).get('writes') is not True:
        return False
    channel_type = as_string(event.get('channel_type')).upper()
    if channel_type == 'D':
        return bool(admin_policy.get('dmEnabled')) and admin_policy.get('decision') == 'allow_dm'
    if channel_type not in {'G', 'O', 'P'}:
        return False
    channels = admin_policy.get('channels') or {}
    entry = channels.get(as_string(event.get('channel_id')))
    if entry is None:
        entry = channels.get('*')
    access = as_string(entry.get('access') if isinstance(entry, dict) else entry).lower()
    return bool(access) and access not in {'deny', 'denied', 'disabled', 'none', 'never'}

def validate_event(ledger: ApprovalLedger, event: dict[str, Any], *, andy_user_id: str=None, admin_channel_id: str=None, admin_policy: dict[str, Any] | None=None) -> dict[str, Any]:
    """Validate a Mattermost approval decision without mutating the ledger."""
    if andy_user_id is None:
        andy_user_id = DEFAULT_ANDY_USER_ID()
    if admin_channel_id is None:
        admin_channel_id = DEFAULT_ADMIN_CHANNEL_ID()
    if event.get('deleted'):
        return {'ok': False, 'status': 'ignored', 'reason': 'deleted_message'}
    if as_string(event.get('provider') or 'mattermost').lower() != 'mattermost':
        return {'ok': False, 'status': 'ignored', 'reason': 'wrong_provider'}
    actor_user_id = as_string(event.get('user_id') or event.get('sender_id'))
    if actor_user_id != andy_user_id:
        return {'ok': False, 'status': 'ignored', 'reason': 'not_authorized_sender'}
    message = as_string(event.get('message') or event.get('text') or event.get('body'))
    strict = parse_strict_standalone_admin_decision(message)
    parsed = strict or parse_decision(message)
    if not parsed:
        return {'ok': False, 'status': 'ignored', 'reason': 'no_strict_decision'}
    explicit_ticket_id = parsed.get('ticket_id')
    ticket_id = explicit_ticket_id or _find_ticket_for_bare_decision(ledger, event, admin_channel_id)
    if not ticket_id:
        return {'ok': False, 'status': 'ignored', 'reason': 'ambiguous_or_unbound_bare_decision'}
    try:
        ticket = ledger.get(ticket_id)
    except KeyError:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'ok': False, 'status': 'ignored', 'reason': 'ticket_not_found', 'ticket_id': ticket_id}
    binding = _event_binding(ticket, event, admin_channel_id)
    if not binding and explicit_ticket_id and (as_string(event.get('channel_id')) == as_string(admin_channel_id)):
        binding = 'bound_admin_channel'
    if not binding and explicit_ticket_id and _policy_surface_allowed(admin_policy, event):
        if strict and strict['ticket_id'] == ticket_id and (strict['decision'] == parsed['decision']):
            binding = 'policy_approved_admin_surface'
    if not binding:
        return {'ok': False, 'status': 'ignored', 'reason': 'decision_post_not_in_bound_origin_or_policy_surface', 'ticket_id': ticket_id}
    bare_binding_allowed = binding == 'bound_admin_thread' or (binding == 'exact_origin_thread' and ticket.get('approval_route') == 'origin_inline')
    if not explicit_ticket_id and (not bare_binding_allowed):
        return {'ok': False, 'status': 'ignored', 'reason': 'bare_decision_only_allowed_in_bound_approval_thread', 'ticket_id': ticket_id}
    post_id = as_string(event.get('post_id') or event.get('message_id'))
    if not post_id:
        return {'ok': False, 'status': 'ignored', 'reason': 'decision_post_id_required', 'ticket_id': ticket_id}
    existing_event = _decision_event_for_post(ledger, post_id)
    if existing_event:
        existing_data = existing_event.get('data') or {}
        existing_decision = as_string((existing_data.get('andy_decision') or {}).get('decision') or existing_data.get('status'))
        if existing_event.get('ticket_id') != ticket_id or existing_decision != parsed['decision']:
            return {'ok': False, 'status': 'ignored', 'reason': 'decision_post_conflicts_with_existing_record', 'ticket_id': ticket_id}
        return {'ok': True, 'status': 'validated', 'ticket_id': ticket_id, 'decision': parsed['decision'], 'instructions': parsed.get('instructions') or '', 'decision_post_id': post_id, 'actor_user_id': actor_user_id, 'binding': binding, 'idempotent_replay': True, 'ticket': ticket}
    if event.get('edited') and (strict or {}).get('normalization') not in ALLOWED_EDIT_NORMALIZATIONS:
        return {'ok': False, 'status': 'ignored', 'reason': 'edited_message_without_existing_decision', 'ticket_id': ticket_id}
    if as_string(ticket.get('status')).lower() != 'pending':
        return {'ok': False, 'status': 'ignored', 'reason': f'ticket_not_pending:{ticket.get('status')}', 'ticket_id': ticket_id}
    return {'ok': True, 'status': 'validated', 'ticket_id': ticket_id, 'decision': parsed['decision'], 'instructions': parsed.get('instructions') or '', 'decision_post_id': post_id, 'actor_user_id': actor_user_id, 'binding': binding, 'idempotent_replay': False, 'ticket': ticket}

def handle_event(ledger: ApprovalLedger, event: dict[str, Any], *, andy_user_id: str=None, admin_channel_id: str=None, admin_policy: dict[str, Any] | None=None) -> dict[str, Any]:
    if andy_user_id is None:
        andy_user_id = DEFAULT_ANDY_USER_ID()
    if admin_channel_id is None:
        admin_channel_id = DEFAULT_ADMIN_CHANNEL_ID()
    validated = validate_event(ledger, event, andy_user_id=andy_user_id, admin_channel_id=admin_channel_id, admin_policy=admin_policy)
    if not validated.get('ok'):
        return validated
    ticket_id = validated['ticket_id']
    post_id = validated['decision_post_id']
    try:
        decided = ledger.decide(ticket_id, decision=validated['decision'], andy_user_id=validated['actor_user_id'], decision_post_id=post_id, instructions=validated.get('instructions') or '', decision_channel_id=as_string(event.get('channel_id')), decision_root_id=as_string(event.get('root_id') or event.get('thread_id') or post_id), decision_binding=validated['binding'])
        if validated['decision'] == 'approved':
            queued = ledger.enqueue(ticket_id, idempotency_key=f'queue:{ticket_id}:{post_id}')
            status = 'approved' if queued.get('status') == 'queued' else 'approved_not_executable'
            return {'ok': True, 'status': status, 'ticket_id': ticket_id, 'binding': validated['binding'], 'idempotent_replay': validated['idempotent_replay'], 'execution_blocker': queued.get('execution_blocker') or '', 'ticket': queued}
        return {'ok': True, 'status': 'rejected', 'ticket_id': ticket_id, 'binding': validated['binding'], 'idempotent_replay': validated['idempotent_replay'], 'ticket': decided}
    except (InvalidTransition, KeyError) as exc:
        logging.getLogger('pd_one_ops').exception('pd one command failed')
        return {'ok': False, 'status': 'ignored', 'reason': str(exc), 'ticket_id': ticket_id}

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ledger', default=str(DEFAULT_LEDGER_PATH))
    p.add_argument('--andy-user-id', default=DEFAULT_ANDY_USER_ID())
    p.add_argument('--admin-channel-id', default=DEFAULT_ADMIN_CHANNEL_ID())
    p.add_argument('--event-json', required=True, help='JSON string/path or - for stdin')
    return p

def load_event(value: str) -> dict[str, Any]:
    if value == '-':
        return json.load(sys.stdin)
    path = Path(value)
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return json.loads(value)

def main(argv: list[str] | None=None) -> int:
    args = build_parser().parse_args(argv)
    result = handle_event(ApprovalLedger(args.ledger), load_event(args.event_json), andy_user_id=args.andy_user_id, admin_channel_id=args.admin_channel_id)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get('ok') else 1
if __name__ == '__main__':
    raise SystemExit(main())

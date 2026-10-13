#!/usr/bin/env python3
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
import os
import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any
requests = _PdLazyMod('requests')
HTTPAdapter = _PdLazyAttr('requests.adapters', 'HTTPAdapter')
Retry = _PdLazyAttr('urllib3.util.retry', 'Retry')

def ENV_PATH_DEFAULT():
    return resolve_configured_path('~/.openclaw/workspace/projects/AppSheet/keydrop/prototype-app.env')

def SCHEMA_MAP_DEFAULT():
    return resolve_configured_path('~/.openclaw/workspace/skills/appsheet-copilot/references/prodesign-schema-map.json')
API_BASE = 'https://www.appsheet.com/api/v2/apps/{app_id}/tables/{table}/Action'
DEFAULT_TIMEOUT = (20, 180)
APP_LOCAL_TZ = ZoneInfo('Asia/Taipei')
APP_API_PROPERTIES = {'Locale': 'zh-TW', 'Timezone': 'Taipei Standard Time'}

@dataclass
class Clarification:
    field: str
    reason: str
    options: list[str] = field(default_factory=list)

@dataclass
class OperationPlan:
    intent: str
    table: str
    description: str
    parsed: dict[str, Any] = field(default_factory=dict)
    clarifications: list[Clarification] = field(default_factory=list)
    selector: str | None = None
    row_payload: dict[str, Any] | None = None
    dry_run_summary: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        data = {'intent': self.intent, 'table': self.table, 'description': self.description, 'parsed': self.parsed, 'clarifications': [c.__dict__ for c in self.clarifications], 'selector': self.selector, 'row_payload': self.row_payload, 'dry_run_summary': self.dry_run_summary, 'warnings': self.warnings}
        if self.execution is not None:
            data['execution'] = self.execution
        return data

class AppSheetClient:

    def __init__(self, env_file: str, schema_map_file: str=None) -> None:
        if schema_map_file is None:
            schema_map_file = SCHEMA_MAP_DEFAULT()
        env = self._load_env(env_file)
        self.app_id = env['APP_ID']
        self.access_key = env['APP_ACCESS_KEY']
        self.run_as = env.get('RUN_AS_USER_EMAIL') or None
        self.schema_map_file = schema_map_file
        self._table_columns: dict[str, set[str]] = {}
        self._load_table_columns(schema_map_file)
        self.session = requests.Session()
        retry = Retry(total=3, connect=3, read=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=frozenset(['POST']), raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    @staticmethod
    def _load_env(path: str) -> dict[str, str]:
        data: dict[str, str] = {}
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            data[key.strip()] = value.strip()
        missing = [key for key in ['APP_ID', 'APP_ACCESS_KEY'] if not data.get(key)]
        if missing:
            raise SystemExit(f'Missing required env keys in {path}: {', '.join(missing)}')
        return data

    def _load_table_columns(self, schema_map_file: str) -> None:
        """Load a lightweight table->column allowlist for write payload validation.

        AppSheet's Data API can return an empty body for some malformed payloads;
        the authoritative error then only appears later in Monitor/export logs. A
        cheap local column check catches common mistakes (for example sending a
        `Timestamp` field to `Case`, whose actual creation column is `Created On`)
        before we make a live write.
        """
        try:
            data = json.loads(Path(schema_map_file).read_text(encoding='utf-8'))
            tables = data.get('tables', {})
            for table_name, table in tables.items():
                self._table_columns[table_name] = {col.get('name') for col in table.get('columns', []) if col.get('name')}
        except Exception:
            logging.getLogger('pd_one_ops').exception('pd one command failed')
            self._table_columns = {}

    def _validate_payload_columns(self, table: str, rows: list[dict[str, Any]] | None) -> None:
        if not rows:
            return
        known = self._table_columns.get(table)
        if not known:
            return
        bad: set[str] = set()
        for row in rows:
            bad.update((key for key in row if key not in known))
        if bad:
            preview = ', '.join(sorted(list(known))[:30])
            raise ValueError(f'Payload for AppSheet table {table!r} contains unknown column(s): {', '.join(sorted(bad))}. Check the synced schema before writing. Known columns include: {preview}')

    def action(self, table: str, action: str, *, rows: list[dict[str, Any]] | None=None, properties: dict[str, Any] | None=None) -> list[dict[str, Any]]:
        self._validate_payload_columns(table, rows)
        headers = {'ApplicationAccessKey': self.access_key, 'Content-Type': 'application/json'}
        if self.run_as:
            headers['RunAsUserEmail'] = self.run_as
        merged_properties = dict(APP_API_PROPERTIES)
        if properties:
            merged_properties.update(properties)
        payload = {'Action': action, 'Properties': merged_properties, 'Rows': rows or []}
        response = self.session.post(API_BASE.format(app_id=self.app_id, table=table), headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        if not response.text.strip():
            if action != 'Find':
                return []
            raise RuntimeError(f'Empty response body from AppSheet for {table}/{action}. This usually means the query was too expensive, the table is poorly visible in the current context, or AppSheet returned a blank success response. Selector={(properties.get('Selector') if properties else None)}')
        data = response.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ('Rows', 'rows', 'Result', 'result'):
                value = data.get(key)
                if isinstance(value, list):
                    return value
            return [data]
        raise RuntimeError(f'Unexpected AppSheet response type for {table}/{action}: {type(data).__name__}')

    def find(self, table: str, selector: str) -> list[dict[str, Any]]:
        return self.action(table, 'Find', properties={'Selector': selector})

    def add(self, table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
        return self.action(table, 'Add', rows=[row])

    def edit(self, table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
        return self.action(table, 'Edit', rows=[row])

    def delete(self, table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
        return self.action(table, 'Delete', rows=[row])

class SchemaMap:

    def __init__(self, path: str) -> None:
        self.path = path
        self.data = json.loads(Path(path).read_text(encoding='utf-8'))
        self.tables = self.data['tables']
        self.slices = self.data['slices']

    def column(self, table: str, name: str) -> dict[str, Any] | None:
        for col in self.tables[table]['columns']:
            if col['name'] == name:
                return col
        return None

    def slice_filter_selector(self, slice_name: str) -> tuple[str, str]:
        info = self.slices[slice_name]
        row_filter = info['row_filter'] or ''
        if row_filter.startswith('='):
            row_filter = row_filter[1:]
        return (info['source_table'], f'Filter({info['source_table']}, {row_filter})')

def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def appsheet_local_datetime(dt: datetime | None=None) -> str:
    """Return a DateTime string in the app's business timezone.

    AppSheet API DateTime values are not timezone-qualified; sending UTC from
    Hermes (host timezone UTC) makes user-visible Case_Updates appear 8 hours
    early in Taiwan. Use Asia/Taipei wall time for operational rows.
    """
    dt = dt or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(APP_LOCAL_TZ).strftime('%m/%d/%Y %H:%M:%S')
CREATE_INCIDENT_RE = re.compile('create\\s+(?:a\\s+)?new\\s+incident\\s+report(?:\\s+with\\s+(?:the\\s+)?following)?\\s+description\\s*:\\s*(?P<description>.+)', re.I | re.S)
QUERY_INCIDENTS_RE = re.compile('(?:give me|show me|list)(?:\\s+an?\\s+itemized\\s+list\\s+of)?\\s+unresolved\\s+incident\\s+reports\\s+created\\s+in\\s+the\\s+last\\s+(?P<amount>\\d+)\\s+(?P<unit>hour|hours|day|days)', re.I)
RESOLVE_ACTIVITY_RE = re.compile('mark\\s+(?P<needle>.+?)\\s+activitylog\\s+as\\s+resolved,\\s+with\\s+troubleshooting\\s+action\\s+as\\s+(?P<action>.+)', re.I | re.S)
UPDATE_ACTIVITY_RE = re.compile('(?:edit|update)\\s+(?P<needle>.+?)\\s+activitylog\\s+set\\s+(?P<field>.+?)\\s+to\\s+(?P<value>.+)', re.I | re.S)
DELETE_ACTIVITY_RE = re.compile('delete\\s+(?P<needle>.+?)\\s+activitylog', re.I)
CREATE_CASE_RE = re.compile('create\\s+(?:a\\s+)?case\\s+(?P<body>.+)', re.I | re.S)
ADD_CASE_UPDATE_RE = re.compile('add\\s+(?:an?\\s+)?update\\s+to\\s+case\\s+(?P<needle>[^:;]+)\\s*:\\s*(?P<body>.+)', re.I | re.S)
CLOSE_CASE_RE = re.compile('(?:close|complete|resolve)\\s+case\\s+(?P<needle>[^:;]+)\\s*:\\s*(?P<body>.+)', re.I | re.S)
QUERY_CASES_RE = re.compile('(?:show|list|find)\\s+(?:open|unresolved)\\s+cases(?:\\s+assigned\\s+to\\s+(?P<responsible>.+?))?(?:\\s+in\\s+the\\s+last\\s+(?P<amount>\\d+)\\s+(?P<unit>day|days))?$', re.I | re.S)

def parse_field_segments(body: str) -> tuple[dict[str, str], str | None]:
    fields: dict[str, str] = {}
    free_text: str | None = None
    aliases = {'title': 'title', 'summary': 'summary', 'description': 'description', 'desc': 'description', 'type': 'type', 'case type': 'type', 'sub-type': 'sub_type', 'subtype': 'sub_type', 'responsible': 'responsible', 'owner': 'responsible', 'next step responsible': 'responsible', 'created by': 'created_by', 'creator': 'created_by', 'requester': 'created_by', 'deadline': 'deadline', 'due': 'deadline', 'status': 'status', 'update type': 'update_type'}
    for idx, part in enumerate(re.split('\\s*;\\s*', body.strip())):
        part = part.strip()
        if not part:
            continue
        if ':' in part:
            key, value = part.split(':', 1)
            canonical = aliases.get(key.strip().lower())
            if canonical:
                fields[canonical] = value.strip()
                continue
        if idx == 0 and free_text is None:
            free_text = part
        else:
            free_text = f'{free_text}; {part}' if free_text else part
    return (fields, free_text)

def parse_request(text: str) -> dict[str, Any]:
    raw = text.strip()
    if (m := CREATE_INCIDENT_RE.search(raw)):
        return {'intent': 'create_incident_report', 'table': 'ActivityLog', 'description': m.group('description').strip()}
    if (m := QUERY_INCIDENTS_RE.search(raw)):
        return {'intent': 'query_unresolved_incident_reports', 'table': 'ActivityLog', 'amount': int(m.group('amount')), 'unit': m.group('unit').lower()}
    if (m := RESOLVE_ACTIVITY_RE.search(raw)):
        return {'intent': 'resolve_activitylog_incident', 'table': 'ActivityLog', 'needle': m.group('needle').strip(), 'troubleshooting_actions': m.group('action').strip()}
    if (m := UPDATE_ACTIVITY_RE.search(raw)):
        return {'intent': 'update_activitylog_field', 'table': 'ActivityLog', 'needle': m.group('needle').strip(), 'field': m.group('field').strip(), 'value': m.group('value').strip()}
    if (m := DELETE_ACTIVITY_RE.search(raw)):
        return {'intent': 'delete_activitylog', 'table': 'ActivityLog', 'needle': m.group('needle').strip()}
    if (m := ADD_CASE_UPDATE_RE.search(raw)):
        fields, free_text = parse_field_segments(m.group('body'))
        summary = fields.get('summary') or free_text or fields.get('description') or ''
        return {'intent': 'add_case_update', 'table': 'Case_Updates', 'needle': m.group('needle').strip(), 'summary': summary.strip(), 'description': fields.get('description', summary).strip(), 'status': fields.get('status'), 'responsible': fields.get('responsible'), 'deadline': fields.get('deadline'), 'update_type': fields.get('update_type', 'Action Record'), 'created_by': fields.get('created_by')}
    if (m := CLOSE_CASE_RE.search(raw)):
        fields, free_text = parse_field_segments(m.group('body'))
        summary = fields.get('summary') or free_text or fields.get('description') or ''
        return {'intent': 'change_case_status', 'table': 'Case_Updates', 'needle': m.group('needle').strip(), 'summary': summary.strip(), 'description': fields.get('description', summary).strip(), 'status': fields.get('status', 'Completed'), 'responsible': fields.get('responsible'), 'deadline': fields.get('deadline'), 'update_type': fields.get('update_type', 'Status Change')}
    if (m := CREATE_CASE_RE.search(raw)):
        fields, free_text = parse_field_segments(m.group('body'))
        return {'intent': 'create_case', 'table': 'Case', 'title': fields.get('title') or free_text, 'description': fields.get('description'), 'type': fields.get('type'), 'sub_type': fields.get('sub_type'), 'responsible': fields.get('responsible'), 'created_by': fields.get('created_by'), 'deadline': fields.get('deadline'), 'status': fields.get('status', 'Not Started')}
    if (m := QUERY_CASES_RE.search(raw)):
        return {'intent': 'query_cases', 'table': 'Case', 'responsible': (m.group('responsible') or '').strip() or None, 'amount': int(m.group('amount')) if m.group('amount') else None, 'unit': m.group('unit') if m.group('unit') else None}
    raise SystemExit('Unsupported request pattern. Current seed intents: create incident, query unresolved incidents, resolve ActivityLog incident, update ActivityLog field, delete ActivityLog, create Case, add Case update, close Case, query open Cases.')

def quote(value: str) -> str:
    return value.replace('"', '\\"')

class RecordOpsPlanner:

    def __init__(self, schema: SchemaMap, client: AppSheetClient | None=None) -> None:
        self.schema = schema
        self.client = client

    def build(self, request_text: str, execute: bool=False, sync_parent_status: bool=True, created_by: str | None=None) -> OperationPlan:
        parsed = parse_request(request_text)
        if created_by:
            parsed['created_by'] = created_by
        intent = parsed['intent']
        if intent == 'create_incident_report':
            plan = self._plan_create_incident(parsed, execute)
        elif intent == 'query_unresolved_incident_reports':
            plan = self._plan_query_unresolved(parsed, execute)
        elif intent == 'resolve_activitylog_incident':
            plan = self._plan_resolve_activity(parsed, execute, sync_parent_status)
        elif intent == 'update_activitylog_field':
            plan = self._plan_update_activity(parsed, execute)
        elif intent == 'delete_activitylog':
            plan = self._plan_delete_activity(parsed, execute)
        elif intent == 'create_case':
            plan = self._plan_create_case(parsed, execute)
        elif intent == 'add_case_update':
            plan = self._plan_add_case_update(parsed, execute, sync_case_status=False)
        elif intent == 'change_case_status':
            plan = self._plan_add_case_update(parsed, execute, sync_case_status=sync_parent_status)
        elif intent == 'query_cases':
            plan = self._plan_query_cases(parsed, execute)
        else:
            raise SystemExit(f'Unhandled intent: {intent}')
        plan.parsed = parsed
        return plan

    def _lookup_slice_rows(self, slice_name: str) -> list[dict[str, Any]]:
        if not self.client:
            return []
        table, selector = self.schema.slice_filter_selector(slice_name)
        return self.client.find(table, selector)

    def _lookup_options(self, slice_name: str) -> list[str]:
        rows = self._lookup_slice_rows(slice_name)
        return [str(row.get('LookupID', '')).strip() for row in rows if row.get('LookupID')]

    def _lookup_row(self, lookup_id: str) -> dict[str, Any] | None:
        if not self.client:
            return None
        selector = f'Filter(Lookup, [LookupID] = "{quote(lookup_id)}")'
        rows = self.client.find('Lookup', selector)
        return rows[0] if rows else None

    def _find_activitylog_contains(self, needle: str) -> list[dict[str, Any]]:
        if not self.client:
            raise SystemExit('Execution requires an AppSheet env file and connectivity.')
        selector = f'Filter(ActivityLog, CONTAINS([ActivityLogID], "{quote(needle)}"))'
        return self.client.find('ActivityLog', selector)

    def _find_case_contains(self, needle: str) -> list[dict[str, Any]]:
        if not self.client:
            raise SystemExit('Execution requires an AppSheet env file and connectivity.')
        selector = f'Filter(Case, OR(CONTAINS([CaseID], "{quote(needle)}"), CONTAINS([Title], "{quote(needle)}"), CONTAINS([Description], "{quote(needle)}")))'
        return self.client.find('Case', selector)

    def _resolve_person(self, text: str | None) -> tuple[str | None, Clarification | None]:
        if not text:
            return (None, None)
        if not self.client:
            return (text, None)
        selector = f'Filter(HR_Employees, AND(OR(ISBLANK([Hidden]), [Hidden] = FALSE), OR(CONTAINS([PersonID], "{quote(text)}"), CONTAINS([Name_ZH_EN], "{quote(text)}"), CONTAINS([Name_EN], "{quote(text)}"), CONTAINS([Name_ZH], "{quote(text)}"), CONTAINS([Appsheet Email], "{quote(text)}"))))'
        rows = self.client.find('HR_Employees', selector)
        if len(rows) == 1 and rows[0].get('PersonID'):
            return (str(rows[0]['PersonID']), None)
        options = [str(row.get('PersonID') or row.get('Name_ZH_EN') or row.get('Name_EN') or '') for row in rows[:20] if row.get('PersonID') or row.get('Name_ZH_EN') or row.get('Name_EN')]
        return (None, Clarification(field='Next Step Responsible Person', reason=f'Responsible person {text!r} did not resolve to exactly one HR_Employees row.', options=options))

    @staticmethod
    def _is_terminal_case_status(status: str | None) -> bool:
        return (status or '').strip().lower() in {'completed', 'canceled', 'cancelled', 'on hold'}

    def _case_choice_options(self, rows: list[dict[str, Any]]) -> list[str]:
        return [str(row.get('CaseID', '')) for row in rows[:20] if row.get('CaseID')]

    def _plan_create_case(self, parsed: dict[str, Any], execute: bool) -> OperationPlan:
        row: dict[str, Any] = {}
        mapping = {'title': 'Title', 'description': 'Description', 'type': 'Type', 'sub_type': 'Sub-Type', 'deadline': 'Deadline', 'status': 'Status', 'created_by': 'Created By'}
        for source, target in mapping.items():
            value = parsed.get(source)
            if value:
                row[target] = value
        row.setdefault('Status', 'Not Started')
        clarifications: list[Clarification] = []
        if parsed.get('responsible'):
            resolved, clarification = self._resolve_person(parsed.get('responsible'))
            if clarification:
                clarifications.append(clarification)
            elif resolved:
                row['Next Step Responsible Person'] = resolved
        missing = []
        for field_name, column_name in [('title', 'Title'), ('description', 'Description'), ('type', 'Type'), ('deadline', 'Deadline')]:
            if not row.get(column_name):
                missing.append(column_name)
        if not self._is_terminal_case_status(row.get('Status')) and (not row.get('Next Step Responsible Person')):
            missing.append('Next Step Responsible Person')
        existing_clarification_fields = {c.field for c in clarifications}
        for field_name in missing:
            if field_name not in existing_clarification_fields:
                clarifications.append(Clarification(field=field_name, reason=f'Case creation needs {field_name} before a safe live write.'))
        plan = OperationPlan(intent='create_case', table='Case', description='Create a parent Case row for a follow-up workflow.', row_payload=row, clarifications=clarifications, dry_run_summary={'will_create_parent': True, 'defaults': {'Status': row.get('Status')}, 'missing_before_execute': [c.field for c in clarifications], 'expected_side_effects': ['Case add automations may enqueue translation/notification work.']})
        if not execute:
            return plan
        if clarifications:
            plan.warnings.append('Execution skipped because required clarification fields are still missing.')
            return plan
        created = self.client.add('Case', row)
        plan.execution = {'created_case_rows': created}
        return plan

    def _case_update_payload(self, parsed: dict[str, Any], parent: dict[str, Any], status: str | None=None) -> tuple[dict[str, Any], Clarification | None]:
        new_status = status or parsed.get('status') or parent.get('Status')
        responsible_text = parsed.get('responsible')
        resolved_person: str | None = None
        clarification: Clarification | None = None
        if responsible_text:
            resolved_person, clarification = self._resolve_person(responsible_text)
        elif not self._is_terminal_case_status(new_status):
            resolved_person = parent.get('Next Step Responsible Person')
        payload = {'CaseID': parent.get('CaseID'), 'Update Summary': parsed.get('summary'), 'Update Description': parsed.get('description') or parsed.get('summary'), 'Update Type': parsed.get('update_type') or 'Action Record', 'Case Type': parent.get('Type'), 'Timestamp': appsheet_local_datetime(), 'New Status': new_status, 'New Deadline': parsed.get('deadline') or parent.get('Deadline')}
        if resolved_person:
            payload['New Next Step Responsible Person'] = resolved_person
        created_by = parsed.get('created_by')
        if created_by:
            payload['Created By'] = created_by
        return ({k: v for k, v in payload.items() if v not in (None, '')}, clarification)

    def _plan_add_case_update(self, parsed: dict[str, Any], execute: bool, sync_case_status: bool=False) -> OperationPlan:
        needle = parsed['needle']
        selector = f'Filter(Case, OR(CONTAINS([CaseID], "{quote(needle)}"), CONTAINS([Title], "{quote(needle)}"), CONTAINS([Description], "{quote(needle)}")))'
        summary = parsed.get('summary') or ''
        status = parsed.get('status')
        plan = OperationPlan(intent=parsed['intent'], table='Case_Updates', description='Find a unique parent Case, then create a child Case_Updates row with the requested progress/status update.', selector=selector, row_payload={'Update Summary': summary, 'Update Description': parsed.get('description') or summary, 'New Status': status, 'New Next Step Responsible Person': parsed.get('responsible'), 'New Deadline': parsed.get('deadline'), 'Timestamp': appsheet_local_datetime(), 'Created By': parsed.get('created_by')}, dry_run_summary={'lookup_contains': needle, 'will_create_child_case_update': True, 'will_sync_parent_status': bool(sync_case_status and status), 'expected_side_effects': ['Case_Updates add automations may update parent Case Latest_CaseUpdateID/Last Updated/Status.', 'Translation/notification queue rows may be created depending on app rules.']})
        if not execute:
            plan.warnings.append('Dry run only. Execute mode requires a unique Case match and explicit approval in the chat layer.')
            return plan
        matches = self._find_case_contains(needle)
        if len(matches) != 1:
            plan.clarifications.append(Clarification(field='CaseID', reason='Case update requires a unique Case match.', options=self._case_choice_options(matches)))
            return plan
        parent = matches[0]
        payload, clarification = self._case_update_payload(parsed, parent, status=status)
        if clarification:
            plan.clarifications.append(clarification)
            return plan
        if not payload.get('Update Summary'):
            plan.clarifications.append(Clarification(field='Update Summary', reason='Case_Updates needs an update summary/description.'))
            return plan
        if not payload.get('Created By'):
            plan.clarifications.append(Clarification(field='Created By', reason='Case_Updates Add requires the exact requester HR PersonID as Created By.'))
            return plan
        if not self._is_terminal_case_status(payload.get('New Status')) and (not payload.get('New Next Step Responsible Person')):
            plan.clarifications.append(Clarification(field='New Next Step Responsible Person', reason='Non-terminal Case updates need a next-step responsible person.'))
            return plan
        created = self.client.add('Case_Updates', payload)
        execution: dict[str, Any] = {'matched_case': {'CaseID': parent.get('CaseID'), 'Title': parent.get('Title'), 'Status': parent.get('Status'), 'Latest_CaseUpdateID': parent.get('Latest_CaseUpdateID')}, 'created_case_update_rows': created}
        if sync_case_status and payload.get('New Status'):
            sync_actions: list[dict[str, Any]] = []
            created_update = created[0] if created else payload
            created_key = created_update.get('CaseUpdateID')
            if created_key:
                created_update = self.client.find('Case_Updates', f'Filter(Case_Updates, [CaseUpdateID] = "{quote(str(created_key))}")')[0]
            for action_name in ('Case_Updates_UpdateCaseWithLatestCaseUpdateID', 'Case_Updates_UpdateCaseInformationFromCaseUpdate'):
                try:
                    result = self.client.action('Case_Updates', action_name, rows=[created_update])
                    sync_actions.append({'action': action_name, 'ok': True, 'rows': result})
                except Exception as exc:
                    logging.getLogger('pd_one_ops').exception('pd one command failed')
                    sync_actions.append({'action': action_name, 'ok': False, 'error': str(exc)})
            refreshed_parent = self.client.find('Case', f'Filter(Case, [CaseID] = "{quote(str(parent.get('CaseID')))}")')
            execution['parent_sync_actions'] = sync_actions
            execution['parent_case_readback'] = refreshed_parent
            if not refreshed_parent or refreshed_parent[0].get('Status') != payload.get('New Status'):
                plan.warnings.append('Created the Case_Updates status-change row, but parent Case readback did not reflect the requested status. Treat this as partial success and inspect the AppSheet bot/action path.')
        plan.row_payload = payload
        plan.execution = execution
        return plan

    def _plan_query_cases(self, parsed: dict[str, Any], execute: bool) -> OperationPlan:
        clauses = ['NOT(IN([Status], LIST("Completed", "Canceled", "Cancelled")))']
        if parsed.get('responsible'):
            clauses.append(f'CONTAINS([Next Step Responsible Person], "{quote(parsed['responsible'])}")')
        if parsed.get('amount'):
            delta = timedelta(days=int(parsed['amount']))
            since = datetime.now(timezone.utc) - delta
            clauses.append(f'[Created On] >= DATETIME("{iso_utc(since)}")')
        selector = f'Filter(Case, AND({', '.join(clauses)}))'
        plan = OperationPlan(intent='query_cases', table='Case', description='List open/unresolved Cases matching the requested filters.', selector=selector, dry_run_summary={'filters': clauses})
        if execute:
            rows = self.client.find('Case', selector)
            plan.execution = {'row_count': len(rows), 'items': [{'CaseID': row.get('CaseID'), 'Title': row.get('Title'), 'Status': row.get('Status'), 'Deadline': row.get('Deadline'), 'Next Step Responsible Person': row.get('Next Step Responsible Person')} for row in rows]}
        return plan

    def _plan_create_incident(self, parsed: dict[str, Any], execute: bool) -> OperationPlan:
        description = parsed['description']
        row = {'Category': 'Incident Report', 'Description': description, 'ActivityLog Status': 'Unresolved'}
        clarifications: list[Clarification] = []
        subcategory_rows = self._lookup_slice_rows('Lookup_Dropdown_Type_ActivityLog')
        incident_subcategories = []
        if subcategory_rows:
            incident_subcategories = [str(row.get('LookupID', '')).strip() for row in subcategory_rows if row.get('LookupID') and 'Incident Report' in str(row.get('Sub-Category 2', ''))]
        if incident_subcategories:
            clarifications.append(Clarification(field='Sub-Category', reason='Incident Report creation requires a sub-category when the category has active ActivityLog subtype lookups.', options=incident_subcategories[:30]))
        else:
            clarifications.append(Clarification(field='Sub-Category', reason='ActivityLog[Sub-Category] is conditionally required for Incident Report rows; the actual valid options come from Lookup rows under the ActivityLog type hierarchy.'))
        clarifications.append(Clarification(field='Risk', reason='Risk is required for Incident Report unless the chosen sub-category is Incident_ProductionProblem_OperatorReport.', options=self._lookup_options('Lookup_Dropdown_Risk')[:30]))
        plan = OperationPlan(intent='create_incident_report', table='ActivityLog', description='Create a parent ActivityLog row for Category = Incident Report.', clarifications=clarifications, row_payload=row, dry_run_summary={'will_create_parent': True, 'defaults': row, 'missing_before_execute': [c.field for c in clarifications]})
        if execute:
            if clarifications:
                plan.warnings.append('Execution skipped because required clarification fields are still missing.')
            else:
                created = self.client.add('ActivityLog', row)
                plan.execution = {'created_rows': created}
        return plan

    def _plan_query_unresolved(self, parsed: dict[str, Any], execute: bool) -> OperationPlan:
        amount = parsed['amount']
        unit = parsed['unit']
        delta = timedelta(hours=amount) if unit.startswith('hour') else timedelta(days=amount)
        since = datetime.now(timezone.utc) - delta
        selector = f'Filter(ActivityLog, AND([Category] = "Incident Report", ISBLANK([Parent ActivityLogID]), [ActivityLog Status] <> "Resolved", [Timestamp] >= DATETIME("{iso_utc(since)}")))'
        plan = OperationPlan(intent='query_unresolved_incident_reports', table='ActivityLog', description='List unresolved parent Incident Reports inside the requested time window.', selector=selector, dry_run_summary={'window_start_utc': iso_utc(since), 'filters': {'Category': 'Incident Report', 'Parent ActivityLogID': 'blank', 'ActivityLog Status': 'not Resolved'}})
        if execute:
            rows = self.client.find('ActivityLog', selector)
            itemized = [{'ActivityLogID': row.get('ActivityLogID'), 'Timestamp': row.get('Timestamp'), 'Sub-Category': row.get('Sub-Category'), 'ActivityLog Status': row.get('ActivityLog Status'), 'Risk': row.get('Risk'), 'Description': row.get('Description')} for row in rows]
            plan.execution = {'row_count': len(rows), 'items': itemized}
        return plan

    def _plan_resolve_activity(self, parsed: dict[str, Any], execute: bool, sync_parent_status: bool) -> OperationPlan:
        needle = parsed['needle']
        action_text = parsed['troubleshooting_actions']
        plan = OperationPlan(intent='resolve_activitylog_incident', table='ActivityLog', description='Find the parent ActivityLog row, then create a resolved child ActivityLog row with troubleshooting notes.', selector=f'Filter(ActivityLog, CONTAINS([ActivityLogID], "{quote(needle)}"))', row_payload={'Troubleshooting Actions': action_text, 'ActivityLog Status': 'Resolved'}, dry_run_summary={'lookup_contains': needle, 'child_defaults': {'ActivityLog Status': 'Resolved', 'Troubleshooting Actions': action_text}})
        if not execute:
            plan.warnings.append('Dry run only. Parent row lookup and child-row inheritance happen during execute mode.')
            if sync_parent_status:
                plan.warnings.append('Because the user explicitly asked to mark the ActivityLog as Resolved, execute mode will also set the matched parent ActivityLog Status to Resolved.')
            return plan
        matches = self._find_activitylog_contains(needle)
        if not matches:
            plan.warnings.append('No ActivityLog rows matched the requested ID fragment.')
            return plan
        if len(matches) > 1:
            plan.clarifications.append(Clarification(field='ActivityLogID', reason='The contains-search matched multiple ActivityLog rows. Choose one exact parent ActivityLogID.', options=[str(row.get('ActivityLogID', '')) for row in matches[:20]]))
            return plan
        parent = matches[0]
        child = {'Parent ActivityLogID': parent.get('ActivityLogID'), 'Category': parent.get('Category'), 'Sub-Category': parent.get('Sub-Category'), 'Sub-Category 2': parent.get('Sub-Category 2'), 'ActivityLog Status': 'Resolved', 'Troubleshooting Actions': action_text}
        if parent.get('Category') != 'Incident Report':
            plan.warnings.append('Matched row is not an Incident Report. Execution skipped for safety.')
            return plan
        created = self.client.add('ActivityLog', child)
        execution: dict[str, Any] = {'matched_parent': {'ActivityLogID': parent.get('ActivityLogID'), 'Category': parent.get('Category'), 'Sub-Category': parent.get('Sub-Category'), 'ActivityLog Status': parent.get('ActivityLog Status')}, 'created_child_rows': created}
        if sync_parent_status:
            parent_update = {'ActivityLogID': parent.get('ActivityLogID'), 'ActivityLog Status': 'Resolved'}
            execution['parent_status_update'] = self.client.edit('ActivityLog', parent_update)
            plan.warnings.append('Matched parent ActivityLog Status was explicitly set to Resolved because the user asked for that status.')
        else:
            plan.warnings.append('Parent status edit was skipped only because sync_parent_status was explicitly disabled.')
        plan.execution = execution
        return plan

    def _plan_update_activity(self, parsed: dict[str, Any], execute: bool) -> OperationPlan:
        needle = parsed['needle']
        field_name = parsed['field']
        value = parsed['value']
        selector = f'Filter(ActivityLog, CONTAINS([ActivityLogID], "{quote(needle)}"))'
        plan = OperationPlan(intent='update_activitylog_field', table='ActivityLog', description='Edit a single ActivityLog field after exact/unique record resolution.', selector=selector, row_payload={field_name: value}, dry_run_summary={'lookup_contains': needle, 'field': field_name, 'value': value})
        if not execute:
            plan.warnings.append('Dry run only. Execute mode requires a unique ActivityLog match.')
            return plan
        matches = self._find_activitylog_contains(needle)
        if len(matches) != 1:
            plan.clarifications.append(Clarification(field='ActivityLogID', reason='Update requires a unique ActivityLog match.', options=[str(row.get('ActivityLogID', '')) for row in matches[:20]]))
            return plan
        target = matches[0]
        if not self.schema.column('ActivityLog', field_name):
            plan.warnings.append(f"Field '{field_name}' is not an exact ActivityLog column name in the schema map.")
            return plan
        payload = {'ActivityLogID': target.get('ActivityLogID'), field_name: value}
        plan.execution = {'edited_rows': self.client.edit('ActivityLog', payload)}
        return plan

    def _plan_delete_activity(self, parsed: dict[str, Any], execute: bool) -> OperationPlan:
        needle = parsed['needle']
        selector = f'Filter(ActivityLog, CONTAINS([ActivityLogID], "{quote(needle)}"))'
        plan = OperationPlan(intent='delete_activitylog', table='ActivityLog', description='Delete is intentionally gated to exact, unique ActivityLog resolution.', selector=selector, dry_run_summary={'lookup_contains': needle, 'requires_exact_match': True}, warnings=['Delete should stay confirmation-gated in the chat layer. Prefer dry-run lookup first.'])
        if not execute:
            return plan
        matches = self._find_activitylog_contains(needle)
        if len(matches) != 1:
            plan.clarifications.append(Clarification(field='ActivityLogID', reason='Delete requires a unique ActivityLog match.', options=[str(row.get('ActivityLogID', '')) for row in matches[:20]]))
            return plan
        target = matches[0]
        payload = {'ActivityLogID': target.get('ActivityLogID')}
        plan.execution = {'deleted_rows': self.client.delete('ActivityLog', payload)}
        return plan

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Seed natural-language AppSheet record ops for the Pro-Design app.')
    parser.add_argument('request', help='Natural-language request to plan or execute.')
    parser.add_argument('--execute', action='store_true', help='Run the planned AppSheet operation instead of returning a dry-run plan.')
    parser.add_argument('--live-lookup', action='store_true', help='Allow dry-run mode to call live AppSheet lookup tables for option resolution.')
    parser.add_argument('--skip-parent-status-sync', action='store_true', help='For resolve flows, do not edit the matched parent ActivityLog to Resolved after child creation.')
    parser.add_argument('--env-file', default=ENV_PATH_DEFAULT(), help=f'Env file with APP_ID / APP_ACCESS_KEY / RUN_AS_USER_EMAIL (default: {ENV_PATH_DEFAULT()})')
    parser.add_argument('--schema-map', default=SCHEMA_MAP_DEFAULT(), help=f'Schema map JSON (default: {SCHEMA_MAP_DEFAULT()})')
    parser.add_argument('--created-by', help='Exact requester HR PersonID to stamp as Created By')
    parser.add_argument('--run-as-email', help='Requester company email for AppSheet RunAsUserEmail')
    return parser.parse_args()

def main(argv=None) -> int:
    args = parse_args(argv)
    schema = SchemaMap(args.schema_map)
    client = AppSheetClient(args.env_file, args.schema_map) if args.execute or args.live_lookup else None
    if client and args.run_as_email:
        client.run_as = args.run_as_email
    plan = RecordOpsPlanner(schema=schema, client=client).build(request_text=args.request, execute=args.execute, sync_parent_status=not args.skip_parent_status_sync, created_by=args.created_by)
    print(json.dumps(plan.as_dict(), ensure_ascii=False, indent=2))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

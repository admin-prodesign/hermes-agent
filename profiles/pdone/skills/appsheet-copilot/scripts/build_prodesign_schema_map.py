#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFINITION_JSON = Path('/home/prodesign/.openclaw/workspace/data/appsheet-definitions/f2073120-8c2e-4930-b13c-105838c5e4c3/latest/latest.json')
OUT_JSON = Path('/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/references/prodesign-schema-map.json')
OUT_MD = Path('/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/references/prodesign-schema-map.md')

TABLE_RE = re.compile(r'^## Table: (?P<name>.+)$', re.M)
SLICE_RE = re.compile(r'^## Slice: (?P<name>.+)$', re.M)
COLUMN_RE = re.compile(r'^- \*\*(?P<name>.+?)\*\* \((?P<type>.+?)\) \[(?P<storage>.+?) Column\]$', re.M)
PROP_RE = re.compile(r'^  - (?P<prop>[^:]+):\s*$', re.M)
INLINE_CODE_RE = re.compile(r'`([^`]+)`')
DEREF_RE = re.compile(r'\[(?P<local>[^\]]+)\]\.\[(?P<remote>[^\]]+)\]')
SLICE_KEY_RE = re.compile(r'([A-Za-z0-9_]+)\[([A-Za-z0-9_ /().-]+)\]')
LOOKUP_RE = re.compile(r'LOOKUP\(\s*[^,]+,\s*"(?P<table>[^"]+)"', re.I | re.S)
SELECT_RE = re.compile(r'SELECT\((?P<table>[A-Za-z0-9_]+)\[', re.I)


def load_sections() -> dict[str, str]:
    data = json.loads(DEFINITION_JSON.read_text(encoding='utf-8'))
    return data['sections']


def split_tables(text: str) -> dict[str, str]:
    matches = list(TABLE_RE.finditer(text))
    tables: dict[str, str] = {}
    for idx, m in enumerate(matches):
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        tables[m.group('name').strip()] = text[start:end].strip()
    return tables


def parse_column_block(block: str) -> dict[str, Any]:
    first = COLUMN_RE.search(block)
    if not first:
        raise ValueError('Invalid column block')
    col = {
        'name': first.group('name').strip(),
        'type': first.group('type').strip(),
        'storage': first.group('storage').strip(),
        'properties': {},
    }
    prop_matches = list(PROP_RE.finditer(block))
    for idx, pm in enumerate(prop_matches):
        start = pm.end()
        end = prop_matches[idx + 1].start() if idx + 1 < len(prop_matches) else len(block)
        raw = block[start:end].strip('\n')
        raw = raw.strip()
        inline = INLINE_CODE_RE.findall(raw)
        if len(inline) == 1 and raw.count('`') == 2:
            value = inline[0].strip()
        else:
            value = raw.replace('```', '').strip()
        col['properties'][pm.group('prop').strip()] = value
    return col


def split_slices(text: str) -> dict[str, str]:
    matches = list(SLICE_RE.finditer(text))
    slices: dict[str, str] = {}
    for idx, m in enumerate(matches):
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        slices[m.group('name').strip()] = text[start:end].strip()
    return slices


def parse_slice_block(block: str) -> dict[str, Any]:
    lines = block.splitlines()
    header = lines[0].strip().replace('## Slice: ', '', 1)
    source_match = re.search(r'^- \*\*Source Table\*\*: (.+)$', block, re.M)
    row_filter_match = re.search(r'^- \*\*Row Filter\*\*: (.+)$', block, re.M | re.S)
    info: dict[str, Any] = {
        'slice': header,
        'source_table': source_match.group(1).strip().strip('`') if source_match else None,
        'row_filter': row_filter_match.group(1).strip().strip('`') if row_filter_match else None,
        'references': [],
        'base_tables_seen': [],
        'base_tables_confident': [],
    }

    ref_candidates = set()
    confident = set()
    row_filter = info['row_filter'] or ''
    if info['source_table']:
        ref_candidates.add(info['source_table'])
        confident.add(info['source_table'])
    for m in SELECT_RE.finditer(row_filter):
        ref_candidates.add(m.group('table'))
    for m in LOOKUP_RE.finditer(row_filter):
        ref_candidates.add(m.group('table'))
    for m in SLICE_KEY_RE.finditer(row_filter):
        ref_candidates.add(m.group(1))

    refs = []
    for target in sorted(ref_candidates):
        if target in SKIP_TARGETS:
            continue
        refs.append({
            'target': target,
            'kind': 'slice-source' if target == info['source_table'] else 'slice-filter-reference',
        })
    info['references'] = refs
    info['base_tables_seen'] = [r['target'] for r in refs]
    info['base_tables_confident'] = sorted(confident)
    return info


def parse_table_block(block: str) -> dict[str, Any]:
    lines = block.splitlines()
    header = lines[0].strip().replace('## Table: ', '', 1)
    table_info: dict[str, Any] = {
        'table': header,
        'meta': {},
        'columns': [],
        'relations': [],
    }

    columns_anchor = block.find('\n### Columns\n')
    meta_part = block[:columns_anchor] if columns_anchor != -1 else block
    columns_part = block[columns_anchor + len('\n### Columns\n'):] if columns_anchor != -1 else ''

    for line in meta_part.splitlines()[1:]:
        if line.startswith('- **'):
            m = re.match(r'- \*\*(.+?)\*\*: (.+)$', line)
            if m:
                table_info['meta'][m.group(1).strip()] = m.group(2).strip().strip('`')

    col_matches = list(COLUMN_RE.finditer(columns_part))
    for idx, cm in enumerate(col_matches):
        start = cm.start()
        end = col_matches[idx + 1].start() if idx + 1 < len(col_matches) else len(columns_part)
        col_block = columns_part[start:end].strip()
        col = parse_column_block(col_block)
        table_info['columns'].append(col)

    table_info['relations'] = infer_relations(table_info)
    return table_info


SKIP_LOCALS = {'_THISROW', '_THISROW_BEFORE', '_THISROW_AFTER'}
SKIP_TARGETS = {'User', '_THISROW', '_THISROW_BEFORE', '_THISROW_AFTER'}


def infer_relations(table_info: dict[str, Any]) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for col in table_info['columns']:
        col_name = col['name']
        col_type = col['type']
        props = col['properties']
        evidence_text = '\n'.join(f'{k}: {v}' for k, v in props.items())

        # Explicit ref-type columns: target may still need inference.
        if col_type == 'Ref':
            candidates = set()
            for m in SLICE_KEY_RE.finditer(evidence_text):
                if m.group(1) not in SKIP_TARGETS:
                    candidates.add(m.group(1))
            if col_name.startswith('Parent '):
                candidates.add(table_info['table'])
            if not candidates and col_name.endswith('ID'):
                candidates.add(col_name.removesuffix('ID').strip())
            if not candidates:
                candidates.add('UNKNOWN')
            for target in sorted(candidates):
                key = (table_info['table'], col_name, target, 'ref-type')
                if key not in seen:
                    seen.add(key)
                    relations.append({
                        'from_table': table_info['table'],
                        'from_column': col_name,
                        'kind': 'ref-type',
                        'target': target,
                        'evidence': 'column type is Ref' if target == 'UNKNOWN' else f'column type is Ref; candidates from expressions: {target}',
                    })

        # Suggested_Values table/key hints.
        if props.get('Suggested_Values'):
            for m in SLICE_KEY_RE.finditer(props['Suggested_Values']):
                target = m.group(1)
                if target in SKIP_TARGETS:
                    continue
                key = (table_info['table'], col_name, target, 'suggested-values')
                if key not in seen:
                    seen.add(key)
                    relations.append({
                        'from_table': table_info['table'],
                        'from_column': col_name,
                        'kind': 'suggested-values',
                        'target': target,
                        'target_key_candidate': m.group(2),
                        'evidence': 'Suggested_Values references target table/key list',
                    })

        # Ref-like dereference usage may appear in other columns' formulas.
        for prop_name, prop_val in props.items():
            if not isinstance(prop_val, str):
                continue
            for d in DEREF_RE.finditer(prop_val):
                local = d.group('local')
                if local in SKIP_LOCALS:
                    continue
                candidates = set()
                for m in SLICE_KEY_RE.finditer(prop_val):
                    if m.group(1) not in SKIP_TARGETS:
                        candidates.add(m.group(1))
                if local in {'Created By'}:
                    candidates.update({'HR_Employees', 'HR_Employees_CurrentlyEmployed_BasicInfo'})
                if not candidates:
                    candidates.add('UNKNOWN')
                for target in sorted(candidates):
                    kind = 'deref-usage'
                    key = (table_info['table'], local, target, kind)
                    if key not in seen:
                        seen.add(key)
                        relations.append({
                            'from_table': table_info['table'],
                            'from_column': local,
                            'kind': kind,
                            'target': target,
                            'remote_column_seen': d.group('remote'),
                            'evidence': f'formula in `{col_name}` uses [{local}].[{d.group("remote")}]',
                            'property': prop_name,
                        })

        # Generic table references found in formulas.
        for prop_name, prop_val in props.items():
            if not isinstance(prop_val, str):
                continue
            for m in LOOKUP_RE.finditer(prop_val):
                target = m.group('table')
                if target in {'Translation', 'Lookup'} or target in SKIP_TARGETS:
                    continue
                key = (table_info['table'], col_name, target, 'lookup-formula')
                if key not in seen:
                    seen.add(key)
                    relations.append({
                        'from_table': table_info['table'],
                        'from_column': col_name,
                        'kind': 'lookup-formula',
                        'target': target,
                        'property': prop_name,
                        'evidence': 'LOOKUP() references target table',
                    })
            for m in SELECT_RE.finditer(prop_val):
                key = (table_info['table'], col_name, m.group('table'), 'select-formula')
                if key not in seen:
                    seen.add(key)
                    relations.append({
                        'from_table': table_info['table'],
                        'from_column': col_name,
                        'kind': 'select-formula',
                        'target': m.group('table'),
                        'property': prop_name,
                        'evidence': 'SELECT() references target table',
                    })
    return relations


def build_payload() -> dict[str, Any]:
    sections = load_sections()
    table_blocks = split_tables(sections['Data Schema'])
    slice_blocks = split_slices(sections.get('Slices', ''))
    parsed = {name: parse_table_block(block) for name, block in table_blocks.items()}
    slices = {name: parse_slice_block(block) for name, block in slice_blocks.items()}
    summary = {
        'table_count': len(parsed),
        'column_count': sum(len(t['columns']) for t in parsed.values()),
        'relation_count': sum(len(t['relations']) for t in parsed.values()),
        'slice_count': len(slices),
    }
    return {
        'source_definition': str(DEFINITION_JSON),
        'summary': summary,
        'tables': parsed,
        'slices': slices,
    }


def write_markdown(payload: dict[str, Any]) -> None:
    lines = []
    lines.append('# Pro-Design prototype schema map')
    lines.append('')
    lines.append(f"- Source: `{payload['source_definition']}`")
    lines.append(f"- Tables parsed: {payload['summary']['table_count']}")
    lines.append(f"- Columns parsed: {payload['summary']['column_count']}")
    lines.append(f"- Relationship hints: {payload['summary']['relation_count']}")
    lines.append(f"- Slices parsed: {payload['summary']['slice_count']}")
    lines.append('')
    lines.append('Use this as a relationship hint map, not gospel. It is built from the exported prototype app definition markdown, so some targets are inferred from Ref types, dereferences, Suggested_Values, LOOKUP(), SELECT(), and slice source/filter evidence.')
    lines.append('')
    lines.append('## Slice collapse map')
    lines.append('')
    lines.append('Use this section to collapse slice names back to their base tables before planning joins or export paths.')
    lines.append('')
    for slice_name, slice_info in payload['slices'].items():
        lines.append(f'### {slice_name}')
        lines.append('')
        lines.append(f"- Source table: `{slice_info['source_table']}`")
        if slice_info['base_tables_seen']:
            lines.append('- Tables seen in slice filter: ' + ', '.join(f'`{t}`' for t in slice_info['base_tables_seen']))
        if slice_info['row_filter']:
            compact = ' '.join(slice_info['row_filter'].split())
            if len(compact) > 220:
                compact = compact[:217] + '...'
            lines.append(f'- Row filter: `{compact}`')
        lines.append('')
    for table_name, table in payload['tables'].items():
        lines.append(f'## {table_name}')
        lines.append('')
        lines.append(f"- Columns: {len(table['columns'])}")
        lines.append(f"- Relationship hints: {len(table['relations'])}")
        relations = defaultdict(list)
        for rel in table['relations']:
            relations[rel['from_column']].append(rel)
        if relations:
            lines.append('- Notable columns with relationship evidence:')
            for col, rels in sorted(relations.items()):
                hints = '; '.join(sorted({f"{r['kind']} -> {r['target']}" for r in rels}))
                lines.append(f'  - `{col}`: {hints}')
        else:
            lines.append('- No relationship hints detected.')
        lines.append('')
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    payload = build_payload()
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    write_markdown(payload)
    print(json.dumps(payload['summary'], ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

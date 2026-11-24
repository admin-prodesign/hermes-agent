#!/usr/bin/env python3
"""Validate dry-run payloads for legacy Case imports.

This is intentionally read-only: it checks generated JSON payload files and the
local schema map, then prints a concise JSON summary. Run AppSheet live duplicate
probes separately before writes.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

DEFAULT_SCHEMA_CANDIDATES = [
    "/home/prodesign/.hermes/skills/appsheet-copilot/references/prodesign-schema-map.json",
    "/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/references/prodesign-schema-map.json",
]

REQUIRED = {
    "Case": ["Row ID", "Created On", "CaseID", "Title", "Description", "Type", "Sub-Type", "Status"],
    "Case_Updates": ["Row ID", "Timestamp", "CaseUpdateID", "Update Summary", "Case Type", "Update Type", "New Status", "CaseID"],
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def table_columns(schema: dict[str, Any], table: str) -> set[str]:
    return {c["name"] for c in schema["tables"][table]["columns"] if c.get("name")}


def default_schema_path() -> str:
    for candidate in DEFAULT_SCHEMA_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return DEFAULT_SCHEMA_CANDIDATES[0]


def main() -> int:
    p = argparse.ArgumentParser(description="Validate legacy Case import dry-run payloads without AppSheet writes.")
    p.add_argument("artifact_dir", help="Directory containing case_payloads.dryrun.json and case_update_payloads.dryrun.json")
    p.add_argument("--schema-map", default=default_schema_path())
    args = p.parse_args()

    base = Path(args.artifact_dir)
    cases = load_json(base / "case_payloads.dryrun.json")
    updates = load_json(base / "case_update_payloads.dryrun.json")
    schema = load_json(Path(args.schema_map))

    errors: list[dict[str, Any]] = []
    rows_by_table = {"Case": cases, "Case_Updates": updates}
    for table, rows in rows_by_table.items():
        cols = table_columns(schema, table)
        unknown = sorted({k for r in rows for k in r if k not in cols})
        if unknown:
            errors.append({"check": f"{table} unknown columns", "count": len(unknown), "examples": unknown[:20]})
        for field in REQUIRED[table]:
            blank = [idx for idx, r in enumerate(rows, start=1) if r.get(field) in (None, "")]
            if blank:
                errors.append({"check": f"{table} required blank: {field}", "count": len(blank), "examples": blank[:20]})

    for table, rows, key in [
        ("Case", cases, "CaseID"),
        ("Case", cases, "Row ID"),
        ("Case_Updates", updates, "CaseUpdateID"),
        ("Case_Updates", updates, "Row ID"),
    ]:
        counts = collections.Counter(r.get(key) for r in rows)
        dups = [k for k, v in counts.items() if v > 1]
        if dups:
            errors.append({"check": f"{table} duplicate {key}", "count": len(dups), "examples": dups[:20]})

    case_ids = {r.get("CaseID") for r in cases}
    missing_parent = sorted({u.get("CaseID") for u in updates if u.get("CaseID") not in case_ids})
    if missing_parent:
        errors.append({"check": "Case_Updates parent CaseID missing in payload", "count": len(missing_parent), "examples": missing_parent[:20]})

    updates_by_case: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for u in updates:
        updates_by_case[u.get("CaseID", "")].append(u)
    mismatches = []
    for c in cases:
        us = updates_by_case.get(c.get("CaseID"), [])
        if not us:
            mismatches.append([c.get("CaseID"), "no updates"])
        elif us[-1].get("New Status") != c.get("Status"):
            mismatches.append([c.get("CaseID"), c.get("Status"), us[-1].get("New Status"), us[-1].get("CaseUpdateID")])
    if mismatches:
        errors.append({"check": "Final Case_Updates New Status != parent Case Status", "count": len(mismatches), "examples": mismatches[:20]})

    summary = {
        "artifact_dir": str(base),
        "case_rows": len(cases),
        "case_update_rows": len(updates),
        "case_status_counts": dict(collections.Counter(r.get("Status") for r in cases)),
        "case_update_status_counts": dict(collections.Counter(r.get("New Status") for r in updates)),
        "errors": errors,
        "ok_to_consider_live_import": not errors,
        "live_duplicate_probe_required": True,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

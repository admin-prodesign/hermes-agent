#!/usr/bin/env python3
# Canonical documentation: [[syntheses/appsheet-data-capture-map|AppSheet Data Capture Map]]
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

ENV_PATH_DEFAULT = "/home/prodesign/.openclaw/workspace/projects/AppSheet/keydrop/prototype-app.env"
EXPORT_DIR_DEFAULT = "/home/prodesign/.openclaw/workspace/projects/AppSheet/exports"
API_BASE = "https://www.appsheet.com/api/v2/apps/{app_id}/tables/{table}/Action"
XML_BAD_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


@dataclass
class EmployeeMatch:
    person_id: str
    name_zh: str
    name_zh_en: str
    employee_id: str
    appsheet_email: str
    raw: dict[str, Any]


def load_env(path: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    required = ["APP_ID", "APP_ACCESS_KEY"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise SystemExit(f"Missing required env keys in {path}: {', '.join(missing)}")
    return data


def appsheet_post(app_id: str, access_key: str, table: str, payload: dict[str, Any], run_as: str | None = None) -> list[dict[str, Any]]:
    headers = {
        "ApplicationAccessKey": access_key,
        "Content-Type": "application/json",
    }
    if run_as:
        headers["RunAsUserEmail"] = run_as
    response = requests.post(
        API_BASE.format(app_id=app_id, table=table),
        headers=headers,
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise SystemExit(f"Unexpected API response type for {table}: {type(data).__name__}")
    return data


def esc(value: str) -> str:
    return value.replace('"', '\\"')


def clean(value: Any) -> str:
    if value is None:
        return ""
    return XML_BAD_RE.sub("", str(value))


def month_bounds(month: str) -> tuple[str, str]:
    start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")


def build_employee_selector(query: str) -> str:
    q = esc(query)
    return (
        "OrderBy(Filter(HR_Employees, OR("
        f'[PersonID] = "{q}", '
        f'[Employee ID] = "{q}", '
        f'[Appsheet Email] = "{q}", '
        f'CONTAINS([Name_ZH], "{q}"), '
        f'CONTAINS([Name_ZH_EN], "{q}")'
        ")), [PersonID], true)"
    )


def resolve_employee(app_id: str, access_key: str, run_as: str | None, person_id: str | None, person_query: str | None) -> EmployeeMatch:
    if person_id:
        rows = appsheet_post(
            app_id,
            access_key,
            "HR_Employees",
            {"Action": "Find", "Properties": {"Selector": f'Filter(HR_Employees, [PersonID] = "{esc(person_id)}")'}, "Rows": []},
            run_as=run_as,
        )
    else:
        assert person_query
        rows = appsheet_post(
            app_id,
            access_key,
            "HR_Employees",
            {"Action": "Find", "Properties": {"Selector": build_employee_selector(person_query)}, "Rows": []},
            run_as=run_as,
        )

    matches = [
        EmployeeMatch(
            person_id=str(r.get("PersonID", "")),
            name_zh=str(r.get("Name_ZH", "")),
            name_zh_en=str(r.get("Name_ZH_EN", "")),
            employee_id=str(r.get("Employee ID", "")),
            appsheet_email=str(r.get("Appsheet Email", "")),
            raw=r,
        )
        for r in rows
        if r.get("PersonID")
    ]

    if not matches:
        needle = person_id or person_query or ""
        raise SystemExit(f"No HR_Employees match found for: {needle}")

    if person_query:
        exact = [
            m for m in matches
            if person_query in {m.person_id, m.employee_id, m.appsheet_email, m.name_zh, m.name_zh_en}
        ]
        if len(exact) == 1:
            return exact[0]

    unique_by_id = {m.person_id: m for m in matches}
    if len(unique_by_id) > 1:
        choices = [
            {
                "PersonID": m.person_id,
                "Name_ZH": m.name_zh,
                "Name_ZH_EN": m.name_zh_en,
                "Employee ID": m.employee_id,
                "Appsheet Email": m.appsheet_email,
            }
            for m in unique_by_id.values()
        ]
        raise SystemExit("Multiple HR_Employees matches found; refine the query:\n" + json.dumps(choices, ensure_ascii=False, indent=2))

    return next(iter(unique_by_id.values()))


def build_activitylog_selector(person_id: str, start_at: str, end_at: str, reads_only: bool) -> str:
    clauses = [
        f'[Timestamp] >= DATETIME("{esc(start_at)}")',
        f'[Timestamp] < DATETIME("{esc(end_at)}")',
        f'[Created By] = "{esc(person_id)}"',
    ]
    if reads_only:
        clauses.append('[RefDocs_Read_Check] = "Y"')
    return f'OrderBy(Filter(ActivityLog, AND({", ".join(clauses)})), [Timestamp], false)'


def export_rows(rows: list[dict[str, Any]], out_prefix: Path, summary_rows: list[tuple[str, str]]) -> dict[str, str]:
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = out_prefix.with_suffix(".json")
    csv_path = out_prefix.with_suffix(".csv")
    xlsx_path = out_prefix.with_suffix(".xlsx")
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    columns: list[str] = []
    seen: set[str] = set()
    preferred = [
        "ActivityLogID",
        "Timestamp",
        "Created By",
        "Employee",
        "Notification Employee",
        "RefDocs_Read_Check",
        "Relevant Reference Documents",
        "Category",
        "Sub-Category",
        "ActivityLog Status",
        "Description",
    ]
    for key in preferred:
        if key not in seen:
            seen.add(key)
            columns.append(key)
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                columns.append(key)

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([clean(row.get(col, "")) for col in columns])

    wb = Workbook()
    ws = wb.active
    ws.title = "Rows"
    ws.append(columns)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append([clean(row.get(col, "")) for col in columns])
    ws.freeze_panes = "A2"
    for idx, col in enumerate(columns, start=1):
        max_len = max([len(col)] + [len(clean(r.get(col, ""))) for r in rows]) if rows else len(col)
        ws.column_dimensions[get_column_letter(idx)].width = min(max(max_len + 2, 12), 48)

    summary = wb.create_sheet("Summary")
    for key, value in summary_rows:
        summary.append([key, value])
    for cell in summary["A"]:
        cell.font = Font(bold=True)
    summary.column_dimensions["A"].width = 22
    summary.column_dimensions["B"].width = 120
    wb.save(xlsx_path)

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "xlsx": str(xlsx_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Pro-Design ActivityLog rows by resolved employee -> PersonID -> Created By.")
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--person-id", help="Exact HR_Employees PersonID (for example SRQUDSAU)")
    who.add_argument("--person-query", help="Employee lookup string: Chinese name, Name_ZH_EN, Employee ID, or Appsheet Email")
    window = parser.add_mutually_exclusive_group(required=True)
    window.add_argument("--month", help="Month window in YYYY-MM format")
    window.add_argument("--start", help="Window start in YYYY-MM-DD or YYYY-MM-DD HH:MM:SS (UTC literal passed to AppSheet)")
    parser.add_argument("--end", help="Window end in YYYY-MM-DD or YYYY-MM-DD HH:MM:SS (required with --start)")
    parser.add_argument("--reads-only", action="store_true", help="Also require RefDocs_Read_Check = Y")
    parser.add_argument("--env-file", default=ENV_PATH_DEFAULT, help=f"Env file with APP_ID / APP_ACCESS_KEY / RUN_AS_USER_EMAIL (default: {ENV_PATH_DEFAULT})")
    parser.add_argument("--export-dir", default=EXPORT_DIR_DEFAULT, help=f"Output directory (default: {EXPORT_DIR_DEFAULT})")
    parser.add_argument("--filename-prefix", default=None, help="Optional filename prefix without extension")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = load_env(args.env_file)
    app_id = env["APP_ID"]
    access_key = env["APP_ACCESS_KEY"]
    run_as = env.get("RUN_AS_USER_EMAIL") or None

    if args.month:
        start_at, end_at = month_bounds(args.month)
        window_slug = args.month
    else:
        if not args.end:
            raise SystemExit("--end is required when --start is used")
        start_at = args.start
        end_at = args.end
        window_slug = re.sub(r"[^0-9A-Za-z_-]+", "-", f"{args.start}_to_{args.end}").strip("-")

    employee = resolve_employee(app_id, access_key, run_as, args.person_id, args.person_query)
    selector = build_activitylog_selector(employee.person_id, start_at, end_at, args.reads_only)
    rows = appsheet_post(
        app_id,
        access_key,
        "ActivityLog",
        {"Action": "Find", "Properties": {"Selector": selector}, "Rows": []},
        run_as=run_as,
    )

    if args.filename_prefix:
        prefix = args.filename_prefix
    else:
        mode = "reads_" if args.reads_only else ""
        prefix = f"activitylog_{window_slug}_{mode}created-by_{employee.person_id}"
    out_prefix = Path(args.export_dir) / prefix

    summary_rows = [
        ("App ID", app_id),
        ("Run As", run_as or ""),
        ("Resolved PersonID", employee.person_id),
        ("Resolved Name_ZH", employee.name_zh),
        ("Resolved Name_ZH_EN", employee.name_zh_en),
        ("Resolved Employee ID", employee.employee_id),
        ("Resolved Appsheet Email", employee.appsheet_email),
        ("Selector", selector),
        ("Row Count", str(len(rows))),
        ("Reads Only", "Y" if args.reads_only else "N"),
        ("Generated At", datetime.now(timezone.utc).isoformat()),
    ]
    paths = export_rows(rows, out_prefix, summary_rows)

    result = {
        "row_count": len(rows),
        "resolved_employee": {
            "PersonID": employee.person_id,
            "Name_ZH": employee.name_zh,
            "Name_ZH_EN": employee.name_zh_en,
            "Employee ID": employee.employee_id,
            "Appsheet Email": employee.appsheet_email,
        },
        "selector": selector,
        "files": paths,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

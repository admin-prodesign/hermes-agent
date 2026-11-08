#!/usr/bin/env python3
"""Count Case_Updates still ReadyToProcess but not yet present in ProcessingQueue.

Read-only probe for Pro-Design/AppSheet queue triage. It intentionally pulls
Case_Updates from the prototype/Data Studio app context (fuller source backlog)
and ProcessingQueue from the physical Google Sheet tab (deployed queue backing
store), then compares unique CaseUpdateID values to ProcessingQueue SourceRowKey.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from appsheet_record_ops import AppSheetClient  # noqa: E402

DEFAULT_ENV = "/home/prodesign/.openclaw/workspace/projects/AppSheet/keydrop/prototype-app.env"
DEFAULT_SHEET_ID = "1n4UtbJkXb_JfrrEt8eeBb_CCgGsPvsr3r7Zmkwbf7NU"
DEFAULT_QUEUE_RANGE = "ProcessingQueue!A1:AP"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count ReadyToProcess Case_Updates not yet added to ProcessingQueue."
    )
    parser.add_argument("--env-file", default=DEFAULT_ENV, help="Prototype/Data Studio AppSheet env file")
    parser.add_argument("--spreadsheet-id", default=DEFAULT_SHEET_ID, help="ProcessingQueue backing spreadsheet ID")
    parser.add_argument("--queue-range", default=DEFAULT_QUEUE_RANGE, help="A1 range containing ProcessingQueue headers/data")
    parser.add_argument("--examples", type=int, default=20, help="Number of missing CaseUpdateID examples to include")
    return parser.parse_args()


def load_sheet_values(spreadsheet_id: str, queue_range: str) -> list[list[str]]:
    result = subprocess.run(
        ["gog", "sheets", "get", spreadsheet_id, queue_range, "--json", "--no-input"],
        check=True,
        text=True,
        capture_output=True,
    )
    data = json.loads(result.stdout)
    values = (
        data.get("values")
        or data.get("Values")
        or data.get("data", {}).get("values")
        or data.get("result", {}).get("values")
    )
    if not values:
        raise RuntimeError(f"Could not parse values from gog output; top-level keys={list(data)[:20]}")
    return values


def main() -> int:
    args = parse_args()

    client = AppSheetClient(args.env_file)
    ready_rows = client.find("Case_Updates", 'Filter(Case_Updates, [Flag_Processed] = "ReadyToProcess")')
    ready_ids = {
        str(row.get("CaseUpdateID") or "").strip()
        for row in ready_rows
        if str(row.get("CaseUpdateID") or "").strip()
    }
    missing_source_key_count = len(ready_rows) - len(ready_ids)

    values = load_sheet_values(args.spreadsheet_id, args.queue_range)
    headers = values[0]
    idx = {header: i for i, header in enumerate(headers)}
    required = ["SourceTable", "SourceRowKey", "Status", "JobType"]
    missing_headers = [header for header in required if header not in idx]
    if missing_headers:
        raise RuntimeError(f"ProcessingQueue range missing required headers: {missing_headers}; headers={headers}")

    def cell(row: list[str], header: str) -> str:
        i = idx[header]
        return str(row[i]).strip() if i < len(row) else ""

    queue_case_ids: set[str] = set()
    queue_rows = 0
    queue_status = Counter()
    queue_job = Counter()
    ready_in_queue_rows = 0
    ready_in_queue_status = Counter()
    ready_in_queue_job = Counter()

    for row in values[1:]:
        if cell(row, "SourceTable") != "Case_Updates":
            continue
        queue_rows += 1
        source_key = cell(row, "SourceRowKey")
        status = cell(row, "Status") or "(blank)"
        job_type = cell(row, "JobType") or "(blank)"
        if source_key:
            queue_case_ids.add(source_key)
        queue_status[status] += 1
        queue_job[job_type] += 1
        if source_key in ready_ids:
            ready_in_queue_rows += 1
            ready_in_queue_status[status] += 1
            ready_in_queue_job[job_type] += 1

    remaining = sorted(ready_ids - queue_case_ids)
    print(
        json.dumps(
            {
                "ready_to_process_case_updates_rows_returned": len(ready_rows),
                "ready_to_process_unique_caseupdateids": len(ready_ids),
                "ready_rows_missing_caseupdateid": missing_source_key_count,
                "processingqueue_case_updates_rows": queue_rows,
                "processingqueue_unique_case_updates_sourcerowkeys": len(queue_case_ids),
                "ready_already_in_queue_rows": ready_in_queue_rows,
                "ready_already_in_queue_unique": len(ready_ids & queue_case_ids),
                "remaining_not_yet_added_to_processingqueue": len(remaining),
                "queue_status_counts_for_case_updates": dict(queue_status),
                "queue_job_counts_for_case_updates": dict(queue_job),
                "ready_already_in_queue_status_counts": dict(ready_in_queue_status),
                "ready_already_in_queue_job_counts": dict(ready_in_queue_job),
                "remaining_examples": remaining[: args.examples],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

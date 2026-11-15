#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from appsheet_record_ops import AppSheetClient


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Probe an AppSheet table with a bounded selector.")
    p.add_argument("table")
    p.add_argument("selector")
    p.add_argument("--env-file", default="/home/prodesign/.openclaw/workspace/projects/AppSheet/keydrop/prototype-app.env")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    client = AppSheetClient(args.env_file)
    rows = client.find(args.table, args.selector)
    print(json.dumps({"row_count": len(rows), "rows": rows[:20]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

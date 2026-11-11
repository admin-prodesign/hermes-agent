#!/usr/bin/env python3
"""Stable gate token for the IT meeting progress-summary prepare job.

Prints one deterministic line and nothing else:
- due:YYYY-MM-DD on a 2nd or 4th Tuesday in Asia/Taipei
- not_due on every other day
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Asia/Taipei")


def meeting_date(now: datetime) -> str | None:
    day = now.astimezone(TIMEZONE).date()
    if day.weekday() != 1:
        return None
    ordinal = ((day.day - 1) // 7) + 1
    if ordinal not in (2, 4):
        return None
    return day.isoformat()


def main() -> int:
    token = meeting_date(datetime.now(TIMEZONE))
    print(f"due:{token}" if token else "not_due")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

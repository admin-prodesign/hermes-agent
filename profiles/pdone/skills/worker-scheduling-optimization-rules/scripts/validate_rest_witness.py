#!/usr/bin/env python3
"""Validate a constructive monthly rest/work witness independently of CP-SAT.

This checks monthly counts, consecutive-work reset semantics, and windows wholly
inside the target month. Cross-month 7/14-day windows require exact prior-month
calendar history and are deliberately reported as not evaluated.
"""
from __future__ import annotations

import argparse
import json
from typing import Iterable


def parse_days(raw: str) -> list[int]:
    if not raw.strip():
        return []
    values = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if len(values) != len(set(values)):
        raise ValueError("rest days contain duplicates")
    return sorted(values)


def internal_windows(rests: set[int], total_days: int, size: int) -> list[dict]:
    if size > total_days:
        return []
    rows = []
    for start in range(1, total_days - size + 2):
        end = start + size - 1
        days = [day for day in range(start, end + 1) if day in rests]
        rows.append({"start": start, "end": end, "rest_count": len(days), "rest_days": days})
    return rows


def max_streak(total_days: int, rests: set[int], previous_consecutive: int) -> tuple[int, int, list[int]]:
    streak = previous_consecutive
    max_with_carryover = streak
    max_in_month = 0
    target_streak = 0
    completed: list[int] = []
    for day in range(1, total_days + 1):
        if day in rests:
            if target_streak:
                completed.append(target_streak)
            streak = 0
            target_streak = 0
        else:
            streak += 1
            target_streak += 1
            max_with_carryover = max(max_with_carryover, streak)
            max_in_month = max(max_in_month, target_streak)
    if target_streak:
        completed.append(target_streak)
    return max_in_month, max_with_carryover, completed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, required=True, help="days in target month")
    parser.add_argument("--rests", required=True, help="comma-separated target-month rest days")
    parser.add_argument("--expected-rests", type=int, required=True)
    parser.add_argument("--previous-consecutive", type=int, default=0)
    parser.add_argument("--max-consecutive", type=int, default=3)
    parser.add_argument("--min-rests-7", type=int, default=2)
    parser.add_argument("--min-rests-14", type=int, default=4)
    args = parser.parse_args()

    rest_days = parse_days(args.rests)
    if args.days < 1:
        raise ValueError("--days must be positive")
    invalid = [day for day in rest_days if day < 1 or day > args.days]
    if invalid:
        raise ValueError(f"rest days outside target month: {invalid}")
    if args.previous_consecutive < 0:
        raise ValueError("--previous-consecutive must be non-negative")

    rests = set(rest_days)
    work_days = [day for day in range(1, args.days + 1) if day not in rests]
    max_month, max_carry, streaks = max_streak(args.days, rests, args.previous_consecutive)
    windows7 = internal_windows(rests, args.days, 7)
    windows14 = internal_windows(rests, args.days, 14)
    min7 = min((row["rest_count"] for row in windows7), default=None)
    min14 = min((row["rest_count"] for row in windows14), default=None)

    checks = {
        "exact_rest_count": len(rest_days) == args.expected_rests,
        "max_consecutive_with_carryover": max_carry <= args.max_consecutive,
        "internal_7_day_windows": min7 is None or min7 >= args.min_rests_7,
        "internal_14_day_windows": min14 is None or min14 >= args.min_rests_14,
    }
    payload = {
        "total_days": args.days,
        "rest_days": rest_days,
        "rest_count": len(rest_days),
        "work_days": work_days,
        "work_count": len(work_days),
        "previous_consecutive": args.previous_consecutive,
        "work_streaks_in_month": streaks,
        "max_work_streak_in_month": max_month,
        "max_work_streak_with_carryover": max_carry,
        "minimum_rests_internal_7_day_window": min7,
        "minimum_rests_internal_14_day_window": min14,
        "checks": checks,
        "all_evaluated_checks_pass": all(checks.values()),
        "cross_month_windows": "not evaluated; supply and inspect exact prior-month calendar history separately",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["all_evaluated_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Parse AppSheet Performance Analyzer raw sync rows into timing/failure rankings.

Usage:
  python3 scripts/perf_raw_timing_analysis.py perf-raw-YYYY.json [perf-scan-YYYY.json] [out.json]

This is intentionally read-only. It handles common exportlog shapes/pitfalls:
- raw JSON as either a list or {"rows": [...]}
- Properties as dict, JSON string, or Python-literal-looking string
- Properties.Performance as a nested JSON string
- AppSheet duration strings like 00:02:41.7585108
- table timing nodes Mid == 116 with table param Pid 13
- virtual/computed column timing nodes Mid == 222 with table Pid 13 and column Pid 1
- paired summary/detail rows by counting only rows with Properties.Performance as detailed samples
"""

from __future__ import annotations

import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def parse_duration(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        if ":" not in s:
            return float(s)
        parts = s.split(":")
        days = 0
        if len(parts) == 3:
            hpart, minutes, seconds = parts
            if "." in hpart:
                day_s, hour_s = hpart.split(".", 1)
                days = int(day_s)
                hours = int(hour_s)
            else:
                hours = int(hpart)
            return days * 86400 + hours * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
    except Exception:
        return None
    return None


def parse_maybe(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s:
        return value
    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(s)
        except Exception:
            pass
    return value


def load_rows(raw_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    obj = json.loads(raw_path.read_text())
    if isinstance(obj, list):
        return obj, {}
    if isinstance(obj, dict):
        rows = obj.get("rows") or obj.get("Rows") or []
        return rows, obj.get("meta") or {}
    return [], {}


def params_map(node: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    params = node.get("Params")
    if isinstance(params, dict):
        param_list = params.get("ParamList") or params.get("paramList") or []
        if isinstance(param_list, dict):
            param_list = [param_list]
        if isinstance(param_list, list):
            for item in param_list:
                if isinstance(item, dict):
                    pid = item.get("Pid") or item.get("pid")
                    val = item.get("Value") if "Value" in item else item.get("value")
                    if pid is not None:
                        out[str(pid)] = val
        for key, val in params.items():
            if key not in ("ParamList", "paramList") and not isinstance(val, (dict, list)):
                out[str(key)] = val
    elif isinstance(params, list):
        for item in params:
            if isinstance(item, dict):
                pid = item.get("Pid") or item.get("pid")
                val = item.get("Value") if "Value" in item else item.get("value")
                if pid is not None:
                    out[str(pid)] = val
    return out


def iter_nodes(perf: Any):
    stack: list[Any] = []
    if isinstance(perf, dict):
        stack.append(perf.get("PerformanceTimingRoot") or perf.get("Timer") or perf)
    elif isinstance(perf, list):
        stack.extend(perf)
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        yield node
        for key in ("Children", "children"):
            children = node.get(key)
            if isinstance(children, list):
                stack.extend(reversed(children))
            elif isinstance(children, dict):
                stack.append(children)


def node_time(node: dict[str, Any]) -> float | None:
    for key in ("Time", "Elapsed", "Duration"):
        seconds = parse_duration(node.get(key))
        if seconds is not None:
            return seconds
    timer = node.get("Timer")
    if isinstance(timer, dict):
        for key in ("Time", "Elapsed", "Duration"):
            seconds = parse_duration(timer.get(key))
            if seconds is not None:
                return seconds
    return None


def quant(values: list[float]) -> dict[str, float] | None:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None

    def pct(p: float) -> float:
        if len(vals) == 1:
            return vals[0]
        k = (len(vals) - 1) * p / 100
        f = int(k)
        c = min(f + 1, len(vals) - 1)
        return vals[f] + (vals[c] - vals[f]) * (k - f)

    return {"n": len(vals), "avg": sum(vals) / len(vals), "p50": pct(50), "p90": pct(90), "max": max(vals)}


def compact_stats(series: dict[str, list[float]], limit: int = 20) -> list[dict[str, Any]]:
    ranked = []
    for name, values in series.items():
        stats = quant(values)
        if stats:
            ranked.append({"name": name, **stats})
    ranked.sort(key=lambda x: (x.get("p90", 0), x.get("avg", 0), x.get("max", 0)), reverse=True)
    return ranked[:limit]


def classify_failure(result: str, exception: str) -> str:
    msg = exception or result or "Failure"
    if "Data table 'ActivityLog' is not accessible" in msg:
        return "sync table timeout: ActivityLog not accessible"
    if "Data table 'Case_Updates' is not accessible" in msg:
        return "sync table timeout: Case_Updates not accessible"
    if "TaskCanceledException" in msg or "OperationCanceledException" in msg or "canceled" in msg.lower():
        return "timeout/cancellation/cache-lock"
    if result.lower() == "failure" and not exception:
        return "generic failure row without exception detail"
    return msg.split("\n", 1)[0][:240]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    raw_path = Path(sys.argv[1])
    scan_path = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None
    out_path = Path(sys.argv[3]) if len(sys.argv) > 3 else raw_path.with_name(raw_path.stem + "-analysis.json")

    rows, meta = load_rows(raw_path)
    scan: dict[str, Any] = {}
    if scan_path and scan_path.exists():
        scan = json.loads(scan_path.read_text())

    durations: list[float] = []
    table_times: dict[str, list[float]] = defaultdict(list)
    vc_times: dict[str, list[float]] = defaultdict(list)
    row_counts: dict[str, list[int]] = defaultdict(list)
    failure_counter: Counter[str] = Counter()
    failure_tables: Counter[str] = Counter()
    result_counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    detailed = 0

    for row in rows:
        result = str(row.get("Result") or row.get("result") or "")
        if result:
            result_counts[result] += 1
        props = parse_maybe(row.get("Properties") or row.get("properties") or {})
        exception = ""
        if isinstance(props, dict):
            exception = props.get("Exception") or props.get("exception") or ""
        exception = exception or row.get("Exception") or row.get("exception") or ""

        if result.lower() == "failure" or exception:
            cls = classify_failure(result, str(exception))
            failure_counter[cls] += 1
            if "ActivityLog not accessible" in cls:
                failure_tables["ActivityLog"] += 1
            if "Case_Updates not accessible" in cls:
                failure_tables["Case_Updates"] += 1
            if len(examples) < 10:
                examples.append({
                    "ts": row.get("EventTimeStamp") or row.get("TimeStamp") or row.get("timestamp"),
                    "result": result,
                    "class": cls,
                    "exception_head": str(exception).split("\n", 1)[0][:500],
                })

        perf = None
        if isinstance(props, dict):
            perf = parse_maybe(props.get("Performance") or props.get("performance"))
        if not isinstance(perf, (dict, list)):
            continue
        detailed += 1

        if isinstance(perf, dict):
            seconds = parse_duration(perf.get("Time"))
            if seconds is None:
                root = perf.get("PerformanceTimingRoot") or perf.get("Timer")
                if isinstance(root, dict):
                    seconds = node_time(root)
            if seconds is not None:
                durations.append(seconds)

        for node in iter_nodes(perf):
            mid = str(node.get("Mid") or node.get("mid") or "")
            seconds = node_time(node)
            if seconds is None:
                continue
            pmap = params_map(node)
            table = pmap.get("13")
            col = pmap.get("1")
            rc = pmap.get("9")
            rc_int = None
            try:
                if rc not in (None, ""):
                    rc_int = int(str(rc).replace(",", ""))
            except Exception:
                pass
            if mid == "116" and table:
                table_times[str(table)].append(seconds)
                if rc_int is not None:
                    row_counts[str(table)].append(rc_int)
            elif mid == "222":
                name = f"{table or '?'}[{col or '?'}]"
                vc_times[name].append(seconds)
                if rc_int is not None:
                    row_counts[name].append(rc_int)

    analysis = {
        "raw_path": str(raw_path),
        "scan_path": str(scan_path) if scan_path else None,
        "meta": meta,
        "window": (scan.get("report") or {}).get("window"),
        "counts": (scan.get("report") or {}).get("counts"),
        "raw_rows": len(rows),
        "detailed_timing_samples": detailed,
        "result_counts": dict(result_counts),
        "duration_seconds": quant(durations),
        "top_table_timings": compact_stats(table_times, 20),
        "top_virtual_column_timings": compact_stats(vc_times, 20),
        "row_count_observations": {
            k: {"min": min(v), "max": max(v), "latest": v[-1], "n": len(v)}
            for k, v in row_counts.items()
            if v
        },
        "failure_classes": failure_counter.most_common(20),
        "failure_tables": failure_tables.most_common(),
        "failure_examples": examples,
    }
    out_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2))
    print(out_path)
    print(json.dumps({
        "raw_rows": analysis["raw_rows"],
        "detailed_timing_samples": analysis["detailed_timing_samples"],
        "duration_seconds": analysis["duration_seconds"],
        "failure_classes": analysis["failure_classes"],
        "failure_tables": analysis["failure_tables"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

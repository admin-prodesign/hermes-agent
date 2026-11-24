# Deterministic-gated AppSheet steward notes (2026-06-20)

This note captures a repeatable workflow refinement from the AppSheet Performance Steward run on 2026-06-20.

## What worked

- Treat the deterministic gate packet as the first evidence source when it already contains actionable evidence.
- Avoid repeating expensive discovery that the gate packet already answered; only rerun scans when you need verification or a bounded comparison window.
- For sync-only scans, expect that generated `perf-scan-*.json` may omit timing rankings. Parse the companion `perf-raw-*.json` with `scripts/perf_raw_timing_analysis.py` and save the derived `perf-analysis-*.json` beside the scan artifacts.
- Use the active-profile AppSheet venv Python for scan execution, then validate the derived analysis JSON with `python3 -m json.tool` before reporting.

## Evidence shapes seen

- Watchdog gate: 237 failure rows, dominated by `OperationCanceledException` / `TaskCanceledException` and stale-row lookup errors around `HeartBeat` / `ProcessingQueue` workers.
- Sync-only scan: 31 detailed timing samples, `p90 = 78.94s`, with `ActivityLog`, `Case_Updates`, `Case`, `Lookup`, and attachment tables the main drag.
- Low-confidence noise remains when failure rows lack exception detail; keep those separate from the real runtime/smoothness findings.

## Practical reminder

- Keep the steward output concise and evidence-backed; the detailed JSON plan stays on disk.
- Live AppSheet definition edits, data writes, bot rewires, Drive/Sheets edits, permission changes, and restarts remain approval-gated.

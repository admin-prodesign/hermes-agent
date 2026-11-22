# 2026-07 作業員-日 writeback timeout notes

Use this note when a future worker-scheduling run has a feasible generated schedule but the live writeback times out or returns no write receipt.

## Context

During the July 2026 `作業員-日` rerun, the solver preview was feasible:

- source report: `/home/prodesign/.hermes/profiles/pdone/tmp/worker-scheduling-2026-07/rerun-operator-day-mcp-20260625-preview-90/generated-schedule-report.json`
- group: `day / 作業員-日`
- solver status: `FEASIBLE`
- candidate schedule actions: `682`
- changed actions: `230`

The old combined `write_generated_schedule` path re-solved the schedule and could degrade from a prior feasible preview into `UNKNOWN`. The split path `write_generated_schedule_from_report` correctly avoided re-solving, but the write still timed out before producing `generated-schedule-write-report.json`.

## Durable lessons

1. **Never use the combined solve+write path after a feasible preview.** Use `write_generated_schedule_from_report` with the existing `generated-schedule-report.json` so the write does not re-run OR-Tools.
2. **Receipt-first after timeout.** If the write action times out, inspect the output directory before retrying. A directory containing only `mcp-write-generated-schedule-from-report-plan.json` means the write was planned but not receipt-confirmed; do not claim completion.
3. **Run a read-only preflight diagnostic after repeated timeouts.** A quick `preflight` proves the MCP server can still parse/read and separates read access from writeback timeout.
4. **Bound formatting work for large operator groups.** Formatting unchanged cells can create many Google Sheets format calls. Prefer write code that formats changed cells only, or chunk/batch formatting more aggressively, while still recording unchanged cells as formatted-only in receipts.
5. **Fix syntax/tooling bugs before more retries.** The split write initially surfaced `unterminated string literal ... shift_scheduler_phase1.py, line 228`; the robust implementation of `quote_sheet_title()` is:

```python
def quote_sheet_title(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"
```

6. **Do not use visual/image tools for scheduling unless the user asks about an attached screenshot or visual evidence.** Scheduling runs should stay on MCP receipts and sheet readbacks; irrelevant `vision_analyze` calls are noise in the thread.

## Reporting rule

In Mattermost group/shared channels, report both English and Traditional Chinese. For failed writes, say exactly what has a receipt and what does not:

- feasible solve report path,
- attempted write output directory,
- whether `generated-schedule-write-report.json` exists,
- whether verification exists and mismatches count,
- whether a read-only preflight still works.

Do not infer completion from a timeout or from the presence of only a plan receipt.

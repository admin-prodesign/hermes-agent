# AppSheet Current Health Check Pattern

Use this when Andy asks a broad status question such as "How does AppSheet look now?" or "Is AppSheet healthy now?" and the answer should be grounded in fresh Performance Analyzer data without applying live changes.

## Goal

Produce a concise, evidence-backed operational readout that separates:

1. App runnable / broad outage status.
2. User sync smoothness.
3. Automation/runtime failure hot spots.
4. Candidate next fixes that require approval.

This is a read-only workflow. Do not save AppSheet definitions, promote versions, edit rows, clear queues, or mutate Google Sheets/Drive data while performing the check.

## Recommended scans

Run two fresh read-only Performance Analyzer scans into a timestamped or `manual-now` directory:

1. **Failures-only runtime scan** for recent automation health, usually 120 minutes:

```bash
APP_PY=/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace/ops/venvs/venv-appsheet/bin/python
SCAN=/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace/tools/appsheet-migration/scripts/perf_analyzer_scan.py
OUT=/home/prodesign/.hermes/profiles/pdone/logs/appsheet-performance-steward/manual-now
mkdir -p "$OUT"
"$APP_PY" "$SCAN" 120 --tz UTC --failures-only --out-dir "$OUT" --max-examples 15 --emit-prompt-packet
```

2. **Sync-only smoothness scan** for user sync health, usually 360 minutes:

```bash
"$APP_PY" "$SCAN" 360 --tz UTC \
  --no-adds --no-updates --no-deletes --no-workflows --no-reports --no-api --no-documents \
  --out-dir "$OUT" --max-examples 10 --emit-prompt-packet
```

3. Parse raw timing for the sync-only raw file:

```bash
/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace/ops/venvs/venv-appsheet/bin/python \
  /home/prodesign/.hermes/profiles/pdone/skills/appsheet-copilot/scripts/perf_raw_timing_analysis.py \
  "$OUT/perf-raw-<timestamp>.json"
```

## Interpretation checklist

- If sync rows are mostly `Success` and there is no schema/data-source/auth exception cluster, say the app appears runnable rather than implying it is clean.
- Report sync duration distribution from the parsed timing analysis: p50, p90, max, and sample count.
- Explicitly label **top-level sync durations** separately from **nested table/virtual-column timings**. Do not imply that table p90 values such as `ActivityLog p90=70s` are separate visible Performance Analyzer sync rows; they are internal timing components extracted from `Properties.Performance`.
- When the user supplies their own Performance Analyzer export, parse that exact file and compare its window/filter to your scan before reconciling differences. A latest-1000 mixed export can legitimately show much shorter current top-level syncs than an earlier 2h/6h sync-only scan.
- If a definition save/stable promotion happened recently, avoid making the headline from a sync window that straddles the promotion timestamp. Label the straddling scan as mixed-context, then run a shorter clean post-change-only sync window before claiming improvement/regression.
- When validating a targeted performance fix, report both the local target metric and whole-app health: e.g. “the target VC disappeared from top timings / target table p90 improved, but overall sync remains slow due to ActivityLog/Case/Lookup.” Do not overstate a local win as whole-app health.
- Report sync failures separately from automation failures; a generic one-off sync `Failure` row without exception detail is usually context, not the headline.
- For automation health, rank by `TOP_PROCESSES`, `TOP_TABLES`, and failure signatures.
- Treat `OperationCanceledException`, `TaskCanceledException`, `Request cancelled`, and cache-lock/process-instance reads as AppSheet runtime instability/timeout signals unless a more specific schema/data issue is present.
- Compare against the latest steward/remediation-plan window when available, but do not rely only on old steward output if the user asked "now".

## Output pattern

Keep the answer concise and status-oriented:

- Lead with the plain-English verdict, e.g. "operational but unhealthy".
- Include a compact table with: app runnable, sync health, sync failures, automation failures, main cluster, definition/data changes.
- Then list current bottlenecks and the next approval-gated candidate fix.
- Include evidence paths for the fresh scan reports and timing analysis.
- Explicitly state that no live changes were applied when the workflow was read-only.

## Approval boundary

Any proposed AppSheet definition save, stable promotion, data-row cleanup, Google Sheets edit, queue-state mutation, or background-processing logic change still requires Andy/admin approval plus a dry-run diff and post-action readback/analyzer verification.
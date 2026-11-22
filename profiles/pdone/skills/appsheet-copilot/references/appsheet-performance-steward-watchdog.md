# AppSheet Performance Analyzer watchdog + steward pattern

Use when Andy asks PD One to proactively detect AppSheet smoothness, sync, automation, or app-not-runnable problems instead of waiting for manual incident prompts.

## Durable pattern

- Keep the frequent path deterministic and script-only: a `no_agent=true` cron watchdog runs the Performance Analyzer exportlog scan, stays silent on no-op ticks, and emits concise stdout only for baseline/cooldowned actionable findings or scanner failures.
- Keep diagnosis separate: a slower LLM steward cron reads the same evidence, classifies bottlenecks/failure signatures, and writes dry-run remediation plans. Do not let it perform AppSheet definition edits, source data writes, queue cleanup, Drive/Sheets edits, gateway restarts, or permission changes without explicit approval.
- Use real AppSheet Performance Analyzer evidence, not ActivityLog-only inference, for app-runnability and sync smoothness issues.
- Preserve the primary alert channel: fallback/extra alerts should not spam, duplicate, or suppress the main failure signal.

## Known PD One implementation receipts

- Watchdog script: `/home/prodesign/.hermes/profiles/pdone/scripts/appsheet_analyzer_watchdog.py`
- AppSheet scan tool: `/home/prodesign/.openclaw/workspace/tools/appsheet-migration/scripts/perf_analyzer_scan.py`
- Preferred Python for scans: `/home/prodesign/.openclaw/workspace/ops/venvs/venv-appsheet/bin/python` when present; fall back only when necessary.
- Watchdog cron: `faf6e314cac2` (`AppSheet analyzer failure watchdog`), every 30 minutes, `no_agent=true`, profile `pdone`.
- Steward cron: `ebcea071f106` (`AppSheet Performance Steward Agent`), every 120 minutes, profile `pdone`.
- Remediation plans directory: `/home/prodesign/.hermes/profiles/pdone/supervisor/remediation-plans/`
- Scan logs:
  - `/home/prodesign/.hermes/profiles/pdone/logs/appsheet-analyzer-watchdog/scans/`
  - `/home/prodesign/.hermes/profiles/pdone/logs/appsheet-performance-steward/scans/`

## Scan command shape

```bash
/home/prodesign/.openclaw/workspace/ops/venvs/venv-appsheet/bin/python \
  /home/prodesign/.openclaw/workspace/tools/appsheet-migration/scripts/perf_analyzer_scan.py \
  360 --tz UTC \
  --no-adds --no-updates --no-deletes --no-workflows --no-reports --no-api --no-documents \
  --out-dir /home/prodesign/.hermes/profiles/pdone/logs/appsheet-performance-steward/scans \
  --max-examples 25 --emit-prompt-packet
```

Adjust the window for the question; keep destructive/write-like categories disabled for read-only monitoring.

## What to classify

- App-not-runnable / schema / data-source / auth / table errors: sync failures with concrete exception text, inaccessible tables, resource waits, or table lookup failures.
- Automation stability failures: `TaskCanceledException`, `OperationCanceledException`, cache/lock failures, Spanner/automation-store failures, stale/deleted target row errors.
- Smoothness bottlenecks: parse `Properties.Performance`, rank table timings and virtual-column timings by p50/p90/max and rows seen.
- Definition inspection for automation chains: extract `DataActions[].ActionSettings` and `DataActions[].ActionDefinition`, not only `Condition`/`FilterCondition`. SET_COLUMN_VALUE assignments and REF_ACTION referenced-row expressions often contain the expensive `COUNT(SELECT(...))` or `ORDERBY(SELECT(...))` scans, while the event condition itself may be a cheap same-row flag.
- Noise: generic `Result=Failure` without exception text should remain lower confidence until paired with a concrete AppSheet exception/signature.

## Output / remediation rules

- For alerts: include window, counts, top tables/processes/actions/messages, evidence path, and whether this is baseline/manual/cooldowned.
- For steward plans: include evidence source, window, findings, suspected cause, dry-run-only remediation options, approval requirements, verification steps, and rollback/safety notes.
- Be proactive: the steward should periodically inspect analyzer logs and evidence packets, detect app-not-runnable or smoothness problems, open/refresh remediation plans, and surface approval-ready next actions before Andy has to report the symptom manually.
- For high-confidence non-destructive repairs or diagnostics, the steward may prepare bounded readbacks, manifests, and dry-runs automatically. Do **not** label read-only definition inspection, analyzer scans, evidence gathering, or dry-run planning as approval-required.
- Live definition edits, record writes/deletes, source-system cleanup, permission changes, outbound messages, or other side effects remain approval-gated.
- For destructive follow-through such as Case/Case_Updates de-dupe, keep a phase ledger: already-applied replacement rows, repaired parent status, child delete attempts, failed/unknown-commit rows, duplicate parent deletes not yet attempted, and required readback before resuming.
- Never claim a fix was applied unless a live, bounded, approved write occurred and was read back.

## Pitfalls

- Do not merge detection and repair into one autonomous fixer. AppSheet changes and business data writes are high-risk; keep repair approval-gated.
- Do not rely only on process/job health; verify cron `last_status`, delivery errors, and actual scan evidence artifacts.
- Do not capture transient scanner/setup failures as permanent tool limitations; capture the preferred venv/path and retry/smoke-test pattern instead.

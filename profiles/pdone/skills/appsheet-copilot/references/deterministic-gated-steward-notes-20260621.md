# Deterministic-gated AppSheet steward notes — 2026-06-21

Use this when a recurring AppSheet steward job is pre-gated by a deterministic packet and the packet already contains fresh actionable evidence.

## What changed in practice
- Treat the deterministic gate packet as the first evidence source.
- Do not repeat expensive discovery that the packet already answers unless a quick verification readback is needed.
- Always inspect the newest watchdog JSON and the newest sync scan JSON, but prefer the parsed raw timing analysis for p90/headline rankings when the generated scan omits them.
- When the scan stdout is truncated, rely on the saved `REPORT:`, `RAW:`, and `PROMPT_PACKET:` files as receipts.

## Proven workflow
1. Run the watchdog once for fresh failures.
2. Run the bounded sync-only scan.
3. Read the newest watchdog report and sync scan report.
4. If the sync scan lacks timing rankings, run `scripts/perf_raw_timing_analysis.py` against the companion `perf-raw-*.json` plus the scan JSON and save the analysis JSON beside the scan artifacts.
5. Classify findings into:
   - concrete app/runtime/schema/data-source failures,
   - timeout/cancellation/cache-lock failures,
   - smoothness bottlenecks by table and virtual column,
   - noise/transient `Result=Failure` rows without rich exception text.
6. If actionable findings exist, write a timestamped remediation-plan JSON and validate it with `python3 -m json.tool` before reporting.

## Current failure shapes seen on 2026-06-21
- Stale-client / newer-version add-row conflicts on `ActivityLog_Attachments`.
- Timeout/cancellation pressure from `ActivityLog_Attachments_Cached`, `ActivityLog Type`, and large function batches.
- Sync bottlenecks concentrated in `Case_Updates`, `ActivityLog`, `Maintenance_Session_Items`, `ActivityLog_Session_Items`, `Case`, and `ActivityLog_Attachments`.
- Largest VC cost: `ActivityLog_Session_Items[Label]`.

## Pitfalls
- Do not trust the generated scan alone if it only prints counts or top failures; compute timings from the raw export when needed.
- Do not claim a fix was applied unless a live change occurred and was read back.
- Do not include live AppSheet edits, data writes, Drive/Sheets writes, bot toggles, or restarts in a read-only steward run.
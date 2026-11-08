# AppSheet analyzer watchdog + steward automation pattern

Use this reference when building proactive monitors for AppSheet runtime health, sync smoothness, or app-not-runnable failures. The operating goal is that Andy/admins should not have to notice and request every investigation manually: the watchdog should surface analyzer-log regressions, repeated sync/runtime failures, and “app not runnable” signals with enough evidence for a steward to triage or prepare an approval-gated fix.

## Pattern

1. Split fast detection from slower reasoning.
   - Fast path: deterministic script-only cron (`no_agent=true`) that scans logs/export endpoints, writes local evidence, and prints nothing on healthy/no-op ticks.
   - Slow path: periodic LLM steward that reads evidence and writes diagnosis/dry-run remediation plans.
2. Keep live repair approval-gated.
   - No AppSheet definition edits, source row writes/deletes, Google Sheets/Drive edits, permission changes, or gateway restarts unless explicitly approved.
   - Steward output should be a plan with evidence, not an unsupervised writeback.
3. Register new jobs in the supervisor/automation registry as fail-closed/approval-required when they touch external systems or business data, even if the current script is read-only.
4. Back up/commit/push durable scripts, cron definitions, supervisor registry changes, and remediation-plan templates/artifacts when this profile has a configured backup repo.

## PD One implementation receipts

- Script: `/home/prodesign/.hermes/profiles/pdone/scripts/appsheet_analyzer_watchdog.py`
- Active-profile scan tool: `/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace/tools/appsheet-migration/scripts/perf_analyzer_scan.py`
- Active-profile scan Python: `/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace/ops/venvs/venv-appsheet/bin/python`
- Legacy mirror paths such as `/home/prodesign/.openclaw/workspace/...` may appear in older notes; for the active `pdone` Hermes profile, prefer the profile-local `legacy-openclaw` paths above unless Andy explicitly asks to inspect/repair the legacy mirror.
- Watchdog cron: `faf6e314cac2`, every 30m, script-only/no-agent, silent on no-op.
- Steward cron: `ebcea071f106`, every 120m, reasoning + remediation-plan only.
- Remediation plans: `/home/prodesign/.hermes/profiles/pdone/supervisor/remediation-plans/`

## Verification checklist

- Compile/smoke-test the script under the same interpreter the cron job will use.
- Run a manual force/baseline report and verify concise actionable stdout.
- Manually run the cron job, then check `last_status`, `last_error`, `last_delivery_error`, `last_run_at`, and `next_run_at` after it completes.
- Verify the steward writes a bounded plan artifact and does not apply live changes.
- Sync to backup repo, inspect staged diff, commit only relevant files, and push.

## Steward remediation-plan discipline

When the steward sees actionable findings, write a timestamped JSON plan under `/home/prodesign/.hermes/profiles/pdone/supervisor/remediation-plans/` and validate it with `python3 -m json.tool` before reporting. Do this even if an earlier plan for the same general issue exists when the current run has materially changed metrics, windows, failure counts, top processes, or top bottlenecks; the new plan is the current receipt and can point to the previous plan conceptually if useful. Include:

- evidence paths for watchdog report, sync report, raw rows, parsed timing analysis, and prompt packet when present;
- evidence windows in UTC;
- classification buckets: non-runnable/schema/data-source/auth/table errors; automation timeout/cancellation/cache-lock failures; sync smoothness bottlenecks; known noise/transients;
- local scanner/watchdog reliability findings separately from AppSheet runtime findings when a forced watchdog run fails but direct analyzer scans still succeed;
- suspected root cause, safe immediate read-only checks, proposed fix/dry-run, risk, approval requirements, and verification steps;
- `live_changes_applied: false` unless a separately approved fix was actually executed and verified.

For final steward chat delivery, report actionable findings concisely with the plan path and validation receipt. Use `[SILENT]` only when there is genuinely no meaningful issue; do not suppress a run that found fresh failures, severe p90 sync degradation, or wrote a remediation plan.

For sync smoothness, the generated scan report may omit timing rankings. In that case, parse the companion `perf-raw-*.json` rows and their `Properties.Performance` payloads directly to compute p50/p90/max, table `Mid == 116`, VC `Mid == 222`, and row-count evidence. Practical parser pitfalls: the report JSON is usually nested under `report`, raw `Properties.Performance` is often a JSON string, timing values are AppSheet duration strings such as `00:02:41.7585108`, params may be `Params.ParamList` rather than a flat dict, paired summary/detail sync rows mean only rows with `Properties.Performance` should count as detailed timing samples, and parser traversal must descend into `PerformanceTimingRoot` before walking `Children` or it can silently miss table/VC timings.

When the steward creates a one-off parsed-analysis artifact to support the plan, save it under the steward log directory and include its path in the remediation-plan `evidence_paths`. This keeps the final chat report concise while preserving the exact computed rankings used for the diagnosis.

When both scans are required in a scheduled steward run, treat them as complementary evidence, not substitutes: the forced watchdog scan is failures-only/all-operation evidence for automation/runtime instability, while the sync-only scan is smoothness evidence. If the watchdog reports repeated failures and the sync-only scan has degraded p90 duration, write one remediation plan that separates (a) automation timeout/cancellation/cache-lock/non-runnable classes from (b) sync table/virtual-column timing bottlenecks. A single generic sync failure without exception detail should be labeled noise/context, but do not suppress delivery when failure volume, severe sync p90 degradation, or a new plan exists.

If both required AppSheet `/manage/exportlog` collectors fail before writing raw/report artifacts (for example HTTP 401 Unauthorized) and the gate has no current timing rows, classify that as `collector_auth_failure` separately from AppSheet runtime health. It is acceptable to use the latest valid same-day artifacts only as directional design context, but mark implementation blocked until read-only analyzer access is restored and a fresh immediate pre-change baseline is captured. Do not claim the current gate proved a sync/runtime regression when the only fresh evidence is collector/auth failure.

Raw scan JSON shape pitfall: `perf-raw-*.json` is commonly a top-level object with `{ "meta": ..., "rows": [...] }`, not a bare list. Any ad hoc parser should branch on `dict` and extract `rows`/`Rows` before iterating; otherwise it may silently report `raw_rows: 0` and miss all timing evidence. Generated `perf-scan-*.json` may also contain huge `latest_examples`/`api_ready_rows` blocks and generic `Failure` messages, so use the raw rows plus `Properties.Performance` for timing and stack-signature classification rather than relying only on the generated report summary.

## Alert-output discipline

- Empty stdout means normal silent no-op for `no_agent` watchdogs.
- Concise stdout should be reserved for baseline/manual reports, cooldowned findings, or scanner failures.
- Include evidence file paths and top signatures; do not paste secrets or raw dumps.
- For chat-visible steward/LLM reports, do not deliver raw gate packets, remediation-plan JSON, or tool-style dumps. Render the final notification into a human-readable Markdown summary with: status, evidence window, plain-English read, top 2-4 findings, next step, approval boundary, and receipt path.
- Keep the detailed JSON remediation plan on disk for audit, but make the Telegram/Mattermost notification manager-readable. If a job is `no_agent=true` and invokes an LLM through a deterministic gate, add a small renderer/post-processor in the wrapper/gate path so future runs cannot leak raw JSON even if the LLM output is verbose.
- For the current PD One AppSheet steward, the renderer is `/home/prodesign/.hermes/profiles/pdone/scripts/render_appsheet_steward_notification.py`, called by `/home/prodesign/.hermes/profiles/pdone/scripts/conditional_llm_cron_gate.py` for `--mode appsheet`.

# Worker Scheduling MCP Usage and Receipts

Use this note when running Pro-Design monthly worker scheduling through the Hermes `pdone_safe_ops` MCP tool.

## Prefer the actual MCP tool

For normal monthly scheduling operations, call the exposed dedicated MCP tool directly, e.g. `mcp_pdone_worker_scheduling_worker_scheduling`. Do not bypass the safe wrapper by importing `pd_one_safe_ops_mcp.py` from `execute_code` or by hand-running the scheduler through shell/Python when the MCP tool is available. The general `pdone_safe_ops` MCP server no longer exports worker scheduling; long scheduling writebacks live on `pdone_worker_scheduling` with a longer timeout so other safe ops do not wait behind them. Generated-schedule execution is split: first run `action="solve_preview"` with solver time capped at 180 seconds, then run `action="write_generated_schedule_from_report"` against a verified feasible/optimal `generated-schedule-report.json`. Do not use the disabled combined solve+write path.

If an MCP solve/write call times out, treat it as a tool/runtime failure until receipts prove otherwise. Continue with MCP-bounded calls one group at a time, but **do not lower the normal solve cap and then treat a short-run `UNKNOWN` as the scheduling result**. First inspect the output directory/receipt, verify the MCP timeout/config/reload state, and rerun the normal bounded `solve_preview` path after the tool issue is fixed. Do **not** fall back to `execute_code` or terminal for scheduling solves/writebacks unless Andy explicitly reverses this rule for that incident.

If Andy says he has run `/reload-mcp` or restarted the gateway, re-check the callable tool list and then use the actual MCP tool. If the tool is not exposed, report the exposure problem instead of working around the wrapper with a general script runner.

## Source-period control gate before preflight, rollover, or solve

The scheduler derives its active month from live `申請日期-當月統計` control cells. Passing `target_year` / `target_month` in a generic MCP payload does **not** override stale live controls for `preflight` or `sync_source_rollover`. A request for August can therefore still parse and preview July if the sheet month remains July.

Before any target-month preflight, rollover, or solve:

1. Run `action="source_setup"`, `dry_run=true`, using the wrapper's exact payload fields:
   - `a2_value`: Gregorian year, e.g. `2026`;
   - `a4_value`: target month number, e.g. `8`;
   - `required_rest_days_count`: monthly required-rest count, e.g. `11`;
   - optional `gog_account` when needed.
2. Do not substitute legacy/guess aliases such as only `target_month`, `required_rest_days`, `a5_value`, or `a10_value`; the current typed action requires `a2_value`, `a4_value`, and `required_rest_days_count`. The verified live layout is `A2=year`, `A3=Month`, `A4=month value`, `A5=Shift`, `A9=Required Rest Days`, and `A10=required-rest value`. The tool must refuse any write when these labels drift.
3. Compare the `before` readback to the requested period. If it still shows the prior month, stop: any preflight/rollover output is for that prior month, even if the caller included a different target month in the payload.
4. A live source-control update requires `dry_run=false` plus `confirm_live_write="RUN LIVE WORKER SCHEDULING SOURCE WRITE"`. For a normal monthly kickoff, this typed confirmation is an MCP execution guard—not a separate Andy/admin approval. When a profiled participant supplied the target month and monthly constants in the active kickoff thread and the dry-run is limited to the expected controls, proceed directly without creating a `PDAPP-*` ticket. Read back `A2:A10` and require the intended year/month/rest values **and the exact labels `A3=Month`, `A5=Shift`, `A9=Required Rest Days` after the write**. The `AV` required-rest read must itself return `status=ok`; a failed or empty read is not proof of zero mismatches.
5. Only then run live `sync_source_rollover` under the same routine-maintenance authority; verify the returned source period, formula-owned helper ranges, and the `E:AI` visual request grid before preflight or solve. Stop and escalate only for unexpected ranges, formula regression, ambiguous request-history changes, participant/roster changes, or broader writes.
6. Treat monthly total working hours separately: they belong to verified target-month destination work-hour cells used by the HR MAX export path, not to the solver's source-period selector. Resolve the exact target tabs/cells and read them back before any hours write; this routine-maintenance exception does not automatically broaden to HR MAX export/upload or generated-schedule writeback.

Safety rule: never run a solve merely to "see whether" the month payload took effect. The control-cell readback is the prerequisite proof.

## Bounded Scheduling Rules gate

The source workbook also has one schema-owned tab, `排班規則 Scheduling Rules`. Create or reconcile it only through `action="setup_scheduling_rules"`:

1. The action accepts no payload overrides. It is bound to the source spreadsheet, exact tab name, and 15-column schema. The original create-seed was `WorkerID=W12` / `王柏凱` / `課長` / `Employed` / `成型一課` / `manager_day`, effective `2026-08`, weekend bias enabled, `PreferenceMode=Prefer`, `RequestProtection=Conservative`, weight `1500`. Andy 2026-08-25 standing rule: before each month's preflight/solve, the live rule row must map to whichever of `楊正義` or `王柏凱` is `幹部-日`. If the create-seed identity is stale, do a bounded dry-run then live edit of the existing row (WorkerID/Name/RunGroup evidence) rather than a second rule. Do not invent a `manager_night` rule.
2. Dry-run first. It reports whether the tab exists and the exact fixed values. Existing non-empty content that differs from the reviewed two-row payload is a conflict; the action must not overwrite it.
3. Live creation uses `dry_run=false` plus `confirm_live_write="RUN LIVE WORKER SCHEDULING SOURCE WRITE"`. Require exactly one tab in metadata, frozen header row, and exact `A1:O2` readback before continuing.
4. Every preflight validates that exactly one active/effective `manager_day` `課長` rule maps by stable WorkerID to exactly one matching source worker. Missing/duplicate rules, a name/group/status mismatch, non-positive weight, or unsupported mode/protection fail preflight and block solve.
5. The solver treats the rule as a soft weekend-coverage preference only for eligible Saturdays/Sundays in the `manager_day` group. Requested rest, hard/flex/protected leave, special/mandatory work, and rule `ExcludedDates` are excluded before objective construction; all other run groups remain no-op.
6. Read `generated-schedule-report.json -> generated_schedule.solver.staffing_summary.weekend_coverage` to verify eligible, excluded, staffed, and missed weekend dates. Do not infer rule application from the objective value alone.

## Raw request date correction pattern

For `correct_raw_request_dates`:

1. Identify the exact raw row in `原資料` first. The MCP action expects `payload.row_number`; worker name + old/new dates alone is not enough.
2. Dry-run first:
   - `action="correct_raw_request_dates"`
   - `dry_run=true`
   - payload includes `row_number`, `old_dates`, `new_dates`, and optional `employee_name` / `worker_name` / `gog_account`.
   - Use the exact field names `old_dates` and `new_dates`; aliases such as `from_dates` / `to_dates` are not accepted by the MCP wrapper.
3. Confirm the dry-run shows the exact old values in the intended cells.
4. Live source write requires:
   - `dry_run=false`
   - `confirm_live_write="RUN LIVE WORKER SCHEDULING SOURCE WRITE"`
5. Verify the receipt fields:
   - `after_values` shows the new dates in `K:O`.
   - `after_notes` shows notes on every edited date cell.
   - `formula_check` still returns the expected year/month helper values.
   - `formula_regression_detected=false`.

Example receipt from the 謝富雄 July 2026 correction:
- row `1398`
- `K1398`: `2026-07-06` → `2026-07-21`
- `L1398`: `2026-07-07` → `2026-07-22`
- receipt path shape: `.../worker-scheduling-mcp/<timestamp>_correct_raw_request_row_1398/mcp-correct-raw-request-dates-receipt.json`

## Solve/write retry pattern for long scheduling runs

The MCP supervisor may have a shorter outer timeout than the scheduler’s own desired timeout. Keep runs bounded and group-by-group. This applies to manager runs and also to larger 作業員 groups, where a preview may need longer solve caps than a writeback can comfortably re-solve inside the MCP call.

1. Run one group at a time (`day`, `night`, `manager_day`, `manager_night`) rather than bundling multiple groups in one call. Pass `solve_groups` as a one-item list. Do not pass `solve_group`. That string is ignored, and the command omits `--solve-group`. Read the returned command and stop the job if `--solve-group` is missing. Do not start the next group until the current stderr shows `[solver] start`. Two jobs in the Sheets-read phase at once return `429`, and the later metadata call then times out.
2. Solve only with `action="solve_preview"`; default/normal cap is `solver_max_time_seconds=180` and the MCP wrapper clamps higher requested caps back to 180 because longer solves have not materially improved schedules. Long operator previews can exceed the gateway MCP keepalive interval, so `solve_preview` starts a background job by default and returns `status="running"`, `output_dir`, and `next_payload`; poll with `action="poll_solve_preview"` in short calls until final `ok`/`error`. Identical stderr with a solver start line and no finish line means the search is still inside the cap. A finish line of `status=FEASIBLE` followed by a Sheets traceback is not a saved preview. Require `generated-schedule-report.json` in that output dir before writeback. Post-solve layout load calls Sheets again and exits before the report is written when that call times out. Do not start a second solve for that group. A source-validation refusal exits before the solver start line. Confirm that pid is gone, fix the source, then start one new solve. Do not hold one MCP call open for the full solve. A finished background job does not wake the session. If Andy expects a result in the current thread and you must end the turn first, create a one-shot cron that delivers to origin before you stop. Do not say you will report later unless that job exists.
3. Distinguish solver result from tool failure before deciding. If the normal bounded `solve_preview` returns a receipt with `UNKNOWN`, do not write; report the unknown solve and adjust constraints/data instead of extending solve time beyond 180 seconds. If the normal bounded attempt timed out at the MCP/tool layer and a later shorter-cap fallback returns `UNKNOWN`, do **not** report that as the final scheduling result; report the MCP/tooling failure, fix/reload/escalate the wrapper, and rerun the normal bounded solve.
4. Write only with `action="write_generated_schedule_from_report"`, one run group per call. A multi-group call returns `one_group_per_write_call_required` and writes nothing. Pass the feasible/optimal `generated-schedule-report.json` from the solve preview. A Google Sheets `429` or metadata dial timeout is a quota or network failure, not a bad schedule. Stop new group writes and resume the same `output_dir` later. If `values_complete` is true, do not re-solve; resume format only. This write action never re-runs OR-Tools, so a shorter write call cannot degrade a previously feasible preview into `UNKNOWN`. If newer solver experiments return `UNKNOWN`, do **not** use those reports; either keep tuning or, if Andy explicitly says to write from report, clearly state when you are writing from an older feasible report instead of the latest failed experiment.
5. `write_generated_schedule_from_report` is resumable across both value batches and format batches. If it returns `status="partial"`, call the same action again using `next_payload` (especially the same `output_dir`, `max_value_batches_per_call`, and `max_format_batches_per_call`) until it returns `status="ok"` or `status="error"`; do not start a new solve or a new output directory. Large operator groups should return `partial` before the MCP outer timeout instead of trying all value writes in one call.
6. If a write call times out, first inspect the write receipt/state output directory before retrying; a timeout can happen after the underlying write started or completed. If the directory contains only `mcp-write-generated-schedule-from-report-plan.json`, the write was not receipt-confirmed — do not claim completion. The resumable state file is `generated-schedule-write-state.json`; check `values_complete`, `next_value_batch_index`, `next_format_batch_index`, and final report files before deciding whether to resume or report.
7. If a solve/write timeout shows only the outer MCP error (`MCP call timed out after ...`) and no scheduler receipt, suspect wrapper subprocess supervision rather than solver infeasibility. The wrapper must run scheduler subprocesses in their own process group, kill the whole group on timeout, and write `mcp-scheduler-subprocess-timeout-receipt.json`; otherwise gog/grandchild pipe inheritance can make `subprocess.run(..., timeout=...)` hang until the outer MCP transport timeout.
8. For large operator groups, avoid unnecessary formatting of unchanged cells. A feasible `作業員-日` split write can still time out if it performs hundreds of value/format calls; prefer code paths that write changed values and format changed cells only, while still recording unchanged actions in the receipt. When a large write risks timing out, continue with smaller `max_value_batches_per_call` and `max_format_batches_per_call` chunks using the same output directory rather than restarting. If the first live write call times out but `generated-schedule-write-state.json` exists, inspect `values_complete`, `next_value_batch_index`, and `next_format_batch_index`; when `values_complete=true`, values have already been written, so resume formatting from the same `output_dir` instead of rerunning the solve or starting a new write directory. It is acceptable to tune chunk size once the resumable state is healthy. After the first `partial` proves the write path, raise chunks instead of staying at 5 value batches: operator groups finish values at `max_value_batches_per_call=10`, then finish format at `max_format_batches_per_call=75`. A cadre group of about 150–180 cells can finish in one call at 25 value batches and 75 format batches. If a raised chunk times out, drop the chunk size and resume the same `output_dir`. The 2026-07 `作業員-夜` write completed after an outer MCP timeout by resuming format batches until `status="ok"` with `713` checked/verified actions and `0` mismatches; the 2026-07 `作業員-日` write used the same pattern and completed with `682` checked/verified actions and `0` mismatches. Future writes should return `partial` before the MCP timeout instead of waiting for that timeout.
9. To answer Andy's quick staffing-balance questions after a solve, read `generated-schedule-report.json -> generated_schedule.solver.staffing_summary.staffed_workers_by_day` for the daily on-duty counts, `target_workers_by_day` for the target (including forced-low days), `low_staffing_days` for below-target days, and `g_grade_missing_days` for grade-coverage gaps. Report this as a dry-run result unless a live writeback receipt has already verified the schedule.
10. Do not use `vision_analyze` or other visual tools for normal scheduling unless the user asks about an attached screenshot or visual evidence; scheduling should be driven by MCP receipts and sheet readbacks.
11. Treat write success as receipt-backed only. For each written group, verify:
   - `generated-schedule-write-report.json` has `status="written"`, `groups_with_write_failures=0`, and `failed_updates=0`.
   - `generated-schedule-write-verification-report.json` has `mismatched_actions=0`; if no value cells changed, `checked_actions` may be `0` while formatting-only actions still completed. Ignore `source_summary.write_enabled` in that file. It is copied from the solve preview and stays `false` on a successful from-report write.
   - Do not require a combined-path `summary.json` with `write_enabled=true`. The split write receipt is `generated-schedule-write-report.json`.

## Cross-sheet count rows after a staff-row delete

Operator and cadre tabs do not link count rows with a live row reference. The formula uses `ROW()` of a cell on the same sheet, then `INDIRECT`s that number on the other tab. Deleting a cadre or operator row shifts the summary block up by one. The pointer stays on the old number.

1. Read the label in column C and the formula. `幹部人數` must land on the `LEN` row under the name-join row, not on the `TEXTJOIN` row. A cell full of joined last characters is the name row.
2. `日班上班人數` and `夜班上班人數` must pull the other tab's `上班人數` row. Do not point them at a row that itself mirrors the broken cadre pointer.
3. Read the corrected range back as values before you report the fix. Numbers, not name fragments, are the receipt.
4. A formula contains commas. `gog sheets update` positional values split on commas. Pass `--values-json` and `--input USER_ENTERED`. If nested quotes break the shell, build the sheet-name pieces with `CHAR()` so the JSON string has no inner double quotes.
5. Schedule marks and summary rows move differently. Before you resume `write_generated_schedule_from_report` after a row delete, compare each report `matched_row_number` with the live name on that row. Resume only when they still match. If they do not, do not reuse that output dir.

11. Treat a roster-removal overwrite as incomplete until destination-only legacy rows are checked. A report writes only workers present in that report; it does not automatically clear a previously published worker who is now omitted from the source/model. After the normal report write verifies, compare the current modeled worker set with previously published destination rows for the same group. For any confirmed removed/retired worker, read the exact destination row, dry-run the bounded cleanup, then—with the same authorized overwrite scope—set the month’s schedule cells to the workbook’s established excluded marker (for the current worker-scheduling workbook, `X`) and require exact readback. Do not infer that report omission cleared the old row, and do not alter unrelated groups or months.

## Reporting compact receipts

For Mattermost reports, keep the output compact and bilingual in shared channels. Include:

- source row/cells changed and readback result;
- receipt path(s);
- per group: output dir, solver/write status, rows/cells written, failed updates, verification mismatch count;
- any important semantic check, e.g. that the parsed source for the affected worker contains the updated requested days.

Do not paste full JSON receipts unless Andy explicitly asks; cite paths instead.
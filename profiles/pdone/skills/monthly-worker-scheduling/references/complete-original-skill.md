---
name: monthly-worker-scheduling
description: 'Use for the monthly worker scheduling cycle: raw rest requests, source sheet corrections, AP:AT intent, scheduler runs, and HR MAX export.'
---

# Monthly Worker Scheduling

Use this skill when Andy wants to run the monthly worker scheduling cycle together and expects you to walk the workflow instead of rediscovering it.

## Scope boundary

This skill covers **worker scheduling only**:
- monthly shift assignment
- leave/rest request handling
- generated-schedule writeback behavior
- HR MAX import preparation
- post-announcement request closeout in `原資料!AD`

This skill does **not** cover:
- production scheduling
- production planning
- machine loading or mold allocation
- work-order sequencing or dispatch decisions

If the task is about what to make, when to make it, in what sequence, or under what production constraints, use the production-scheduling docs/project instead.

Adjacent company-wide manpower policies, such as employee trip group assignment rules that keep `人力` balanced across dates/groups, belong in the All-Company work manual as policy source of truth. Use this scheduling skill only to supply staffing/coverage constraints and implementation reminders; do not bury a cross-department employee behavior policy solely inside monthly scheduling docs.

Annual employee trip planning reminder: before next year's employee trip sign-up/group assignment is opened, proactively check the All-Company manual policy section for "員工旅遊梯次分配與人力覆蓋 Employee Trip Group Assignment and Manpower Coverage" and remind Andy/HR that trip groups should be assigned to keep `人力` balanced across dates/groups, avoiding concentrated absences in the same department/critical role/day/night coverage bucket. Treat the manual as the source of truth; use scheduler/staffing data only to validate coverage constraints and identify risk.

## Canonical files

Read these first, in this order:
1. `/home/prodesign/.openclaw/workspace/docs/runbooks/project-workflows/monthly-worker-scheduling.md`
2. `/home/prodesign/.openclaw/workspace/projects/automatic-worker-scheduling/docs/shift-scheduler-phase1.md`
3. `/home/prodesign/.openclaw/workspace/projects/automatic-worker-scheduling/docs/shift-scheduler-phase1-implementation-notes.md`

Project home:
- `/home/prodesign/.openclaw/workspace/projects/automatic-worker-scheduling/`

Canonical script:
- `/home/prodesign/.openclaw/workspace/projects/automatic-worker-scheduling/scripts/shift_scheduler_phase1.py`

## Default stance

- Treat the workflow as **source-first**.
- Start from `原資料` and `申請日期-當月統計`, not downstream schedule views.
- Dry-run is the default.
- Be conservative with live writes.
- Do not silently fix ambiguous data.
- Walk the runbook top-to-bottom. Andy standing instruction (2026-08-24): assume rest requests are already in, run month/source consistency checks, and if the run is green fill required columns and solve/write the primary month automatically. Do not wait for a go-ahead on a green run. See `references/auto-run-when-consistency-green.md`.

## Durable rules to preserve

### Playbook / Anna handoff
- Do **not** ask Anna to provide employee rest-request data; employee rest requests are collected separately through Google Forms into `原資料`.
- Ask Anna for monthly scheduling constants instead: the required rest-day count for the target month, the required rest-day count for the immediately following month, and total working hours for the target month. Refuse solver execution until both rest-day counts are explicit.
- Before asking Anna/HR to restate those constants, first search existing in-scope evidence: the active kickoff thread, other same-cycle Injection Molding Management scheduling threads, the durable `排班流程追蹤 Tracker` tab, and local run receipts. If Andy or a profiled participant says the numbers were already provided in another thread, treat that as a lookup instruction—retrieve and reuse the existing values. Do not ask Anna to repeat constants that are already source-backed.
- For automated monthly kickoff posts, Andy prefers PD One to **start the scheduling playbook directly in a new thread** rather than posting a passive reminder. @ mention the responsible task owner(s), e.g. `@anna`, and state exactly what they should provide.

### Annual employee trip checkpoint
- Starting with the January monthly scheduling playbook run each year, ask Andy whether the annual employee trip dates/groups are known yet.
- Continue asking in every monthly schedule playbook run until Andy gives an answer for that year.
- If dates/groups are unknown, keep the checkpoint open for the next monthly run instead of dropping it.
- Once known, carry the dates/groups into staffing checks and flag concentrated absence risk by department, critical role, and day/night coverage bucket before solve/writeback.
- Treat the All-Company manual section `員工旅遊梯次分配與人力覆蓋 Employee Trip Group Assignment and Manpower Coverage` as the policy source of truth; worker scheduling is the validation layer.

### Raw request corrections
- Correct confirmed request changes in `原資料`, not just in downstream schedule tabs.
- Before source rollover / solve, scan current-month `原資料` rows by submitter for duplicate submissions and reason/message text that says a later request overwrites an earlier one (examples: `change`, `final`, `replace`, `更改`, `變更`, `最終`). Do not blindly union all rows for that worker/month when the message says the latest request is a replacement.
- Treat Randy / `阿弟 | SALARDA RANDY PERALTA` in the 2026-07 cycle as the canonical example: rows 1364 and 1384 requested 7/4 and 7/10, but row 1408 says `change my request off this is my final🙏` and should be reviewed as replacing the earlier rows with 7/1, 7/2, 7/3 only.
- For overwrite candidates, produce a review table first: worker, old row(s), latest row, old days, final days, and message text. Only after Andy/admin confirms, mark or correct the superseded `原資料` rows / statuses; do not silently edit raw request history.
- Use `USER_ENTERED` for date-cell edits.
- Add notes on every edited date cell.
- Verify stored values and notes after writing.
- After source edits, watch for formula regressions in `原資料`.

### Live scheduler path
- Current live runs do **not** use `previous_schedule.xlsx`.
- Previous-month context comes from the live previous-month destination tabs.
- Use the project venv on this host: `.venv`.
- Pass `--gog-account` explicitly when needed.
- `--write-generated-schedule` requires `--solve`.
- `--sync-source-rollover` is separate and must not be combined with solve/write-generated-schedule.
- Before AP:AT mapping, set the current live control cells based on the month being scheduled. As of the 2026-07 run, the controls read back as `A2=Year`, `A4=Month`, and `A10=Required Rest Days` (despite older notes mentioning A5); verify labels before writing.
- Before `sync_source_rollover`, preflight, or solve, rebuild `申請日期-當月統計!AP:AT` from the already keyed **target-month** schedule cells by exact employee and date-column matching. Use `V` → `HardRestDays` (`AP`), `喪` → `ProtectedLeaveDays` (`AQ`), `特` → `FlexRestDays` (`AR`), and `訓` → `SpecialWorkDays` (`AT`). Clear stale prior-month AP/AQ/AR/AT values lacking target-month evidence. Do not infer `MandatoryWorkDays` (`AS`) from blank cells; change AS only from explicit source-backed instructions or a defined visible marker. Inspect notes on keyed `V` cells before classifying them—vacation/leave notes belong in AR, not AP. Dry-run the exact source-row changes, live-write through the approved bounded Sheets path, read back AP:AT, and only then run `sync_source_rollover`. `sync_source_rollover` consumes AP:AT to populate destination markers; it does not itself prove AP:AT was refreshed. Invalidate and rerun any solver result produced before this gate.
- Before solving, update operator grades from the latest operator-grade survey/analysis source. The destination day/night tabs use an `E4` array formula (`級`) that spills grades from `LOOKUP` named ranges; **do not write direct values into the spilled grade cells** because that causes `#REF!`. Update the lookup/source range instead, and if any current grade is `G`, leave that operator unchanged.
- Then verify `申請日期-當月統計!B:D`: `B` class/group, `C` names, and `D` PreviousConsecutiveWorkDays from the target-month schedule sheets.
- Before solve/writeback, run a bidirectional name cross-check between the target-month schedule tabs (`115年M月-日`, `115年M月-夜`, `115年M月-幹部`) and `申請日期-當月統計` / current-month `原資料`:
  - schedule tab name present but missing from source stats = blocker, because generated scheduling may lack that worker's grade/previous-days/request context even if they submitted no request;
  - source stats name missing from destination schedule = blocker unless intentionally excluded with a tracker receipt (example: Romulo temporarily moved to QA);
  - active request name missing from schedule = blocker or explicit handoff decision.
  - When cross-checking destination schedule names, filter out totals/summary/footer rows such as `休假人數`, `上班人數`, `幹部人數`, `日上班人`, `夜上班人`, and rows with marker codes such as `X`; use actual employee-code/name rows only.
- If Andy/admin confirms an employee should be excluded from the target month because they are temporarily moved, no longer employed, or retiring mid-cycle, follow the Romulo pattern: blank only the class/scheduling participation cell in `申請日期-當月統計` (usually column `B`) while preserving the name, worker ID, grade, previous-days, and other audit/context columns. For mid-cycle retirement, also read back the destination schedule row and verify dates from the retirement date onward are excluded/blocked (for example `X`) before deciding whether a generated rerun is needed. Dry-run the single-cell update where practical, live write with `gog`, read back the full row, rerun scheduler dry-run, rerun the refined name cross-check, and append a tracker row with receipt paths. Do not delete the row or clear identity/context columns.
- When adding a missing worker to `申請日期-當月統計`, write only the manual participation fields in columns `B:D` on a true blank/spacer row (class, name, previous consecutive work days). Columns `AK:AO` and `AU:AX` are arrayformula-owned, and the visual request grid `E:AI` is formula/audit-grid owned; do **not** write into those ranges for a normal missing-worker add. Let formulas populate `WorkerID`, `Name`, `Grade`, `PreviousConsecutiveWorkDays`, `TotalDaysInMonth`, required-rest, year, and month fields. If `AK1:AX1` turns into `#REF!` after a bad manual row add, immediately clear the formula-owned cells in that row (for example `E{row}:AX{row}`), verify headers recover, and rerun dry-run before any solve/writeback. 2026-07 correction: Jonas / `喬那司 | ABALA MARK JONAS PADIGOS` should have been added only to `B:D`, not `AK:AX`. See `references/2026-07-hours-and-safe-tooling.md` for the concise reusable pattern.
- 2026-07 pitfall: `喬那司 | ABALA MARK JONAS PADIGOS` existed in `115年7月-日` but was absent from `申請日期-當月統計`, while `吳宜娟` remained in source stats but not the July destination schedule. `吳宜娟` was later excluded by blanking only `申請日期-當月統計!B23` after Andy confirmed she was no longer employed. Do not proceed to solve/writeback until this class of mismatch is reviewed and corrected or explicitly accepted.

### Pre-print schedule finalization

After Andy confirms the 104 HR MAX import/export was accepted, but **before** printing/signing the schedule:
- run the pre-print conversion on the finalized schedule tabs for the accepted month: convert all remaining visible `未` schedule cells to `特`.
- Scope the conversion to the finished target-month schedule tabs only (for example `115年7月-日`, `115年7月-夜`, `115年7月-幹部`); do not touch source sheets, the HR MAX export tab `115年-N月`, prior-month carryover sheets, or future-month tabs.
- Locate `未` from a `FORMATTED_VALUE` date-grid read, then confirm each A1 with a one-cell formatted read. Do not compute the column letter from a formula render of a wide row. See `references/preprint-un-to-te-finalization.md`.
- Dry-run/count the cells first, then live write after Andy's instruction/confirmation, and verify by rereading the changed ranges/cells.
- This step happens after 104 acceptance because `未` is intentional preview/export output, but the signed/printed schedule should use final `特` markers instead.
- Do this pre-print conversion before telling Anna/HR the schedule can be printed and signed.

### Post-announcement request closeout

Only after Andy confirms the 104 HR MAX import was accepted, the pre-print `未` → `特` conversion is complete, and schedules were announced/ready to print/sign:
- identify the scheduled month explicitly
- dry-run scan `原資料!A:AD`
- dry-run `closeout_processed_requests` to list candidates
- when scheduling is finished and Andy confirms all rest requests for that month were granted, select every blank `AD` row that contains any date in the scheduled month, including mixed-month rows
- preserve nonblank AD statuses, including superseded rows
- report candidate count, AD status distribution, blanked-request candidates, mixed-month rows, and any nonblank AD rows; a mixed-month list is a receipt, not a hold
- the granted-all confirmation is the write confirmation; do not ask again to include mixed-month rows
- write exactly `0 Processed` to column `AD` for every selected blank row, including mixed-month rows
- run `closeout_processed_requests` live with `RUN LIVE WORKER SCHEDULING SOURCE WRITE` when that confirmation exists; it already includes mixed-month rows
- verify by rereading the written AD cells, including mixed-month rows
- do not overwrite nonblank AD statuses unless Andy explicitly confirms the overwrite
- keep `原資料!U:V` arrayformulas hardened so all-blank `K:O` rows return blank, not `#VALUE!`
- if Andy has not confirmed that all requests were granted, stop after the dry-run. See `references/preprint-un-to-te-finalization.md`.

### Run groups
Canonical groups:
- `day`
- `night`
- `manager_day`
- `manager_night`

Worker-label normalization must accept both:
- `日` / `夜`
- `作業員-日` / `作業員-夜`

### One-person / exception scheduling groups
- `諾威 | NOGALES NOEL MANGALIMAN` is his own scheduling group. Before any broad solve/writeback that includes him, check his consecutive work days at the end of the previous month, check his current-month requested rest days, then space out his work days so the schedule avoids excessive consecutive-day runs. Do not rely on normal group headcount-balancing logic for him.
- `黃俊中` is his own scheduling group. His normal pattern is Monday-Friday, but he still follows labor-law rest constraints and may commonly rest on Friday. Always consider his submitted rest-request days first, then apply the weekday pattern and Friday-rest preference where it fits.
- Treat these exception groups as focused pre-solve / separate-solve checks with their own review/writeback receipt. Do not silently overwrite them as part of a broad manager/operator generated-schedule writeback.

### Locked generated-schedule semantics
- `SpecialWorkDays` in `申請日期-當月統計` are visible training/special-work days and must be written to the destination schedule as `訓` (for example, 2026-07 幹部 7/20). Do not leave them blank just because the solver treats them as work/excluded-staffing constraints.
- Blank solver output must not clear existing `訓`.
- `未` is intentional preview output.
- Solver weight tuning note: June 2026 manager-day review showed the root priority is staffing consistency: even out adjacent daily worker counts before preserving the 2-work/1-rest rhythm. Keep `DEFAULT_CONFIG["rest_request_weight"]` at the normal request-satisfaction level and make the staffing-fluctuation penalty dominate the 2-work/1-rest bonus. Keep a regression test for Nomer 6/19 vs 6/20 before retuning weights.
- Solver runtime cap note: for normal monthly playbook solves, start with `solver_max_time_seconds=180` and `solver_no_improvement_seconds=60`; escalate to 600s only if staffing balance is visibly bad, Andy flags a specific assignment, or solver output/status looks suspicious. Do not optimize for tiny objective improvements if the 180s result preserves stable daily staffing. See `references/solver-runtime-capping.md`.
- `V -> 特` is allowed on flex-rest days.
- Before solve/writeback, inspect destination schedule cell notes for `V` rest days when the note indicates vacation/leave rather than hard rest (examples: `vacation`, `on vacation`, `特休`, `休假`). Those days must be represented in `申請日期-當月統計` as `FlexRestDays`, not `HardRestDays`, so the solver can choose `特`/rest semantics correctly. 2026-07 example: 劉展宏 had `V` cells with vacation notes that needed moving from `HardRestDays` to `FlexRestDays` before generated scheduling.
- If `申` and `V` overlap, hard rest wins and `申` writeback is suppressed.
- `喪` is `ProtectedLeaveDays`, excluded from staffing counts and rest counts.
- Manager writes must never touch column `F`.
- Formatting contract:
  - `申`, flex-rest `特`, and protected leave `喪` should be yellow because they are pre-requested/known leave.
  - Treat `申請日期-當月統計!E:AH` as a required visual audit grid, not optional decoration. Before any solver/writeback after source rollover, verify the grid still shows `申` markers for worker-requested dates from `原資料`; if it is blank for most workers, stop further schedule writes and repair/rebuild the visual grid from canonical raw requests before continuing.
  - Reference: see `references/2026-06-source-rollover-visual-grid.md` for the June 2026 pitfall where structured helper columns survived but the `申請日期-當月統計!E:AH` visual `申` grid was blanked; future source rollover must verify and repair the visual grid from `原資料` before continuing schedule writes.
  - orange = mandatory/special/hard-rest constraints
  - neutral cells must clear stale fills

## Monthly kickoff automation

When Andy asks PD One to initiate the worker scheduling playbook automatically each month, use the existing 21st-of-month kickoff pattern rather than inventing a new reminder each time.

Reference: `references/monthly-kickoff-automation.md`

Current durable pattern:
- Hermes `no_agent` cron posts a bilingual Mattermost reminder on the 21st of each month.
- Target Mattermost channel for 成型部管理 / Injection Molding Management: `87e6pxw6x3d5x8zitsquu3ec8o` (`https://mattermost.prodesign-group.com/injection-molding/channels/management`).
- Script wrapper lives under `~/.hermes/scripts/`; state/logs live under `~/.hermes/state/pd-one-worker-scheduling-initiator/` and `~/.hermes/logs/pd-one-worker-scheduling-initiator/`.
- The script must support `--check-only`, `--dry-run`, idempotent one-post-per-target-month state, and a post ID receipt before claiming the automation is live.
- If setup occurs on the 21st itself, dry-run first, then send the current-cycle kickoff manually so that month is not missed; the state file prevents duplicate posts for that target scheduling month.

## Runtime reminders

### Mattermost long-turn discipline for scheduling runs

For PD One Mattermost worker-scheduling sessions, do not let a single turn look like 30+ minutes of opaque work. Treat long solver/tool waits as an operational risk, not just a model/runtime nuisance:
- Before starting a solver run, state the group, max solver time, no-improvement cap, and that it is dry-run unless live writeback was explicitly approved.
- Use normal caps first: `solver_max_time_seconds=180`, `solver_no_improvement_seconds=60`, and a bounded tool timeout such as `timeout_seconds=360` for one group.
- If a run/tool wait exceeds roughly 4-5 minutes, stop after the current tool result and report a compact receipt/status before starting any next long tool call.
- Separate code repair from schedule execution: if the scheduler code or write-plan logic needs patching, patch/test/report first, then start a fresh dry-run turn.
- Never summarize a long scheduler turn as if all elapsed time was meaningful work. Report solver elapsed, wall elapsed, output directory, and whether the delay was solver time, sheet I/O, provider latency, context compression, or tool orchestration.
- For normal reports, return only the compact receipt: group, status, worker count, solver elapsed, wall elapsed, objective, output directory, blockers/warnings, and `write_enabled=false/true`. Inspect saved artifacts only if needed.

### Protected leave (`喪`) verification before operator/manager solves

Before running a solve group that may be affected by funeral/protected leave, explicitly verify `ProtectedLeaveDays` population before trusting the solver result:
- Parse `ProtectedLeaveDays` from `申請日期-當月統計` as the canonical structured source.
- If the destination schedule already contains `喪`, mirror those days back into the rest-request/source helper sheet first so Andy can visually confirm the same structured data PD One will use. Then rerun the solve from the updated source.
- Also infer existing destination schedule cells containing `喪` into protected leave before building solver inputs; this protects manual roster edits when helper columns are stale, but do not describe this as “source populated” unless the Google Sheet helper column was actually written and verified.
- Remove inferred/written `喪` days from requested/hard/flex rest lists for that worker before solving, so the same date is not treated as both rest and protected leave.
- Do **not** overwrite `申請日期-當月統計!AO1`. It is formula-owned; overwriting it with plain text `RequestedRestDays` can blank the `E:AI` visual request grid. If the parser sees `#REF!`/missing `RequestedRestDays` around AO1, use a local parser fallback only, stop before live source writes if needed, and ask Andy/admin to restore the sheet formula rather than writing AO1.
- Confirm the summary/input warnings or source-rollover receipt show protected leave, e.g. `ProtectedLeaveDays` / `protected_leave_days` for `<name>` has `[days]` or `5,20`.
- In the result receipt, mention the protected leave source write/verification and confirm whether live schedule writeback occurred.

### PD One / OpenClaw timeout triage for playbook kickoff threads

When a Mattermost worker-scheduling playbook thread reports `Request timed out before a response was generated` or suggests raising `agents.defaults.timeoutSeconds`, **do not immediately increase the global agent timeout**. First distinguish:
- `agents.defaults.timeoutSeconds`: overall agent run budget; in the OpenClaw runtime this may already be very large/unset.
- Codex app-server idle/completion timeout: logs such as `codex app-server turn idle timed out waiting for completion` point to `plugins.entries.codex.config.appServer.turnCompletionIdleTimeoutMs` instead.
- Approval/tool waiting: logs such as `plugin.approval.waitDecision` near 120s or a failed read-only shell command indicate approval handling, not a global timeout.

Safe diagnostic sequence:
1. Fetch/read the Mattermost thread and timestamp the failure posts.
2. Check OpenClaw config for `agents.defaults.timeoutSeconds` and Codex app-server config before proposing edits.
3. Check gateway logs around the thread timestamps for app-server idle timeout vs approval wait vs actual tool failure.
4. If only the Codex app-server idle timeout is implicated, prefer a targeted `turnCompletionIdleTimeoutMs` increase (for example 180–300s) over raising the global agent timeout.
5. If approval wait caused the failure, retry with smaller read-only steps and avoid approval-gated process checks unless necessary.

Reference: `references/pd-one-openclaw-timeout-triage.md`

Reference for the June 2026 manager-night dry-run/writeback receipt and interruption pitfall: `references/manager-night-writeback-2026-06.md`

Preferred live-run pattern on this host:

```bash
cd /home/prodesign/.openclaw/workspace/projects/automatic-worker-scheduling
HOME=/home/prodesign .venv/bin/python scripts/shift_scheduler_phase1.py \
  --gog-account admin@prodesign-group.com \
  --solve --solve-group <group>
```

When the worker scheduling MCP tool is available, prefer it over hand-running shell commands for normal monthly scheduling actions. In Hermes PD One it is exposed by the dedicated `pdone_worker_scheduling` MCP server (`/home/prodesign/.hermes/profiles/pdone/tools/pd_one_worker_scheduling_mcp.py`) as `mcp_pdone_worker_scheduling_worker_scheduling` after MCP discovery/reload; the general `pdone_safe_ops` server no longer exports worker scheduling so long scheduling writebacks do not block AppSheet/policy/Google-group tools. For normal playbook operations, do not bypass the safe MCP/google wrapper:
- `action="preflight"` for parse + destination dry-run only.
- `action="solve_preview"` for dry-run solves capped at 180 seconds.
- `action="write_generated_schedule_from_report"` for live generated-schedule writeback from an existing feasible/optimal `generated-schedule-report.json` after Andy/admin explicit approval. The old combined solve+write action is disabled.
- For live writeback, pass `confirm_live_write="RUN LIVE WORKER SCHEDULING WRITE"` exactly.
- Use `solve_groups=["day"|"night"|"manager_day"|"manager_night"]`, `solver_max_time_seconds`, `solver_no_improvement_seconds`, and an adequate `timeout_seconds`.
- Treat the tool's returned `output_dir`, solver status, and post-write verification/mismatch summary as the receipt. If the chat turn is interrupted after the tool returns, first process the prior tool result and report whether the write finished before doing anything else.
- After interrupted writeback, report only the groups that actually have a saved `generated_schedule_write` receipt; do not infer all originally requested groups completed. A writeback may be mostly formatting (`cells_written: 0`, `cells_formatted_only > 0`) when values already matched.
- If Andy reports a missing/deleted unrelated tab near a scheduling run, separate incident tracing from scheduler receipts: verify the tab's workbook ID, search local logs/artifacts for destructive Sheets calls, and recommend Drive Activity/Sheets version history for exact who/when if local evidence is inconclusive. See `references/worker-scheduling-writeback-receipts-and-unrelated-sheet-incidents.md`.

Use `HOME=/home/prodesign` for live Google Sheets runs from Hermes/PD One sessions. Normal `gog` PATH resolution should work in the `pdone` profile via `/home/prodesign/.hermes/profiles/pdone/home/.local/bin/gog`, which delegates to `/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace/scripts/google/gog.sh`. If a future environment still selects a stale wrapper or fails with `gog binary not found in standard locations` / missing-wrapper errors, pass the real binary explicitly to scheduler runs: `--gog-safe-path /home/prodesign/.local/bin/gog`, and use `/home/prodesign/.local/bin/gog` in shell commands until the profile shim is repaired.

Common blockers from the last cycle:
- `gog` missing default account -> pass `--gog-account`
- `gog binary not found in standard locations` from Hermes profile HOME -> prefix the scheduler command with `HOME=/home/prodesign`
- OR-Tools missing under system Python -> use `.venv`
- browser/HR MAX upload access can fail for network reasons unrelated to scheduler correctness

### Work-hours constant and HR MAX import

- The monthly total work-hours cell(s) on destination schedule tabs (for example July `115年7月-日!C1`, `115年7月-夜!C1`, `115年7月-幹部!C1`) are for the spreadsheet-bound Generate Import File / 104 HR MAX export path.
- The Python solver does **not** use these total work-hours cells to choose assignments; it uses `RequiredRestDaysCount`, request/constraint fields, previous-days, grade/staffing constraints, and AP:AT semantics.
- If Andy corrects only the monthly total hours (2026-07 example: `176H` → `184H` because July had four full weekends), update/read back the target-month work-hours cells and later regenerate/verify the import file. Do not rerun the solver just for that constant.
- Scope the update to the target month tabs only; do not update next-month tabs such as `8月-幹部` when a UI find operation lands there. See `references/2026-07-hours-and-safe-tooling.md`.

## HR MAX handoff

- The spreadsheet Apps Script can generate the HR MAX import workbook.
- Before generating/exporting a target month such as `2026-07`, refresh/recalculate the previous-month schedule sheet first (for example `115年-6月` / June carryover source) so rolling 7-day 104 checks that cross the month boundary use current data. Do **not** offer/export the previous month; use it only as carryover context, then calculate/prep/export the target month.
- Because Andy normally triggers HR MAX / 104 export manually through the spreadsheet **Custom Actions Menu**, the Apps Script export action itself must enforce this order automatically: refresh/recalculate prior-month carryover first, wait/read back enough to avoid stale formulas, then generate only the target-month export. Do not rely on the human operator to remember a separate prior-month recalculation step. The `Download XLSX` line `Previous-month carryover refreshed:` is that receipt when it names the prior-month tab. Do not add a second manual recalculation step.
- Observed export path on workbook `10DU9Yro5tDacrjBlOfuGE9JCcYFkC7ribJKuaxnRWhE` (`良器-成型部-排班表 Injection Molding Shift Schedule`). Open `自訂動作 / Custom Actions`, not the Google Sheets Extensions menu. Under `自動排班後 / After Auto Scheduling`, run `產生匯入檔案 / Generate Import File`. The year-month dialog carries the script version, for example `Joi-v20260225b`. Do not require that token on the menu itself. The dialog title is `Enter year and month`. The note is `Format: YYYY-MM (e.g. 2026-11)`. Buttons are `Cancel` and `OK`. After OK, the dialog title is `Download XLSX`. The output line uses `Output created: 班表匯入_<year>_<month>.` Treat the token before the final period as the output name until a downloaded filename proves otherwise. The download control is the link `Click here to download as .xlsx`. Clicking OK does not download the file. A new tab `115年-<M>月` can appear before the file exists. A collapsed row `Schedule violations (no 例假日 every 7 days)` is unread until expanded. Do not call the export clean while that row is collapsed. `標記未排班的假日 / Mark Unscheduled Holidays` and `標記班表 / Mark Schedule` are not the export. The import page is now observed. Follow the portal steps in the next bullets. Do not invent fields that were not on screen.
- To watch that desktop, use container `pdone-desktop-browser`. The page is `https://nemo.tail05d15a.ts.net/pdone-desktop/vnc.html?path=pdone-desktop/websockify&autoconnect=1`. Do not post the VNC password in a group channel. Host display `:99` is a different Chrome. The container's own `DISPLAY=:99` is the desktop. Raw `:6081` is a different browser. A connection reset on host `127.0.0.1:9224` does not mean the desktop container is down. Use in-container CDP `Page.captureScreenshot` against `127.0.0.1:9222` only for a Sheets dialog that is page content. That capture misses the browser download shelf, a native file dialog, and any other window. When the user is demonstrating the download or the HR portal, record the container X11 root and let them finish one pass. Do not ask them to pause after every click. An unchanged page screenshot is not proof the download failed.
- Treat stale prior-month carryover as a likely cause of 104 calendar errors such as `2026/06/29 ~ 2026/07/05 ... 少 1 日例假日`, especially when the prior-month sheet incorrectly marks a worker as `例假日` but the final schedule has them working on 6/29 and/or 6/30. Fix/refresh the prior-month schedule context first, regenerate the 104 file, and patch Apps Script/export menu logic so future manual Custom Actions exports do the carryover refresh before the target export.
- File generation is automatable.
- Live Apps Script source patching requires a working `gog appscript content/get` + Apps Script API update path (or an equivalent Apps Script editor session). If a subagent has only MCP scheduling/file tools and no terminal/gog/AppScript update tool, do not claim the live script was patched; create a bounded patch/diff receipt under the task tmp directory and report the exact tooling blocker.
- Probe `https://hrs.prodesign-group.com:2020/` before calling the portal unreachable. Plain HTTP on port 2020 returns nginx `400` `The plain HTTP request was sent to HTTPS port`. Use `https://hrs.prodesign-group.com:2020/hrm/30100`. A 200 shell titled 104 HR Max is reachability, not a signed-in session; the login form is client-rendered, so a raw HTML GET will not show 登入.
- Do not type a password or accept one in chat. Claim backend access only after a saved browser-vault login completes a session. A missing vault item means the host is reachable and the backend is not entered.
- Observed import path after a signed-in session: open `出勤` then `排班`. Set the range to the target month, department `成型`, and `一段班` before import. The page buttons are `儲存班表`, `匯入班表`, `匯出班表`, and `報表`.
- Click `匯入班表`. The dialog title is `匯入班別排班班表`. Keep import type `行事曆別班別合併，不含標籤`. The drop text is `請「點擊」選擇匯入檔案，或將匯入檔案「拖拉」於此處進行匯入作業`. The warning says import overwrites the preview and the update is final only after `儲存班表`.
- The Sheets link `Click here to download as .xlsx` does not give Chrome a filename. This desktop saves the first file as `download` and the next as `download (1)`, with no extension. Both are still xlsx: the first bytes are `PK`. Do not upload the extensionless file. Tell Chrome to assign `.xlsx`, or rename the file to `download.xlsx`, before the HR MAX picker. Do not require the disk name `班表匯入_YYYY_MM.xlsx`. After the extension is present, confirm sheets `班表資料`, `匯入班表說明`, and `行事曆別及班別`, plus the target-month string such as `2026/11/01 ~ 2026/11/30`. The native file dialog can open at `/`. Choose the Downloads file that ends in `.xlsx`, not a root folder and not the extensionless file.
- The preview chip shows the file name and size. A pass shows green `正常` rows and the button `確認匯入`. The other button is `取消匯入`. Click `確認匯入` only after that preview. The success toast is `匯入成功`.
- After success, an hours-rule dialog opens. A spinner is not the result. The pass line is `班表內所有員工都符合工時規則檢查`. The observed header was `排班人員` `成型 56 位員工 + 其他員工 0 位員工，共 56 位員工` and `班表起訖時間` `2026/11/01 - 2026/11/30`. Rule rows A through L showed `0`. Close with `關閉`.
- Do not call the portal month saved unless `儲存班表` is clicked after `匯入成功` and a save receipt is on screen. The observed pass stopped at `匯入成功` plus the hours-rule pass. `儲存班表` was visible and was not clicked after that toast.
- Do not conflate HR MAX portal access problems with scheduler correctness.

## Output expectations

When helping Andy live:
1. state the current step in the monthly workflow
2. say what is verified vs not yet verified
3. use the smallest safe next action
4. update a durable run tracker or create/link a receipt after every material step; do not rely on active session memory as the only state tracker for a monthly scheduling run
5. update the runbook/docs if the process materially changes
6. if you promise that next month will be easier, write the damn rule down before you stop

For tracker schema and migration-away-from-Mattermost-Playbooks details, see `references/worker-scheduling-run-tracker.md`.

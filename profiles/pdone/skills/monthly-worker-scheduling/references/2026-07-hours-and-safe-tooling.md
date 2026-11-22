# 2026-07 scheduling notes: work hours, source rows, and safe tooling

## Work-hours constant vs actual scheduling

During the 2026-07 run, there was a correction cycle around total work hours: an initial inference changed July schedule-tab work hours from `176H` to `184H`, but Anna later clarified that **`176H` was correct** because July/August rest-day counts had been adjusted to average rest days (`7月: 8→9`, `8月: 10→9`).

Operational rule:
- Treat monthly total work hours as an HR/admin scheduling constant, not something to infer from calendar weekends alone. Do not override Anna/HR-provided constants with arithmetic such as `8 * working days` unless Andy explicitly confirms that formula for the month.
- The total work-hours cells on the target-month schedule tabs (for example `115年7月-日!C1`, `115年7月-夜!C1`, `115年7月-幹部!C1`) feed the script-generated 104 HR MAX import file / downstream export.
- They are not solver inputs for the generated schedule assignment. The Python scheduler uses `RequiredRestDaysCount` / rest constraints, AP:AT constraints, previous-days, and grade/staffing data; it does not use the total-hours cell to decide daily assignments.
- Therefore, changing the total work-hours constant normally requires regenerating/verifying the import file, not rerunning the solver, unless some other schedule input also changed.
- Scope the change to the target month tabs only. Do not update the next-month tab (for example `8月-幹部`) just because a find operation lands there.
- If a wrong work-hours value was already written, revert the same scoped target-month cells after dry-run/readback and cite the HR/admin correction as the reason.

Verification pattern:
1. Read/inspect the target month schedule tabs and identify the work-hours cell(s), commonly `C1` with a label like `工作小時`.
2. Update only the target month day/night/manager tabs.
3. Read back each changed cell before reporting completion.
4. State explicitly whether the solver was rerun. For work-hours-only corrections, it usually should not be.

## Missing-worker source-stat additions

When a worker exists in the target-month destination schedule tab but is missing from `申請日期-當月統計`, add the worker only through the manual participation fields:
- `B`: class / participation group
- `C`: name
- `D`: previous consecutive work days

Do **not** manually write into:
- `E:AI` visual request grid
- `AK:AO`
- `AU:AX`

Those ranges are formula/arrayformula-owned. A normal missing-worker add should let formulas populate worker ID, grade, required-rest/month/year helpers, and structured request fields. If formula-owned ranges were accidentally populated manually, clear only the formula-owned cells on that row, verify headers/formulas recover, then rerun preflight before solving or writing back.

## Tooling discipline from this run

For routine worker-scheduling playbook actions, prefer the dedicated MCP worker-scheduling tool or normal `gog` calls. Avoid bypassing the safe wrapper with `execute_code` for regular playbook operations.

Good pattern:
- MCP `worker_scheduling` actions for raw request corrections, preflight, solve previews, and generated writeback.
- Normal `gog`/browser UI for narrow sheet reads/writes that the MCP wrapper does not yet cover, with dry-run/readback where practical.
- If a tool call times out after a live writeback attempt, search/read the expected output directory and verification reports before retrying or claiming failure. Some writebacks complete successfully even when the wrapper response times out.

Do not encode transient tool-routing/model-selection failures as durable claims that a tool is broken. Capture the safe fallback/retry pattern instead.
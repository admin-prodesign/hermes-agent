# Worker scheduling writeback receipts and unrelated-sheet incident tracing

## Trigger

Use this reference when a monthly worker scheduling turn is interrupted during live writeback, or when Andy reports a Google Sheet issue that may have happened around the same time as a scheduling run.

## Receipt-first rule after interruption

If a chat turn is interrupted after `worker_scheduling_execute(action="write_generated_schedule")` returns, do **not** start another run immediately. First inspect/report the saved output directory or `summary.json` from the interrupted tool result.

Key fields in `summary.json`:

- `generated_schedule_write.summary.groups_written`
- `generated_schedule_write.summary.groups_with_write_failures`
- `generated_schedule_write.runs[].run_group`
- `generated_schedule_write.runs[].status`
- `generated_schedule_write.runs[].write.mode == "generated_schedule_write_complete"`
- `generated_schedule_write.runs[].write.summary.candidate_write_action_count`
- `value_write_batch_count`
- `cells_written`
- `cells_formatted_only`
- `rows_written`
- `cells_with_background_cleared`
- `cells_with_yellow_background`
- `cells_with_orange_background`
- `failed_updates`

Report the exact group(s) actually written. Do not infer that requested groups were all written; interrupted turns often leave one group complete and the next group not started.

## MCP resumable write gate

`write_generated_schedule_from_report` returns `partial` while batches remain. Call it again with `next_payload` and the same `output_dir` until status is `ok` or a hard error. Do not start a new output directory. A caller that omits `output_dir` creates a new directory and does not resume state.

Claim the group complete only when both are true:

- the write report status is `written` and `failed_updates` is 0
- verification `mismatched_actions` is 0

Do not require verification `source_summary.write_enabled=true`. That object is copied from the solve preview. A successful from-report write still shows `write_enabled=false` there. Judge the write report, not that field.

A verification file with `mismatched_actions` 0 proves cell values only. Background-color clears are separate format updates. If those fail while values verify, say the values are verified and the format write is not complete. Resume the same output dir for the remaining format batches. Do not re-solve.

`dial tcp ... i/o timeout` and `http2: timeout awaiting response headers` are network failures, not a bad schedule. Resume the same output dir. Do not create a new solve directory for that group.

## June 2026 example

During the June 2026 rerun after the `AO1` formula restore, a live writeback output existed at:

`/home/prodesign/.openclaw/workspace/tmp/shift-scheduler-phase3/20260526-122320/summary.json`

It showed:

- write timestamp around `2026-05-26T12:57`
- `groups_written: 1`
- `run_group: day / 作業員-日`
- `status: written`
- `failed_updates: 0`
- `cells_written: 0`
- `cells_formatted_only: 660`
- `cells_with_yellow_background: 54`
- `cells_with_orange_background: 1`

This meant the interrupted tool did complete the **day operator** schedule formatting/write receipt, but it did **not** rerun/write the night operator group in that same output.

## Unrelated workbook/sheet incident tracing

When Andy reports a missing/deleted tab near a scheduling run, do not assume causation. Trace separately:

1. Identify the workbook ID and tab name Andy reported.
2. Compare it against the worker scheduling spreadsheet IDs/tabs used by the current run.
3. Search local session/tool logs and workspace artifacts for the reported tab/workbook ID plus destructive request terms:
   - the exact tab name, e.g. `C Dashboard - 未結`
   - the workbook ID
   - `deleteSheet`, `DeleteSheet`, `delete_sheet`, `spreadsheets.batchUpdate`, `batchUpdate.*delete`
4. Check current read-only metadata to confirm whether the tab exists now and record `sheetId`, grid size, and hidden state.
5. If local evidence does not show a delete, say so plainly and recommend Google Workspace/Drive Activity or Sheets version history for exact who/when. Do not claim deletion was or was not caused by PD One beyond the evidence.

## Pitfalls

- Worker-scheduling receipts live under the scheduler output directory, not necessarily in the visible chat if the turn was interrupted.
- A completed writeback may be mostly formatting (`cells_written: 0`, `cells_formatted_only > 0`) if the values already match; this is still a writeback/formatting receipt.
- Night color-coding complaints require a fresh post-write format verification/readback for the night tab before making any new writes.
- Do not conflate worker scheduling sheet writes with unrelated Tech Dev / Cases workbook tabs. If a tab belongs to another workbook, treat it as a separate incident investigation.

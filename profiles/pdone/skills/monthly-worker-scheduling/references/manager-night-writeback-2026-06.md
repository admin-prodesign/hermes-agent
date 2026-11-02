# June 2026 manager-night dry-run/writeback notes

Session learning from the June 2026 worker scheduling cycle.

## Correct scheduling priority

For manager schedules, the root priority from Andy's correction is staffing consistency:
1. Keep adjacent daily manager staffing counts even.
2. Preserve 2-work/1-rest rhythm only as a secondary preference.
3. Keep requested rest satisfaction at normal priority; do not over-explain manager balancing as a rest-request-weight issue.

In this session the durable config direction was:
- `rest_request_weight = 100`
- `work_2_rest_1_bonus = 100`
- `fluctuation_weight = 1000`

## Tool pattern that worked

Use `worker_scheduling_execute` when available.

Dry-run example:
```json
{
  "action": "solve_preview",
  "solve_groups": ["manager_night"],
  "solver_max_time_seconds": 600,
  "solver_no_improvement_seconds": 90,
  "stdout_summary_only": true,
  "timeout_seconds": 900
}
```

Live writeback example after explicit Andy/admin approval:
```json
{
  "action": "write_generated_schedule",
  "confirm_live_write": "RUN LIVE WORKER SCHEDULING WRITE",
  "solve_groups": ["manager_night"],
  "solver_max_time_seconds": 600,
  "solver_no_improvement_seconds": 90,
  "stdout_summary_only": true,
  "timeout_seconds": 1200
}
```

## Receipts from the successful writeback

Dry-run output directory:
- `/home/prodesign/.openclaw/workspace/tmp/shift-scheduler-phase3/20260525-044433`

Live writeback output directory:
- `/home/prodesign/.openclaw/workspace/tmp/shift-scheduler-phase3/20260525-050351`

Live writeback summary:
- run group: `manager_night` / `幹部-夜`
- target tab: `115年6月-幹部`
- solver status: `FEASIBLE`
- solver elapsed: about `600s`
- post-write verification mismatches: `0`

## Pitfall

If the assistant turn is interrupted while a long `worker_scheduling_execute` call is running, the next turn may already contain the tool result. Always process the previous tool result first and report the completion/verification status instead of assuming work is still running.

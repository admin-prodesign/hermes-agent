# Manager-day Weekend Supervisor Bias

## Trigger

Use this pattern when the day-shift 課長 should preferentially work Saturdays and Sundays so other 幹部 have an experienced escalation point.

## Implementation status rule

Treat the feature as **not implemented** until all three receipts exist:

1. live `排班規則 Scheduling Rules` tab readback;
2. parser/solver test results;
3. read-only `manager_day` solve preview reporting weekend coverage.

A design discussion or admin handoff is not an implementation receipt.

## Resolve the source workbook

The run tracker and live scheduling source may be different workbooks. Run typed worker-scheduling `preflight` and read `summary.source.spreadsheet_id` plus `summary.source.sheet_name` before creating or querying the rules tab.

For the 2026-08 source cycle, preflight resolved:

- spreadsheet: `1vdxticeWyaJrAPrmVcLmm8wld6ZBxzdNriXdc8ywH44`
- source tab: `申請日期-當月統計`

Re-resolve on future cycles instead of relying indefinitely on this recorded ID. Treat `排班流程追蹤 Tracker` as run-state storage unless preflight independently identifies its workbook as the live source.

## Verify the supervisor by stable identity

Do not hard-code a display name in the solver. Seed and join by scheduler `WorkerID`, and verify current role/employment from a scoped authoritative source for each effective period.

Evidence from the 2026-08 source snapshot (initial seed only):

- scheduler source: `W12` → `王柏凱`, group `幹部-日`;
- bounded AppSheet `HR_Employees` lookup: `Job Title = 課長`, `Employment Status = Employed`, `BU = 成型一課`.

**Andy 2026-08-25 standing rule:** the weekend-bias person is whichever of `楊正義` or `王柏凱` is `幹部-日` for that month. Remap `WorkerID`/name to that person before preflight/solve. Do not invent a `manager_night` copy. Do not revert source class to keep a stale seed. Revalidate `課長` / `Employed` from a scoped HR source when remapping.

This is not a permanent guarantee of either name. Revalidate after role, employment, or rotation changes.

## Rules-tab row

Recommended tab: `排班規則 Scheduling Rules`.

Recommended columns:

- `RuleID`
- `Enabled`
- `WorkerID`
- `ScheduleGroup`
- `ManagementRole`
- `BiasType`
- `BiasMode`
- `Weight`
- `WeekendCoverageTarget`
- `ProtectRequestedRest`
- `EffectiveFrom`
- `EffectiveTo`
- `Notes`

Initial rule values (2026-08 create-seed; remap WorkerID each month):

- `WorkerID` = current `幹部-日` person among `楊正義` / `王柏凱` (was `W12` in 2026-08)
- `ScheduleGroup = manager_day`
- `ManagementRole = 課長`
- `BiasType = weekend_work`
- `BiasMode = prefer`
- `WeekendCoverageTarget = all_eligible_weekend_days`
- `ProtectRequestedRest = TRUE`
- preview starting weight around `1500`
- effective start aligned to the approved target scheduling cycle

Preflight must fail clearly when zero or multiple enabled/effective `manager_day` 課長 rows exist, the configured worker is absent from `manager_day`, or rule values/dates are invalid.

## Solver contract

Apply only to `manager_day`:

1. derive Saturdays and Sundays from target year/month;
2. compute the configured supervisor’s eligible weekend days;
3. exclude `HardRestDays`, `FlexRestDays`, `ProtectedLeaveDays`, and `SpecialWorkDays`;
4. when `ProtectRequestedRest = TRUE`, exclude `RequestedRestDays`;
5. reward working on eligible weekends or penalize eligible weekend absence;
6. keep `RequiredRestDaysCount` unchanged and shift preferred rest to weekdays where feasible;
7. preserve legal constraints and existing manager staffing-floor/low-staffing objectives.

Recommended precedence:

1. legal and hard constraints;
2. protected leave and required rest count;
3. manager staffing floor / low-staffing avoidance;
4. protected employee leave/rest requests;
5. weekend 課長 coverage;
6. adjacent-day smoothing and 2-work/1-rest rhythm.

Do not use `SpecialWorkDays` to force the result; it writes `訓` and has different staffing semantics.

## Implementation sequence

1. Create the rules tab and read back headers/seed row.
2. Patch parser loading, normalization, effective-date selection, and uniqueness validation.
3. Patch solver objective only for the intended rule/group.
4. Add report fields: weekend dates, eligible dates, scheduled dates, missed dates/reasons, and coverage rate.
5. Add regression tests.
6. Run baseline and enabled `manager_day` previews against the same source snapshot.
7. Compare weekend coverage, weekday rest substitutions, daily manager counts, requested-rest satisfaction, and maximum consecutive workdays.
8. Record the selected preview in the monthly tracker.
9. Keep generated-schedule writeback as a separate explicitly confirmed operation.

Report unrelated preflight mismatches separately; do not silently repair participant rows, request history, or destination tabs while implementing this feature.

## Regression cases

- exactly one active/effective rule parses successfully;
- zero and duplicate effective rules fail visibly;
- configured worker absent from `manager_day` fails visibly;
- `manager_night` and operator groups are unchanged;
- hard, flex, protected, special-work, and protected requested-rest dates are excluded;
- required rest-day count stays unchanged;
- weekend coverage improves without new low-staffing days;
- report gives a reason for every missed eligible weekend;
- implementation QA performs no generated-schedule writeback.

# HeartBeat case-count cache speedup follow-up (2026-06-11)

Use this as a concrete reference for AppSheet HeartBeat optimizations where a scheduled bot fans out to many user/settings rows and creates cache-lock or cancellation failures.

## Implemented pattern

Throttle the HeartBeat fan-out to only stale rows and process a bounded oldest-first batch:

```appsheet
TOP(
  ORDERBY(
    SELECT(
      HR_Employees_AppSheet_Settings[PersonID],
      AND(
        [Needs_Case_Count_Cache] <> "FALSE",
        OR(
          ISBLANK([Counts_UpdatedAt]),
          UTCNOW() - [Counts_UpdatedAt] > "000:55:00"
        )
      )
    ),
    [Counts_UpdatedAt],
    TRUE
  ),
  25
)
```

Also put the same freshness guard on the row action so manually/internally invoked work skips recently refreshed rows:

```appsheet
AND(
  CONTEXT("Host") = "Server",
  [Needs_Case_Count_Cache] <> "FALSE",
  OR(
    ISBLANK([Counts_UpdatedAt]),
    UTCNOW() - [Counts_UpdatedAt] > "000:55:00"
  )
)
```

## Verification pattern

1. Verify definition readback after save/promotion: latest version, stable version, and `IsValid=true`.
2. Smoke the selector through the Data API or an equivalent readback: target count should be bounded at the configured batch size, e.g. `25`.
3. Run one row-action smoke against a stale test `PersonID` and read back `Counts_UpdatedAt` / updater fields.
4. Re-run the selector after the smoke: the freshly updated row should drop out of the next batch.
5. Check Performance Analyzer after deployment with both:
   - failures-only HeartBeat rows, and
   - all HeartBeat rows for the same windows, so success/failure rate is visible.

## Analyzer comparison used

For a fair quick check, compare same-duration windows immediately before and after stable promotion rather than only overlapping rolling watchdog windows.

Example result from the 2026-06-11 case-count cache change:

| Metric | Before | After | Direction |
|---|---:|---:|---:|
| HeartBeat failure rows, all HeartBeat export | 105 / 632 | 55 / 725 | failure rate `16.6% -> 7.6%` |
| HeartBeat rows in failures-only export | 332 | 69 | down ~79% |
| Failed HeartBeat `Change Bot` rows | 315 | 65 | down ~79% |
| `MatchesCondition=True` rows in failures-only export | 51 | 7 | down ~86% |
| `HeartBeat - RowCount` average duration sample | 122.4s | 79.5s | down ~35% |

Interpretation rule: if RowCount/cache failures improve but HeartBeat remains noisy, identify the next HeartBeat processes separately instead of claiming the whole HeartBeat system is fixed. In this case the remaining pressure moved to PQ / ActivityLog / CaseUpdate HeartBeat processes such as `HeartBeat_PQ_CaseUpdateParentSync`, `HeartBeat_AL_Repair_NG_MissingSessionItems`, and `HeartBeat_PQ_ActivityLogInit`.

## Pitfalls

- Do not judge improvement from failures-only scans alone; they show failure volume but hide total HeartBeat volume and success rate.
- Rolling 2-hour watchdog windows overlap the deployment boundary; for before/after claims, run explicit same-duration windows split around the actual stable-promotion time.
- AppSheet `Properties.Performance` duration fields may be nested JSON strings. Parse `PerformanceTimingRoot` and nested timers; do not rely only on top-level report counts.
- Remaining failures after a targeted RowCount/cache fix may be real, but they can belong to different HeartBeat process classes. Report that distinction.
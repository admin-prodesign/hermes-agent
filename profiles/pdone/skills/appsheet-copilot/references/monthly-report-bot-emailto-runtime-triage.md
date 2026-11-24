# Monthly report bot `EmailTo` runtime triage

Use this note when monthly AppSheet bots for Excel report summaries fire on schedule but recipients report no email, or AppSheet logs show the email task failed with a blank `EmailTo`.

## Incident signature
- Scheduled event exists and fires at the intended local time, e.g. day 2 at noon Taipei (`0 12 2 * *`, `Taipei Standard Time`).
- Performance/export logs show the bot condition matched and the XLSX attachment was generated.
- The task result is failure because `EmailTo` evaluated to blank/empty at runtime.
- The report attachment can still be visible in task details, so do not assume report generation failed.

## Fast diagnosis path
1. Pull a tight AppSheet performance/export-log window around the scheduled time in UTC.
2. Identify both the process/bot row and the child email-task row.
3. Confirm separately:
   - schedule/event fired,
   - condition evaluated true,
   - attachment template rendered,
   - `EmailTo` value at runtime,
   - task result.
4. Probe the recipient source table with the same deployed/prototype context used by the automation. For Pro-Design HR runtime recipient roles, prefer `HR_Employees_AppSheet_Settings[Appsheet Email]` filtered by the relevant role token in `[Appsheet Roles]` / `[Combined Appsheet Roles]`; do not conclude recipients are absent from a zero-row result until the selector shape has been checked.
5. Inspect the saved AppSheet definition for the actual email task `ToList`/recipient expression. Treat the saved definition as wiring truth and export/performance logs as runtime truth.

## Durable fix pattern
Avoid server-automation recipient expressions that cross from `HR_Employees` through `LOOKUP()`/`SPLIT()` back into runtime role data when the same result can be selected directly from settings/runtime rows. Those expressions can evaluate blank in automation context even when role memberships exist.

Preferred pattern for report emails:
- Normal branch: send the report XLSX only if `COUNT(<recipient-select>) > 0`.
- Recipient select: direct `SELECT(HR_Employees_AppSheet_Settings[Appsheet Email], <role-membership predicate>)` using the report recipient role token.
- Failure branch: if the count is zero, do **not** send the report XLSX to an admin fallback. Instead send a separate failure notification to `admin@prodesign-group.com` stating that the recipient email list was empty and the automation failed.

This keeps confidential report attachments from being redirected to an admin fallback while still surfacing the configuration failure.

## Manual-run validation pattern
To manually validate a monthly scheduled bot without waiting a month:
1. Save a temporary definition version that changes only the scheduled event cron/timezone to a near-immediate run time.
2. Promote that temporary version stable if AppSheet requires stable scheduled automations.
3. Wait for the run and scan a tight runtime log window around it.
4. Restore the original cron/timezone immediately and promote the restored version stable.
5. Verify from logs that the manual run had non-empty `EmailTo`, generated the expected attachment, and returned `Success`.
6. Verify the final definition still has the intended original schedule and `IsValid`/`IsRunnable` are true.

## Pitfalls
- A wait/orchestration script may time out while AppSheet still runs the scheduled automation. Follow up with performance/export-log evidence before declaring failure.
- AppSheet save conflicts such as HTTP 409 can indicate stale editor payload/version collision. Re-load/read back the final definition before reporting the schedule is restored.
- Backup/sync the refreshed definition after live editor saves so future investigations see the final stable version.

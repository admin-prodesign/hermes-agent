# Retry-until-deadline cron pattern

Use this pattern for scheduled reports/posts whose first attempt may fail due to transient upstream API, DNS, or network issues, but where duplicate external sends are unacceptable.

## When to use

- A scheduled job sends a user-visible report/message once per local business date.
- Transient upstream failures are common enough that a single cron attempt is brittle.
- Retrying immediately would be noisy, but waiting until tomorrow is unacceptable.
- The useful delivery window has a clear cutoff, e.g. morning briefing retries until 09:30 local time.

## Pattern

1. Replace the one-shot cron with a bounded retry window, e.g. every 5 minutes from start time through deadline.
2. Keep the existing sender small and focused on one attempt.
3. Add a retry wrapper that:
   - computes the local business date using the business timezone;
   - reads a durable per-date state file;
   - exits 0 without calling the sender when that date already has `ok` or expected `skip` recorded;
   - calls the sender for each uncompleted attempt;
   - records each attempt with start/end timestamps, return code, payload, target, and whether it was the final attempt;
   - treats successful send/skip payloads as terminal for that local date.
4. Use `flock` or equivalent to prevent overlapping attempts.
5. Suppress external failure alerts on non-final retries, but still log every failed attempt.
6. On the final deadline attempt, allow normal failure alerts and return non-zero if still failing.
7. If a human-approved manual rerun succeeds before the wrapper state exists or before the next retry, seed the state file with the post/result id to prevent duplicate sends.

## Cron shape example

```cron
# Every 5 minutes 08:00-09:30 Asia/Taipei == 00:00-01:30 UTC
*/5 0 * * 1-5 /usr/bin/flock -n /tmp/job.lock /path/run_with_capped_log.sh /path/job.log 1048576 /path/retry_wrapper.py target
0-30/5 1 * * 1-5 /usr/bin/flock -n /tmp/job.lock /path/run_with_capped_log.sh /path/job.log 1048576 /path/retry_wrapper.py target
```

## Verification checklist

- `python3 -m py_compile` or equivalent syntax check for touched scripts.
- Run a dry-run/readback that verifies the external target identity before scheduling (for example Mattermost channel display name/id, sender username, attachment existence/size).
- Run wrapper after seeding a success state and confirm it returns `already_done` without sending.
- Inspect installed crontab/timer schedule and timezone conversion.
- Confirm non-final attempt logs failure but does not send external failure alert.
- Confirm final attempt remains alert-enabled/non-zero.
- For posts with attachments, verify the sender records a created post id and non-empty attachment/file id before claiming delivery.
- Commit/push durable script, skill, and documentation changes when the repo has a backup remote.

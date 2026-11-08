# AppSheet HR_E_A_S blank-settings canary monitor

Use this when monitoring the Pro-Design `HR_Employees_AppSheet_Settings` (`HR_E_A_S`) migration after disabling populate bots, backfilling settings, repairing `_Is_*` flags, or investigating reports of blank Home/views.

## Purpose

Detect real database regressions separately from AppSheet browser/client cache symptoms.

Real data regression indicators:
- `HR_E_A_S` has a blank core app-setting value while linked `HR_Employees` still has a populated value.
- Stored `_Is_*` permission booleans disagree with the expected value computed from `Combined Appsheet Roles`.
- Runtime logs show `ADD_RECORD_TO`, `SET_COLUMN_VALUE`, REST API edit, or bot/process write touching `HR_Employees_AppSheet_Settings` near the report time.

Client/cache symptom indicators:
- Data API/current Settings row is correct.
- No HR_E_A_S writes occur in the report window.
- User sync logs repeatedly show `Table:HR_Employees_AppSheet_Settings = LastModified:01/01/0001 00:00:00, NotModified:True` with the same per-table etag, even after app definition changes or recent server-side row edits.
- User says logout/login or a later session made views reappear without any database repair.

## Monitor checks

At minimum, each check should:

1. Pull `HR_Employees_AppSheet_Settings` and `HR_Employees` through the AppSheet Data API/read-only helper.
2. Join by `PersonID`.
3. For each currently relevant settings row, compare the six core duplicated app-setting columns:
   - `Appsheet Dashboard Type`
   - `Appsheet Views Access`
   - `Appsheet Navigation Bar`
   - `Appsheet Menu Items`
   - `Appsheet Roles`
   - `Appsheet Notification Group`
4. Count only true blank gaps: `HR_E_A_S` blank while linked `HR_Employees` has a nonblank value.
5. Recompute expected `_Is_*` permission booleans from normalized `Combined Appsheet Roles` and report mismatches separately from blank gaps.
6. Persist a JSON artifact every run, including timestamp, row counts, gap count, mismatch count, first sample rows, and artifact path.
7. Keep state so alerts distinguish new regressions, persistent problems, and recovery.

## Scheduling pattern

For short canaries, create an expiring Hermes no-agent cron job:

```text
schedule: every 1h
repeat: 48 or 168 depending on requested window
script: hr_eas_blank_monitor.sh
workdir: /home/prodesign/.openclaw/workspace
deliver: origin
```

Prefer a shell wrapper under `~/.hermes/scripts/` that execs system Python, for example:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/python3 /home/prodesign/.hermes/scripts/hr_eas_blank_monitor.py "$@"
```

This avoids scheduler failures when no-agent cron tries to resolve a missing project venv/interpreter. Verify by manually running the wrapper and then using `cronjob(action='run')` plus `cronjob(action='list')` to confirm `last_status=ok`.

## Alert behavior

- Silent on clean scheduled runs.
- Alert on new blank-gap increase, new permission mismatch increase, or script failure.
- Send a recovery message when the gap/mismatch count returns to zero after a previous problem.
- Keep unrelated employee rows with blank HR legacy values out of `blank_gap_count`; they may be valid incomplete/temporary HR records, but include a separate diagnostic count if useful.

## Runtime-log investigation window

When a user reports blank settings or missing views:

1. Convert reported local time to UTC explicitly.
2. Export user-specific logs for the suspected window by AppSheet user id if known.
3. Export `HR_Employees_AppSheet_Settings` table logs over the same window.
4. If the user reports later recovery, export through that recovery time too.
5. Interpret recovery without HR_E_A_S writes as likely client/cache/session refresh, not database repair.

Evidence pattern from the Lorelie May 2026 case:
- Screenshot at `20:48 TPE`; reported views returned around `05:00 TPE` next day.
- User syncs between those times were polling syncs with no HR_E_A_S table writes.
- Syncs repeatedly reported `HR_Employees_AppSheet_Settings` as `NotModified:True` with the same etag.
- Settings DB row and `_Is_*` flags were correct; logout/login or later session reload explained the visible recovery better than a data backfill.

## Reporting guidance

When reporting to Andy:
- Separate “database value was wrong” from “client showed stale/false value.”
- Name the exact window, timezone conversion, user id/email/PersonID, and whether any HR_E_A_S writes occurred.
- If no writes occurred but the user recovered, say no database repopulation evidence was found and recommend force sync/logout/login for affected users.
- Do not rerun a backfill solely because a user reports a blank screen if Data API/current Settings row and monitor are clean.

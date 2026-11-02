# Facilities recurring-task catalog rows

Use when adding, pausing, or retargeting a Facilities recurring reminder in `良器-廠務-定期任務 Facilities Recurring Tasks` (`1w1JAybCT8lfh9kt5jGzCJVdYTqt71qBBPtCl1cNWBos`). Do not tell colleagues to type into the protected catalog; change rows through PD One.

## Runner

- Script: `/home/prodesign/.hermes/profiles/pdone/scripts/facilities_recurring_task_runner.py`
- Cron: `3ff9b34d92c1` daily `0 1 * * *` (09:00 Taiwan), `deliver=local`, posts itself into Facilities `4exmpsnorjy8xxhse5z3sm564h`
- Config: `/home/prodesign/.hermes/profiles/pdone/config/facilities_recurring_tasks.json`
- Tests: `/home/prodesign/.hermes/profiles/pdone/tests/test_facilities_recurring_task_runner.py`

## Due rules

- `first_workday_of_month` + `Due month`: annual, first Taiwan workday of that month.
- `first_workday_of_each_month`: monthly, first Taiwan workday of each month. After complete, next due is the first workday of the month after the completion date (late close does not immediately reopen).

## Nag

- `Nag every days / 催辦天數` may be `14` (calendar days) or `3 workdays` / `3w` (Taiwan workdays, weekends and config holidays skipped).
- Repeat nags stay in the same root thread. Before posting the next nag, delete the previous bot nag in that thread if no non-bot reply landed after it. Never delete the cycle root or a failure card.

## Done rules

- Default: human (non-bot) first-line `完成` / `done`.
- `Done tokens` containing `CASE_ID`, or `Done mode` = `facilities_lead_case_id`: only a `facilities_lead` / `facilities_head` Mattermost user posting an AppSheet Case ID (`C-...`) closes the cycle. `完成` alone is not enough. Completer IDs are resolved from canonical `mattermost-users.json` by exact role, not by @username.

## Current production rows

- `FAC-AC-ANNUAL`: April first workday, 14 calendar-day nags, done tokens, mention `@ericliu`.
- `FAC-CRANE-ANNUAL`: November first workday, 14 calendar-day nags, done tokens including `已申購`, mention `@ericliu`. First due `2026-11-02`.
- `FAC-RUST-MONTHLY`: monthly rust prevention; first cycle `2026-10-01`; 3 workday nags; done when `facilities_lead` (`@ericliu` / user `mi8d7mp65frm9b9ox5a8azmeye`) posts a Case ID.

## Smoke-row done after auto-retire

- `FAC-SMOKE-*` rows are auto-retired after the first root post. The daily runner then `skip_inactive` and will not stamp `Last completed` from a later first-line `完成` / `done`.
- If a human still replies `完成`/`done` in that retired smoke thread, stamp `Last completed` and `Completed by` on the exact Task ID row without changing `Status` back to Active, and clear open-root/cycle cells. Do not reopen nags.

## Verification

1. Unit tests.
2. `--dry-run --date YYYY-MM-DD --json` against the live Sheet: today should be `no_op` unless a row is due; the due date should `open_root` without posting.
3. Read back the exact Task ID row after catalog writes.

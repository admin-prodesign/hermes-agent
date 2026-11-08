# Google Sheet date-driven reminder automations

Use this reference when building or reviewing reminder jobs whose due dates live in an editable Google Sheet, especially where users may change dates, formulas, column order, or statuses after reminders begin.

## Durable pattern

1. **Read the live Sheet on every run**
   - Do not rely on cached rows for reminder eligibility.
   - Read by an approved account/wrapper and log both no-op and reminder events.

2. **Resolve columns by header name, not column letter**
   - Build a header map from row 1 and fail loudly if required headers are missing.
   - This protects normal column reordering while preventing silent skips after accidental header deletion/rename.

3. **Separate eligibility from delivery dedupe**
   - Eligibility should be recomputed from the current row every run.
   - Dedupe keys should include the business object ID plus the effective due/review dates, not only the object ID.
   - For repeating reminders, include a repeat bucket/period in the key.

4. **Handle blank formula/output cells with fallback logic**
   - If a reminder-date formula/cell is blank but the source date exists, compute the effective reminder date from source date minus lead days.
   - Include a data-quality warning in the reminder/log so the Sheet can be fixed.

5. **Repeat overdue reminders until explicitly closed**
   - Do not let one sent/ignored reminder suppress the item forever.
   - Use a bounded interval such as weekly repeats while the row remains active and not closed/completed/inactive.
   - When posting the next reminder in the same thread, delete the previous bot reminder unless a human/non-bot reply landed after it.

6. **State key shape**
   - Good: `<item_id>|review=<review_date>|reminder=<effective_reminder_date>|bucket=<repeat_bucket>`
   - This means changing either review date or reminder date reopens reminder eligibility.

7. **Stop conditions**
   - Define explicit closed/inactive/completed tokens in both English and local language when applicable.
   - Keep reminders active until one of those tokens is present or the date moves forward.

8. **Verification before claiming reliability**
   - Dry-run current date: expect empty stdout/no-op when nothing is due, with a log receipt.
   - Fixture first due date: confirm the first reminder emits.
   - Fixture later date: confirm the repeat bucket emits.
   - Fixture changed date: confirm the state key changes and the reminder is eligible again.
   - Fixture blank reminder date + source date: confirm fallback date and data-quality warning.

## User-facing explanation pattern

For Mattermost/admin users asking “will reminders be missed if dates change?”, answer concisely with:

- the job schedule and delivery target,
- live Sheet read behavior,
- header-name column mapping,
- fallback reminder-date calculation,
- dedupe key contents,
- repeat interval and stop statuses,
- remaining infrastructure risk and optional watchdog.

Avoid over-claiming: date logic can be hardened, but infrastructure failures still need separate watchdog/canary coverage.

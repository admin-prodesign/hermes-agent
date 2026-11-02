# Google Sheets reminder automation verification

Use when a user asks whether a Google Sheet tracker is "wired", "sending reminders", or "automated" for due dates, renewals, follow-ups, or alerts.

## Core lesson
A `Reminder Date` / `Reminder Recipients` column only proves the Sheet can calculate reminder timing. It does **not** prove that any message/email/Chat/Mattermost reminder is automatically sent.

## Verification sequence
1. **Read the Sheet structure**
   - Confirm columns for due date, lead days, calculated reminder date, recipients, status, and any sent/log columns.
   - Prefer header-aware reads; do not assume fixed columns.
2. **Inspect Sheet-native automation**
   - Check for bound Apps Script projects, triggers, installable time triggers, and any script functions that send email/Chat/webhooks.
   - If using Apps Script, verify trigger metadata and source code names; do not infer from custom menus alone.
3. **Inspect external automation**
   - Check Hermes/OpenClaw cron/job registries, scripts, systemd timers, n8n workflows, or other declared producers for the spreadsheet ID/title and reminder terms.
   - Search for the spreadsheet ID, tracker title, and reminder/send keywords.
4. **Verify send evidence**
   - Look for a durable send log, sent timestamp column, cron output, Mattermost/Slack/Email send receipt, or automation run receipt.
   - If no receipt exists, say the send path is unverified even if the schedule formula exists.
5. **Answer with a status split**
   - `Reminder dates/recipients exist` vs. `Automatic sending is active/verified` vs. `Automatic sending not found/unverified`.

## Reporting pattern
Use concise language:

> The Sheet is wired for reminder-date tracking, but I do not see verified automatic reminder sending. To make it active, we need a daily/weekly job or Apps Script trigger that reads rows due for reminder, sends to approved recipients, and logs the send receipt.

## Master versus generated tabs

When a workbook has an editable master and generated year or month tabs:

1. Read the job entry point, not the sheet note. Confirm which tab the sender reads and which source the refresher uses.
2. If refresh uses a hardcoded list, or the sender reads only generated tabs, tell the user that master adds and owner changes do not sync until refresh reads the live master.
3. Preserve cycle status such as completed or not-applicable across refresh. Do not wipe those marks when regenerating dates or owners.
4. Mentions follow the Mattermost username column. Changing only the display name does not change the mention.
5. Skip a master row whose cutoff, anchor month, and note disagree, or whose anchor month is outside 1–12. Do not invent the missing month or day. Ask for one consistent day and one month, then generate.
6. A frequency rule means every occurrence in the years the user named. A single sample due date is not the schedule.

## Destination

Look up the exact channel or group before naming it as the reminder target. A nickname is not the department channel. Retargeting the sender is a new external send and stays on the approved channel until that change is approved and read back.

## Pitfalls
- Do not say "wired" or "active" just because formulas calculate dates.
- Do not rely only on wiki/source-page descriptions; verify live Sheet metadata and actual automation/job records when available.
- Do not quote a sheet note that says edits sync unless the job reads that tab.
- For Mattermost reminders, recipient/channel sends are external sends and require approved-user authorization plus a post-action receipt.
- For compliance/safety trackers, remind users that automation supports process follow-up but does not constitute regulatory validation.

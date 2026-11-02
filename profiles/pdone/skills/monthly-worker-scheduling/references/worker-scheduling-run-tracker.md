# Worker scheduling run tracker

Use this reference when migrating the monthly worker scheduling workflow away from Mattermost Playbooks, or whenever a live monthly scheduling run may span multiple turns, gateway restarts, or long solver/writeback operations.

## Core distinction

The internal playbook/runbook is the **procedure**. It tells PD One what order to do things in and what safety checks apply.

A run tracker is the **state of one scheduling month**. Do not rely on active session memory, compacted context, or Mattermost Playbooks run state as the only tracker. Those are fragile during long solver runs, interruptions, and context compaction.

## Implemented tracker location

Use the `排班流程追蹤 Tracker` tab in the live worker schedule spreadsheet:

- Spreadsheet: `良器-成型部-排班表 Injection Molding Shift Schedule`
- Spreadsheet ID: `10DU9Yro5tDacrjBlOfuGE9JCcYFkC7ribJKuaxnRWhE`
- Tab gid: `749037439`
- URL: `https://docs.google.com/spreadsheets/d/10DU9Yro5tDacrjBlOfuGE9JCcYFkC7ribJKuaxnRWhE/edit#gid=749037439`

At the start of each monthly run, locate or create rows in this tab for the target month before doing long solver/writeback work.

## Recommended durable tracker fields

Create one row per target scheduling month/run step, with linked receipt/output rows when needed:

- target scheduling month
- Mattermost thread/root link
- required rest days
- total working hours
- Anna/monthly constants checked
- worker schedule tabs created/verified
- source `申請日期-當月統計` controls aligned (`A2`, `A4`, `A10`, `AV`)
- raw `原資料` request audit status
- flagged raw request rows and decision state
- annual employee trip checkpoint state
- manager rotation checkpoint state
- operator day/night swap and headcount-balance checkpoint state
- inventory-day / 5S skeleton-crew checkpoint state
- exception workers checked (`諾威 | NOGALES NOEL MANGALIMAN`, `黃俊中`)
- source rollover / AP:AT mapping status
- protected leave (`喪`) verification status
- per-group preview status and output directory: `day`, `night`, `manager_day`, `manager_night`
- per-group writeback status, timestamp, output directory, and receipt path
- known manual exceptions / rows not to overwrite
- HR MAX export generated/verified
- HR MAX import accepted
- schedule announced
- `原資料!AD` closeout dry-run count
- `原資料!AD` closeout write/readback receipt
- final archive/retrospective notes

## Operating rule

At the start of each monthly run, PD One should create or locate the tracker row and post/link the Mattermost thread. After every material step, update the durable tracker or create a receipt path before relying on chat summary.

If a batch update past the last Tracker grid row returns a grid-limit error, append with `INSERT_ROWS` instead. Read back the returned `updatedRange`. Do not claim the tracker row exists until that readback matches.

For each long-running tool action, record enough to recover after interruption:

- action/group
- dry-run vs live write
- max solver/no-improvement limits
- output directory
- result status
- failures/mismatches
- whether a live write occurred

## Migration-away note

Mattermost Playbooks previously provided checklist state, run summary, assignees, and status reminders. The replacement should keep those behaviors in the tracker + Mattermost thread + PD One reminders, not in session memory.

# AppSheet stale Case analysis pattern

Use this PD One/AppSheet admin pattern when asked to identify stale AppSheet `Case` records: cases created or deadlined long ago with little/no activity.

## Source of truth and access

- Schema/design source: OpenClaw workspace AppSheet corpus, especially:
  - `/home/prodesign/.openclaw/workspace/docs/runbooks/appsheet-agent-rules.md`
  - `/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/SKILL.md`
  - `/home/prodesign/.openclaw/workspace/projects/AppSheet/appsheet_schema_index.json`
  - `/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/references/prodesign-schema-map.json`
- Data-pull source: prototype/data-access app by default via:
  - `/home/prodesign/.openclaw/workspace/projects/AppSheet/keydrop/prototype-app.env`
- Do not print access keys. Do not write/edit AppSheet rows for this analysis unless separately requested and explicitly confirmed.

## Tables to pull

Use `AppSheetClient.find()` from `/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/scripts/appsheet_record_ops.py` or the lightweight table probe.

Recommended read set:

```python
from appsheet_record_ops import AppSheetClient
client = AppSheetClient('/home/prodesign/.openclaw/workspace/projects/AppSheet/keydrop/prototype-app.env')
case_rows = client.find('Case', 'Filter(Case, true)')
updates = client.find('Case_Updates', 'Filter(Case_Updates, true)')
case_attachments = client.find('Case_Attachments', 'Filter(Case_Attachments, true)')
update_attachments = client.find('Case_Updates_Attachments', 'Filter(Case_Updates_Attachments, true)')
employees = client.find('HR_Employees', 'Filter(HR_Employees, true)')
```

## Activity calculation

For each `Case[CaseID]`, compute last activity as the maximum available timestamp among:

- `Case[Last Updated]`
- latest `Case_Updates[Timestamp]` where `Case_Updates[CaseID] = Case[CaseID]`
- latest `Case_Attachments[Timestamp]` where `Case_Attachments[CaseID] = Case[CaseID]`

`Case_Updates_Attachments` may be pulled for completeness/evidence, but it normally requires joining through `Case_Updates[CaseUpdateID]` before it can affect a parent case's activity.

## Terminal statuses

Exclude terminal cases from stale flagging unless the user explicitly asks for closed/completed anomalies:

- `Completed`
- `Closed`
- `Cancelled` / `Canceled`
- `Resolved`
- `Done`
- `Archived`

Treat these as open/non-terminal in current Pro-Design data unless told otherwise:

- `Not Started`
- `In Progress`
- `On Hold`
- `Needs Review`
- `Pending Summary`
- `Status_WaitingForResponse`

## Suggested scoring heuristic

Score only open/non-terminal cases. Useful default thresholds:

- `very stale`: score >= 95
- `stale`: score >= 70
- `watch`: score >= 50

Inputs:

- inactive days: strongest signal (`>=60`, `>=90`, `>=120`, `>=180`)
- overdue deadline age (`Case[Deadline] < today` and no completion date)
- created age (`Case[Created On]`)
- no or sparse `Case_Updates`

Reason strings should be explicit, e.g. `no activity 180d`, `deadline overdue 90d`, `created 120d ago`, `no Case_Updates`, `only 1 update(s)`.

## Output shape

Write artifacts under `/home/prodesign/.openclaw/workspace/projects/AppSheet/exports/`:

- `stale-cases-report-<timestamp>.md`
- `stale-cases-analysis-<timestamp>.csv`
- `stale-cases-analysis-<timestamp>.json`
- optional full pulled table snapshots for auditability

Report summary should include:

- pull time and app/source used
- row counts by table
- total cases, open/non-terminal count, flagged counts by bucket
- status/type/responsible-person breakdowns
- top flagged cases table with `Bucket`, `Score`, `CaseID`, `Status`, `Inactive days`, `Deadline`, `Update Count`, `Responsible`, `Title`, and `Reasons`

Final chat response should be concise and attach/link the generated report plus CSV. Say explicitly that AppSheet was not modified.

## Human review batches

When Andy asks to review very stale cases, present them in batches of 10 unless he asks for a different page size. Include enough context for fast decisions:

- ordinal within the current batch
- `CaseID`
- current `Status`
- Chinese/source `Title`
- English description
- responsible person display label
- inactive days, deadline, update count

English description rule:

1. Prefer `Case[Description_en]` if populated.
2. If `Description_en` is blank, use `Title_en` if it is already acceptable and not obviously machine-garbled.
3. For Chinese-only or awkward/missing English content, delegate a bounded language transformation to `utility-agent` when available. Prompt it to translate only the provided case text into concise, accurate English, preserving product/mold/process codes and dates and not adding facts.
4. If `utility-agent` cannot be spawned in the active environment, say so only if necessary and use a bounded fallback translation path rather than blocking the review.

Avoid dumping the full CSV during review. Keep each batch readable and wait for Andy's decisions such as `cancel 1-10`, `cancel 1,2,5`, `keep 6`, or `next`.

## Canceling stale cases by Case Update

If Andy explicitly instructs cancellation during stale-case review, do not directly edit the parent `Case` status by default. Instead, add a `Case_Updates` row so AppSheet's normal bots/status-sync logic can update the parent `Case`.

Default cancellation Case Update payload shape:

- table: `Case_Updates`
- `CaseID`: target case key
- `Created By`: Andy Lin's AppSheet `PersonID` (resolve/verify from `HR_Employees`; do not guess if not already known from current data)
- `Update Summary`: `Reviewed as stale. Canceled.`
- `Update Description`: `Reviewed as stale. Canceled.`
- `New Status`: `Canceled`
- include other required fields from schema/app conventions as needed, such as `CaseUpdateID`, `Timestamp`, `Case Type`, or `Updater`

Safety sequence:

1. Resolve Andy Lin in `HR_Employees` and verify the `PersonID` used for `Created By`.
2. Re-read the target cases before writing to ensure they are still non-terminal and the user-selected ordinals still map to the intended `CaseID`s.
3. Dry-run/show the exact rows to be added and get explicit confirmation for AppSheet writes unless the immediately preceding user instruction clearly authorizes the specific selected cancellation batch.
4. Execute the `Case_Updates` adds through the approved AppSheet record-operation/API path.
5. Verify each new `Case_Updates` row by `CaseUpdateID` or selector.
6. Re-read the parent `Case` rows after a short wait or follow-up check and report whether AppSheet bots changed `Case[Status]` to `Canceled`; if not yet updated, report the added update rows and that parent sync is pending/not observed.
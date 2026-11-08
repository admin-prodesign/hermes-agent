# Mold repair records on Case

Use this when digitizing mold repair orders into the shared Case app. Do not reopen the parent choice or flatten repeating work back onto Case.

## Parent

`Case` with `Type = "Mold Repair"` is the repair order. An ActivityLog incident may create it. `Case_Updates` is handoff only (assign, wait, review). It is not the work log.

Reuse existing Case fields: `Title`, `Description` (the problem, not the cause), `Deadline`, `Completion Date`, `Created By`, `Next Step Responsible Person`, `Equipment`, `Molds`, `Products`, `Parent ActivityLogID`, `Case_Attachments`, `Case_Updates`.

Before the first Mold Repair Case can save, make `Sub-Type` required only when that type needs a sub-type. The column is required on every Case, and the Mold Repair lookup says no sub-type is required.

Do not add a hand-typed in-house/vendor flag, a T number, repair-type columns 1–6, drop/mount dates, vendor, cost, or trial result on Case. Do not add a `Case_Updates`-style cache list on day one. Use normal related lists until volume proves a cache is needed.

Case additions, shown only when `[Type] = "Mold Repair"`. Display names go through Lookup. Do not clone `_en` / `_zh-tw` twins for these fields.

| Column | Type | Rule |
|---|---|---|
| `Mold Repair Order Number` | Text | Required for this type. Generate `送YYYYMMDD-NN`. Do not free-type. |
| `Cause` | LongText | 原因判定. Not `Description`. |
| `Countermeasure` | LongText | 維修對策. |
| `Urgent` | Yes/No | Ticket flag only. Not a schedule date. |
| `Difficulty` | Enum | Lookup. Do not invent values from a blank sheet sample. |
| `Estimated Hours` | Number | Order estimate. Actual hours stay on the action. |
| `Sample Attached` | Yes/No | See the form contract below. |
| `Mold Repair Result` | Enum | `OK` / `NG` / `N/A`. Trial OK/NG is not this column. |
| `Mold Repair Result Note` | LongText | |

## Own tables

| Table | Link | One row is |
|---|---|---|
| `MoldRepair_Action` | Required Ref to Case | One in-house work session: who, when, actual hours, repair-type list, what was done, understood-countermeasure. |
| `MoldRepair_Action_Items` | Required Ref to the action | One checklist mark. Yes / No / N/A plus note. Not Yes/No columns on the action. |
| `MoldRepair_Items` | Catalog | ISO line, repair type, sort, active. Seed from the issued form page 3. Do not borrow `Maintenance_Items` unless a line-by-line match is confirmed. Do not reuse `Maintenance_Session_Items`. |
| `MoldRepair_OutsideService` | Required Ref to Case. Optional Ref to the action. | One job that leaves the shop (weld, CNC, EDM). Zero or more per Case. |
| `Mold_Test` | Optional Ref to Case | One trial. QA, RD, and mold repair write the same table. A trial may have no Case. Sequence 1/2/3 is T1/T2/T3. Do not store `T_` on Case. |

Outside-service rows hold service type, vendor from the existing vendor list, sent / expected return / actual return, status, result, optional quote note, and a few images. Quote, invoice, and write-off stay on the vendor accounting sheet. Link later. Do not make technicians fill 核銷 on this row.

First-article inspection stays on ActivityLog. A trial may link to it. Do not replace it. Do not add a second ActivityLog repair record or a third parent table.

## Open-form contract

`AL_Open_MoldRepair_Form` opens `Case_MoldRepair_Form` with `LINKTOFORM` on a `NAVIGATE_APP` action.

- `Next Step Responsible Person` opens blank. The action must not pass a person into that column. Blank is allowed only when `[Type] = "Mold Repair"`. Do not clear the requirement for other case types.
- Hide translation twins only on `Case_MoldRepair_Form`: `Title_en`, `Title_zh-tw`, `Description_en`, `Description_zh-tw`, `Cause_en`, `Cause_zh-tw`, `Countermeasure_en`, `Countermeasure_zh-tw`, `Mold_Repair_Result_Note_en`, `Mold_Repair_Result_Note_zh-tw`. Do not delete them and do not hide them on other Case forms.
- `Sample Attached` display name is **Physical Sample Provided** / **已提供實體樣品**. Required only when `[Type] = "Mold Repair"`. The user must choose Yes or No.
- Show `Case_Attachments` on the form so the user can add images. `LINKTOFORM` cannot copy incident attachment rows before the Case key exists. If `Parent ActivityLogID` is an Enum, the form cannot dereference those image files. Copy them after save, once the Case key exists.

## Status

`Case.Status` keeps only Lookup rows where `Active` is true, `Category` contains `Status`, and `Sub-Category` contains the Case `Type`. Shared rows such as `Not Started`, `In Progress`, and `Completed` are scoped to other types. They do not appear for `Mold Repair`.

Add new Lookup rows. Do not widen another type's `Sub-Category` list. `LookupID` is the value Case stores. `Row ID` is a separate unique token. Do not reuse the type key `Mold Repair` as a status key.

Required Mold Repair statuses:

- `Pending` — one NG from Injection Molding, QA, or R&D returns the Case here. Do not wait for the other two.
- `Completed, Awaiting Manager Final Check` — mold repair manager. Use this only after the required trials on the latest attempt are all OK.
- `Completed, Needs Final Senior Mgmt Review` — present in Lookup, unused.

Lookup sheet `12VYax7QqWjl6WrmNKdNNPAe4dRgn508KPg9rZ1nu0yc`, tab `Lookup`: A `Row ID`, B `LookupID`, C `Active`, D `en`, E `zh-tw`, F `Sort Order`, M `Category`, N `Sub-Category`. Column O is `Sub-Category 2`. Do not search O for the type scope.

If a Lookup table probe returns 0 rows, read that sheet. Do not treat 0 as absence.

## Attempt and trial link

One `MoldRepair_Action` row is one attempt. Store the attempt number on that row. Do not store `T_` on Case. Generate one `MoldRepair_Action_Items` set for that attempt, not one set for the whole Case.

Each `Mold_Test` row links to that action and, when the trial belongs to an order, to the Case. Trial OK/NG stays on `Mold_Test`. It is not `Mold Repair Result`.

Before writing `Department`, read the live `Mold_Test.Department` enum. Do not assume `Injection Molding` is already a value.

## Trial status bots

One NG trial must set the parent Case to `Pending`. The latest attempt must set `Completed, Awaiting Manager Final Check` only when Injection Molding, QA, and RD are all OK and that attempt has no NG. Do not store that rule on Case.

Stable bots: `MR_Test_NG_SetPending` and `MR_Test_AllOK_SetManagerCheck`. They call `MR_Case_SetPending` and `MR_Case_SetManagerCheck`. A raw Case `Edit` can fail with `ChangeImage does not contain column number 55`. Use the status action, not a raw edit.

The event table and the process input table must both be `Mold_Test`. The process step must run the `Mold_Test` ref action (`MR_Test_SetCasePending` or `MR_Test_SetCaseManagerCheck`). Do not set the process input to `Case`, and do not put `MR_Case_SetPending` or `MR_Case_SetManagerCheck` directly in that process. AppSheet then reports `Action '...' cannot be used in this process` and `The table of event and the input of the process must be the same`. Those are severity-0 errors. They set `IsRunnable` false while `IsValid` can stay true. Do not promote that version. Users run the stable version when percent-on-latest is 0, so the deployed app does not launch even though the editor still opens. The ref action already calls the Case status action with `LIST([CaseID])`.

To repair a process whose input is `Case`, change only `InputSchemaName` to the `Mold_Test` schema and keep the step action on `Mold_Test`. A save regenerates the process state-table columns from the new input schema. Do not hand-rebuild those columns first. After reload, require the step `ActionName` to be the `Mold_Test` ref action, `InputSchemaName` to be the `Mold_Test` schema, and `IsRunnable` true before promotion.

`EnableAutomationTriggers` is false. An API add or edit does not run these bots. Do not turn that flag on for a test. An in-app save is the proof path.

## Home list

A Home list belongs to one menu group. `LookupID` is the key, and `LINKTOVIEW` uses that key as the view name. One Lookup row cannot appear in both `Menu_MoldRepair` and `Menu_Molding`.

To show the same mold-repair case list in both groups, keep `Case_MoldRepair_All` under `Menu_MoldRepair` and add a second table view plus a second Lookup row under `Menu_Molding`. Point both views at slice `Case_MoldRepair_All`. Give both rows the same viewable roles: `Team_MoldRepair_Technicians`, `Team_Molding_Staff`, `Team_SeniorStaff`, `Case_Admin`, and `Case_Manager`. Do not put the second row on the first view name.

## Overlapping requests

Do not merge a later mold-repair request by editing `Description`, and do not make it a subcase that the technician must open. `Parent Case ID` can be set by a bot, but `Sub-Cases` still hides each ask, and `MoldRepair_Action[CaseID]` points at one Case.

Keep Case as the work package. A new request is its own line on that package. The requester enters the mold, the problem, and the photos. The requester does not search for an existing order.

Match only when both sides have exactly one mold. If an open Mold Repair Case for that mold has not started, attach the new line to it. Not started means no `MoldRepair_Action` row, no sent outside-service row, and `Status` is still the first open status. Assignment alone is not started. If that Case has started, or no open Case exists, create a new Case and attach the line there.

Show every request line on the Case form. Do not overwrite `Description`.

When several open Cases exist for one mold, group them by mold on the technician list and show each request line there. One repair record may be checked onto other open Cases for that same mold. Do not apply it to every open Case automatically. A later request may be a different issue.

## Physical sheets

`Mold_Test`, `MoldRepair_Action`, and `MoldRepair_Action_Items` are tabs on `1qPT4Ongw7v5vB1ZhJPIjDzC8OGOsVBsgmiEC0XV19iY`. Read the live header before adding a column. Append the new header at the end. Do not insert it between existing headers. Do not append the header until the schema save can run in the same flow.

## Live proof script

Pick a recent completed schedule row with trial `OK` and `結案`. Exclude `換模仁`, `清水路`, and `保養-大`. Do not use the newest rows when they are still open. Join `模具送修清單` by `模修單號` for photos and applicant fields. Do not write `模具維修明細表`.

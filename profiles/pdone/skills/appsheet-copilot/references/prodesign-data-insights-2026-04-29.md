# Pro-Design AppSheet Data Insights — 2026-04-29

Purpose: aggregate-only insights from already collected AppSheet data. Use this to understand operational adoption and data quality before proposing AppSheet design changes. Avoid exposing row-level/private records from this file.

Evidence:
- Aggregate export: `projects/AppSheet/exports/appsheet-data-insights-aggregate.json`
- AppSheet API full-table aggregate pass generated `20260429T132405Z`.
- Data pulls were run through the prototype app API/env (`projects/AppSheet/keydrop/prototype-app.env`, `app_id=3d6f2d39-9f45-488a-9f5d-6a931d83bd63`).
- If a user-facing AppSheet link is needed for any row referenced from this analysis, build the link with the deployed app (`app_id=f2073120-8c2e-4930-b13c-105838c5e4c3`).
- `ProcessingQueue` and `Customer_Details` returned empty AppSheet API bodies for full-table selectors; verify with narrower selectors before drawing conclusions from those two tables.

## High-level volume signals

Largest collected tables in the aggregate pass:

| Table | Rows | What it suggests |
|---|---:|---|
| `ActivityLog_Attachments` | 46,825 | The app is heavily evidence/photo driven. |
| `Maintenance_Session_Items` | 25,440 | Forklift maintenance/checklist execution is mature and high-volume. |
| `ActivityLog` | 23,077 | Activity/incident/event logging is the main operational history. |
| `ActivityLog_Session_Items` | 4,073 | Structured per-item activity/check data exists beyond parent logs. |
| `ERP_Data_Combined` | 1,962 | ERP product/mold/equipment catalog is substantially mirrored. |
| `Maintenance_Sessions` | 1,814 | Maintenance sessions are regularly used. |
| `Case_Updates` | 1,329 | Case-update history exists, especially legacy/imported Tech Dev and IT work. |
| `HR_Employees` | 1,045 | Employee master data includes historical and inactive people, not just current users. |
| `HR_Employees_PerformanceRecords` | 846 | Performance-point records are already captured from ActivityLog-linked events. |
| `Lookup` | 781 | Controlled vocabulary is broad and central. |
| `Reference_Documents` | 293 | SOP/SIP/reference document mapping is significant. |

## Operational insights

### 1. ActivityLog is the real operational event warehouse

`ActivityLog` has 23,077 rows. Major categories:
- `5S Action`: 8,087
- `Mold Movement`: 6,185
- `Incident Report`: 3,828
- `Machine Parameters`: 2,279
- `First Article Inspection`: 1,506
- `NG_Product_Weight`: 767
- `Entry_Exit_Record`: 399

Interpretation:
- The app is not only an incident system; it is also a production-floor evidence system for 5S, mold movement, machine setup, inspection, weight checks, and entry/exit records.
- Incident reporting is large but not dominant; the largest data volume is routine operational logging.
- Future analytics should treat `ActivityLog[Category]` as the top-level business lens, not assume every row is an incident.

Data richness in `ActivityLog`:
- 75.4% have a description.
- 81.0% have a thumbnail.
- 62.9% reference equipment.
- 59.0% reference molds.
- 19.5% reference products.
- 19.4% reference reference documents.
- 12.6% include troubleshooting actions.

Interpretation:
- Equipment/mold linkage is strong enough for asset-centric analysis.
- Product linkage is present but less universal, so product-level analytics need category-specific expectations.
- Troubleshooting is sparse compared with descriptions; if management wants better corrective-action analytics, the form/process should nudge for structured troubleshooting on incident-like categories.

ActivityLog is concentrated in factory-facing departments:
- `成型一課`: 6,586
- `成型二課`: 6,167
- `品保部`: 5,123
- `資材部`: 2,283
- `模修課`: 866
- `機修廠務課`: 837

Interpretation:
- Molding and QA are the strongest adopters/users of the logging model.
- Any redesign should protect speed and mobile usability for these teams first.

### 2. Evidence capture is very mature

`ActivityLog_Attachments` has 46,825 rows against 23,077 ActivityLog rows, about 2.03 attachments per log.
- 46,820 attachment rows have images.
- Only 6 have files.
- 15,683 parent ActivityLog rows have attachments.

Top attachment types include:
- `Other_Attachment`: 17,881
- `5S_Before`: 3,386
- `5S_After`: 3,298
- First article inspection / cross-section / quality defect photos
- Multiple machine-parameter photo categories

Interpretation:
- The app is already a visual evidence repository.
- Image-based workflows are core; file/document attachment is rare in ActivityLog.
- `Other_Attachment` is very large, which suggests either useful flexibility or an opportunity to tighten attachment categories for better analytics.

### 3. Maintenance is currently dominated by forklift maintenance

Maintenance data:
- `Maintenance_Sessions`: 1,814 rows
- `Maintenance_Session_Items`: 25,440 rows
- About 14.0 checklist items per maintenance session.
- All visible sessions are `Maintenance_Forklift`.

Session status distribution:
- `Nominal`: 1,342 / 74.0%
- `Caution`: 196 / 10.8%
- `NG`: 172 / 9.5%
- `Not Completed`: 104 / 5.7%

Item status distribution:
- `Nominal`: 20,253 / 79.6%
- `Caution`: 2,437 / 9.6%
- `NG`: 268 / 1.1%
- `Not Applicable`: 39 / 0.2%

Only 17 maintenance item rows have abnormal descriptions, and only 1 has a resolution description.

Interpretation:
- Forklift maintenance is operationalized well as a checklist workflow.
- Session-level NG/Caution is much higher than item-level NG, suggesting caution/NG may be surfaced at session summary level even when specific item resolution notes are sparse.
- If the goal is maintenance analytics, the next improvement is not more structure in the session shell; it is better abnormal/resolution capture when items are Caution/NG.
- Maintenance expansion to molds/equipment exists structurally, but the collected data indicates forklift is the currently mature live use case.

### 4. Case workflow is much larger after removing the prototype security filter

Correction after Andy removed the prototype `Case` security filter and saved the app: `Case` now pulls correctly through the prototype app.

Evidence from `projects/AppSheet/exports/case-data-refresh-2026-04-29.json`:
- `Case`: 648 rows
- `Case_Updates`: 1,329 rows
- `Case_Attachments`: 165 rows
- `Case_Updates_Attachments`: 188 rows

`Case` type distribution:
- `Tech Dev Case`: 489
- `IT Ticket`: 110
- `Facilities Repair`: 37
- `Case_Quality`: 12

`Case` status distribution:
- `Completed`: 344
- `Not Started`: 157
- `In Progress`: 87
- `Needs Review`: 40
- `On Hold`: 9
- `Canceled`: 7
- `Status_WaitingForResponse`: 2
- `Pending Summary`: 2

Other signals:
- Approximate active/open cases: 297
- Completed cases: 344
- Case IDs with updates: 430
- Case IDs without updates: 218
- Update IDs without a parent `Case`: 0 after the filter fix
- CaseID formats still show both newer canonical IDs and legacy/migrated IDs: 539 `C-...` IDs and 109 numeric/serial-style legacy IDs.
- All 648 parent case rows have Mattermost links.
- 595 cases have deadlines; 371 have completion dates.
- 341 cases reference molds; 31 reference products; 17 reference equipment; 9 reference parent ActivityLog rows.

Top subtypes:
- `SIP Update`: 275
- `Molding_Project_for_KPI`: 59
- `Project`: 54
- `Appsheet`: 35
- `Facilities_Repair_Case`: 32
- `Design Change`: 28
- `New Mold`: 26
- `Other_IT`: 25

Interpretation:
- Case workflow is a major operational dataset, not a small current-only pilot.
- Tech Dev dominates case volume, but IT and Facilities are also significant.
- Mattermost linkage is universal in the parent `Case` rows, so case work is deeply tied to collaboration threads.
- The security filter was the reason earlier pulls undercounted `Case`; future aggregate pulls should verify the prototype app's security-filter context when counts look suspicious.

### 5. ERP mirror is product-heavy and mold-linked

`ERP_Data_Combined` has 1,962 rows:
- Product: 1,475 / 75.2%
- Mold: 300 / 15.3%
- Equipment: 187 / 9.5%

Other signals:
- 1,447 rows have mold numbers.
- 1,822 rows have cavity counts.
- 854 rows have cached related reference documents.
- 149 rows have latest mold movement.
- Quality status is mostly standard: 1,876 `S:標準`, 86 `X:廢棄`.

Interpretation:
- The ERP mirror is strong enough to power product/mold/equipment references in operational forms.
- The unusually high cavity-count coverage means mold/product manufacturing metadata is deeply embedded, not just names.
- Latest mold movement is present but much smaller; mold movement analytics may need to combine ERP fields with `ActivityLog` mold-movement rows.

### 6. Reference documents are mostly SOP/SIP and strongly product/mold-linked

`Reference_Documents` has 293 rows:
- `RefDoc_SOP`: 133
- `RefDoc_SIP`: 94
- `RefDoc_Mold_Connections`: 23
- `RefDoc_InjectionMolding_StandardSettings`: 23
- `RefDoc_Mold_CoolingChannelDesign`: 17

Coverage:
- 279 active, 12 inactive.
- 293 have URLs.
- 263 have files.
- 287 reference molds.
- 263 reference products.
- 46 have images.

Interpretation:
- The app has a meaningful controlled-document layer connected to manufacturing assets/products.
- The document corpus is suitable for asset/product-contextual help inside AppSheet.
- Since nearly all reference docs have URLs and most have files, future UX should prioritize quick lookup and contextual surfacing rather than simply collecting more docs.

### 7. HR data is mostly historical, but app access is smaller and controlled

`HR_Employees` has 1,045 rows:
- `Not Employed`: 909
- `Employed`: 132
- `Shared_User_Account`: 2
- `Unpaid Leave of Absence`: 1
- `Special_User_Account`: 1

Access/signals:
- 161 rows have AppSheet email.
- 38 rows have company email.
- 133 rows have `ALL_CHANGES`; 912 are `READ_ONLY`.
- Language is mostly `zh-tw` with a smaller `en` population.
- Top app roles include `IT_User`, `All_User`, `ActivityLog_5S_Submitter`, `Customer_Viewer`, `5S_Points_Viewer`, `Dashboard_User`, `RefDoc_User`, and `Maintenance_User`.

Interpretation:
- HR_Employees is a historical/person master, not just active app users.
- Current AppSheet write access appears intentionally limited compared with total people represented.
- Designs should avoid assuming every `HR_Employees` row is a current user or employee.

### 8. Inventory/sample retention is embryonic

`Inventory_Mgmt` has 1 row and `Inventory_WithdrawalRecord` was queried but has little/no visible volume in this pass.

Interpretation:
- The schema exists for sample retention, but collected data indicates it is not yet a mature workflow.
- If sample retention matters operationally, this is a good candidate for focused UX/process work.

### 9. Translation/queue data needs narrower verification

The aggregate pass found only 6 visible `GoogleTranslate` rows, and full-table selectors for `ProcessingQueue` returned an empty body.

Interpretation:
- This does not necessarily mean translation/queue infrastructure is unused; queue tables may be cleaned frequently, filtered, or too sensitive/expensive for full-table API reads.
- For runtime/queue debugging, use fresh targeted selectors and AppSheet export logs rather than this aggregate snapshot.

## Practical design implications

- Treat `ActivityLog` as the operational event warehouse and design category-specific analytics around it.
- Protect photo-first mobile capture; images are one of the app's strongest existing data assets.
- Improve structured follow-up capture where current data is sparse: troubleshooting actions, maintenance abnormal/resolution descriptions, and categorized attachments instead of broad `Other_Attachment`.
- Do not judge case workflow health from the current `Case` table alone; reconcile parent case visibility with the much larger `Case_Updates` history.
- Use ERP/reference-document links for contextual help: the data is already there for product/mold/SOP/SIP surfacing.
- Treat inventory/sample retention as a promising but early-stage workflow, not an established mature process.

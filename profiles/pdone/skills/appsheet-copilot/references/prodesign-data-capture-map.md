# Pro-Design AppSheet Data-Capture Map

Purpose: describe what kind of operational data the Pro-Design AppSheet app captures, beyond table/column structure. Use this before AppSheet design advice so proposed forms, automations, and lookups fit the existing business vocabulary.

Evidence used:
- Synced deployed-app definition: `projects/AppSheet/appsheet_definition.json` (`generated_at_utc=20260428T164952Z`, app `f2073120-8c2e-4930-b13c-105838c5e4c3`) for schema/structure.
- Prototype app data pulls via `projects/AppSheet/keydrop/prototype-app.env` (`app_id=3d6f2d39-9f45-488a-9f5d-6a931d83bd63`) for row evidence.
- Bounded AppSheet API probes run against every table with `TOP(FILTER("<table>", TRUE), 5)` for field presence only.
- Full `Lookup` table read: 781 rows. Do not preserve row-level private data here; this is a semantic map only.

## 1. Lookup table: app vocabulary, translations, menus, permissions

`Lookup` is not just a small dropdown table. It is the central controlled vocabulary and localization layer for the app.

Core fields:
- `LookupID`: stable token used by expressions, enum values, display names, roles, menus, and status logic.
- `Active`: soft-enable flag for vocabulary rows.
- `en`, `zh-tw`: bilingual labels.
- `Description_en`, `Description_zh-tw`: bilingual explanatory text.
- `Category`, `Sub-Category`, `Sub-Category 2`, `Sub-Category 3`: multi-level semantic grouping.
- `Sort Order`: order for statuses, menus, views, and other UI lists.
- `IntervalDays`, `Standard_Lead_Time_Days`: cadence/lead-time metadata for maintenance, review, and case behavior.
- `Viewable Roles`, `Editable Roles`, `Notification Group`, `Initial Next Step Responsible Person`, `Reviewer`: access, routing, responsibility, and notification metadata.
- Virtual fields `Translation`, `Description Translation`, `Status (Sorted)`, `View Category (Sorted)`, `RowCount_Realtime`: current-user-language rendering and UI helpers.

Observed category distribution in `Lookup`:

| Category | Rows | Meaning |
|---|---:|---|
| `Type` | 238 | Business/domain types used by `ActivityLog`, `Case`, attachments, maintenance, reference docs, equipment/products, incident reports, IT tickets, quality cases, mold movements, injection parameters, etc. |
| `Columns` | 219 | Column display-name/translation dictionary. Many AppSheet display names use `LOOKUP("Column Name", "Lookup", "LookupID", "Translation")`. |
| `Views` | 126 | App view definitions/menu entries and access metadata. Frequently grouped under `Menu_*`. |
| `Translation` | 70 | General interface/action/category labels such as Home, Status, Images, Attachment, Done, Add. |
| `Appsheet Role` | 40 | App roles and permission groups such as IT/HR/Case/ActivityLog roles. |
| `Status` | 26 | Workflow statuses for cases, maintenance, incident reports, employment status, ECRN, mold movement, etc. |
| `Notification Group` | 26 | Notification audience/team group tokens. |
| `Menu` | 18 | Navigation/menu buckets for departments and modules. |
| `Dashboard` | 9 | Dashboard variants by audience/role. |
| `Sub-Category` | 4 | Secondary category labels including 5S, Leave, contract-days-left categories. |
| `Module` | 3 | Top-level modules: `ActivityLog`, `Case`, `Maintenance`. |
| `Risk` | 3 | Risk severity values. |
| `Language` | 2 | `zh-tw`, `en`. |
| `Department` | 2 | Department lookup tokens. |

Lookup design implications:
- Treat `LookupID` values as canonical system tokens; never translate them by guesswork.
- Add new dropdown/status/menu vocabulary in `Lookup` first when the value is reused, translated, permissioned, sorted, routed, or shown in multiple places.
- Use `Category`/`Sub-Category*` to scope enum choices instead of hard-coding broad `Lookup[LookupID]` scans.
- When adding workflow statuses, include `Sort Order`, bilingual labels, and the relevant subcategory (for example case type/status family).
- When adding visible modules/views, check `Viewable Roles`, `Menu_*`, `Dashboard_*`, and row-count behavior.
- When translating field names or labels, prefer existing `Columns`/`Translation` rows over direct literal text.

## 2. Major data domains captured

### People, HR, identity, access, and employee lifecycle

Tables:
- `HR_Employees`: master employee/person records. Captures `PersonID`, employee ID, Chinese/English/pinyin/nickname names, email/account fields, photos, BU, job level/title, language preference, employment status, join/separation dates, managers/recommenders, transport/license info, AppSheet roles, notification groups, dashboard/data-access modes, annual-review metadata, birthday/age, and generated display labels.
- `HRS_Data`: imported HR system records. Captures employee number/name, passport/English names, entry/exit/residency dates, department/job/grade/category, employment status, hire/separation/leave/reinstatement dates, seniority dates, and HR MAX import identifiers.
- `HRS_Data_MasterNames`: compact HR/person lookup used for names, AppSheet email, BU, operator code, job level, notification group, managers, and review stages.
- `HR_Employees_AppSheet_Settings`: per-user app settings and permissions. Captures language, team members, dashboard type, data access mode, allowed views/navigation/menu items, roles, notification group, data retention windows by module, and boolean capability flags.
- `HR_Employees_NotesAttachments`: employee-related documents/notes. Captures attachment IDs, target `PersonID`, creator, category, title/description translations, files/images/links, contract/validity dates, and processed flags.
- `HR_Employees_PerformanceRecords`: performance-point/bonus adjustment records tied to `ActivityLogID` and `PersonID`, including role/category/points/bonus percentage.
- `GoogleForm_SuddenAbsenceRequests` and `SuddenAbsenceRequests`: sudden-leave submissions. Capture multilingual Google Form fields, submitter/email/name/department, requested leave date, reason, translation IDs/translated reason, comments, notification-sent flag, and year.

Design notes:
- Resolve people by `HR_Employees[PersonID]`, not names, whenever possible.
- For bilingual name display, use `Name_ZH`, `Name_EN`, `Name_ZH_EN`, or `Name_PINYIN` from HR tables; do not machine-translate names.
- User permissions and language-dependent behavior usually flow through `Current User` / `HR_Employees_AppSheet_Settings` plus `Lookup` roles.

### Activity logging, incident reports, checks, and operational events

Tables:
- `ActivityLog`: central event/incident/report table. Captures timestamp/shift/month, BU, creator, category/subcategory hierarchy, related equipment/molds/employees/products/customers, thumbnail, description and troubleshooting actions with bilingual translations, risk, notification groups, status, Mattermost/other links, reference documents, performance-point flags, labels, flags, and related attachments/items.
- `ActivityLog_Attachments`: photos/files/instructions for an activity log, including type, creator, category, description translations, thumbnail selection, translation/thumbnail processing status, retry count, and last error.
- `ActivityLog_Items`: reusable checklist/report items for activity logging. Captures active flag, multilingual descriptions/details, sort order, instruction photos/files, applicable equipment/molds/products/location, activity log type, roles, and attachment category.
- `ActivityLog_Session_Items`: per-session completed activity/checklist items linked back to `ActivityLogID` and `ActivityLogItemID`, including performer, status, location/assets/products/employees, amount/unit, comments translations, thumbnail, sort order, and processed flags.
- `ActivityLog_Session_Items_Attachments`: attachments for session items, including image/file/description, activity type, creator, attachment category, thumbnail flag, and label.

Design notes:
- `ActivityLog` is the main historical source for incident-report briefings and person/time/category queries.
- Activity logging blends free-text narratives, structured categories, related assets/products/employees, and attachment evidence.
- For queue/automation designs, judge success by final persisted business fields (`Status`, translated text, thumbnail/image targets, related rows), not only whether a job ran.

### Cases, case updates, and follow-up workflows

Tables:
- `Case`: parent case/work item table. Captures parent `ActivityLogID`, multilingual title/description, deadline/completion/days overdue, creator, related equipment/molds/products/customers, type/subtype/status, next responsible persons, Mattermost/other links, exported/processed flags, cached latest update, related updates and attachments.
- `Case_Updates`: progress/update records for cases. Captures timestamp/day/month, creator/photo, multilingual update summary/description, proposed new responsible person/title/description/related assets/status, case/update type, links, target `CaseID`, label, and processed flags.
- `Case_Attachments` and `Case_Updates_Attachments`: image/file evidence attached to cases or updates, with creator/type/category/description translations and processed flags.

Design notes:
- Cases are structured follow-up containers; ActivityLog rows can spawn or parent cases.
- New designs should distinguish incident/event capture (`ActivityLog`) from follow-up ownership/deadline/status (`Case`).
- Status values are Lookup-driven and often scoped by case type/subtype.

### Maintenance sessions, maintenance items, and maintenance evidence

Tables:
- `Maintenance_Items`: maintenance checklist/template items. Captures active/sort, multilingual title/location/description, frequency, explanatory/instruction images/files, roles, creator, maintenance type, label.
- `Maintenance_Sessions`: performed maintenance sessions. Captures equipment ID, timestamp/shift, performer, notes, overall status, maintenance/equipment type, cached session items, label.
- `Maintenance_Session_Items`: performed item results in a maintenance session. Captures performer, abnormal/resolution descriptions with translations, status, linked molds/equipment/products/employees, session/item refs, instruction media, label.
- `Maintenance_Session_Items_Attachments`: attachment evidence for maintenance session items.

Design notes:
- Maintenance uses template items plus session/session-item execution records.
- Frequencies and intervals should align with `Lookup` rows and `Maintenance_Items[Frequency]` / `IntervalDays` when designing new checklists.

### ERP assets, products, molds, equipment, and asset details

Tables:
- `ERP_Data_Combined`: imported ERP item/asset/product/mold records. Captures item number/name, item category/subcategory, quality status, supplier, location/warehouse, mold numbers/alternate mold, cavity count, friendly name, type/equipment type, latest mold movement, last reported location, and related asset details/reference documents.
- `ERP_Asset_Details`: structured details/measurements for ERP assets. Captures target ERP asset, detail type, linked activity/item IDs, asset detail item ID, standard value text/decimal, allowable error range, actual value text/decimal, unit, descriptions, and modification metadata.
- `Customer_Details`: customer-specific packaging/logistics/detail fields such as capping method, shipping cages, ESG, packing methods. Current API probe returned an empty body, so verify visibility before relying on live rows.

Design notes:
- Product/mold/equipment references often point back to ERP-derived IDs, not free text.
- When designing asset-specific forms, capture both the asset key and human-friendly label fields only where needed; avoid duplicating ERP truth.

### Reference documents, manuals, links, and controlled resources

Tables:
- `Reference_Documents`: controlled document/reference library. Captures active flag, document type, multilingual title/description, URL, revision, effective/review dates, related molds/equipment/products/all assets/tags, file/image/thumbnail, notification group, and processed flags.
- `ExternalLinks`: curated external links. Captures active flag, type, multilingual title/description, URL, thumbnail, sort order, viewable roles, and label.

Design notes:
- Use Reference_Documents when the object needs revision/effective/review lifecycle, asset relationships, tags, file/image, or notification group.
- Use ExternalLinks for simpler role-visible links/resources.

### Inventory/sample retention and withdrawals

Tables:
- `Inventory_Mgmt`: sample/inventory tracking records. Captures tracking type, timestamp/day/month, related case/activity/product/mold, initial sample photo, sample test date, retention purpose/reason translations, retention duration, initial/current quantity, personnel, storage location, comments translations, and label.
- `Inventory_WithdrawalRecord`: withdrawals from tracked inventory. Captures inventory tracking ID, withdrawal date/time, quantity, withdrawn by, purpose/comments translations, related attachments, processed flags.
- `Inventory_WithdrawalRecord_Attachments`: image/file evidence for withdrawals.

Design notes:
- Inventory is sample-retention oriented, not a full ERP stock ledger.
- Designs should preserve quantity movement evidence and link withdrawals back to the tracked inventory row.

### Translation, processing queues, API targets, and automation plumbing

Tables:
- `GoogleTranslate`: translation job/result ledger. Captures source table/key/column, target columns, status, original text, translated English/Traditional Chinese, and pinyin.
- `ProcessingQueue`: general queue for translation/thumbnail/processing work. Captures source table/key/job type, scoped job key, multiple source/target column slots, GoogleTranslate IDs, source texts, status, attempt count, heartbeat/run/lock timestamps, result/error fields, thumbnail source/target fields, and idempotency flags. Current API probe returned an empty body; verify with a narrower selector before assuming live queue state.
- `API_Target_Queue`: small target queue with `QueueID`, `TargetID`, `TargetTable`, timestamp. Bounded probe found no visible rows.
- `HeartBeat`: heartbeat timestamp rows.
- `RowCount`: cached/real-time row counts by `RowCountID`.

Design notes:
- Queue tables are infrastructure. Keep user-facing process designs separate from queue worker implementation.
- For new async jobs, define the source table/key/column, target field(s), idempotency key, retry policy, and final business-state verification.

## 3. Cross-cutting capture patterns

- Bilingual content is common: many tables have `_en` and `_zh-tw` fields plus queue/GoogleTranslate support.
- Attachments are normalized into separate `*_Attachments` tables with Image/File, description, category, parent ref, and processing flags.
- Most operational tables have stable IDs (`ActivityLogID`, `CaseID`, `MaintenanceSessionID`, etc.) in addition to `Row ID`.
- Many tables keep `Flag_Processed`, `Updater`, `Last Modified`, or queue status fields for automation/export pipelines.
- Role/access vocabulary is Lookup-driven (`Appsheet Role`, `Notification Group`, `Viewable Roles`, `Editable Roles`) and user-specific settings live in `HR_Employees_AppSheet_Settings`.
- App records often capture both structured links (equipment/molds/products/employees/customers) and narrative text with translations.
- Date/time fields often include derived month/day/shift helper columns for filtering and dashboards.

## 4. How to use this map in future AppSheet work

When designing or debugging:
1. Start with the business domain above before choosing a table.
2. Verify exact schema in `projects/AppSheet/appsheet_definition.json`; this map is semantic context, not a substitute for exact column names.
3. Check `Lookup` before adding new enum/status/menu/role/translation values.
4. For person queries, resolve through `HR_Employees[PersonID]`.
5. For incidents/events, begin with `ActivityLog`; for follow-up ownership/deadlines, use `Case`/`Case_Updates`; for recurring checks, use maintenance/activity item templates plus session item rows.
6. For evidence, look for the relevant attachment child table rather than embedding more files on the parent row.
7. For bilingual output, prefer existing translation fields or queue/GoogleTranslate patterns; do not add one-language-only fields unless the use case is truly internal.

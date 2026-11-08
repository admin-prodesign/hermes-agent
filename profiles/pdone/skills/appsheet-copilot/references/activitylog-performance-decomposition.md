# ActivityLog performance decomposition and category-split assessment

Use this when `ActivityLog` remains a top AppSheet sync bottleneck, sync failures say `ActivityLog is not accessible due to: Timed out waiting for a resource`, or Andy asks whether the table should be split by category (Incident Reports, Mold Movement, 5S, etc.).

## Core lesson

A category split can help, but only if normal user sync/view paths stop depending on the broad master `ActivityLog` table. Duplicating category tables while keeping `ActivityLog` as the loaded root table will not materially improve sync; AppSheet will still load/filter/augment the broad table and compute its refs/VCs.

Prefer the target architecture:

```text
Thin ActivityIndex / Activity feed table
+ category-specific operational tables
+ category-specific or domain-scoped attachments
+ archive/cold history tables
```

## What to verify before recommending a split

1. Refresh/inspect the deployed definition.
2. Confirm `ActivityLog` dataset/schema:
   - source/provider (`google_tables` / AppSheet Database vs Sheets)
   - `DataFilter` / security filter
   - current active-window logic such as `Data_Days_ActivityLog`
   - number of columns and virtual columns
   - related cached fields (`ActivityLog_Children_Cached`, `ActivityLog_Session_Items_Cached`, `ActivityLog_Attachments_Cached`)
3. Run a fresh sync-only Performance Analyzer scan and parse raw timings.
4. Label timing correctly:
   - top-level sync duration distribution
   - nested table timing (`ActivityLog`, `Case_Updates`, attachments, etc.)
   - nested virtual-column timing (`ActivityLog_Session_Items[Label]`, row counts, etc.)
5. Get or estimate row/attachment volume by category and month. If the Data API user is filtered and returns 0 rows, do not conclude the table is empty; use admin/source-system exports or an approved data pull.

## Category split decision criteria

Splitting is more likely worthwhile when one or more categories:

- dominate recent rows within the normal security-filter window;
- dominate attachment/session-item volume;
- have category-specific fields that cause many irrelevant Show_If / Valid_If / Suggested_Values / deref formulas to exist on the shared table;
- have independent automation lanes that can be isolated;
- are not required in the global feed for most users.

Likely candidates seen in Pro-Design `ActivityLog` views/fields include:

- `Incident Report`
- Mold movement / mold repair activity
- `5S`
- warehouse inspection
- injection machine parameters / FAI flows
- entry/exit records

## 5S split specifics

For the Pro-Design 5S split, load `references/activitylog-5s-physical-split.md` before creating or recommending columns. Key durable points: existing records use `Category = "5S Action"`; user prefers `5S*` names rather than `FiveS*`; bounded selectors are required for practical audits; and a lean schema should omit unused generic `ActivityLog` fields such as troubleshooting actions, parent/child/session-item fields, molds/products, risk, and reference-document fields unless a current 5S workflow proves they are needed.

## Preferred migration sequence

1. **Quantify** rows and attachments by `Category`, month, BU/creator, and active status.
2. **Contain** before splitting where possible:
   - tighten `Data_Days_ActivityLog` for normal users;
   - archive old rows to `ActivityLog_Archive` or category archives;
   - keep a small active-window table if historical offline access is not needed.
3. **Split the heaviest workflow first**, not every category at once.
4. **Create/keep a thin ActivityIndex** for global recent feed/search/linking/notifications:

```text
ActivityID
Timestamp
Category
SubCategory
CreatedBy
BU
Status
ShortLabel
TargetTable
TargetID
Thumbnail/SearchText as needed
```

5. Move category-specific fields, views, forms, child rows, attachments, and automation into the category table.
6. Update views/slices/actions so normal users load the category tables or thin index, not the old broad `ActivityLog` root.
7. Verify with clean post-promotion sync-only and failure-only analyzer windows.

## Pitfalls

- Do not recommend a split from table p90 alone. A table timing can be high because of active-window size, formula/deref cost, attachment tables, or backend/cache contention.
- Do not confuse AppSheet slices (`ActivityLog_5S`, `ActivityLog_Incident_All`) with physical separation. Slices can improve UX but still require the source table to load.
- Do not migrate all categories in one pass unless there is a tested rollback and a full definition/data migration plan.
- When Data API read returns 0 rows for `ActivityLog`, suspect security/user filtering and source via approved admin export rather than assuming no volume.
- Splitting attachments may be as important as splitting parent rows. `ActivityLog_Attachments` failures often indicate the attachment domain needs its own containment/cache/archive plan.

## Output guidance

Answer in phases: current evidence, why splitting may help, what would not help, recommended audit, lowest-risk first split/archive candidate, and required verification. Keep it clear that schema splits are high-impact writes requiring dry-run, backup/export, validation, stable promotion, and analyzer readback.

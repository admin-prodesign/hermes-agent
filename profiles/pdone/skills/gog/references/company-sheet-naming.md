# Company Google Sheets/Docs naming convention

Use this when creating, copying, or proposing renames for Pro-Design / 良器 company-related Google Sheets or Google Docs.

## Canonical pattern

`良器-部門-表格中文名字 English Name`

Interpretation:

1. `良器-` prefix marks company-owned/company-maintained Sheets/Docs.
2. Department / owning function comes next, followed by `-`.
3. Chinese file purpose comes before the English purpose.
4. Separate the Chinese and English purpose with a space, not another slash-only or English-only title.

Examples in the observed naming family:

- `良器-資材-生管排程 Production Schedule`
- `良器-模修課-模修 Mold Repair`
- `良器-模修課-模修-分析 Mold Repair Analysis`
- `良器-跨部門-線上打卡 Online Punch Clock`

Older project, archive, one-off analysis, or imported files may not follow the pattern. Do not silently rename existing files; produce a proposed rename list and ask for approval before Drive writes.

## Audit workflow

For a naming scan, prefer read-only Drive metadata listing and local filtering:

1. Stay within the approved Drive scope.
2. Do not traverse protected `appsheet` or `sql-srv` descendants unless explicitly approved for that action.
3. Recursively list My Drive folders within scope, not only root + one child level. Company Sheets/Docs often live under `文件 Documents/<department>` such as `文件 Documents/資材 Materials` or `文件 Documents/製造 Manufacturing`, which are two levels below root.
4. Handle pagination with `nextPageToken` for every folder listing.
5. Avoid custom `--fields` masks with `gog drive ls` for audits on this host; observed behavior can return only `nextPageToken` and omit `files`, causing false empty results. Use the default JSON output, then filter locally.
6. Locally filter items whose `mimeType` contains `spreadsheet` or `document`, including native Google Sheets/Docs and imported spreadsheet/document files.
7. Cross-check against the company wiki registry/deep-scan reports when available (`company-wiki/main/syntheses/google-sheets-registry.md` and `reports/google-docs-sheets-deep-scan-*.md`) so previously ingested files are not missed.
8. Classify each visible Sheet/Doc as:
   - matches canonical company naming;
   - bilingual but missing `良器-部門-`;
   - company-related but English/Chinese incomplete;
   - project/archive/import where the convention may not apply.

When proposing renames, include current name, parent folder, rationale, and suggested canonical title. Avoid Markdown tables in Discord; use compact bullets.

## Create-time sharing and protection

Naming is not the whole create job. After a new company Sheet exists, follow `google-sheets-group-editor-and-admin-protection.md`: department Google Group = file Editor; PD One-owned tabs = admin-only sheet protection; parent folder ACL stays as-is unless Andy asked to change it.
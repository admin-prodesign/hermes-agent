# PD One Data Source Registration

Use this when Andy asks to add a Google Sheet, AppSheet table/export, Drive document, Mattermost history source, or similar operational data source to PD One's available sources.

## Pattern

0. **Every durable ingested source gets a wiki page.** Do not treat ingestion/registration as complete just because PD One has an ID or link. Any durable document, workbook, export, Drive file, or operational source that Hermes/PD One will rely on should have a canonical wiki source page that explains what the document is, how it is structured, how to use it safely, and what is unclear.
1. **Load PD One context first.** Use `pd-one-admin`; if the source is Google Workspace, also load `google-workspace`.
2. **Find the current registry/source layer before writing.** Search both:
   - `/home/prodesign/.openclaw/wiki/main/` for canonical wiki pages.
   - `/home/prodesign/.openclaw/workspace/out/wiki-mirror/` only as a read-only/public mirror or discovery aid.
   Common registries include `wiki/main/syntheses/google-sheets-registry.md` and `wiki/main/sources/index.md`.
3. **Create a classed source page, not just a note.** For a Google Sheet, add a page under `wiki/main/sources/` with frontmatter like:
   ```yaml
   ---
   title: <Human title> / <Chinese title if useful>
   id: source.google-sheets.<stable-slug>
   pageType: source
   status: active
   updatedAt: <UTC ISO timestamp>
   sourceType: google-sheet
   sourceSystem: google-workspace
   spreadsheetId: <id>
   sourceIds:
     - <registry/provenance id>
   accessTier: <public|internal|production-sensitive|sensitive>
   ---
   ```
4. **Record safe operating rules on the source page.** Include intended PD One use, read/write boundary, raw-dump limits, approval requirement for writes/share/formula/script changes, and source provenance. For manually digitized sources, explicitly record freshness/lag behavior (for example paper reports entered a few days later, longer after weekends/long weekends) so PD One can caveat time-sensitive answers.
5. **For complex workbooks and durable documents, perform a second-pass source guide/data dictionary.** Basic registration lets PD One know the source exists, but reliable analysis requires understanding the document in its entirety: tab/section map, header/field meanings, date/freshness logic, canonical analysis patterns, data-quality caveats, and role-specific disclosure limits. Trigger a read-only thorough scan as part of wiki building, and ask Andy/owners follow-up questions for unclear fields, ambiguous tabs, suspicious formulas, or undocumented business meanings instead of guessing. If the user asks whether more setup is needed, recommend this scan/source-guide pass rather than claiming full analytical readiness from the registry entry alone. The canonical durable playbook for this is Hermes skill `company-wiki`, `references/durable-source-ingestion-playbook.md`.
6. **For role recommendations, map to existing PD One role classes.** Prefer scoped access language already used in `policies/mattermost-roles.json`: admin/executive, production scheduler, molding operations, QA, key employee operations, sales, procurement, general employees, and unrelated HR/Finance/IT-only roles. State whether access is detailed, aggregate, task-scoped, or denied by default.
7. **Link from the registry.** Patch the relevant registry entry with a `Detailed source page` line and any access-tier/use caveat.
8. **Regenerate indexes.** Run from `/home/prodesign/.openclaw/workspace`:
   ```bash
   openclaw wiki compile
   ```
   This updates generated index/related sections. Do not hand-edit generated blocks unless the compiler is unavailable.
9. **Refresh the public mirror when the wiki page should be browseable there.** Run:
   ```bash
   python3 tools/wiki_public_export.py
   ```
   Treat `out/wiki-mirror/` as generated output; do not use it as canonical source.
10. **For published employee-readable Google Drive corpora, use manifest default access deliberately.** In `workspace/data/google-docs-index/manifest.json`, entries can opt into PD One employee readability with `sensitivity: shared-operational`, `sensitive: false`, and `defaultEmployeeAccess: reader`. This is for explicit internal/public corpora Andy/admin has classified as employee-readable (for example published ISO files under `管理部/文管中心/發行版`), not for production-sensitive workbooks. Then run:
   ```bash
   python3 tools/sync_google_group_document_access.py --account admin@prodesign-group.com
   python3 tools/mattermost_policy_lookup.py generate-cache
   ```
   Verify `group-document-access-cache.json` and per-user Mattermost policy caches show the expected document count/readability for exact active Mattermost user IDs.
11. **Verify targeted evidence.** Check the new source page, registry link, source/index inclusion, generated access caches, and the current compiled/digest surface if present. Some deployments may not keep `.openclaw-wiki/cache/agent-digest.json`; do not invent that path if it is absent.
12. **Commit narrowly.** The OpenClaw workspace often has unrelated dirty/generated state. Before committing, inspect `git status --short` and `git diff` for only the files you touched. Stage only the new source page, registry/index files, manifest/access-cache/policy-cache files, and tool changes that are directly required. Do not accidentally commit unrelated cron, metrics, exports, or bulk mirror changes.

## Second-pass source guide checklist

For a complex Google Sheet that PD One will analyze regularly, create or extend the source page with:

- **Tab map:** every tab name, rough purpose, grid size, whether it is raw input, lookup/config, summary/dashboard, or legacy.
- **Field dictionary:** key columns/header rows, units, identifiers (date, machine, mold, product, operator/shift if present), and formulas vs manual-entry fields.
- **Freshness model:** latest reliable data date, manual digitization lag, weekend/holiday effects, and how PD One should phrase caveats.
- **Analysis recipes:** approved question patterns (daily/weekly/monthly output, throughput, bottlenecks, capacity/schedule impact, quality/reject trends) and fields/tabs to use.
- **Data-quality caveats:** merged/header rows, missing dates, inconsistent names/codes, formula-only summaries, stale/legacy tabs, and any columns unsafe for broad disclosure.
- **Role disclosure rules:** what detailed, aggregate, task-scoped, and denied responses look like for the roles listed below.

## Access recommendation defaults for production-sensitive Google Sheets

- **Andy / Vice President / PD One admin:** full read plus approved workflow changes; writes/sharing/formula/script changes still need explicit confirmation.
- **Executive data access:** broad read/summarize/analyze.
- **Domain operators/leads who own the workflow:** detailed read/summarize/analyze for their work domain.
- **Adjacent departments (QA, Sales, Procurement):** scoped or aggregate read only when tied to their business purpose.
- **Key employee operations:** aggregate/task-scoped read; avoid raw row dumps and individual employee/operator comparisons unless approved.
- **General employees/operators:** usually no direct workbook analysis through PD One; provide only shift/task-relevant summaries via approved surfaces.
- **Unrelated HR/Finance/IT-only roles:** no default access unless another role grants the domain scope or Andy/admin approves a specific request.

## Pitfalls

- Do not treat a generated mirror entry as the canonical source; patch the canonical wiki under `/home/prodesign/.openclaw/wiki/main/`.
- Do not commit all dirty wiki/workspace changes after compiling; the compile step may expose pre-existing dirty state. Stage narrowly.
- Do not turn a production-sensitive data source into a broad employee capability. Prefer least-disclosure summaries and provenance.
- Do not grant source-system writes by implication when a user asks to add a data source; registration for analysis is separate from write authority.
- `tools/mattermost_policy_lookup.py` currently merges role `dataAccess` by dictionary update in assigned-role order, so a later role can overwrite an earlier role's value for the same key. Avoid adding explicit `deny` values for orthogonal roles that may be combined with allowed roles; represent no default access by omitting the source key and rely on source-page guidance/admin approval.

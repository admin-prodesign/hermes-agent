# ISO / ECRN Google Docs access registration

Use this when Andy/admin says `employee-assistant` should not block employees from company-published ISO files, ECRN sheets, or similar shared-operational documents.

## Core lesson
Do not treat a missing result from `scoped_google_document_access` / `scoped_google_sheet_read` as proof the employee should be blocked. For Google Docs/Sheets, PD One access is driven by the manifest-backed deterministic Drive/Google Group access cache. If a company-published ISO file is shared in Drive/Groups but absent from `workspace/data/google-docs-index/manifest.json`, it will not appear in the employee policy cache.

## Safe default
- ISO-system files such as ECRN can be registered as `sensitivity: shared-operational` / `sensitive: false` when Andy confirms they are company-published/shared-operational.
- Still rely on exact Mattermost sender-id policy resolution and Drive/Google Group permission evidence. Do not grant by employee name or fuzzy matching.
- Keep the tool read-only for employees. Google Sheet writes, permission changes, Drive moves/renames, and source-system record edits remain approval-gated.
- Do not restart the gateway for a manifest/cache-only update unless a separate code/config change requires it and Andy approves the restart.

## Procedure
1. Verify the target file by Drive search/permissions, preferably via `gog`:
   - `gog drive search "ECRN" --max=20 --json`
   - `gog drive permissions <file_id> --account admin@prodesign-group.com --json --no-input`
2. Add or update a manifest entry in `/home/prodesign/.openclaw/workspace/data/google-docs-index/manifest.json`:
   ```json
   {
     "id": "<drive_file_id>",
     "name": "良器-技術發展部-ECRN",
     "category": "iso-system:engineering-change:ECRN",
     "mimeType": "application/vnd.google-apps.spreadsheet",
     "sensitive": false,
     "sensitivity": "shared-operational",
     "accessNote": "ISO-system ECRN workbook. Andy confirmed ISO files are company-published/shared-operational by default; PD One may read bounded ranges through scoped_google_sheet_read when requester access is verified by Drive/Google Group evidence. Writes remain approval-gated."
   }
   ```
3. Regenerate document access evidence and per-user policy cache:
   - `python3 tools/sync_google_group_document_access.py --account admin@prodesign-group.com`
   - `python3 tools/mattermost_policy_lookup.py generate-cache`
4. Verify the result:
   - Confirm the file id exists in `data/google-docs-index/group-document-access-cache.json`.
   - Confirm affected `policy-cache/mattermost/users/<id>.json` entries include the document under `googleWorkspace.documentAccess.documents`.
   - For sheets, read a bounded range, e.g. `gog sheets get <sheet_id> 'A1:J5' -a admin@prodesign-group.com -j --no-input`.
   - Run targeted employee safety-gate tests, e.g. `node --test tests/pd-one-employee-safety-gate-scope.test.mjs`.
5. Commit and push durable manifest/cache changes when the OpenClaw backup remote is configured.

## Example receipt from the ECRN fix
- File registered: `良器-技術發展部-ECRN` (`1fOk3hDP1Q7bBB224w1HxPVXLJopaXvUd49oU1PWgSSU`).
- Drive permissions showed existing group/user grants including sales, production scheduler, R&D, finance, senior staff, admin, and owner.
- Cache generation reported `fileCount: 15`, `failureCount: 0`.
- Policy cache verification found ECRN access for 10 mapped Mattermost users.
- Sheet smoke read returned `'總表'!A1:J5` with 5 rows.
- `node --test tests/pd-one-employee-safety-gate-scope.test.mjs` passed `8/8`.

## Pitfall
If the desired policy becomes “all ISO files under `sql-srv/管理部` are employee-readable by default,” a one-file manifest entry is not enough. Register a broader ISO corpus/data source with explicit source policy and read-only indexing rather than bypassing the safety gate or relying on arbitrary filesystem access.
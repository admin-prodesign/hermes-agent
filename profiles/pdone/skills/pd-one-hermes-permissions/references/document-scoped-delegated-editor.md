# Document-scoped delegated editor approval

Use when Andy/admin wants an employee to be able to ask PD One for changes to one specific Google Drive/Sheets document without repeating admin approval every time.

## Durable pattern

1. **Interpret admin wording as delegated PD One authority when explicit.** If Andy/admin says an employee may have “full admin/editor privileges on this document except deletes” so PD One no longer needs repeat approval, treat that as authorization for PD One to perform the employee's requested non-delete writes on that exact document. Do not narrow it to only “the employee may edit in the Google UI.”
2. **Keep identity exact.** Scope the grant to the employee's exact Mattermost sender id and their known Google Workspace principal. Do not grant from name/display-name matching.
3. **Verify the Drive side.** Read back the target file's Drive permissions and confirm the employee or approved group has `writer` access on the exact file id.
4. **Record the PD One side in canonical policy.** Add a document-specific scope/data-access note to `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-users.json` (or the appropriate role only if it should apply to a whole class of users). Regenerate policy cache with `tools/mattermost_policy_lookup.py generate-cache` and read back the exact sender-id cache.
5. **Define what PD One may do without re-approval.** Prefer narrow language such as: add/update sheets, formulas, charts, filters, formatting, validation/dropdowns, selectors, and report/analysis tabs on this one workbook.
6. **Define hard stops.** Deletes remain destructive: deleting sheets/rows/source data, destructive cleanup, external sharing, Drive moves, unrelated files, source-system writebacks, credentials/config/gateway/policy changes, and permission expansion still require separate Andy/admin approval.
7. **Read back receipts.** Report the file id/title, relevant Drive permissions, cache source hash, exact sender-id cache field/scope, and the limits.

## Important Drive/Sheets limitation

Google Drive/Sheets does not provide a clean native role for “full editor except delete.” A Google `writer` can still perform many destructive edits in the UI. The enforceable PD One pattern is therefore layered:

- Drive grants the employee `writer` ability on the document.
- PD One policy records a document-specific delegated non-delete authority for that exact sender id.
- PD One refuses delete/destructive requests unless Andy/admin separately approves.

Do not claim Google itself enforces “cannot delete” unless you have implemented and verified additional file/sheet protections that actually do so.

## Andy 2026-09-08: live Drive editor auto-approve

If Andy/admin says requests from users who already have Google Sheets editor access should be auto-approved without Andy review, treat that as a standing file-ACL rule, not a one-document grant:

1. Verify live Drive permissions on the exact file id.
2. Match the requester by exact Mattermost sender id → company/associated Google emails → direct `writer`/`owner` **or** membership in a Drive `writer`/`owner` Google Group.
3. If writer/editor is verified, do **not** create a PDAPP ticket. Run the non-destructive in-place edit (including non-delete column inserts that only shift other columns, and addSheet/new-tab) with typed Sheets/Docs MCP (`mcp__pdone_safe_ops__pd_one_drive_acl_authorize` then `mcp__pdone_safe_ops__pd_one_sheets_*` / Docs ops) and read it back. Coarse `approval.writes=false` / `tools.writes=confirm-by-admin` does not cancel this class. A blocked employee terminal is not a reason to ticket, and is **not** a reason to open employee-lane `terminal` even when the Google email is in an editor group. Lookup: `tool_search` first, then exact `mcp__pdone_safe_ops__…` names. Short-name `tool_describe` `not_found` is a lookup miss — retry search; do not report tools unavailable or browser-type cells.
4. If the requester is only a viewer/commenter, or live ACL cannot be verified, keep the existing approval-ticket path.
5. Red lines unchanged: deletes, sharing, Drive moves, unrelated files, credentials/config/gateway/policy.

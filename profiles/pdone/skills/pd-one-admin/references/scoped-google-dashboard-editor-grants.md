# Scoped Google dashboard editor grants for PD One employees

Use this when Andy/admin asks that a named employee (for example a department lead) can ask PD One to modify a specific Google Sheets dashboard without separate approval each time.

## Durable pattern

1. Identify and verify the exact Google file.
   - Search Drive with `gog drive search` or another authenticated admin route.
   - Read permissions before changing them.
   - Grant the employee direct `writer` access only to the intended file, then read permissions back and record the permission id.
2. Identify the exact PD One sender identity.
   - Use Mattermost/OpenClaw user ids, not display names or fuzzy names.
   - Update the policy for the exact sender id.
3. Add a class/scope role plus a user-level override.
   - Role: describes the reusable scoped capability and safe scope.
   - User override: may be needed because merged role policy can still leave `tools.writes` as `confirm-by-admin` from the user's base role.
   - Keep redlines explicit: `permissionChanges`, `externalSends`, and `destructive` stay `never` unless Andy separately approves those powers.
4. Regenerate both policy caches.
   - Run JSON validation first.
   - Run `tools/mattermost_policy_lookup.py generate-cache`.
   - Verify the main cache and the employee mirror cache contain the new scope and write override.
5. Create an approved admin-ticket grant in the ledger.
   - Bind the exact Google file id as the write target.
   - If Andy's request is meant to work from the employee's DM or normal PD One context, create an origin-independent/any-origin grant rather than one tied only to the original admin Discord/Mattermost thread.
   - Grant matching should fail closed for new write targets or materially different workflows.
6. Smoke-test without sending employee messages.
   - Positive: employee sender id + exact file + non-destructive dashboard capabilities should match the standing grant.
   - Negative: unrelated roles/unknown users should require new approval.
   - Redline negative: permission/share/credential/config/destructive requests should require new approval.
7. Commit and push durable policy/cache changes when the backup repo is configured.

## Scope wording to preserve

Allowed without separate approval should be narrowly phrased: non-destructive dashboard layout, formula, chart, filter/control, label, and summary-table updates on the named spreadsheet.

Still require separate approval: external sharing, permission changes, destructive deletes/purges, credentials/config/gateway changes, unrelated files, HR/payroll/private records, and source-system writebacks.

## Pitfalls

- For ordinary non-destructive Google Sheets/Docs edits on a file the requester can already edit, Andy 2026-09-08 standing rule is: live Drive writer/editor (direct or writer-group) is enough; do not open a PDAPP ticket. Keep named dashboard-editor grants for cases that still need a user-level `tools.writes` override or any-origin ledger grant beyond that ACL. Red lines (delete/share/move/unrelated files/config) still need new approval.
- Do not rely on the new role alone if the merged user policy still says `confirm-by-admin`; add a targeted user-level write override for the specific file/scope.
- Do not tie the grant only to the original Andy/admin thread when the intent is employee DM reuse.
- Do not send smoke-test messages to employees unless explicitly requested; use deterministic policy and grant-matching checks.
- Do not include broad permission/share powers in a dashboard-editor grant unless separately approved.

## Session receipt: Leon Lin / Injection Molding Dashboard, 2026-05-22

- Dashboard file id: `1jDutDQQJR6sVUDm_q8wnR7BoYiDMD4cTFUu78Ilhk7I`.
- Employee Google account: `leonlin@prodesign-group.com`, verified as direct `writer`.
- Mattermost sender id: `x8yps7k9pfrg9yxm6a3h9p64qe`.
- Initially added scoped role `injection_molding_dashboard_editor`; follow-up clarification moved the same permission into reusable leadership role `injection_molding_lead` and assigned that role to Leon.
- Later clarification: `molding_assistant_manager` is a title, not Leon's actual role. Former `molding_assistant_manager` operational permissions were consolidated into `injection_molding_lead`, Leon's policy now uses only `injection_molding_lead`, and the old role key was deleted.
- Added safe scope: `injection-molding-dashboard-readwrite`.
- Added user-level `tools.writes` override for non-destructive edits to that file only; permission changes, external sends, and destructive actions stayed `never`.
- Created any-origin standing grant `GRANT-PDAPP-20260522-88E2C181`, bound to the dashboard file id.
- Smoke tests: Leon positive grant match passed; unrelated roles/unknown users and permission-change redline returned new-approval-required; after role refactors, positive grant match still passed and old scoped-only/title roles were absent from active policy/cache.

# Role-scoped work manual editor grants

Use when Andy/admin asks to let a current department lead (for example the injection molding lead) use PD One to change specific Google Docs work manuals without making a broad Drive sharing or policy/admin grant.

## Pattern

1. Verify requester authorization from the injected exact Mattermost sender-id policy context. This is policy expansion/config work, so Andy/admin approval in the current request is sufficient, but still use least scope.
2. Identify the target role by canonical policy role name, not by title wording alone. Example: Andy called it "Leon's lead role / molding staff lead"; canonical role was `injection_molding_lead` and Leon's exact Mattermost id was `x8yps7k9pfrg9yxm6a3h9p64qe`.
3. Identify the exact target documents by file id and title from the document-access cache or manifest. Example molding work manual docs:
   - `10qh8peJerJhWo7ILFtr42yqTYAwW9W9ynpqw1lZGxXI` — `良器-工作指南與程序手冊-成型非作業員 Molding Staff`
   - `1pW8TwDcYG8PbSUmWcucvIOo7NUe7w2FKXODbh2zovbM` — `良器-工作指南與程序手冊-作業員 Operator Work Guidelines and Procedures Manual`
4. Edit canonical policy, not generated cache:
   - Add role/user `safeScopes` such as `work-manual` plus a narrow role-specific scope like `molding-work-manuals-readwrite`.
   - Add a `dataAccess` entry naming exact file ids/titles, non-destructive content-update scope, preview/confirmation requirement, and explicit exclusions.
   - Update `tools.writes` to allow only the named docs/content class, and keep all other writes admin-confirmed.
   - Add only relevant channel access if there is a work-manual channel policy entry.
5. Regenerate Mattermost policy cache with `tools/mattermost_policy_lookup.py generate-cache`; do not hand-edit cache files.
6. Verify by resolving the exact target Mattermost user id and checking relevant scopes, `tools.writes`, channel access, and `dataAccess` entry in the generated cache.
7. Report clearly whether Drive permissions were changed. Usually this task changes PD One authorization only; direct Google Drive sharing/permission changes remain separate approval-gated work.

## Safety boundaries to preserve

- Do not convert this into a broad Google Drive permission grant unless Andy explicitly asks for Drive sharing.
- Keep destructive edits, deletes/purges, external sends, Drive permission changes, unrelated files, HR/payroll/private records, source-system writebacks, credentials/config/gateway/policy changes beyond the approved scope, and official ISO-control/release commitments outside the delegated grant.
- If live Drive access shows the lead only has reader/commenter permission, note that PD One may still be authorized to perform confirmed edits on their behalf if PD One's service account/editor account has write access; that is distinct from granting the human Google Drive writer permission.
# Group-keyed work-manual change grants

Use when Andy/admin authorizes a department Google Group to submit content that PD One should automatically add to that department’s live work manual in a non-DM setting.

This is **request-authorization**, not Drive sharing, and not a personal `allow_emails` grant.

## Pattern

1. Audience key is Google Group `expanded_members` from `hermes.google-workspace-group-memberships.v1` (identity cache emails, including associated Gmail). Exact Mattermost sender id only. Never display-name matching. Never mint a second Google Admin lookup.
2. Map document key → group email → preferred department Mattermost channel in `config/work_manual_change_grants.json`. Enable only live manuals. Neighboring manuals do not inherit another manual’s grant.
3. Encode a narrow role `dataAccess.workManualChange` plus a scope such as `it-work-manual-group-auto-apply` so injected policy is not prompt memory. The **runtime gate** is still group membership, not the role name.
4. Hard check: `tools/work_manual_change_authorize.py`. Fail closed on missing/stale/incomplete identity or group cache.
5. **Non-DM vs DM:** auto-approve and write only in non-DM Mattermost settings. In DM: do not execute; bilingual redirect to the preferred department channel so the rest of the department can see the request. Never do the work from a DM and post a summary later.
6. In-scope = secret-free content add/update for that named manual (procedure text, redacted screenshots, header/changelog). Denied: verbatim credentials, other manuals, Drive sharing, destructive edits, gateway/config/policy expansion, unrelated source-system writes.
7. Live Google Docs writes still use `pd_one_google_docs_document_ops` with dry-run, revision, idempotency, and readback. Pass the exact requester id plus `channel_id`/`chat_type`. Do not impersonate Andy’s requester id.
8. Regenerate exact-sender cache with `tools/mattermost_policy_lookup.py generate-cache` and read back an IT-role user (redact). No gateway restart.

## IT live grant (2026-09-04)

- Group: `it@prodesign-group.com`
- Manual: `it_manual` / `良器-工作指南與程序手冊-IT` (`1GshCdEa6GFkb8OrrVBf0waoIqDoRGtzkd38rJBDAf5E`)
- Preferred channel: `itbmu3ycsjb3tfuscmw69b9iny` (`IT工作 | IT Work`)
- Also mapped: IT department channel `jp47xmyu8prytmqrhimaw9hy7e`
- `auto_approve_any_non_dm`: true

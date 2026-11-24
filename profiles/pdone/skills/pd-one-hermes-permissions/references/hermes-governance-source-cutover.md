# Hermes governance source cutover for PD One Mattermost permissions

Use this reference when continuing or auditing the PD One/OpenClaw → Hermes migration, especially when deciding which files are authoritative for Mattermost permission, channel, review-log, and safety behavior.

## Durable outcome

- PD One runs under Hermes profile `pdone`.
- Default-profile Hermes (`HERMES_HOME=/home/prodesign/.hermes`) is PD Neo, not PD One.
- PD One Mattermost permission/governance source of truth is the Hermes PD One profile: `/home/prodesign/.hermes/profiles/pdone`.
- Legacy OpenClaw paths under `/home/prodesign/.openclaw/` are compatibility/reference mirrors only unless Andy explicitly asks to inspect or repair them.

## Canonical Hermes PD One policy paths

- Channel policy: `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-channels.md`
- User policy: `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-users.json`
- Role policy: `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-roles.json`
- Exact-sender generated cache: `/home/prodesign/.hermes/profiles/pdone/policy-cache/mattermost/users/{sender_id}.json`
- Employee mirror cache: `/home/prodesign/.hermes/profiles/pdone/policy-cache/employee/`

## Verification pattern

1. Confirm active config points to Hermes-native paths (`pd_one_hermes_policy_root: /home/prodesign/.hermes/profiles/pdone`, with the old `pd_one_openclaw_workspace` key accepted only as a compatibility alias in Hermes Agent code).
2. Confirm the active `pdone` gateway process has `HERMES_HOME=/home/prodesign/.hermes/profiles/pdone`.
3. Regenerate policy cache from the Hermes profile and verify `ok=true`.
4. Run exact-sender lookup for an admin/known user and an unknown sender; known user should allow scoped work, unknown should fail closed.
5. Generate sub-agent policy context and verify it uses the Hermes cache path and exposes summary/least-privilege context, not raw document lists.
6. Run focused Mattermost gateway tests with Hermes policy path environment variables.
7. Back up durable profile state to `admin-prodesign/hermes-backup` and report the commit receipt.

## Naming caveat

Gateway/test labels may still say `PD One Hermes permission bridge` for backward-compatible naming. Treat the configured cache/source path, not the label, as authoritative.

## Do not overcorrect

Do not rewrite historical sessions, logs, old backups, or pre-migration inventory just because they mention OpenClaw. Historical evidence should stay historical. Only live profile rules, skills, policies, cache generators, and current migration docs need source-of-truth wording.
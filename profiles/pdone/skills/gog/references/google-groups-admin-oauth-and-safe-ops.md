# Google Groups admin OAuth and safe operations

Use this when Andy/admin asks PD One to create Google Groups, copy Google Group settings, add members, or add a subgroup such as `safety@prodesign-group.com` into `all-company@prodesign-group.com`.

## Required scopes

For Google Groups creation plus settings read/copy, the Gog `admin@prodesign-group.com` credential needs these scopes in addition to the normal operational non-Gmail scopes:

```text
https://www.googleapis.com/auth/admin.directory.group
https://www.googleapis.com/auth/admin.directory.group.member
https://www.googleapis.com/auth/apps.groups.settings
```

Meanings:

- `admin.directory.group` — create/read/update Google Groups.
- `admin.directory.group.member` — list/add/remove group members and group-in-group membership.
- `apps.groups.settings` — read/update/copy Google Groups settings.

Gog’s built-in `--services admin` is documented as Workspace service-account-only, so for the user OAuth handoff append these with `--extra-scopes` rather than expecting `--services admin` to work in a normal browser consent flow.

## Avoid approval-noisy command shapes

Do **not** use these patterns for normal Google Groups admin work unless deliberately debugging Gog internals:

```bash
python - <<'PY'
...
PY
python -c '...'
gog ... | python3 ...
# exporting OAuth tokens and then using ad-hoc Google API Python
```

They trigger dangerous-command or token-handling gates and make receipts harder to audit. Prefer:

1. Typed MCP safe tools from `pdone_safe_ops` when available:
   - `pd_one_google_group_members` for bounded group/member reads and filters.
   - `pd_one_google_group_owner_enforcement` for fixed administrative-continuity operations:
     - `operation=ensure_owners` ensures `andylin@gmail.com` and `pro.design.group.tw@gmail.com` are `OWNER` in every accessible `@prodesign-group.com` group. It is dry-run by default, rejects arbitrary domains/members, cannot remove or demote, caps discovery at 100 groups, and performs full readback verification. Live mode requires both the exact phrase `RUN LIVE GOOGLE GROUP OWNER ENFORCEMENT` and an unused approval ticket whose immutable action binding, trusted Andy decision, `permission_changes_allowed` scope, capability, domain, and owner allowlist all match; the ticket is claimed and then completed or failed, preventing replay.
     - `operation=remove_admin_except_it` removes only `admin@prodesign-group.com` from accessible Pro-Design groups other than `it@prodesign-group.com`. It verifies both continuity accounts are already `OWNER` in every removal target before any deletion, preserves IT exactly, is idempotent, and performs per-removal plus full-inventory readback. Live mode requires the exact phrase `RUN LIVE GOOGLE GROUP ADMIN REMOVAL EXCEPT IT` following Andy's explicit request.
     - Both operations may bridge the Gog credential through a mode-0700 temporary directory; the file is deleted immediately and credential values are never returned or logged.
   - `pd_one_google_group_change_dry_run` for general group create/member add/remove previews. This is preview-only; live changes still need approval and an approved apply path.
2. First-class `gog` commands (`gog admin groups ...`, `gog drive ... --json --no-input`) when MCP does not cover the operation.
3. A checked-in helper script with narrow subcommands and dry-run defaults if Gog/MCP lacks a command.
4. File-backed JSON parsing/readback rather than pipe-to-interpreter.

Fallback helper shape if first-class MCP/Gog commands are missing:

```bash
/home/prodesign/.hermes/profiles/pdone/scripts/google_group_safe_ops.py list-groups
/home/prodesign/.hermes/profiles/pdone/scripts/google_group_safe_ops.py create-group --email safety@prodesign-group.com --name '安全 Safety' --dry-run
/home/prodesign/.hermes/profiles/pdone/scripts/google_group_safe_ops.py add-member --group safety@prodesign-group.com --member erika@prodesign-group.com --dry-run
/home/prodesign/.hermes/profiles/pdone/scripts/google_group_safe_ops.py add-group-to-group --child safety@prodesign-group.com --parent all-company@prodesign-group.com --dry-run
/home/prodesign/.hermes/profiles/pdone/scripts/google_group_safe_ops.py copy-settings --from facilities@prodesign-group.com --to safety@prodesign-group.com --dry-run
/home/prodesign/.hermes/profiles/pdone/scripts/google_group_safe_ops.py verify --group safety@prodesign-group.com
```

Helper guardrails should include: `prodesign-group.com` allowlist only, no Gmail scopes, no token printing, dry-run by default, `--live` required for writes, and readback verification after each mutation.

## OAuth consent via visible noVNC browser

When the user says the headless/remote auth flow is troublesome, use the `pd-one-gog-oauth-vnc-handoff.md` noVNC pattern, but include the Google Groups extra scopes.

Generate a consent URL for noVNC startup:

```bash
SERVICES='calendar,drive,driveactivity,drivelabels,docs,slides,contacts,tasks,sheets,people,forms,sites,meet,appscript'
EXTRA='https://www.googleapis.com/auth/admin.directory.group,https://www.googleapis.com/auth/admin.directory.group.member,https://www.googleapis.com/auth/apps.groups.settings'

gog auth add admin@prodesign-group.com \
  --client prodesign-admin \
  --remote --step=1 \
  --services "$SERVICES" \
  --drive-scope full \
  --extra-scopes "$EXTRA" \
  --force-consent \
  --json --no-input > /home/prodesign/.hermes/browser-profiles/gog-auth-step1.json
```

Before sharing the browser, parse the returned URL from the local JSON file and verify:

- requested scopes include all three Google Groups scopes;
- no scope contains `gmail`;
- the URL is saved locally for `START_URL`, not pasted repeatedly in chat.

Start the temporary browser using the existing noVNC container workflow. Give the user the noVNC URL and temporary VNC password only. Tell them to approve as `admin@prodesign-group.com`. If Google ends on `127.0.0.1/.../oauth2/callback?code=...&state=...`, the failed page is expected; have them paste the full final address-bar URL privately back to PD One.

Complete exchange:

```bash
gog auth add admin@prodesign-group.com \
  --client prodesign-admin \
  --remote --step=2 \
  --auth-url "$PASTED_REDIRECT_URL" \
  --json --no-input
```

Do not echo the pasted redirect URL into logs or chat because it contains an OAuth code.

## Verification after auth

Run read-only checks before attempting writes:

```bash
gog auth doctor --json --no-input
gog auth list --json --no-input
gog admin groups list --domain prodesign-group.com --account admin@prodesign-group.com --json --no-input --all
```

If Gog has group-settings commands, verify settings access read-only first:

```bash
gog admin groups settings get facilities@prodesign-group.com \
  --account admin@prodesign-group.com --json --no-input
```

For the group creation task, final receipts should include readbacks for:

- target group exists;
- target group settings match the template group;
- direct member user was added;
- target group was added as a member of `all-company@prodesign-group.com`;
- any Drive ACLs granted to the new group are present on the exact folder/file IDs.

## Cleanup

Always remove temporary browser state promptly after successful exchange or timeout:

```bash
docker rm -f pdone-gog-auth-browser
rm -f /home/prodesign/.hermes/browser-profiles/gog-auth-pdone.vnc-password
```

A delayed cleanup timer/background process is acceptable, but still clean up immediately if the handoff completes early.

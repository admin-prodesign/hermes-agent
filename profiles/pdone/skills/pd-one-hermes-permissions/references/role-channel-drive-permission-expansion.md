# Role/channel/Drive permission expansion pattern

Use this reference when Andy/admin approves a PD One/Hermes permission expansion that spans Mattermost policy, agent routing, generated policy cache, and Google Drive ACLs.

## Durable pattern

1. **Confirm exact identity and scope first**
   - Resolve the requester by exact Mattermost sender id from the injected bridge/cache.
   - Resolve the target employee by exact canonical user id in `policies/mattermost-users.json`; do not rely on display name alone.
   - If the requested scope names a Drive location, resolve the folder/file id before editing policy.

2. **Separate policy capability from external ACL**
   - Policy role/channel changes authorize what PD One may do for the user.
   - Google Drive sharing/permission changes are a separate side effect and require explicit approved-user authorization.
   - If the employee's company email is not a Google account, use the exact Google account that Drive accepts and record that fact in the policy notes for future role holders.

3. **Prefer reusable role names over title-specific names**
   - If Andy asks to avoid job-title implications, rename role bundles to reusable function names such as `qa_lead` rather than `qa_manager`.
   - Update all canonical policy references and generated cache, but do not rewrite historical logs/exports unless explicitly requested.

4. **Edit all relevant layers**
   - `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-roles.json`: role name, scopes, channels, `dataAccess`, tools, approvals.
   - `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-users.json`: assigned roles and any user-level tool overrides.
   - `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-channels.md`: explicit channel policy, allowed work, guardrails, bilingual/mention behavior.
   - Hermes `pdone` config/channel bindings when making a default channel into a specialist channel.
   - Wiki/runbook notes if the change is durable operational policy.

5. **Regenerate and verify**
   - Run `/home/prodesign/.hermes/profiles/pdone/tools/mattermost_policy_lookup.py generate-cache`.
   - Verify the target employee lookup shows the new role, expected channel access, expected scope/dataAccess text, and no old role if it was renamed.
   - Validate JSON for canonical policy files, generated cache, and touched Hermes config files.
   - Verify Drive ACL readback after any Drive permission grant.

6. **Commit/push durable state**
   - Commit policy/cache/wiki changes and config binding changes to the private Hermes backup repo when configured.
   - Report commit SHAs and whether a gateway reload/restart is still needed.

## Caveats from the Lydia QA dashboard grant

- Channel policy alone is not enough for a new specialist channel: `openclaw.json` also needed a Mattermost channel group entry and a product-quality agent binding for `~qa`.
- Generated policy cache can touch many per-user files because `sourceHash` changes. That is expected when canonical policies change.
- `mattermost_review_log.py append` intentionally skips Andy/admin rows (`skippedAndyRows: 1`); do not treat that as a failed write for Andy-originated permission changes.
- Do not restart the gateway just to activate a config binding unless Andy/admin explicitly approved the restart or bounded checks show the gateway is already unresponsive under the standing restart permission.

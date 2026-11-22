# Hermes-native PD One permission migration smoke checks

Use this reference when migrating or validating PD One Mattermost permission/governance artifacts from OpenClaw workspace paths into the active Hermes `pdone` profile.

## Key lesson

Do not stop at copying policy files or regenerating one cache. A credible cutover requires classifying generated-cache differences, verifying tracker/audit dry-runs, testing gateway injection, and validating sub-agent least-privilege handoff.

## Minimum verification set

1. **Canonical policy equality**
   - Compare OpenClaw vs Hermes SHA-256 for:
     - `policies/mattermost-users.json`
     - `policies/mattermost-roles.json`
     - `policies/mattermost-channels.md`
     - `policies/automation-self-heal.json`
   - Equality here means the canonical policy source was mirrored; generated caches may still differ because they include timestamps and newly included evidence.

2. **Generated cache classification**
   - Compare per-user cache file sets between old and new locations: no missing user files either way.
   - Ignore volatile fields such as `generatedAtUtc` and `sourceHash` when looking for semantic differences.
   - Classify added `googleWorkspace.documentAccess` evidence separately from privilege-policy changes; it is evidence used by policy, not by itself a permission expansion.

3. **Document-access regeneration**
   - Run the Hermes-profile document access sync and confirm:
     - `ok=true`
     - nonzero expected `fileCount`
     - expected `userCount`
     - `failureCount=0`
     - employee mirror path is under `/home/prodesign/.hermes/profiles/pdone/policy-cache/employee/`

4. **Exact-sender cache regeneration**
   - Run `tools/mattermost_policy_lookup.py generate-cache` from the Hermes profile.
   - Confirm the cache dir is `policy-cache/mattermost`, the employee mirror is written, and the source/document-access hash is reported.

5. **Google Sheet governance dry-runs**
   - `tools/user_memory_onboarding_state_sync.py --dry-run` should report `status=ok` and row counts for both `user_memory_onboarding_dm_state` and `mattermost_user_setup_state`.
   - `tools/mattermost_review_log.py ensure-headers --dry-run` should report `missing=[]` and should not need to rewrite headers unless the schema intentionally changed.
   - `tools/mattermost_review_log.py lookup-user <known-admin-id>` should resolve the known admin identity.

6. **Policy lookup smoke tests**
   Test at least:
   - known admin exact sender id: `found=true`, `active=true`, allowed decision.
   - known employee exact sender id: `found=true`, `active=true`, allowed decision.
   - employee with Drive/Google Group-derived document-access evidence: doc summary present.
   - unknown exact sender id: fail closed (`found=false`, `active=false` or sub-agent `allowedForScopedWork=false`).

7. **Gateway bridge config and tests**
   - Confirm active `config.yaml` points to Hermes-native paths:
     - `pd_one_hermes_policy_root: /home/prodesign/.hermes/profiles/pdone`
     - `pd_one_policy_cache_users: /home/prodesign/.hermes/profiles/pdone/policy-cache/mattermost/users`
   - Confirm the old OpenClaw cache path is not still present in active config.
   - Run focused Mattermost gateway tests for policy bridge injection, missing-cache fail-closed behavior, and channel scopes.

8. **Sub-agent-safe handoff**
   - Use `tools/build_subagent_policy_context.py` to build least-privilege context for internal delegates.
   - The output should include summary authorization, safe scopes, approval boundaries, and document summary counts only.
   - It must not expose raw document lists to sub-agents.
   - Unknown users must produce `allowedForScopedWork=false`.

9. **Restart discipline**
   - Do not restart PD One/Hermes/OpenClaw gateway just because config or cache validation happened.
   - Check config mtime and active gateway process start time first.
   - If a restart is needed because runtime config/code changed, ask Andy/admin for explicit restart approval unless the gateway is already unresponsive.

## Common pitfall

After a gateway restart or context compression, resume from the implementation phase and verify current file/process state instead of answering as if the user asked only for a recap. Keep a checklist or todo state for multi-phase permission migrations and continue until the requested phase is actually complete.

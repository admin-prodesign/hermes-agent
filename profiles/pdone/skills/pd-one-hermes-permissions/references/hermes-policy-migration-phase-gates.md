# Hermes-native PD One permission migration phase gates

Use this reference when migrating PD One/Mattermost permission artifacts from OpenClaw paths into the active Hermes profile, or when resuming such work after a gateway restart/context compression.

## Resume discipline

- Resume from the active task list and latest explicit user instruction, not from a generic recap.
- Verify current filesystem/config/process state before claiming where the migration stands.
- Continue through the named phase target unless blocked by an approval gate or unavailable source.

## Minimum phase gates

1. **Diff/classify**
   - Compare canonical users/roles/channels/self-heal policy files.
   - Compare generated exact-sender user caches separately from canonical policy.
   - Ignore volatile generated fields such as timestamps/source hashes when classifying semantic diffs.
   - Treat added Google Workspace document-access evidence as access evidence, not automatically as a privilege-policy mismatch; still fail closed for sensitive red lines.

2. **Hermes-native tool verification**
   - Verify migrated policy/cache/review-log/tracker tools import and show help from the Hermes profile.
   - If a migrated helper imports an OpenClaw-only support module, add a Hermes-profile shim or port the module so the tool is runnable from the active profile.

3. **Regenerate evidence**
   - Regenerate Google Workspace document-access cache.
   - Regenerate Mattermost exact-sender policy cache and employee mirror.
   - Preserve machine receipts: ok flag, counts, output paths, source/document cache hash.

4. **Operator-visible tracker dry-runs**
   - Dry-run `user_memory_onboarding_state_sync.py` for onboarding/setup tracker tabs.
   - Dry-run review-log header/lookup paths so governance Sheets remain usable.

5. **Smoke tests**
   - Test at least admin, ordinary employee, employee with Drive/Group-derived document access, and unknown user.
   - Verify unknown users fail closed.
   - Verify sub-agent context exposes summaries only, not raw document lists.
   - Run Mattermost gateway policy/channel tests against the intended policy paths when available.

6. **Cutover prep**
   - Verify config points at the intended Hermes profile policy/cache paths.
   - Compare config mtime with gateway process start time before asking for a restart.
   - Do not restart the Hermes/PD One/OpenClaw gateway without Andy’s approval unless it is already unresponsive.

7. **Sub-agent-safe handoff**
   - Build a least-privilege package from one exact Mattermost sender id.
   - Include authorization decision, roles/safe scopes, channel/data summaries, document summary counts, approval boundaries, and worker rules.
   - Exclude raw policy internals and raw document lists.
   - Require workers to return receipts/statuses and escalate writes/sends/config/policy/source changes back to PD One for approval and verification.

## Reporting

- Write a compact completion report with artifacts, test results, restart status, backup commit if any, and remaining governance caveats.
- If runtime-defining durable Hermes state changed, back it up to the private Hermes repo and report the commit hash.

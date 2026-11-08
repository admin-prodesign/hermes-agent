# Mattermost allow-list additions

Use when Andy/admin approves adding a Mattermost user to PD One/Hermes allow-list policy.

## Evidence and identity

1. Authorize the requester by the injected exact sender-id bridge or cache first.
2. Resolve the target by exact Mattermost user id, not username/name alone. Reliable evidence includes:
   - existing `mattermost-users.json` / policy-cache entries;
   - Mattermost system posts such as `system_add_to_channel` with `props.addedUserId` and `props.addedUsername`;
   - deterministic Mattermost API/user metadata when available.
3. For an Andy/admin-approved **channel-wide playbook participant grant** (for example “authorize anyone in this channel for this scheduling playbook”), enumerate the current channel members through deterministic Mattermost API evidence, then add each missing active human by exact Mattermost user id. Do not turn the admin statement into name/fuzzy authorization; the durable policy entry still must be keyed by exact sender id, with channel/playbook scope and least privilege.
4. Only after the exact Mattermost id is known, cross-reference HR/AppSheet using strict email matching (`Mattermost email` -> `HR_Employees[Company Email]`) for language, PersonID, and display metadata. Do not infer identity by Chinese/English name.
4. If the live Mattermost API resolves an exact user id + username + email, but the matching HR/AppSheet row has blank `Company Email` / `Appsheet Email`, do **not** silently fall back to name-based authorization. For an Andy/admin-approved allow-list addition, you may still prepare the policy entry keyed by the exact Mattermost id, record the Mattermost API email and the HR `PersonID` as contextual metadata, and include an explicit note that future authorization is by exact Mattermost id only until HR email fields are repaired. Treat the blank HR email as a data-quality caveat, not as proof that the Mattermost user is unresolvable.

## Choosing privileges

- If Andy says “similar to <employee>,” inspect that employee’s current policy profile and copy the class of roles/scopes intentionally.
- Preserve least privilege: read-only operational roles by default; keep `writes`, `destructive`, `externalSends`, `gatewayRestart`, `policyChanges`, and `configChanges` false unless Andy explicitly approved that capability.
- Add channel access only when it is supported by the requested similarity or exact channel evidence. For R&D/Eric Lee-like access, the observed pattern was `key_employee_operations`, `product_quality_readonly`, and `operational_employee_default`, plus R&D/mold-engineering read-only when channel evidence exists.

## Combined Google Groups + PD One onboarding

When Andy/admin asks whether a new employee has been added to relevant Google Groups and onboarded for PD One, handle the two layers separately and report partial completion explicitly:

1. **Google Groups / document access layer:** list the relevant Google Groups, inspect current membership, dry-run the add when practical, perform the approved add, then verify by listing the group again and confirming the target email appears with the expected role. For Production Scheduler, the current group is `production-scheduler@prodesign-group.com`; `all-company@prodesign-group.com` may include this as a nested group, so verify the department group membership first rather than assuming all-company membership is enough.
2. **PD One exact-sender policy layer:** resolve the exact Mattermost user id from reliable evidence (for example new-employee introduction alert/log or live Mattermost metadata) and update canonical `mattermost-users.json`; Google Group membership alone does not onboard the user for PD One chat access. The inverse is also true: removing someone from a department Google Group does not deactivate their Mattermost allow-list. For a departure, set that exact id's `status` to `inactive`, regenerate cache, and require lookup `active=false`, `decision=inactive_user`, and `dmEnabled=false`. Portal ACL is a third layer: refresh `policy-cache/portal/google-group-members.json` after the live group removal. Full steps are in `pd-one-admin` → `references/employee-termination-resignation-playbook.md`.
3. If one layer succeeds and the other is blocked (for example command-approval blocks the policy write), do **not** describe the overall onboarding as complete. Report the Google Groups receipt separately from the PD One policy/cache status and name the exact remaining action.
4. Do not restart the gateway for group membership or policy-cache work unless separately approved.

## Apply and verify

1. Dry-run the exact JSON entry for Andy/admin when practical.
2. Update the canonical source: `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-users.json`. Do not hand-edit generated cache as the source of truth.
3. Validate JSON (`python3 -m json.tool ...`).
4. Run `python3 tools/mattermost_policy_lookup.py generate-cache` from the Hermes PD One profile root (`/home/prodesign/.hermes/profiles/pdone`).
5. Verify lookup for the exact target id: `found=true`, `active=true`, expected `decision`, `dmEnabled`, `language`, roles/scopes/channels, and `sourceHash`.
   - The deterministic lookup CLI requires the subcommand: `python3 tools/mattermost_policy_lookup.py lookup <mattermost_user_id>`. Do not call it as `mattermost_policy_lookup.py <id>`.
   - If piping JSON into another interpreter would trigger command-approval friction, run a small Python `subprocess.run([...,'lookup', id], stdout=PIPE)` wrapper or read back `policy-cache/mattermost/users/<id>.json` directly.
6. For 管理部/general employee setup where Andy did not name a specialized class, prefer the least-privilege `operational_employee_default` profile with exact Mattermost id + strict HR `Company Email` evidence. Add only department-specific/specialized roles when Andy explicitly approves that scope or reliable policy precedent exists.
7. If a policy write or cache generation command is stopped by the command-approval layer, do not claim the user was enabled. Report the prepared identity/role plan, the exact blocker, and that no permission change is live yet; wait for approval rather than retrying through another path.
8. Commit and push the durable Hermes profile policy/cache change to the configured private Hermes backup repo; stage only relevant policy/cache files and avoid unrelated dirty-tree noise. The active profile root may not itself be a Git checkout; on this host the backup helper `/home/prodesign/hermes-backup/scripts/commit-hermes-backup.sh "<message>"` is the normal receipt path.
9. Review-log helper may return `skippedAndyRows` for Andy/admin approval rows; that is expected and not a failure.
10. Do not restart the gateway unless explicitly approved or already-unresponsive under the standing exception.

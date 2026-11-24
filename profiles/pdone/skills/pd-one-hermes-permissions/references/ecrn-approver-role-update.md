# ECRN approver role update pattern

Use this reference when Andy/admin asks to narrow or adjust Mattermost ECRN approval participants.

## Durable lesson

Do not use broad department roles like `sales_member` directly as required approval authority when the workflow needs a narrower approval subset. Add or use a workflow-specific role such as `ecrn_approver`, then make deterministic runners require both the department/lead role and the workflow role.

## Safe sequence

1. Confirm requester authorization by exact Mattermost sender ID and verify the injected PD One permission bridge context shows admin/policy-change approval authority.
2. Read canonical Hermes PD One policy files as needed:
   - `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-users.json`
   - `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-roles.json`
3. Resolve requested usernames to exact Mattermost user IDs from `mattermost-users.json`. Never assign by display name or fuzzy match.
4. Add or update a workflow-specific role in `mattermost-roles.json`, e.g. `ecrn_approver`, with narrow scope only:
   - channel-limited to `~ecrn` (`o37eouyp5j85by4m1m11zukwpy`)
   - no general data access
   - no source writes, external sends, policy/config authority, or destructive authority
5. Assign the workflow role only to the approved users in `mattermost-users.json`.
6. Update deterministic workflow code so required approvers are the intersection of the operational role and workflow role, for example:
   - Sales stage: `sales_member` + `ecrn_approver`
   - downstream stages: scan the ECRN form’s `會辦單位` checkbox area and require `ecrn_approver` plus the mapped department role(s); current mapped examples include QA lead, Injection Molding lead, Logistics lead, and Finance BU member/manager. Checked but unmapped units must be logged for admin mapping instead of being silently dropped.
7. Regenerate policy cache from canonical files; do not edit generated cache by hand:
   - `python3 /home/prodesign/.hermes/profiles/pdone/tools/mattermost_policy_lookup.py generate-cache --no-employee-mirror`
8. Dry-run the workflow runner and verify counts/usernames before sending. If the runner previously cached a failed form scan (`routing_checked_from_form.ok=false`), fix the parser/converter and let it retry rather than treating the failed scan as final. For `.doc` form conversion, shell-quote the full `/work/<filename>` path with `shlex.quote`; do not use empty-string replacement tricks because they can corrupt CJK/space filenames.
9. Execute the approved send/action and capture receipt IDs.
10. Update the relevant runbook and commit/push the durable workspace changes. No gateway restart is needed unless the changed component actually requires it.

If the mapped department lead is inactive, the runner counts zero signers for that unit and cannot finish electronically. To staff Injection Molding ECRN signing, assign both `injection_molding_lead` and `ecrn_approver` to the exact active Mattermost user id; `ecrn_approver` alone is not counted.

## Example from 2026-06-03

Andy narrowed Sales ECRN approvers to `@yvonne`, `@danielhsu`, `@apple`, `@hui`, `@tsengliming`, and assigned downstream leads `@lydia`, `@m00713`, `@hsu`. The ECRN runner was changed to count Sales approvers only when users had both `sales_member` and `ecrn_approver`; downstream lead approvals also required `ecrn_approver`. Verification showed counts Sales=5, QA=1, Injection Molding=1, Logistics=1 before re-sending the narrowed Sales approval request.

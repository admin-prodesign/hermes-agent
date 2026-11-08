# Mattermost channel purpose and access setup

Use this when Andy/admin adds PD One to a Mattermost channel and asks to infer the channel purpose or configure which roles may use channel search/summary/analysis.

## Workflow

1. **Inspect the live channel, not memory.** Use Mattermost API credentials from the active PD One profile `.env` without printing secrets. Fetch channel metadata plus recent posts. Summarize only the task-relevant channel pattern; avoid raw transcript disclosure in the final answer.
2. **Purpose field:** for Mattermost Channel Purpose rewrites, follow `policies/mattermost-channels.md`: Chinese first, then English, concise safe margin under the server limit (target <=240 characters total). Verify by reading the channel back after the API update.
3. **Access recommendation:** compare observed channel use against existing `policies/mattermost-roles.json` role scopes and current channel members from Mattermost. Prefer class-level roles, not one-off user grants. Identify unprofiled current members separately; do not infer privileges from usernames/names.
4. **When Andy says “set it up”:** update canonical policy, not generated cache:
   - Add a channel section to `policies/mattermost-channels.md` with approved roles, purpose, historical-use summary, allowed work, and guardrails.
   - Add channel entries and any needed `dataAccess` notes to the relevant roles in `policies/mattermost-roles.json`.
   - Keep `operational_employee_default` insufficient by itself for channel-history search unless Andy explicitly wants a broad default channel.
5. **Regenerate and verify cache:** run `python3 tools/mattermost_policy_lookup.py generate-cache` from `/home/prodesign/.hermes/profiles/pdone`, then lookup exact Mattermost IDs for representative users/roles to confirm the new channel access appears. A gateway restart is not normally required for policy-cache regeneration.
6. **Verify multi-role collisions, not just role snippets:** when a user has several roles, a narrower role such as `key_employee_operations` can mask or overwrite a more specific role grant in the generated effective cache, depending on merge order. Always verify representative exact users with realistic multi-role combinations (for example production + key-employee, QA + product-quality, logistics + scheduler) and one default-only negative control. If a specific role should win, adjust the narrower fallback grant wording/access so it is not more restrictive than intended for multi-role users, or add a role-specific channel grant that survives cache generation.
7. **Backup durable runtime state:** sync changed policy files and regenerated policy-cache files to the private Hermes backup repo when present, then commit and push when the helper reports changes. If the helper says there is nothing to commit, verify the backup copy matches the edited policy files and report the existing backup commit as the receipt.

## Guardrails to encode in new channel sections

- Require explicit PD One mention unless Andy defines the channel as free-response/admin.
- Mattermost channel replies remain bilingual per global policy.
- Treat private channels as channel-scoped: no unrelated channel summaries or private data unless Andy/admin approves the lookup.
- Default to read/search/summarize/analyze/draft. External sends, source-system writes, inventory/ERP/AppSheet/Sheet changes, delivery/customer commitments, destructive actions, Drive permission changes, and admin/runtime/config changes stay approval-gated with dry-run where practical.
- Do not expose credentials, private memory, raw transcript dumps, unrelated HR/personnel/finance data, or admin internals.

## Example: Sales & Logistics channel

For `業務&資材 | Sales & Logistics`, a good policy shape was: `sales_member`, `production_scheduler`, `facilities_logistics_lead`, and `facilities_logistics_assistant` get channel-scoped search/summary/analysis/drafting; `key_employee_operations` is only when the requester is an active channel member or Andy/admin-approved; `admin` and `executive_data_access` retain broader authority; `operational_employee_default` alone is not enough for channel-history search.
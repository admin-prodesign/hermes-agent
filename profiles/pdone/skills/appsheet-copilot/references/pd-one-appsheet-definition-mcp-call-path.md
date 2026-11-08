# PD One AppSheet definition inspect/apply (MCP)

Hermes-agent release `tools/pd_one_safe_ops_mcp.py` exposes typed `pdone_safe_ops` tools (admin-prodesign/hermes-agent). Do not copy MCP Python into the profile; registry points at the release CLI/MCP siblings.

## When to use

- Read-only editor definition state (latest vs stable, structure counts, validity flags): **inspect** before advising or planning edits.
- Staged definition save/promote after Andy approves a PDAPP ticket: **apply** only through the ticket-gated path.

Shared Mattermost rooms are OK for Andy/admin when the MCP tool is visible; use MCP instead of `terminal`, `execute_code`, or ad hoc `/api/saveapp` scripts. This does **not** loosen `pd_one_sender_tool_gate` or card-guard rules.

## Call sequence

1. **`mcp__pdone_safe_ops__pd_one_appsheet_definition_inspect`** (or `pd_one_appsheet_definition_inspect` after tool search). Optional `app_id`, `app_name`, `version`. Read-only; no saveapp.
2. Build a patch envelope JSON under PD One `cache/`, `cache/scratch/`, definition snapshots, or `logs/appsheet-definition-ops/` with bounded `patch_id`, `app_id`, `proposed_app_path`, optional `proposed_app_sha256`, `change_summary`, and `promote_stable`.
3. **`mcp__pdone_safe_ops__pd_one_appsheet_definition_apply_approved`** with `patch_envelope_path` and default **`dry_run=true`**. Review the plan receipt (before/after sha, structures, would_change).
4. After **`PDAPP-YYYYMMDD-XXXXXXXX`** is executable and the grant includes **`appsheet_definition_apply`** with the **exact** `patch_id` and `app_id` in ticket scope, call apply again with **`dry_run=false`**, **`ticket_id`**, and **`confirm_live_write='RUN LIVE APPSHEET DEFINITION APPLY'`**.
5. Report live receipts: snapshot path, save/readback, stable promotion if requested, ops receipt under `logs/appsheet-definition-ops/`, or rollback outcome on failure.

CLI fallback (same release module): `appsheet-definition-inspect`, `appsheet-definition-apply --dry-run|--live`.

## Do not

- Bypass the ticket grant or confirmation phrase for live writes.
- Use employee-lane AppSheet record ops or Data API Add paths for editor definition changes.
- Assume it-work channel prompts still ban definition writes; ticket + MCP apply is the approved admin path when scoped.

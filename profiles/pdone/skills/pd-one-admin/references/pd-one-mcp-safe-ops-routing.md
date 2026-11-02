# PD One MCP safe-ops routing

Use this when PD One admin/safe-ops work would otherwise use raw shell, `execute_code`, pipe-to-interpreter parsing, or profile-local safe wrapper scripts.

## Rule

Prefer typed MCP tools from `pdone_safe_ops` when they cover the task. Fall back to profile-local safe wrappers only when no MCP tool exists or the current live session has not loaded the MCP tools. Live writes, permission changes, external sends, gateway restarts, and source-system mutations remain approval-gated.

**Name lookup:** deferred tools are `mcp__pdone_safe_ops__<short>`. Always `hermes_tool_search` / `tool_search` first, then `tool_describe`/`tool_call` with the **exact** catalog name. Never `tool_describe(["pd_one_sheets_batch_update"])` or other short names. A short-name `not_found` is a lookup miss, not a missing capability — retry search; do not report MCP unavailable. Employee-lane Sheets/Docs writes stay on this MCP path; do not unblock `terminal` because a Google Group has editor access.

## Available typed tools

The MCP server is configured in `/home/prodesign/.hermes/profiles/pdone/config.yaml` as `mcp_servers.pdone_safe_ops` and implemented by the Hermes-agent release `tools/pd_one_safe_ops_mcp.py` (release interpreter), backed by release `tools/pd_one_ops/pd_one_safe_ops.py`. Profile `tools/pd_one_safe_ops_mcp.py` copies are retired.

| Need | Prefer MCP tool |
|---|---|
| Capability registry | `pd_one_capability_registry` |
| Dangerous-command audit/proposals | `pd_one_dangerous_command_audit` |
| Google group member reads/filters | `pd_one_google_group_members` |
| Google group create/member add/remove previews | `pd_one_google_group_change_dry_run` |
| Google Docs header/revision/changelog reads | `pd_one_google_docs_metadata_inspect` |
| Registry-bounded Google Docs inspect/dry-run/live edits | `pd_one_google_docs_document_ops` |
| Auth-browser/container status | `pd_one_auth_browser_status` |
| Mattermost policy dry-run diff | `pd_one_policy_change_dry_run` |
| Approved-path DOCX/PPTX/PDF extraction | `pd_one_doc_extract` |
| AppSheet editor definition inspect (loadApp, read-only) | `pd_one_appsheet_definition_inspect` |
| Ticket-gated AppSheet definition save/promote (dry-run default) | `pd_one_appsheet_definition_apply_approved` |
| Cached dest rest-count | `pd_one_cached_dest_rest_count` |

## Fallback order

1. MCP typed tool, if visible in the current tool list and scoped to the task.
2. Profile-local safe wrapper with dry-run/readback defaults.
3. First-class CLI command with bounded flags and no pipe-to-interpreter glue.
4. `read_file`/`search_files`/`patch`/`write_file` for transparent local file work.
5. Raw `terminal` only for commands that are already narrow, auditable, and not better covered above.
6. Avoid `execute_code` for production/admin mutations unless there is no safer route and the approval scope is explicit.

If the capability registry/MCP discovery shows a typed tool but the current session tool schema does not expose it, treat that as a stale tool-inventory problem—not permission to use `execute_code`. Use an already-implemented bounded safe wrapper if available; otherwise stop and route through admin handoff or request the approved MCP reload/new-session path. Never surface an internal dangerous-command prompt in an employee thread.

### Approval-ledger exception to the fallback order

Approval-ticket mutation is a trust-boundary operation, so the generic fallback order above does not authorize a model to invoke a legacy ticket CLI. Use typed read-only tools for status/listing. For `approve`, `reject`, `claim`, `complete`, or `fail`, require either the deterministic Mattermost approval listener or a narrow admin-only typed capability whose backend re-fetches and verifies the trusted decision post.

The decision backend should accept only the ticket ID and source decision-post ID from the caller. It must re-fetch the post and derive the decision, instructions, sender, channel, and thread server-side; verify exact active-admin sender ID, exact accepted text, bound Admin thread or intentionally allowed exact ticket-origin thread, current ticket state, and idempotency; then return a state-transition readback. Caller-supplied identity or decision text must never be authoritative. MCP is only the bounded adapter and does not itself constitute authorization.

If no such transition capability is visible, stop with a concise “approval not recorded / capability unavailable” status and point to the bound approval handoff. Never substitute `execute_code`, terminal, inline Python, shell passthrough, or `admin_approval_tickets.py decide`. Approved work must then dispatch only to the registered capability named by the ticket—not to a generic command runner.

### Implemented PDAPP decision path

- Gateway hook: `hooks/pd-one-admin-approval-listener` (`agent:start`). It runs only for Mattermost, exact Andy sender ID `5nak6m7nmf8kudbrwbtccazbgc`, an explicit `admin: approve PDAPP-...` / `admin: reject PDAPP-...` command, and a stable platform `message_id` receipt.
- Typed MCP: `pd_one_admin_approval_decide(ticket_id, decision_post_id, dry_run=True, confirm_live_write=...)`.
- Server trust boundary: the tool re-fetches `decision_post_id` from Mattermost and derives sender, current message, channel, root/thread, and decision. It does not accept caller-supplied identity, decision, instructions, channel, or thread.
- Accepted bindings: the ticket-bound Admin approval thread or the exact origin channel/root stored in the ticket. Origin-thread decisions require the explicit ticket ID; bare approvals are never guessed there.
- State transition: valid approval records `decision_recorded` and idempotently enqueues `approved → queued`; rejection records `rejected`. The tool does not execute the approved capability in-process. After a live enqueue it kicks `pd-one-admin-approval-executor.service` (`--no-block`). The oneshot claims, executes, posts the origin receipt, and completes the ledger. Kanban is only for tickets with `capability_scope.execution_plane=kanban`.
- Replay behavior: source post ID is the idempotency key. Same-post/same-decision replay is a no-op readback; a changed decision on the same post is rejected.
- Fail closed: missing post receipt, wrong sender/thread/ticket, quoted command, invalid text, stale ticket, or MCP/hook unavailability cannot mutate the ledger and must never trigger a shell/CLI fallback.
- Activation: adding or modifying a gateway hook requires an explicitly approved healthy-gateway restart. MCP server changes require MCP reload/discovery; do not imply that source files alone activated an already-running gateway process.

### Source placement and rollout order

1. Keep new approval parsing/validation authority in the Hermes-native profile, such as `tools/pd_one_admin_approval_listener.py`. A legacy workspace may remain a ledger dependency during migration, but do not place the only maintained copy of new logic under a backup-excluded legacy tree.
2. Treat **built**, **fresh-process verified**, and **active in the running gateway** as separate states. Unit tests plus `hermes --profile pdone mcp test pdone_safe_ops` prove source/discovery; `scripts/verify_pdapp_decision_mcp.py` proves a real dry-run transport call; neither proves the existing gateway loaded the new MCP schema or hook.
3. Update the capability registry/runbook and durable backup after tests, then request explicit healthy-gateway restart approval. After restart, verify hook discovery, gateway health, Mattermost listener health, and one non-mutating canary before calling the prevention path active.
4. Do not use a historical production ticket as a convenient live smoke test when the underlying approved workflow may already be running. Dry-run the exact post or use an isolated fixture. Reconcile an old `pending` ticket only after checking executor/cron state and duplicate-execution risk; restart approval does not implicitly authorize historical ledger reconciliation.

## Current coverage notes

- Google Groups: use `pd_one_google_group_members` for reads and `pd_one_google_group_change_dry_run` for previews. Preview-only is not live apply approval.
- Google Docs metadata: use `pd_one_google_docs_metadata_inspect` for header text, revision ID, and bounded changelog reads. Do not import legacy `docs_api.py` through `execute_code` for this readback.
- Google Docs live edits: use `pd_one_google_docs_document_ops` for registered manuals. It defaults to dry-run; typed write actions require an exact registered requester, a fresh `expected_revision_id`, a stable `idempotency_key`, exact `confirm_live_write='RUN LIVE GOOGLE DOCS DOCUMENT OPS'`, and successful post-write readback. It never accepts raw `batchUpdate` arrays and does not cover sharing/permissions, Drive moves, document deletion, comments, or suggestion resolution. If the tool is absent from the current session inventory, use the existing bounded module only through an approved safe route or stop/escalate—never fall back to arbitrary `execute_code`.
- Mattermost policy: use `pd_one_policy_change_dry_run` for exact-user/scope/role diffs before any policy write.
- Auth browser: use `pd_one_auth_browser_status` instead of ad-hoc `docker`/`curl`/`ss` probes.
- Document extraction: use `pd_one_doc_extract` only for approved PD One document roots; still apply normal privacy/scope checks.
- AppSheet editor definition writes: use `pd_one_appsheet_definition_inspect` then `pd_one_appsheet_definition_apply_approved` (dry-run first). Live apply needs PDAPP grant `appsheet_definition_apply` bound to exact `patch_id`+`app_id` and `confirm_live_write='RUN LIVE APPSHEET DEFINITION APPLY'`. See `appsheet-copilot/references/pd-one-appsheet-definition-mcp-call-path.md`. Row/Data API writes stay on `appsheet_record_ops` and existing approval gates.
- Cached dest rest-count: use `pd_one_cached_dest_rest_count` for named-worker `V` counts on a tmp Sheets dump; do not `execute_code` `r[6:]` loops.
- AppSheet row ops, Google Sheets, Drive, and live group changes are not automatically covered unless a typed MCP tool exists for that exact operation; keep existing safe wrappers and approval gates.

## Dangerous-command prompt forensic triage

When an admin links a Mattermost post and asks why a dangerous command ran, do not assume execution merely because an approval card exists.

1. Inspect the exact linked post/thread first through an exact-requester, live-membership-checked Mattermost read path. Keep the lookup bounded to that post/thread.
2. Correlate the approval card with the command approval-hook event using timestamp, command hash/run ID, session key, tool-call ID, and command excerpt where available.
3. Read the Hermes approval/audit outcome and execution receipt. Distinguish clearly among:
   - **prompted/attempted** — approval was requested;
   - **blocked/denied/timed out** — the command body did not run;
   - **approved and executed** — require the actual tool result or side-effect receipt;
   - **auto-approved** — require the recorded approval outcome and tool result rather than inferring from nearby chat text.
4. Treat `tool_calls_made=0`, `blocked_timeout_denied`, or equivalent as proof that the linked attempt did not execute. Do not describe it as “a dangerous command was run.”
5. Explain operational intent separately from safety classification: what the agent was trying to verify, why the generic command shape was flagged, and whether it was actually necessary.
6. Identify the correct typed/safe route. If one exists, run its read-only/dry-run verification and report that receipt. If no bounded capability exists, record a wrapper gap; do not retry, rephrase, or bypass a denied command through another tool.
7. Report minimally: exact linked post, intended purpose, approval outcome, execution count/side effects, and safe replacement route. Avoid raw thread/session dumps and full command bodies.

For fixture matrices and repeated validation, prefer a fixed-case typed `check`/`sweep` action over ad hoc `execute_code` loops that spawn subprocesses merely to aggregate JSON.

## Verification

- Run `hermes --profile pdone mcp list` or `hermes --profile pdone mcp test pdone_safe_ops` when diagnosing tool availability.
- If a config/tool change is made, validate and back up durable state. Do not restart a healthy PD One gateway without Andy's explicit approval.
- Report which route was used: MCP tool, safe wrapper fallback, or approval-gated manual path.
- For dangerous-command investigations, cite both the source post/thread and the approval/audit execution outcome; neither alone proves what ran.

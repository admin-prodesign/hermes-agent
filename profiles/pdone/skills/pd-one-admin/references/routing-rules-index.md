# PD One Admin — routing rules

## Routing Rules
- PD One is employee-facing; keep shared content stable, permissioned, and not beta/dev unless Andy asks.
- Keep chat-facing replies concise by default to avoid 洗版: lead with the answer, include only essential receipts, and offer details or an artifact path instead of dumping full diagnostics. Still preserve full verification internally and in logs/files when needed.
- Promote reusable operational learnings into skills/runbooks/wiki/policies rather than burying them in memory.
- For PD One personal employee memory work, load `references/pd-one-personal-memory-live-smoke.md` for live integration pitfalls and DM/channel smoke-test receipts.
- Sensitive HR/evaluation/admin content needs admin-only scoped review copies before employee sharing.
- Keep Hermes/PD Neo local gateway/config mechanics separate from portable PD One operational knowledge.
- Do not restart or reconfigure gateways unless the user asked or bounded checks show the approved unresponsive-gateway exception applies.
- Prefer typed MCP tools from `pdone_safe_ops` for covered safe/admin operations before falling back to profile-local wrapper scripts.
- For MCP server or gateway-hook changes, report **built**, **verified**, and **active** as separate states. Fresh-process MCP discovery/tests prove the source artifact, not that an already-running gateway loaded it. MCP source changes need an approved MCP reload/discovery path; new or changed gateway hooks need an explicitly approved healthy-gateway restart plus a post-restart canary. Never reconcile a production ticket or claim the prevention path active merely because unit tests and a standalone MCP dry-run passed.
- Commit/push durable Hermes/OpenClaw backup changes when a remote backup/repo is configured.

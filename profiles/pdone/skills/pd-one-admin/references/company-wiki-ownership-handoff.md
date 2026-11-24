# Company wiki ownership handoff: Hermes owns, PD One consumes

Use this reference when planning or executing a Pro-Design company wiki migration between PD One/OpenClaw and PD Neo/Hermes.

## Durable lesson

Do **not** treat “remove the wiki from PD One” as “employees can no longer ask PD One wiki questions.” The desired architecture separates canonical ownership from permitted access:

- **PD Neo / Hermes owns the canonical company wiki**: imports, structure, page creation, provenance, lint, exports, backups, cron upkeep, and documentation debt.
- **PD One remains an employee-facing front door**: it may query or expose permitted wiki content on behalf of employees when channel/user policy allows.
- **PD One should not retain canonical write/maintenance authority** after cutover unless Andy explicitly re-enables it.

## Preferred architecture

1. Canonical Hermes vault, e.g. `/home/prodesign/.hermes/company-wiki/main`.
2. Permissioned exports generated from the canonical vault, e.g. `admin`, `manager`, and `staff` profiles.
3. PD One reads only an allowed export/profile for employee-facing answers, or calls a controlled Hermes query service later.
4. Legacy OpenClaw vault remains read-only historical/rollback source after cutover.
5. Migration state belongs outside the canonical/exported vault in a Hermes-owned workspace such as `/home/prodesign/.hermes/company-wiki/migration/` with `staging/`, `quarantine/`, manifests, and hash baselines.

## Migration planning pattern

When drafting or implementing the handoff, use a staged/fail-closed plan rather than a direct copy:

1. Inventory current PD One wiki, OpenClaw config, mirror repo/checkout, cron entries, and baseline lint/compile state.
2. Capture source hashes, OpenClaw config hash, and current mirror commit before migration.
3. Import into `migration/staging/` first. Do **not** run `rsync --delete` directly into canonical `main/`, because it can delete Hermes-only files like `SCHEMA.md`, `log.md`, `_meta/`, and `raw/`.
4. Classify staged pages before promotion. Quarantine bridge memory, user memory, Mattermost/runtime/history, HR/private, review-log, payroll, raw transcript/log, and admin-policy-heavy pages unless explicitly approved.
5. Promote only reviewed pages into canonical `main/`, then restore/verify the Hermes `llm-wiki` layer (`SCHEMA.md`, `index.md`, `log.md`) and PD One provenance/access conventions.
6. Generate import manifests that include source count, staging count, promoted count, quarantined count, exclusions, and cutover status.
7. Ask for a second-pass review before treating the plan as ready; check especially for path inconsistencies, direct-delete imports, export leaks, mirror repo layout, cron races, and rollback gaps.

## Cutover rule

Before disabling OpenClaw/PD One `memory-wiki` behavior:

- Verify Hermes import, lint/search, mirror/export, cron, and backup.
- Verify PD One has a replacement **read-only, permission-filtered** wiki access path if employees should keep querying the wiki.
- Disable PD One’s wiki **ownership/write/maintenance** role first; do not delete config immediately.
- Preserve rollback by keeping the old config/vault and avoiding an OpenClaw gateway restart unless Andy explicitly approves.

## Access control guardrails

PD One employee-facing wiki answers must be based only on content allowed for the active user/channel. Filter or exclude:

- secrets and `.env` data
- raw logs/transcripts/session histories
- private memory
- employee-private notes
- admin policy mechanics
- raw Mattermost evidence unless explicitly approved and scoped
- customer/commercial/sensitive operational details not included in the relevant export profile

When uncertain, answer from the staff-safe export or escalate to Andy/admin rather than reading broader canonical/admin content into a shared channel.

Export rules:

- Do **not** create one mirror per exact employee role by default. Use canonical wiki + coarse exports (`admin`, `manager`, `staff`, and only stable/high-traffic domain exports) + runtime policy filtering.
- Non-admin exports must fail closed: missing/invalid access metadata means exclude until classified, not include by filename pattern.
- Apply `denyScopes` and `sensitivity: confidential|restricted` before positive `audience`/`scopes` matches.
- Treat `sources/`, `reports/`, `_meta/`, `raw/`, `AGENTS.md`, inbox pages, bridge-memory pages, user-memory pages, Mattermost/runtime evidence, HR/payroll/private records, and review logs as excluded from staff/manager exports unless explicitly reviewed and reclassified.
- Regression-test exports by asserting known sensitive pages are absent.

## Mirror handoff guardrails

PD One already has a private mirror workflow; preserve it until the Hermes replacement proves itself:

- Current mirror source tooling may live under OpenClaw, but Hermes replacement should adapt the existing exporter/sync rather than rewrite from memory.
- Keep the existing private mirror repo admin-only at first; do not mix admin and staff/manager GitHub access in one repo.
- If multi-profile mirroring is later approved, write profiles into separate subdirectories or separate repos by audience tier. Never `rsync --delete` a single profile over a multi-profile repo root.
- Mirror sync must verify git root, resolved path, expected remote URL, branch `main`, non-detached HEAD, clean pre-rsync worktree, and use a lock so old/new cron jobs cannot race on the same checkout.
- Staff/manager exports may be generated locally for PD One query access without being pushed to the admin mirror repo.

# PD One employee-access smoke tests

Use this whenever Andy asks to verify PD One access by pretending to be different employees, and proactively whenever creating a new employee role, editing an existing role, changing role/source permissions, or changing the access policy gate. The goal is to test likely employee-visible policy outcomes before claiming the permission change works.

## Safety boundary

- Do **not** send Mattermost/LINE/Discord messages during smoke tests unless Andy explicitly asks for delivery.
- Prefer deterministic read-only probes and local policy/tool invocation.
- If invoking a PD One plugin/tool directly, pass a synthetic context/session and a purpose such as: `Smoke test only. Read-only. Do not send messages, write, create watches, or make commitments.`
- Avoid creating schedule watches, approval tickets, cron jobs, AppSheet writes, or admin handoff messages during access-only testing.

## Representative matrix

Pick exact Mattermost sender IDs from the Hermes PD One source of truth, not display names or legacy mirrors:

- Canonical users: `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-users.json`
- Generated exact-sender cache: `/home/prodesign/.hermes/profiles/pdone/policy-cache/mattermost/users/*.json`

Cover at least:

- Sales / product quality readonly
- QA / product quality readonly
- Molding manager or production role
- Production scheduler
- Finance role
- HR role
- Unknown/unprofiled sender

Mask sender IDs in reports. Do not rely on names or fuzzy matching; PD One auth should resolve by exact Mattermost sender ID.

## Deterministic checks

1. Confirm live gateway/plugin health separately if needed:
   - `openclaw config validate`
   - `openclaw health --json`
2. Resolve authorization with the Hermes-native lookup/cache before deriving expected behavior:
   - `python3 /home/prodesign/.hermes/profiles/pdone/tools/mattermost_policy_lookup.py lookup <sender_id>`
   - Verify `found`, `active`, `dmEnabled`, `decision`, roles, safe scopes, channel access, and deny-only `dataAccess` fields.
3. Inspect or invoke the policy matcher from `plugins/pd-one-employee-safety-gate/index.js` when testing the legacy OpenClaw runtime path rather than mentally deriving roles.
4. For Sales customer-follow-up context across approved sources, use the Hermes-native read-only packet tool. It authorizes by exact Mattermost sender ID, searches only allowed source channels, returns bounded excerpts/provenance, and blocks raw transcripts/arbitrary cross-channel history:
   - `python3 /home/prodesign/.hermes/profiles/pdone/tools/pd_one_sales_customer_context_packet.py --sender-id <id> --customer '<customer>' --request '<bounded internal customer follow-up request>' --limit-per-source 5`
   - Run negative controls for finance/non-sales, unknown sender, `所有頻道`/`all channels`, and `完整對話逐字稿`/raw transcript wording.
5. For legacy Product Quality-only summary access, use the read-only source packet tool if present. As of 2026-06, this helper is still in the legacy OpenClaw workspace and reads legacy policy mirrors, so treat it as a data/tool availability smoke test and separately compare against Hermes policy:
   - `python3 /home/prodesign/.openclaw/workspace/tools/pd_one_product_quality_source_packet.py --sender-id <id> --request '<bounded internal request>' --limit 5`
6. Include negative tests for over-broad raw transcript and cross-channel requests; authorized Product Quality/Sales users should still be blocked from raw transcript dumps and arbitrary cross-channel history.
7. Verify AppSheet Lookup visibility separately when the issue involves Reference Docs/SIP/SOP. `Reference_Documents_All` being admin-only does not prove `RefDocs_MyViewable` or SIP/SOP doc-type rows are wrong.

## Pitfall: deny text can grant regex scopes

When testing or editing `pd-one-employee-safety-gate`, do not let free-text `dataAccess` descriptions grant specialist domains by regex. Examples that must **not** grant finance access:

- `payroll: deny`
- `financeRecords: deny-unless-explicitly-approved`
- descriptive text such as `no payroll, discipline, or staffing writebacks`

Scope matching should derive grants from explicit safe scopes/roles and non-deny data-access keys, not from deny-only keys or descriptive values. Add/maintain a regression test similar to `tests/pd-one-employee-safety-gate-scope.test.mjs` whenever changing this logic.

## Reporting shape

Keep the report brief:

- State that no actual messages were sent.
- List authorized/blocked outcomes by role class, not full identities.
- Call out any live-data caveat separately from PD One policy-gate behavior.
- If code/config changed, include tests run and backup commit hash.

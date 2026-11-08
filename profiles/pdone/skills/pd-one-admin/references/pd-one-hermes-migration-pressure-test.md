# PD One → Hermes migration pressure-test

Use this when Andy asks whether PD One should migrate from OpenClaw to Hermes Agent, whether Hermes can be constrained safely for employee use, or whether PD One/OpenClaw should be consulted before architectural decisions.

## Core conclusion from live PD One dialogue

A locked-down Hermes PD One can be **safety-comparable** to OpenClaw if broad tools are truly removed and profiles are isolated. Hermes is **materially better** only if it turns today’s custom OpenClaw rails into clearer platform/control-plane primitives rather than merely rehosting the same glue.

Recommended framing:

- Keep PD One constrained at the employee-facing edge.
- Let PD Neo/Hermes act as the admin learning/control plane.
- Do not migrate for “more autonomy.” Migrate only for governance, auditability, policy centralization, job ownership, memory separation, backup/skill lifecycle, and reduced custom patch burden.
- Keep OpenClaw as the production employee edge until parity is proven.

## Live pressure-test methods

When higher confidence is needed, ask the running PD One/OpenClaw runtime directly rather than relying only on memory/skills. Prefer a verified Mattermost admin DM for employee-channel behavior, and use ACP only as a control-plane/test harness unless it carries a verified identity envelope.

### Mattermost admin DM probe

Safe probe pattern:

1. Use `mattermost_review_log.py::mattermost_context()` from `/home/prodesign/.openclaw/workspace/tools` to verify Mattermost base URL and PD One bot credentials without printing tokens.
2. Use the approved admin PAT from `/home/prodesign/.openclaw/workspace/keydrop/mattermost-admin.env` for requester-side DM probes; do not paste or print the token.
3. Resolve `/api/v4/users/me` for the admin user and `/api/v4/users/username/pdone` for the bot.
4. Create/get the DM channel with `POST /api/v4/channels/direct` using `[admin_user_id, pdone_user_id]`.
5. Post a clearly admin-scoped prompt that asks PD One to answer as current PD One/OpenClaw runtime, not as an employee announcement.
6. Poll the DM channel for new bot posts created after the probe post; avoid treating older bot posts as the response.
7. Record post IDs and summarize conclusions, but do not auto-post externally or change production behavior.

### ACP direct probe

Use ACP to test runtime/channel assumptions and fail-closed behavior, but do **not** treat ACP as employee authentication. ACP may appear as `cli`, WebChat, or ACP metadata rather than a Mattermost employee sender ID.

Safe ACP probe pattern:

1. Target the employee assistant through an explicit ACP session such as `agent:employee-assistant:<probe-name>` and reset the session for clean results.
2. Use the employee workspace when probing employee-facing behavior: `/home/prodesign/.openclaw/workspace-employee`.
3. Suppress non-JSON notes/warnings when using a raw ACP stdio client; otherwise config warning banners can corrupt the JSON stream.
4. In the prompt, explicitly require direct ACP text and forbid `message`/send/tool use if you want the response in the ACP transcript rather than posted elsewhere.
5. Make client-side callbacks fail closed during the probe: deny permission, filesystem, terminal, and unknown callbacks unless the test specifically needs them.
6. Ask whether the runtime perceives source/platform/sender identity, whether ACP changes the Mattermost answer, and what ACP-specific cutover gates are required.

Key ACP lesson: **ACP is runtime proximity, not user identity.** It is useful for evaluation, refusal tests, and control-plane harnesses, but it must not unlock scoped employee data unless Hermes/OpenClaw receives a verified identity packet equivalent to the channel-native sender ID.

## Questions that exposed useful constraints

Ask PD One to critique these points:

- Which current PD One/OpenClaw capabilities or safety rails would be hardest to preserve in Hermes?
- Which parts of current PD One are OpenClaw-specific rather than generic agent behavior?
- What would PD One require before trusting a Hermes cutover?
- If Hermes can disable toolsets and isolate profiles, is that materially better than OpenClaw agents/tool profiles or mostly equivalent?
- What migration risks would justify keeping OpenClaw as the employee-facing edge?
- Which Hermes features would be clear improvements if implemented safely?

## Findings to carry forward

PD One identified these hard gates before any employee-facing Hermes cutover:

- **Mattermost identity/routing:** Preserve immutable requester sender ID, DM/channel visibility, thread context, channel context, and visible delivery behavior. A generic bridge is weaker unless it preserves/signs this context per request.
- **ACP/control-plane identity:** ACP should be treated as a test/control-plane surface by default. Session keys, labels, usernames, or `cli` metadata must not authorize employee data; ACP must carry a verified identity envelope before it can stand in for a channel-native employee identity.
- **Approval rails:** Tool disabling reduces blast radius but does not replace wrapper-enforced approval flows such as `request_approval`, scoped specialist handoff, SOP approval packets, and schedule/watch wrappers.
- **Review log and missed-message handling:** Hermes needs durable logs/queues for denials, approvals, capability gaps, missed replies, attachment audit rows, closure states, retry visibility, and corrective replies. Chat/tool logs alone are insufficient.
- **Attachment/thread grounding:** Preserve the distinction between generated, uploaded, and delivered artifacts. Mattermost delivery claims require real created posts and non-empty `file_ids`; replies must preserve correct DM/thread context.
- **Memory:** Hermes is only safer/better if employee memory is explicit, private, inspectable, forgettable, and profile-isolated. Silent absorption of employee DMs into admin/control-plane memory is a blocker.
- **Cron/jobs:** Do not expose arbitrary cron creation to employee PD One. Only scoped domain watches/jobs should be available, ideally owner-bound, centrally visible, cancellable, expiring, and policy-audited.
- **Auditability:** Prefer structured immutable audit events for identity resolution, policy decision, denial, approval, handoff, tool call, external send, artifact delivery, and memory write/delete.
- **Custom patch burden:** Hermes’s main potential win is reducing bespoke OpenClaw patches. If migration just ports the same wrappers and runbooks into Hermes glue, it is mostly rehosting, not simplification.

## Migration confidence guidance

Use calibrated language:

- High confidence: Hermes can be constrained in principle with profile isolation, tool removal, and explicit/gated memory.
- Moderate confidence: Hermes is a better long-term admin/control plane for PD One.
- Conditional confidence: Hermes is a better employee-facing runtime only after parity on the hard gates above.
- Low confidence: quick/big-bang cutover is safe.

## Recommended architecture

- `pd-neo` / admin Hermes profile: self-learning, skills/runbooks, audits, incident triage, code/admin tools, knowledge promotion.
- `pd-one` employee profile: no self-modification, no broad terminal/file/cron/skills/memory, only narrow business wrappers, private explicit memory if enabled.
- `pd-one-shadow` profile: dry-run replay/comparison against OpenClaw outputs before cutover.
- OpenClaw remains fallback/production edge until Hermes demonstrates parity over real workflows.

## Parity checklist before cutover

- Tool inventory proves no broad/self-modifying tools are available to employee PD One.
- Per-request Mattermost identity and privacy tests pass, including missing sender ID, spoofed display name, group channel, inactive user, and federation mismatch negatives.
- ACP/control-plane probes fail closed without verified identity: unknown `cli`/ACP users get no scoped company data, ACP labels/session names cannot spoof employee identity, and ACP cannot bypass delivery, memory, tool, or approval gates.
- Approval, specialist handoff, SOP, production schedule, watches, and AppSheet wrappers have behavior parity.
- Review-log, missed-message, denial, capability-gap, retry, and closure-state flows are durable and inspectable.
- Attachment/file delivery tests prove post creation and non-empty `file_ids`; Office artifacts pass no-corruption gates before delivery.
- Public/group memory fail-closed tests pass; private personal memory is explicit/listable/forgettable and cannot leak into admin/global learning.
- Red-team prompt-injection transcripts cannot unlock hidden tools, broaden scope, bypass approval, or exfiltrate private memory.
- Shadow outputs are compared against OpenClaw on a meaningful sample before any employee pilot.
- Rollback routing to OpenClaw remains available during pilot.

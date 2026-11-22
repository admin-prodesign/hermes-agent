# Hermes Mattermost Pairing-Prompt Triage

Use when an already-authorized PD One user unexpectedly receives a Hermes pairing code in Mattermost.

## Key distinction

Hermes gateway admission and the PD One permission bridge are separate layers:

- Gateway admission checks platform allow-all, platform allowlist, persisted DM pairing, global allow-all, then denies/pairs by default.
- The PD One permission bridge performs later exact-sender policy authorization.
- A valid PD One policy cache entry does not prove every active Hermes gateway process has the same pairing/allowlist state.

## Bounded diagnostic sequence

1. Verify the exact Mattermost sender ID from the injected bridge.
2. Search the requester-visible DM for the exact pairing post and timestamp; do not repeat the code in the final reply.
3. Check the intended profile only:
   - `hermes --profile pdone pairing list`
   - verify whether the exact sender is approved and whether a pending request exists.
4. Inspect the profile-scoped pairing files only as needed:
   - current/legacy location is resolved by `gateway/pairing.py` via `get_hermes_dir("platforms/pairing", "pairing")`;
   - compare approved-entry timestamp and pairing-file mtime with the prompt timestamp.
5. Check active Hermes gateway processes and profile identity. If more than one gateway is running, verify which processes have live connections to the Mattermost host without exposing tokens.
6. Correlate logs by exact sender ID, DM channel ID, post timestamp, and active process/profile.

## Strong attribution pattern

If all of the following are true:

- `pdone` already approved the exact sender before the prompt,
- `pdone` has no matching pending code and its pairing files did not change,
- the `pdone` gateway processed the same user message normally,
- another Hermes profile gateway was simultaneously connected to Mattermost,

then the pairing prompt did not come from the intended PD One admission store. The likely cause is another gateway/profile receiving the same bot event with a separate authorization store. State this as evidence-based attribution; do not claim shared-token equality unless it was verified without disclosing credentials.

## Pitfalls

- Do not say Hermes “failed to detect the user ID.” A pairing request itself proves the platform user ID was received. The failure is authorization lookup/admission, not identity extraction.
- Do not conflate a pairing code with a dangerous-command `/approve` prompt or PD One admin approval ticket.
- Do not approve, revoke, clear pairing state, edit config, stop gateways, or restart services during a why/diagnostic request.
- Do not inspect or print raw bot tokens. If credential comparison is essential and authorized, return only a boolean equality result.
- A code is one-time and short-lived; redact it in admin summaries even if it appeared in the requester’s own DM.

## Remediation gate

The durable fix is usually to ensure only the intended profile owns the PD One Mattermost bot connection, or to align the intended allowlist/pairing state. This is a config/gateway ownership change: produce a dry-run plan and obtain explicit approval before edits or restarts.

## User-facing receipt

Keep the answer concise and bilingual in Mattermost groups/channels. Report:

- which layer generated the prompt,
- whether the exact sender is currently approved in `pdone`,
- whether duplicate gateway ownership was observed,
- whether any changes/restarts were made,
- `Sources checked / 已查來源` without raw logs or codes.

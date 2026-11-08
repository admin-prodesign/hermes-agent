# PD One `admin:` escalation in Mattermost threads

## Durable lesson

When implementing or debugging PD One `admin:` escalation, detect the prefix against the raw Mattermost event text, not the prepared agent message.

The prepared message may be wrapped with:

- `[PD One Hermes permission bridge]`
- Mattermost thread context
- `[New message]`
- sender-name prefixes such as `[andy.lin] ...`

If scope resolution checks the start of that wrapped block, a real user message like `admin: Make this channel name bilingual` can fail detection because the string no longer starts with `admin:`.

## Correct routing pattern

1. Capture `raw_event_text = event.text or ""` before any policy/thread/context wrapping.
2. Build the normal prepared message for the model; keep the Hermes policy bridge and full thread context intact for safety.
3. Pass `raw_event_text` separately into the gateway agent run path.
4. Call `resolve_pd_one_channel_scope(..., text=raw_event_text)` for prefix detection.
5. If authorized by exact Mattermost sender id and Hermes policy/admin scope, resolve only this turn to the admin scope.
6. Ensure the effective scope prompt/toolsets are included in the agent cache signature so an admin-prefix turn cannot reuse an employee-scoped cached agent.

## Tests to add or confirm

- Authorized sender uses `admin:` in the middle of an existing Mattermost thread and escalates to admin scope.
- Prepared message starts with OpenClaw bridge/thread context, but raw text starts with `admin:`.
- Unauthorized sender using `admin:` remains in original scope.
- Inactive or `found=false` policy cache does not escalate.
- Non-Mattermost platforms ignore the prefix.
- Missing admin scope fails closed to the original channel scope.
- Normal-scope and admin-prefix turns in the same thread produce different cache signatures.

## Hermes gateway implementation notes

In `gateway/run.py`, preserve raw text in the top-level message handler before `_prepare_inbound_message_text(...)`, then pass it through `_run_agent(..., raw_event_text=raw_event_text)`. Inside `_run_agent`, call `resolve_pd_one_channel_scope(..., text=raw_event_text if raw_event_text is not None else message)`. Apply the same pattern for queued follow-up turns created from a real `pending_event`; synthetic/background prompts may safely fall back to their prompt text and should not invent escalation.

Add a lightweight log line only when `pd_one_scope.get("admin_prefix_invoked")` is true. Log metadata such as platform, chat id, user id, resolved agent id, and original agent id; never log the message body, policy JSON, credentials, or secrets.

Useful regression coverage:

- `tests/gateway/test_pd_one_channel_scopes.py`: include a prepared message that starts with `[PD One Hermes permission bridge]` and contains `[andy.lin] admin: ...` later; verify it stays employee-scoped when used as `text`, while raw `admin: ...` escalates and produces a different `scope_signature_fragment`.
- A gateway handler test should assert `_handle_message(...)` forwards `raw_event_text` into `_run_agent(...)`.
- Keep proxy-mode tests passing; proxy dispatch should tolerate the added `_run_agent` parameter without requiring remote API changes.

## Safety constraints

`admin:` is a scope-selection mechanism, not blanket approval. It must still preserve:

- exact Mattermost sender-id authorization;
- Hermes PD One policy cache as the permission source of truth;
- one-turn escalation rather than permanent channel mode switch;
- configured admin scope/toolsets, not prompt-only privilege expansion;
- explicit approval/dry-run/readback for writes, destructive actions, external sends, gateway/config/policy changes, and source-system edits.

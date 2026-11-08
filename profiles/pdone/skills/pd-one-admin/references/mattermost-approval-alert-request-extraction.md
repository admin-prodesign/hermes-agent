# Mattermost approval-alert request extraction

Use when Andy/admin reports that a PD One admin approval card, handoff alert, or approval-ticket preview shows the permission bridge or thread-context blob instead of the employee's actual request.

## Symptom

The admin-facing card has a useful requester/source section, but **User asked** begins with text such as:

```text
[PD One Hermes permission bridge]
Authorize by exact sender id only...
Policy JSON...
```

or repeats `[Mattermost thread context: ...]` rather than surfacing the active employee message.

## Durable fix pattern

1. Prefer the raw platform event text when available. For Hermes gateway hooks, the prepared `message` field may be truncated and may start with permission/thread/memory/attachment context; approval-card hooks should read `context['raw_message']` first and fall back to the prepared `message` only when raw text is absent.
2. If `raw_message` is not available, patch the gateway hook context to expose it from `raw_event_text` before injected policy/thread/attachment context is prepended. Keep the historical bounded `message` field for generic telemetry hooks, but add/document `raw_message` for request-card and admin-handoff hooks.
3. Patch the alert/card builder at the boundary where it formats the inbound Mattermost prompt, not the final admin card renderer only.
4. Extract the active human request in this order:
   - Remove compact media markers such as `[1 image]` that may appear before the permission bridge.
   - Remove injected memory/context blocks such as `<memory-context>...</memory-context>`.
   - Prefer the final `[New message]` block when present.
   - Strip one Mattermost sender prefix like `[andy.lin] ...` or `[irene] ...` from the selected block.
   - If no `[New message]` exists, remove only the leading permission-bridge preamble; if the cut lands at a thread-context block, use the last visible Mattermost sender line rather than prior context.
5. Keep source/requester metadata from the runtime context; do not infer identity from the stripped display-name prefix.
6. Add regression tests with a full synthetic prompt containing permission bridge + thread context + `[New message]` + memory context. Also cover raw-message precedence over a truncated prepared message, and media-marker-before-bridge fallback. Assert the rendered/extracted request equals only the human message.
7. Verify with targeted pytest/py_compile. For this class, run both the profile hook tests and the gateway hook tests when the gateway hook context was changed. Do not restart the PD One gateway unless Andy separately approves or the gateway is already unresponsive.
8. Back up/commit durable Hermes profile changes when the backup repo is configured.

## Pitfalls

- Do not truncate harder as a workaround. The problem is selecting the wrong part of the prompt, not card length.
- Do not remove thread/source metadata from the card; Andy still needs requester, channel, root/post/session, and PD One's employee-facing reply.
- Do not rely on display name/username for authorization. The stripped `[sender]` prefix is presentational only.
- Avoid broad transcript/history reads just to repair formatting; the active inbound prompt fixture is enough for regression coverage.

## Known implementation shape

A small helper like `_extract_user_request(message: str) -> str` in the approval-alert hook is usually sufficient. It should be unit-testable without live Mattermost credentials and called before `_quote_block(...)` renders the **User asked** section.

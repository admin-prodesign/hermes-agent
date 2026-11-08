# Mattermost channel admin operations

Use this for Andy/admin requests to change Mattermost channel settings, especially display-name bilingualization.

## Key lesson

Do not reflexively refuse a current-channel rename just because the request came from a shared/group channel. If the injected Hermes permission bridge resolves the exact sender id to an active admin and the message gives explicit admin authorization (for example `admin:`), a bounded current-channel display-name change can be executed with dry-run/readback discipline when policy says config changes are approvable.

## Safe sequence for current-channel display-name changes

1. Verify authorization from the injected permission bridge by exact sender id:
   - `found=true`, `active=true`.
   - requester has an admin role or equivalent approved scope.
   - approval allows config changes, or the request is explicitly approved by an approved admin.
   - never use display name or prior-session identity.
2. Treat the action as a config write:
   - use a dry-run/readiness probe where practical;
   - print/verify bot identity, channel id, current display name, target display name, endpoint, and payload;
   - keep technical channel `name` unchanged unless the user explicitly asks to change it.
3. Resolve the target name conservatively:
   - if user says “make bilingual, Chinese first” and the current display name is Chinese-only, append a concise English translation after ` / `.
   - If translation is uncertain or the current name is ambiguous, ask for the exact English/Chinese target rather than inventing.
Header-only appends (for example the `bu-it` coverage line) use the same authorization and readback, but the JSON payload must be only `{"header": "..."}`. Do not call channel-setup `apply_metadata` for a header change: that action also writes `purpose` and can replace an empty or manual purpose with a generated one. Preserve every existing header line, including the IT manual link, and abort if the live header is not the expected text.

4. Apply via Mattermost REST as the PD One bot/admin context:
   - obtain context using `/home/prodesign/.openclaw/workspace/tools/mattermost_review_log.py::mattermost_context()`;
   - verify `/api/v4/users/me` is the expected bot (usually `pdone`) and has appropriate roles;
   - read the channel with `GET /api/v4/channels/{channel_id}`;
   - patch only the display name with `PUT /api/v4/channels/{channel_id}/patch` and JSON `{"display_name": "..."}`.
5. Verify before reporting success:
   - read back `GET /api/v4/channels/{channel_id}`;
   - confirm `display_name` exactly equals the target;
   - report the channel id, API status, and readback match.

## Pitfall

Earlier PD One behavior incorrectly refused an Andy/admin `admin:` request in-channel as “employee-assistant scope.” For bounded admin operations on the current channel, the correct behavior is to honor the exact-sender admin authorization and perform the dry-run/apply/readback sequence, unless channel policy explicitly forbids that operation or the exact target name is unclear.

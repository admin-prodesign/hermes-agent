# Google Form → AppSheet fallback sync pattern

Use when a Google Forms response is accepted and lands in the linked Google response sheet, but native AppSheet Forms/Event automation does not reliably copy it into the downstream AppSheet table even after the bot/event definition is restored and promoted.

## When this pattern applies

- Forms API returns a real `responseId` and `createTime`.
- The linked response sheet contains the response row.
- AppSheet `/api/loadApp` shows the intended bot/event is enabled and stable/promoted.
- AppSheet Monitor/exportlog around the response window has no useful form-event/process execution, or the downstream table still lacks the row after a reasonable wait.
- The downstream table has a durable source-response column such as `GoogleForm_ResponseID` that can be used for idempotency.

## Recommended operating sequence

1. Restore the native AppSheet bot/event first when the definition is visibly wrong:
   - For known Google Forms triggers, verify `EventType = Forms`, an `AppFormsEventDefinition`, and the expected `DataSourceId`/`SchemaName`.
   - Promote latest to stable and verify `Version == StableVersion`.
   - **Then prove the native subscription, not just the JSON.** Pause any fallback sync, submit a tagged live response, and require AppSheet exportlog evidence for the Forms event/process. If there are no `GoogleForm` / `FORM_SUBMISSION` / expected process rows, the native subscription is still not firing even if the definition looks correct.
2. Backfill missing real responses through the AppSheet Data API using the response ID as the idempotency key.
3. Smoke-test with one clearly tagged form response.
4. If native automation still does not copy the smoke response, install or run a small idempotent fallback sync job.
5. Delete/quarantine smoke-test rows after verifying the copy path so the live operational table is not polluted.

## Idempotency and write shape

- Use `GoogleForm_ResponseID = responseId` as the duplicate guard.
- Before every add, `Find` by the response ID.
- After every add, read back by the response ID and record the AppSheet-generated row key.
- For AppSheet Database-backed tables, do **not** assume you can supply the key. A key column may be read-only through the Data API even when the AppSheet action computes a deterministic key internally. If an Add fails with `Invalid request provided to AppSheet database`, retry without sending the read-only key and rely on `GoogleForm_ResponseID` for idempotency.
- For copied DateTime values, convert Forms UTC `createTime` to the AppSheet app's local wall time before writing.

## Fallback job behavior

A safe fallback script should:

- poll recent Forms responses with an overlapping watermark;
- treat Google Forms API/gog empty-result shapes such as `"responses": null` as an empty list, not as an iterable failure;
- use deterministic command paths or a cron-equivalent PATH for non-system CLIs, then smoke-test under the same no-agent cron environment;
- skip already-processed response IDs and already-present AppSheet rows;
- skip known smoke/test markers in unattended mode;
- emit stdout only when it actually adds rows (empty stdout = silent/no notification);
- persist state in the active Hermes profile, not in a legacy/default profile path;
- be scheduled frequently enough for operational needs (for example every 5 minutes), with no-agent/script-only mode if the script already emits final user-facing output.
- have failure routing that is separate from ordinary `deliver=origin` cron notifications if PD One/admin triage is expected; verify bridge/queue evidence rather than assuming a visible cron error was federated.

## Smoke-test checklist

- [ ] Submit exactly one tagged response through the live public form.
- [ ] Verify Forms API shows the `responseId` and marker.
- [ ] Run/poll the native or fallback pipeline.
- [ ] Read back the downstream AppSheet row by `GoogleForm_ResponseID`.
- [ ] Delete the smoke row from the downstream table and verify remaining count is zero.
- [ ] Report receipts: app version/stable version, response ID, downstream row ID, cleanup result, and fallback job ID if one was installed.

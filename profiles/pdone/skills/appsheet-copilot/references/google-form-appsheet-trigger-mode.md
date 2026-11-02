# Google Form → AppSheet trigger-mode drift

Use when a Google Forms response reaches the linked Google response sheet, but no row appears in the downstream AppSheet table and no AppSheet Monitor/exportlog row appears for the form table at the submission time.

## Signature

- Forms API shows accepted responses with `responseId` and `createTime`.
- The linked response sheet receives the row.
- The downstream AppSheet table is missing the response ID / copied row.
- `/manage/exportlog` around the response time has no `GoogleForm_*` / expected process rows.
- Definition history shows the Google Form bot changed from the known-good external data-change trigger shape to sync-only or disabled.

For the Sudden Absence pipeline, the known-good bot shape before the 2026-06-10 regression was:

```text
Bot: GoogleForm_SuddenAbsenceRequests_New
Disabled: false
TriggerDataChangeEvent: true
TriggerDataChangeEventSync: false
TriggerDataChangeEventAsync: false
Event: Sudden Absence Form Submitted
Process: Process for GoogleForm_SuddenAbsenceRequests_New
```

The broken/stalled shapes observed were:

```text
# fully disabled
Disabled: true
Event Disabled: true

# later re-enabled but sync-only, so external Google Form submissions did not fire automatically
Disabled: false
TriggerDataChangeEvent: false
TriggerDataChangeEventSync: true
TriggerDataChangeEventAsync: false
```

## Triage steps

1. Verify accepted Forms responses:
   ```bash
   gog forms responses list <formId> --account admin@prodesign-group.com --json --no-input --filter="timestamp >= YYYY-MM-DDTHH:MM:SSZ"
   ```
2. Verify the linked response sheet received them.
3. Read the downstream AppSheet table via the deployed app Data API and compare `GoogleForm_ResponseID` values.
4. Export AppSheet logs in a tight window around the Forms `createTime`; absence of the form table/process means the automation did not fire.
   - For isolation, pause any fallback sync cron first, submit exactly one tagged response, wait long enough for AppSheet automation, then query `SuddenAbsenceRequests` by `GoogleForm_ResponseID` and exportlog for the response ID / `GoogleForm_*` / form-process strings.
   - If `/api/loadApp` shows the Forms event/bot enabled but the isolated exportlog has zero form-event hits, the raw definition is not enough proof: the underlying Google Forms/AppSheet subscription may not be registered. Re-register/recreate the Forms trigger through the AppSheet editor (or equivalent supported editor flow) and smoke-test again before removing a fallback job.
5. Compare raw `/api/loadApp` history for the bot/event flags above.

## Fix/backfill pattern

- Restore the bot trigger flags to the known-good external data-change shape, after dry-run and approval.
- **Do not treat raw JSON restoration as sufficient proof that a native Google Forms event is repaired.** The AppSheet definition can show `EventType=Forms`, `AppFormsEventDefinition`, correct `DataSourceId`, enabled bot/event, and `Version == StableVersion` while the underlying Google-side/AppSheet-side external subscription still does not fire. If a live form response produces no exportlog `GoogleForm` / `FORM_SUBMISSION` / process rows, recreate or re-register the Forms event through the AppSheet editor rather than only patching JSON.
- Keep the form event condition guarding against duplicate response IDs.
- Backfill missing responses by adding downstream rows with deterministic `Row ID = "SAR-" + LEFT(responseId,20) + "-" + RIGHT(responseId,12)` (or the table-specific equivalent) and `GoogleForm_ResponseID = responseId`; verify by Data API readback. If the target is AppSheet Database and the key is read-only through the Data API, omit the key and rely on the source response ID for idempotency.
- If the live Google Form schema has gained extra/untitled required questions, handle that separately: it can break future submissions/schema sync but is not the same as trigger-mode drift. Compare `gog forms raw` / public `FB_PUBLIC_LOAD_DATA_` question titles against the AppSheet `GoogleForm_*_Schema`; remove untitled/dummy questions or add matching AppSheet handling before re-registering native Forms automation.

## Isolated native-trigger verification

When a fallback sync exists, pause it before testing the native Forms trigger, otherwise the fallback can mask native failure.

1. Pause/disable the fallback job.
2. Submit one tagged live Google Forms response.
3. Verify Forms API returns the `responseId` and timestamp.
4. Wait a bounded window, then query the downstream table by `GoogleForm_ResponseID`.
5. Export AppSheet logs for the tight response window and require evidence of the native form event/process (`GoogleForm`, `FORM_SUBMISSION`, or the expected process name). A downstream row alone is not proof if any fallback was running.
6. Delete the smoke-test downstream row if one was created, then resume the fallback if the native path did not pass.

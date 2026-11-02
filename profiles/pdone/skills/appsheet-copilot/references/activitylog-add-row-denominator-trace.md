# ActivityLog direct Add-row denominator trace

Use when AppSheet steward evidence shows ActivityLog or ActivityLog_Attachments add/edit failures and the next safe step is read-only denominator evidence, not a live change.

## Read-only workflow

1. Keep this branch separate from sync p90/getAllTables and from thumbnail/notification/cache automation failures.
2. Use the current gate failure window as the exact time bound. Pull table-filter Performance Analyzer exports for each target table with:
   - `--table-name ActivityLog` and `--table-name ActivityLog_Attachments`;
   - adds enabled, syncs/updates/deletes/workflows/reports/API/documents disabled;
   - failuresOnly false;
   - per-table/chunked windows that stay below the exportlog cap;
   - when gate bounds include sub-seconds but the export endpoint accepts whole seconds, fetch the enclosing whole-second interval and post-filter every all-result and failures-only row in memory back to the exact gate/chunk timestamps before de-duplication. Record aggregate excluded-before/after/unparseable counts, but persist no excluded rows or identifiers.
3. Count only Stop/result rows for denominators. Paired Start rows contain raw payloads/base64/row data and blank Result; exclude them from success-rate counts. Treat uncapped all-result table exports as the Success source and matching uncapped failures-only table exports as the authoritative Failure source because table-scoped all-result exports can omit failures; report this caveat and do not double-count all-result Failure rows.
4. Classify direct Add-row failures separately:
   - ASDB after-image/readback: `Unable to find the specified row from AppSheet database` with `GetAfterImagesAsync` / `AppendRowsAsync` stack methods.
   - Duplicate/replayed request: duplicate/already-processed request signatures or repeated client/request pairs.
   - Timeout/formula/cancel classes only when the direct Add-row stop row says so.
5. Aggregate retry/replay without persisting identifiers: count repeated client/request pairs, stop rows in repeated pairs, max retry count, result patterns, and pairs with eventual success after failure. Do not write raw UserId/clientId/requestId/row keys/payloads to the derived artifact.
6. Preserve evidence paths: raw scanner receipts can remain local under steward logs, but manager-facing and Support-draft artifacts should include only aggregate counts, table/form names, AppTemplateVersion/localVersion buckets, row-size buckets, timings, and redacted exception heads.
7. When converting denominator evidence into a local Support draft, consume prior artifacts defensively: older appendices may store results as `completed_stop_rows`, `completed_success_rows`, `completed_failure_rows`, `completed_row_success_rate`, and `failure_classes_from_all_result_completed_rows` rather than generic `success_count`/`failure_count`. Read the source JSON shape before templating counts, validate the draft JSON with `python3 -m json.tool`, and run a redaction search for emails, raw Client/Request IDs, `updatedKeys`, base64/payload markers, and accidental `None Success`/`None Failure` placeholders before treating it as approval-ready.

## Key-source coverage follow-up for uncheckable failure-only cohorts

Use this when a current-state reconciliation leaves cohorts uncheckable because no target key was decoded.

1. Reconstruct and assert the exact prior failure-only cohort and prior key-coverage counts before testing additional sources.
2. Inspect terminal and companion Add rows only in memory. Require unique cohort alignment from exact client/request identity, unique request identity, or exact request-start/event-time alignment with available client/user context; reject conflicting alignment methods.
3. Accept target or parent candidates only from the exact schema-verified key names, schema-ordered `Data` payloads, or an explicitly named row-key-list field. Do not mine exception prose, unrelated scalar fields, or positional lists without verified schema order.
4. Persist aggregate aligned-row, source-presence, recovered/ambiguous/still-missing, cap, and validation counts only. Persist no identities, keys, payloads, users, attachment values, business values, or raw rows.
5. A zero-recovery audit is still useful evidence: it proves the analyzer omitted usable key-bearing companion evidence under the tested deterministic alignments. It does not prove the target never existed and should not trigger a speculative definition edit.

## Current business-state follow-up for failure-only cohorts

Use this after a right-edge check still shows failure-only request cohorts and the remaining question is whether the intended rows currently exist.

1. Reconstruct the exact prior cohort from fresh cap-clean analyzer leaves and assert its terminal, request-cohort, and version counts against the validated aggregate before using any identifier.
2. Load the exact AppTemplateVersion definition used by the cohort. Verify the real key from `DataSchemas[].Attributes[].IsKey/IsKeyPart` and obtain the schema column order before decoding analyzer `Data`; never infer the key from column order.
3. Match payload/detail evidence to target cohorts only in memory. Prefer exact client/request identity; use timestamp-plus-user fallback only when it maps to exactly one target cohort. Classify each cohort as one unambiguous target, multiple candidates, or no decodable key.
4. Query only unambiguous targets with read-only AppSheet `Find` calls through the Data Studio prototype app. Batch key selectors, then query both the target table and expected parent table. Persist no target, parent, request, client, user, payload, attachment, or business values.
5. Report both cohort-level and distinct-target counts because retries under new request identities can point to the same business row. Separate target found/not-returned/duplicate from expected-parent found/not-returned and parent-link match/mismatch.
6. Interpret a found target as current-state convergence, not proof that the failed request committed it. Interpret a target not returned as a bounded read result, not proof of permanent physical absence; preserve prototype visibility/source-lag caveats. Do not generalize checkable-cohort outcomes to cohorts with no decodable key.
7. Validate aggregate JSON, key/candidate/current-state reconciliation, cap cleanliness, and redaction before using the result in a Support appendix. Any external send remains separately approval-gated.

## Direct Edit denominator extension

Use the same terminal/result-row and privacy rules when the carry-forward item is a direct Edit census, with these additional guards:

1. Fetch update-family exports with adds/syncs/workflows/reports/API/documents/deletes disabled, then filter the retained rows to the exact `Edit row` operation. Keep `Update row` as a different operation unless the stated scope explicitly combines it.
2. Exclude terminal Edit rows carrying a process/action name from the direct user-edit denominator. Persist their aggregate count separately so process-driven Edit activity is not mistaken for successful user edits.
3. A cap-clean zero-attempt direct-Edit window is a completed opportunity-count result, but its success rate is non-estimable. Never report it as 100% reliability or as proof that an older failure cohort resolved.
4. When a short gate window has zero direct Edit attempts, the next independent read-only step may be a current rolling 24-hour operation-specific census, with AppTemplateVersion and window-overlap caveats explicit.

## Interpretation

- A thumbnail pause may reduce noncritical automation pressure, but it does not prove direct Add-row reliability improved; keep Add-row denominators separate.
- Sync p90/getAllTables evidence is a different branch from Add-row ASDB/retry failures.
- If repeated request pairs eventually succeed after failures, treat the branch as AppSheet/client retry/readback evidence suitable for a redacted Support packet before speculative local definition changes.

## Approval boundary

No approval is needed for read-only analyzer pulls and local aggregate artifacts. Approval is required before any Support/external send, AppSheet definition edit, stable promotion, row/queue mutation, security-filter change, Drive/Sheets mutation, permission change, gateway restart, or employee-visible guidance.

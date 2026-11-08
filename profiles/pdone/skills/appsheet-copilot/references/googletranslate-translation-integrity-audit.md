# GoogleTranslate Translation Integrity Audit

Use when a `GoogleTranslate` helper-table row shift, schema mismatch, or bulk translation worker issue may have pushed mismatched translations into real AppSheet tables.

## Core rule
Do **not** validate only the `GoogleTranslate` rows. The helper table may be the corrupted source of truth. Instead, independently identify recently touched target records and compare each live translated field against its current source field in the target table.

## Recommended workflow
1. Establish the time window, usually the last 24 hours unless the user gives a narrower incident window.
2. Use AppSheet/exportlog/update logs to identify records actually touched during that window. Include all tables the translation worker can write to, not just the table mentioned in the symptom.
3. For each touched target row, read the current source and translated target columns directly from AppSheet/the backing source of the target table.
4. Re-translate or semantically validate each pair from the source text, independent of any existing `GoogleTranslate` value.
5. Treat blanks carefully:
   - If the source text is blank and the translated field is blank, leave it alone.
   - If the source text is nonblank and the translation is blank, repair it.
   - If both languages are present but clearly describe different work/actions/entities, repair it even if both strings are fluent.
6. Apply edits with the AppSheet record API using the verified key column, then read back the edited rows and compare exact values.
7. Report concise counts: tables scanned, records touched, records corrected, fields verified, and any intentionally skipped blank-source fields.

## Practical notes
- For Pro-Design/Data Studio prototype operations, the helper script `scripts/appsheet_record_ops.py` is a good fit for bounded row edits and readback verification.
- When translation mismatches involve imported legacy work orders, preserve legacy identifiers, requestor/reviewer names, vendor names, and machine/equipment numbers exactly; translate prose and labels without normalizing away traceability.
- A row can have multiple translated fields (summary, description, troubleshooting/actions, etc.); verify each field pair separately.
- If exportlog shows no edited rows for a table in the chosen window, state that explicitly rather than scanning the whole table by default.
- After repairing pushed translations, check whether any related `ProcessingQueue` rows that were in API-error/retry states actually processed again. If the user asks to “check later,” create a real expiring follow-up job immediately and include the job receipt. Keep this follow-up read-only unless the user explicitly approves replaying or editing queue rows.
- `ProcessingQueue` can return blank AppSheet API responses for broad `Find` selectors, even when target-table reads/writes work. For follow-up verification, start with bounded selectors by `SourceTable`/`SourceRowKey` and recent `CreatedAt`/`FinishedAt`; if AppSheet still returns blank, use safer alternate evidence such as the helper sheet/mirror, export logs, recent utility-agent/OpenClaw session evidence, or a bounded utility-agent inspection. Report the evidence source and classify queue state as processed again, pending/retry scheduled, still API-error/dead, or inconclusive.

## Report shape
Keep the final update action-oriented:

```text
Checked <table>: <N> touched rows; corrected <M>; verified <K> translation fields by readback.
Skipped <field/table> only where source was blank.
```

Avoid long narrative translations in the user-facing report unless the user asks for examples.
# AppSheet Debug Playbook

## 1) Confirm symptom type

- Wrong value returned
- Action not firing
- Bot not triggering
- Slice/view missing rows
- Slow sync/performance

## 2) Fast root-cause checklist

1. Column type mismatch (Text vs Enum vs Ref vs Number)
2. Null/blank branch not handled
3. Wrong row context (`[_THISROW]`, deref, related table)
4. Predicate too broad/narrow in `SELECT()`
5. Security filter excluding expected rows
6. Automation condition false due to expression type/coercion
7. Duplicate event execution (missing idempotency key)
8. Idempotency key mismatch (guard key formula differs from write-back formula or context: `_THISROW_AFTER` vs row value)
9. Shared ProcessLog collision (key not scoped by source table)
10. ProcessLog visibility gap (security filter hides prior log rows from bot principal)
11. Mixed idempotency modes (ProcessLog + row-local stamp not aligned)
12. Timestamp-only row-local guard (`ISBLANK([LastProcessedAt])`) blocks valid later events
13. Missing server-only guard (`CONTEXT("Host") = "Server"`) lets scheduled/bulk automations fire during manual edits or mobile syncs
14. Prototype/deployed context mismatch: prototype API writes are visible in shared data but do not trigger deployed automations
15. Parent row visibility/security-filter gap: child rows exist, but automation/API principal cannot see or update the parent row
16. Helper-sheet row-number drift: Apps Script reads a sheet snapshot, then concurrent AppSheet adds/deletes/reorders rows before `setValue()`/pushback; translations or side effects land on the wrong current row. For `GoogleTranslate`, trace by `GoogleTranslateID`, not row number, and re-resolve the live row by ID before writing translated values or pushing back.

## 3) Isolation method

- Reduce expression to smallest failing condition
- Test each predicate separately
- Move expensive sub-expression to virtual column for observability
- Validate result types explicitly (`TEXT()`, `NUMBER()`, `DATE()`, `DATETIME()`)
- Use a quick probe for unknown branches:

```appsheet
IFS(
  ISBLANK(<expr>), "blank",
  ISNUMBER(<expr>), "number",
  ISDATE(<expr>), "date",
  ISDATETIME(<expr>), "datetime",
  ISTEXT(<expr>), "text",
  TRUE, "other"
)
```

If you suspect a type mismatch (common in bot conditions / date comparisons), try forcing the type to see where it breaks:

```appsheet
TEXT(<expr>)
```

```appsheet
NUMBER(<expr>)
```

```appsheet
DATE(<expr>)
```

```appsheet
DATETIME(<expr>)
```

When duplicate side effects are suspected, inspect the exact key being generated:

```appsheet
IF(
  ISNOTBLANK([EventKey]),
  [EventKey],
  CONCATENATE([ID], "|", TEXT([UpdatedAt]))
)
```

If available, also inspect the helper-column value directly (recommended for parity checks):

```appsheet
[EffectiveEventKey]
```

If one ProcessLog table is shared across multiple source tables, inspect a scoped key too:

```appsheet
CONCATENATE(
  "Orders",
  "|",
  IF(
    ISNOTBLANK([EventKey]),
    [EventKey],
    CONCATENATE([ID], "|", TEXT([UpdatedAt]))
  )
)
```

If you are using row-local idempotency instead of ProcessLog, inspect the row stamp directly:

```appsheet
[LastProcessedEventKey]
```

Then verify whether the event is already visible in ProcessLog for the acting principal:

```appsheet
IN(
  IF(
    ISNOTBLANK([EventKey]),
    [EventKey],
    CONCATENATE([ID], "|", TEXT([UpdatedAt]))
  ),
  ProcessLog[EventKey]
)
```

```appsheet
IN(
  CONCATENATE(
    "Orders",
    "|",
    IF(
      ISNOTBLANK([EventKey]),
      [EventKey],
      CONCATENATE([ID], "|", TEXT([UpdatedAt]))
    )
  ),
  ProcessLog[ScopedEventKey]
)
```

If using helper-column idempotency, verify guard/write-back parity with a source-row specific check:

```appsheet
COUNT(
  SELECT(
    ProcessLog[EventKey],
    AND(
      [SourceTable] = "Orders",
      [SourceKey] = [_THISROW].[ID],
      [EventKey] = [_THISROW].[EffectiveEventKey]
    )
  )
) > 0
```

If using row-local idempotency, verify the persisted stamp equals the helper key:

```appsheet
AND(
  ISNOTBLANK([LastProcessedEventKey]),
  [LastProcessedEventKey] = [EffectiveEventKey]
)
```

## 4) Bot troubleshooting

- Validate Event source table and update type (adds/updates/deletes)
- Validate condition result on a known row
- Check process step order and required inputs
- Add a diagnostic step (write log row / send email) temporarily

## 4.5) Slice / Security filter troubleshooting (missing rows)

- Confirm which filter applies:
  - Slice row filter condition
  - Table security filter
  - View row filter / referenced slice
- Temporarily reduce to a single predicate to isolate which clause excludes rows.
- Sanity-check user scoping:
  - `USEREMAIL()` matches what you think (test on desktop + mobile)
  - `LOOKUP(USEREMAIL(), "Users", "Email", "Role")` returns non-blank
- If date-based filters are involved, validate types explicitly (`DATE()`, `DATETIME()`) and avoid comparing Text dates.

## 5) Performance fixes

- Replace repeated `SELECT()` scans with precomputed virtual columns where possible
- Narrow predicates early (`AND([Plant]=..., [Status]=...)`)
- Minimize cross-table deref chains in heavily-used views
- Use slices to reduce row volume per UX view
- Remember: `FILTER("Table", condition)` returns a list of row keys (not rows). Great for `COUNT()`/`IN()`, but for sums/values use `SELECT(Table[Col], ...)`.
- If parent records depend on many child `REF_ROWS()`, move to cached parent fields + reconciliation bot/action

## 5.1) Common failure signatures (fast mapping)

- **Symptom:** Parent table sync becomes slow after adding child rollup virtual columns  
  **Likely cause:** Every parent row recalculates expensive child scans on each sync (`REF_ROWS()`/`SELECT()` fanout).  
  **Fix:** Store rollups in physical parent columns (e.g., `[TaskCountCached]`, `[TotalAmountCached]`) and update via child add/update/delete actions; keep a periodic reconciliation bot.

- **Symptom:** QA rejects a new form/schema because the field list/validation doesn’t match the agreed spec
  - **Likely cause:** The response skipped an explicit schema checklist (columns, types, validations), so QA can’t confirm alignment.
  - **Fix:** Deliver the schema summary (field names, data types, validation expressions) and sample rows plus the QA confirmation steps; call out any columns or enum values the QA reviewer must sign off on before deployment.
  - **Verify:** Compare the checklist to the QA spec, point QA to the sample row(s) that trigger each validation, and confirm the reviewer sees the same column names/types before sign-off.

- **Symptom:** Bot condition "looks true" but step never runs  
  **Likely cause:** Condition returns Text/blank instead of strict Yes/No.  
  **Fix:** Wrap condition with explicit boolean expression, e.g. `AND(NOT(ISBLANK([Status])), [Status]="Ready")`.

- **Symptom:** Duplicate records/actions after retries  
  **Likely cause:** Missing idempotency key check.  
  **Fix:** Gate with idempotency check (`NOT(IN([_THISROW].[EffectiveEventKey], ProcessLog[EventKey]))`) and write back the same helper value (`EventKey: [_THISROW].[EffectiveEventKey]`) once processed.

- **Symptom:** Bot keeps re-firing on every edit after status already reached target  
  **Likely cause:** Condition checks current value only, not state transition.  
  **Fix:** Use BEFORE/AFTER transition guard, e.g. `AND([_THISROW_BEFORE].[Status]<>"Ready", [_THISROW_AFTER].[Status]="Ready")`.

- **Symptom:** Automation fires during manual edits or mobile testing even though the state transition already happened  
  **Likely cause:** Missing host-context guard (`CONTEXT("Host") = "Server"`) so the expression still evaluates TRUE during every local sync.  
  **Fix:** AND the transition/idempotency guard with `CONTEXT("Host") = "Server"` so the automation only executes when AppSheet runs on the server.  
  **Verify:** Temporarily expose `CONTEXT("Host")` (e.g., virtual column) and confirm the expression returns FALSE for `Editor`/`MobileApp` contexts.

- **Symptom:** Bot still creates duplicate side effects after retries/re-syncs even with transition guard  
  **Likely cause:** Transition guard blocks repeat edits, but retries replay the same event without idempotency persistence.  
  **Fix:** Add a blank-safe event-key gate (or scoped gate for shared logs) and write that exact key in ProcessLog (or stamp `LastProcessedEventKey: [_THISROW].[EffectiveEventKey]`) in the same process.

- **Symptom:** Idempotency gate exists, but duplicates still slip through intermittently  
  **Likely cause:** `EventKey` is blank/unstable, so each retry looks like a new event.  
  **Fix:** Ensure `EventKey` is non-blank and stable per logical event; if needed, set with `CONCATENATE([ID], "|", TEXT([UpdatedAt]))` and persist before side effects.

- **Symptom:** Idempotency guard exists, but duplicates still happen consistently on retries  
  **Likely cause:** Condition checks one key formula/context, but ProcessLog write-back stores a different formula/value.  
  **Fix:** Create a helper virtual column (e.g. `[EffectiveEventKey]`) and reference that same column in both guard + ProcessLog EventKey mapping.

- **Symptom:** Guard seems correct, but duplicate behavior changes after unrelated schema/column edits  
  **Likely cause:** Key formula was copy-pasted in multiple places and one copy drifted (`[_THISROW_AFTER]` vs `[UpdatedAt]`, extra prefixes, etc.).  
  **Fix:** Collapse to one helper source (`[EffectiveEventKey]`) and use parity probe (`COUNT(SELECT(ProcessLog[EventKey], AND([SourceTable]="Orders", [SourceKey]=[_THISROW].[ID], [EventKey]=[_THISROW].[EffectiveEventKey])))>0`).

- **Symptom:** Duplicates happen only for some users/devices, while others look correct  
  **Likely cause:** ProcessLog security filter hides prior keys for the acting principal, so `IN(..., ProcessLog[EventKey])` misses history.  
  **Fix:** Ensure the bot principal can read ProcessLog keys used for idempotency (or keep idempotency table unfiltered for bot reads).

- **Symptom:** Behavior flips between duplicate replays and false "already processed" blocks after idempotency edits  
  **Likely cause:** Mixed modes — ProcessLog guard + row-local `LastProcessedEventKey` are both active but not written from the same key source.  
  **Fix:** Pick one idempotency source-of-truth per bot path. Either (A) ProcessLog-only using `[EffectiveEventKey]` everywhere, or (B) row-local-only with `LastProcessedEventKey: [_THISROW].[EffectiveEventKey]` write-back.

- **Symptom:** Row-local guard prevents all later valid events after the first successful run  
  **Likely cause:** Guard uses `ISBLANK([LastProcessedAt])` (timestamp-only), so once stamped it blocks forever regardless of event identity.  
  **Fix:** Compare keys instead of timestamp emptiness, e.g. `OR(ISBLANK([_THISROW_AFTER].[LastProcessedEventKey]), [_THISROW_AFTER].[LastProcessedEventKey] <> [_THISROW].[EffectiveEventKey])`.

- **Symptom:** `Case_Updates` rows exist and are stuck at `ReadyToProcess`, but parent `Case` fields and queue rows do not advance  
  **Likely cause:** The child rows were written through the prototype app API, so deployed-app add/update bots did not run; or the deployed app/security-filter context cannot see the old parent Case.  
  **Fix:** Verify deployed definition wiring, then pull fresh runtime/exportlog evidence for the row keys. Check final parent fields (`Case[Status]`, `Latest_CaseUpdateID`, `Last Updated`) and parent visibility in the deployed app context before claiming success. For live effects, write through deployed app when visible or report the security-filter blocker.

- **Symptom:** Some events are wrongly blocked as "already processed" across different source tables  
  **Likely cause:** Shared ProcessLog uses unscoped `EventKey`, causing collisions between tables.  
  **Fix:** Scope the key, e.g. `CONCATENATE("Orders", "|", <effective_event_key_expr>)`, and check against `ProcessLog[ScopedEventKey]`.

## 6) Response format when debugging for user

- Symptom
- Root cause
- Fix expression/config
- Verification steps (2-4)
- Optional hardening tip

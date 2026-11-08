# AppSheet Expression Patterns

## Common filters

```appsheet
[Status] = "Open"
```

```appsheet
AND([Status]="Open", [DueDate] <= TODAY()+3)
```

## User-scoped data

```appsheet
[OwnerEmail] = USEREMAIL()
```

```appsheet
IN(USEREMAIL(), [AllowedUsers])
```

## Parent/child rollups

```appsheet
COUNT(SELECT(Tasks[ID], [ProjectID] = [_THISROW].[ID]))
```

```appsheet
SUM(SELECT(LineItems[Amount], [InvoiceID] = [_THISROW].[ID]))
```

## Performance-first rollup alternatives (large child tables)

Use these when `REF_ROWS()` + virtual rollups are slowing sync.

### Parent cached count (updated by action/bot)

```appsheet
COALESCE([TaskCountCached], 0)
```

### Reconciliation expression (run on schedule or after bulk imports)

```appsheet
COUNT(SELECT(Tasks[ID], [ProjectID] = [_THISROW].[ID]))
```

### Parent cached amount (default-safe)

```appsheet
COALESCE([TotalAmountCached], 0)
```

### Reconciliation sum expression

```appsheet
SUM(SELECT(LineItems[Amount], [InvoiceID] = [_THISROW].[ID]))
```

## Latest-row retrieval

```appsheet
MAXROW("TaskUpdates", "UpdatedAt", [TaskID] = [_THISROW].[ID])
```

```appsheet
LOOKUP(
  MAXROW("TaskUpdates", "UpdatedAt", [TaskID] = [_THISROW].[ID]),
  "TaskUpdates",
  "ID",
  "Progress"
)
```

## Safe dereference/defaulting

```appsheet
IF(ISBLANK([Manager]), "Unassigned", [Manager].[Name])
```

```appsheet
COALESCE([OverrideValue], [DefaultValue], 0)
```

## Coercion helpers (useful for debugging + strict comparisons)

```appsheet
TEXT([AnyValue])
```

```appsheet
NUMBER([AnyValue])
```

```appsheet
DATE([AnyValue])
```

```appsheet
DATETIME([AnyValue])
```

## Schema validation helpers (for new forms that must stay aligned with QA)

Use these when you need to document the expected fields/validations for a data-collection form.

### Required contact field guard

```appsheet
AND(
  NOT(ISBLANK([EmployeeEmail])),
  REGEXMATCH([EmployeeEmail], "^[^@\s]+@[^@\s]+\.[^@\s]+$")
)
```

Replace `[EmployeeEmail]` with the actual column being validated; the regex above is a light sanity check.

### Enumerated picklist guard

```appsheet
IN([Department], {"Ops","QA","Support"})
```

Swap the options with the approved list for the form you are building.

### Date-range guard (start/hire dates, etc.)

```appsheet
AND(
  ISNOTBLANK([HireDate]),
  [HireDate] <= TODAY(),
  [HireDate] >= TODAY() - 365*10
)
```

Adjust the range to match the dataset's expected window.

## EnumList / list membership

```appsheet
IN("Taipei", [Cities])
```

```appsheet
IN([_THISROW].[ID], [RelatedIDs])
```

## Prefer FILTER() for readability (when you want rows, not just values)

```appsheet
COUNT(
  FILTER("Tasks", [ProjectID] = [_THISROW].[ID])
)
```

```appsheet
SUM(
  SELECT(
    LineItems[Amount],
    [InvoiceID] = [_THISROW].[ID]
  )
)
```

If you specifically want to use `FILTER()` for readability, remember it returns a list of row keys. Sum a column by converting that key-list into a `SELECT()` predicate:

```appsheet
SUM(
  SELECT(
    LineItems[Amount],
    IN([ID], FILTER("LineItems", [InvoiceID] = [_THISROW].[ID]))
  )
)
```

## De-duplication checks

```appsheet
COUNT(SELECT(Orders[ID], [ExternalRef] = [_THISROW].[ExternalRef])) = 0
```

## Idempotency guard (automation safe re-run)

Row-local guard (no ProcessLog):

```appsheet
OR(
  ISBLANK([_THISROW_AFTER].[LastProcessedEventKey]),
  [_THISROW_AFTER].[LastProcessedEventKey] <> [_THISROW].[EffectiveEventKey]
)
```

ProcessLog guard (shared history table):

```appsheet
NOT(
  IN(
    IF(
      ISNOTBLANK([_THISROW].[EventKey]),
      [_THISROW].[EventKey],
      CONCATENATE([_THISROW].[ID], "|", TEXT([_THISROW_AFTER].[UpdatedAt]))
    ),
    ProcessLog[EventKey]
  )
)
```

### Idempotency guard (scoped; for shared ProcessLog tables)

```appsheet
NOT(
  IN(
    CONCATENATE(
      "Orders",
      "|",
      IF(
        ISNOTBLANK([_THISROW].[EventKey]),
        [_THISROW].[EventKey],
        CONCATENATE([_THISROW].[ID], "|", TEXT([_THISROW_AFTER].[UpdatedAt]))
      )
    ),
    ProcessLog[ScopedEventKey]
  )
)
```

### Blank-safe event key helper (inline expression)

```appsheet
IF(
  ISNOTBLANK([_THISROW].[EventKey]),
  [_THISROW].[EventKey],
  CONCATENATE([_THISROW].[ID], "|", TEXT([_THISROW_AFTER].[UpdatedAt]))
)
```

### Single-source event key via helper column (recommended)

Use this when duplicate prevention keeps failing because guard and write-back formulas drift.

```appsheet
Column: EffectiveEventKey (Virtual, Text)
App formula:
IF(
  ISNOTBLANK([EventKey]),
  [EventKey],
  CONCATENATE([ID], "|", TEXT([UpdatedAt]))
)
```

Unscoped guard:

```appsheet
NOT(IN([_THISROW].[EffectiveEventKey], ProcessLog[EventKey]))
```

Scoped guard (shared ProcessLog):

```appsheet
NOT(
  IN(
    CONCATENATE("Orders", "|", [_THISROW].[EffectiveEventKey]),
    ProcessLog[ScopedEventKey]
  )
)
```

Write-back mappings:

```appsheet
EventKey: [_THISROW].[EffectiveEventKey]
ScopedEventKey: CONCATENATE("Orders", "|", [_THISROW].[EffectiveEventKey])
```

### Row-local idempotency (no ProcessLog dependency)

Use this when side effects are one-per-row-event and ProcessLog visibility/scoping adds complexity.

Guard:

```appsheet
AND(
  [_THISROW_BEFORE].[Status] <> "Ready",
  [_THISROW_AFTER].[Status] = "Ready",
  OR(
    ISBLANK([_THISROW_AFTER].[LastProcessedEventKey]),
    [_THISROW_AFTER].[LastProcessedEventKey] <> [_THISROW].[EffectiveEventKey]
  )
)
```

Write-back mappings (same source row):

```appsheet
LastProcessedEventKey: [_THISROW].[EffectiveEventKey]
LastProcessedAt: NOW()
```

(Replace `"Orders"` with your source table name. Keep one idempotency source-of-truth per bot path: ProcessLog or row-local stamp.)

### Duplicate-gate probes (preflight/debug)

Inline formula probe:

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

Helper-column probe:

```appsheet
IN([EffectiveEventKey], ProcessLog[EventKey])
```

Scoped helper-column probe:

```appsheet
IN(
  CONCATENATE("Orders", "|", [EffectiveEventKey]),
  ProcessLog[ScopedEventKey]
)
```

Row-local stamp probe:

```appsheet
AND(
  ISNOTBLANK([LastProcessedEventKey]),
  [LastProcessedEventKey] = [EffectiveEventKey]
)
```

Guard/write-back parity probe:

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

## Transition-safe bot conditions (run once on status change)

Use when automations should fire only when value changed to target state.

```appsheet
AND(
  [_THISROW_BEFORE].[Status] <> "Ready",
  [_THISROW_AFTER].[Status] = "Ready"
)
```

```appsheet
AND(
  [_THISROW_BEFORE].[Approved] <> TRUE,
  [_THISROW_AFTER].[Approved] = TRUE
)
```

## Transition + idempotency combined guard (side-effect safe)

Use when retries/network flakiness could replay actions.

```appsheet
AND(
  [_THISROW_BEFORE].[Status] <> "Ready",
  [_THISROW_AFTER].[Status] = "Ready",
  NOT(IN([_THISROW].[EffectiveEventKey], ProcessLog[EventKey]))
)
```

```appsheet
AND(
  [_THISROW_BEFORE].[Status] <> "Ready",
  [_THISROW_AFTER].[Status] = "Ready",
  NOT(
    IN(
      CONCATENATE("Orders", "|", [_THISROW].[EffectiveEventKey]),
      ProcessLog[ScopedEventKey]
    )
  )
)
```

```appsheet
AND(
  [_THISROW_BEFORE].[Approved] <> TRUE,
  [_THISROW_AFTER].[Approved] = TRUE,
  OR(
    ISBLANK([_THISROW_AFTER].[LastProcessedEventKey]),
    [_THISROW_AFTER].[LastProcessedEventKey] <> [_THISROW].[EffectiveEventKey]
  )
)
```

## Server-only execution guard

Use this when a webhook, scheduled job, or import action should run only on the server-side execution context. Combine it with your existing condition or guard to keep local edits from re-triggering the process.

```appsheet
CONTEXT("Host") = "Server"
```

## Boolean-safe bot conditions (avoid Text/blank truthiness bugs)

```appsheet
AND(
  NOT(ISBLANK([Status])),
  [Status] = "Ready"
)
```

```appsheet
OR(
  [Priority] = "Urgent",
  AND([DueDate] <= TODAY(), [Status] <> "Done")
)
```

## Security filter examples

```appsheet
OR(
  [OwnerEmail] = USEREMAIL(),
  IN(USEREMAIL(), Admins[Email])
)
```

```appsheet
[Plant] = LOOKUP(USEREMAIL(), "Users", "Email", "Plant")
```

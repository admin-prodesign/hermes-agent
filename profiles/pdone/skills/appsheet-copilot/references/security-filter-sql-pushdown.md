# AppSheet security-filter SQL pushdown notes

Use this when reviewing whether a security filter is likely to be database/AppSheet-DB optimized.

## What AppSheet optimizes best

Per AppSheet's security-filter scaling guidance, database-backed tables can be efficient when the filter reduces to simple row-local predicates that can be mapped to the data source query, such as:

```appsheet
[Column] = constant-value
[Column] >= constant-value
IN([Column], {constant1, constant2, ...})
AND(simple-condition1, simple-condition2, ...)
```

This is strongest when the compared value is constant/user-derived and the predicate is on columns of the same table being filtered.

## Dynamic list / parent-table filters

A filter like:

```appsheet
AND(
  ISNOTBLANK([CaseID]),
  IN([CaseID], Case[CaseID])
)
```

is correct for constraining child rows to currently visible parent rows, but do **not** describe it as strictly SQL-optimized. The second argument, `Case[CaseID]`, is a dynamic list derived from another filtered table, not a constant list. AppSheet may need to evaluate the parent table visibility first and then use that list to filter child rows.

## How to explain the trade-off

- It is a correctness/security-visibility improvement when child rows must track parent visibility.
- It can reduce downloaded child rows if the visible parent set is much smaller than all historical parents.
- It may still be slow for users who can see many parent rows.
- It is usually less pushdown-friendly than a direct child-table predicate such as `[Created On] >= <cutoff>`.

## Preferred long-term shape for large child tables

Prefer physical/cached child-row predicates where feasible, for example:

```appsheet
AND(
  ISNOTBLANK([CaseID]),
  [Created On] >= <user cutoff>,
  [CaseIsVisible] = TRUE
)
```

or copied/cached parent fields on the child table that allow simple row-local predicates. For high-volume parent/child designs, cache parent summary/latest-child fields rather than relying on broad child-table cross-lookups or heavy labels during sync.

## Server/API target queue exceptions

When tightening security filters for high-volume tables that are also touched by AppSheet server automations, preserve the `API_Target_Queue` exception so old records can still be targeted by backend jobs. In Pro-Design this queue has columns `TargetID`, `TargetTable`, and `Timestamp`, and is itself owner-only. Use a narrow server-owner branch rather than reopening old data to all users.

Parent table pattern:

```appsheet
OR(
  AND(
    LOOKUP(
      USEREMAIL(),
      "HR_Employees_AppSheet_Settings",
      "Appsheet Email",
      "_Is_Case_User"
    ),
    OR(
      ISBLANK([Completion Date]),
      [Completion Date] >= (TODAY() - 60)
    )
  ),
  AND(
    USEREMAIL() = CONTEXT("OwnerEmail"),
    CONTEXT("Host") = "Server",
    IN(
      [CaseID],
      SELECT(API_Target_Queue[TargetID], [TargetTable] = "Case")
    )
  )
)
```

Child table pattern when child visibility follows the filtered parent but API jobs may directly target old children:

```appsheet
OR(
  AND(
    ISNOTBLANK([CaseID]),
    IN([CaseID], Case[CaseID])
  ),
  AND(
    USEREMAIL() = CONTEXT("OwnerEmail"),
    CONTEXT("Host") = "Server",
    IN(
      [CaseUpdateID],
      SELECT(API_Target_Queue[TargetID], [TargetTable] = "Case_Updates")
    )
  )
)
```

Caveat: the `API_Target_Queue` branch is also a dynamic `SELECT(...)` and is not the most SQL-pushdown-friendly predicate. Keep it scoped to `CONTEXT("Host") = "Server"` and owner context so normal user syncs still benefit from the tighter date/parent filters.

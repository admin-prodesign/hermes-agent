# AppSheet HR_E_A_S Deprecated `HR_Employees` Column Removal

Use this reference when Andy asks to remove, hide, or finish deprecating duplicated AppSheet settings columns from `HR_Employees` after migrating canonical settings to `HR_Employees_AppSheet_Settings` (`HR_E_A_S`).

## Removal gate

Do **not** delete deprecated `HR_Employees` AppSheet-setting columns until all of these pass in a fresh live definition/data audit:

1. Latest AppSheet definition has been freshly read from `/api/loadApp` and `StableVersion == Version` is checked.
2. Zero blocker references remain to deprecated `HR_Employees` settings columns across source expression/config surfaces, especially:
   - table security filters / update modes
   - slices
   - view/menu/default-start/show-if expressions
   - actions
   - bots, events, processes, tasks, and task recipient lists
   - column formulas/defaults/valid-if/show-if/editable-if
3. `HR_E_A_S` is independently canonical: no remaining formula/default fallback copies duplicated settings from `[PersonID].[...]`, except intentional identity/person facts like `Appsheet Email`.
4. Existing `HR_E_A_S` rows are backfilled for active/employed users before clearing/deleting the HR columns.
5. Admin and normal AppSheet accounts have expected roles/groups/flags after the backfill.
6. Monitoring/canary period, if requested, has no migration-specific failures.

## Important audit pitfall: bot/task references

A zero-reference audit must not only search for `Current User[Appsheet Roles]` or direct `[PersonID].[...]` dereferences. Bot recipient and process-condition expressions can still read deprecated fields through `SELECT()` / `FILTER()` over `HR_Employees`, for example:

```appsheet
SELECT(
  HR_Employees[Appsheet Email],
  AND(
    [Language] = "en",
    IN("HR_Manager", [Appsheet Roles])
  )
)
```

and notification-routing patterns such as:

```appsheet
SELECT(
  HR_Employees[Appsheet Email],
  AND(
    [Language] = "zh-tw",
    ISNOTBLANK(
      INTERSECT(
        [Appsheet Notification Group],
        [_THISROW].[Notification Group]
      )
    )
  )
)
```

These are blockers for deleting `HR_Employees[Appsheet Roles]` or `HR_Employees[Appsheet Notification Group]` even if UX/security-filter migration looks complete.

## Rewrite pattern for notification/role bots

When rewriting recipient/condition expressions:

- Keep `HR_Employees` as the source for HR/person facts such as `Appsheet Email`, `Language`, employment status, and manager/person relationships when needed.
- Use `HR_E_A_S` as the source for runtime settings such as `Appsheet Roles`, `Appsheet Notification Group`, and `Combined Appsheet Roles`.
- Prefer resolving eligible `PersonID`s from `HR_E_A_S`, then dereference or look up the HR email/language as needed, rather than filtering large `HR_Employees` rows by duplicated settings.
- Preserve language-specific recipient splits: if the original expression filters `[Language] = "en"` or `"zh-tw"`, keep the same language semantics via the linked `HR_Employees` row or a canonical language field if one exists in HR_E_A_S.

Example direction, to adapt after checking the exact schema/key names:

```appsheet
SELECT(
  HR_Employees_AppSheet_Settings[Appsheet Email],
  AND(
    [PersonID].[Language] = "en",
    IN("HR_Manager", [Appsheet Roles])
  )
)
```

If the task needs `PersonID` recipients rather than email recipients, return `HR_Employees_AppSheet_Settings[PersonID]` and keep all role/group filtering on HR_E_A_S.

## Backfill check before deletion

For each existing `HR_E_A_S` row, compare these columns against the linked `HR_Employees` row and flag blanks in HR_E_A_S where HR has a value:

- `Appsheet Dashboard Type`
- `Appsheet Views Access`
- `Appsheet Navigation Bar`
- `Appsheet Menu Items`
- `Appsheet Roles`
- `Appsheet Notification Group`

Do not mass-normalize by BU/job level during this removal gate. Backfill only direct blank-from-linked-HR values unless Andy approves a broader cleanup/template policy.

Also verify:

- `HR_E_A_S[Combined Appsheet Roles]` formula remains `UNIQUE([Appsheet Notification Group] + [Appsheet Roles])` or an explicitly approved equivalent.
- `_Is_*` booleans for admin/critical users match expected access.
- Andy's normal AppSheet account (`pro.design.group.tw@gmail.com`) is intentionally blank/disabled if it has no roles/groups; otherwise backfill/fix before deleting HR fallbacks.
- `admin@prodesign-group.com` retains `All_User`/`Super_Admin` and key access flags.

## Reporting rule

If blocker references remain, report clearly that the columns are **not safe to delete yet**, list the blocker surfaces/columns, and provide the next migration plan. Do not proceed to schema deletion in the same step unless a fresh follow-up audit passes and Andy explicitly asks for deletion.
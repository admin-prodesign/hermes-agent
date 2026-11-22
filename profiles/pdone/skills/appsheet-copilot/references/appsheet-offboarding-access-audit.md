# AppSheet offboarding access audit

Use this reference when asked who recently left the company and should be removed from AppSheet access/user lists.

## Purpose

Produce a read-only offboarding candidate list by comparing recent HR separation status against AppSheet access fields. Do not edit/remove access unless the user explicitly authorizes the bounded write.

## Default read-only flow

1. Use the prototype data-pull app for analysis unless Andy explicitly asks for deployed-app writes.
2. Get current date/time with a tool when computing “last month” or “recently”.
3. Interpret “last month” in the obvious default as the last 30 days from today unless the user clearly means previous calendar month. If ambiguity matters, report the window used and optionally include a previous-calendar-month cross-check.
4. Query `HR_Employees` for:
   ```appsheet
   Filter(
     HR_Employees,
     AND(
       [Employment Status] = "Not Employed",
       ISNOTBLANK([Separation Date]),
       [Separation Date] >= DATE("YYYY-MM-DD")
     )
   )
   ```
5. For each separated employee, check access-bearing fields in `HR_Employees`:
   - `Appsheet Email`
   - `Appsheet Roles`
   - `Combined Appsheet Roles`
   - `Appsheet Views Access`
   - `Appsheet Navigation Bar`
   - `Appsheet Menu Items`
   - `Appsheet Notification Group`
   - `Team Members`
6. Cross-check `HR_Employees_AppSheet_Settings` by `PersonID`:
   ```appsheet
   Filter(HR_Employees_AppSheet_Settings, [PersonID] = "<PersonID>")
   ```
   Inspect the same access-bearing fields there.
7. Return a concise table with: remove-candidate verdict, name, `PersonID`, employee ID, BU, separation date, and evidence. Do not expose sensitive HR detail beyond what is needed for access cleanup.

## Interpretation notes

- A separated employee with nonblank AppSheet email/roles/views/access fields is a strong cleanup candidate.
- A separated employee with no AppSheet email/roles/views/settings row may not need AppSheet access removal; report as “probably no AppSheet access to remove,” not as a removal target.
- `HR_Employees_AppSheet_Settings` may not have rows for all employees. Absence of a settings row does not clear access if `HR_Employees` still contains AppSheet access fields.
- If the request asks to “remove” users, treat the first response as an audit/dry-run unless the user already clearly authorized the exact write. Writes require bounded confirmation and readback receipts.

## Output shape

Lead with the query window and data source, then a compact table:

| Remove from AppSheet access? | Employee | PersonID | Employee ID | BU | Separation Date | Evidence |

End with whether any changes were made. For audits, say “No changes were made.”

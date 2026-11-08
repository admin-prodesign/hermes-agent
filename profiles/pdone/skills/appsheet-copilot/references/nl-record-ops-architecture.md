# AppSheet natural-language record ops architecture

## Recommendation

Use a two-layer design:

1. **Chat/agent layer** in `appsheet-agent`
   - parses the human request
   - asks clarifying questions
   - decides whether the request is read-only or mutating
   - requires explicit confirmation before delete and high-risk edits
2. **Deterministic backend layer** in `skills/appsheet-copilot/scripts/appsheet_record_ops.py`
   - loads the synced schema map
   - maps intent to table-aware AppSheet API calls
   - resolves required fields and lookup-backed options
   - executes `Find` / `Add` / `Edit` / `Delete`

That split is the right one here. The language side should stay conversational. The AppSheet side should stay boring, inspectable, and testable.

## What already exists

- Schema sync artifacts:
  - `data/appsheet-definitions/f2073120-8c2e-4930-b13c-105838c5e4c3/latest/latest.md`
  - `data/appsheet-definitions/f2073120-8c2e-4930-b13c-105838c5e4c3/latest/latest.json`
- Distilled relationship/schema surface:
  - `skills/appsheet-copilot/references/prodesign-schema-map.json`
  - `skills/appsheet-copilot/references/prodesign-schema-map.md`
- Existing AppSheet API export pattern:
  - `skills/appsheet-copilot/scripts/export_prodesign_activitylog.py`
- Runtime keydrop path already established:
  - `projects/AppSheet/keydrop/prototype-app.env`

## What had to be built

- A record-ops backend entrypoint that can plan and optionally execute natural-language requests.
- Schema-aware clarification logic for ActivityLog incident flows.
- Safe resolution flow for `contains(ActivityLogID)` lookup before update/delete.
- A documented operational architecture for chat orchestration vs backend execution.

## Verified schema facts used by the backend

From the synced definition/map:

- `ActivityLog_Incident_All` is a slice over `ActivityLog` where:
  - `[Category] = "Incident Report"`
  - `ISBLANK([Parent ActivityLogID])`
- `ActivityLog[Parent ActivityLogID]` is a `Ref` to `ActivityLog`
- `ActivityLog[Category]` initial value inherits from parent when a child row is created
- `ActivityLog[Sub-Category]` initial value inherits from parent when a child row is created
- `ActivityLog[Sub-Category 2]` initial value inherits from parent when a child row is created
- `ActivityLog[ActivityLog Status]` initial value inherits the parent status if there is a parent, otherwise defaults to `Unresolved` for `Incident Report`
- `ActivityLog[Description]` is required for parent Incident Reports (`[Category] = "Incident Report"` and parent blank)
- `ActivityLog[Troubleshooting Actions]` is required when a child incident row is being set to `Resolved` and the parent is not already `Resolved`
- `ActivityLog[Risk]` is required for Incident Reports except `Incident_ProductionProblem_OperatorReport`
- `ActivityLog[Sub-Category]` is conditionally required based on the Lookup hierarchy for ActivityLog types

## How NL intent should map to execution

### Create

Example: `Create a new Incident Report with the following description: ...`

- Normalize to intent `create_incident_report`
- Force table `ActivityLog`
- Seed row payload:
  - `Category = "Incident Report"`
  - `Description = <text>`
  - `ActivityLog Status = "Unresolved"`
- Before execute:
  - resolve whether `Sub-Category` is required
  - if yes, fetch valid options from Lookup-backed ActivityLog type hierarchy
  - once sub-category is known, decide whether `Sub-Category 2` is required
  - require `Risk` unless sub-category exempts it
- Only execute after required fields are present

### Query

Example: `Give me an itemized list of unresolved Incident Reports created in the last 24 hours`

- Normalize to intent `query_unresolved_incident_reports`
- Build a `Find` selector over `ActivityLog`
- Keep query flows read-only, no confirmation needed
- Return normalized itemized objects, not raw AppSheet rows unless the caller asks

### Edit / resolve

Example: `Mark uebf ActivityLog as Resolved, with Troubleshooting Action as ...`

- Normalize to intent `resolve_activitylog_incident`
- `Find` parent rows with `CONTAINS([ActivityLogID], "uebf")`
- If 0 or >1 matches, stop and clarify
- If exactly 1 match:
  - create a child `ActivityLog` row
  - set `Parent ActivityLogID` to the matched parent
  - set `ActivityLog Status = "Resolved"`
  - set `Troubleshooting Actions = <text>`
  - copy `Category` / `Sub-Category` / `Sub-Category 2` explicitly for safety, even though the schema also provides parent-based initial values
  - because `ActivityLog Status` is user-defined, if the user explicitly says the ActivityLog should be `Resolved`, also set the matched parent `ActivityLog Status = "Resolved"`
- Only skip the parent status edit when the caller explicitly disables that sync behavior

### Delete

- Always resolve the record uniquely first
- Require explicit human confirmation in the chat layer
- Prefer exact `ActivityLogID` over fuzzy contains-match
- Return a dry-run preview before execute

## Confirmation and clarification policy

### Read/query flows

- can execute immediately once table + filters are understood
- ambiguous lookup terms should trigger clarification only when multiple rows match
- safe default is to return a compact itemized list

### Write/edit flows

- if schema-required fields are missing, return a clarification bundle
- if the record match is ambiguous, return concrete choices
- if the request mutates many rows, require extra confirmation

### Delete flows

- always explicit confirmation
- always show exact target row ids first

## Auth/config assumptions

- Runtime env file:
  - `projects/AppSheet/keydrop/prototype-app.env`
- Expected keys:
  - `APP_ID`
  - `APP_ACCESS_KEY`
  - optional `RUN_AS_USER_EMAIL`
- Tracked examples can live in:
  - `projects/AppSheet/secrets/prototype-app.env.example`
  - `projects/AppSheet/secrets/prototype-app.local.env`
- Real secrets should stay in keydrop or another gitignored runtime file, not in tracked docs

## Known risks / unknowns

- The schema map is good enough for column logic, but not a full substitute for live app behavior.
- `Update Mode` is expression-driven, so some users may still be blocked from add/edit/delete despite the API key unless server context or `RunAsUserEmail` aligns with app policy.
- The `ActivityLog` security filter has special server-host behavior. API behavior may differ depending on whether AppSheet treats the API request as server-hosted plus whether `RunAsUserEmail` is set.
- Parent incident status propagation is **not yet proven** from the synced artifacts alone. But when the user explicitly asks to set `ActivityLog Status = Resolved`, honor that instruction directly instead of waiting for inferred roll-up behavior.
- Delete safety is the biggest footgun. Keep delete confirmation in the chat layer even if backend execution exists.
- Generic cross-table CRUD is possible, but only ActivityLog incident flows are strong enough to expose first.

## Next recommended steps

1. Wire the main appsheet agent to call `appsheet_record_ops.py` in dry-run mode first.
2. Feed clarification responses back into the backend as structured field values.
3. Add live verification for parent incident status propagation so the agent can distinguish explicit user-driven parent status edits from app-managed roll-up behavior.
4. Add table-specific handlers for other high-value tables only after their required-field logic is verified.

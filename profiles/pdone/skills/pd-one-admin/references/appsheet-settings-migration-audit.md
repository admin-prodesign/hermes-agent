# AppSheet settings migration audit pattern

Use this when Andy asks about duplicated AppSheet user/settings columns between `HR_Employees` and `HR_Employees_AppSheet_Settings` (`HR_E_A_S`), especially for security filters, show-if logic, roles, teams, menus, notifications, and performance cleanup.

## Source of truth

Before concrete advice, read the migrated AppSheet skill and synced definition:

- `/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/SKILL.md`
- `/home/prodesign/.openclaw/workspace/docs/runbooks/appsheet-agent-rules.md`
- `/home/prodesign/.openclaw/workspace/projects/AppSheet/appsheet_definition.json`
- optional quick index: `/home/prodesign/.openclaw/workspace/projects/AppSheet/appsheet_schema_index.json`

Do not answer AppSheet schema/wiring questions from generic memory. The local synced definition is the canonical schema/design source unless Andy asks to refresh/sync first.

## Key current slices to inspect

In the synced definition, compare these slices first:

- `Current User` — source table `HR_Employees`, row filter usually `[Appsheet Email] = USEREMAIL()`.
- `Current User Settings` — source table `HR_Employees_AppSheet_Settings`, row filter usually `[Appsheet Email] = USEREMAIL()`.

A partially completed migration often looks like this:

- security filters/update modes already use direct `LOOKUP(USEREMAIL(), "HR_Employees_AppSheet_Settings", "Appsheet Email", ...)` calls;
- UX/show-if/action/view logic still uses `Current User[...]`, which means it still reads `HR_Employees`;
- `HR_Employees_AppSheet_Settings` columns may still have initial values/app formulas derived from `[PersonID].[...]`, so it is a cache/settings mirror rather than fully canonical.

## Deterministic audit recipe

Use a small Python script against `appsheet_definition.json` to count and extract references from `sections`:

```python
import json, re
p = '/home/prodesign/.openclaw/workspace/projects/AppSheet/appsheet_definition.json'
defn = json.load(open(p))
sections = defn['sections']

for needle in [
    'HR_Employees_AppSheet_Settings',
    'Current User Settings',
    'Current User',
    'LOOKUP(USEREMAIL(),"HR_Employees"',
    'LOOKUP(USEREMAIL(), "HR_Employees"',
]:
    print('\n###', needle)
    print({sec: txt.count(needle) for sec, txt in sections.items() if needle in txt})
```

Extract table blocks from `sections['Data Schema']`:

```python
def table_block(table):
    text = sections['Data Schema']
    m = re.search(rf'(?ms)^## Table: {re.escape(table)}\b.*?(?=^## Table: |\Z)', text)
    return m.group(0) if m else ''

def columns(table):
    return re.findall(r'^- \*\*(.*?)\*\* \((.*?)\)', table_block(table), re.M)

hr = dict(columns('HR_Employees'))
settings = dict(columns('HR_Employees_AppSheet_Settings'))
print(sorted(set(hr) & set(settings)))
```

Extract the two user slices from `sections['Slices']`:

```python
for block in re.split(r'(?=^## Slice: )', sections['Slices'], flags=re.M):
    if block.startswith('## Slice: Current User') or block.startswith('## Slice: Current User Settings'):
        print(block[:2500])
```

## Migration recommendation pattern

Default target ownership:

- `HR_Employees`: HR/personnel identity facts (`PersonID`, employee ID, names, employment status, managers, BU, job title, HR history).
- `HR_Employees_AppSheet_Settings`: AppSheet access/UX/permissions (`Appsheet Email` if treated as login identity, language if app preference, dashboard type, views/menu/navigation, roles, notification groups, combined roles, data access mode, `Data_Days_*`, `_Is_*` booleans).

Migration order:

1. Keep already-working security filters on `HR_Employees_AppSheet_Settings`; do not churn them first.
2. Move app-setting reads in UX/actions/views from `Current User[...]` to `Current User Settings[...]` in batches:
   - `Appsheet Roles`
   - `Combined Appsheet Roles`
   - `Appsheet Navigation Bar`
   - `Appsheet Menu Items`
   - `Appsheet Views Access`
   - `Appsheet Dashboard Type`
   - `Appsheet Notification Group`
3. Keep `Current User[...]` for genuine HR identity/profile context (`PersonID`, managers, employment status, names) unless the setting table has intentionally become canonical for that field.
4. After references move, remove HREAS initial-value dependencies like `[PersonID].[Appsheet Roles]` if those fields should be manually/canonically maintained in HREAS.
5. Hide/deprecate duplicate AppSheet-setting columns in `HR_Employees`; delete only after a fresh expression audit shows no dependencies.

## View-access cleanup pattern

When cleaning `HR_E_A_S[Appsheet Views Access]`, do not remove a token just because `Appsheet Notification Group` appears to cover it. First classify each view token against the current editor definition:

- **Migrate ShowIf first:** the view is active and still gates on `IN("<view>", Current User Settings[Appsheet Views Access])`.
- **Safe role/group gate:** the view ShowIf uses `Current User Settings[Combined Appsheet Roles]` intersected with `LOOKUP("<view>", "Lookup", "LookupID", "Viewable Roles")`. A common pattern keeps the existing nav/menu surfacing guard and replaces only the access gate.
- **Inactive/stale cleanup:** `Lookup[Active] = "N"`, no `Presentation.Controls` entry, and no `Presentation.MenuEntries` entry. Remove these values as stale configuration, not as live permission simplification. Old Case split views such as completed/uncompleted Tech Dev, Facilities Repair, and IT variants are common examples.
- **Keep / separate design needed:** personal/default views such as `HR_MyData`, `HR_Employees_BasicList`, and `ActivityLog_MyActivity` may not be covered by Notification Group and should not be removed by a group-redundancy audit alone.

After editing ShowIf through `/api/saveapp`, reload `/api/loadApp` and verify the exact targeted `Presentation.Controls[].ShowIf`. Saving latest/editor version does not promote stable; report that distinction explicitly.

## Output shape

For Andy, lead with the concrete current-state finding, not a request for exports if the local synced definition exists. Include:

- definition timestamp/app id checked;
- which table/slice is currently canonical for security filters vs UX/show-if/action logic;
- duplicated columns;
- migration plan and safe batch order;
- explicit note that no AppSheet rows or app definition were modified, if read-only.
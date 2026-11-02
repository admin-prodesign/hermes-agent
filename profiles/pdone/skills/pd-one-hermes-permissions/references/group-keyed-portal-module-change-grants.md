# Group-keyed portal module change grants

Use when Andy/admin authorizes a department Google Group to ask PD One to modify that department’s live Portal module.

This is **request-authorization**, not view ACL, not Drive sharing, and not a personal `allow_emails` grant.

## Pattern

1. Audience key is Google Group `expanded_members` from `hermes.google-workspace-group-memberships.v1` (identity cache emails, including associated Gmail). Exact Mattermost sender id only. Never display-name matching. Never mint a second Google Admin lookup.
2. Map module id `/path/` → group email → department Mattermost channel id in `config/portal_module_change_grants.json`. Enable only live modules. Neighboring modules do not inherit another module’s grant.
3. Encode a narrow role `dataAccess.portalModuleChange` plus a scope such as `portal-finance-module-change` on the department roles so injected policy is not prompt memory. The **runtime gate** is still group membership, not the role name.
4. Hard check: `tools/portal_module_change_authorize.py`. Fail closed on missing/stale/incomplete identity or group cache.
5. **Channel vs DM:** auto-approve and execute only in the mapped department channel (semi-public). In DM or any other channel: do not execute; bilingual redirect to the department channel so the rest of the department can see the request. Never do the work from a DM and post a summary later.
6. In-scope = layout/tabs/copy/filters/metrics already in that module’s contract. Denied: ACL widening, other modules, payroll/GL/unit prices, customer full names, source-system writes, Drive sharing, gateway/config/policy expansion, Facilities paper acceptance, mold write-off.
7. View ACL stays as the portal manifest. CXO view ≠ change-request authority unless that person is also in the department group.
8. Regenerate exact-sender cache with `tools/mattermost_policy_lookup.py generate-cache` and read back a department-role user (redact). No gateway restart. Do not restart `pd-one-public-static.service` unless origin Python actually changed.

## Finance live grant (2026-09-04)

- Group: `finance@prodesign-group.com`
- Module: `finance` `/finance/`
- Channel: `fej3f4mkftdduyfi84ymkkyksc` (`🅱️ 財務部 | Finance BU`)
- If the Finance head is not in `expanded_members`, do not add a personal portal email bypass. They must be in Directory `finance@`.

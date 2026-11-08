# Historical search source ladder + source reporting

Use this for PD One Mattermost requests that ask for historical info, dilution/process parameters, “do we have a rule for X”, or any multi-source search.

## Permission first

1. Resolve exact Mattermost `sender_id` from gateway context.
2. Apply channel policy + requester roles/dataAccess.
3. Inter-Department Discussion (`miiyt4zm9frexdbhxokxqgyxeo`) pre-approves ordinary read-only Mattermost/Yammer historical synthesis for in-scope ops questions. Do **not** wait for Andy/admin for normal process lookups.
4. Domain denials still apply: if `financeRecords`/`payroll`/`hrPrivate*`/`credentials` are deny, refuse those domains even when Yammer access is allowed.

## Source ladder (run before answering “not found”)

1. Current thread / attached files in-thread.
2. In-scope work manuals / quality standards / company docs.
3. `mcp_pdone_safe_ops_pd_one_mattermost_member_search` with exact `sender_id` (member-visible channels only).
4. `mcp_pdone_safe_ops_pd_one_yammer_archive_search` with exact `sender_id` and `origin_channel_id`.

Only after those in-scope sources are checked may PD One say no historical rule was found.

## Source reporting (mandatory)

In every bilingual search reply, include:

```text
Sources checked / 已查來源
- ...
Blocked / out of scope / 超出權限而未查
- ... (if any)
```

Use the `sources_searched` field returned by tools. Do not invent sources. Do not claim “full Mattermost and Yammer check” unless both were actually searched.

## Tool notes

- Yammer CLI path is also available via `tools/pd_one_safe_ops.py yammer-archive-search`.
- Archive DB: `legacy-openclaw/workspace/projects/yammer-migration/archive/search/yammer_archive.sqlite` (read-only immutable).
- Excerpts are bounded; no raw transcript dumps.

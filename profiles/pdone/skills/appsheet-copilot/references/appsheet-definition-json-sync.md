# AppSheet Definition JSON Sync

Use this reference when syncing, parsing, or relying on Pro-Design AppSheet app definitions.

## Canonical source

All AppSheet definition sync and schema/config inspection should use authenticated editor JSON from:

```text
GET https://www.appsheet.com/api/loadApp/<app_id>
```

This is a general AppSheet skill rule, not just the HR settings migration rule. Periodic and manual definition syncs must use this JSON path as their canonical input whenever authenticated editor access is available.

For the Pro-Design deployed app, the live Nemo artifacts are under the pdone legacy OpenClaw workspace:

```text
/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace/data/appsheet-definitions/f2073120-8c2e-4930-b13c-105838c5e4c3/latest/latest_raw_app.json
```

The generated bundle is `latest.json` in that same `latest/` directory. Older `/home/prodesign/.openclaw/workspace/...` paths are stale.

## Deprecated path

The old AppSheet HTML app documentation path is deprecated for current work:

- `template/appdoc?appId=...`
- `Application Documentation.html`
- `tools/appsheet-migration/scripts/doc-to-md.py`
- `latest.html`

Keep old HTML artifacts only for provenance or historical troubleshooting. Do not build new AppSheet schema, security-filter, show-if, bot, or write-path analysis on the HTML parser if `/api/loadApp` is available.

## Why JSON-first matters

`/api/loadApp` exposes exact editor-managed structures that HTML/generated docs can omit or flatten:

- `AppData.DataSets[*].DataFilter` security filters
- `AppData.DataSchemas[*].Attributes[*].IsKey`
- `IsKeyPart`, `IsLabel`, `IsRequired`, `IsVirtual`, `IsHidden`, `IsReadOnly`, `IsSensitive`
- column defaults/formulas/type qualifier data where present
- slices and row filters
- presentation controls/views/show-if expressions
- `Behavior.AppBots`, `AppEvents`, `AppProcesses`
- process nodes and branch/task/action wiring
- top-level `Version`, `StableVersion`, `LastModified`

Known failure avoided: `HR_Employees_AppSheet_Settings` (`HR_E_A_S`) API edits must key rows by `PersonID`. Old generated docs encouraged using `Row ID`; raw editor JSON correctly shows `PersonID` as `IsKey=true` / `IsKeyPart=true` / `IsLabel=true`.

## Sync/tooling pattern

Live systemd unit `appsheet-definition-sync.service` runs every 6 hours via:

```text
/home/prodesign/.hermes/profiles/pdone/scripts/appsheet_definition_sync_guarded.sh
```

That wrapper flocks and executes:

```text
/home/prodesign/.hermes/profiles/pdone/scripts/appsheet_definition_sync.sh
```

Manual quiet run:

```bash
NOTIFY_ON_SUCCESS=0 NOTIFY_ON_FETCH_FAIL=0 NOTIFY_ON_PARSE_FAIL=0 \
/bin/bash /home/prodesign/.hermes/profiles/pdone/scripts/appsheet_definition_sync.sh
```

Expected outputs:

- `latest_raw_app.json` — canonical raw parsed app JSON
- `latest.json` — generated machine-readable bundle, with `canonical_raw_app_path`, normalized `editor_api_coverage`, source verification, checksums, and Markdown sections
- `latest.md` — generated human-readable report

After parser changes, regenerate the relationship/schema map from the pdone `appsheet-copilot` skill copy on Nemo.

## Chromium ownership pitfall

The fetch decrypts AppSheet editor cookies with:

```text
.../legacy-openclaw/browser/openclaw/user-data/Default/Cookies
.../legacy-openclaw/browser/openclaw/user-data/Local State
```

If a root Chromium session opens that profile, `Local State` becomes `root:root` mode `600`. The user timer then dies in ~1s with `cp: cannot open '.../Local State' for reading: Permission denied` even when cookies are still valid. This is not a 401.

Repair only when no Chromium is using that `--user-data-dir`:

```bash
docker run --rm --user 0:0 --entrypoint chown \
  -v /home/prodesign/.hermes/profiles/pdone/legacy-openclaw/browser/openclaw/user-data:/data \
  pdone/browser-vnc:latest \
  -R 1001:1001 /data
```

The sync script now attempts that bounded chown before failing closed. Do not launch the AppSheet editor profile as root; Looker uses `/data/chrome`, not this user-data dir.

## Parser expectations

JSON-derived reports should preserve or expose at least:

- table/schema/source/provider/update mode metadata
- key and label columns
- `is_key`, `is_key_part`, `is_label`, `is_required`, `is_virtual`, `is_hidden`, `is_read_only`, `is_sensitive`
- defaults/formulas/type qualifiers where available
- table security filters
- slice source and row-filter expressions
- presentation controls/show-if expressions
- bot/event/process wiring and process nodes

## Guardrails

- Treat `/api/loadApp` as read-only inspection unless a separate `/api/saveapp` workflow has been explicitly approved and tested for the exact change class.
- Generated Markdown is for readability; use raw JSON for API-write planning, exact key metadata, or hidden/ambiguous wiring.
- Do not commit raw endpoint wrappers if they may contain unnecessary session/cache data. Prefer committing compact raw app JSON only in approved private backups.
- For shared Pro-Design AppSheet rules, keep Hermes `appsheet-copilot` and OpenClaw `skills/appsheet-copilot` aligned.

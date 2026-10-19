# PD One safe ops

PD One's safe-ops CLI and MCP server ship in the Hermes release. The pdone
profile does not need its own copies of `pd_one_safe_ops.py` or
`pd_one_safe_ops_mcp.py`. Site-specific ids, emails, and paths come from the
profile `config.yaml` (or the same `PDONE_*` environment variables) at call
time. This page uses placeholders only.

## Rollout

1. Rebuild the nemo release from `main` with the `nemo` extra
   (`honcho-ai`, PyYAML, requests, and the `[mcp]` client stack): `hermes pm` / the release
   build you already use, passing `--extra nemo`.
2. Point the pdone profile `mcp_servers.pdone_safe_ops` command at
   `tools/pd_one_safe_ops_mcp.py` in that release, using the release
   interpreter. Do not copy the server into `profiles/pdone/tools/`. A script's
   import path is its own directory, and a copy beside an old module would
   import that module.
3. Set the `pd_one` values below on the pdone profile.
4. Retire `profiles/pdone/tools/pd_one_safe_ops.py` and
   `profiles/pdone/tools/pd_one_safe_ops_mcp.py` after the release server
   answers the same command names.

CLI entry stays `python tools/pd_one_safe_ops.py <subcommand>` inside the
release. Approval protocol field names (`andy_decision` and the rest) are
unchanged. The display fallback when `owner_display_name` is unset is the
word `Owner`.

`pd_one.load_profile_tools` defaults to false. Leave it false. The MCP server
does not import the profile `tools/` directory unless that flag is true, and
even then it will not call a release-owned name from the profile file.

## Worker scheduling

Monthly scheduling stays on its own stdio server, `pdone_worker_scheduling`,
so a long solve does not block or circuit-break `pdone_safe_ops`. Point
`mcp_servers.pdone_worker_scheduling` at
`<release>/tools/pd_one_worker_scheduling_mcp.py` and start it with the
release interpreter. Do not copy the file into a profile `tools/` directory.
Keep this server's `timeout` long enough for a normal bounded
`solve_preview` (the tool's own default is 420 seconds). A timeout at that
bound is a tool failure, not an infeasible schedule.

```yaml
mcp_servers:
  pdone_worker_scheduling:
    command: <release>/.venv/bin/python
    args:
      - <release>/tools/pd_one_worker_scheduling_mcp.py
    timeout: 900
```

## Config

Unknown top-level keys are kept. A `pd_one:` section does not need a core
default. Structured keys win, then `pd_one.values.PDONE_*`, then the process
environment of the same name. Secrets stay in `.env` / the secret store
(Mattermost token, AppSheet keys). The values below are ids and paths, not
secrets.

```yaml
pd_one:
  profile: pdone
  load_profile_tools: false
  owner_display_name: Owner
  owner_mm_username: owner-username
  owner_mm_user_id: mattermost-user-id
  owner_name_en: Owner Name
  channels:
    admin_alert: mattermost-channel-id
    inter_dept: mattermost-channel-id
    work_manual: mattermost-channel-id
  drive:
    parent_folder: drive-folder-id
    sheet: spreadsheet-id
    source_doc: document-id
    source_spreadsheet: spreadsheet-id
    gdoc_1: document-id
  emails:
    admin: placeholder@example.com
    andy_lin: placeholder@example.com
    hr: placeholder@example.com
  apps_script:
    worker_scheduling:
      script_id: apps-script-id
    appsheet_helper:
      script_id: apps-script-id
    appsheet_data_mirror:
      script_id: apps-script-id
    finance_forex:
      script_id: apps-script-id
  scheduling_rule_w12_name: Worker Name
  portal_public_hosts: portal.example.com,portal-alt.example.com
  docx_repair_ticket_id: PDAPP-EXAMPLE
  external:
    sqlsrv_readonly: /path/to/sqlsrv_readonly.py
    winrm_python: /path/to/winrm/bin/python
    winrm_site_packages: /path/to/winrm/site-packages
    office_no_corruption_gate: /path/to/office_no_corruption_gate.py
    schema_map: /path/to/prodesign-schema-map.json
    admin_approval_tickets: /path/to/admin_approval_tickets.py
    gog: /path/to/gog
    gog_credentials: /path/to/gog-credentials.json
    freecadcmd: /path/to/freecadcmd
    freecadcmd_alt: /path/to/FreeCADCmd
    freecad_lib: /path/to/freecad/lib
    office_deb_root: /path/to/office-visual-qa/apt-debs
    docx_repair_python: /path/to/release/.venv/bin/python
    hermes_bin: /path/to/hermes
```

| Config | Also accepted as |
| --- | --- |
| `profile` | Profile folder name under `profiles/`. Default `pdone`. `profile_name` is the same key. |
| `channels.admin_alert` | `PDONE_ADMIN_ALERT_CHANNEL_ID` |
| `channels.inter_dept` | `PDONE_INTER_DEPT_CHANNEL_ID` |
| `channels.work_manual` | `PDONE_WORK_MANUAL_CHANNEL` |
| `owner_mm_username` | `PDONE_OWNER_MM_USERNAME` |
| `owner_mm_user_id` | `PDONE_OWNER_MM_USER_ID` |
| `owner_name_en` | `PDONE_OWNER_NAME_EN` |
| `owner_display_name` | `PDONE_OWNER_DISPLAY_NAME` |
| `drive.parent_folder` | `PDONE_PARENT_FOLDER_ID` |
| `drive.sheet` | `PDONE_SHEET_ID` |
| `drive.source_doc` | `PDONE_SOURCE_DOC_ID` |
| `drive.source_spreadsheet` | `PDONE_SOURCE_SPREADSHEET_ID` |
| `drive.gdoc_N` | `PDONE_GDOC_N` |
| `emails.<suffix>` | `PDONE_EMAIL_<SUFFIX>` |
| `apps_script.<name>.script_id` | `PDONE_APPS_SCRIPT_<NAME>` |
| `scheduling_rule_w12_name` | `PDONE_SCHEDULING_RULE_W12_NAME` |
| `portal_public_hosts` | `PDONE_PORTAL_PUBLIC_HOSTS` (comma-separated) |
| `docx_repair_ticket_id` | `PDONE_DOCX_REPAIR_TICKET_ID` |

`portal_public_hosts` must be set. An empty list does not classify a public
URL as the local probe. Any other `PDONE_*` name can be set under
`pd_one.values`.

## Profile folder

The release MCP server often runs with `HERMES_HOME` at the Hermes install
root. Capability registries, policies, and legacy project trees live in the
profile folder. `profile_root()` resolves that folder at call time:

1. `HERMES_PROFILE_HOME`, or `PD_ONE_PROFILE_HOME` when the first is unset.
2. The active Hermes profile, when the runtime names one: `HERMES_PROFILE_NAME`
   or `HERMES_PROFILE`, otherwise the profile implied by a profile-shaped
   `HERMES_HOME`, otherwise the sticky active profile.
3. `<HERMES_HOME>/profiles/<name>`, where `<name>` is `pd_one.profile`
   (or `pd_one.profile_name`), otherwise `pdone`.

When `HERMES_HOME` already points at a profile folder, that folder is the
profile root. Kanban boards and other shared state stay on the install root.

`pd_one` values come from `<HERMES_HOME>/config.yaml` with that profile
folder's own `config.yaml` layered on top (profile wins, key by key). The
gateway starts every stdio MCP server with `HERMES_HOME` set to the profile it
serves, so the safe-ops server reads the pdone config without an `env` entry.
An `env: {HERMES_HOME: ...}` in `mcp_servers.pdone_safe_ops` still wins, and
the profile layer above still applies when it names the install root.

## Running helpers from a read-only release

Releases are published read-only, and `tools/**/*.py` carries no exec bit. A
tool that runs a helper script always runs `<interpreter> <script>`: the
interpreter running the MCP server, or the configured one
(`pd_one.external.winrm_python` for the file-server content search). Children
get `HERMES_HOME` and the release on `PYTHONPATH`, so a helper started by a
different interpreter still imports `tools.pd_one_ops`.

## Apps Script self-registration

`pd_one.apps_script.<key>.script_id` still fills in the four built-in
projects (`worker_scheduling`, `appsheet_helper`, `appsheet_data_mirror`,
`finance_forex_notification`). Those keys cannot be replaced. An employee
registers an additional container-bound project with
`apps_script_project_ops` action `register_project`. The registry file is
`<profile home>/pd-one/apps-script-registry.json`, read on every call, so
adding a project does not reload MCP. The file is profile data, not part of
the release tree.

Dry-run is the default. It resolves the script id and the parent Drive file,
checks that the PD One Google account can see that file, and checks that the
bound session user is an owner or writer (directly or through a Google
Group). The requester is the bound session. A tool argument cannot supply a
different user id or email. Addresses outside the domain of
`pd_one.emails.admin` are refused. A live registration writes the registry
only when `confirm_live_register` is `RUN LIVE APPS SCRIPT REGISTER`.

A self-registered project can be listed, read back, or patched only by the
user who registered it, or by a user whose policy-cache roles include
`admin`. Patches stay dry-run unless `confirm_live_patch` is
`RUN LIVE APPS SCRIPT PATCH`, and a live patch still read-backs. Register,
patch, and readback append one line to
`<profile home>/pd-one/apps-script-audit.jsonl` (`who`, `at`, `script_id`,
`action`, `result`). The line has no tokens and no file contents.

`action=check_gog_scopes` reads JSON under `~/.config/gogcli` and reports
whether the token metadata includes
`https://www.googleapis.com/auth/script.projects` and a Drive read scope
(`drive.readonly`, `drive.metadata.readonly`, or full `drive`). It does not
print refresh tokens. gog usually keeps the refresh token in the OS keyring,
so a `scopes_not_found` result means the config directory has no scope list
to check. Re-consent without dropping services the account already uses:

```bash
gog auth add <pd_one.emails.admin> \
  --services <existing-services>,appscript,drive \
  --drive-scope readonly \
  --extra-scopes https://www.googleapis.com/auth/script.projects \
  --force-consent
```

Enable the Apps Script API and Google Drive API on the OAuth client first.
`gog auth list --json` shows the recorded grant. Run `check_gog_scopes`
again after consent.

### Post-merge deploy

1. Rebuild the nemo release from `main` and point `releases/current` at that
   build. Restart the pdone gateway so the MCP process loads this code.
   Later registrations do not need another reload.
2. Do not copy the server into `profiles/pdone/tools/`.
3. Run `check_gog_scopes` (or inspect `~/.config/gogcli`). If
   `script.projects` or Drive read is missing, re-consent with the command
   above.
4. Update the profile copies of `gog/SKILL.md` and
   `pd-one-hermes-permissions/SKILL.md` so they describe self-registration.
   Those skills are not in this repository.
5. Confirm a dry-run `register_project`, then a live register with the
   register phrase. Another employee cannot list that key. A policy-cache
   admin can. The four built-ins still list.

## HR columns

HRS tables (`HRS_Data`, `HRS_Data_MasterNames`) and HR-employee row payloads
drop private columns through `tools/pd_one_hr_fields.py`. That includes the
AppSheet probe, row get, `pd_one_appsheet_hr_employee_patch`,
`appsheet_record_ops` when the table is HRS or `HR_Employees`, and
`call_function_twin` when the twin is `hr`. Policy documents are not blanked;
the filter removes column values, not prose.

`pd_one_hr_private_lookup` is the only path that returns those columns, and
only when the bound Mattermost session is an HR or admin DM, or a channel
whose human members all have those roles. The destination is not a model
argument.

## Cron scripts on the pdone profile

HR sync, the reaper, the digest, and the typhoon check are profile scripts
under the pdone `scripts/` directory on the host. They are not in this
repository. A host edit that points a wrapper at `releases/current/.venv/bin/python`
is the same interpreter the cron runner now selects itself: `.py` files run
on that interpreter, and every script (including shell wrappers and
`#!/usr/bin/env python3` children) gets that `bin` first on `PATH`. Leaving
an old wrapper pointed at the same interpreter is harmless. Further runtime
changes belong in this repo, not in another host edit.

The typhoon check fetches `cwa.gov.tw` and `www.dgpa.gov.tw`. Python 3.14
enables `ssl.VERIFY_X509_STRICT`, and those chains fail with `Missing Subject
Key Identifier`. The runner mounts `cron/cwa_tls.py` only when the script text
contains `cwa.gov.tw` or `dgpa.gov.tw`, or the file name contains `typhoon`.
Verification and hostname checks stay on; only that flag is cleared, and only
for those hosts and their subdomains.

### Post-merge deploy

Use `scripts/deploy/nemo/` from this tree. Each build's audit and rollback
files still land under that profile's `upgrade-audits/<build>/`.

1. `probe.py` checks whether `git fetch <sha>` against the bare mirror
   answers. Exit 75 means it hung; `build.sh` then uses the GitHub tarball.
2. `build.sh --sha <sha> --mirror <bare-repo>` fetches that commit, installs
   `.[nemo]` (honcho-ai, PyYAML, requests, and `[mcp]`), installs the dashboard npm
   dependencies, and publishes a read-only release. It creates the release
   directory only after the source tree validates.
3. `cutover.sh --build <name>` runs the verifies the diff touches (`--full`
   runs every verify this deploy knows about), waits until pdone and the
   top-level default profile (PD Neo) are quiet, swaps `releases/current`,
   rewrites units and configs, and polls
   systemd plus the gateway and dashboard health endpoints.
4. The post-cutover check runs the cron scripts' safe checks immediately.
   Typhoon `840af263673e` fetches `cwa.gov.tw` and `www.dgpa.gov.tw` with the
   cron TLS mount. Digest `870dd7349151` must import `yaml`. Reaper
   `c9287579f167` runs only with `--dry-run` (or is compiled, when it has no
   such flag). HR sync `6adb0e5216c5` runs with `--dry-run` when the script
   declares that flag, and is compiled otherwise. It must not write AppSheet
   `HR_Employees`. Do not wait for the scheduled runs.
5. `rollback.sh --manifest upgrade-audits/<build>/manifest.json` restores the
   previous symlink, unit files, and configs. The new release directory stays
   on disk.

Before the idle gate, `cutover.sh` runs the safe-ops selftest from the new
release (`--skip-selftest` turns it off):

```bash
cd <release> && .venv/bin/python -m tools.pd_one_ops.selftest --hermes-home <home> --profile pdone
```

It calls every MCP tool once in dry-run with placeholder arguments: child
processes are planned and checked, not run; network is refused; writes outside
a scratch directory are refused. Then it starts each release helper with
`--help`. Exit 1 lists what failed and stops the deploy. `--allow-missing <key>`
(cutover: `--selftest-allow-missing`) accepts an external key that is absent on
the host on purpose. `--readonly-copy` runs the same test from a temp copy of
`tools/` with every file 0444.

Once `install_autodeploy.sh` has run on nemo, a merge to `main` runs these same
steps without a hand deploy: a timer on nemo polls GitHub for `main` about once a
minute, and nemo waits for idle profiles before it restarts anything. `cutover.sh`
exits 75 when the profiles never went quiet. One-time setup, the no-restart path
for docs and skills, retention, and the drift check are in
`scripts/deploy/nemo/README.md`. Stop `hermes-deploy-poll.timer` and
`hermes-deploy.path` before a hand deploy.

## Dependencies that stay outside the repo

`appsheet_record_ops.py` ships in `tools/pd_one_ops/`. The helpers below are
not copied. Each is `pd_one.external.<key>`. `exists()` is false when the key
is unset, so a status command can report it missing. `require()` raises
`MissingExternalConfig` (a `FileNotFoundError`) naming `pd_one.external.<key>`.

A launch whose argument is an unset external key never reaches the OS. The
tool returns `"error": "missing_external_config"` with the key, and the
message names every config file it read. Reading it in code raises
`MissingExternalConfig` (a `FileNotFoundError`).

| Key | What it is |
| --- | --- |
| `sqlsrv_readonly` | SQL Server ACL read helper. No in-repo default. |
| `winrm_python` | Interpreter for that helper. |
| `winrm_site_packages` | Site-packages for that interpreter. |
| `office_no_corruption_gate` | Office file gate. If unset, the release looks under the profile skills path `skills/pd-one/pd-one-admin/scripts/office_no_corruption_gate.py`, then fails with the config key. |
| `schema_map` | AppSheet schema map JSON. |
| `admin_approval_tickets` | Legacy approval-ticket helper. |
| `gog` | `gog` binary. |
| `gog_credentials` | gog credentials file. |
| `freecadcmd` / `freecadcmd_alt` / `freecad_lib` | FreeCAD. |
| `office_deb_root` | LibreOffice packages used by visual QA. |
| `docx_repair_python` | Interpreter for the ticket-bound docx repair. |
| `hermes_bin` | Hermes executable, when a command needs to re-invoke it. |
| `kanban_boards` | Optional override for the shared kanban boards directory. |

Legacy OpenClaw project trees (worker scheduling, AppSheet env files) stay on
the profile folder above. Commands that need them resolve that folder and fail
with the resulting path when the file is absent.

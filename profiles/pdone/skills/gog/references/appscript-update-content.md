# Updating bound Apps Script when `gog appscript` is read/run-only

Use when a Google Apps Script project must be patched programmatically and `gog appscript --help` exposes `get`, `content`, `run`, and `create`, but not an update command.

## When this path is the wrong tool

- Do not start here from a shared Mattermost room, and do not start here when `apps_script_project_ops` `list_registered_projects` omits the script id. That typed tool is the Mattermost path. This token workflow needs a shell, which a shared room blocks even for an admin sender. A sheet cell that says to paste into `Code.gs` is not the bound project. Do not `updateContent` a guessed id, and do not report a cell edit as a script change.
- Editor share on the spreadsheet lets a person open the bound editor. It does not register the project for this path. A Drive copy of the spreadsheet has a new script id; do not reuse the source project's URL. A pasted `Code.gs` file is not a successful `updateContent`.

## Safe update workflow

1. Export the current project content with `gog appscript content <scriptId> --json` and keep a short-lived before snapshot only while patching.
2. Patch the local `Code.js` and run a JavaScript syntax check where possible, e.g. `node --check Code.js` for V8-compatible syntax.
3. Get an OAuth access token from the same configured `gog` account without printing secrets:
   - export the refresh token to a restricted temp file with `gog auth tokens export <email> --out /tmp/token.json --overwrite`
   - read OAuth client credentials from the configured `credentials-<client>.json`
   - exchange refresh token for an access token at `https://oauth2.googleapis.com/token`
4. Build the Apps Script API payload from the exported project content, replacing only the intended file source. For `projects.updateContent`, send each file as `{name,type,source}`; omit read-only metadata fields from the payload.
5. `PUT https://script.googleapis.com/v1/projects/<scriptId>/content` with `Authorization: Bearer <access_token>` and JSON payload.
6. Re-fetch `gog appscript get` / `gog appscript content` and verify:
   - project `updateTime` advanced and `lastModifyUser.email` is the expected account
   - expected guard strings/functions are present
   - the remote file hash matches the patched local file
7. Delete temp token/access-token/payload/response files immediately after verification, especially if the script contains API keys or app access keys.

## Verifying bound form-submit webhook repairs

When repairing a bound Apps Script that posts Google Form/Sheet submissions to Mattermost, Slack, LINE, or another webhook:

- Preserve the existing user-visible message format by sampling prior destination messages and mapping live Sheet headers by name, not fixed column letters.
- Keep existing non-webhook behavior such as copying row formatting unless the user explicitly asks to remove it.
- Prefer a non-posting preview helper that returns the message body, but remember `gog appscript run --dev-mode` can fail with `404 notFound` if the project is not deployed as an API executable. Do not treat that run-channel failure as a failed script update.
- To avoid fake production messages, do not send a dummy webhook post into an employee-facing channel unless the user explicitly approves. Instead verify by: `projects.updateContent` status 200, re-fetching metadata/updateTime, re-fetching content/hash, local syntax check (`node --check` for V8-compatible JS), and Apps Script process history.
- For trigger evidence, call Apps Script API `processes:listScriptProcesses?scriptId=<id>` with a Gog-derived short-lived OAuth token and confirm recent `formRowOnFormSubmit`/target function executions or statuses. This confirms the installable trigger path exists without creating a test row or fake referral.
- After verification, delete exported refresh tokens, access-token responses, update payloads, and full source snapshots if they could contain secrets; keep only concise receipts/hashes and rollback source where safe.

## Pitfalls

- Do not commit or persist full Apps Script source snapshots or update responses if they may contain `ACCESS_KEY`, OAuth tokens, API keys, or deployment secrets. Keep only distilled notes or hashes.
- `gog appscript run <scriptId> <function> --dev-mode` may return `404 notFound` for projects/functions that are not exposed through the Execution API even though `updateContent` succeeds. Treat that as a run-channel limitation, not proof the saved script failed. Verify by content hash/update time and by the normal trigger/audit path.
- Avoid logging token exchange responses or file contents. Print only status codes, key presence, timestamps, and short hashes.

# PD One Mattermost status monitor

Maintains a single pinned Mattermost status post, bot avatar badge, bot description, and
`state/pd-one-mattermost-status/state.json` for downstream publishers (for example rpi5).

Runs headless on a timer (every five minutes on nemo). It is silent on success unless
`PD_ONE_STATUS_VERBOSE=1`.

## Install on nemo

After the release that contains this package is live under `releases/current`:

1. Set required environment variables in the gateway env file (or the systemd unit). At minimum:

   - `PD_ONE_STATUS_MATTERMOST_CHANNEL` — Mattermost channel id (no default in the repo).
   - `MATTERMOST_URL` and `MATTERMOST_BOT_TOKEN` (or `MATTERMOST_TOKEN`) — usually already in
     `gateway.systemd.env` for the pdone profile.

2. Optional provider checks (default on). Disable while migrating auth:

   - `PD_ONE_STATUS_PROVIDER_CHECK=0`
   - `PD_ONE_STATUS_CANARY=0`
   - `PD_ONE_STATUS_HERMES_CANARY=0`

3. Point the existing user systemd unit at the release copy. The unit file lives outside this
   repository; update **ExecStart** only, for example:

   ```ini
   [Service]
   Environment=HERMES_HOME=%h/.hermes/profiles/pdone
   Environment=PD_ONE_STATUS_EXPECTED_HERMES_HOME=%h/.hermes/profiles/pdone
   Environment=PD_ONE_STATUS_MATTERMOST_CHANNEL=<your-channel-id>
   Environment=PD_ONE_GATEWAY_ENV=%h/.hermes/profiles/pdone/gateway.systemd.env
   ExecStart=%h/.hermes/releases/current/.venv/bin/python -m tools.pd_one_ops.mattermost_status
   WorkingDirectory=%h/.hermes/releases/current
   ```

   Use the same `HERMES_HOME` / `PD_ONE_STATUS_EXPECTED_HERMES_HOME` values you already run the
   gateway with. `WorkingDirectory` should be the Hermes release root so imports resolve.

4. Reload and restart the timer:

   ```bash
   systemctl --user daemon-reload
   systemctl --user restart pd-one-mattermost-status.timer
   ```

## Dry run

```bash
cd ~/.hermes/releases/current
HERMES_HOME=~/.hermes/profiles/pdone \
PD_ONE_STATUS_MATTERMOST_CHANNEL=<channel-id> \
PD_ONE_STATUS_DRY_RUN=1 \
.venv/bin/python -m tools.pd_one_ops.mattermost_status
```

## Provider checks

When enabled, probes use the profile's configured utility lane (`auxiliary.monitor` when pinned,
otherwise the main `model` provider) through `hermes_cli.runtime_provider` and `call_llm` — no
Codex-specific OAuth paths. Metadata hits `PROVIDER_MODEL_URL_SUFFIX` (default `/v1/models`) on the
resolved base URL. The inference canary caches success and backs off on failure
(`PD_ONE_STATUS_CANARY_FAILURE_BACKOFF_SECONDS`, default 900s). The Hermes-path canary runs hourly
in a child process via `AIAgent`.

# Self-hosted agent service integration pattern

Use this reference when wiring a local self-hosted service into an agent runtime (for example an external memory backend, local API, model service, or sidecar) where credentials, containers, and runtime config must all line up.

## Safe install shape

- Keep the service under a dedicated directory below agent-managed state, e.g. `~/.hermes/services/<service-name>/`, instead of mixing it into the core agent checkout.
- Bind service ports to loopback unless there is an explicit exposure requirement: `127.0.0.1:<host-port>:<container-port>`.
- Use non-default host ports for dependencies such as Postgres/Redis to avoid collisions with existing stacks.
- Put the user-editable secret in a single private key file, separate from generated `.env` files:
  - `openrouter.key.env` or equivalent: `chmod 600`, contains only `PROVIDER_API_KEY=...`.
  - Generated `.env`: also `chmod 600`, created by a small render script; never print secret values in logs or final replies.
- Create start/stop scripts with `chmod 700`; start script should render `.env`, run compose up/build, then perform a health check.

## Workflow

1. Validate prerequisites first: Docker/Compose availability, port availability, existing containers, and current agent config path.
2. Create/clone the service repo and overlay any reviewed self-host config files.
3. Write the key-file template and render script before asking the user for the secret.
4. Configure the agent conservatively before first live use:
   - prefer on-demand/tool recall over automatic injection when evaluating memory backends;
   - use a separate workspace/namespace for the service;
   - avoid migrating native curated memories into a new backend unless explicitly requested.
5. Do not start containers until the key file exists and required env values are non-empty; validate without printing the secret.
6. For slow Docker builds/pulls, start with `background=true` and `notify_on_complete=true`; poll status briefly, then report that the build is still running instead of blocking indefinitely.
7. After start, verify all layers:
   - `docker compose ... ps`
   - service health endpoint, e.g. `/openapi.json` or `/health`
   - agent CLI/status command
   - logs for API and worker services
8. If the build is intentionally interrupted, report it as an interrupted pull/build rather than a service failure, and confirm no containers are running before the next attempt.
9. Back up durable agent config/state after successful config changes when the environment has a configured backup repo.

## Reporting expectations

- Provide exact paths for the user-editable key file, start/stop scripts, and main config.
- State whether containers are actually running or only configured/pending.
- Redact credentials and say only that required key values are present.
- Include the local URL/ports and the verification commands/results.
- If first build is still in progress, name the tracked process/session and say which checks remain after completion.

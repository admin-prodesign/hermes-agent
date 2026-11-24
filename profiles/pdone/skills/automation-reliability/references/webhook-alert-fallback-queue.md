# Webhook alert fallback queue pattern

Use this when an unattended local producer sends failure alerts to an agent/webhook endpoint and the alert must not be lost if the gateway/webhook listener is down.

## Pattern

1. Preserve the original human-visible alert path first.
   - Existing Discord/Mattermost/email alerting remains the primary path.
   - The agent/webhook notification is a secondary best-effort path.

2. Add a tiny local bridge script.
   - Build a bounded JSON payload with `source`, `severity`, `summary`, `detail`, `command`, `host`, `run_id`, and timestamp.
   - Load the webhook secret from local state, sign the request, and POST to loopback when possible.
   - Tail/truncate verbose logs before writing/sending.

3. Queue on delivery failure.
   - On connection refused, timeout, non-2xx, or signing/config exceptions, append one JSON line to a durable queue file.
   - Include `queued_at` and `queue_reason`.
   - Return non-zero for manual tests, but production callers should invoke the secondary bridge with `|| true` so primary alerting is never broken by agent downtime.

4. Drain with a no-agent cron/script worker.
   - Frequent schedule is OK if the worker is silent on empty queue.
   - Use a lock file or atomic rename to avoid concurrent drains.
   - Cap alerts per run and requeue overflow.
   - Move malformed or failed records to a `failed/` directory with enough context for recovery.

5. Guard remediation scope in the queued prompt.
   - The agent may inspect bounded local evidence and apply low-risk reversible fixes.
   - Require explicit approval for restarts, process kills, destructive cleanup, token/gateway changes, external-send replays, or production-impacting writes.

## Verification checklist

- Compile/lint the bridge and worker scripts.
- Validate shell wrappers with `bash -n`.
- Dry-run the bridge without network and parse JSON.
- Verify successful POST behavior with a tiny local HTTP server on a random loopback port; assert signed headers/payload arrive and no queue file is created.
- Force a temporary delivery failure using an alternate queue file and confirm exactly one queued JSONL row.
- Run the queue worker against an empty queue and verify zero stdout/stderr.
- Confirm the cron job is enabled and has a successful empty tick.
- Confirm the queue is empty after removing test records.
- For Hermes gateway webhooks, compare config mtime to service start time (`stat ~/.hermes/config.yaml`; `systemctl --user show hermes-gateway -p ActiveEnterTimestamp --value`) and check `ss -ltnp | grep ':<port>'` / `curl http://127.0.0.1:<port>/health`. If config changed after gateway start, the adapter may not be loaded until a restart; fallback queue coverage is the safe interim state.

## Worker subprocess hygiene

- Invoke agent subprocesses in quiet/tool mode when available (for Hermes: `hermes chat -Q --source tool ...`) so scheduled triage output contains the final result rather than banners/session noise.
- Strip any remaining machine-readable session headers (for Hermes, lines starting `session_id:`) before printing the worker output to cron delivery.
- Keep empty queue ticks silent: exit 0 with no stdout/stderr.

## Pitfalls

- Do not make the webhook alert the only alert path until the webhook listener, gateway, and drain worker are independently monitored.
- Do not assume a gateway config edit enabled a webhook adapter in the already-running service; verify the port or restart the gateway through an approved/safe channel.
- Do not restart the live chat gateway from the same conversation path when it may interrupt the user; prefer fallback queue operation and report the restart as a remaining blocker unless the user approves a safe restart path.
- Do not let frequent empty queue checks produce chat noise.
- Do not persist secrets in queued payloads; queue enough evidence to investigate, not raw credentials.
- Do not auto-replay external sends from queued alerts without approval and idempotency keys.

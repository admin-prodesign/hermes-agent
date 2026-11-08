# PD Neo → PD One runtime watchdog pattern

Use this when PD Neo-side infrastructure, Honcho, embeddings, gateways, or model-provider health issues must remain visible to PD One after the original troubleshooting session ends.

## Goal

Create a low-noise, admin-only reverse federation path that records actionable warnings/errors for PD One without posting employee-facing messages or duplicating normal alerts.

## Canonical reverse rail

- Reverse event writer: `/home/prodesign/.hermes/scripts/pd_neo_to_pd_one_event.py`
- Reverse queue: `/home/prodesign/.openclaw/workspace/data/cross-agent/pd-neo-to-pd-one/queue.jsonl`
- Event direction: `pd-neo-to-pd-one`
- Typical event type: `pd-neo.runtime_note`
- Privacy: `admin-only`

Use `--dry-run` first, then one live forced handoff for a receipt.

## Watchdog design

1. Keep checks bounded and local:
   - health endpoints, service status, queue counters, bounded log tails;
   - no broad chat/log transcript search;
   - no automatic employee-facing posts.
2. Compute a stable signature from finding kind/severity/bounded detail.
3. Persist cooldown state under the active profile, e.g. `~/.hermes/profiles/pdone/state/<watchdog>.json`.
4. Stay silent on healthy ticks and on repeated same-signature findings inside cooldown.
5. Emit concise stdout only when a new handoff is written or when the watchdog itself fails.
6. Register the cron job in `/home/prodesign/.hermes/profiles/pdone/supervisor/automations.json` with alert expectations and autorepair policy.

## Example live write

```bash
python3 /home/prodesign/.hermes/scripts/pd_neo_to_pd_one_event.py \
  --source pdneo-honcho-local-embedding-watchdog \
  --event-type pd-neo.runtime_note \
  --severity warning \
  --privacy-scope admin-only \
  --summary 'Honcho/Ollama embedding watchdog found warning finding(s)' \
  --detail '<bounded JSON evidence>' \
  --source-path /home/prodesign/.hermes/services/honcho-pd-neo \
  --destination-path /home/prodesign/.openclaw/workspace/data/cross-agent/pd-neo-to-pd-one/queue.jsonl \
  --desired-response-mode 'admin-only monitoring/triage; no employee-facing relay' \
  --idempotency-key '<source>:<signature>' \
  --run-id '<source>:<signature>'
```

## Verification receipts

After live emission, read back only metadata unless detail is needed:

```bash
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/home/prodesign/.openclaw/workspace/data/cross-agent/pd-neo-to-pd-one/queue.jsonl')
rows=[json.loads(l) for l in p.read_text().splitlines() if l.strip()]
r=rows[-1]
print(r['schema_version'], r['direction'], r['event_type'], r['severity'], r['idempotency_key'])
PY
```

Expected shape:

```text
pd-federation.v1 pd-neo-to-pd-one pd-neo.runtime_note warning <source>:<signature>
```

## Cron pattern

Use a no-agent cron for deterministic watchdogs:

- `no_agent=true`
- `profile=pdone`
- `enabled_toolsets=["terminal"]`
- `deliver=origin`
- stdout silent on no-op ticks

Run once immediately after creation and then list the job to verify `enabled=true`, `state=scheduled`, and the expected `next_run_at`.

## Safety boundaries

- Do not auto-restart Hermes/OpenClaw gateways from the watchdog.
- Do not change model/provider/embedding config automatically.
- Do not re-embed or delete queues automatically.
- Do not post employee-facing messages.
- For Honcho/embedding warnings, describe whether the issue is generation-provider, OAuth proxy, local embedding capacity, or queue backlog; these have different remediations.

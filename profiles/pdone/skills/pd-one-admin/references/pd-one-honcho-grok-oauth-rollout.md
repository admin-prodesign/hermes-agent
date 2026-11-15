# PD One Honcho Grok OAuth Rollout Notes

Use with `references/pd-one-honcho-model-config-triage.md` when moving Honcho generative paths to Grok/xAI via Hermes OAuth proxy.

## Durable pattern
Honcho does not consume xAI OAuth directly. Put the Hermes OAuth proxy between Honcho and xAI, then configure Honcho with its normal OpenAI-compatible transport.

```text
Honcho container -> http://172.17.0.1:8645/v1 -> Hermes xAI OAuth proxy -> xAI/Grok
```

## Known-good proxy service
A one-off background proxy is enough for a smoke test but not enough for Honcho service config. Make it persistent with a user systemd unit under the `pdone` profile.

Example unit:

```ini
[Unit]
Description=PD One Honcho xAI Grok OAuth proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=HERMES_HOME=/home/prodesign/.hermes/profiles/pdone
WorkingDirectory=/home/prodesign/.hermes/profiles/pdone
ExecStart=/home/prodesign/.hermes/runtime/current/.venv/bin/hermes proxy start --provider xai --host 172.17.0.1 --port 8645
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

Enable/check:

```bash
systemctl --user daemon-reload
systemctl --user enable --now pdone-xai-oauth-proxy.service
systemctl --user is-enabled pdone-xai-oauth-proxy.service
systemctl --user is-active pdone-xai-oauth-proxy.service
loginctl show-user prodesign -p Linger
curl -fsS --max-time 10 http://172.17.0.1:8645/health
```

Expected health:

```json
{"status":"ok","upstream":"xAI Grok OAuth","authenticated":true}
```

## Known-good Honcho model config shape
Use the installed Honcho nested config schema, not legacy flat `PROVIDER`/`MODEL` keys. Apply the same OpenAI-compatible proxy settings to all text-generation paths that should use Grok.

```toml
[deriver.model_config]
transport = "openai"
model = "grok-4.20-0309-non-reasoning"
max_output_tokens = 2048

[deriver.model_config.overrides]
base_url = "http://172.17.0.1:8645/v1"
api_key = "dummy"

[summary.model_config]
transport = "openai"
model = "grok-4.20-0309-non-reasoning"
max_output_tokens = 2048

[summary.model_config.overrides]
base_url = "http://172.17.0.1:8645/v1"
api_key = "dummy"

[dialectic.levels.minimal.model_config]
transport = "openai"
model = "grok-4.20-0309-non-reasoning"
max_output_tokens = 512

[dialectic.levels.minimal.model_config.overrides]
base_url = "http://172.17.0.1:8645/v1"
api_key = "dummy"

[dream.deduction_model_config]
transport = "openai"
model = "grok-4.20-0309-non-reasoning"

[dream.deduction_model_config.overrides]
base_url = "http://172.17.0.1:8645/v1"
api_key = "dummy"
```

Repeat for every configured `dialectic.levels.*.model_config` plus `dream.induction_model_config` when those should use Grok. Keep embeddings separate.

## CLI/auth pitfalls
Use the installed Hermes console script with the explicit PD One profile home. Do **not** tell Andy to run `python3 cli.py ...` from a checkout; the system Python may miss Hermes dependencies such as `prompt_toolkit`, and the checkout may not match the active runtime.

```bash
export HERMES_HOME=/home/prodesign/.hermes/profiles/pdone
/home/prodesign/.hermes/runtime/current/.venv/bin/hermes auth status xai-oauth
/home/prodesign/.hermes/runtime/current/.venv/bin/hermes proxy status
```

If OAuth is actually revoked, prefer a real logout/re-add over `auth reset`: reset clears local exhaustion/cooldown state but may leave the bad refresh token in place.

```bash
/home/prodesign/.hermes/runtime/current/.venv/bin/hermes auth logout xai-oauth
/home/prodesign/.hermes/runtime/current/.venv/bin/hermes auth add xai-oauth --type oauth --manual-paste
```

Model names must be discovered from the live proxy/account before editing Honcho config. `grok-4.1-fast-non-reasoning` was not available in one rollout; `grok-4.20-0309-non-reasoning` was the working low-latency non-reasoning model.

```bash
curl -fsS http://172.17.0.1:8645/v1/models -H 'Authorization: Bearer dummy'
```

## Validation sequence
1. Back up `/home/prodesign/.hermes/services/honcho-pd-neo/config.toml` with a timestamp before editing.
2. Validate the edited config through the Honcho container's installed settings classes before restart. Copy it to `/tmp/config.toml`, run from `/tmp`, and set `PYTHONPATH=/app`/venv path so the current image parses the same settings model.
3. Copy the config into both API and deriver containers, then restart only those containers.
4. Verify runtime settings from inside the API container:

   ```bash
   docker exec -i honcho-pd-neo-api-1 sh -lc 'VIRTUAL_ENV=/app/.venv PATH=/app/.venv/bin:$PATH PYTHONPATH=/app python - <<"PY"
   from src.config import settings
   for label, cfg in [
       ("deriver", settings.DERIVER.MODEL_CONFIG),
       ("summary", settings.SUMMARY.MODEL_CONFIG),
       ("dialectic low", settings.DIALECTIC.LEVELS["low"].MODEL_CONFIG),
       ("dream deduction", settings.DREAM.DEDUCTION_MODEL_CONFIG),
   ]:
       print(label, cfg.transport, cfg.model, cfg.overrides.base_url)
   PY'
   ```

5. Health-check both layers:

   ```bash
   curl -fsS http://172.17.0.1:8645/health
   curl -fsS http://127.0.0.1:18080/health
   ```

6. Run the real Honcho LLM wrapper from inside the API container to prove the loaded Honcho settings route through Grok:

   ```python
   from src.config import settings
   from src.llm.api import honcho_llm_call
   resp = await honcho_llm_call(
       model_config=settings.DERIVER.MODEL_CONFIG,
       prompt="Deployment smoke test. Reply with exactly GROK_HONCHO_OK and nothing else.",
       max_tokens=20,
       temperature=0,
       retry_attempts=1,
   )
   assert resp.content.strip() == "GROK_HONCHO_OK"
   ```

7. Also smoke the structured-output path, because deriver/dreamer workloads may use `response_model`/parsed completions even when the plain chat wrapper works:

   ```python
   from pydantic import BaseModel
   from src.config import settings
   from src.llm.api import honcho_llm_call

   class Smoke(BaseModel):
       ok: bool
       value: str

   resp = await honcho_llm_call(
       model_config=settings.DERIVER.MODEL_CONFIG,
       prompt="Return JSON with ok=true and value=GROK_STRUCTURED_OK.",
       max_tokens=100,
       temperature=0,
       response_model=Smoke,
       retry_attempts=1,
   )
   assert resp.content.ok and resp.content.value == "GROK_STRUCTURED_OK"
   ```

## Quality gate for candidate Grok models
Before switching Honcho, run representative memory/profile prompts through `/v1/chat/completions`, not only arithmetic. Check at minimum:

- profile JSON/schema following;
- sensitive-data refusal (`remember=false`, `refuse_to_store=true` for secrets);
- contradiction update (keep new preference, discard stale one).

For one PD One rollout, `grok-4.20-0309-non-reasoning` passed those checks with sub-2s responses, while tiny local Qwen models failed schema/safety/contradiction checks.

## Pitfall: full dialectic endpoint is not a pure model smoke test
`/v3/workspaces/.../peers/.../chat` exercises the agentic dialectic path, including memory-search tools and broader session context. It can time out even when model routing is correct. Treat it as an end-to-end product test, not the first routing proof. Use the direct `honcho_llm_call` and structured-output wrapper smokes above to isolate provider/model config, then separately investigate dialectic/tool-loop latency if `/chat` stalls.

When `/chat` stalls after a Grok rollout, check the embedding layer and queue before blaming the Grok model:

```bash
curl -fsS http://127.0.0.1:18080/v3/workspaces/pd-neo/queue/status -o /tmp/honcho_queue_status.json
OLLAMA_HOST=http://172.17.0.1:11434 /home/prodesign/.hermes/services/ollama/bin/ollama ps
curl -fsS http://172.17.0.1:11434/api/tags >/dev/null && echo 'ollama tags ok'
docker logs --since 10m honcho-pd-neo-api-1 2>&1 | grep -Ei 'search_memory|search_messages|APITimeout|tool call' | tail -n 120
docker logs --since 10m honcho-pd-neo-deriver-1 2>&1 | grep -Ei 'RetryError|APIStatus|sync_vectors|Observation Count|Llm Call Duration|ERROR' | tail -n 120
```

Symptoms that point to embeddings/backlog rather than Grok include repeated `search_memory`/`search_messages` `APITimeoutError`, `bge-m3` stuck at 100% CPU, embedding requests taking minutes, or local Ollama memory-pressure messages. A green `/health` only proves the API is up; it does not prove the dialectic tools are fast enough for live chat.

## Backlog and re-analysis guidance
After switching Honcho generative paths to Grok, inspect the Honcho queue. Pending work units mean Honcho still has background representation/summary/dream work to process with the current model; they are not by themselves evidence that completed sessions need mass re-analysis.

Default stance:

- Let pending work drain under the new provider/model.
- Do **not** re-analyze completed session data solely because the provider changed.
- Re-analyze selectively only when evidence shows stale/bad conclusions, failed batches that did not retry, or a known-bad previous model produced unacceptable output.
- If the pending queue is large and embeddings are slow, fix embedding throughput or scheduling before judging `/chat` quality.

A typical backlog summary to report is `total_work_units`, `completed_work_units`, `in_progress_work_units`, `pending_work_units`, and count of sessions with pending/in-progress work; avoid dumping per-session IDs unless Andy asks.

## Embeddings are separate from Grok/xAI
Do not assume xAI/Grok can replace Honcho embeddings. In one live rollout, the xAI OAuth proxy's `/v1/models` only listed chat/image/video models, and probing `/v1/embeddings` with `grok-4.20-0309-non-reasoning` returned an `invalid-argument` error saying the model is a language model and must use chat completions.

Honcho's embedding path is separate from the Grok generative path:

- `src.embedding_client` supports `transport="openai"` for OpenAI-compatible `/v1/embeddings` providers.
- It also supports `transport="gemini"`, with `output_dimensionality=settings.EMBEDDING.VECTOR_DIMENSIONS`.
- The current pgvector dimension must match `EMBEDDING_VECTOR_DIMENSIONS`; Honcho validates this at startup and fails closed on mismatch.

Useful inspection commands:

```bash
docker exec -i honcho-pd-neo-api-1 sh -lc 'VIRTUAL_ENV=/app/.venv PATH=/app/.venv/bin:$PATH PYTHONPATH=/app python - <<"PY"
from src.config import settings
print(settings.EMBEDDING.model_dump())
print("send_dimensions", settings.EMBEDDING.resolve_send_dimensions())
PY'

docker exec -i honcho-pd-neo-database-1 psql -U honcho -d honcho -At <<'SQL'
SELECT 'documents_total', count(*) FROM documents;
SELECT 'documents_with_embedding', count(*) FROM documents WHERE embedding IS NOT NULL;
SELECT 'message_embeddings_total', count(*) FROM message_embeddings;
SELECT 'message_embeddings_with_embedding', count(*) FROM message_embeddings WHERE embedding IS NOT NULL;
SELECT table_name,column_name,atttypmod
FROM information_schema.columns c
JOIN pg_attribute a ON a.attname=c.column_name
WHERE data_type='USER-DEFINED' AND udt_name='vector'
ORDER BY table_name,column_name;
SQL
```

When Andy wants to avoid OpenRouter for embeddings, prefer these paths:

1. **Gemini embeddings** if a Google AI key is available. This is a good fit because Honcho has native Gemini embedding support and can request the existing vector dimension (for example 1024) without a DB dimension migration.
2. **Direct OpenAI embeddings** only with a real OpenAI key. Do not reuse an OpenRouter `sk-or-v1...` key against `https://api.openai.com/v1`; it will 401.
3. **Other OpenAI-compatible embedding APIs** only after a live `/v1/embeddings` smoke test with the exact provider/model and the configured vector dimension.
4. **Local Ollama** only if the host has enough RAM/CPU and a benchmark proves sub-second/low-second embedding calls under queue load; `bge-m3` can become the bottleneck and make `/chat` tool searches time out.

If changing embedding model/provider, do not mix embedding spaces silently. Even when the dimension stays the same, plan to re-embed existing `documents` and `message_embeddings` rows or otherwise invalidate/rebuild vector state; mixed vectors degrade search quality.

## Reporting
Report concise receipts only:

- proxy service enabled/active + health;
- loaded Honcho settings showing model/base URL;
- direct Honcho LLM smoke content/timing;
- final Honcho `/health`;
- backup path;
- if embeddings were investigated, current embedding transport/model/base URL class, vector dimension, row counts, and whether re-embedding is needed.

Do not paste OAuth tokens, full env dumps, or long logs.
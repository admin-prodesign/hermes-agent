# PD One Honcho Model Config / Timeout Triage

Use this when PD One/Hermes can reach Honcho but Honcho-backed profile/context or dialectic calls timeout, return empty context, or logs show LLM authentication/model errors.

## Durable lesson
A healthy Honcho API does not prove Honcho's LLM-powered paths are configured correctly. Basic endpoints such as `/health`, peer cards, and session context can be fast while deriver/dialectic/background LLM calls fail because Honcho silently falls back to built-in default model settings when the config file uses an outdated schema.

## Compose mount requirement (PD Neo deriver)

`[deriver.model_config]` in host `config.toml` is inert unless the deriver container mounts it at `/app/config.toml`. Without that bind mount, Honcho loads the image-baked TOML (or defaults) and falls through to `DeriverSettings` defaults (`openai` / `gpt-5.4-mini`) plus `LLM_OPENAI_API_KEY` against `api.openai.com` — which yields night-window 401s when the key is OpenRouter-shaped (`sk-or-v1-...`).

Durable compose shape for both `api` and `deriver`:

```yaml
volumes:
  - ./config.toml:/app/config.toml:ro
```

After editing compose, recreate only deriver (`docker compose -p honcho-pd-neo up -d --force-recreate --no-deps deriver`). Daytime parking (01:00–06:30 Asia/Taipei embedding window) will stop/start deriver; the mount must already be in compose so the next night start is correct.

## Failure signature
- Honcho API/container/database/redis are healthy and quick for non-LLM endpoints.
- Hermes gateway can reach Honcho, but dialectic/profile/context enrichment times out.
- Honcho API logs show OpenAI auth errors such as `openai.AuthenticationError: 401` or references to a default model like `openai/gpt-5.6-luna`.
- The configured key may be an OpenRouter-style key, but runtime model settings show `transport=openai`, default model, and no OpenRouter base URL.

## Current config-shape check
Current Honcho expects nested model config sections, not legacy flat provider/model keys.

Legacy keys that may be ignored by current Honcho:

```toml
PROVIDER = "vllm"
MODEL = "z-ai/glm-4.7-flash"
BACKUP_PROVIDER = "custom"
BACKUP_MODEL = "..."
```

Expected shape is nested model configs, for example:

```toml
[deriver.model_config]
transport = "openai"
model = "z-ai/glm-4.7-flash"
# include the current supported override fields for base URL/API-key env

[summary.model_config]
transport = "openai"
model = "z-ai/glm-4.7-flash"

[dialectic.levels.low.model_config]
transport = "openai"
model = "z-ai/glm-4.7-flash"

[dream.deduction_model_config]
transport = "openai"
model = "z-ai/glm-4.7-flash"

[dream.induction_model_config]
transport = "openai"
model = "z-ai/glm-4.7-flash"
```

For local Ollama-backed text generation, keep the same nested shape but point every text-generation `model_config.overrides` at Ollama's OpenAI-compatible endpoint:

```toml
[deriver.model_config]
transport = "openai"
model = "gemma4:e2b"
max_output_tokens = 2048

[deriver.model_config.overrides]
base_url = "http://host.docker.internal:11434/v1"
api_key = "ollama"

[dialectic.levels.minimal]
MAX_TOOL_ITERATIONS = 1
MAX_OUTPUT_TOKENS = 250
TOOL_CHOICE = "auto"

[dialectic.levels.minimal.model_config]
transport = "openai"
model = "gemma4:e2b"
max_output_tokens = 512

[dialectic.levels.minimal.model_config.overrides]
base_url = "http://host.docker.internal:11434/v1"
api_key = "ollama"
```

Repeat the same `model_config` + `overrides` pattern for `summary`, each enabled `dialectic.levels.*`, and `dream.deduction_model_config` / `dream.induction_model_config` if those should be local. Keep embeddings separate (`bge-m3` through `[embedding.model_config]`, vector dimensions usually 1024, `dimensions_mode = "never"` for Ollama-style embeddings).

For OpenRouter-backed use, the overrides must point at `https://openrouter.ai/api/v1` and an environment variable containing the OpenRouter key, rather than sending an OpenRouter key to the default OpenAI endpoint. Verify the exact supported override field names from the installed Honcho code/docs before editing.

## Local-model and OAuth decision notes
- Do not assume a provider slot named `vllm` means Honcho is using local vLLM. Verify the effective base URL from the container/process; it may point to OpenRouter or another remote OpenAI-compatible endpoint.
- A common split is local memory state + local embeddings, while generative Honcho paths still use a remote OpenAI-compatible endpoint. Check embeddings and chat/reasoning separately.
- Hermes OAuth providers such as `openai-codex` are not a drop-in Honcho backend. Honcho's current model config resolves static-style `api_key`, `api_key_env`, and `base_url` fields; it does not natively call Hermes OAuth token refresh or ChatGPT/Codex backend routes.
- Grok/xAI OAuth can still be used indirectly through the Hermes OAuth proxy if `xai-oauth` is authenticated. Use the installed Hermes console script/venv with an explicit PD One profile, not `python3 cli.py` from a checkout (system Python may lack dependencies such as `prompt_toolkit`, and `cli.py` can enter chat-mode parsing rather than subcommand routing):

  ```bash
  export HERMES_HOME=/home/prodesign/.hermes/profiles/pdone
  /home/prodesign/.hermes/runtime/current/.venv/bin/hermes auth status xai-oauth
  /home/prodesign/.hermes/runtime/current/.venv/bin/hermes proxy status
  ```

  If OAuth needs a fresh login, prefer `hermes auth logout xai-oauth` before `hermes auth add xai-oauth --type oauth --manual-paste`; `auth reset` only clears exhaustion/cooldown state and may leave a revoked refresh token. Do not paste OAuth tokens into Honcho config.

  Start the proxy bound where Honcho containers can reach it. For Docker-on-host Honcho, binding only to `127.0.0.1` proves the host path but may not be enough for containers; binding to the Docker bridge worked:

  ```bash
  /home/prodesign/.hermes/runtime/current/.venv/bin/hermes proxy start --provider xai --host 172.17.0.1 --port 8645
  ```

  Smoke-test `/health` and `/v1/chat/completions` from both the host and inside `honcho-pd-neo-api-1`, then point Honcho's OpenAI transport overrides at `http://host.docker.internal:8645/v1` or `http://172.17.0.1:8645/v1` with a dummy client API key. Verify `/v1/models`; do not assume model names from public examples. In one PD One check the working non-reasoning OAuth model was `grok-4.20-0309-non-reasoning`, while `grok-4.1-fast-non-reasoning` returned `Model not found`.
- For small no-GPU PD One/Hermes hosts around 8 GB RAM, treat local generation as experimental and prove it with representative Honcho prompts, not only arithmetic. Local `bge-m3` embedding traffic can keep Ollama busy for minutes and starve generation; temporarily pause Honcho API/deriver only with approval, clear embedding connections/runners, test, then restore and verify `/health`.
- Qwen thinking models may appear to return empty output unless calls include `think=false`; include that in direct Ollama smoke tests and check whether the target Honcho/OpenAI-compatible path can pass the option before considering the model viable.
- Do not rely on tiny local models for Honcho profile reasoning without quality checks. `qwen3.5:0.8b` was runnable with `think=false` but failed representative Honcho memory/profile tasks (schema following, contradiction handling, sensitive-store boundaries) and should only be used for trivial smoke tests. `qwen3.5:2b` could answer with `think=false` after a long cold load but used roughly 4 GB loaded and is too heavy to share with active `bge-m3` on this VM. Larger tags such as `gemma4:e2b` may be too large despite a successful pull; trust the runtime memory error and remove unusable pulls.
- If higher-quality synthesis is required, use a hybrid config: local embeddings plus an external/OpenAI-compatible model for generative Honcho paths, or local only after the exact model passes representative profile/safety/schema prompts. Make the privacy/quality tradeoff explicit before changing config.
- Do not restart Honcho immediately after editing config to a new model unless the model/path is already installed/authenticated and a local OpenAI-compatible smoke test passes. If a pull or proxy/auth setup is long-running, stage the config with a timestamped backup, leave current containers running, and only restart API+deriver after approval and verified readiness.

For a concrete Grok/xAI OAuth rollout checklist, persistent `systemd --user` proxy unit, known-good Honcho TOML snippets, and verification commands, also load `references/pd-one-honcho-grok-oauth-rollout.md`. Use that reference when the task is to actually switch Honcho to Grok rather than just diagnose model fallback.

## Triage steps
1. Check container/service health first, but do not stop there.
2. Probe one non-LLM Honcho endpoint and one LLM/dialectic/profile path separately so transport health is not confused with model health.
3. Inspect safe runtime config from inside the Honcho API container/process: provider/transport, model, base URL presence, and API-key environment variable name or redacted prefix only.
4. Compare the on-disk TOML shape with the installed Honcho settings classes. If runtime still shows defaults, the TOML keys are likely ignored.
5. Inspect recent Honcho API/deriver logs for default model names and auth errors.
6. Only after confirming schema mismatch, convert the TOML to the installed nested `model_config` shape. For local Ollama, use `transport = "openai"`, `model = "<ollama-tag>"`, `[...model_config.overrides] base_url = "http://host.docker.internal:11434/v1"`, and a dummy/static API key such as `api_key = "ollama"` if the client requires one.
7. Before restart, verify the target model exists in Ollama (`/api/tags`) and smoke-test the local OpenAI-compatible `/v1` endpoint. If the Ollama CLI cannot reach the service because it is bound on a Docker bridge/host-gateway address, set `OLLAMA_HOST=http://<reachable-host>:11434` rather than treating the CLI error as proof the service is down. For Qwen thinking models, include `think=false` in the direct Ollama test and verify the Honcho path can carry equivalent options.
8. For OAuth-backed Grok, verify the Hermes proxy separately before touching Honcho: check proxy dependencies/auth status, re-auth `xai-oauth` if refresh is revoked, start the proxy, host-smoke `/v1/chat/completions`, then container-smoke `http://host.docker.internal:8645/v1`.
9. For any candidate model/provider, run at least one representative Honcho memory/profile prompt that checks schema following, contradiction updates, and sensitive-data refusal. A model that answers `2+2` is not proven usable for Honcho.
10. Restart/rebuild only the Honcho API and deriver containers after approval and after the target model/path is installed/authenticated and smoke-tested. Re-test the same LLM path and confirm logs no longer mention the default model or invalid-key errors.

## Reporting pattern
Keep chat-facing output short and explicit:
- "Honcho is reachable" vs. "Honcho LLM paths are broken".
- The exact fallback/default model observed.
- The config-shape mismatch.
- Whether any restart or config edit is still pending approval.

Do not paste secrets, full env dumps, or long logs into chat.
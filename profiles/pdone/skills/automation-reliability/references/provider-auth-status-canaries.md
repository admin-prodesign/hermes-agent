# Provider auth and inference status canaries

Use this reference when a status monitor says an agent is online but the real failure is upstream model-provider authentication or generation.

## Why this exists

A process/service check plus messaging-platform API check only proves the bot can appear alive. It does not prove the agent can authenticate with its active model provider or complete an inference call. For OAuth-backed providers such as OpenAI Codex/ChatGPT-account auth, this can leave Mattermost/Discord status showing online while replies fail.

## Low-token check pattern

Add a provider-health dimension before marking the agent fully online:

1. Read the active provider/auth profile for the runtime being monitored.
2. For OAuth/JWT-style providers, decode token expiry locally where possible. Missing or expired token is a health failure.
3. Call a cheap provider metadata endpoint that does not generate model output, for example Codex model catalog:
   `GET https://chatgpt.com/backend-api/codex/models?client_version=1.0.0`
4. Use the same provider-specific headers as production calls. For Codex OAuth, include the Codex/Cloudflare-compatible headers used by Hermes real requests, not a generic HTTP client fingerprint.
5. Treat 401/403, Cloudflare challenge, DNS/TLS/connectivity failure, or unexpected non-2xx as degraded/offline evidence.
6. Log only redacted status, HTTP code, and summarized error class; never log access tokens or raw auth payloads.

This catches most provider-auth and provider-reachability incidents with zero LLM tokens.

## Tiny inference canary pattern

Metadata endpoints do not prove generation works. Add a real inference canary, but throttle it:

- Run every 15–60 minutes depending on risk/cost tolerance; 15 minutes is still cheap when the prompt is minimal and the result is cached between 5-minute monitor ticks.
- Prefer the exact runtime/profile being monitored. If the user explicitly wants a utility-agent/low-cost profile, call that provider/model profile directly; do **not** spawn a full utility-agent conversation just to check generation, because the agent wrapper injects large system/workspace context.
- Prompt: a minimal `.` / `ping` / `OK` style prompt.
- Cap output to one or a few tokens when the backend supports it. Note: the ChatGPT Codex backend used by Hermes has rejected `max_output_tokens` on some paths, so a Codex canary may need to omit the cap and rely on minimal input, no tools, `store=false`, disabled/minimal reasoning where accepted, and a short timeout.
- Match the backend's required transport shape. For Codex/Hermes incidents, verify whether production uses streaming; a non-streaming direct SDK canary that fails with `Stream must be set to true` is a probe-shape bug, not proof that Hermes cannot answer.
- For OpenAI Codex/ChatGPT-account canaries, prefer the same streaming shape as production: `responses.stream(...)`, with fallback to `responses.create(stream=True)` if the SDK/runtime exposes that path instead. Keep `store=false`, no tools, minimal reasoning where accepted, a one-token-style prompt, and a short timeout. Do not restrict the fallback to only one exception class: SDK stream helpers can fail with probe-shape errors such as `TypeError: 'NoneType' object is not iterable`; catch narrow known stream-helper failures (for example `RuntimeError` and this `TypeError`) and retry the streaming-create path before marking the canary failed.
- Cache `last_inference_canary_ok`, timestamp, model/profile, auth source, and summarized failure in monitor state.
- Normal frequent checks should reuse the cached canary result rather than generating every run.
- Run the monitor with the same Python environment as the agent when it imports provider helpers (`httpx`, `openai`, Hermes auth utilities). A system `/usr/bin/python3` wrapper can falsely report provider/auth failures just because the agent venv dependencies are unavailable.

## Coverage decision tree

When asked whether an existing canary covers an incident, answer by layer instead of by yes/no intuition:

1. **Credential/auth failure** (missing/expired OAuth token, consumed refresh token, `resolve_codex_runtime_credentials` failure): provider-auth and tiny direct inference canaries should catch it.
2. **Provider metadata/reachability failure** (model catalog, 401/403, Cloudflare/TLS/DNS): metadata canary should catch it with zero LLM tokens.
3. **Direct inference shape failure** (wrong endpoint parameters, non-streaming vs streaming mismatch): fix the canary to mirror the production provider call shape before trusting the result.
4. **Hermes provider routing/streaming failure** (credentials resolve and direct SDK call works, but Hermes request path times out or parses streams incorrectly): requires a Hermes-path canary. Build this as a low-frequency direct `AIAgent`/provider-path probe using the same provider profile as production, no tools, skipped memory/context files where the framework permits it, a `Reply exactly OK` prompt, and a bounded timeout (for example 45 seconds). This catches failures between provider SDK success and actual Hermes routing without paying the full gateway/tool prompt cost. Verify persisted monitor state after implementation: the current status may remain offline if another stricter check is still failing, even when the Hermes-path canary itself is passing.
5. **Full bot path failure** (Mattermost/Discord gateway receives messages but agent orchestration/tool/session startup fails): requires a lowest-frequency end-to-end gateway→agent canary or synthetic message loop.

Use layered cadence to control token cost: frequent process/messaging checks, less frequent provider-auth/metadata checks, cached tiny inference checks, and lowest-frequency true Hermes-path checks.

## Status mapping

For user-visible status posts or avatar/profile indicators:

- `online`: gateway/process, messaging API, provider auth/metadata, and recent canary are OK.
- `degraded`: any provider-auth/metadata/canary check fails once or is stale, while the bot can still update status.
- `offline`: repeated consecutive failures cross the monitor threshold, e.g. 3 failed runs.

Keep existing anti-flap counters. Provider checks should add signal, not create noisy one-off alerts.

When checks are layered, map severity by the strongest end-to-end evidence, not by a flat "any bad check = offline" rule. If provider metadata/auth is OK and the Hermes-path `AIAgent` canary succeeds, but a lower-level direct SDK canary fails, treat that as `degraded` and investigate the direct canary for a probe false negative rather than declaring the agent offline. Direct SDK probes are useful diagnostics, but the Hermes-path canary is closer to real answerability.

## Display fields

Include concise bilingual/user-facing checks when the status surface is employee-visible:

- Gateway service active
- Messaging platform API OK
- Active provider OAuth/token valid
- Provider model catalog or metadata reachable
- Last tiny inference canary OK timestamp

Prefer the pinned/editable status post as source of truth; native presence dots only prove messaging session activity and can be misleading about model-provider health.

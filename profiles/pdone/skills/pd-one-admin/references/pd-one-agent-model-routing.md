# PD One agent model routing and OpenClaw runtime mapping

Use this reference when changing PD One/OpenClaw agent model assignments in `~/.openclaw/openclaw.json`.

## Durable lesson

For PD One agents that should use the global default model, prefer removing the per-agent `model.primary` override rather than copying the current default model into every agent. This keeps future default-model changes centralized under `agents.defaults.model.primary`.

However, do **not** blindly remove per-agent `models` runtime maps when the runtime mapping is required for auth. On this installation, `openai/gpt-*` agent runs use the OpenAI Codex runtime (`agentRuntime.id: codex`) and OpenAI Codex OAuth. If a hot reload sees an inherited `openai/gpt-*` model with no Codex runtime mapping, queued/background runs can route as direct OpenAI API calls and fail with auth errors such as:

```text
No API key found for provider "openai". You are authenticated with OpenAI Codex OAuth; OpenAI agent model runs use openai/gpt-* through the Codex runtime.
```

## Safe edit pattern

1. Inspect `agents.defaults.model.primary` first; this is the model all non-overridden agents should inherit.
2. For every non-specialized agent:
   - remove the per-agent `model` block when the intent is “use default model”; and
   - preserve or add the `models` entry that maps the inherited default model to the expected runtime, e.g. `openai/gpt-5.5 -> agentRuntime.id: codex`.
3. For `utility-agent`:
   - keep an explicit `model.primary` override, currently `openai/gpt-5.6-luna`;
   - keep only the runtime map for that mini model unless the user explicitly asks for fallbacks; and
   - remove stale fallbacks if the requirement is “set to mini,” not “try mini then another model.”
4. Validate and verify after the edit:
   - `openclaw config validate`
   - `openclaw agents list` and confirm each agent’s displayed model
   - check gateway logs for config hot reload and for new provider/auth errors
   - `openclaw status` should show the gateway reachable after reload
5. Commit/push the OpenClaw backup repo when configured.

## Heartbeat strictness

PD One heartbeat runs may intentionally use a heartbeat-specific model override such as `openai/gpt-5.6-luna`. If the runtime has resolved a heartbeat model override, do not allow normal model fallbacks for that heartbeat run; otherwise a heartbeat auth/model issue can silently route onto the default/primary model and mask the exact heartbeat failure. Verify the installed package/runtime has loaded the strict behavior after a source patch by checking syntax, restarting the gateway when the running process predates the installed JS patch, and confirming gateway health/logs directly if `openclaw status` hangs.

## Pitfall

A JSON-level diff that removes all per-agent model-related blocks may look correct because `openclaw agents list` still displays the inherited default model, but queued agent runs may fail after hot reload if runtime auth mapping was also removed. Treat “model selection” and “runtime/auth mapping” as separate concerns.
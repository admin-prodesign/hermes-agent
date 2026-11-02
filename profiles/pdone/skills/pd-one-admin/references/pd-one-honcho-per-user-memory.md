# PD One Honcho Per-User Memory/Profile Injection

Use this when implementing or reviewing Honcho-backed per-user memory/profile support for PD One/Hermes.

## Durable lesson
Per-user memory is useful only when identity scoping is stronger than display names. For PD One, Honcho profile/context injection should be keyed from trusted runtime platform metadata and exact stable sender/user IDs, while authorization remains entirely outside Honcho.

## Recommended design
- Keep Mattermost permission decisions in the PD One Hermes permission bridge / policy cache, resolved by exact Mattermost sender ID. Honcho memory must never grant permissions or expand data scope.
- Pass gateway/runtime `platform` into Honcho memory session initialization along with runtime `user_id` / aliases.
- Resolve explicit aliases in this order:
  1. `platform:user_id`
  2. legacy raw `user_id`
- Preserve backwards compatibility with a default legacy mode for deployments that already rely on raw runtime IDs.
- Add an explicit `runtimePeerScope` config option instead of changing defaults globally:
  - `legacy`: existing raw runtime ID behavior.
  - `platform` / `platform-scoped`: generated peer IDs include a sanitized platform prefix.
  - `platform-hash`: generated peer IDs include a sanitized platform prefix plus a short SHA-256 digest of `platform:user_id`, avoiding raw platform ID exposure.
- Allow existing explicit `runtime_peer_prefix` behavior to keep precedence for compatibility.
- Use `recallMode: hybrid` when the goal is both automatic profile/context injection and explicit Honcho memory tools.
- Host-specific Honcho knobs such as `injectionFrequency`, `contextCadence`, and `dialecticCadence` should be read from the active host block first, with root-level config as fallback.

## Honcho runtime-health pitfall
If profile/context injection works only partially, separate Honcho transport health from Honcho LLM health. `/health`, peer cards, and session context can be fast while dialectic/deriver calls fail because current Honcho ignored legacy flat `PROVIDER`/`MODEL` TOML keys and fell back to default OpenAI model settings. For this failure class, load `references/pd-one-honcho-model-config-triage.md` before editing config or restarting containers.

## Verification pattern
1. Unit-test config parsing for `runtimePeerScope` default and configured values.
2. Unit-test alias order: `platform:id` beats raw `id`.
3. Unit-test platform-scoped and platform-hashed generated peer IDs.
4. Smoke-test active profile config loading for the intended Hermes host key.
5. Smoke-test a known runtime user/platform and verify the generated peer ID is platform-scoped and, if using `platform-hash`, does not contain the raw sender ID.
6. Confirm no sensitive endpoint/secret values are printed in summaries; report only that they are set.
7. Commit/push source changes and run the Hermes backup script when durable runtime config under `~/.hermes` changes.
8. Do not restart Hermes/PD One/gateways without Andy/admin approval unless the approved unresponsive-gateway exception applies.

## Chat-facing report pattern
Keep the final report short: implemented behavior, security boundary, test receipts, source/backup commit IDs, and whether a restart/reload is still needed. Avoid dumping full diffs or secrets into chat.
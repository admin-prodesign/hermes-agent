# PD One Hermes control-plane cleanup and legacy OpenClaw reference handling

Use this when Andy/admin asks whether OpenClaw is still active, complains that OpenClaw should not be involved, or requests cleanup of old OpenClaw policy/runtime/control-plane references after PD One migration to Hermes.

## Core rule

PD One's authoritative runtime/policy/control-plane source is the Hermes `pdone` profile:

- `/home/prodesign/.hermes/profiles/pdone`

OpenClaw paths may remain as historical migration references, archived receipts, compatibility notes, or source-level implementation history, but they must not be described as the active PD One control plane unless live evidence proves a still-running legacy component and Andy has explicitly asked to inspect/repair it.

## Cleanup pattern

1. Separate **active policy/runtime** files from **historical references/archives** before editing.
2. In active PD One policy/cache/config wording, replace OpenClaw-scoped names with Hermes/PD One names. Example from the cleanup session:
   - `openclaw-health-readonly` → `pd-one-host-health-readonly`
   - `openclawStatus` → `pdOneHostStatus`
3. Regenerate any derived policy/cache artifacts after schema/key renames.
4. Remove or archive stale user systemd units only after proving they are dead/not-found/inactive and not listening on legacy ports.
5. Kill stale legacy child processes only when they are clearly old/orphaned and unrelated to current Hermes PD One gateway work.
6. Keep historical skill references and migration receipts if they are still useful, but label them as legacy/compatibility and avoid letting their wording leak into active reports.

## Verification receipts to collect

- Active PD One policy files have no OpenClaw control-plane references.
- Generated Mattermost/employee policy caches have no OpenClaw references.
- Mattermost policy lookup still works for Andy/admin exact sender id.
- No legacy OpenClaw gateway process/listener remains, especially on the old gateway port if known.
- No OpenClaw user systemd unit files remain active; archived unit files have a clear path if retained.
- Hermes PD One gateway remains running.
- JSON/YAML validation passes after policy/cache edits.
- Durable changes are committed/pushed to the configured Hermes/PD One backup repo when available.

## Reporting pitfall

Do not say "OpenClaw backup", "OpenClaw runtime", or "OpenClaw control plane" in a way that implies current authority. If a path/name is legacy, say so explicitly: "legacy OpenClaw migration/archive/reference path". Andy treats OpenClaw-as-active wording as a substantive correctness issue, not a cosmetic naming issue.

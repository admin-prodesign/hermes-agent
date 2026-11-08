# PD One agent/channel audit notes

Use this reference when asked why a PD One/OpenClaw agent exists, what channel it is bound to, or whether a legacy agent can be removed.

## Bounded audit pattern

1. Load the live OpenClaw config from `~/.openclaw/openclaw.json` without printing secrets.
2. Inspect `agents.list` for the agent object. A minimal object such as `{ "id": "openclaw" }` means it inherits defaults and has no dedicated workspace/agentDir/model in config.
3. Inspect top-level `bindings[]` for `agentId == <agent>`; this is the live channel binding source of truth.
4. Search session state under `~/.openclaw/agents/<agent>/sessions/sessions.json` for historical use. Convert millisecond timestamps to UTC before drawing conclusions.
5. Search gateway logs for recent `agent:<id>` / `agentId=<id>` patterns when deciding whether usage is current.
6. Check historical config backups/git history only to explain origin, not as evidence of current routing.

## PD One `main` / compatibility-agent cleanup finding from 2026-05

The `main` agent in PD One can be a legacy compatibility/default-ish channel shim rather than a distinct production persona. In the observed cleanup, `main` had only `id` + `name`, no workspace/tool profile/model/runtime config, and exactly one Mattermost channel binding for IT channel `jp47xmyu8prytmqrhimaw9hy7e`. Since `employee-assistant` already had the broad Mattermost default binding and a safer minimal scoped tool profile, the IT channel was explicitly rebound to `employee-assistant` and `main` was removed.

Safe cleanup pattern for this class of agent:
- Confirm the agent object is minimal or otherwise redundant; do not infer from name alone.
- Confirm all live `bindings[]` references and decide the replacement agent per channel purpose.
- Edit both `agents.list` and affected `bindings[]` in the same validated write when possible.
- Validate JSON and `openclaw config validate --json` before relying on the change.
- Let the gateway config watcher hot-reload routine binding/agent-list edits; do not restart for convenience if health is still reachable.
- Verify from both config assertions and runtime state: no removed agent in `agents.list`, no binding references the removed agent, the target channel resolves to the intended agent, `openclaw agents list --json` excludes the removed agent, and direct gateway health is OK.
- If `openclaw health --json` times out during event-loop pressure, corroborate with `openclaw gateway call health --json`, systemd state, and recent journal reload lines before considering restart.
- Commit/push only the scoped config file change when the backup repo has other unrelated dirty state.

Evidence from the successful cleanup:
- Removed `main` from `agents.list`.
- Rebound Mattermost IT channel `jp47xmyu8prytmqrhimaw9hy7e` from `main` to `employee-assistant`.
- Hot reload logged `config change detected; evaluating reload (agents.list, bindings)` followed by `config hot reload applied (agents.list)`.
- Runtime agents list no longer included `main`; direct gateway health was OK; no restart was required.

## PD One `openclaw` agent finding from 2026-05

The `openclaw` agent in PD One was a legacy/generic OpenClaw self/ACP agent, not a current production department/channel agent.

Evidence pattern:
- Current config entry was only `{ "id": "openclaw" }` in `agents.list`.
- Current `bindings[]` contained no `agentId: "openclaw"` entries; live Mattermost/Discord routing used role agents such as `admin`, `main`, `finance`, `hr`, `employee-assistant`, etc.
- Historical state existed in `~/.openclaw/agents/openclaw/sessions/sessions.json`, including:
  - a Mattermost Testing channel session for `shrapa36ifbrtpfcrb1sayjh6o`, documented as the Testing channel, last updated 2026-04-27 UTC;
  - an Andy Mattermost DM ACP/Pi runtime session last updated 2026-05-06 UTC;
  - failed ACP sessions spawned from an early Discord channel/thread around 2026-04-25.
- The agent appeared in the first sanitized committed config (`e50eaae`, 2026-04-25) when the initial agents were just `main` and `openclaw`.

Conclusion for future audits: no production channel was bound to `openclaw` at that time; treat it as legacy/compatibility state unless fresh `bindings[]`, sessions, or gateway logs show new use.

## PD One `main` agent / IT channel finding from 2026-05

The `main` agent in PD One was a minimal compatibility/general-purpose agent and may be removable when its only live route is superseded by a scoped role agent.

Evidence pattern from the 2026-05 cleanup discussion:
- Current config entry was only `id: "main"` plus name `PD One Core Compatibility`; it had no dedicated workspace, tool profile, elevated access, subagent policy, or explicit model/runtime config.
- Its only live binding was the Mattermost IT coordination channel `jp47xmyu8prytmqrhimaw9hy7e`.
- `employee-assistant` already had a broad Mattermost default binding and a safer employee-facing configuration: dedicated employee workspace, minimal scoped tool profile, disabled memory search, and only approved scoped tools plus `utility-agent` delegation.

Recommended future cleanup when this pattern recurs:
1. Confirm `main` has no additional live `bindings[]`, recent required sessions, or special config fields.
2. If the target channel should behave like normal employee-facing/internal support, replace the specific `main` binding with `agentId: "employee-assistant"` and remove `main` from `agents.list`.
3. Do **not** route an IT/admin/operator channel to `employee-assistant` if it needs full tools or Andy-only elevated access; use `admin` or create a dedicated scoped IT/admin agent instead.
4. Validate config, hot reload, verify health, verify no binding references the removed agent, verify routing resolves to the intended agent, then commit/push the backup repo.

## Removal caution

Do not remove legacy generic agents blindly. First decide whether explicit OpenClaw ACP/Pi harness sessions, old session continuity, or channel-specific authority still matter. If removing, back up config, validate, hot-reload/restart through the PD One gateway restart rules, verify no new routing/auth errors, and commit/push durable backup changes.
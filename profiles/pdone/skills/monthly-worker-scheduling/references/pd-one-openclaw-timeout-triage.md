# PD One / OpenClaw timeout triage for worker-scheduling playbook threads

Use this reference when Andy asks whether PD One needs a timeout increase while running the monthly worker scheduling playbook from a Mattermost thread.

## Pattern observed

A worker-scheduling kickoff thread can produce user-facing copy like:

- `Request timed out before a response was generated. Please try again, or increase agents.defaults.timeoutSeconds in your config.`
- Tool failure banners such as `Codex Apps.google Drive Get Spreadsheet Metadata failed` or a failed shell/process check.

Do not accept the user-facing timeout hint at face value. It is generic.

## Diagnostic steps

1. Read/fetch the Mattermost thread and note:
   - user request timestamp
   - bot failure timestamp
   - exact failure text
   - whether the retry failed at a different phase
2. Inspect OpenClaw config for:
   - `agents.defaults.timeoutSeconds`
   - `plugins.entries.codex.config.appServer.turnCompletionIdleTimeoutMs`
   - runtime/plugin settings for Codex and any translation/review plugins involved in the response path
3. Check gateway/systemd logs around the exact timestamps.
4. Classify the failure:
   - `codex app-server turn idle timed out waiting for completion` => Codex app-server completion idle timeout, not the global agent budget.
   - `plugin.approval.waitDecision` around ~120s => approval decision wait, not global timeout.
   - command/tool timeouts such as shell `exit_code 124` => tool-specific timeout.
   - Google Drive / Sheets metadata failure => source/API/tool failure; retry and verify source access before changing runtime budgets.

## Fix preference

Prefer the narrowest knob:

- Codex app-server idle: set/increase `plugins.entries.codex.config.appServer.turnCompletionIdleTimeoutMs` to a targeted value such as 180000–300000 ms.
- Approval waits: retry with smaller read-only steps and avoid approval-gated shell/process checks unless necessary; approve promptly if a command is truly needed.
- Tool-specific timeout: adjust that tool call/script timeout or split the task.
- Global agent timeout: change `agents.defaults.timeoutSeconds` only when logs prove the whole agent run budget is the limiting factor.

## Worker-scheduling-specific handling

When retrying the playbook:

- Load/follow `monthly-worker-scheduling`.
- Start with Mattermost Playbooks and Worker Scheduling Sheets metadata/content checks.
- Keep source-first behavior: `原資料` and `申請日期-當月統計` before downstream schedule views.
- Avoid unnecessary process checks (`ps`, `rg`, `gog`) in the Mattermost thread unless there is evidence of a stuck scheduler process.

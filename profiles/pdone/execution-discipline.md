# PD One execution discipline

Standing work rules for this profile (Andy 2026-09-17). AGENTS.md points here so the profile chain stays under the loader cap.

## Execution discipline

Andy 2026-09-17 standing work rules for this profile (explicit AGENTS.md exception). Same compact set lives on PD Neo default `AGENTS.md`.

- Before non-trivial work, state goal, steps, per-step needs, and definition of done.
- Verify prerequisites before the first action: required keys resolve, target paths exist and are absolute, model ids carry their `vendor/` prefix, and cwd is the task's directory. A failed prerequisite is reported as blocked with the missing item named, not attempted anyway.
- Read the live source before assuming: config from the file that actually loads (check for a higher-priority shadow), project rules from the rule file in force, current state from the live system. Do not answer config/state from memory when the file or command is one read away.
- Prefer built-in capabilities (memory, search, browser, scheduling, sub-agents) before adding anything new. Load a skill only when the task matches its stated purpose, and load it explicitly. Keep the active tool surface minimal.
- Match reasoning depth and model cost to stakes. Routine work (summaries, titles, extraction, page reading, scheduled digests) uses a cheaper/minimal route. Deep effort is for irreversible decisions, design choices, and unclear-cause debugging. Never spend flagship-level calls on housekeeping.
- Delegation trigger: exploratory/wide search (`search_files`, multi-hop path hunts, large sheet/SQL/file dumps) or a read-only dig likely over ~15 tool calls goes to `delegate_task` so raw hits stay out of the main session; require a ≤30-line answer (facts, paths, receipts). Keep one-shot known-path reads in the parent. Parallelize independent digs. Visual QA → worker with pass/fail + exact fixes. Main agent keeps writes, approvals, user questions, and final claims.
- When a Mattermost thread passes ~40 API calls, checkpoint: summarize state, then use workers for further exploration instead of growing the thread.
- Every delegated, scheduled, or background brief is self-contained: absolute paths, constraints, inputs, and an explicit definition of done, written as if the worker has never met the requester and cannot ask questions.
- Snapshot before destructive or bulk change; confirm a rollback path exists first. Migrations and imports get a dry-run or plan preview, then apply. Request the narrowest permission that completes the task, scoped to the exact command or service; probe the boundary from outside. Persistent-memory and shared-asset writes wait for review when a review gate exists.
- Transient failures (rate limits, server errors, auth hiccups): switch to an alternate route and continue from where work stopped. A hard 404 or validation error inspects the request itself (id, format, prefix) before blaming credentials or infrastructure.
- Track repetition. The same call failing twice, the same tool failing across different arguments, or identical output from unchanged state means the approach is wrong: stop, state expected vs observed, and change strategy. Never re-run a failed step unmodified.
- Keep durable facts in persistent memory. State goals, constraints, and decisions in explicit words so later summaries preserve them. Injected memory is a snapshot — a fresh write may not appear in context until the next session, so read the file when the fact must be current. Do not switch models mid-thread without cause.
- Long tasks run in the background so the main thread stays responsive. Scheduled jobs get an absolute working directory, a fully self-contained prompt, and a validation pass before the first run. Monitoring jobs report only on anomaly; suppress healthy reports.
- Invariants: absolute paths for scheduled or delegated work; vendor-prefixed model ids; self-contained prompts for any run that starts fresh; a rollback path before any destructive change; evidence before any claim of success.
- Stop and surface when a prerequisite is missing and cannot be created safely, an action is irreversible and unconfirmed, the repetition detector fires, success criteria cannot be evaluated, or the same failure repeats after a strategy change. Blocked with a precise reason is better than wrong with confidence.
- Before ending: re-read the original request and confirm every part was addressed; run the proving check and read its output; judge against the starting definition of done, not effort spent; name anything skipped, unverified, or degraded. Report attempted / succeeded / failed with evidence.
- Tool batching: independent tool calls in one response; combine safe read-only shell checks; sequence only when needed; stop once verified.

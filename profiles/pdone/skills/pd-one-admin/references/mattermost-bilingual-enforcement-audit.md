# Mattermost bilingual enforcement audit

Use this reference when PD One/OpenClaw stops replying bilingually in Mattermost channels or when auditing prompt-policy enforcement for channel agents.

## Source-of-truth policy locations

- `/home/prodesign/.hermes/profiles/pdone/policies/mattermost-channels.md` — canonical channel policy. The language rule section requires Mattermost channels/groups to always reply with equivalent English + Traditional Chinese, ordered by requester preference; DMs are the normal exception. Named channel `reply_language` exceptions override this; machine-readable copy is `policies/mattermost-channel-language.json`. PD One Admin `5gmqtwqf7bde3cyihas79xi8ie` is English-only while Andy is the sole current user.
- `/home/prodesign/.openclaw/workspace/AGENTS.md` — main/admin workspace hard pre-send check may duplicate the rule.
- `/home/prodesign/.openclaw/workspace/MEMORY.md` and wiki syntheses may contain the original historical policy note, but treat them as provenance, not the runtime source.

## Runtime enforcement model

OpenClaw currently enforces this mostly through prompt/bootstrap instructions, not a deterministic post-send bilingual gate. Therefore, check what the routed agent actually receives at startup, not only whether the policy exists in the admin workspace.

## Audit sequence

1. **Find the active route.** Inspect `/home/prodesign/.openclaw/openclaw.json` `bindings[]` and Mattermost `groups{}` to determine which agent handles the channel. Department channels often route to specialized workspaces such as `finance`, `senior-staff`, `facilities`, `product-quality`, `hr`, etc.; fallback Mattermost traffic may route to `employee-assistant`.
2. **Inspect the routed workspace bootstrap.** Read that agent workspace's `AGENTS.md` and any injected files (`SOUL.md`, `TOOLS.md`, `IDENTITY.md`, `USER.md`, `HEARTBEAT.md`, optional `BOOTSTRAP.md`). A pointer like “read Mattermost policy when detail is needed” is weaker than an always-on hard pre-send rule.
3. **Check session prompt reports.** In `/home/prodesign/.openclaw/agents/<agent>/sessions/sessions.json`, inspect recent Mattermost group/channel session entries:
   - `systemPromptReport.workspaceDir`
   - `systemPromptReport.injectedWorkspaceFiles[]`
   - `bootstrapMaxChars`, `bootstrapTotalMaxChars`, and `bootstrapTruncation`
   - whether the report indicates the relevant file is missing or truncated
4. **Check visible outputs, not only reasoning.** Session JSONL files store messages under `sessionFile`. Visible final text is usually assistant content parts of type `text`; do not count Chinese in source titles or tool output as proof of bilingual compliance.
5. **Use git history for regressions.** `git -C /home/prodesign/.openclaw log --oneline -- <workspace>/AGENTS.md workspace/docs/agent-rules/channel-agent-common.md workspace/policies/mattermost-channels.md` often reveals prompt slimming or pointer-file changes that moved hard rules out of always-injected context.

## Common root cause

A common regression is replacing direct agent-bootstrap rules with pointer-only references. Example failure mode: specialized channel `AGENTS.md` says to read `mattermost-channels.md` “when a request needs detail,” so routine channel answers never load the canonical policy and become monolingual. `employee-assistant` may still comply if its own `AGENTS.md` directly contains “Mattermost group/channel replies are bilingual…”.

## Safe remediation options

- **Lowest-risk durable prompt fix / Option A:** add a short hard pre-send bilingual line directly to every Mattermost channel agent `AGENTS.md` (or a small injected `BOOTSTRAP.md` if that is part of the runtime bootstrap) so the rule is always in prompt context. Patch all channel-bound specialized agents discovered from `openclaw.json`, not just the one that visibly failed.
- **Prevention guard:** after adding or changing Mattermost channel-specific bindings, run `/home/prodesign/.openclaw/workspace/tools/mattermost_channel_agent_guard.py`. It reads `openclaw.json`, finds Mattermost channel-bound specialized agents, and fails if the routed workspace `AGENTS.md` lacks the hard bilingual phrase. If the guard script is missing, recreate it as a deterministic checker for the required phrase in every channel-bound agent workspace.
- **Existing sessions caveat:** new files or edited bootstrap files may not affect already-open sessions/threads until a new session, compaction, or gateway reload. Do not restart the PD One gateway without explicit Andy approval.
- **Stronger later fix:** implement a deterministic Mattermost visible-reply QA gate that warns, blocks, or rewrites channel/group responses missing English or Traditional Chinese. Treat this as plan-first code/config work with smoke tests.

## Minimal hard pre-send wording

```md
Hard pre-send check: If the inbound surface is Mattermost and the chat is a channel/group, the final visible reply must be bilingual English + Traditional Chinese with equivalent substance, ordered by requester preference when known. Mattermost DMs are the only normal exception. This rule does not apply to Discord.
```

## Verification checklist

- [ ] The routed agent workspace, not just admin workspace, has the hard rule in injected startup context.
- [ ] Recent session prompt report shows the file containing the hard rule is injected and not truncated.
- [ ] A new Mattermost channel/group test reply contains both English and Traditional Chinese with equivalent substance.
- [ ] No gateway restart was performed unless Andy explicitly approved it.

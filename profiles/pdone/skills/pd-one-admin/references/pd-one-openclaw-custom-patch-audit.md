# PD One/OpenClaw Custom Patch Audit

Use when Andy asks whether PD One/OpenClaw custom patches are installed, active, or still working after concurrent runtime changes or an upstream update.

## Goal
Report three separate facts clearly:

1. **Source patch stack** — what commits/files differ from the upstream release/tag.
2. **Installed runtime activation** — whether the live OpenClaw process is using a package/build that contains those patches.
3. **Verification status** — health checks and targeted tests, with any caveats separated from confirmed facts.

## Recommended sequence

1. Identify the live OpenClaw process without restarting it:
   - Look for the `openclaw ... gateway --port ...` node process.
   - Record PID, start time, command, and current working directory if useful.
   - Check the local gateway health endpoint when known, for example `http://127.0.0.1:18789/health`.

2. Inspect the maintained source checkout, usually `/home/prodesign/openclaw`:
   - `git status --short --branch`
   - `git branch --show-current`
   - `git log --oneline --decorate --max-count=40`
   - Compare against the upstream release/tag, e.g. `git log --oneline --no-merges vYYYY.M.DD..HEAD` and `git diff --stat vYYYY.M.DD...HEAD`.

3. Summarize custom commits by capability, not only by hash:
   - Preserve the commit hash and subject.
   - Name the user-visible/runtime behavior each patch enables.
   - Mention affected files only when helpful for auditability.

4. Confirm installed runtime artifacts separately from source:
   - `openclaw --version` may still show the upstream release hash/version even when downstream custom dist artifacts are installed; do not treat the version string alone as proof that patches are absent.
   - Check the installed package root used by the live command, commonly `/home/prodesign/.npm-global/lib/node_modules/openclaw`.
   - Look for expected built outputs under `dist/` or deployed workspace plugin files under `.openclaw/workspace/plugins/<plugin-id>/`.

5. Run bounded verification only:
   - Health endpoint / lightweight CLI status first.
   - Narrow tests for touched surfaces if local deps are healthy.
   - Avoid broad `openclaw status`, huge log pulls, or full dependency reconciliation from live chat unless debugging an active incident and using the admin-heavy lock/runbook.
   - Prefer existing repo wrappers exactly as documented. For Vitest in this checkout, `node scripts/run-vitest.mjs <files...>` is the safe narrow path; do not add `--reporter=basic` because this Vitest version treats `basic` as a custom reporter module and fails at startup.
   - For runtime-patch audits, include both source tests and installed-artifact signature checks. A source test passing after a fix does not prove the already-installed global runtime has been rebuilt or restarted.

## Targeted regression suites seen useful

Use the current file list as a starting point, not a mandatory exhaustive suite:

```bash
# Personal employee memory deterministic surfaces
node scripts/run-vitest.mjs \
  extensions/personal-memory/src/config.test.ts \
  extensions/personal-memory/src/identity.test.ts \
  extensions/personal-memory/src/filter.test.ts \
  extensions/personal-memory/src/context.test.ts \
  extensions/personal-memory/src/store.test.ts

# Mattermost send/monitor + trusted inbound metadata/tool-context surfaces
node scripts/run-vitest.mjs \
  extensions/mattermost/src/mattermost/send.test.ts \
  extensions/mattermost/src/mattermost/monitor.test.ts \
  extensions/mattermost/src/mattermost/monitor-resources.test.ts \
  src/agents/openclaw-tools.plugin-context.test.ts \
  src/auto-reply/reply/agent-runner-utils.test.ts \
  src/auto-reply/reply/inbound-meta.test.ts

# Local Codex installed-plugin hotpatch helper
node --test scripts/pd-one-hotpatch-codex-self-heal.test.mjs
```

## Installed artifact checks

When the question is “are the patches active?”, look for exact installed signatures in the package/plugin actually loaded by PD One. Examples from the 2026-05 custom patch stack:

- `personal_memory_remember` and `before_agent_reply` in the loaded `personal-memory` workspace plugin.
- `clearSharedCodexAppServerClientAndWait` in installed Codex/OpenClaw harness dist for Codex app-server self-heal.
- Mattermost attachment behavior in installed `dist/` must be inspected carefully: if the dist still contains `media upload failed, falling back to URL text`, the fail-closed source patch is not fully deployed even if source tests pass. The desired fail-closed path throws `Mattermost media upload failed` before posting fallback text.
- Trusted inbound metadata fixes should use existing normalization helpers such as `normalizePromptMetadataString` rather than stale helper names that may compile only in a different source snapshot.

## Reporting pattern

Use short sections:

- **Current runtime**: source branch, HEAD, upstream base, clean/dirty status, live PID/start command, health.
- **Custom patches installed**: numbered list of hash + subject + behavior.
- **Activation evidence**: installed package/dist/plugin artifact checks.
- **Verification**: pass/fail/blocked; separate runtime-loaded evidence from regression-test status.
- **Caveats**: e.g. upstream version string still reports base release; dependency fetch/test-runner problems are not the same as runtime patch absence.

## Pitfalls

- Do not restart the PD One/OpenClaw gateway just to inspect patches.
- Do not collapse “source branch contains commit” and “live installed package has artifact” into one claim; verify both when the user asks if changes are active.
- Do not report transient local dependency install failures as durable tool limitations. If tests are blocked by package fetch/dependency state, say verification is blocked and state what proof did run.
- Keep Discord/Hermes runtime patch audits separate from PD One/OpenClaw audits; they use different checkouts, processes, and patch stacks.

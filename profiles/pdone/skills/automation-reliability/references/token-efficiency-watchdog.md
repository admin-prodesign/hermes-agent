# Token-Efficiency Watchdog Pattern

Use this pattern when a Hermes/PD One session reveals recurring prompt-footprint drift: oversized skill routers, repeated policy/context injection, or profile/tool loading that grows over time.

## Durable pattern

1. **Compact the live prompt surface first**
   - Keep per-turn injected context to authorization decision, scope, approval gates, language rule, and source paths.
   - Move full detail behind deterministic file/skill lookups or a `full`/`legacy` debug mode.
   - For policy bridges, summarize bulky maps such as `dataAccess` into categories (`full`, `read_limited`, `planned`, `denied`) instead of injecting long prose on every turn.

2. **Convert oversized skills into router stubs**
   - Preserve the original `SKILL.md` under `references/complete-original-skill.md` before replacing it.
   - Main `SKILL.md` should keep only: when to use, what detail to load, non-negotiables, and verification checklist.
   - Prefer class-level umbrella skills; do not create one-off session skills for a single audit.

3. **Install a silent-on-success audit script**
   - Put the deterministic script under `~/.hermes/profiles/<profile>/scripts/`.
   - For Hermes no-agent cron, schedule it by relative script filename only, not absolute path.
   - Default output should be empty when clean; emit only high-severity drift for chat delivery.
   - Provide `--all` or `--json` for manual full reports.

4. **Verify with receipts**
   - Run syntax/compile checks for the audit script.
   - Run the relevant adapter/unit tests after prompt-injection code changes.
   - Manually run the cron once and read back `last_status=ok`.
   - Commit/push code changes and refresh configured Hermes backups.

## Watchdog thresholds that worked well

- High: `SKILL.md` router over ~15k chars without being compacted.
- Medium: `SKILL.md` router over ~10k chars, or frontmatter description over ~180 chars.
- High: policy bridge is not compact-capable when it is injected every Mattermost turn.
- Default cron mode should report only high findings; manual `--all` can include medium cleanup backlog.

## Pitfalls

- Do not schedule no-agent scripts with absolute paths; Hermes cron expects scripts relative to the profile scripts directory.
- Do not make the watchdog LLM-driven when deterministic thresholds are enough; no-agent avoids spending tokens to report that token usage is fine.
- Do not delete full skill content during compaction; preserve it in `references/complete-original-skill.md` first.
- Avoid hardcoding today’s session facts as memory. Store the reusable audit/compaction pattern in this reference instead.

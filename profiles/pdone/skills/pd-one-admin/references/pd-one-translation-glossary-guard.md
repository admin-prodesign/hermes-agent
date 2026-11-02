# PD One translation glossary guard

Use this reference when Andy asks whether PD One translations/final answers are going through the official translation list, or when maintaining translation consistency for bilingual employee-facing output.

## Durable lesson

For PD One, the official translation list/glossary must be treated as **prompt/context guidance only**. Supported agents should see a compact active glossary summary so they can choose approved terms while drafting, but final prose must not be mechanically rewritten from the table.

Reason: Pro-Design translations depend on context, syntax, audience, grammar, and sentence flow. The table is a terminology guide, not a deterministic find-and-replace rule set. For example, `inner mold sticker` is an avoid-as-default translation for `膜內貼`, but the model should still decide whether the natural phrase is `in-mold labels (IML)`, `in-mold labeling (IML)`, or another context-fit construction.

The canonical editable glossary source is the Google Sheet `良器-跨部門-翻譯表 Translation Table` (`CanonicalGlossary` tab, spreadsheet ID `1oFN52hvGDXSP0c_C9OXsNm9sJDH7Rb9fWtzZnj_RvW0`). Prompts read only rows with `Active=TRUE` and `Status=approved`. The former AppSheet Helper `TranslationGlossary` tab is legacy unless Andy explicitly re-promotes it.

## Review queue

Do not write an uncertain term into `CanonicalGlossary` as approved. Append one JSON object to `/home/prodesign/.hermes/profiles/pdone/state/translation-glossary-inbox.jsonl` with `source_term`, `source_language`, `target_language`, `canonical_translation`, `signal_type`, `notes`, and `sample_ref`. The weekly collector imports that inbox into the `ReviewQueue` tab as `Active=FALSE` and `Status=pending-review`. An Andy explicit correction still updates `CanonicalGlossary` directly, then refresh the local cache. Example: `封蓋` → `capping` is an explicit Andy correction, not an inbox candidate.

Send a pending-review notice only to PD One Admin `5gmqtwqf7bde3cyihas79xi8ie`, with `@andy.lin` once. Do not send that digest to IT Work. Send it only when a new unnotified candidate exists, or when a decision was applied. Empty runs stay silent.

Apply a sheet Decision, or one Admin reply line, only when the value is `keep`, `reject`, `approve-add`, or `approve-change`. `approve-change` requires `ProposedChange` or the replacement after the colon. `keep` and `reject` do not change `CanonicalGlossary`. Do not create the reverse row unless the reverse meaning is also safe. Do not scan old Mattermost history. The collector starts from its Admin watermark.

The table stays prompt guidance. Do not replace a full sentence from the table.

## Implementation shape

- Maintain the prompt glossary plugin:
  - `/home/prodesign/.openclaw/workspace/plugins/pd-one-translation-glossary-guard/`
- Maintain the outgoing review plugin:
  - `/home/prodesign/.openclaw/workspace/plugins/pd-one-outgoing-translation-review/`
- Enable both in `/home/prodesign/.openclaw/openclaw.json` through the normal plugin entries/allowlist path.
- Expose a compact active glossary summary to agent prompts via `before_prompt_build` where supported.
- Use `message_sending` only for a bounded **model translation/terminology QA pass** on risk-selected outgoing text.
- Default behavior is prompt-only; avoid a second AI call unless risk signals are present.
- Review-on-risk signals include already-bilingual text, explicit translation/glossary/terminology keywords, announcement/policy wording, or active glossary source/canonical/abbreviation/avoid-term matches.
- Mattermost mentioned-channel auto-translation must handle mixed-language source direction explicitly: a short Chinese heading plus English PD One instructions should target Traditional Chinese for the English prose, not treat the whole message as “mixed Chinese” and repeat the English instructions unchanged. Keep a regression test around `_mention_translation_target_language` / `_generate_mention_translation` for this case.
- Do **not** use `message_sending` for deterministic glossary replacement.
- Do **not** mechanically rewrite outgoing text from glossary pairs.
- Keep behavior context-first:
  - Prefer canonical terms when they naturally fit.
  - Treat `AvoidTranslations` as terms the model should avoid as default translations, not phrases to blindly replace.
  - Preserve Traditional Chinese, English grammar, and mixed-language sentence meaning.
- Standing language policy:
  - Mattermost/employee DMs: reply in the user's language.
  - Mattermost channels/groups: reply bilingually with Traditional Chinese first, English second.
- Reliability policy:
  - Normal outgoing review is fail-open with logging so routine messages are not silently dropped.
  - High-risk workflows (HR, policy, company-wide announcements) may add workflow-specific fail-closed review/approval before send.

## Verification checklist

Before reporting success:

- Validate OpenClaw config: `openclaw config validate`.
- Syntax-check changed plugin files, e.g. `node --check <file>.mjs`.
- Add regression tests covering:
  - Prompt context includes active glossary entries.
  - Prompt context explicitly says the table is context-aware guidance, not deterministic find-and-replace.
  - Prompt plugin registers `before_prompt_build`.
  - Outgoing review plugin registers `message_sending` for risk-selected model QA, not mechanical replacement.
  - Prompt-only default skips ordinary group/channel messages that have no bilingual/glossary/translation risk signals.
  - Review prompt enforces Traditional Chinese first / English second for channels/groups.
  - Review validation rejects empty, too-short, missing-token, or non-bilingual channel rewrites.
- Run targeted/full Node tests as appropriate, e.g. `node --test tests/*.test.mjs`.
- If a gateway reload/restart is needed, follow `references/pd-one-gateway-restart.md`: do not restart unless Andy explicitly approved or bounded checks prove the gateway is already unresponsive.
- After a plugin-load-path change, verify the **live** plugin list with `openclaw health --verbose --json`, not only config validation. A hot reload may apply config entries while the running gateway still lacks local workspace plugins; if the configured plugin is missing from `plugins.loaded`, perform a bounded controlled `systemctl --user restart openclaw-gateway.service` only when policy allows, then re-check health, plugin list, and channel connectivity.
- Treat unrelated OpenClaw runtime/wiki/cache dirt in `git status` as pre-existing unless it is in the touched paths for the current change. Commit/push the scoped plugin/config/docs/test changes first; do not sweep unrelated generated state into the task commit.

## Reportback wording

When asked whether translations are now going through the official list, answer in operational terms:

- "Yes, after the next approved gateway reload/restart, PD One injects the canonical glossary into translation/bilingual prompts by default. Only risk-selected outgoing messages get a second utility-agent translation QA pass; it does not deterministically rewrite final text from the table."
- Mention if config/tests are ready but runtime is not yet live because the gateway has not been restarted.
- Avoid overclaiming live behavior until the restart/reload and smoke test are verified.

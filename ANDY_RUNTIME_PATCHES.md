# House runtime overlay ledger

Source of truth for the next tagged rebase. Score every custom commit
(`git log <tag>..HEAD --oneline`) against this file. Do not skip KEEP.
Do not replay DROP or UPSTREAM-NOW.

## Current base

| | |
|---|---|
| Destination tag | official `v0.23.3` (NousResearch/hermes-agent), annotated |
| Peeled commit | `caafe5389ae585ef77387a962aee05b1bcf17029` |
| Before (previous main) | `87bded48036e304b2373e080184ece2f17fb13d0` (merge of #105, 2026-11-20) |
| After (rebase merge) | `7119fda28b9140719ce5967687d3b1bd95357874` — first parent the peeled tag, second parent the before SHA. The branch tip is the commit that records this SHA. |
| Previous overlay | `v0.23.1` peeled `3b421578588243f920886e6fe79a6faa87ea026e` (PR #92). It is the merge-base of the before SHA and `v0.23.3`. |
| Method | checkout the peeled tag, then `git merge --no-ff` of the before SHA. A linear `rebase --onto` would replay the other parent of the v0.23.1 overlay (~50k fork commits) or would drop the overlay. Do not squash: the tag must stay an ancestor. |
| Recorded before state | HEAD `87bded48036e304b2373e080184ece2f17fb13d0`; `git describe --tags` was `v2026.5.7-108440-g87bded4803` before official tags were fetched, and `v0.23.1-50850-g87bded48036` after (v0.23.1 is an ancestor). Latest calendar ancestor tag `v2026.5.7`. Dirty list empty. |

## Classification rule

No `ANDY_RUNTIME_PATCHES.md` existed on main, in history, or on the house
branches searched before this rebase. The standing rule from the v0.23.1
rebase (PR #92, same as PR #66) still applies: every house change since the
previous overlay is KEEP. DROP none. UPSTREAM-NOW none. This rebase did not
invent drops.

`git log v0.23.3..87bded4803 --oneline` is 50850 commits (the whole fork-only
history, not a linear KEEP series). The commits that landed after the v0.23.1
overlay (#93–#105) are all KEEP and `git cherry v0.23.3` marks each non-merge
as not equivalent (`+`):

- `9ade5d00e3` fix(nemo) provision pinned pnpm and Node for autodeploy builds
- `e6b6ac271c` docs(pdone) route notify guidance to Mattermost
- `491719929a` fix(pdone) show real finding on failure-autofix decision pages
- `7e9ae7993f` fix(pdone) parse self-heal markdown on decision pages
- `07b35a6f61` feat(pdone) vendor live office skills from 2026-11-17 nemo snapshot
- `c30a162001` fix(pdone) retarget pptx-author at firm template
- `afffef2431` build(pdone) pin matplotlib 3.11.2 and guard office skills
- `aec536ab47` chore(pdone) waive lint on vendored office-skill scripts
- `f8d4e9591f` fix(pdone) drop firm-template gallery slides
- `f72a2c94d7` fix(pd_one_ops) Google Docs ops via live Drive writer ACL
- `a247b26be6` andy-auto fix `_PdUnset` shadowing in `execute_document_ops`
- `f6c2f80d0e` andy-auto AppSheet live apply from Andy origin posts
- `6d81a4caa6` andy-auto `pd_one_gateway_restart` safe-ops MCP
- `f7c4110237` fix(deploy) ignore release build scratch in nemo drift check
- `7960ce23bb` fix(nemo) hold failure-autofix pages for Neo webhook
- `22f8c5db81` fix(deploy) build desktop webapp into every nemo release
- `fd53e24157` feat(pdone) Andy Mattermost post auth for Google group member ops

## KEEP scorecard (this rebase)

Conflicted, kept (11 content conflicts). None were skipped.

| Surface | Result |
|---|---|
| `cron/scheduler_script.py` | Conflicted. Kept `_resolve_release_python` (nemo `releases/current` venv when no PM store). `project_root_str()` is already upstream; the house `parents[1]` fallback was not put back. |
| `gateway/platforms/webhook.py` | Conflicted. Kept `_maybe_run_webhook_post_script`. Took the tag's log line (length at info, body at debug). |
| `gateway/run_inbound.py` | Conflicted. Kept `event._memory_recall_user_text`. Used upstream `label_shared_sender` (Slack id neutralization is already in the tag). |
| `gateway/session_worker_delegation.py` | Conflicted. Did not replay the pre-persistence SQLite `_dispatch`. The pdapp-executor allowlist moved to `DELEGATION_ORIGIN_SOURCES` in `persistence/authority/coordination.py`. |
| `plugins/platforms/mattermost/adapter.py` | Conflicted. `is_bot` was already computed the same way above the hunk. Kept the `build_session_key` import. PD One policy/workflow calls outside the hunk stayed. |
| `plugins/platforms/telegram/standalone.py` | Conflicted on the rewritten send-error handlers only. Took the tag's handlers. The house `asyncio.to_thread(os.path.exists, media_path)` check is outside the hunk and remains. |
| `scripts/bundles/stage.py` | Conflicted. Kept `terminal_deps_install_command` (`--reuse`) and `publish_terminal_node_modules`, and the tag's `apps/desktop` workspace plus `webapp` frontend. |
| `scripts/install_root_lint_baseline.json` | Conflicted. Union of both baselines, counts at the max, so neither house pd_one sites nor tag sites fall under the ratchet. |
| `tests/agent/test_bitwarden_secrets.py` | Conflicted. Kept the tag's URL-validation tests and the house rate-limit tests. The rate-limit calls now pass `PROJECT_ID` (a UUID) because v0.23.3 rejects any other project id before the retry. |
| `tests/scripts/test_agent_build.py` | Conflicted. Assertions match the combined command: 5 build steps, `--reuse`, three `--workspace` entries including `apps/desktop`, and the published `node_modules` receipt. |
| `uv.lock` | Conflicted. Restored the tag lock, then `python -m pm.cli lock` for the merged `pyproject.toml`. |

Auto-merged (replayed clean, not hand-edited): the rest of the house tree, including `gateway/session_policy.py` (`pdapp-executor` keeps its stored label and runs as cli), `agent/secret_sources/bitwarden.py` rate-limit retry, memory-recall modules, Mattermost PD One helpers, `profiles/pdone/`, the `[nemo]` extra, cron CWA TLS helpers, and `hermes_cli/terminal_node_deps.py`.

Already upstream, not copied a second time:

- `project_root_str()` for cron script argv (the PR #92 KEEP).
- `label_shared_sender` Slack `<@U…>` neutralization.
- Session-store move. `SCHEMA_VERSION` stays 33 and now lives in `persistence/sqlite/_schema_ddl.py`. `hermes_state_common.py` is the tag's 17-line downgrade marker. House did not edit that file between v0.23.1 and `87bded4803`.

## DROP / UPSTREAM-NOW

None. Nothing in those classes was replayed, because there is nothing in those classes.

## Schema / `_config_version`

`_config_version` on this tree is **54** (`hermes_cli/config_defaults.py`). Session DB `SCHEMA_VERSION` stays **33**, in `persistence/sqlite/_schema_ddl.py`.

A host whose config stamp is 53 runs `_migrate_to_54` on next startup (`hermes_cli/config_migrations.py`). That migration sets the `prompt_caching.cache_ttl` default to `auto` (1h human-paced, 5m machine-paced). A template-seeded `"5m"` (comment-byte proof on a local file) is deleted. Any other `"5m"` is treated as a user pin and kept, with a notice. Non-file backends keep `"5m"`.

This rebase does not edit host or profile configs, does not set `prompt_caching.cache_ttl`, and does not replace `jobs.json`. Neo sets `cache_ttl` to the documented default `auto` on PD Neo and pdone host configs after deploy.

Earlier tag steps a host still below 53 would also run: 51 removes `cron.bot_chat_delivery_timeout_seconds`; 52 adds `browser.backend` and extension control; 53 changes a still-default `clarify_timeout` from 3600 to 90.

## Lockfiles

`needs_manual`: yes. All three changed relative to `87bded4803`.

- `pyproject.toml` vs the tag is only the house `[nemo]` extra and the matching office pins under `[test]` (`honcho-ai==2.5.1`, `browser-cookie3==0.20.1`, `pyyaml==6.0.3`, `requests==2.34.2`, `openpyxl==3.1.5`, `python-docx==1.2.0`, `python-pptx==1.0.2`, `matplotlib==3.11.2`, plus `hermes-agent[mcp]` and `hermes-agent[messaging]`).
- `uv.lock` vs the tag is `+456 / -1` after `python -m pm.cli lock`.
- `pm/lock.json` matches the tag (it differs from main because main was still on the v0.23.1 lock).

## Rollback

```
git reset --hard 87bded48036e304b2373e080184ece2f17fb13d0
```

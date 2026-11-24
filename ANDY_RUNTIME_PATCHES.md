# House runtime overlay ledger

Source of truth for the next tagged rebase. Score every custom commit
(`git log <tag>..HEAD --oneline`) against this file. Do not skip KEEP.
Do not replay DROP or UPSTREAM-NOW.

## Current base

| | |
|---|---|
| Destination tag | official `v0.23.4` (NousResearch/hermes-agent), annotated `3ac54e1012be`, peeled `8fc0374447313e276f6b9a2764bfc750190c966a` |
| Before (previous main) | `607472c055f4f5a1558981b43a87ef5a3acbb40d` (merge of #108, 2026-11-24; includes #106 v0.23.3 overlay, #107, #108) |
| After (rebase merge) | `36ec386728e9e034899547e20aa1d4184b644d45` — first parent the peeled tag, second parent the before SHA. The PR head is that merge plus the ledger stamp and the v0.23.4 CI lint adaptations. |
| Previous overlay | `v0.23.3` peeled `caafe5389ae585ef77387a962aee05b1bcf17029` (PR #106). It is an ancestor of the before SHA. |
| Method | checkout the peeled tag, branch `overlay/v0.23.4`, then `git merge --no-ff` of the before SHA. A linear `rebase --onto` would replay fork-only history or drop the overlay. Do not squash: the tag must stay an ancestor. |
| Recorded before state | HEAD `607472c055f4f5a1558981b43a87ef5a3acbb40d`; dirty list empty on this run. |

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

## KEEP scorecard (v0.23.4 rebase)

Conflicted, kept (2 content conflicts). None were skipped.

| Surface | Result |
|---|---|
| `tui_gateway/contracts/canonical_sessions.py` | v0.23.4 moved `CanonicalClientIdentity` to `tui_gateway/contracts/common.py`. Kept the tag import from `.common`, added house `WireEnum` + `SessionCreateSource` built from `gateway.session_policy.SURFACES` (includes `pdapp-executor`). |
| `apps/shared/src/gateway-contract.generated.ts` | Dropped the duplicate `CanonicalClientIdentity` hunk from main; kept v0.23.4's definition (with `kind`) and house `SessionCreateSource` including `pdapp-executor`. Regenerated with `scripts/gen_gateway_contracts.py`. |

Auto-merged (replayed clean, not hand-edited): the full house tree from the v0.23.3 overlay plus #107 (Mattermost cron thread delivery) and #108 (Mattermost member usernames with dots), including `gateway/session_policy.py`, PD One ops, nemo extras, and Mattermost cron targeting.

House commits on main since the v0.23.3 overlay merge (`7119fda28b..607472c055`, non-merge):

- `bc9a7e8acf` fix(cron): deliver Mattermost jobs into the named thread (#107)
- `34cddc8948` fix(pd_one_ops): allow dots in Mattermost member usernames (#108)

## KEEP scorecard (v0.23.3 rebase, PR #106)

Historical reference — eleven content conflicts; see git history at `7119fda28b` and the PR #106 description.

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

## CI adaptations on top of the merge

v0.23.4 merge (on top of #106's adaptations): `scripts/check` failed on ruff until `tools/pd_one_ops/pd_one_safe_ops_part1.py` sorted `validate_mattermost_member_username` before `validate_mattermost_name` in `__all__` and used `str.removeprefix('@')` for member username normalization (#108).

`python scripts/check` then reported 22 checks ok. No `boundary_lint` or `catalog_core_imports` baseline changes were required (unlike PR #106).

## Rollback

```
git reset --hard 607472c055f4f5a1558981b43a87ef5a3acbb40d
```

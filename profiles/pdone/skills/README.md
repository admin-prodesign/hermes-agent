# PD One profile skills (vendored)

Hermes profile skills for the `pdone` profile. They ship on the nemo host under
`~/.hermes/profiles/pdone/skills/` and are **not** bundled under top-level
`skills/` in the release tree.

When tracked here, they sync into a profile via distribution update / house
deploy (`scripts/deploy/nemo/hot.py` skill sync). Keep each `SKILL.md` lean
(about 8 KB or less): triggers, decision rules, and canonical paths in
frontmatter; move tables, long prose, and examples into `references/*.md`.

## Lean targets (nemo live sizes, 2026-11-02)

| Skill | Live `SKILL.md` (bytes) | Notes |
| --- | ---: | --- |
| `pd-one-hermes-permissions` | 40,600 | `skills.auto_load` on pdone |
| `monthly-worker-scheduling` | 32,400 | high `skill_view` |
| `appsheet-copilot` | 25,200 | safe-ops scripts under this tree |
| `worker-scheduling-optimization-rules` | 24,300 | **Not in Neo dump (2026-11-02)** — still on nemo only |
| `pd-one/pd-one-admin` | 23,200 | **Not in Neo dump (2026-11-02)** — still on nemo only |

After lean (this repo, bytes): `pd-one-hermes-permissions` 4509; `monthly-worker-scheduling` 4463; `appsheet-copilot` 1474; `gog` 1208; `automation-reliability` 1400; nested `automation-source-key-integrity` 951, `approval-queue-incident-response` 1535, `stateful-runner-delivery` 1583.

Export from nemo before editing in git (Neo ops: do not change pdone
`auto_load` or host config in the lean PR):

```bash
rsync -a ~/.hermes/profiles/pdone/skills/ ./profiles/pdone/skills/
```

Do not restate root `AGENTS.md` permission rules in these skills.

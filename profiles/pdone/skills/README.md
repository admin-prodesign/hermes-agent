# PD One profile skills (vendored)

Hermes profile skills for the `pdone` profile. They ship on the nemo host under
`~/.hermes/profiles/pdone/skills/` and are **not** bundled under top-level
`skills/` in the release tree.

When tracked here, they sync into a profile via distribution update / house
deploy (`scripts/deploy/nemo/hot.py` skill sync). Keep each `SKILL.md` lean
(about 8 KB or less): triggers, decision rules, and canonical paths in
frontmatter; move tables, long prose, and examples into `references/*.md`.

## Size guard (repo `SKILL.md` bytes)

| Skill | Before import (bytes) | After lean (bytes) |
| --- | ---: | ---: |
| `pd-one-hermes-permissions` | 40,576 | 4,509 |
| `automation-reliability` | 34,719 | 1,401 |
| `monthly-worker-scheduling` | 32,429 | 5,761 |
| `gog` | 26,936 | 1,208 |
| `appsheet-copilot` | 25,173 | 1,473 |
| `worker-scheduling-optimization-rules` | 24,301 | 6,216 |
| `pd-one-admin` | 23,208 | 1,332 |
| `stateful-runner-delivery` | 14,970 | 1,583 |
| `approval-queue-incident-response` | 14,543 | 1,502 |
| `automation-source-key-integrity` | 10,711 | 951 |
| `it-meeting-briefing` | 6,501 | 6,501 |
| `it-meeting-progress-summary` | — | 4,253 |

`it-meeting-briefing` is the 2026-11-11 live skill, kept intact so the 12:00 pack job still inlines the same body. `it-meeting-progress-summary` is the summary-only skill for cron job `9606f49ec7ec`.

Export from nemo before editing in git (Neo ops: do not change pdone
`auto_load` or host config in the lean PR):

```bash
rsync -a ~/.hermes/profiles/pdone/skills/ ./profiles/pdone/skills/
```

Do not restate root `AGENTS.md` permission rules in these skills.

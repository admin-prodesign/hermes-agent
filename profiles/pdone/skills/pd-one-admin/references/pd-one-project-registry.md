# PD One Project Registry

Use this reference when Andy asks to centralize, broaden, classify, or brief ongoing PD One/Hermes projects: automations, playbooks, features, monitors, dashboards, integrations, migration streams, and recurring reports.

## Current canonical surface

- Google Sheet: dedicated PD Neo Project Registry spreadsheet `1IUpq9ytsI6YWMOHb4jgF8J3oSVV-sQVuFeWbqPp-PgU`, tab `project_registry` (`gid=727992106`). The separate `PD One` governance spreadsheet `1kJntZ6L8P72q_Brsp7ixrQsmxnDs6EACMQqpwgGxLOE` is not the Project Registry write target.
- Daily briefing cron: `3b53eff259cd` (`PD One Project Registry morning briefing`), scheduled `0 1 * * *` = 09:00 Taiwan time, delivered to the originating Mattermost admin thread/channel.
- Script: `/home/prodesign/.hermes/profiles/pdone/scripts/pd_one_project_registry_briefing.py`.
- Same-turn touch helper: `/home/prodesign/.hermes/profiles/pdone/scripts/pd_one_project_touch.py`.

## Same-turn Project Index update rule

When meaningful work creates, resumes, changes, blocks, verifies, or retires a Project Index item, run the touch helper with `--live` before the final reply of that same turn. Do not wait for thread/session close or rely on the daily briefing sync; the daily scheduled sync is only a safety net.

Minimum pattern:

```bash
/home/prodesign/.hermes/profiles/pdone/scripts/pd_one_project_touch.py \
  --project-id PDOP-KEYWORD-SLUG \
  --status "Active / 進行中" \
  --last-did "What changed or was verified." \
  --next-action "Next concrete action." \
  --why "Why this project exists or why the change matters." \
  --source-of-truth "Canonical file/sheet/service/thread id." \
  --runtime-info "Script, cron, service, commit, or readback receipt." \
  --notes "Optional concise operator notes." \
  --live
```

The helper reads live headers, preserves existing row values unless a field is supplied, uses stable keyword IDs such as `PDOP-AUTOMATION-SUPERVISOR`, maps old sequential IDs through `/home/prodesign/.hermes/profiles/pdone/config/project_registry_id_aliases.json`, timestamps `Last updated UTC`, runs the project registry briefing/list sync immediately, and prints JSON containing the project id, row/range, status, sync status, dashboard URL, counts, update receipt, and live readback.

## Registry schema

Maintain rows by stable keyword `Project ID / 專案ID` values (`PDOP-KEYWORD-SLUG`), not sequential numbers. Current core columns:

1. `Project ID / 專案ID`
2. `Project / 專案`
3. `Category / 類別`
4. `Status / 狀態`
5. `Owner / 負責人`
6. `Source / 來源`
7. `Evidence / 證據`
8. `Last did / 上次進度`
9. `Next steps / 下一步`
10. `Cadence / 頻率`
11. `Briefing include? / 早報`
12. `Risk / 風險`
13. `Last updated UTC / 更新時間`
14. `Notes / 備註`
15. `Primary channel / 主要頻道`

Important user correction from rollout: broad sweeps must include the primary discussion/grouping channel, such as `PD One Admin`, `Facilities`, `Sales`, `Product Quality`, `Production Schedule`, etc. The daily briefing should group by `Primary channel`, not produce a long flat list.

## Status classification

Normalize `Status / 狀態` instead of leaving mixed ad-hoc statuses:

- `Active / 進行中` — ongoing work, active automation, or maintained playbook.
- `Review / 待確認` — candidate or unclear live ownership; needs Andy/admin triage.
- `Paused / 暫停` — explicitly stopped/paused but worth tracking until replaced/retired.
- `Active until YYYY-MM-DD / 進行至YYYY-MM-DD` — time-boxed recurring workflow.
- `Retire / 退役` — use only with clear evidence/approval; do not retire uncertain rows just to reduce noise.

For daily briefings, use `Briefing include? / 早報 = no` to quiet low-value monitor rows rather than deleting them.

## Discovery sources for broad sweeps

For a broader project sweep, combine several read-only sources and dedupe by project class:

- Recent session history for non-one-off work: `automation`, `playbook`, `feature`, `dashboard`, `monitor`, `watchdog`, `tracker`, `integration`, `migration`, `SOP`, `AppSheet`, etc.
- Hermes cron jobs (`cronjob list`) and cron scripts under the active `pdone` profile.
- User systemd timers/services (`pd-one-*`, Hermes dashboard, Honcho/Ollama/proxy services, LINE tunnel, webhook receivers).
- Supervisor registry and remediation plans under `/home/prodesign/.hermes/profiles/pdone/supervisor/`.
- Runtime scripts, runbooks, artifacts, and state files under `/home/prodesign/.hermes/profiles/pdone` and legacy-reference subtrees.
- Existing tracking sheets/tabs such as `automation_registry` and related Project List maintenance state.

Avoid dumping sensitive log contents. Use paths, timestamps, job IDs, and high-level evidence summaries.

## Triage-and-dispatch workflow

When Andy asks to tackle the PD One project list interactively, run it as a controller-led conveyor rather than trying to solve the whole registry in one pass:

1. Read the live `project_registry` plus current automation/job evidence and present only the first 10–15 highest-signal items.
2. For each item, show a compact decision card/table: project ID, current state, recommended next step, and decision options such as `Investigate`, `Dry-run`, `Monitor`, `Park`, `Retire`, `Split`, or `Merge`.
3. Wait for Andy's decision per item or batch. Treat `Investigate` as read-only; treat `Dry-run` as a no-side-effect plan/probe; do not write registry rows, send DMs, requeue events, edit config, or restart gateways without explicit follow-up approval.
4. Dispatch independent read-only investigations to subagents with exact project IDs, paths, safety boundaries, expected receipts, and restricted toolsets. Keep the main thread moving to the next decision while subagents run.
5. When async subagent results return, verify key claims with direct receipts where practical before recommending status changes. Summarize results into decision outcomes such as `Continue investigate`, `Dry-run route audit`, `Monitor`, or `Approval-required fix`.
6. Avoid claiming registry updates unless the Sheet write/readback has actually been performed after approval.

Useful first-batch prioritization signals: high risk, `Review / 待確認`, active error/failure status, cross-cutting reliability impact, production DMs/Sheet writebacks, approval-ticket infrastructure, and missed-reply/replay rails.

## Write/update workflow

1. Prefer the same-turn helper for single-project changes: `/home/prodesign/.hermes/profiles/pdone/scripts/pd_one_project_touch.py --project-id PDOP-#### ... --live`.
2. For bulk sweeps, read the current `project_registry` header and rows.
3. Generate new/updated rows locally, preserving stable IDs and existing human edits where possible.
4. Do a dry-run bounded Sheets update, then live update after scope is clear/approved.
5. Read back the exact written range.
6. Keep the grid tidy: freeze header row + first two columns; auto-size; trim or intentionally document allocated blank rows/columns.
7. Run the briefing script locally and verify preview length/readability before reporting success; the touch helper does this automatically for single-project changes.
8. Report concise receipts: row count, project count, range, grid dimensions, status counts, and briefing schedule/job ID.

## Briefing format

For small registries, section-per-project can work. For broad registries (dozens of projects), keep the briefing compact:

- Sort/group by `Primary channel / 主要頻道`.
- Use one bullet per project: ID, title, status, last did, next step.
- Keep text short; the Sheet is the detailed source of truth.
- Mention that editing `Status`, `Primary channel`, or `Briefing include?` changes future briefings.

## Interactive triage-and-dispatch mode

When Andy asks to tackle the PD One project list interactively, run it as a controller-led conveyor rather than dumping the entire registry:

1. Read the live `project_registry` and relevant read-only inventory such as cron jobs, timers, state/log mtimes, and recent session evidence.
2. Present a first batch of roughly 10–15 high-signal projects with compact decision cards: current state, risk/blocker, recommended next step, and decision options (`Investigate`, `Dry-run`, `Monitor`, `Park`, `Retire`, `Split`, `Merge`).
3. After Andy chooses actions, dispatch bounded subagents for independent read-only investigations or dry-run designs, while the controller keeps the thread moving down the next item.
4. Respect the live `delegate_task` concurrency cap (currently 3 concurrent child tasks): batch only up to the cap, then dispatch later items in a second wave.
5. For approval-gated areas, subagents may gather evidence and prepare dry-runs/designs, but the controller must stop before writes, sends, source-system changes, policy/config edits, gateway restarts, requeues, or ticket mutations.
6. If Andy says to execute next steps and only bother him when needed, continue with read-only/dry-run work, maintain a session todo list, and report back only for real approval gates, blockers, or decision points.
7. If a subagent times out or returns incomplete, do not stop the whole workflow. Do a bounded controller-side read-only fallback, record the timeout honestly, and either produce a partial result with receipts or re-dispatch a narrower task.
8. Before reporting a subagent result as fact, verify important receipts from the main controller when practical (paths, mtimes, counts, cron IDs, state summaries, readbacks). Keep the user-facing report concise and bilingual in Mattermost group/channel contexts.

## Pitfalls

- Do not let project tracking live only in chat/session summaries.
- Do not make the daily report a long ungrouped wall of text; group by primary channel and use `Briefing include?` to suppress low-value rows.
- Do not retire rows without clear evidence; classify uncertain rows as `Review / 待確認`.
- Do not conflate the Project Registry with the cross-department Project List maintenance automation; the former tracks PD One/Hermes work, while the latter tracks business project follow-ups.
- For source-system writes, external sends, employee DMs, policy/config changes, or gateway restarts discovered during project triage, stop at recommendation/dry-run unless explicitly approved.
- When the same turn includes durable code/doc changes, commit/push first when practical, then run the same-turn touch helper again with the final commit SHA/push target in source/evidence/runtime fields. Otherwise the ledger can record an intermediate state and miss the real verification receipt.
- Keep touch-helper notes concise and deduplicated. Treat `Purpose/why:` and `Runtime:` as singleton labeled fields: `build_notes` should collapse legacy duplicates and replace the prior line by prefix, not merely dedupe exact strings. Add a unit test with multiple old `Runtime:` lines. When a turn has several commits/touches, perform one final live touch after the last push, then verify readback contains exactly one current Purpose line and one current Runtime line together with final `Last did`, `Next steps`, `Evidence`, and `Last updated UTC`.

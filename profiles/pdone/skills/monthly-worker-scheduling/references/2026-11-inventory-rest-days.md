# 2026-11 inventory-day rest / 5S skeleton crew

Andy requested this on 2026-09-16 in Mattermost Injection Molding Management thread `ps75zk79tf878n5d1bmieb1x7c` (channel `87e6pxw6x3d5x8zitsquu3ec8o`).

## Cycle

- Target scheduling month: **2026-11** (November 2026 / `115年11月`)
- Inventory dates: **2026-11-26** and **2026-11-27**
- Checkpoint type: plant inventory rest plus a small 5S skeleton crew
- Status: all 4 groups were FEASIBLE. Day operators, day cadres, and night cadres have write verification with `mismatched_actions` 0. Night-operator values were written from the normal 11/27 solve. Do not claim night-operator formatting complete unless that group's verification report also has `mismatched_actions` 0. Do not write the older night report that locked 11/27 as rest.

## Required action when November scheduling starts

Remind Andy before November source setup / preflight / solve / writeback:

1. Most operators and cadres rest on 11/26. Day shift and `幹部-日` also rest on 11/27. Schedule `作業員-夜` normally on 11/27. Do not lock night operators to hard rest or mandatory work that day.
2. A **handful** of people stay on those two days to do **5S** (work, not rest).
3. Andy named two people on 2026-10-28 and told PD One to propose a Taiwanese/Filipino mix, then encode it.

Confirmed encoding, already written to source `申請日期-當月統計`:

- 11/26 mandatory work (`AS` = `26`), day shift: 楊正義, 林三原, 帕薩 | PAASA, 達迎 | CORBANTES DARWIN VELASCO, and 阿弟 | SALARDA RANDY PERALTA. 觀貝拉 | ABELLA JAYSON SANTOS is not on this crew.
- Andy 2026-10-29: 觀貝拉 is terminated on 2026-11-13. His last active day is 2026-11-12, and that day is hard rest. Source row is `W30` / `申請日期-當月統計!C30`. `AP30` is `12`. `AS30` is blank. Days 13-30 are inactive. The source grid has no free column, so the solver reads `config/last_active_days.json`. Do not put 22, 26, or 27 back on his row. Do not mark days after 11/12 as `V`. The parse note `LastActiveDay N applied from config` is a receipt. It must not block solve. Out-of-range and identity-mismatch warnings still block.
- 楊正義 and 林三原 stay because Andy named them. Paasa, Randy, and Darwin are the remaining operators Andy selected on 2026-10-28. 馬若南 and 諾門 were removed from that crew and returned to hard rest on 11/26 and 11/27.
- The six 5S people have hard rest on 11/27 (`AP` = `27`).
- Day-shift and `幹部-日` rows keep hard rest on 11/27. Night operators keep hard rest on 11/26 only. Do not put 27 in their `AP` or `AS`.
- 黃俊中 is off the November dest cadre tab. Blank his source class. Keep the name. Do not encode his old flex-rest days and do not re-add him.
- Existing mandatory-work days stay. Examples: 呂會銘 day 20, 阮紅蓉 day 15.
- 5S is mandatory work, not training. Do not write `AT` for this crew.
- No past schedule from 114年11月 through 115年10月 named a 5S inventory crew. Do not add more names unless Andy names them.
- Blank-class rows were not marked: 陳玉賢, 羅木, 艾格.
- If the November solve is infeasible, relax only the hard-rest days that block it. Do not drop the six 11/26 mandatory-work marks unless Andy changes the crew.
- If `sync_source_rollover` or `preflight` returns `invalid literal for int() with base 10: ''`, stop. The worker-scheduling MCP call is sending an empty integer. Do not bypass that tool with a shell command. Report the tool defect.
- The guard belongs in `admin-prodesign/hermes-agent` through the Cursor Cloud Agents API, based on the live `HERMES_RUNTIME_SHA`. If `POST /v1/agents` returns `usage_limit_exceeded`, stop. Do not retry that POST. Do not open a local branch unless Andy asks. On 2026-10-28 the live SHA was `2fa20d3dbfe03a68a0ea1ec0fddfec938a883caf` and the create call returned that billing error.
- A later retry can still fail after the payload helper exists. `source_setup` does not call the command runner, so it can succeed. `sync_source_rollover` calls `_run_worker_scheduling_command`, which does `int(site_text('WORKER_SCHEDULING_MIN_TIMEOUT_SECONDS'))`. That key is absent from live `config.yaml`. `site_text` then returns `''`, and `int('')` raises the same error. Do not treat a Pillow fix as clearance for this path. Do not bypass the tool with a shell command.
- Andy 2026-10-28: Taiwanese operators have flex rest on 11/28 for election day (`AR` includes `28`). Basis is the November dest 工號 prefix `M`, not a name guess and not an HR identity-category read. Do not add day 28 to Filipino `F` operators or to cadres. The ten source rows are 阮紅蓉, 陳淑敏, 范珮晴, 黃廣妹, 劉山英, 何雅菁, 楊焰雰, 羅秀鳳, 劉純安, and 林玉彩.
- Do not leave day 28 in both `RequestedRestDays` and `FlexRestDays`. Remove `28` from requested rest for 陳淑敏, 黃廣妹, 劉山英, and 楊焰雰. Keep `28` in `FlexRestDays`. The `E2` array formula clears the day-28 `申` marker. Do not type into `AF`. Keep `申` on the remaining requested days.
- Dest night name for Centeno is exactly `森特諾 | CENTENO CHRISTIAN LAWRENCE`. Do not append `VITERBO` on the source name. Source `C38` must match that dest string.
- Before any November solve, read dest notes. `115年11月-日!AD15` is day 22 `V` with note `該員須體檢須排休` for 蕾查兒. That day is hard rest for 蕾查兒. The same note on `AD16` was for 觀貝拉, but Andy later said he leaves on 2026-11-13. Do not keep day 22 as his hard rest. A solve that does not rebuild `AP:AT` from dest markers is not valid for writeback, except the 觀貝拉 termination override in `config/last_active_days.json` wins over the old dest note.
- Andy 2026-10-28 correction: do not force night operators to rest or to work on 11/27. Schedule `作業員-夜` normally that day. Keep 11/26 hard rest for night operators. `幹部-夜` stays mandatory work on 11/27 unless Andy changes that. Do not apply a 11/27 work lock to day shift or `幹部-日`.
- Andy said 羅蒂思 | MENDOZA MA. LOURDES CAY is no longer employed. Blank only source class `B45`. Keep the name. AppSheet `HR_Employees` employee `F00020` / person `YGJRQVQP` still says Employed with an empty separation date. Report that conflict. Do not edit the HR row from this scheduling task.

## Playbook gate

The inventory-day source intent is written. Continue the normal November playbook. Do not ask Andy to name the crew again unless he changes it.

Do not treat this reminder as a reason to skip preflight or solve. The solve is the feasibility test for the hard rests.

Record the decision on the `排班流程追蹤 Tracker` tab under inventory-day / 5S skeleton-crew.

## Reminder automation

A one-shot Hermes cron should fire at the November playbook kickoff window: **2026-10-21 01:00 UTC** (09:00 Taipei), matching the 21st-of-month kickoff. The reminder must not assign rest or write sheets.

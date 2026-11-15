# 2026-10 night-to-day operator swap checkpoint

Andy requested this on 2026-09-05 in Mattermost Injection Molding Management thread `t3ntk97idib7denyc5b43xxash` (channel `87e6pxw6x3d5x8zitsquu3ec8o`).

## Cycle

- Target scheduling month: **2026-10** (October 2026 / `115年10月`)
- Checkpoint type: operator day/night swap and headcount-balance
- Status: **confirmed 2026-09-22**; class remap written; 24h night→day rest applied for 瑪菈 Oct 1

## Required action before October preflight/solve/writeback

Swap **three seasoned night-shift operators** (`作業員-夜`) onto **day shift** (`作業員-日`).

Andy confirmed 2026-09-22 (Sarel excluded; contract ends December):

- Night→day: 阿弟 `F00043`, 瑪菈 `F00067`, 古倫 `F00095`
- Day→night: 來斯特 `F00106`, 雷恩 `F00107`, 森特諾 `F00108`

**24h shift-change rule (Andy 2026-09-22):** if a night→day worker **worked the last prior-month night**, require one day-shift rest on the first new day-shift date (`HardRestDays` day 1). If that last night was already rest (`V`/`特`/`喪`/`申`/`病`), do not add a day rest. Day→night after a prior day-shift work day does **not** require a rest. Derive prior-night work from the previous **night** tab, not the new day tab’s `Last Days Worked` formula.

October 2026 evidence (Sept 30 night): 瑪菈 worked → Oct 1 hard rest; 阿弟 and 古倫 already `V` → no extra rest.

Historical note: names were unspecified until that confirmation. Do not invent additional names. Class/participation writes need Andy confirm:

1. which three night operators move to day;
2. whether three day operators move to night in exchange, or another headcount-balance plan;
3. that destination October day/night tabs and `\u7533\u8acb\u65e5\u671f-\u7576\u6708\u7d71\u8a08` class fields should be updated.

## Playbook gate

Treat this as a roster class-remap decision. It is **not green**. Do not fill AP:AT, run solve, or write the generated October schedule until this checkpoint is decided or Andy explicitly defers it.

After a confirmed swap, follow the missing-worker / class-participation pattern: change only the scheduling class/participation field, preserve name/audit context, dry-run, live write, and read back `B:D` plus formula-owned structured output. Do not write formula-owned `E:AI`, `AK:AO`, or `AU:AX`.

Record the decision on the `\u6392\u73ed\u6d41\u7a0b\u8ffd\u8e64 Tracker` tab under operator day/night swap and headcount-balance.

## Reminder automation

A one-shot Hermes cron should fire at the monthly kickoff window: **2026-09-21 01:00 UTC** (09:00 Taipei), matching the 21st-of-month playbook kickoff. The reminder must not execute the swap.

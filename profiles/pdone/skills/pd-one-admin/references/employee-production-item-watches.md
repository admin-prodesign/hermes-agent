# Employee production-item watches

Use when an employee asks PD One to notify them when a product is scheduled, for example “Notify me when 18LB 桶 is scheduled for production.”

This is not cron. Employees never receive `cronjob` / `hermes cron create`.

## First slice

Type: `production_item_on_schedule`

- MCP: `mcp__pdone_safe_ops__pd_one_employee_watch`
- Actions: `create` / `list` / `cancel`
- One-shot, current Mattermost thread only
- Exact sender from session env, else claimed sender must be an active profiled user
- Unique canonical product or mold id at create time
- Cap 5 active watches per owner, expiry 1–30 days (default 14)
- Shared no-agent poller: `scripts/pd_one_employee_watch_poller.py`

## Agent path

1. Call `create` with `query`, `origin_channel_id`, `origin_root_id`, and the live sender id.
2. If `item_not_found` or `ambiguous_item`, show `candidates` and ask the requester to pick one exact product name or `PD-xxx`. Do not guess.
3. If `already_scheduled`, report the matches and do not create a watch.
4. If `ok`, tell them this thread will get one bilingual reply when it appears. They can `list` / `cancel`.

## Poller

Reads the latest `production-schedule_*.json` snapshot. Silent stdout when idle. On fire, posts in the origin thread and marks the watch `fired`.

Live Mattermost send requires the pdone poller cron. MCP create does not send.

## Do not

- Create per-employee Hermes cron jobs
- Notify a different channel or company outbound DM
- Store unresolved fuzzy chat text as the predicate
- Run an LLM on each tick

# Monthly worker scheduling kickoff automation

Use this reference when Andy asks PD One/Hermes to initiate the monthly worker scheduling playbook automatically in Mattermost.

## Current implementation / desired behavior

- Legacy purpose: post a bilingual kickoff reminder to the Mattermost 成型部管理 / Injection Molding Management channel on the 21st of each month.
- Current Andy preference from 2026-06-22: future 21st-of-month automation should **directly kick off the scheduling playbook in a new Mattermost thread**, not only send a reminder. The kickoff should @ mention task owners who need to act, such as `@anna` for monthly scheduling constants, and should make the next required reply obvious.
- Target channel URL: `https://mattermost.prodesign-group.com/injection-molding/channels/management`
- Target channel ID: `87e6pxw6x3d5x8zitsquu3ec8o`
- Channel display/name observed during setup: `管理相關 Management` / `management`
- Hermes cron job name: `PD One monthly worker scheduling playbook kickoff`
- Hermes cron schedule: `0 1 21 * *` (01:00 UTC = 09:00 Taipei, every 21st)
- Script wrapper: `/home/prodesign/.hermes/scripts/pd_one_worker_scheduling_initiator.sh`
- Python script: `/home/prodesign/.hermes/scripts/pd_one_worker_scheduling_initiator.py`
- State: `/home/prodesign/.hermes/state/pd-one-worker-scheduling-initiator/state.json`
- Log: `/home/prodesign/.hermes/logs/pd-one-worker-scheduling-initiator/runs.jsonl`

## Reliability pattern

- Use a Hermes `no_agent` cron with a shell wrapper under `~/.hermes/scripts/`.
- Keep the actual logic in a Python script so it can:
  - verify Mattermost credentials and the target channel with `--check-only` before posting;
  - render a `--dry-run` message for review;
  - lock with `fcntl.flock` to avoid overlap;
  - record one sent post per target scheduling month, preventing duplicate monthly reminders;
  - write JSON state and JSONL run logs with post IDs.
- When the setup happens on the 21st itself, run the script once manually after dry-run verification so the current cycle is not missed; the idempotency state then prevents duplicate posts for that target month.

## Message content requirements

The kickoff reminder should be bilingual in Mattermost channels and should include:

- target month;
- reminder that Anna/HR should provide monthly constants: required rest-day count and total working hours;
- before asking Anna to restate constants, search the active kickoff thread, other same-cycle management scheduling threads, the Tracker tab, and local receipts first;
- explicit reminder not to ask Anna for employee rest-request data, because requests come from Google Forms into `原資料`;
- source-first correction rule: confirmed request corrections belong in `原資料`, not only downstream schedule tabs;
- annual employee trip checkpoint language where appropriate;
- dry-run-before-solve/writeback reminder;
- instruction that once monthly constants exist, the playbook assumes rest requests are already submitted, runs month/source consistency checks, and on a green result fills required columns and solves/writes the primary month without waiting for Andy;

## Verification receipt to report

When creating or changing this automation, report:

- cron job ID/name/schedule/next run;
- channel ID + channel readback name;
- dry-run result was rendered;
- live post ID if a current-cycle kickoff was sent;
- state/log paths;
- backup/commit receipt if Hermes backup is configured.

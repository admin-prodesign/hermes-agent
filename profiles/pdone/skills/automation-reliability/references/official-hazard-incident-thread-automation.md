# Official-source hazard trigger → Mattermost thread workflow

Use this pattern for unattended weather/disaster automations that turn public official data into an employee-facing incident thread and tracker writes.

## Source hierarchy

1. Prefer a machine-readable official product over visible page labels.
2. Keep the public human page as a cited/readback surface.
3. Treat the government closure/suspension page as confirmation, not as a forecast model.
4. Record source timestamp, event identifier, parsed value, and raw-source URL in every event receipt.

### Taiwan typhoon example

- CWA storm metadata: `https://www.cwa.gov.tw/Data/js/typhoon/TY_NEWS-Data.js`
  - Parse `TY_DataTime` and active storm codes.
- CWA Taoyuan 120-hour force-7 wind probability:
  - `https://www.cwa.gov.tw/Data/typhoon/TY_NEWS/WSP-AREA_<TY_DataTime>_WHOLE-DURATION.json`
  - Read `AREA.Taoyuan`.
- CWA active warning products: `https://www.cwa.gov.tw/Data/js/warn/Warning_Content.js`
  - Parse `WarnContent_TyWarn`; `W21` is the land typhoon warning product.
- Human-readable citations:
  - `https://www.cwa.gov.tw/V8/C/P/Typhoon/TY_NEWS.html`
  - `https://www.cwa.gov.tw/V8/C/P/Typhoon/TY_WARN.html`
- DGPA stop-work confirmation:
  - `https://www.dgpa.gov.tw/typh/daily/nds.html`
  - Parse the exact table row containing `桃園市`; do not use a greedy cross-row regex.
  - Distinguish a citywide closure from district-only closures. For a Guishan-based factory, a district-only announcement is positive only when its closed-district scope includes `龜山區`; `復興區停止上班` alone must not be treated as a Taoyuan-wide rest day.
  - Treat citywide wording as positive only when the row contains `停止上班` and does not also say `照常上班` or `正常上班`.

## Parsing pitfalls

- **Do not activate from static page labels.** The CWA warning page markup always contains hidden/template phrases such as `陸上颱風警報` and `海上陸上颱風警報`, even with no active warning. Use the active warning product array and require `W21`.
- Decode official CWA/DGPA response bytes as UTF-8 when HTTP charset handling is ambiguous; otherwise Chinese evidence and date/row matching can silently fail.
- Parse DGPA dates with optional whitespace between ROC year/month/day components, then convert ROC year to Gregorian.
- A CWA force-7 wind-impact probability is **not** a typhoon-rest-day probability or damage probability. Label it as a readiness proxy; DGPA/local government is the official suspension source.

## Explainable activation tiers

A conservative starting policy:

- Low: official local force-7 probability `<20%`.
- Watch: `20–49%`.
- High forecast: `>=50%` across two **distinct official forecast timestamps**, not two polls of the same source cycle.
- Immediate high: active official land warning.
- Confirmed: government stop-work row is positive.

Thresholds are operational policy, not meteorological truth. Store them in a reviewed configuration surface and cite the exact official value that crossed the threshold.

## Thread and tracker state

- Stable task IDs (`T01`, `T02`, …) are the reply contract. Parse an explicit completion token. Do not guess from prose.
- Do not count the automation account's own posts. A reminder that lists task IDs and also contains a done-word (`完成`, `已完成`, `done`, `completed`, `finished`) is not a completion. Skip that author before token matching, or the next poll records the reminder as the completion post. Apply the same author skip to guard-list matching. The live guard-list path does not skip the automation account; it excludes only a factory-header guard prompt. Until that skip exists, a bot post that contains the marker plus a colon is stored as the list.
- Do not treat `未完成` as a done-word. Require a done-word that is not inside a negation.
- Do not use a word-boundary marker beside Chinese. `T01完成` has no boundary before `完`, so `\bT01\b` does not match it. Accept `完成 T01`, `Done T01`, `T01 完成`, and the joined form `T01完成`. The poller reads the thread and does not check for an @mention. Do not tell the assignee to mention the bot again; that mention does not create a tracker write.
- Process completion replies only while the event is open. A closed event ignores later replies. Do not reopen it from an employee chat turn, and do not rewrite the tracker sheet or state file from that turn. Roster-contributor scope is drafting-only, and a missing Drive writer grant is not a poller write.
- On that chat turn, acknowledge the named assignee reply as thread evidence and cite the post id. If those rows are already checked, say the check is already present and name the completion post when it is not the assignee's post. Do not claim the tracker changed. Do not clear or reopen other assignees' rows from that reply. Do not open an admin ticket only to replace completer identity when the status already matches the report.
- An operator repair of a false check must take the poller lock, clear only the false rows, and keep the event closed while every remaining task is still checked. Reopen only when a task must return to open, and only after the parser accepts the assignee's actual token and ignores automation posts. Reopening first lets the next poll send reminders and reparse unprocessed posts, including the repair reply.
- A chat reply is itself a thread post. Do not put a bare `T01`–`T09` token and a done-word in the same reply. A task title that contains `完成` counts as a done-word. The joined form `T01完成` does not match `\bT01\b`, but a nearby bare token plus any done-word in that message does. A later reopen will count that reply if the poller does not skip the automation account. Do not put the guard-list marker immediately before a colon in that reply. Name the marker, then tell the sender to add the colon, so the next poll cannot store the acknowledgement.
- Snapshot task title, stage, assignee user ID, and username into each event's tracker rows.
- Update the root checklist from durable task state; keep replies as evidence.
- A live poll rebuilds the root checklist and the daily reminder from the flow catalog. The visible `@username` comes from the catalog unless the open event task stores `assignee_username`. An event task that stores only `assignee_mm_user_id` does not change the mention, and the next poll restores the catalog name.
- Daily reminders use `event_id|local_date` dedupe and include only unresolved tasks. Treat the initial event root as that day's notification: initialize the reminder date at event creation so a post created after the reminder hour does not immediately generate a duplicate reminder.
- A closure/guard list or other consequential intake must use an explicit reply token and preserve the source post ID. A roster that lacks `留守名單` or `guard list` plus a colon is thread evidence only. Acknowledge every name and section exactly, bind a bare month/day to the date the prompt already named, and do not write the tracker or state from that chat turn.
- A conditional pre-list is not a confirmed guard list. Require a positive DGPA stop-work row before you store guard names or generate a merit draft. Do not generate the merit draft from the chat turn. The poller generates it after the stop-work row is positive and the guard list is stored.
- The live matcher keeps only the remainder of the marker line. A second line is dropped. Preserve every date and section line in the parser, or later name pairs are lost. Until that parser change is live, ask for one resubmit that puts every section on the marker line, and do not demonstrate that line in the bot post.
- Separate template/flow, event runs, and event-task status tables. Map Sheet fields by live headers, not fixed positions.
- Acquire a process-level single-instance lock before polling or mutating state. A concurrent scheduler tick should exit successfully and silently; it must not race the claim/recovery state machine or emit a false failure alert.

## Side-effect idempotency: pre-claim before publish

A local state write performed only after the first Mattermost post is insufficient. A crash after post acceptance but before Sheet/state commit can create a duplicate root on the next run.

Use a recoverable phase machine:

1. Persist `planned` event claim with deterministic event key and source receipt.
2. Search/read back the target channel for an existing bot post carrying that exact event key.
3. If absent, create the root post; immediately persist `thread_created` with post ID.
4. Upsert run/task tracker rows by stable keys; persist `tracker_synced`.
5. Only then mark `active`.
6. On retry, resume from the stored phase and read back before every side effect. Never blindly replay employee-facing posts/files.

For stronger guarantees, put the deterministic event key in both the post text/props and Sheet row so recovery can reconcile either source.

### Review-hardened recovery invariants

Independent review of a live incident-thread implementation exposed four reusable failure modes. Apply all of these, not only the basic pre-claim:

- **Separate event ID from lifecycle identity.** Store a stable storm/event fingerprint (year + sorted storm codes). Include the official date only for a government-only event with no storm code. Do not put the stop-work date in a named-storm fingerprint: an extra rest day would look like a new event and open a second root. Once an event is closed, suppress reactivation while that same typhoon remains active, including overlapping storm codes and a short date gap. A disjoint storm-code set is a new typhoon.
- **One thread per typhoon, including rest-day extensions.** A second producer, such as a rest-day monitor, must post with the stored `root_id` and must not print the notice. Keep that job's cron `deliver` and `failure_deliver` local. Channel delivery of stdout creates a second root even when the script also replies in-thread. A cleared rest-day episode means the stop ended on an earlier poll; reuse its thread id while the last stop date is inside the same-typhoon gap unless incoming storm codes are disjoint. Persist the adopted thread id before releasing the shared readiness lock, so the readiness job adopts that root instead of posting another one.
- **Never accept a root older than its durable claim.** Recovery must validate bot author, top-level/root status, exact deterministic marker, target channel, and `create_at >= claimed_at`. Using the claim timestamp only as a pagination stop condition can still select an old matching root.
- **Fail closed when absence cannot be proven.** Paginate until reaching the claim-time boundary or exhausting the channel. A bounded safety cap is fine, but hitting it must raise/alert and refuse to post—not return “not found” and create a possible duplicate.
- **Pre-claim recurring reminders too.** Persist `pending_reminder_date` before posting, include a deterministic marker such as `Reminder:<event_id>:<local_date>` in the raw post, and search the exact thread for that bot-authored marker before sending. After acceptance/readback, atomically clear the pending claim and set the completed reminder date. A final in-memory date update alone is not crash-idempotent.

Use the same claim → exact-marker readback → side effect → durable receipt pattern for every employee-facing prompt, file attachment, or generated-document post where duplicate delivery would matter.

## Assignee scope: this run versus future runs

The flow catalog is the source for a new event. The open event is a snapshot. Do not treat a checklist edit as durable until both surfaces that the request named are read back.

1. Resolve the person by exact Mattermost username or by the named role's current holder. Write that person's Mattermost user id and username. The catalog does not re-resolve a role on each poll, so a later role change does not move the task.
2. **This run only:** do not edit the catalog row. On the open event task, store both `assignee_username` and `assignee_mm_user_id`. Update only that event's task-status assignee cells, matched by `event_task_key`. Leave historical events with the same task id unchanged.
3. **This run and future runs:** do step 2, and also update the catalog assignee id and username for that task id. A catalog-only edit does not stick on an already open event, because the poll prefers a stored event username and otherwise keeps the snapshot taken at creation.
4. Take the same exclusive state lock the poller uses before writing the event file. The poller rewrites the whole state at the end of a run; an edit that races an in-memory load is dropped. A non-blocking lock means the overlapping tick skips. Do not wait by polling the lock in a loop that itself becomes a second writer.
5. Rebuild the root post from the same override function the poller uses, then read the post back. Require the new `@username` and the absence of the old mention. Read back the catalog row and the current-event status row by header name.
6. Keep merit-draft review mentions bound to the current task assignees (drafter and reviewer), not a hardcoded username. A catalog reassignment that leaves the draft prompt on the old reviewer still assigns the work to the wrong person.

## Generated reward/merit drafts

- Require government event confirmation plus a thread-confirmed recipient/guard list.
- Use historical announcements only as wording/policy precedent when the official current template is required.
- Generate a visibly marked `草稿 / Draft`; leave final number/signatures unresolved and state that it is not a formal award/personnel record.
- Name the current drafter and reviewer from the task assignees. Do not hardcode a former reviewer in the draft prompt.
- Reopen the DOCX structurally, render it, inspect every page, and upload only after QA succeeds.

## Safe verification route

Do not wrap the hazard runner in ad hoc `execute_code`/`subprocess.run()` loops to compile, test, or aggregate fixture JSON. That generic shape creates an unnecessary dangerous-command approval surface and obscures whether the requested operation is read-only or live.

For the PD One typhoon implementation, prefer the registered `pd_one_typhoon_automation` action dispatcher:

- `check` — compile and run the bounded unit-test suite;
- `preview` — one dry-run observation, optionally with an approved fixture path;
- `sweep` — run the fixed canonical low/high/land-warning/DGPA fixture matrix without shell or subprocess orchestration;
- `live` — production execution only with the exact live confirmation phrase and normal business authorization.

Use the MCP tool when exposed; otherwise use the same profile-local safe dispatcher with fixed arguments. If the tool is registered but absent from the current session schema, treat that as stale tool inventory—not permission to fall back to arbitrary code execution. A blocked or timed-out approval request must not be retried through another tool.

Verification receipts should state the action, case/failure counts, read-only/live-write flags, and whether shell/subprocess execution was used. An approval prompt proves only that execution was attempted; actual execution requires the tool result or side-effect receipt.

## Verification matrix

- Current official low-risk source → no event and no tracker rows.
- First high forecast timestamp → claim/watch only.
- Second distinct high timestamp → one event plan.
- Active land-warning code → immediate event plan.
- DGPA positive/negative/absent-row fixtures.
- Duplicate/retry after each phase boundary, plus concurrent-run lock contention.
- Completion reply, ambiguous reply, unauthorized close, daily-reminder dedupe, and same-day creation suppression.
- Reminder that lists task IDs plus a done-word → no completion. Joined `T01完成` on an open event → completion. Same token after close → no tracker write. Bot receipt that contains a bare task token and a done-word → not counted.
- Guard-list confirmation → draft generation, structural reopen, visual render. A roster without the marker is not stored. A bot acknowledgement that contains the marker plus a colon is not a confirmation; skip the automation account before guard-list matching.
- Cron-equivalent clean environment, scheduler readback, and failure delivery to admin lane.
- Extra rest day on a closed event, and a cleared rest-day episode inside the gap, both reuse the same root. A disjoint storm code opens one new thread. Rest-day stdout stays empty, and cron delivery stays local.
- Do not create a fake employee-facing incident merely to prove the high-risk path. Validate high-risk side effects with fixtures/mocks and record the first genuine qualifying event as the bounded live end-to-end canary.

# Case staleness and automation triage

Use this when asked to identify stale `Case` rows or diagnose why `Case_Updates` did not advance parent Case state.

## Stale Case heuristic

Treat a Case as likely stale when several of these are true:

- `CreatedAt` / created timestamp is old relative to current operations.
- Deadline / expected completion date is old or long past.
- Status is still open-ish (`New`, `In Progress`, `Pending`, etc.) rather than terminal (`Resolved`, `Completed`, `Canceled`).
- `Last Updated`, latest related `Case_Updates`, ActivityLog references, or other child activity are missing or old.
- No recent automation / queue / notification side effects are visible for the Case.

Report with concise evidence per Case: key, status, created date, deadline, last activity date, update count, owner/next responsible person when available, and why it qualifies. If the user asks to "highlight" stale rows, prefer a sorted high-confidence list first, then borderline rows. For larger reviews, write durable working artifacts together (`.md` summary for reading, `.csv` for spreadsheet triage, `.json` for reprocessing) and attach/report their paths. When reviewing candidates interactively in Discord, present about 10 candidates at a time as numbered compact blocks rather than Markdown tables, so the user can reply with simple selections like `cancel: 1,2,5` / `keep: 3,4`.

When retrying after an interrupted AppSheet write/test, first verify any row that may have been temporarily changed and restore expected state before continuing the read-only analysis. For transient AppSheet API timeouts during cleanup, retry the targeted repair with bounded backoff, then re-read the row and report the verified final value. AppSheet Data API writes can time out client-side after the server has already persisted the change; before retrying a write, do a minimal targeted `Find` for the affected key(s) and decide whether repair is still needed. If a cleanup script temporarily opens `Lookup[LookupID="Canceled"][Editable Roles]`, explicitly re-read that Lookup row after any timeout/interruption and restore it to `Case_Admin` through the Data API if it is blank; when the deployed app write times out, try the same `Lookup` edit through both deployed and prototype app API contexts, then verify via prototype `Find`.

## Case_Update automation verification path

When Case state should advance from new `Case_Updates` rows:

1. Verify bot wiring from the synced deployed definition:
   - `C_U_FlagProcess_Blank` (add event) should mark blank `Flag_Processed` rows as `ReadyToProcess`.
   - `Case_U_FlagProcess_ReadyToProcess` (update event) should run the Case update grouped action/process for rows where `Flag_Processed = "ReadyToProcess"`.
   - Confirm the parent update action and any enqueue/translation/notification actions are still present.
2. Pull fresh runtime/exportlog evidence for the relevant time window and row keys; definition truth only proves wiring, not execution.
3. Check the exact `Case_Updates` rows:
   - `Flag_Processed`
   - parent `Case` key/reference
   - created/updated timestamps
   - whether `Latest_CaseUpdateID` on the parent Case changed
4. Check queue side effects (`ProcessingQueue` or equivalent) by source row key/job type/status, but do not treat queue absence alone as proof until parent state and bot logs are checked.
5. Verify the parent Case is visible in the same app context/principal that the automation or API call uses. Old/filtered Cases may be readable in prototype but invisible to deployed app/security filters.

## Prototype vs deployed app pitfall

Rows added or edited through the prototype app API can appear in shared tables but may not trigger deployed-app bots. For live business effects, use the deployed app API when the row is visible there, or explicitly report that prototype-written rows are present but deployed automation did not execute.

For stale-Case cleanup specifically:

- Pull/read candidate `Case` and `Case_Updates` evidence from the prototype app because it bypasses deployed security filters.
- Write live `Case_Updates` through the deployed app so deployed automations fire.
- If re-submitting a previously prototype-written `Case_Update`, delete the old row first, then add through deployed with `Flag_Processed` omitted/blank so the deployed add/update bot chain owns the transition.
- Do not include blank JSON link placeholders such as `{\"Url\":\"\",\"LinkText\":\"\"}` in `Mattermost Link` / `Other Link` when re-adding through the deployed Data API; AppSheet may reject them as invalid `Url` values.
- If direct parent `Case[Status] = "Canceled"` edits are part of an approved stale-case cleanup, verify whether `Lookup[LookupID="Canceled"][Editable Roles]` makes the value valid for the Data API principal. If needed, temporarily set `Editable Roles` blank/open, perform only the targeted parent edits, then restore it to the original value (currently `Case_Admin`) in a `finally`/cleanup step and re-read `Lookup` before reporting success. Because a long cleanup script can time out while direct parent edits have actually persisted, final verification must include both: targeted deployed `Case` reads for `Status`, `Latest_CaseUpdateID`, and `Last Updated`, and a targeted `Lookup` read proving `Editable Roles` is back to `Case_Admin`.

When diagnosing a stuck `Case_Update`:

- Separate "bot exists" from "bot ran for this row".
- Separate "bot ran" from "parent Case update persisted".
- If the deployed app cannot see the parent Case because of security filters, parent update actions may fail or no-op even when child update rows exist. Current deployed `Case` security filter for app owner/server only includes rows created within `TODAY() - 365` or explicitly listed in `API_Target_Queue` with `TargetTable = "Case"`; stale Cases older than 365 days will be invisible unless queued/whitelisted.
- The grouped stale-Case update action can still advance `Case_Updates[Flag_Processed]` and enqueue translation/notification after the parent ref-actions no-op, so `AwaitingTranslation`/queue rows are not proof that `Case[Status]`, `Latest_CaseUpdateID`, or `Last Updated` persisted.
- Final claim should be based on persisted parent fields (`Case[Status]`, `Latest_CaseUpdateID`, `Last Updated`) plus runtime evidence, not just child row creation.

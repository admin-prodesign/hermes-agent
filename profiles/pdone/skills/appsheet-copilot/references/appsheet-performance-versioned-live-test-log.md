# AppSheet performance patch: versioned live-test and wiki log pattern

Use this reference when the user asks to optimize AppSheet sync/add/edit/workflow performance and wants live testing plus revert tracking.

## Durable workflow

1. **Baseline first, split by operation.** Pull fresh Performance Analyzer/exportlog windows separately for sync, add row, edit row, and relevant workflows. Keep raw `perf-raw-*.json` receipts.
2. **Inspect definition architecture before editing.** Read the deployed AppSheet definition and identify the exact action/process/event-filter bottleneck. Do not infer names from UI labels or old notes.
3. **Patch one significant architecture change per version.** Save as a new version, promote only after readback says valid/runnable/deployable, and record the previous stable version.
4. **Live-test with clean windows.** Always run at least one analyzer window after the stable-promotion timestamp. If the first window straddles the promotion or contains old in-flight work, label it residual/non-headline and run a later clean window.
5. **Use multiple receipts.** For each version keep: patch script or diff, save response, promote response, fresh definition readback, API/business-state readback when relevant, analyzer raw/report files, and revert instructions.
6. **Update the company wiki optimization page before reporting done.** The page should include version, architecture change, receipts, analyzer results, current assessment, and revert path. Ensure it stays linked from the main AppSheet wiki page.
7. **Close todos only after real verification.** Do not stop at a save/promotion receipt; the deliverable is performance evidence after deployment.

## Analyzer interpretation pitfalls

- A slow/failing row immediately after promotion may still be old in-flight automation. Check whether the timing trace invokes actions removed in the newly promoted version. If yes, call it residual and collect a later window.
- Also check `AppTemplateVersion`/client version in analyzer rows. If a post-promotion add/workflow row still reports an older app template version, it is old-client/runtime evidence and cannot prove the new definition path succeeded or failed; require a fresh current-version client/session for runtime proof.
- Report sync/add/edit separately; workflow failures can remain active even when user-facing add/edit operations improve.
- No detailed duration in the analyzer row is not proof of sub-10-second performance; state it as “no >10s detailed duration seen in this sample” and continue watching when sample size is small.
- For the <10s goal, flag near misses explicitly. Example: a successful sync at `12.720s` is still above target even with zero failures.

## 2026-06-12 example: defer attachment parent-cache refresh

Observed bottleneck: `ActivityLog_Attachments` adds spent 26–52 seconds, sometimes near 120 seconds, inside immediate parent refresh action `Action for Updated ActivityLog cached Attachments 2`, which re-read `ActivityLog_Attachments`/`ActivityLog` while the add was still in flight.

Patch shape:

- Remove the immediate parent-cache refresh action from `Process for ActivityLog_A_FlagProcess_0_New`.
- Leave the add path doing only the necessary queue/enqueue work.
- Defer/decouple parent `ActivityLog_Attachments_Cached` refresh from the user-facing attachment add path.

Verification shape:

- Definition readback for version `26.061144` showed the process nodes no longer included the parent-cache refresh action.
- A first post-promotion analyzer window still contained one stale `134s` add whose trace invoked the removed action; classify as residual/in-flight.
- A later clean window had add/edit rows with zero failures and no >10s detailed duration, while sync still had a `12.720s` near miss and thumbnail HeartBeat worker cancellations remained active.

Revert pattern:

- Fast revert: promote the previous stable version.
- File revert: restore the saved `before_loadapp_response.json` from the definition-edit receipt directory, save/promote as a new version, then rerun analyzer windows.

## 2026-06-13 example: use analyzer traces to find the next inline user-path action

When a patch improves one operation but not the overall target, immediately parse the `Properties.Performance` tree on the remaining >10s rows rather than declaring the architecture “done”. In this session, stable `26.061146` was valid/runnable/deployable and edit rows were under target, but fresh analyzer rows still showed:

- sync: successful but still over 10s, dominated by table reads such as `ActivityLog`, `Case_Updates`, `Case`, `Lookup`, and attachment/session tables;
- add row: successful `ActivityLog` adds still at ~98–124s;
- workflow: `HeartBeat` cancellations still present.

The decisive add-row trace showed `Process for ActivityLog_FlagProcess_0_New` → `AL_Group_EnqueueInitialWork` → `AL_SetFlag_ReadyToProcess`, with `ActivityLog_Attachments_Cached` evaluation taking roughly 107s. That made the next safe bounded candidate to defer/remove the immediate ready-flag action from the user-facing add path while preserving the durable queue/wake mechanism.

Operational lesson:

1. After each promoted version, run a clean post-promotion analyzer window and parse nested timing nodes for each remaining >10s row.
2. Distinguish “definition readback good” from “performance goal met”; valid/runnable/deployable only proves the app can run.
3. If a trace still enters an inline user-facing process that performs large cached-list evaluation, treat that exact action as the next bounded architecture candidate.
4. Keep reporting operation-specific status: edit may be solved while sync/add remain above target.
5. Do not claim success until sync/add/edit all have clean sub-10s evidence or a blocker requiring user input is identified.

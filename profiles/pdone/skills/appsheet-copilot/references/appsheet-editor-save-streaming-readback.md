# AppSheet editor save: streaming readback and runtime verification

Use this when an AppSheet `/api/saveapp` change is small but the app JSON is huge, causing `/api/loadApp` or `/api/saveapp` clients to hang while downloading the full returned app.

## Pattern

1. Make the smallest possible JSON mutation from the freshest available definition.
   - For bot/event enablement, patch only the target `Disabled` fields.
   - For new physical-table views, patch only the target `Presentation.Controls[]` / `Presentation.MenuEntries[]` and needed `Version` marker.
   - Save a compact pre-save summary listing every touched object and before/after value.
2. Post to `/api/saveapp` with `validate=true` when practical. For very large UI-only rebases where validation streaming is the blocker, a bounded `validate=false` save can be followed immediately by fresh `/api/loadApp` validation/readback; do not report success until readback shows `IsValid`/`IsRunnable` and the intended objects.
3. If the foreground call times out while waiting for the full response body, do **not** assume failure.
   - AppSheet may have accepted the write and then spent minutes streaming the full app JSON back.
   - Start a streaming readback instead of blindly retrying the same stale payload.
4. Verify via streaming `/api/loadApp`:
   - Use `stream=True` / chunked reads, or an authenticated browser `fetch('/api/loadApp/<app_id>')` readback when browser cookies are the writable session.
   - Stop once the target object names and surrounding JSON snippets are found.
   - Capture snippets showing target object state, `IsValid:true`, `IsRunnable:true`, `LastModified`, and version evidence.
5. If a later retry returns HTTP `409 Conflict`, treat it as a rebase signal, not proof that the first save failed.
   - Check whether the first save already landed via streaming readback.
   - If not landed, rebase the tiny mutation onto the current returned/live app before retrying.
   - `409` responses may include a full `App` JSON payload that already has some of the attempted changes or a newer editor `Version`; use that payload or a fresh `loadApp` as the rebase base instead of reposting the stale request body.
6. Verify final business state, not only definition state.
   - For cached-column bot work, run or wait for the enqueue + worker path and read back the parent cached column.
   - For schema/UX work, verify `DataSets`, `DataSchemas`, `Presentation.Controls`, `Presentation.MenuEntries`, key/label/ref qualifiers, and `IsRunnable` from fresh `loadApp`.
   - Record queue status (`Queued` → `Done`), retry count, last error, and parent field values where runtime workers are involved.

## Example: cached Case Update parent sync

Definition objects to verify after enabling:

- `AppBots / Case Update Added - Enqueue Parent Sync` → `Disabled:false`, `IsValid:true`
- `AppEvents / Case Update Added - Enqueue Parent Sync` → `Disabled:false`
- `AppBots / HeartBeat_PQ_CaseUpdateParentSync` → `Disabled:false`, `IsValid:true`
- `AppEvents / HeartBeat_PQ_CaseUpdateParentSync` → `Disabled:false`

Runtime proof sequence:

1. Pick a real `Case_Updates` row whose parent `Case[Case_Updates_Cached]` is blank or missing that update.
2. Run AppSheet Data API action `Case_Updates_EnqueueParentSync` on the `CaseUpdateID`.
3. Read back `ProcessingQueue` for `JobType="case_update_parent_sync"` and `SourceRowKey=<CaseUpdateID>`.
4. Run or wait for `PQ_Process_CaseUpdateParentSync` on the `QueueID`.
5. Read back:
   - `ProcessingQueue[Status] = "Done"`
   - `ProcessingQueue[RetryCount] = 0`
   - `ProcessingQueue[LastError]` blank
   - parent `Case[Latest_CaseUpdateID] = <CaseUpdateID>`
   - parent `Case[Case_Updates_Cached]` contains `<CaseUpdateID>`

## Pitfalls

- Do not report success from `/api/saveapp` request completion alone; AppSheet can return very large bodies and client timeouts can obscure whether the server committed the edit.
- Do not repeatedly POST a stale full-app payload after a timeout. First do streaming readback; then rebase if necessary.
- Browser/editor sessions may be logged into a different account than the cookie profile used for API calls. If the UI shows 404/no access but API cookies can read/save, keep the contexts separate in the report.
- ActivityLog attachment cache may already be enabled through a direct action chain. Distinguish “definition is enabled” from “runtime parent cache equals related attachments” with a parent row readback.

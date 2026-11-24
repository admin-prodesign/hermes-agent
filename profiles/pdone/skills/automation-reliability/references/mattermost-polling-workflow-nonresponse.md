# Debugging Mattermost polling workflow non-response

Use when a cron/API polling workflow appears silent in Mattermost even though it is installed and running.

## Pattern learned
A scheduled Mattermost runner can correctly detect a post and still intentionally avoid replying when its state machine is waiting for a configured trigger phrase or workflow gate. Do not assume no response means the cron failed.

## Verification sequence
1. Verify the installed schedule and recent log receipt for the runner.
2. Fetch or reconstruct the target post/thread by post ID, not by channel browsing alone.
3. Check these against the runner constants/config:
   - target channel id/name
   - bot user id ignored by scanner
   - root post vs thread reply handling
   - ECRN/workflow identifier regex or equivalent intake detector
   - activation/start regex or other state-machine gate
   - nudge throttle window and already-used state slots
4. Run the runner in dry-run or diagnostic mode against the target thread when possible. Compare normal dry-run and force-nudge/force-check modes to distinguish:
   - not detected
   - detected but waiting for activation/check-cleared
   - detected but outside throttle slot
   - detected but already nudged
   - detected but blocked by approver/permission mapping
5. Inspect persisted state and structured logs for the exact root post id. A result such as `waiting_for_checks_cleared` is a successful observation, not a failure.
6. Report the reason using receipts: post id, channel match, detected workflow id, cron/log result, and the exact gate that prevented a reply.

## User-facing remediation options
- If the current design is correct, tell the user the trigger phrase/action needed to advance the workflow.
- If silence is confusing, propose or implement a lightweight intake acknowledgement that posts once per new root thread, e.g. "received; reply `開始簽核` / `checks cleared` after checks are complete." Guard it with state so it does not spam.
- If the workflow should start immediately on root-post creation, update the activation gate deliberately and document the changed behavior.

## Pitfalls
- Do not run a live `--send --force-nudge` just to test unless the user has approved the side effect; use dry-run diagnostics first.
- Do not disclose broad unrelated Mattermost history. Fetch only the linked post/thread and the runner's own bounded logs/state needed for diagnosis.
- For channel/group answers, keep the explanation bilingual and concise, with receipts first.

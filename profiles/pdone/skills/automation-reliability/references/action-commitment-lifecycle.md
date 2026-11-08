# Action commitment lifecycle

Use this reference when an agent reply creates a user-visible promise: “I will…”, “done”, “scheduled”, “live”, “created”, “sent”, “synced”, “I’ll check later”, or similar.

## Principle

Treat visible action claims as part of the system state. The agent should either do the action and verify it before replying, or clearly say what is pending/blocked. A plausible plan is not a completed action.

## Commitment receipt checklist

For each action claim, capture at least one durable receipt plus a verification readback when possible:

- Message/send: target channel/thread, post ID, API response, and readback of created post when available.
- File/artifact: absolute path or storage URL, existence/readback check, attachment/upload receipt if claiming delivery.
- Sheet/database write: spreadsheet/table, row count or row IDs, status cell/state row, readback of written range/record.
- Cron/scheduled follow-up: job ID, schedule/timezone, delete/expiry behavior, delivery target, and `hermes/openclaw cron list` or job file readback.
- Recurring automation: idempotency key/dedupe strategy, bounded log path, no-overlap lock, status state, first-run/dry-run result, failure alert/queue path.
- Code/config change: changed paths, tests/checks run, commit hash if repo backup is expected.

## Reply rules

- Say “done/live/scheduled” only after the receipt exists.
- Say “pending/blocked” when approval, credential, permission, runtime, or user input is still needed.
- Say “I created a follow-up job” only after the job exists and has been read back.
- If no automatic follow-up exists, say so explicitly rather than relying on memory.
- For high-noise channels, keep evidence concise and audience-appropriate; admin users can receive paths/commit hashes, regular users usually need only a link/status.

## Auditor pattern

A longer-term prevention layer should scan recent agent replies for commitment language and verify matching receipts:

1. Extract candidate commitments from user-visible replies.
2. Classify type: send, write, file/artifact, scheduled follow-up, recurring automation, code/config change.
3. Locate expected receipt in logs, cron/jobs, status rows, state files, commits, or API readback.
4. Alert only on missing receipt, failed first run, stale status, or mismatch between claimed and verified outcome.
5. Store seen fingerprints so alerts are not repeated.

This complements prompt rules: prompt rules reduce false claims; the auditor catches remaining mismatches so humans do not need to manually verify every promise.

# Mattermost Auto-Reply Recovery Rails

Use this when Andy asks why PD One did not automatically reply to a Mattermost DM/thread after a gateway restart, helper timeout, or queue stall, and the question is not just a one-off manual catch-up.

## Durable helper surfaces

The active control plane is Hermes profile `pdone`; inspect these before assuming the gateway must be restarted:

- Gateway/source logs: `/home/prodesign/.hermes/profiles/pdone/logs/{gateway,agent}.log`
- Review scanner and reconciliation: `/home/prodesign/.hermes/profiles/pdone/tools/mattermost_review_log.py` and `review_log_source_collector.py`
- Reply-quality supervisor: `/home/prodesign/.hermes/scripts/pd_one_quality_supervisor.py`, with state under `/home/prodesign/.hermes/supervisor/`
- Mattermost missed-mention REST backfill is built into the active Hermes adapter; verify its log receipts and exact post/thread readback.
- The old `legacy-openclaw/workspace/tools/pd_one_missed_reply_replayer.py` and its units are historical references only unless Andy explicitly asks to inspect/repair the legacy plane.

A review row can race an in-flight turn: the first scan may correctly report no reply, then reconciliation may see a temporary heartbeat/progress bubble. A progress bubble is liveness evidence, not proof of a completed answer; inspect the eventual final post before closing the quality finding.

## Recovery sequence

1. Read the exact Mattermost thread/post by REST, not from the pasted permalink alone. Capture `channel_id`, `root_id`, user post id/time, and any later bot post id/time.
2. Check whether the post should route:
   - DM/group DM to PD One,
   - explicit bot mention or bot-id mention,
   - configured `requireMention: false` channel,
   - or a follow-up in a thread where PD One had already participated.
3. Check whether there is already a later PD One bot reply in the same thread/conversation. If yes, report it as delayed/handled rather than replaying.
4. Inspect active Hermes gateway/agent logs, the review scanner/source collector, and the quality-supervisor state. Treat helper failures as execution-environment issues first; do not restart the Hermes gateway merely because a scanner or collector failed.
5. Distinguish three outcomes: no bot post, temporary heartbeat/progress only, or a final employee-visible answer. Do not close a finding from temporary-progress evidence, and do not replay blindly.
6. If a corrective reply is authorized, post it in the original Mattermost thread/root and verify the exact post readback. External sends remain approval-gated.
7. After code/script changes, run targeted tests and verify the next normal scanner/supervisor tick. Gateway code changes are only active after an explicitly approved restart and live canary.

## Wiki/runbook promotion expectation

When the recovery required custom OpenClaw scripts or durable logic changes, update a high-level company wiki/system-map page in addition to source/runbook changes. The wiki does not need every low-level code diff, but it should expose the operational rail names, paths, and what they protect against so future admins can discover them.

Recommended wiki targets:

- Canonical vault: `/home/prodesign/.hermes/company-wiki/main`
- System map page: `syntheses/pd-one-system-map.md`
- Add a dated `log.md` entry for important PD One Mattermost recovery rail updates.

After wiki edits, run the wiki lint/export path and push the private mirror. Then refresh Hermes/OpenClaw backups as applicable.

## Busy-session presence-check fast path

Standalone liveness checks such as `PD ONE 你在嗎?請回覆我`, `are you there?`, or `ping` should receive an immediate deterministic acknowledgment while a turn is busy. They must not interrupt the running agent, enter the pending-turn FIFO, consume a later model turn, or suppress the normal busy acknowledgment for a substantive follow-up. Presence wording followed by real work (for example, `你在嗎？請幫我檢查這份文件`) must stay on the normal busy input path. The active Hermes implementation is in `gateway/run.py::_is_simple_presence_check` and `_handle_active_session_busy_message`; regression coverage is in `tests/gateway/test_busy_session_ack.py`. Code changes remain inactive until an explicitly approved PD One gateway restart and live canary.

## Pitfalls

- Do not equate “gateway restarted” with “reply was impossible”; scanner races, a stuck turn, or structured-content handling bugs can also explain a missing or delayed answer.
- Do not trust a broad scanner result when Andy provides a concrete permalink. Inspect the exact post/thread and matching active Hermes session/log evidence.
- Do not count typing indicators, long-running heartbeat posts, or temporary progress bubbles as a completed employee-visible answer.
- Do not replay or send a corrective response blindly. Respect routing/approval policy and require same-thread evidence.
- Do not leave durable Mattermost recovery fixes only in source code. Update the PD One admin skill/reference and company wiki/system map when the operational rail materially changes.

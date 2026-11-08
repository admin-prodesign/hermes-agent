# Missed message replay for chat/agent automations

Use this pattern when a chat/agent bridge accepted and routed a user's message, but the agent failed before delivering a reply. This is not a generic resend queue; it is a conservative recovery lane for messages already proven to have triggered the agent.

## When to use

- Logs show a routed chat lane/session for the original message.
- The failure happened before a user-visible reply was delivered.
- The target chat thread can be queried to verify whether the bot already replied.
- Replaying a reply is acceptable for the channel and agent.

## Required safety gates

1. **Evidence-based candidate detection**
   - Derive candidates from runtime evidence: routed session/lane, channel/thread ids, agent id, and a pre-reply failure marker.
   - Do not infer missed replies solely from “no bot post” because many messages may not require a reply.

2. **Thread readback before replay**
   - Fetch the original root post/thread from the chat API.
   - Skip deleted/missing posts.
   - Skip if the bot already replied anywhere in the thread, or after the relevant timestamp if the platform supports ordering cleanly.

3. **Idempotent state**
   - Key replay state by the original platform root message id.
   - Store the replayed reply post id, channel id, agent id, timestamp, and permalink.
   - Re-check the thread immediately before posting to prevent race duplicates.

4. **Audit without secrets**
   - Log scan counts, skip reasons, candidate metadata, replay result, and post ids.
   - Never log bot tokens, gateway tokens, Authorization headers, or raw env files.

5. **Reply generation context**
   - Generate the reply as the same agent that was originally routed when possible.
   - Prompt should say this is a missed-message replay, include original author/channel/time/message, and instruct the agent to apologize briefly and answer the original request.
   - Do not mention stack traces or internal module/runtime errors unless the user asked for diagnostics.

6. **Output-shape verification**
   - For CLI/API agent calls, probe or inspect the JSON response shape before live posting.
   - Extract the assistant-visible text, not run ids or metadata. For OpenClaw `agent --json`, visible text may be under `result.payloads[].text` or a final-assistant field, while top-level `runId` is not the reply.

## Operationalization

- Start with `scan` and dry-run `replay` modes.
- Add built-in self-tests for log parsing, bot-reply detection, prompt construction, session id safety, and response extraction.
- Install as a quiet recurring oneshot timer only after a one-shot run succeeds.
- Use a small limit per run to avoid posting a burst after a long outage.
- Keep audit logs local or ignored from backup if they can contain user message snippets.

## Mattermost/OpenClaw implementation note

A proven implementation exists on `nemo` at:

- Script: `/home/prodesign/.openclaw/workspace/tools/pd_one_missed_reply_replayer.py`
- User timer: `pd-one-missed-reply-replayer.timer`
- State: `/home/prodesign/.openclaw/workspace/data/pd-one-missed-replies/state.json`
- Runbook: `/home/prodesign/.openclaw/workspace/docs/runbooks/pd-one-missed-reply-replayer.md`

It scans OpenClaw log lanes of the form `session:agent:<agent>:mattermost:group:<channel_id>:thread:<root_id>`, verifies no `pdone` reply exists in Mattermost, then uses the routed agent to post one reply back into the original thread. Detector evidence should include both direct pre-reply lane errors and the final stuck-session watchdog abort outcome (`stuck session recovery outcome: status=aborted action=abort_embedded_run activeWorkKind=embedded_run`); generic stuck-session warnings alone are not enough evidence to replay.
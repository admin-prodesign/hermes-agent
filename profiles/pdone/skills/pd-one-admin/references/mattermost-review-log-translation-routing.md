# Mattermost review-log translation routing pitfall

## Trigger
Use this when a PD One Mattermost user report says the bot echoed an English translation, failed to perform the requested action, or failed to attach a generated artifact after a Chinese request.

## Symptom pattern
- User asks PD One in Chinese to perform an action, especially create/download/attach an XLSX or other file.
- PD One replies with an English translation of the request, or a follow-up like `Where is it? Download.` instead of doing the task.
- No generated file or Mattermost `file_ids` receipt exists for the expected artifact.

## Debug path
1. Inspect the relevant OpenClaw/Codex utility-agent session around the Mattermost timestamp.
2. Look for prompts that start with audit-log translation instructions such as:
   - `You are translating one audit-log request_summary...`
   - `You are translating one audit-log reply_summary...`
3. Confirm whether the real user request appears inside quoted audit content rather than as the current task.
4. If the session output is just a translated summary, treat the failure as routing/audit-enrichment leakage, not artifact-generation failure.
5. Separately inspect Mattermost delivery only if the generation path actually produced a media URL or file and called the Mattermost send path.

## Root-cause distinction
- If the request was handled by `tools/mattermost_review_log.py` translation enrichment via `summarizer --model openclaw/utility-agent`, the utility-agent can create visible channel-style sessions that look like normal replies. This can turn audit translations into user-visible answers.
- Mattermost attachment delivery is a different path: it should receive `mediaUrl`, upload with `uploadMattermostFile`, and create a post with non-empty `file_ids`. If those calls never happened, do not frame the incident as a Mattermost upload failure.

## Fix direction
- Keep review-log translation local/non-deliverable. Prefer disabling live translation enrichment (`REVIEW_LOG_TRANSLATION=0`) or routing it through a non-channel provider unless OpenClaw exposes a guaranteed no-delivery utility mode.
- Add a guard that audit-log translation prompts cannot be sent as visible Mattermost/Telegram/Discord replies.
- Regression probe: a Chinese Mattermost request to create and attach an XLSX must either produce a file receipt with non-empty `file_ids` or give an explicit inability response; it must never return only an English translation.

## Reporting guidance
For Andy/admin reports, distinguish clearly between:
- action path not reached (routing/audit translation leakage), and
- action reached but delivery failed (Mattermost file upload/post failure).

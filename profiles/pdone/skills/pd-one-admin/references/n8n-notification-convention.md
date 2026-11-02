# n8n Common Notification Convention

Use this when administering PD One/OpenClaw n8n workflows that notify users, admins, or channels.

## Default rule

New or revised n8n workflows should route user/admin-facing notifications through the shared/common notification workflow instead of embedding direct Discord, Mattermost, email, or other channel-send nodes in each workflow.

## Payload shape

Call the approved webhook or Execute Workflow entrypoint with a normalized payload containing at least:

```json
{
  "severity": "info|success|warning|error",
  "title": "short notification title",
  "message": "human-readable body",
  "source_workflow": "workflow name or id",
  "run_id": "n8n execution id or generated run id",
  "dedupe_key": "stable duplicate-suppression key"
}
```

Optional fields can include `target`, `thread`, `details_url`, or workflow-specific context.

## Why

Centralizing notification delivery keeps channel credentials and formatting policy in one workflow, reduces duplicate alert logic, and makes smoke tests meaningful: a successful smoke notification confirms the shared notification path is available from the user-visible side.

## Pitfalls

- Do not hardcode secret webhook suffixes or credentials in skill files, wiki pages, reports, or chat output.
- Do not add direct channel credential nodes unless Andy explicitly asks for a workflow-specific exception.
- For frequent recurring workflows, still apply alert-spam controls: retries, consecutive-failure thresholds, time-window thresholds, or error budgets before sending external alerts.
- Log every failure attempt durably even when suppressing noisy notifications.

## Source-of-truth locations in OpenClaw workspace

- `/home/prodesign/.openclaw/workspace/skills/n8n-workflow-automation/SKILL.md`
- `/home/prodesign/.openclaw/workspace/skills/n8n-Automation/SKILL.md`
- `/home/prodesign/.openclaw/workspace/out/wiki-mirror/syntheses/n8n-automation-support.md`

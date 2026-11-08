# PD One admin alert routing after Discord removal

Use when Andy asks to verify or change PD One/OpenClaw alerts that formerly went to Discord or were accidentally delivered to Telegram. Current operating target: **PD One Admin Mattermost channel** `5gmqtwqf7bde3cyihas79xi8ie` (`channel:5gmqtwqf7bde3cyihas79xi8ie`). PD One should not send admin/operator alerts or employee-originated approval requests to Discord or Telegram unless Andy explicitly re-enables that specific path.

## Inventory checklist

Check all of these; do not stop at `openclaw.json`:

1. OpenClaw config and channel split:
   - `/home/prodesign/.openclaw/openclaw.json`
   - `openclaw config validate --json`
2. Workspace scripts and systemd units:
   - `workspace/ops/systemd/user/*.service`
   - `workspace/tools/**/*.sh`, `workspace/tools/**/*.py`
   - `workspace/projects/**/*.py`
   - search for `--channel discord`, `ALERT_CHANNEL=discord`, `NOTIFY_CHANNEL=discord`, `discord.com/api`, old Discord channel IDs, and `Send Discord`.
3. Hermes cron jobs that run PD One monitors:
   - If the script now sends directly to PD One Admin Mattermost, set the cron delivery to `local` so Hermes does not additionally announce to Discord.
4. n8n workflows:
   - Load `.env.n8n` from `/home/prodesign/.openclaw/workspace` without printing secrets.
   - List active workflows and inspect full workflow JSON for `discord.com/api`, `Send Discord`, old Discord channel IDs, or direct Discord credentials.

## Approval-request routing rule

Employee-originated Mattermost approval requests should surface in the PD One Admin Mattermost channel, even if Andy later responds from Telegram because a stale/misrouted alert reached him there. Treat Andy's Telegram approval as authorization for the specific request, but post the approval record/receipt into the Admin Mattermost channel and correct the routing path so future requests do not depend on Telegram. Use the Mattermost Admin channel id `5gmqtwqf7bde3cyihas79xi8ie`; do not silently continue the Telegram approval loop.

## Reroute pattern

For OpenClaw CLI sends, use:

```bash
openclaw message send \
  --channel mattermost \
  --target channel:5gmqtwqf7bde3cyihas79xi8ie \
  --message "..."
```

Use dry-run before claiming delivery is wired:

```bash
openclaw message send \
  --channel mattermost \
  --target channel:5gmqtwqf7bde3cyihas79xi8ie \
  --message 'PD One alert routing dry-run verification' \
  --dry-run --json
```

For systemd env defaults, prefer both variables where applicable:

```ini
Environment=ALERT_CHANNEL=mattermost ALERT_TARGET=channel:5gmqtwqf7bde3cyihas79xi8ie
Environment=NOTIFY_CHANNEL=mattermost NOTIFY_TARGET=channel:5gmqtwqf7bde3cyihas79xi8ie
```

After editing unit files, run `systemctl --user daemon-reload` and inspect `systemctl --user cat <unit>`.

## n8n reroute pattern

If an active workflow has an HTTP Request node posting to Discord:

1. Back up the live workflow JSON under `workspace/backups/n8n-workflows/<timestamp>/` before updating.
2. Replace the HTTP Request Discord node with `n8n-nodes-base.mattermost` using the PD One bot Mattermost credential.
3. Set `channelId` to `5gmqtwqf7bde3cyihas79xi8ie` and message to the workflow's existing content expression, usually `={{ $json.content }}`.
4. Rename node and connection references from `Send Discord ...` to `Send Mattermost ...`; n8n connections can retain stale node names even after the node itself is renamed, and searches will keep flagging Discord until connection references are updated too.
5. Re-fetch the live workflow and verify active workflows have zero Discord alert refs.

Verification query shape:

```bash
cd /home/prodesign/.openclaw/workspace
set -a; . ./.env.n8n; set +a
python3 - <<'PY'
import json, os, subprocess
api=os.environ['N8N_API_URL'].rstrip('/'); key=os.environ['N8N_API_KEY']
raw=subprocess.check_output(['curl','-fsS','-H',f'X-N8N-API-KEY: {key}',f'{api}/workflows?limit=100'])
left=[]
for w in json.loads(raw).get('data',[]):
    if not w.get('active'):
        continue
    full=json.loads(subprocess.check_output(['curl','-fsS','-H',f'X-N8N-API-KEY: {key}',f'{api}/workflows/{w["id"]}']))
    txt=json.dumps(full, ensure_ascii=False).lower()
    if any(x in txt for x in ['discord.com/api','send discord','1500011194109530233','1503946606985216090']):
        left.append((full['id'], full['name']))
print('active_n8n_discord_alert_refs=', len(left))
for item in left:
    print(*item)
PY
```

## Verification and commit discipline

- Validate OpenClaw config.
- Dry-run the Mattermost send target.
- Compile/check changed Python files with `python3 -m py_compile` where applicable.
- Verify `openclaw-gateway.service` is active/running; if a health endpoint probe times out, do not repeatedly retry the same hung probe. Use bounded service status and other verification instead unless a restart has been approved or the gateway is demonstrably unresponsive.
- Commit a narrow OpenClaw backup containing only routing changes, workflow backups/payloads, and matching docs/runbooks. Avoid staging unrelated generated wiki/AppSheet churn.
- Run the Hermes backup script after skill/Hermes-side cron or script changes.

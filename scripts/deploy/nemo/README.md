# Nemo push deploy

A merge to `main` reaches nemo in seconds instead of waiting for a poll. Nemo still
decides when the merge goes live: it builds the exact merged SHA, waits until every
Hermes profile is idle, cuts over, and rolls back on its own if health fails.

```
merge to main
  └─ .github/workflows/nemo-deploy.yml
       joins the tailnet as an ephemeral tag:ci node, POSTs a signed {sha, ref, repository}
  └─ nemo: hermes-deploy-listener.service      (verifies, then writes deploy/queue/<sha>.json)
  └─ nemo: hermes-deploy.path → hermes-deploy.service  (oneshot worker, autodeploy.py)
       1. refuses a SHA that is not on origin/main, or is older than the live SHA
       2. classifies the diff: noop / skills / restart          (changes.py)
       3. prunes old releases, then build.sh --sha <sha>
       4. restart: cutover.sh  (idle gate → swap → unit rewrite → restart → /health → rollback)
          noop/skills: cutover.sh without gate or restart, then sync bundled skills
       5. prunes again (keeps current, its rollback target, and the running build)
  └─ nemo: hermes-deploy-drift.timer  (hourly: live files vs the deployed SHA)
```

The listener only verifies and queues. It never builds, restarts, or reads profile
state. Every unit runs code from `releases/current`, so a merged change to this
directory goes live with the release that carries it. A worker change therefore
first runs on the deploy *after* the one that shipped it.

## What happens to a deploy

| Diff touches | Mode | Restart | Idle gate |
| --- | --- | --- | --- |
| only `website/`, `tests/`, `tests-js/`, `.github/`, `contributors/`, `AGENTS.md`, root `README*/CONTRIBUTING*/SECURITY*.md` | `noop` | no | no |
| the above plus `skills/` | `skills` | no | no |
| anything else (Python, prompts, locales, dependencies, `optional-skills/`, `SOUL.md`), or an unreadable diff | `restart` | yes | yes |

- **Idle gate.** `cutover.sh` waits until pdone and pdneo have no turn or compression
  lease, no live goal, and no message newer than 90 s (`gate.py`). It waits up to 6 h;
  if the profiles are still busy it exits 75, nothing changes, and the request goes
  back on the queue to wait again. You get a `waiting` alert each time.
- **Rollback.** If systemd or `/health` (gateway `:8642`, dashboard `:9119`) is not
  healthy within 90 s of the restart, `cutover.sh` restores the previous symlink,
  unit files, and configs from `upgrade-audits/<build>/` and restarts again.
- **Skills without restart.** The release's bundled skills are synced into each
  profile's `skills/` with the usual `sync_skills` rules (user-edited and
  curator-pruned skills are left alone). The gateway reads a skill by name at call
  time. A newly added or removed skill shows in the slash-command list after
  `/reload-skills`. The processes keep running the previous release directory, which
  `releases/.running` protects from pruning until the next restart deploy.
- **Retention.** Nemo's disk is nearly full. Before a build, only `current` and the
  running build stay. After a deploy, `current`, its rollback target, and the running
  build stay. That's 2 releases, or 3 right after a no-restart deploy. A build that rolled back
  is deleted; its audit directory stays. The worker refuses to build with less than
  2 GB free.
- **Queue.** Only the newest request matters. Older queued SHAs are dropped as
  superseded. A request that arrives during a gate wait is deployed after it.
- **Status.** `<home>/deploy/status.json` is the last outcome and
  `<home>/deploy/history.jsonl` keeps every one: `deployed`, `live` (already
  current), `waiting`, `failed`, or `rejected`.

## Drift check

`hermes-deploy-drift.timer` runs hourly. It alerts when:

- a tracked file in the live release differs from `git ls-tree <deployed sha>`, or is
  missing (git blob hashes, so mode-only noise does not count);
- an untracked `.py` or `.sh` file sits in the release outside build output (`.venv`,
  `.python`, `node_modules`, `web_dist`, `ui-tui/dist`, `__pycache__`);
- a systemd unit points at a release other than `current` or the running build;
- `main` has been ahead of the live SHA for more than 2 h with nothing queued.

## One-time setup

Do these once, in order. Nothing in this PR changes nemo until step 3.

### 1. Tailscale

1. **Tags.** In the tailnet policy file, own the two tags and grant CI only the
   listener port. Keep any rules you already have, but make sure no `*` rule gives
   `tag:ci` wider access:

   ```jsonc
   "tagOwners": {
     "tag:ci":   ["autogroup:admin"],
     "tag:nemo": ["autogroup:admin"],
   },
   "grants": [
     { "src": ["tag:ci"], "dst": ["tag:nemo"], "ip": ["tcp:8443"] },
   ],
   ```

   Tag nemo with `tag:nemo` (Machines → nemo → Edit ACL tags). To leave nemo
   untagged instead, define `"hosts": {"nemo": "<nemo tailnet IP>"}` and use
   `"dst": ["nemo"]`.
2. **OAuth client.** Settings → OAuth clients → Generate: scope **Auth Keys → Write**,
   tag `tag:ci`. Nodes it creates are ephemeral and disappear after the job.
3. **HTTPS.** DNS → enable MagicDNS and HTTPS Certificates, then on nemo:

   ```bash
   sudo tailscale serve --bg --https=8443 http://127.0.0.1:8765
   ```

   The deploy URL is `https://<nemo machine name>.<tailnet>.ts.net:8443/deploy`.
   Pick another port if 8443 is taken, and update the grant to match.

Instead of `tailscale serve`, you can bind the listener to nemo's tailnet address
(`--bind <100.x.y.z>`, plain HTTP inside WireGuard) and add
`--require-tailscale-tag tag:ci`. The listener then also checks the caller's tag with
`tailscale whois`. Behind `tailscale serve` the caller appears as loopback, so that
check can't run there. The HMAC signature is required either way.

### 2. Ship this code to nemo the existing way

Build and cut over a `main` SHA that contains this directory with the hand flow in
`website/docs/user-guide/pd-one-safe-ops.md` (`build.sh`, then `cutover.sh`).

### 3. Install the units on nemo

From the deployed release, as the user that owns the Hermes home:

```bash
cd ~/.hermes/releases/current
loginctl enable-linger "$USER"     # user units keep running after logout
bash scripts/deploy/nemo/install_autodeploy.sh install \
  --mirror /path/to/hermes-agent.git \
  --alert-script ~/.hermes/deploy/alert.sh     # optional, see below
```

- `--dry-run` prints the five units without writing anything.
- On the first run the installer creates `~/.hermes/deploy/webhook-secret` (0600, a
  random 64-character value). It never prints the value.
- If the Hermes gateway units are system units (`/etc/systemd/system`), run the
  installer with `sudo` and `--scope system --run-as <hermes user>`. The worker
  rewrites and restarts those units, so give it the same identity the hand cutover
  uses (`--worker-user`, which defaults to `--run-as`).
- `--mirror` is the bare mirror `build.sh` already uses. It needs working fetch
  credentials for the private repo.

The alert script is called as `alert.sh "<subject>"` with JSON details on stdin.
For example, posting to a Mattermost incoming webhook whose URL is in a 0600 file:

```bash
#!/usr/bin/env bash
jq -Rs --arg s "$1" '{text: ("**" + $s + "**\n" + .)}' \
  | curl -fsS -H 'Content-Type: application/json' -d @- "$(cat ~/.hermes/deploy/mattermost-hook)"
```

Without an alert script, failures still show in `journalctl` and `systemctl --failed`.

### 4. GitHub repository secrets

Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
| --- | --- |
| `TS_OAUTH_CLIENT_ID` | OAuth client ID from step 1.2 |
| `TS_OAUTH_SECRET` | OAuth client secret from step 1.2 |
| `NEMO_DEPLOY_URL` | `https://<nemo>.<tailnet>.ts.net:8443/deploy` |
| `NEMO_DEPLOY_HMAC_SECRET` | contents of `~/.hermes/deploy/webhook-secret` on nemo |

### 5. Check it

Run the **Nemo push deploy** workflow by hand on `main` (Actions → Run workflow).
The job should log `HTTP 202 {"queued": "<sha>"}`. On nemo:

```bash
journalctl --user -u hermes-deploy.service -f
cat ~/.hermes/deploy/status.json
systemctl --user start hermes-deploy-drift.service && journalctl --user -u hermes-deploy-drift.service -n 20
```

## Operating

- **Pause automatic deploys:** `systemctl --user stop hermes-deploy.path`. Requests
  keep queueing. `start` deploys the newest one.
- **Hand deploys:** stop the path unit first. `build.sh` and `cutover.sh` do not take
  the worker's lock (`deploy/deploy.lock`).
- **Rotate the secret:** replace `deploy/webhook-secret`, restart
  `hermes-deploy-listener.service`, update `NEMO_DEPLOY_HMAC_SECRET`.
- **Remove:** `install_autodeploy.sh uninstall` (add `--scope system` if installed so).

## Not covered yet

- Prompts are built in Python and profile `config.yaml` is not in this repo, so neither
  has a no-restart path. Only bundled skills do.
- A newer merge that arrives while the worker waits on the idle gate does not
  interrupt that wait; it deploys right after.
- Each release still copies `node_modules` from the previous one. Hard-linking it
  (releases are read-only) would cut most of the per-release disk use.

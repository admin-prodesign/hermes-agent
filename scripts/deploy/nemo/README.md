# Nemo pull deploy

Nemo polls GitHub for `main` about once a minute and deploys a new commit on its own.
Nothing has to reach nemo from outside: no webhook, no Tailscale tags or OAuth client,
and no GitHub secrets. Nemo still decides when the merge goes live. It builds the exact
SHA, waits until every Hermes profile is idle, cuts over, and rolls back on its own if
health fails.

```
nemo: hermes-deploy-poll.timer → hermes-deploy-poll.service   (poll.py, every ~60 s + jitter)
       skips its turn while a deploy holds deploy/deploy.lock
       git ls-remote <mirror remote> refs/heads/main
       main == live SHA, refused, or already queued → nothing
       otherwise → deploy/queue/<sha>.json
nemo: hermes-deploy.path → hermes-deploy.service  (oneshot worker, autodeploy.py)
       1. fetches main; refuses a SHA that is not on main, or is older than the live SHA
       2. classifies the diff: noop / skills / restart          (changes.py)
       3. prunes old releases, then build.sh --sha <sha>
       4. restart: cutover.sh  (idle gate → swap → unit rewrite → restart → /health → rollback)
          noop/skills: cutover.sh without gate or restart, then sync bundled skills
       5. prunes again (keeps current, its rollback target, and the running build)
nemo: hermes-deploy-drift.timer  (hourly: live files vs the deployed SHA)
```

The poller only reads `main` and writes the queue. It never builds, restarts, or reads
profile state. Every unit runs code from `releases/current`, so a merged change to this
directory goes live with the release that carries it. A worker change therefore first
runs on the deploy *after* the one that shipped it.

## Read access to the private repo

The poller and the worker use the bare mirror that `build.sh` already fetches from
(`--mirror`). They run `git --git-dir <mirror> ls-remote origin refs/heads/main` and
`git fetch origin` as the user that owns the Hermes home, so they use the mirror's
`origin` URL and whatever read credential that user already has for it: an SSH deploy
key (`~/.ssh`, or `core.sshCommand` in the mirror's config) or a git credential helper
for an HTTPS URL. No new credential is added, and nothing goes into the repo.

Units run without a terminal or an SSH agent, and they set `GIT_TERMINAL_PROMPT=0`, so a
credential that needs a prompt or a passphrase fails instead of hanging. Check it the
way the timer will run it:

```bash
git --git-dir /path/to/hermes-agent.git config --get remote.origin.url
env -u SSH_AUTH_SOCK GIT_TERMINAL_PROMPT=0 \
  git --git-dir /path/to/hermes-agent.git ls-remote origin refs/heads/main
```

That should print one `<sha>\trefs/heads/main` line.

## What happens to a deploy

| Diff touches | Mode | Restart | Idle gate |
| --- | --- | --- | --- |
| only `website/`, `tests/`, `tests-js/`, `.github/`, `contributors/`, `AGENTS.md`, root `README*/CONTRIBUTING*/SECURITY*.md` | `noop` | no | no |
| the above plus `skills/` | `skills` | no | no |
| anything else (Python, prompts, locales, dependencies, `optional-skills/`, `SOUL.md`), or an unreadable diff | `restart` | yes | yes |

- **Idle gate.** `cutover.sh` waits until pdone and pdneo have no turn or compression
  lease, no live goal, and no message newer than 90 s (`gate.py`). It waits up to 6 h.
  If the profiles are still busy it exits 75 and nothing changes. You get a `waiting`
  alert, and the next poll queues the newest `main` again for another wait. A running
  turn is never interrupted.
- **Rollback.** If systemd or `/health` (gateway `:8642`, dashboard `:9119`) is not
  healthy within 90 s of the restart, `cutover.sh` restores the previous symlink,
  unit files, and configs from `upgrade-audits/<build>/` and restarts again.
- **Refused SHAs.** A SHA that is `rejected` (not on main, or older than the live one)
  or `failed` (build failed, too little disk, rolled back, skill sync failed) goes into
  `deploy/refused.jsonl`. The poller skips it, so a broken commit does not rebuild every
  minute. The next commit on main is a new SHA and is tried as usual. To try a refused
  SHA again, run `autodeploy.py retry <sha>` (no SHA clears the whole list).
- **Transient failures.** If `git ls-remote` fails or times out, the poll records an
  `error` and queues nothing. If the worker can't fetch main, the outcome is `deferred`.
  Nothing is built or refused, and the next poll tries again. The drift check alerts if
  main stays ahead of the live SHA for more than 2 h.
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
- **Queue.** Only the newest SHA matters. Older queued SHAs are dropped as
  superseded.
- **Dependencies.** A change to `pyproject.toml` or `uv.lock` is a `restart` deploy like
  any other code change: `build.sh` installs the locked environment into the new
  release. There is no separate manual-approval step.

## Status

```bash
cd ~/.hermes/releases/current
.venv/bin/python -m scripts.deploy.nemo.autodeploy status
```

This prints:

- `deploy`: the last worker outcome (`<home>/deploy/status.json`). One of `deployed`,
  `live` (already current), `waiting`, `deferred`, `failed`, or `rejected`.
  `<home>/deploy/history.jsonl` keeps every outcome.
- `poll`: the last poll (`<home>/deploy/poll.json`): `main`, `live`, and one of `live`,
  `queued`, `pending` (already queued), `busy` (a deploy holds the lock), `refused`, or
  `error`.
- `queued`: what is waiting for the worker.
- `refused`: SHAs the poller skips, with the reason.

## Drift check

`hermes-deploy-drift.timer` runs hourly. It alerts when:

- a tracked file in the live release differs from `git ls-tree <deployed sha>`, or is
  missing (git blob hashes, so mode-only noise does not count);
- an untracked `.py` or `.sh` file sits in the release outside build output (`.venv`,
  `.python`, `node_modules`, `web_dist`, `ui-tui/dist`, `__pycache__`);
- a systemd unit points at a release other than `current` or the running build;
- `main` has been ahead of the live SHA for more than 2 h with nothing queued. That covers
  a refused SHA, a poller that keeps failing, and a gate that never goes quiet.

## One-time setup

Nothing changes in GitHub or Tailscale. Everything below runs on nemo.

### 1. Ship this code to nemo the existing way

Build and cut over a `main` SHA that contains this directory with the hand flow in
`website/docs/user-guide/pd-one-safe-ops.md` (`build.sh`, then `cutover.sh`).

### 2. Check the mirror's read credential

Run the `ls-remote` check under [Read access](#read-access-to-the-private-repo).

### 3. Install the timer

From the deployed release, as the user that owns the Hermes home:

```bash
cd ~/.hermes/releases/current
loginctl enable-linger "$USER"     # user units keep running after logout
bash scripts/deploy/nemo/install_autodeploy.sh install \
  --mirror /path/to/hermes-agent.git \
  --alert-script ~/.hermes/deploy/alert.sh     # optional, see below
```

- `--dry-run` prints the six units (poll service and timer, worker service and path,
  drift service and timer) without writing anything.
- `--poll-every 2min` polls less often. Each poll waits an extra 0–20 s of jitter.
- If the Hermes gateway units are system units (`/etc/systemd/system`), run the
  installer with `sudo` and `--scope system --run-as <hermes user>`. The worker
  rewrites and restarts those units, so give it the same identity the hand cutover
  uses (`--worker-user`, which defaults to `--run-as`). The `--run-as` user needs the
  mirror credential.
- If an earlier version installed `hermes-deploy-listener.service`, the installer
  disables and removes it. You can delete `~/.hermes/deploy/webhook-secret`, and the
  `TS_OAUTH_*` and `NEMO_DEPLOY_*` repo secrets if anyone added them.

The alert script is called as `alert.sh "<subject>"` with JSON details on stdin.
For example, posting to a Mattermost incoming webhook whose URL is in a 0600 file:

```bash
#!/usr/bin/env bash
jq -Rs --arg s "$1" '{text: ("**" + $s + "**\n" + .)}' \
  | curl -fsS -H 'Content-Type: application/json' -d @- "$(cat ~/.hermes/deploy/mattermost-hook)"
```

Without an alert script, failures still show in `journalctl` and `systemctl --failed`.

### 4. Check it

```bash
systemctl --user list-timers 'hermes-deploy-*'
systemctl --user start hermes-deploy-poll.service && journalctl --user -u hermes-deploy-poll.service -n 5
.venv/bin/python -m scripts.deploy.nemo.autodeploy status
journalctl --user -u hermes-deploy.service -f
```

The poll prints `"action": "live"` when nemo already runs `main`, or `"queued"` and the
worker starts.

## Operating

- **Pause automatic deploys:** `systemctl --user stop hermes-deploy-poll.timer hermes-deploy.path`.
  `start` both to resume; the next poll queues `main` if it moved.
- **Hand deploys:** pause first. `build.sh` and `cutover.sh` do not take the worker's
  lock (`deploy/deploy.lock`).
- **Retry a refused SHA:** `.venv/bin/python -m scripts.deploy.nemo.autodeploy retry <sha>`.
- **Remove:** `install_autodeploy.sh uninstall` (add `--scope system` if installed so).

## Not covered yet

- Prompts are built in Python and profile `config.yaml` is not in this repo, so neither
  has a no-restart path. Only bundled skills do.
- A newer merge that lands while the worker waits on the idle gate is not seen until
  that wait ends: the poller skips its turn while the deploy holds the lock.
- Each release still copies `node_modules` from the previous one. Hard-linking it
  (releases are read-only) would cut most of the per-release disk use.

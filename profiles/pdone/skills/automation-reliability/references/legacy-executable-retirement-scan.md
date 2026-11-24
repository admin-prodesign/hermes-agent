# Legacy executable retirement scan pattern

Use after migrating scheduled jobs away from an older control-plane executable such as OpenClaw.

## Durable pattern

1. Separate dependency classes:
   - scheduler dependency: cron/systemd still calls the old executable or legacy runner;
   - script-internal CLI dependency: migrated scripts still shell out to old `message send`, `agent`, `health`, etc.;
   - textual/archive references: docs, old sessions, logs, migration notes.
2. Patch active/migrated scripts first:
   - replace old message-send calls with a Hermes-native helper or stdout delivery for `no_agent` cron;
   - keep deterministic fallback paths and remove nonessential old agent enrichment if it would only add quality polish;
   - preserve locks, logs, watermarks, and failure federation.
3. Scan the authoritative active set, not the whole home directory:
   - enabled Hermes cron scripts;
   - migrated legacy manifest commands;
   - direct absolute `.py` script references reachable from those scripts.
4. Treat zero executable hits in that active set as the uninstall-readiness signal. Whole-tree scans can still show historical skills, sessions, logs, archives, and docs; report them separately as non-blocking unless they are active policy/runtime files.
5. Verify with smoke tests before reporting:
   - Python/shell syntax checks for patched files;
   - migrated runner smoke test;
   - key wrapper smoke tests;
   - process/systemd check proving no live old gateway/service remains.
   - Run smoke tests under the same non-login environment the job uses. For Hermes no-agent Python runners, prefer invoking the executable script with `HOME=/home/prodesign` and a bounded `PATH` that includes the Hermes venv before `/usr/bin`; a bare `python3 script.py` can create false failures for dependencies that are present in the cron runtime.
6. For backup repos, copy only the changed active receipts/scripts/skills into the mirror and commit/push a focused commit. Avoid staging unrelated live state churn.

## Pitfalls

- Do not search only for crontab entries; migrated scripts can still call the old executable internally.
- Do not let historical wording like “OpenClaw gateway” in active scripts create false dependency hits; either reword active runtime comments or classify them as doc-only.
- Treat variables named `OPENCLAW` carefully: `OPENCLAW = Path(.../legacy-openclaw/workspace)` is usually a workspace-path alias, not executable CLI usage. Block retirement only on executable calls/shims such as `openclaw message`, `openclaw agent`, `OPENCLAW_BIN`, `shutil.which("openclaw")`, or an absolute CLI path.
- When scanning reachable scripts with path-regex expansion, avoid pulling in credential/env/log/state files as if they were executable dependencies; keep the authoritative set to active cron scripts, manifest command entrypoints, and direct script references reachable from those scripts.
- Do not remove the executable automatically after scan success when policy marks cleanup/destructive actions as confirmation-gated; report exact safe uninstall commands and wait for approval.

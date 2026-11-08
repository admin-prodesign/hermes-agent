# Hermes Curator Markdown report delivery

Use this when a user wants Hermes Curator's full `REPORT.md` posted back to a chat/channel after each scheduled run instead of only being written under `logs/curator/`.

## Problem pattern

Hermes Curator writes the authoritative per-run report to disk:

```text
$HERMES_HOME/logs/curator/<YYYYMMDD-HHMMSS>/REPORT.md
```

The built-in gateway/CLI callback usually surfaces only a short summary/log line. If the user wants the full Markdown report in the current chat, create a wrapper job that runs Curator synchronously, reads Curator state, and prints the Markdown to stdout from a `no_agent` cron job.

## Recommended implementation

Create a profile-local script, for example:

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/home/prodesign/.hermes/profiles/pdone"))
STATE_PATH = HERMES_HOME / "skills" / ".curator_state"


def latest_report() -> tuple[dict, Path, str]:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    report_md = Path(state["last_report_path"]) / "REPORT.md"
    return state, report_md, report_md.read_text(encoding="utf-8")


def main() -> int:
    # Non-mutating smoke test: CURATOR_REPORT_MODE=latest script.py
    if os.environ.get("CURATOR_REPORT_MODE") == "latest":
        state, report_md, markdown = latest_report()
        print(markdown.rstrip())
        print(f"\n---\n_Smoke-test replay only. Report source: `{report_md}`._")
        return 0

    env = os.environ.copy()
    env["HERMES_HOME"] = str(HERMES_HOME)
    env.setdefault("HERMES_PROFILE", "pdone")
    env["PATH"] = "/home/prodesign/.local/bin:/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")

    proc = subprocess.run(
        ["hermes", "--profile", env["HERMES_PROFILE"], "curator", "run", "--sync"],
        cwd=str(HERMES_HOME), env=env, text=True, capture_output=True, timeout=1200,
    )
    if proc.returncode != 0:
        print("# Hermes Curator run failed\n")
        print(f"Exit code: `{proc.returncode}`")
        if proc.stdout:
            print("\n## stdout\n```text\n" + proc.stdout.strip() + "\n```")
        if proc.stderr:
            print("\n## stderr\n```text\n" + proc.stderr.strip() + "\n```")
        return proc.returncode

    state, report_md, markdown = latest_report()
    print(markdown.rstrip())
    print(f"\n---\n_Delivered by scheduled curator reporter. Report source: `{report_md}`._")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

Schedule it as a script-only/no-agent cron job so stdout is delivered verbatim:

```text
schedule: 45 5 * * 3        # align just after the weekly Curator due time
script: run_curator_and_emit_report.py
no_agent: true
deliver: origin
profile: pdone              # or the target profile
```

## Verification checklist

1. Confirm Curator configuration/state first: `hermes curator status` and the profile `curator.*` config.
2. Do **not** trigger an unscheduled real Curator pass just to test delivery unless the user explicitly wants that. Use `CURATOR_REPORT_MODE=latest <script>` to replay the latest existing report and verify Markdown stdout.
3. Create/list the cron job and record its `job_id`, schedule, `next_run_at`, delivery target, script, and `no_agent` mode.
4. For durable Hermes profile changes, run the configured backup helper and report the backup commit/receipt when available.

## Pitfalls

- A normal `cronjob` LLM prompt is unnecessary here and can reformat/truncate the report; use `no_agent=true` for exact Markdown delivery.
- The built-in Curator scheduler and the Hermes cron scheduler are separate systems. The delivery job may not appear as the Curator itself; it is a wrapper that runs Curator and emits the report.
- Keep the script profile-local and set `HERMES_HOME`/`HERMES_PROFILE` explicitly so the wrong profile's Curator state is not read.

"""No-restart path: sync the release's bundled skills into each profile.

Runs the release interpreter once per profile with ``HERMES_HOME`` at that profile,
so ``sync_skills`` keeps its usual rules (user-modified skills and curator-pruned
built-ins are left alone). A running gateway reads a skill by name at call time;
a skill added or removed shows in the slash-command list after ``/reload-skills``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Callable

from scripts.deploy.nemo.layout import profile_home

SYNC_SNIPPET = (
    "import json\n"
    "from tools.skills_sync import sync_skills\n"
    "r = sync_skills(quiet=True)\n"
    "print(json.dumps({k: r.get(k) for k in ('copied', 'updated', 'user_modified', 'cleaned')}))\n"
)
_DROPPED_ENV = ("HERMES_BUNDLED_SKILLS", "HERMES_OPTIONAL_SKILLS", "PYTHONPATH")

SyncRun = Callable[[list[str], dict[str, str], Path], subprocess.CompletedProcess]


def _run(argv: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv, env=env, cwd=cwd, capture_output=True, timeout=300, stdin=subprocess.DEVNULL, check=False,
    )


def sync_env(base: dict[str, str], home: Path) -> dict[str, str]:
    env = {key: value for key, value in base.items() if key not in _DROPPED_ENV}
    env["HERMES_HOME"] = str(home)
    return env


def sync_profiles(release: Path, home: Path, profiles: tuple[str, ...], *, run: SyncRun = _run) -> list[dict]:
    python = release / ".venv" / "bin" / "python"
    results: list[dict] = []
    for name in profiles:
        target = profile_home(home, name)
        if not target.is_dir():
            results.append({"profile": name, "ok": False, "detail": f"missing {target}"})
            continue
        completed = run([str(python), "-c", SYNC_SNIPPET], sync_env(dict(os.environ), target), release)
        out = (completed.stdout or b"").decode("utf-8", "replace").strip().splitlines()
        try:
            detail = json.loads(out[-1]) if out else {}
        except json.JSONDecodeError:
            detail = {"stdout": out[-1]}
        if completed.returncode != 0:
            detail = {"stderr": (completed.stderr or b"").decode("utf-8", "replace")[-2000:]}
        results.append({"profile": name, "ok": completed.returncode == 0, "detail": detail})
    return results

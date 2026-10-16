"""Decide whether a deploy needs a restart.

``noop``: nothing the running processes read changed (docs, tests, CI).
``skills``: bundled skills changed too. Skills are read by name from each profile's
``skills/`` directory at call time, so syncing them is enough.
``restart``: everything else, including an unreadable diff. Python, prompts (built
in code), locales, and dependencies are only picked up by a fresh process.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from scripts.deploy.nemo.source import Run, run_cmd

NOOP = "noop"
SKILLS = "skills"
RESTART = "restart"

NOOP_PREFIXES = ("website/", "tests/", "tests-js/", ".github/", "contributors/")
NOOP_FILE_RE = re.compile(r"(?:[^/]+/)*AGENTS\.md|(?:README|CONTRIBUTING|SECURITY)[^/]*\.md")
SKILL_PREFIXES = ("skills/",)


def changed_paths(mirror: Path, old: str, new: str, *, run: Run = run_cmd, timeout: float = 30.0) -> list[str] | None:
    """Both sides of a rename, so a skill moved out of ``skills/`` is not mistaken for a skill edit."""
    argv = ["git", "--git-dir", str(mirror), "diff", "--no-renames", "--name-only", old, new]
    try:
        completed = run(argv, timeout)
    except subprocess.TimeoutExpired:
        return None
    if completed.returncode != 0:
        return None
    text = (completed.stdout or b"").decode("utf-8", "replace")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _is_noop(path: str) -> bool:
    return path.startswith(NOOP_PREFIXES) or bool(NOOP_FILE_RE.fullmatch(path))


def classify(paths: list[str] | None) -> str:
    if paths is None:
        return RESTART
    skills = False
    for path in paths:
        if path.startswith(SKILL_PREFIXES):
            skills = True
        elif not _is_noop(path):
            return RESTART
    return SKILLS if skills else NOOP

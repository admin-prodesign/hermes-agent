"""Run only the verifies (and pytest files) the old/new diff can affect.

``--full`` runs every verify this deploy knows about. An unreadable diff fails
open to that same set: skipping a verify we could not prove irrelevant is worse
than running it.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from scripts.deploy.nemo.source import Run, run_cmd


@dataclass(frozen=True)
class Verify:
    name: str
    script: str
    prefixes: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    verifies: tuple[str, ...]
    tests: tuple[str, ...]
    full: bool
    reason: str


CATALOG: tuple[Verify, ...] = (
    Verify(
        "verify_mcp",
        "scripts/deploy/nemo/verify_mcp.py",
        ("tools/mcp", "tools/pd_one", "cron/cwa_tls.py", "cron/scheduler_script.py"),
    ),
    Verify(
        "verify_ws",
        "scripts/deploy/nemo/verify_ws.py",
        (
            "web/", "ui-tui/", "scripts/build/",
            "hermes_cli/web_", "hermes_cli/pty", "hermes_cli/main_tui_launch.py",
            "hermes_cli/main_web_build.py", "hermes_cli/main_dashboard.py",
            "hermes_cli/source_build.py",
        ),
    ),
)

# Host preflight runs these only when the diff touches the deploy or the
# frontend launch path. CI runs them on every push of this tree.
DEPLOY_TESTS = (
    "tests/scripts/deploy/test_nemo_deploy.py",
    "tests/scripts/deploy/test_nemo_autodeploy.py",
    "tests/hermes_cli/test_tui_npm_install.py",
    "tests/hermes_cli/test_frontend_preinstall.py",
)
_DEPLOY_TEST_PREFIXES = (
    "scripts/deploy/nemo/",
    "hermes_cli/source_build.py",
    "hermes_cli/main_tui_launch.py",
    "hermes_cli/main_web_build.py",
)


def _matches(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in prefixes)


def changed_files(mirror: Path, old: str, new: str, *, run: Run = run_cmd, timeout: float = 30.0) -> list[str] | None:
    """``None`` when git cannot answer. The caller then runs the full set."""
    argv = ["git", "--git-dir", str(mirror), "diff", "--name-only", old, new]
    try:
        completed = run(argv, timeout)
    except subprocess.TimeoutExpired:
        return None
    if completed.returncode != 0:
        return None
    text = (completed.stdout or b"").decode("utf-8", "replace")
    return [line.strip() for line in text.splitlines() if line.strip()]


def plan_for(changed: list[str] | None, *, full: bool) -> Plan:
    if full:
        return Plan(tuple(item.name for item in CATALOG), DEPLOY_TESTS, True, "full")
    if changed is None:
        return Plan(tuple(item.name for item in CATALOG), DEPLOY_TESTS, True, "diff unavailable")
    verifies = tuple(item.name for item in CATALOG if any(_matches(path, item.prefixes) for path in changed))
    tests = DEPLOY_TESTS if any(_matches(path, _DEPLOY_TEST_PREFIXES) for path in changed) else ()
    return Plan(verifies, tests, False, "diff")


def verify_script(name: str) -> str:
    for item in CATALOG:
        if item.name == name:
            return item.script
    raise KeyError(name)

"""On-demand safe checks for the pdone cron scripts.

The scripts themselves stay on the profile. HR sync (``6adb0e5216c5``) is never
executed unless its source declares ``--dry-run`` and that flag is on the argv.
A bare run would write new-hire rows to AppSheet.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from scripts.deploy.nemo.layout import profile_home

HR_SYNC = "6adb0e5216c5"
DIGEST = "870dd7349151"
TYPHOON = "840af263673e"
REAPER = "c9287579f167"
_DRY_FLAGS = {"--dry-run", "--dry_run"}
_PYTHON_SUFFIXES = {".py", ".pyw"}
_SHELL_SUFFIXES = {".sh", ".bash"}
_SHELL_INTERPRETERS = frozenset({"bash", "sh", "dash", "zsh", "ksh"})


@dataclass(frozen=True)
class Policy:
    job_id: str
    name: str
    kind: str  # exec_readonly | dry_run | compile
    required_imports: tuple[str, ...] = ()


POLICIES: tuple[Policy, ...] = (
    Policy(TYPHOON, "typhoon", "exec_readonly"),
    Policy(DIGEST, "digest", "compile", ("yaml",)),
    Policy(REAPER, "reaper", "dry_run"),
    Policy(HR_SYNC, "hr-sync", "dry_run", ("requests",)),
)


@dataclass(frozen=True)
class Invocation:
    job_id: str
    name: str
    action: str  # exec | compile | skip
    argv: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class SyntaxCheckPlan:
    action: str
    argv: tuple[str, ...]
    reason: str


def _shebang_kind(first_line: str) -> str | None:
    stripped = first_line.strip()
    if not stripped.startswith("#!"):
        return None
    body = stripped[2:].strip()
    if not body:
        return None
    parts = body.split()
    token = parts[1] if parts[0].endswith("env") and len(parts) > 1 else parts[0]
    name = Path(token).name
    if name == "python" or name.startswith("python"):
        return "python"
    if name in _SHELL_INTERPRETERS:
        return "shell"
    if name.endswith("sh") and name not in {"fish", "wish"}:
        return "shell"
    return None


def classify_script(script: Path, source: str) -> str:
    """Return ``python``, ``shell``, or ``unknown`` for syntax-check routing."""
    suffix = script.suffix.lower()
    if suffix in _PYTHON_SUFFIXES:
        return "python"
    if suffix in _SHELL_SUFFIXES:
        return "shell"
    first_line = source.splitlines()[0] if source else ""
    kind = _shebang_kind(first_line)
    return kind if kind is not None else "unknown"


def exec_argv_for_script(script: Path, source: str, python: str) -> tuple[str, ...]:
    """Argv to run a read-only cron script (shell via bash, Python via ``python``)."""
    kind = classify_script(script, source)
    if kind == "shell":
        bash = shutil.which("bash")
        if bash is None:
            return (str(script),)
        return (bash, str(script))
    return (python, str(script))


def syntax_check_plan(script: Path, source: str, python: str) -> SyntaxCheckPlan:
    """Pick ``py_compile`` or ``bash -n`` (or a benign skip) from the script type."""
    reason = "no --dry-run in argparse; not executing"
    kind = classify_script(script, source)
    if kind == "python":
        return SyntaxCheckPlan(
            "compile", (python, "-m", "py_compile", str(script)), reason,
        )
    if kind == "shell":
        bash = shutil.which("bash")
        if bash is None:
            return SyntaxCheckPlan("skip", (), "skipped: shell")
        return SyntaxCheckPlan("compile", (bash, "-n", str(script)), reason)
    return SyntaxCheckPlan("skip", (), "skipped: unknown")


def postcheck_ok(invocation: Invocation, codes: list[int]) -> bool:
    if invocation.action == "skip":
        return invocation.reason.startswith("skipped:")
    return all(code == 0 for code in codes)


def script_accepts_dry_run(source: str) -> bool:
    """True only when argparse declares ``--dry-run``. A mention in a string is not enough."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else ""
        if name != "add_argument":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and arg.value in _DRY_FLAGS:
                return True
    return False


def load_jobs(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        jobs = data.get("jobs", [])
        if isinstance(jobs, dict):
            return [{**value, "id": value.get("id") or key} for key, value in jobs.items() if isinstance(value, dict)]
        if isinstance(jobs, list):
            return [job for job in jobs if isinstance(job, dict)]
        return []
    if isinstance(data, list):
        return [job for job in data if isinstance(job, dict)]
    return []


def resolve_script(profile: Path, raw: str) -> Path | None:
    """Profile cron scripts must stay under that profile's ``scripts/`` directory."""
    if not raw or not str(raw).strip():
        return None
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = profile / "scripts" / path
    try:
        resolved = path.resolve()
        root = (profile / "scripts").resolve()
    except OSError:
        return None
    if resolved != root and root not in resolved.parents:
        return None
    return resolved


def find_job(home: Path, job_id: str, profiles: tuple[str, ...]) -> tuple[Path, dict] | None:
    for name in profiles:
        root = profile_home(home, name)
        jobs_file = root / "cron" / "jobs.json"
        if not jobs_file.is_file():
            continue
        for job in load_jobs(jobs_file):
            if str(job.get("id") or "") == job_id:
                return root, job
    return None


def plan_policy(policy: Policy, script: Path | None, source: str, python: str) -> Invocation:
    accepts = bool(source) and script_accepts_dry_run(source)
    if policy.kind == "exec_readonly":
        if script is None:
            return Invocation(policy.job_id, policy.name, "skip", (), "job script not found")
        return Invocation(
            policy.job_id, policy.name, "exec", exec_argv_for_script(script, source, python),
            "read-only script run",
        )
    if script is not None and accepts:
        return Invocation(
            policy.job_id, policy.name, "exec", (python, str(script), "--dry-run"),
            "dry-run only",
        )
    if script is None:
        return Invocation(policy.job_id, policy.name, "skip", (), "job script not found")
    planned = syntax_check_plan(script, source, python)
    return Invocation(
        policy.job_id, policy.name, planned.action, planned.argv, planned.reason,
    )


def guard(invocation: Invocation) -> None:
    """Last line of defense before any subprocess. HR sync cannot live-write."""
    if invocation.job_id == HR_SYNC and invocation.action == "exec" and "--dry-run" not in invocation.argv:
        raise RuntimeError("refusing to live-write HR sync to AppSheet")
    if invocation.job_id == REAPER and invocation.action == "exec" and "--dry-run" not in invocation.argv:
        raise RuntimeError("refusing to run the reaper without --dry-run")


def command_list(invocation: Invocation, policy: Policy, python: str) -> list[tuple[str, ...]]:
    guard(invocation)
    if invocation.action == "skip":
        return []
    commands: list[tuple[str, ...]] = []
    if invocation.action in {"exec", "compile"} and invocation.argv:
        commands.append(invocation.argv)
    for module in policy.required_imports:
        commands.append((python, "-c", f"import {module}"))
    return commands


def child_env(script: Path | None, base: dict[str, str] | None = None) -> dict[str, str]:
    """Match the cron runner's CWA/DGPA TLS mount when the script needs it."""
    env = dict(os.environ if base is None else base)
    env["HERMES_DEPLOY_SAFE_CHECK"] = "1"
    if script is None:
        return env
    from cron.scheduler_script import _apply_cwa_tls_env, _script_wants_cwa_tls

    if _script_wants_cwa_tls(script):
        _apply_cwa_tls_env(env)
    return env


def run_postcheck(
    home: Path, profiles: tuple[str, ...], python: str, *,
    run, base_env: dict[str, str] | None = None,
) -> list[dict]:
    """Plan and run every known job. ``run`` returns a process return code."""
    results = []
    for policy in POLICIES:
        found = find_job(home, policy.job_id, profiles)
        script: Path | None = None
        source = ""
        if found is not None:
            root, job = found
            script = resolve_script(root, str(job.get("script") or ""))
            if script is not None and script.is_file():
                source = script.read_text(encoding="utf-8-sig")
            else:
                script = None
        invocation = plan_policy(policy, script, source, python)
        commands = command_list(invocation, policy, python)
        env = child_env(script, base_env)
        codes = [int(run(argv, env)) for argv in commands]
        ok = postcheck_ok(invocation, codes)
        results.append({
            "job_id": policy.job_id,
            "name": policy.name,
            "action": invocation.action,
            "reason": invocation.reason,
            "argv": [list(argv) for argv in commands],
            "codes": codes,
            "ok": ok,
        })
    return results

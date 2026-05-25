"""Scoped PD One worker-scheduling execution tool.

This tool intentionally exposes only the known monthly worker scheduling entrypoint
instead of broad terminal/code execution. It is meant for tightly scoped Mattermost
channel use where the agent needs to run the scheduling playbook but should not get
a general shell.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from tools.registry import registry

TOOLSET = "worker_scheduling_execution"
TOOL_NAME = "worker_scheduling_execute"
PROJECT_DIR = Path("/home/prodesign/.openclaw/workspace/projects/automatic-worker-scheduling")
SCRIPT_PATH = PROJECT_DIR / "scripts" / "shift_scheduler_phase1.py"
VENV_PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"
DEFAULT_TIMEOUT_SECONDS = 900
MAX_OUTPUT_CHARS = 24000
LIVE_CONFIRM_PHRASE = "RUN LIVE WORKER SCHEDULING WRITE"

ACTIONS = {
    "preflight": [],
    "solve_preview": ["--solve"],
    "sync_source_rollover": ["--sync-source-rollover", "--yes"],
    "write_generated_schedule": ["--solve", "--write-generated-schedule", "--yes"],
}
RUN_GROUPS = {"day", "night", "manager_day", "manager_night"}
LIVE_ACTIONS = {"sync_source_rollover", "write_generated_schedule"}


def _available() -> bool:
    return PROJECT_DIR.is_dir() and SCRIPT_PATH.is_file() and VENV_PYTHON.is_file()


def _json_result(**kwargs: Any) -> str:
    return json.dumps(kwargs, ensure_ascii=False, default=str)


def _build_command(
    action: str,
    solve_groups: list[str] | None = None,
    stdout_summary_only: bool = True,
    solver_max_time_seconds: int | None = None,
    solver_no_improvement_seconds: int | None = None,
    output_dir: str | None = None,
) -> list[str]:
    if action not in ACTIONS:
        raise ValueError(f"Unsupported action: {action}")

    cmd = [str(VENV_PYTHON), str(SCRIPT_PATH), *ACTIONS[action]]
    if stdout_summary_only:
        cmd.append("--stdout-summary-only")

    groups = solve_groups or []
    if groups and action not in {"solve_preview", "write_generated_schedule"}:
        raise ValueError("solve_groups can only be used with solve_preview or write_generated_schedule")
    for group in groups:
        if group not in RUN_GROUPS:
            raise ValueError(f"Unsupported solve group: {group}")
        cmd.extend(["--solve-group", group])

    if solver_max_time_seconds is not None:
        if solver_max_time_seconds < 30 or solver_max_time_seconds > 3600:
            raise ValueError("solver_max_time_seconds must be between 30 and 3600")
        cmd.extend(["--solver-max-time-seconds", str(solver_max_time_seconds)])

    if solver_no_improvement_seconds is not None:
        if solver_no_improvement_seconds < 10 or solver_no_improvement_seconds > 1800:
            raise ValueError("solver_no_improvement_seconds must be between 10 and 1800")
        cmd.extend(["--solver-no-improvement-seconds", str(solver_no_improvement_seconds)])

    if output_dir:
        out_path = Path(output_dir).expanduser()
        if not out_path.is_absolute():
            raise ValueError("output_dir must be an absolute path when provided")
        allowed_roots = [PROJECT_DIR / "output", Path("/tmp")]
        try:
            resolved = out_path.resolve()
        except FileNotFoundError:
            resolved = out_path.parent.resolve() / out_path.name
        if not any(resolved == root or root in resolved.parents for root in allowed_roots):
            raise ValueError("output_dir must be under the scheduling project output/ directory or /tmp")
        cmd.extend(["--output-dir", str(resolved)])

    return cmd


def worker_scheduling_execute(
    action: str = "preflight",
    solve_groups: list[str] | None = None,
    confirm_live_write: str = "",
    stdout_summary_only: bool = True,
    solver_max_time_seconds: int | None = None,
    solver_no_improvement_seconds: int | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    output_dir: str | None = None,
    task_id: str | None = None,
) -> str:
    """Run a narrow, whitelisted worker-scheduling operation."""

    if not _available():
        return _json_result(
            success=False,
            error="worker_scheduling_unavailable",
            detail=f"Expected project/script/python under {PROJECT_DIR}",
        )

    if action in LIVE_ACTIONS and confirm_live_write != LIVE_CONFIRM_PHRASE:
        return _json_result(
            success=False,
            error="live_write_confirmation_required",
            detail=(
                f"Live sheet mutations require confirm_live_write exactly equal to "
                f"{LIVE_CONFIRM_PHRASE!r}. Run solve_preview/preflight first unless the user explicitly approved live writes."
            ),
            action=action,
        )

    if timeout_seconds < 30 or timeout_seconds > 3600:
        return _json_result(
            success=False,
            error="invalid_timeout",
            detail="timeout_seconds must be between 30 and 3600",
        )

    try:
        cmd = _build_command(
            action=action,
            solve_groups=solve_groups,
            stdout_summary_only=stdout_summary_only,
            solver_max_time_seconds=solver_max_time_seconds,
            solver_no_improvement_seconds=solver_no_improvement_seconds,
            output_dir=output_dir,
        )
    except ValueError as exc:
        return _json_result(success=False, error="invalid_request", detail=str(exc))

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_DIR),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _json_result(
            success=False,
            error="timeout",
            action=action,
            timeout_seconds=timeout_seconds,
            stdout=(exc.stdout or "")[-MAX_OUTPUT_CHARS:],
            stderr=(exc.stderr or "")[-MAX_OUTPUT_CHARS:],
        )

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    return _json_result(
        success=proc.returncode == 0,
        action=action,
        returncode=proc.returncode,
        command_preview=" ".join(cmd),
        stdout=stdout[-MAX_OUTPUT_CHARS:],
        stderr=stderr[-MAX_OUTPUT_CHARS:],
        truncated_stdout=len(stdout) > MAX_OUTPUT_CHARS,
        truncated_stderr=len(stderr) > MAX_OUTPUT_CHARS,
    )


registry.register(
    name=TOOL_NAME,
    toolset=TOOLSET,
    description="Run the PD One monthly worker scheduling playbook via a narrow whitelisted wrapper.",
    emoji="📅",
    check_fn=_available,
    handler=lambda args, **kw: worker_scheduling_execute(
        action=args.get("action", "preflight"),
        solve_groups=args.get("solve_groups"),
        confirm_live_write=args.get("confirm_live_write", ""),
        stdout_summary_only=args.get("stdout_summary_only", True),
        solver_max_time_seconds=args.get("solver_max_time_seconds"),
        solver_no_improvement_seconds=args.get("solver_no_improvement_seconds"),
        timeout_seconds=args.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
        output_dir=args.get("output_dir"),
        task_id=kw.get("task_id"),
    ),
    schema={
        "name": TOOL_NAME,
        "description": (
            "Run the PD One monthly worker scheduling playbook without general shell access. "
            "Use preflight/solve_preview first. Live write actions require explicit user approval and exact confirmation text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["preflight", "solve_preview", "sync_source_rollover", "write_generated_schedule"],
                    "description": "Whitelisted scheduling action. preflight/dry-run is read-only; solve_preview generates schedule preview; the other two mutate sheets.",
                    "default": "preflight",
                },
                "solve_groups": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["day", "night", "manager_day", "manager_night"]},
                    "description": "Optional solve groups for solve_preview/write_generated_schedule. Omit for all groups.",
                },
                "confirm_live_write": {
                    "type": "string",
                    "description": f"For live sheet mutations only, must exactly equal {LIVE_CONFIRM_PHRASE!r} after explicit user approval.",
                },
                "stdout_summary_only": {
                    "type": "boolean",
                    "description": "Print only the scheduler's final summary JSON when supported.",
                    "default": True,
                },
                "solver_max_time_seconds": {
                    "type": "integer",
                    "description": "Optional solver max time override, 30-3600 seconds.",
                },
                "solver_no_improvement_seconds": {
                    "type": "integer",
                    "description": "Optional no-improvement stop threshold, 10-1800 seconds.",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Overall subprocess timeout, 30-3600 seconds.",
                    "default": DEFAULT_TIMEOUT_SECONDS,
                },
                "output_dir": {
                    "type": "string",
                    "description": "Optional absolute output directory under the scheduling project's output/ directory or /tmp.",
                },
            },
            "additionalProperties": False,
        },
    },
    max_result_size_chars=30000,
)

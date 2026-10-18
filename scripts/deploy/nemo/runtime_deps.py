"""Extras and import probes for a nemo release venv.

Auto-builds used to install only ``[nemo]``. The PD One selftest constructs
the MCP server (``tools.pd_one_safe_ops_mcp.build_server``) on that
interpreter, so a missing ``mcp`` extra fails cutover with
``No module named 'mcp'``. Hand builds hid this by constraining to a previous
freeze that already contained mcp. The extras list and the published-venv
import check make a clean auto-build fail here instead.

``[nemo]`` remains the production-host overlay and now composes
``hermes-agent[mcp]`` (same pattern as ``termux`` / ``[all]``), so a
build that still runs the previous release's ``.[nemo]``-only install
gets the SDK. Deploy also accepts a comma-separated extras list
(default ``nemo,mcp``) for extras that should not live inside ``[nemo]``.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

# Default ``--extra`` value. Comma-separated so build.sh / autodeploy can
# override the whole list without changing pyproject extras.
DEFAULT_EXTRAS = ("nemo", "mcp")
DEFAULT_EXTRA = ",".join(DEFAULT_EXTRAS)

# Modules the published release interpreter must import. ``mcp`` is the
# selftest ``build_server`` import; ``httpx2`` is the mcp extra's named pin
# (tools/mcp_tool.py looks it up by module name). ``requests`` / ``yaml``
# come from the nemo extra (gateway run + cron postcheck).
RUNTIME_IMPORTS = ("hermes_cli", "requests", "yaml", "mcp", "httpx2")

# Freeze names that must not disappear when a previous freeze had them.
# honcho-ai / pyyaml / requests are the [nemo] extra; mcp / httpx2 are [mcp].
RUNTIME_PACKAGES = ("honcho-ai", "pyyaml", "requests", "mcp", "httpx2")

_EXTRA_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def parse_extras(raw: str | None = None) -> tuple[str, ...]:
    """Split a comma-separated extras list. Empty / None uses the default."""
    text = DEFAULT_EXTRA if raw is None else str(raw)
    names: list[str] = []
    for part in text.split(","):
        name = part.strip()
        if not name:
            continue
        if not _EXTRA_NAME.fullmatch(name):
            raise ValueError(f"invalid extra: {name}")
        if name not in names:
            names.append(name)
    if not names:
        raise ValueError("extras list is empty")
    return tuple(names)


def extras_spec(extras: tuple[str, ...] | None = None) -> str:
    """``nemo,mcp`` for ``uv pip install -e '.[nemo,mcp]'``."""
    return ",".join(extras if extras is not None else parse_extras())


def import_statement(modules: tuple[str, ...] = RUNTIME_IMPORTS) -> str:
    return "import " + ", ".join(modules)


def check_runtime_imports(
    python: str | Path,
    *,
    cwd: Path | None = None,
    timeout: float = 30.0,
    modules: tuple[str, ...] = RUNTIME_IMPORTS,
) -> None:
    """``<python> -c 'import …'`` must succeed. Fail with the missing module."""
    argv = [str(python), "-c", import_statement(modules)]
    try:
        done = subprocess.run(
            argv,
            cwd=str(cwd) if cwd is not None else None,
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"release import check could not start {python}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"release import check timed out at {python}") from exc
    if done.returncode == 0:
        return
    detail = (done.stderr or done.stdout or "").strip() or f"exit {done.returncode}"
    raise RuntimeError(f"release import check failed at {python}: {detail}")


def check_release_imports(release: Path, *, timeout: float = 30.0) -> None:
    """Import the runtime modules from the published release interpreter."""
    python = release / ".venv" / "bin" / "python"
    if not os.access(python, os.X_OK):
        raise RuntimeError(f"release interpreter missing: {python}")
    check_runtime_imports(python, cwd=release, timeout=timeout)

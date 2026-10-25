"""Static checks that the dashboard terminal will not npm-install at runtime.

The websocket path (``/api/pty`` → ``_make_tui_argv``) installs Node dependencies
only when the release is writable and has no preinstall marker. A built release
must already contain ``node_modules``, the TUI bundle, and ``web_dist``.
"""

from __future__ import annotations

from pathlib import Path

from hermes_cli.source_build import FRONTEND_PREINSTALL_MARKER, runtime_npm_install_allowed


def static_problems(release: Path) -> list[str]:
    problems: list[str] = []
    if not (release / "hermes_cli" / "web_dist" / "index.html").is_file():
        problems.append("missing hermes_cli/web_dist/index.html")
    if not (release / "ui-tui" / "dist" / "entry.js").is_file():
        problems.append("missing ui-tui/dist/entry.js")
    if not (release / "node_modules").is_dir():
        problems.append("missing node_modules")
    if not (release / FRONTEND_PREINSTALL_MARKER).is_file():
        problems.append("missing frontend preinstall marker")
    elif runtime_npm_install_allowed(release):
        problems.append("runtime npm install is still allowed")
    return problems

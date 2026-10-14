"""Node dependencies for the dashboard browser terminal.

``/api/pty`` launches the embedded TUI through ``_make_tui_argv``. When that
launch is not already a prebuilt bundle, it prepares the ``ui-tui`` and ``web``
workspaces with ``npm ci`` (``scripts/build/node-deps.mjs``) into the release
root. Those workspaces pull in the packages the terminal compiles and runs
with (the TUI's React/Ink toolchain and the dashboard's xterm packages).

A release installed mode ``0555`` cannot accept that write. If the tree
already contains the install, launch skips ``npm``. If it does not, and the
release directory is not writable, the terminal is disabled with one warning.
Nothing is written outside the release: there is no implicit cache fallback.
"""

from __future__ import annotations

import errno
import json
import logging
import shutil
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Workspaces ``prepare_launch_dependencies`` installs for a dashboard terminal
# launch. ``apps/desktop`` is not part of this set.
TERMINAL_NODE_WORKSPACES = ("ui-tui", "web")

_PROBE_NAME = ".hermes-terminal-deps-probe"
_state_lock = threading.Lock()
_warned = False
_disabled = False


class TerminalDepsUnavailable(Exception):
    """Deps are missing and the release install directory cannot be written."""

    def __init__(self, install_dir: Path):
        self.install_dir = install_dir
        super().__init__(self.user_message)

    @property
    def user_message(self) -> str:
        return (
            "Chat unavailable: this release has no Node dependencies for the "
            f"dashboard terminal under {self.install_dir}, and that directory "
            "is not writable. Rebuild the release so it already contains "
            "node_modules (the ui-tui and web workspaces). The terminal stays "
            "disabled until then."
        )


def reset_terminal_deps_state() -> None:
    """Clear the one-warning latch. Tests only; a process keeps the latch."""
    global _warned, _disabled
    with _state_lock:
        _warned = False
        _disabled = False


def _package_dir(modules: Path, name: str) -> Path:
    return modules.joinpath(*name.split("/"))


def _workspace_installed(root: Path, modules: Path, workspace: str) -> bool:
    manifest_path = root / workspace / "package.json"
    try:
        name = json.loads(manifest_path.read_text(encoding="utf-8")).get("name")
    except (OSError, json.JSONDecodeError, UnicodeError):
        return False
    if not isinstance(name, str) or not name:
        return False
    return _package_dir(modules, name).joinpath("package.json").is_file()


def terminal_node_deps_present(root: Path) -> bool:
    """True when the terminal workspaces are already installed in ``root``.

    The node-deps receipt counts (a build with ``--reuse`` writes it inside
    ``node_modules``). Otherwise npm's install lock plus each workspace's
    linked manifest must be present. A receipt hash mismatch does not count
    as missing: a read-only release cannot refresh it.
    """
    modules = root / "node_modules"
    if (modules / ".hermes-node-deps").is_file():
        return True
    if not (modules / ".package-lock.json").is_file():
        return False
    return all(_workspace_installed(root, modules, name) for name in TERMINAL_NODE_WORKSPACES)


def directory_writable(path: Path) -> bool:
    """True when a file can be created in ``path``.

    Mode bits lie on some mounts, so this probes. It does not create ``path``.
    """
    if not path.is_dir():
        return False
    probe = path / _PROBE_NAME
    try:
        probe.touch()
    except OSError:
        return False
    try:
        probe.unlink()
    except OSError:
        return True
    return True


def _permission_denied(exc: BaseException) -> bool:
    if isinstance(exc, OSError) and exc.errno in {errno.EACCES, errno.EPERM, errno.EROFS}:
        return True
    parts = [str(exc)]
    stderr = getattr(exc, "stderr", None)
    if isinstance(stderr, bytes):
        parts.append(stderr.decode("utf-8", "replace"))
    elif isinstance(stderr, str):
        parts.append(stderr)
    text = "\n".join(parts).lower()
    return (
        "permission denied" in text
        or "eacces" in text
        or "read-only file system" in text
        or "erofs" in text
    )


def sealed_tui_entry(project_root: Path, entry: Path) -> bool:
    """True when the release already has a TUI bundle and cannot rebuild it."""
    return entry.is_file() and not directory_writable(project_root)


def _warn_once(install_dir: Path) -> None:
    global _warned, _disabled
    _disabled = True
    if _warned:
        return
    _warned = True
    logger.warning(
        "Dashboard terminal disabled: Node dependencies for the ui-tui and web "
        "workspaces are not installed under %s, and that directory is not writable. "
        "Install them at build time (`node scripts/build/node-deps.mjs --source <release> "
        "--workspace ui-tui --workspace web`) so the release contains node_modules. "
        "This warning is logged once; the terminal will not retry the install.",
        install_dir,
    )


def ensure_dashboard_terminal_deps(root: Path, *, install) -> bool:
    """Skip ``install`` when deps are already in the release.

    Returns False, without calling ``install`` and without raising, when the
    deps are missing and ``root`` is not writable. The warning is logged once
    per process. A later call does not probe, install, or warn again.

    ``install`` runs only when the release directory itself is writable.
    """
    global _disabled
    root = Path(root)
    with _state_lock:
        if _disabled:
            return False
        if terminal_node_deps_present(root):
            return True
        if not directory_writable(root):
            _warn_once(root)
            return False
    try:
        install()
    except (OSError, subprocess.CalledProcessError) as exc:
        if not _permission_denied(exc):
            raise
        with _state_lock:
            _warn_once(root)
        return False
    return True


def publish_terminal_node_modules(prepared_source: Path, release_repo: Path) -> Path:
    """Copy the build-time ``node_modules`` tree into the release repo.

    Symlinks are preserved. The destination is ``<release>/node_modules`` and
    nowhere else.
    """
    source = Path(prepared_source) / "node_modules"
    if not source.is_dir():
        raise FileNotFoundError(
            f"{source} is missing; run node-deps for the ui-tui and web workspaces before packaging"
        )
    destination = Path(release_repo) / "node_modules"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=False)
    return destination


def terminal_deps_install_command(source: Path) -> list[str]:
    """Argv tail for the build-time install (node is the caller’s binary)."""
    return [
        "scripts/build/node-deps.mjs",
        "--source", str(source),
        "--reuse",
        *(arg for workspace in TERMINAL_NODE_WORKSPACES for arg in ("--workspace", workspace)),
    ]

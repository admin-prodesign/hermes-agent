"""Make a staged release venv usable after ``mv`` onto the final path.

``uv venv --python <staging>/.python/bin/python3`` writes absolute interpreter
links, ``pyvenv.cfg home =``, and console-script shebangs into the staging
directory. After ``releases/.staging-<name>.<rand>`` is renamed to
``releases/<name>``, those paths are stale and cutover dies with
``release interpreter missing``.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

_SKIP_SUFFIXES = {".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe"}
_MAX_REWRITE_BYTES = 1_000_000


def _norm(path: Path) -> str:
    return os.path.normpath(str(path.resolve()))


def _is_under(path: str, root: str) -> bool:
    return path == root or path.startswith(root + os.sep)


def _retarget(path: str, old_root: str, new_root: str) -> str:
    if _is_under(path, old_root):
        return new_root + path[len(old_root):]
    return path


def _rewrite_symlink(path: Path, old_root: str, new_root: str) -> None:
    target = os.readlink(path)
    if not os.path.isabs(target):
        return
    updated = _retarget(target, old_root, new_root)
    if _is_under(updated, new_root):
        updated = os.path.relpath(updated, start=path.parent)
    if updated == target:
        return
    path.unlink()
    path.symlink_to(updated)


def _rewrite_text(path: Path, old_root: str, new_root: str) -> None:
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size == 0 or size > _MAX_REWRITE_BYTES:
        return
    if path.suffix.lower() in _SKIP_SUFFIXES:
        return
    try:
        data = path.read_bytes()
    except OSError:
        return
    old_b = old_root.encode("utf-8")
    if old_b not in data or b"\0" in data:
        return
    mode = path.stat().st_mode
    path.write_bytes(data.replace(old_b, new_root.encode("utf-8")))
    os.chmod(path, stat.S_IMODE(mode))


def relocate_venv(release: Path, staging: Path) -> None:
    """Rewrite venv paths that still point at ``staging`` so they match ``release``."""
    new_root = _norm(release)
    old_root = _norm(staging)
    venv = release / ".venv"
    if not venv.is_dir():
        raise RuntimeError(f"release venv missing: {venv}")
    if old_root != new_root:
        for dirpath, dirnames, filenames in os.walk(venv, followlinks=False):
            root = Path(dirpath)
            dirnames[:] = [name for name in dirnames if name != "__pycache__"]
            for name in filenames:
                path = root / name
                if path.is_symlink():
                    _rewrite_symlink(path, old_root, new_root)
                elif path.is_file():
                    _rewrite_text(path, old_root, new_root)


def check_release_interpreter(release: Path, *, timeout: float = 30.0) -> None:
    """``<release>/.venv/bin/python -c 'import sys'`` must run from the final path."""
    python = release / ".venv" / "bin" / "python"
    if not os.access(python, os.X_OK):
        raise RuntimeError(f"release interpreter missing: {python}")
    try:
        done = subprocess.run(
            [str(python), "-c", "import sys"],
            cwd=str(release),
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"release interpreter could not be started at {python}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"release interpreter timed out at {python}") from exc
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip() or f"exit {done.returncode}"
        raise RuntimeError(f"release interpreter failed at {python}: {detail}")


def publish_venv(release: Path, staging: Path, *, timeout: float = 30.0) -> None:
    relocate_venv(release, staging)
    check_release_interpreter(release, timeout=timeout)

"""Atomic ``releases/current`` symlink swap. The link target is the build name."""

from __future__ import annotations

import os
from pathlib import Path


def current_target(releases: Path) -> str | None:
    current = releases / "current"
    if current.is_symlink():
        return os.readlink(current)
    return None


def swap_current(releases: Path, build: str) -> str | None:
    """Point ``current`` at ``build``. Returns the previous relative target.

    ``os.replace`` replaces an existing symlink in one step on Linux.
    """
    releases.mkdir(parents=True, exist_ok=True)
    if not (releases / build).is_dir():
        raise FileNotFoundError(f"release is missing: {releases / build}")
    previous = current_target(releases)
    tmp = releases / f".current-{os.getpid()}"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(build, tmp)
    os.replace(tmp, releases / "current")
    return previous

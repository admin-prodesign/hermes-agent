"""Prune old release directories. Nemo's disk is nearly full, so two releases stay.

Kept: ``current``, the build the processes are actually running (``.running``,
which differs from ``current`` after a no-restart deploy), and after a deploy the
rollback target named by the current manifest. Audit directories are left alone.
"""

from __future__ import annotations

import os
import shutil
import stat
import time
from pathlib import Path

from scripts.deploy.nemo.layout import DEFAULT_KEEP_RECENT_RELEASES, audit_dir
from scripts.deploy.nemo.manifest import read_manifest
from scripts.deploy.nemo.release_swap import current_target

RUNNING_MARKER = ".running"
STAGING_STALE_S = 12 * 3600.0


def running_build(releases: Path) -> str | None:
    marker = releases / RUNNING_MARKER
    if not marker.is_file():
        return None
    name = marker.read_text(encoding="utf-8-sig").strip()
    return name or None


def set_running(releases: Path, build: str) -> None:
    tmp = releases / f"{RUNNING_MARKER}.tmp"
    tmp.write_text(build + "\n", encoding="utf-8")
    os.replace(tmp, releases / RUNNING_MARKER)


def previous_build(home: Path, current: str | None) -> str | None:
    if not current:
        return None
    previous = read_manifest(audit_dir(home, current) / "manifest.json").get("previous")
    return str(previous) if previous else None


def previous_symlink_target(releases: Path) -> str | None:
    link = releases / "previous"
    if link.is_symlink():
        name = os.readlink(link)
        return os.path.basename(name) if name else None
    return None


def audit_rollback_targets(home: Path) -> set[str]:
    root = home / "upgrade-audits"
    if not root.is_dir():
        return set()
    keep: set[str] = set()
    for manifest in root.glob("*/manifest.json"):
        previous = read_manifest(manifest).get("previous")
        if previous:
            keep.add(os.path.basename(str(previous)))
    return keep


def recent_release_names(releases: Path, keep_recent: int) -> set[str]:
    if keep_recent <= 0 or not releases.is_dir():
        return set()
    ranked: list[tuple[float, str]] = []
    for child in releases.iterdir():
        if not child.is_dir() or child.name.startswith(".") or child.is_symlink():
            continue
        ranked.append((child.stat().st_mtime, child.name))
    ranked.sort(reverse=True)
    return {name for _, name in ranked[:keep_recent]}


def keep_set(
    home: Path, releases: Path, *, with_previous: bool, keep_recent: int = DEFAULT_KEEP_RECENT_RELEASES,
) -> set[str]:
    current = current_target(releases)
    keep = {name for name in (current, running_build(releases)) if name}
    link_previous = previous_symlink_target(releases)
    if link_previous:
        keep.add(link_previous)
    keep |= audit_rollback_targets(home)
    manifest_previous = previous_build(home, current)
    if manifest_previous:
        keep.add(os.path.basename(manifest_previous))
    keep |= recent_release_names(releases, keep_recent)
    return {os.path.basename(name) for name in keep}


def _make_writable(path: Path) -> None:
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            target = Path(root) / name
            if target.is_symlink():
                continue
            mode = target.stat().st_mode
            target.chmod(mode | stat.S_IWUSR | (stat.S_IXUSR if target.is_dir() else 0))
    path.chmod(path.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)


def _remove(path: Path) -> None:
    _make_writable(path)
    shutil.rmtree(path)


def _abandoned_staging(path: Path, now: float, stale_s: float) -> bool:
    """A hand-run build.sh does not take the deploy lock, so only an old staging dir is removed."""
    return path.name.startswith(".staging-") and now - path.stat().st_mtime > stale_s


def prune(
    releases: Path, keep: set[str], *, now: float | None = None, staging_stale_s: float = STAGING_STALE_S,
    allow: bool = True,
) -> list[str]:
    """Remove release directories not in ``keep`` and abandoned staging. Call under the deploy lock."""
    if not allow or not releases.is_dir() or not keep:
        return []
    clock = time.time() if now is None else now
    removed: list[str] = []
    for child in sorted(releases.iterdir()):
        name = child.name
        if name == "current" or child.is_symlink() or not child.is_dir():
            continue
        if name.startswith(".") and not _abandoned_staging(child, clock, staging_stale_s):
            continue
        if name in keep:
            continue
        _remove(child)
        removed.append(name)
    return removed

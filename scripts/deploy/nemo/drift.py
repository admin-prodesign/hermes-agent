"""Drift check: does the live release still match the commit it was built from?

Every tracked file is compared by git blob hash against ``git ls-tree`` of the
deployed SHA. Untracked ``.py``/``.sh`` files outside build output are drift too
(a hand-dropped module would be imported). Systemd units that point at a release
other than ``current`` or the running build are reported, as is main moving ahead
of the deployed SHA for longer than ``max_lag_s``.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from scripts.deploy.nemo.source import Run, run_cmd

BUILD_OUTPUT_DIRS = frozenset({
    ".venv", ".python", "node_modules", "__pycache__", ".hermes", ".pytest_cache",
})
BUILD_OUTPUT_PATHS = ("hermes_cli/web_dist/", "ui-tui/dist/", "freeze.txt")
EXTRA_SUFFIXES = (".py", ".sh")
GIT_LINK_MODE = "120000"
GIT_SUBMODULE_MODE = "160000"


@dataclass
class DriftReport:
    sha: str
    modified: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)
    behind: str | None = None
    error: str | None = None

    @property
    def clean(self) -> bool:
        return not (self.modified or self.missing or self.extra or self.units or self.behind or self.error)

    def summary(self, limit: int = 20) -> str:
        if self.clean:
            return f"no drift from {self.sha}"
        lines = [f"drift from {self.sha}:"]
        if self.error:
            lines.append(f"  error: {self.error}")
        for label, items in (("modified", self.modified), ("missing", self.missing),
                             ("untracked", self.extra), ("unit", self.units)):
            for item in items[:limit]:
                lines.append(f"  {label}: {item}")
            if len(items) > limit:
                lines.append(f"  ... {len(items) - limit} more {label}")
        if self.behind:
            lines.append(f"  behind: {self.behind}")
        return "\n".join(lines)


def blob_hash(path: Path) -> str:
    data = os.readlink(path).encode("utf-8") if path.is_symlink() else path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tree_blobs(mirror: Path, sha: str, *, run: Run = run_cmd, timeout: float = 60.0) -> dict[str, tuple[str, str]]:
    completed = run(["git", "--git-dir", str(mirror), "ls-tree", "-r", "-z", "--full-tree", sha], timeout)
    if completed.returncode != 0:
        err = (completed.stderr or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(err or f"git ls-tree {sha} failed")
    blobs: dict[str, tuple[str, str]] = {}
    for record in (completed.stdout or b"").split(b"\0"):
        if not record:
            continue
        meta, _, name = record.partition(b"\t")
        mode, _kind, obj = meta.decode("ascii").split()
        blobs[name.decode("utf-8", "surrogateescape")] = (mode, obj)
    return blobs


def _is_build_output(rel: str) -> bool:
    parts = rel.split("/")
    if any(part in BUILD_OUTPUT_DIRS or part.endswith(".egg-info") for part in parts):
        return True
    return rel.startswith(BUILD_OUTPUT_PATHS)


def compare_tree(release: Path, blobs: dict[str, tuple[str, str]], report: DriftReport) -> None:
    for rel, (mode, obj) in sorted(blobs.items()):
        if mode == GIT_SUBMODULE_MODE:
            continue
        path = release / rel
        if not path.is_symlink() and not path.exists():
            report.missing.append(rel)
            continue
        if (mode == GIT_LINK_MODE) != path.is_symlink() or blob_hash(path) != obj:
            report.modified.append(rel)
    for root, dirs, files in os.walk(release):
        rel_root = os.path.relpath(root, release).replace(os.sep, "/")
        rel_root = "" if rel_root == "." else rel_root + "/"
        dirs[:] = [name for name in dirs if not _is_build_output(rel_root + name)]
        for name in files:
            rel = rel_root + name
            if rel not in blobs and name.endswith(EXTRA_SUFFIXES) and not _is_build_output(rel):
                report.extra.append(rel)
    report.extra.sort()


def stray_units(unit_dirs: list[Path], releases: Path, allowed: set[str]) -> list[str]:
    root = re.escape(str(releases.resolve()))
    pattern = re.compile(root + r"/([A-Za-z0-9._-]+)")
    found: list[str] = []
    for directory in unit_dirs:
        if not directory.is_dir():
            continue
        for unit in sorted(directory.glob("*.service")):
            for build in set(pattern.findall(unit.read_text(encoding="utf-8-sig"))):
                if build != "current" and build not in allowed:
                    found.append(f"{unit} -> {build}")
    return found


def main_lag(mirror: Path, sha: str, now: float, max_lag_s: float, *, remote: str = "origin",
             run: Run = run_cmd, timeout: float = 90.0, ref: str = "refs/nemo/drift-main") -> str | None:
    """``None`` when the deployed SHA is main, or main moved less than ``max_lag_s`` ago.

    Fetches into its own ref: the worker may be fetching the same mirror, and a shared
    ``FETCH_HEAD`` would race.
    """
    try:
        fetched = run(["git", "--git-dir", str(mirror), "fetch", "--no-tags", remote,
                       f"+refs/heads/main:{ref}"], timeout)
    except subprocess.TimeoutExpired:
        return "git fetch main timed out"
    if fetched.returncode != 0:
        return "could not fetch main"
    head = run(["git", "--git-dir", str(mirror), "log", "-1", "--format=%H %ct", ref], timeout)
    if head.returncode != 0:
        return "could not read main"
    main_sha, _, stamp = (head.stdout or b"").decode("ascii", "replace").strip().partition(" ")
    if main_sha.startswith(sha) or sha.startswith(main_sha):
        return None
    age = now - float(stamp or now)
    if age < max_lag_s:
        return None
    return f"main is {main_sha[:12]}, committed {int(age // 60)} min ago; live is {sha[:12]}"

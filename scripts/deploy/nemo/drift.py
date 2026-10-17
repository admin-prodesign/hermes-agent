"""Drift check: does the live release still match the commit it was built from?

Every tracked file is compared by git blob hash against ``git ls-tree`` of the
deployed SHA. Work-tree bytes are hashed with ``git hash-object --stdin-paths``,
one call per effective ``.gitattributes`` group (``text`` / ``eol`` / ``crlf`` /
``filter`` / ``ident`` from ``git check-attr --source`` of that SHA), so ``eol``
normalization matches checkout without one process per file. Untracked
``.py``/``.sh`` files outside build output are drift too (a hand-dropped module
would be imported). Systemd units that point at a release other than ``current``
or the running build are reported, as is main moving ahead of the deployed SHA
for longer than ``max_lag_s``.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from scripts.deploy.nemo.source import Run, run_cmd

BUILD_OUTPUT_DIRS = frozenset({
    ".venv", ".python", "node_modules", "__pycache__", ".hermes", ".pytest_cache",
})
BUILD_OUTPUT_PATHS = ("hermes_cli/web_dist/", "ui-tui/dist/", "freeze.txt")
EXTRA_SUFFIXES = (".py", ".sh")
GIT_LINK_MODE = "120000"
GIT_SUBMODULE_MODE = "160000"
ATTR_KEYS = ("text", "eol", "crlf", "filter", "ident")
GitRun = Callable[..., subprocess.CompletedProcess]


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


def _file_bytes(path: Path) -> bytes:
    return os.readlink(path).encode("utf-8") if path.is_symlink() else path.read_bytes()


def blob_hash(path: Path) -> str:
    """Raw git blob hash (no ``.gitattributes`` filters). Used only in tests."""
    data = _file_bytes(path)
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _git(argv: list[str], timeout: float, *, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_ATTR_NOSYSTEM"] = "1"
    return subprocess.run(
        argv, input=stdin, capture_output=True, timeout=timeout, check=False, env=env,
    )


def _git_error(completed: subprocess.CompletedProcess, fallback: str) -> RuntimeError:
    err = (completed.stderr or b"").decode("utf-8", "replace").strip()
    return RuntimeError(err or fallback)


def worktree_blob_hash(mirror: Path, rel: str, path: Path, *, timeout: float = 60.0) -> str:
    """Hash *path* as git would after applying attribute clean filters for *rel*.

    One-file form used as the parity reference and for symlinks. Regular files go
    through :func:`worktree_blob_hashes`.
    """
    completed = subprocess.run(
        ["git", "--git-dir", str(mirror), "hash-object", f"--path={rel}", "--stdin"],
        input=_file_bytes(path), capture_output=True, timeout=timeout, check=False,
    )
    if completed.returncode != 0:
        raise _git_error(completed, f"git hash-object --path={rel} failed")
    return (completed.stdout or b"").decode("ascii").strip()


def _parse_check_attr_z(data: bytes) -> dict[str, dict[str, str]]:
    parts = data.split(b"\0")
    parsed: dict[str, dict[str, str]] = {}
    index = 0
    while index + 2 < len(parts):
        path_b, attr_b, value_b = parts[index], parts[index + 1], parts[index + 2]
        index += 3
        if not path_b:
            continue
        path = path_b.decode("utf-8", "surrogateescape")
        parsed.setdefault(path, {})[attr_b.decode("ascii")] = value_b.decode(
            "utf-8", "surrogateescape")
    return parsed


def _attr_token(name: str, value: str) -> str | None:
    if value == "unspecified":
        return None
    if value == "unset":
        return f"-{name}"
    if value == "set":
        return name
    return f"{name}={value}"


def _synthetic_attributes(values: tuple[str, ...]) -> str:
    tokens: list[str] = []
    for name, value in zip(ATTR_KEYS, values, strict=True):
        token = _attr_token(name, value)
        if token:
            tokens.append(token)
    return ("* " + " ".join(tokens) + "\n") if tokens else ""


def attribute_groups(
    mirror: Path, sha: str, rels: list[str], *, timeout: float = 60.0, run: GitRun | None = None,
) -> dict[tuple[str, ...], list[str]]:
    """Group *rels* by the deployed SHA's effective ``text/eol/crlf/filter/ident``."""
    if not rels:
        return {}
    git = run or _git
    payload = b"\0".join(rel.encode("utf-8", "surrogateescape") for rel in rels) + b"\0"
    completed = git(
        ["git", "--git-dir", str(mirror), "check-attr", "--source", sha, "--stdin", "-z", *ATTR_KEYS],
        timeout, stdin=payload,
    )
    if completed.returncode != 0:
        raise _git_error(completed, f"git check-attr --source {sha} failed")
    parsed = _parse_check_attr_z(completed.stdout or b"")
    groups: dict[tuple[str, ...], list[str]] = {}
    for rel in rels:
        attrs = parsed.get(rel, {})
        key = tuple(attrs.get(name, "unspecified") for name in ATTR_KEYS)
        groups.setdefault(key, []).append(rel)
    return groups


def _hash_stdin_paths(
    mirror: Path, items: list[tuple[str, Path]], attr_file: Path, *, timeout: float, run: GitRun,
) -> dict[str, str]:
    payload = "".join(f"{path}\n" for _, path in items).encode("utf-8", "surrogateescape")
    completed = run(
        ["git", "--git-dir", str(mirror), "-c", f"core.attributesFile={attr_file}",
         "hash-object", "--stdin-paths"],
        timeout, stdin=payload,
    )
    if completed.returncode != 0:
        raise _git_error(completed, "git hash-object --stdin-paths failed")
    digests = (completed.stdout or b"").decode("ascii").split()
    if len(digests) != len(items):
        raise RuntimeError(
            f"git hash-object --stdin-paths returned {len(digests)} hashes for {len(items)} paths")
    return {rel: digest for (rel, _path), digest in zip(items, digests, strict=True)}


def worktree_blob_hashes(
    mirror: Path, sha: str, items: list[tuple[str, Path]], *, timeout: float = 60.0,
    run: GitRun | None = None,
) -> dict[str, str]:
    """Hash work-tree files, one ``hash-object --stdin-paths`` per attribute group.

    ``--stdin-paths`` cannot take ``--path``, so each group is hashed with a
    synthetic ``core.attributesFile`` of ``* <attrs>`` taken from
    :func:`attribute_groups`. Symlinks stay on the per-file ``--stdin`` path
    (blob bytes are the link text).
    """
    git = run or _git
    hashes: dict[str, str] = {}
    batched: list[tuple[str, Path]] = []
    for rel, path in items:
        if path.is_symlink() or "\n" in rel or "\n" in os.fspath(path):
            hashes[rel] = worktree_blob_hash(mirror, rel, path, timeout=timeout)
            continue
        batched.append((rel, path))
    if not batched:
        return hashes
    groups = attribute_groups(mirror, sha, [rel for rel, _ in batched], timeout=timeout, run=git)
    by_rel = {rel: path for rel, path in batched}
    with tempfile.TemporaryDirectory(prefix="nemo-drift-attrs-") as raw:
        attr_file = Path(raw) / "attributes"
        for key, rels in groups.items():
            attr_file.write_text(_synthetic_attributes(key), encoding="utf-8")
            hashes.update(_hash_stdin_paths(
                mirror, [(rel, by_rel[rel]) for rel in rels], attr_file, timeout=timeout, run=git,
            ))
    return hashes


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


def compare_tree(release: Path, blobs: dict[str, tuple[str, str]], report: DriftReport,
                 *, mirror: Path, sha: str, timeout: float = 60.0, run: GitRun | None = None) -> None:
    pending: list[tuple[str, Path, str, str]] = []
    for rel, (mode, obj) in sorted(blobs.items()):
        if mode == GIT_SUBMODULE_MODE:
            continue
        path = release / rel
        if not path.is_symlink() and not path.exists():
            report.missing.append(rel)
            continue
        pending.append((rel, path, mode, obj))
    try:
        hashed = worktree_blob_hashes(
            mirror, sha, [(rel, path) for rel, path, _, _ in pending], timeout=timeout, run=run)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        report.error = str(exc)
        return
    for rel, path, mode, obj in pending:
        on_disk = hashed.get(rel)
        if on_disk is None:
            report.error = f"{rel}: missing hash"
            return
        if (mode == GIT_LINK_MODE) != path.is_symlink() or on_disk != obj:
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

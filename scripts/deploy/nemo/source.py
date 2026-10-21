"""Fetch one commit from a bare mirror, with a tarball fallback.

A missing source raises ``SourceMissing`` before the caller publishes a release
directory. The historical failure was ``mkdir`` then ``tar`` under ``set -e``,
which left an empty release behind.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

Run = Callable[[list[str], float], subprocess.CompletedProcess]


def resolve_bare_mirror(path: Path) -> Path:
    """Normalize a bare-repo path (including a ``gitdir:`` pointer file)."""
    mirror = path.expanduser()
    if not mirror.is_absolute():
        mirror = mirror.resolve()
    else:
        try:
            mirror = mirror.resolve()
        except OSError:
            pass
    if mirror.is_file():
        for line in mirror.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("gitdir:"):
                gitdir = Path(line.split(":", 1)[1].strip())
                if not gitdir.is_absolute():
                    gitdir = (mirror.parent / gitdir).resolve()
                mirror = gitdir
                break
    return mirror


class SourceMissing(RuntimeError):
    """The build has no tree to install. Do not create a release directory."""


@dataclass(frozen=True)
class AcquireResult:
    method: str
    dest: Path
    sha: str


@dataclass(frozen=True)
class ProbeResult:
    status: str
    detail: str

    @property
    def exit_code(self) -> int:
        return {"ok": 0, "hang": 75, "error": 1}[self.status]


def _kill_group(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        proc.kill()
    else:
        sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
        try:
            os.killpg(proc.pid, sigkill)  # windows-footgun: ok — POSIX-only branch
        except (ProcessLookupError, PermissionError, AttributeError):
            proc.kill()
    try:
        proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def run_cmd(argv: list[str], timeout: float) -> subprocess.CompletedProcess:
    """Run ``argv`` in its own process group so a hung ``git fetch`` can be killed."""
    proc = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        raise
    return subprocess.CompletedProcess(argv, proc.returncode or 0, stdout, stderr)


def fetch_sha(mirror: Path, sha: str, timeout: float, *, remote: str = "origin", run: Run = run_cmd) -> str:
    """``git fetch <sha>`` against a bare mirror. ``timeout`` / ``failed`` / ``ok``."""
    argv = ["git", "--git-dir", str(mirror), "fetch", "--no-tags", remote, sha]
    try:
        completed = run(argv, timeout)
    except subprocess.TimeoutExpired:
        return "timeout"
    if completed.returncode != 0:
        return "failed"
    return "ok"


def _member_ok(member: tarfile.TarInfo, root: Path) -> None:
    parts = Path(member.name).parts
    if not member.name or member.name.startswith("/") or ".." in parts:
        raise SourceMissing(f"unsafe tar member: {member.name}")
    target = root / member.name
    if root != target and root not in target.resolve().parents and target.resolve() != root:
        raise SourceMissing(f"tar member escapes staging: {member.name}")
    if member.issym() or member.islnk():
        link_parts = Path(member.linkname).parts
        if member.linkname.startswith("/") or ".." in link_parts:
            raise SourceMissing(f"tar link escapes staging: {member.name}")


def _extract(tar: tarfile.TarFile, dest: Path) -> None:
    root = dest.resolve()
    for member in tar.getmembers():
        _member_ok(member, root)
    if sys.version_info >= (3, 12):
        tar.extractall(root, filter="data")
    else:
        tar.extractall(root)


def extract_tar_bytes(payload: bytes, dest: Path) -> None:
    import io

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as tar:
        _extract(tar, dest)


def extract_tarball(tarball: Path, dest: Path) -> None:
    if not tarball.is_file():
        raise SourceMissing(f"tarball missing: {tarball}")
    with tarfile.open(tarball, mode="r:*") as tar:
        _extract(tar, dest)


def export_archive(mirror: Path, sha: str, dest: Path, timeout: float, *, run: Run = run_cmd) -> None:
    argv = ["git", "--git-dir", str(mirror), "archive", "--format=tar", sha]
    try:
        completed = run(argv, timeout)
    except subprocess.TimeoutExpired as exc:
        raise SourceMissing(f"git archive {sha} timed out") from exc
    if completed.returncode != 0:
        err = (completed.stderr or b"").decode("utf-8", "replace").strip()
        raise SourceMissing(err or f"git archive {sha} failed")
    extract_tar_bytes(completed.stdout or b"", dest)


def promote_single_root(dest: Path) -> None:
    """GitHub tarballs wrap the tree in one directory. ``git archive`` does not."""
    if (dest / "pyproject.toml").is_file():
        return
    children = [p for p in dest.iterdir()]
    if len(children) == 1 and children[0].is_dir() and (children[0] / "pyproject.toml").is_file():
        inner = children[0]
        for child in inner.iterdir():
            child.rename(dest / child.name)
        inner.rmdir()


def tree_is_valid(dest: Path) -> bool:
    return (dest / "pyproject.toml").is_file()


def _wipe(dest: Path) -> None:
    if not dest.exists():
        return
    for child in dest.iterdir():
        if child.is_dir() and not child.is_symlink():
            import shutil
            shutil.rmtree(child)
        else:
            child.unlink()


def _try_archive(mirror: Path, sha: str, dest: Path, timeout: float, run: Run) -> bool:
    try:
        export_archive(mirror, sha, dest, timeout, run=run)
        promote_single_root(dest)
    except (SourceMissing, tarfile.TarError, OSError):
        _wipe(dest)
        return False
    if tree_is_valid(dest):
        return True
    _wipe(dest)
    return False


def acquire_source(
    *, sha: str, dest: Path, mirror: Path | None, tarball: Path | None,
    timeout: float, remote: str = "origin", run: Run = run_cmd,
) -> AcquireResult:
    """Fill an empty staging directory. Raise ``SourceMissing`` with ``dest`` empty.

    Fetch is attempted first. A hang or a fetch error still tries a local
    ``git archive`` (the mirror may already hold the commit), then the tarball.
    """
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        raise SourceMissing(f"staging directory is not empty: {dest}")
    mirror_note = "absent"
    if mirror is not None and mirror.exists():
        outcome = fetch_sha(mirror, sha, timeout, remote=remote, run=run)
        mirror_note = outcome
        if _try_archive(mirror, sha, dest, timeout, run):
            method = "mirror" if outcome == "ok" else "mirror-local"
            return AcquireResult(method, dest, sha)
    if tarball is not None and tarball.is_file():
        try:
            extract_tarball(tarball, dest)
            promote_single_root(dest)
        except (SourceMissing, tarfile.TarError, OSError) as exc:
            _wipe(dest)
            raise SourceMissing(f"tarball extract failed: {exc}") from exc
        if tree_is_valid(dest):
            return AcquireResult("tarball", dest, sha)
        _wipe(dest)
    raise SourceMissing(
        f"source missing for {sha}: mirror {mirror_note}, tarball "
        f"{tarball if tarball else 'unset'}"
    )


def probe_fetch(
    mirror: Path, sha: str, timeout: float, *, remote: str = "origin", run: Run = run_cmd,
) -> ProbeResult:
    """One bounded ``git fetch``. Does not write a release. Exit 75 means the fetch hung."""
    if not mirror.exists():
        return ProbeResult("error", f"mirror missing: {mirror}")
    outcome = fetch_sha(mirror, sha, timeout, remote=remote, run=run)
    if outcome == "ok":
        return ProbeResult("ok", f"fetch {sha} finished within {timeout:.0f}s")
    if outcome == "timeout":
        return ProbeResult("hang", f"git fetch {sha} still running after {timeout:.0f}s")
    return ProbeResult("error", f"git fetch {sha} failed")

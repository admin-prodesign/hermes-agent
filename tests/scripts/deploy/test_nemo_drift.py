"""Batched drift hashing: parity with per-file ``hash-object --path``, tamper detection, call count.

A fixture repo with mixed ``eol`` attributes is hashed both ways. ``*.ps1`` is
checked out as CRLF and ``*.py`` as LF so a single ``--path`` for every file
would disagree. Nothing here writes to the real Hermes home.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts.deploy.nemo.drift import (
    GIT_LINK_MODE, DriftReport, attribute_groups, compare_tree, tree_blobs,
    worktree_blob_hash, worktree_blob_hashes,
)

_GITATTRS = "*.py text eol=lf\n*.ps1 text eol=crlf\n"


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    done = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=30, check=True)
    return done.stdout.strip()


def _commit(work: Path, files: dict[str, bytes | str], message: str) -> str:
    for rel, payload in files.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, bytes):
            path.write_bytes(payload)
        else:
            path.write_text(payload, encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", message)
    return _git(work, "rev-parse", "HEAD")


@pytest.fixture
def mixed_eol_repo(tmp_path: Path):
    """Bare origin + mirror + a release tree with checkout-like line endings."""
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(bare), str(work))
    _git(work, "checkout", "-q", "-b", "main")
    files: dict[str, bytes | str] = {
        ".gitattributes": _GITATTRS,
        "a.py": "print(1)\n",
        "b.py": "print(2)\n",
        "pkg/c.py": "print(3)\n",
        "pkg/d.py": "print(4)\n",
        "one.ps1": "Write-Host 1\n",
        "two.ps1": "Write-Host 2\n",
        "tools/three.ps1": "Write-Host 3\n",
        "readme.bin": b"raw\x00bytes",
    }
    sha = _commit(work, files, "mixed eol")
    _git(work, "push", "-q", "origin", "main")
    mirror = tmp_path / "mirror.git"
    _git(tmp_path, "clone", "-q", "--mirror", str(bare), str(mirror))
    release = tmp_path / "release"
    for rel, (mode, _obj) in tree_blobs(mirror, sha).items():
        dest = release / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(subprocess.check_output(["git", "-C", str(work), "show", f"{sha}:{rel}"]))
        if rel.endswith(".ps1"):
            dest.write_bytes(dest.read_bytes().replace(b"\n", b"\r\n"))
        assert mode != GIT_LINK_MODE
    items = [(rel, release / rel) for rel, _meta in sorted(tree_blobs(mirror, sha).items())]
    return work, mirror, sha, release, items


@pytest.mark.platforms("linux", "macos")
def test_batched_hashes_match_per_file_on_mixed_eol(mixed_eol_repo) -> None:
    _work, mirror, sha, _release, items = mixed_eol_repo
    per_file = {rel: worktree_blob_hash(mirror, rel, path) for rel, path in items}
    batched = worktree_blob_hashes(mirror, sha, items)
    assert batched == per_file
    tree = {rel: obj for rel, (_mode, obj) in tree_blobs(mirror, sha).items()}
    assert batched == tree
    groups = attribute_groups(mirror, sha, [rel for rel, _ in items])
    assert len(groups) >= 3
    assert len(items) > len(groups)


@pytest.mark.platforms("linux", "macos")
def test_compare_tree_detects_tampered_py_and_ps1(mixed_eol_repo) -> None:
    _work, mirror, sha, release, _items = mixed_eol_repo
    blobs = tree_blobs(mirror, sha)
    clean = DriftReport(sha=sha)
    compare_tree(release, blobs, clean, mirror=mirror, sha=sha)
    assert clean.clean

    (release / "a.py").write_text("print('tampered')\n", encoding="utf-8")
    (release / "one.ps1").write_bytes(b"Write-Host tampered\r\n")
    report = DriftReport(sha=sha)
    compare_tree(release, blobs, report, mirror=mirror, sha=sha)
    assert set(report.modified) == {"a.py", "one.ps1"}
    assert not report.missing and not report.error


@pytest.mark.platforms("linux", "macos")
def test_batch_hash_object_calls_scale_with_attr_groups_not_files(mixed_eol_repo) -> None:
    _work, mirror, sha, _release, items = mixed_eol_repo
    groups = attribute_groups(mirror, sha, [rel for rel, _ in items])
    assert len(items) > len(groups)

    calls: list[list[str]] = []

    def spy(argv: list[str], timeout: float, *, stdin: bytes | None = None):
        calls.append(argv)
        return subprocess.run(
            argv, input=stdin, capture_output=True, timeout=timeout, check=False,
            env={**os.environ, "GIT_ATTR_NOSYSTEM": "1"},
        )

    hashed = worktree_blob_hashes(mirror, sha, items, run=spy)
    assert len(hashed) == len(items)
    hash_object = [argv for argv in calls if "hash-object" in argv]
    assert hash_object
    assert all("--stdin-paths" in argv for argv in hash_object)
    assert len(hash_object) == len(groups)
    assert len(hash_object) < len(items)

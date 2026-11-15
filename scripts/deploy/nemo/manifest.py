"""Per-build audit manifest under ``upgrade-audits/<build>/``."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.deploy.nemo.layout import SHA_RE, audit_dir

RELEASE_NAME_SHA_RE = re.compile(r"^hermes-agent-([0-9a-fA-F]{10})(?:-|$)")
AUTO_RELEASE_SUFFIX = "auto"
_SUFFIX_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = read_manifest(path)
    current.update(payload)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def utc_build_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_from_release_name(name: str) -> str | None:
    text = (name or "").strip()
    if not text:
        return None
    if SHA_RE.fullmatch(text):
        return text.lower()
    match = RELEASE_NAME_SHA_RE.match(text)
    if match:
        return match.group(1).lower()
    return None


def release_dir_name(sha: str, suffix: str = AUTO_RELEASE_SUFFIX) -> str:
    """Hand-built and auto-built directory name: ``hermes-agent-<sha10>-<suffix>``.

    A SHA shorter than 10 hex characters cannot form that name, so the bare SHA
    is kept (the same default ``build.sh`` used before this convention).
    """
    text = (sha or "").strip().lower()
    label = (suffix or "").strip()
    if not label or label in {".", ".."} or "/" in label or not _SUFFIX_RE.fullmatch(label):
        raise ValueError(f"invalid release suffix: {suffix!r}")
    if SHA_RE.fullmatch(text) and len(text) >= 10:
        return f"hermes-agent-{text[:10]}-{label}"
    if SHA_RE.fullmatch(text):
        return text
    raise ValueError(f"sha must be 7-40 hex characters, got {sha!r}")


def live_sha(home: Path, build: str | None) -> str | None:
    """SHA for a release directory: manifest first, then ``hermes-agent-<sha10>-`` naming."""
    if not build:
        return None
    basename = os.path.basename(build)
    manifest = read_manifest(audit_dir(home, basename) / "manifest.json")
    sha = manifest.get("sha")
    if sha:
        return str(sha).lower()
    return sha_from_release_name(basename)


def main_matches_live(main: str, live: str | None) -> bool:
    if not live:
        return False
    main_l = main.lower()
    live_l = live.lower()
    if len(live_l) < len(main_l):
        return main_l.startswith(live_l)
    return main_l == live_l


def resolve_sha_in_mirror(mirror: Path, sha: str, *, run, timeout: float = 30.0) -> str | None:
    """Expand a short SHA using the bare mirror; returns lowercase full SHA or ``None``."""
    text = (sha or "").strip().lower()
    if not text:
        return None
    if len(text) >= 40:
        return text
    done = run(
        ["git", "--git-dir", str(mirror), "rev-parse", "--verify", f"{text}^{{commit}}"],
        timeout,
    )
    if done.returncode != 0:
        return None
    full = (done.stdout or b"").decode("ascii", "replace").strip().lower()
    return full or None


def record_build_manifest(path: Path, *, sha: str, release_name: str, **fields: Any) -> None:
    payload: dict[str, Any] = {
        "sha": sha,
        "release_name": release_name,
        "build_time": utc_build_time(),
    }
    payload.update(fields)
    write_manifest(path, payload)

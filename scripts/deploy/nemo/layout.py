"""Paths for a nemo release. Every host-specific root is a parameter."""

from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT_PROFILES = ("pdone", "pdneo")
DEFAULT_EXTRA = "nemo"
DEFAULT_QUIET_S = 90.0
DEFAULT_POLL_S = 30.0
DEFAULT_FETCH_TIMEOUT_S = 90.0
DEFAULT_PROBE_TIMEOUT_S = 20.0
DEFAULT_HEALTH_TIMEOUT_S = 90.0
DEFAULT_HEALTH_INTERVAL_S = 2.0
DEFAULT_GATEWAY_HEALTH = "http://127.0.0.1:8644/health"
DEFAULT_DASHBOARD_HEALTH = "http://127.0.0.1:8765/api/health"
DEFAULT_KEEP_RECENT_RELEASES = 3
# Same relative path hermes_cli.source_build.FRONTEND_PREINSTALL_MARKER uses.
FRONTEND_MARKER_RELATIVE = Path(".hermes") / "frontend-preinstalled"
SHA_RE = re.compile(r"[0-9a-fA-F]{7,40}")
NEMO_PACKAGES = ("honcho-ai", "mcp", "pyyaml", "requests")


def resolve_hermes_home(explicit: Path | None = None) -> Path:
    """``--hermes-home``, else ``HERMES_HOME``, else the profile-aware default."""
    if explicit is not None:
        return explicit.expanduser().resolve()
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env).expanduser().resolve()
    from hermes_constants import get_hermes_home

    return Path(get_hermes_home())


def releases_dir(home: Path, explicit: Path | None = None) -> Path:
    return explicit.expanduser().resolve() if explicit is not None else home / "releases"


def audit_dir(home: Path, build: str) -> Path:
    return home / "upgrade-audits" / build


def profile_home(home: Path, name: str) -> Path:
    if name in {"", "default"}:
        return home
    return home / "profiles" / name


def pin_uv_cache(explicit: Path | None = None) -> Path:
    """Export a stable ``UV_CACHE_DIR`` so later builds reuse ``~/.cache/uv``."""
    if explicit is not None:
        path = explicit.expanduser()
    elif os.environ.get("UV_CACHE_DIR"):
        path = Path(os.environ["UV_CACHE_DIR"]).expanduser()
    else:
        path = Path.home() / ".cache" / "uv"
    path.mkdir(parents=True, exist_ok=True)
    os.environ["UV_CACHE_DIR"] = str(path.resolve())
    return path.resolve()


def valid_sha(sha: str) -> bool:
    return bool(SHA_RE.fullmatch(sha or ""))

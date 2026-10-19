"""Paths for a nemo release. Every host-specific root is a parameter."""

from __future__ import annotations

import os
import re
from pathlib import Path

# PD Neo is the top-level/default Hermes profile (``$HERMES_HOME``), not
# ``profiles/pdneo``. Installed autodeploy units may still pass ``--profile pdneo``.
DEFAULT_PROFILES = ("pdone", "default")
TOP_LEVEL_PROFILE_ALIASES = frozenset({"", "default", "pdneo"})
DEFAULT_EXTRA = "nemo"
DEFAULT_QUIET_S = 90.0
DEFAULT_POLL_S = 30.0
DEFAULT_STALE_GOAL_S = 7 * 24 * 3600.0
DEFAULT_FETCH_TIMEOUT_S = 90.0
DEFAULT_PROBE_TIMEOUT_S = 20.0
DEFAULT_HEALTH_TIMEOUT_S = 90.0
DEFAULT_HEALTH_INTERVAL_S = 2.0
DEFAULT_RESTART_DELAY_S = 3.0
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
    if name in TOP_LEVEL_PROFILE_ALIASES:
        return home
    return home / "profiles" / name


def gateway_unit_name(profile: str, overrides: dict[str, str] | None = None) -> str:
    """``hermes gateway install`` naming, unless ``--gateway-unit PROFILE=UNIT`` overrides it."""
    if overrides and profile in overrides:
        return overrides[profile]
    if profile in TOP_LEVEL_PROFILE_ALIASES:
        return "hermes-gateway.service"
    return f"hermes-gateway-{profile}.service"


def canary_order(profiles: tuple[str, ...]) -> tuple[str, ...]:
    """The top-level profile (PD Neo) first, then the others in the order given."""
    top = [name for name in profiles if name in TOP_LEVEL_PROFILE_ALIASES]
    return tuple(top + [name for name in profiles if name not in TOP_LEVEL_PROFILE_ALIASES])


def pairs(items: list[str] | None) -> dict[str, list[str]]:
    """``KEY=VALUE`` arguments grouped by key, values in order."""
    grouped: dict[str, list[str]] = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key or not value:
            raise ValueError(f"expected KEY=VALUE, got {item!r}")
        grouped.setdefault(key, []).append(value)
    return grouped


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

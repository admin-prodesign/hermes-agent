"""Locate the deployed Hermes release without hardcoding a profile home.

Cron and webhook entry points live under ``$HERMES_HOME/scripts`` and are not
the release tree. Callers that can run as either a release module or one of
those profile copies use this module to find ``runtime/current`` or
``releases/current`` and to resolve a Hermes home when the release package is
not on ``sys.path``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# A profile copy of this file runs with sys.path[0] set to $HERMES_HOME/scripts,
# which cannot see the release tree. The router then passes an explicit home
# parsed from notification-routes.json, so the platform default is unused.
try:
    from hermes_constants import get_hermes_home
except ImportError:
    get_hermes_home = None

_ROUTER_MARKER = Path("scripts") / "pd_one_notification_router.py"


def resolve_hermes_home(explicit: Path | None = None) -> Path:
    """Profile home. ``explicit`` wins, then ``HERMES_HOME``, then the platform default."""
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("HERMES_HOME", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    if get_hermes_home is None:
        raise RuntimeError(
            "HERMES_HOME is unset and hermes_constants is not importable"
        )
    return Path(get_hermes_home())


def candidate_release_roots() -> list[Path]:
    """Release checkouts in preference order, including ones that are not installed."""
    roots: list[Path] = []
    env = os.environ.get("HERMES_AGENT_DIR", "").strip()
    if env:
        roots.append(Path(env).expanduser())
    home = resolve_hermes_home()
    roots.append(home / "runtime" / "current")
    roots.append(home / "releases" / "current")
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            key = str(root.resolve())
        except OSError:
            key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def resolve_release_root() -> Path | None:
    """First candidate that contains the notification router, else None."""
    for root in candidate_release_roots():
        if (root / _ROUTER_MARKER).is_file():
            return root
    return None


def log_fallback(detail: str) -> None:
    """Cron captures stderr. Logging is not configured for these profile scripts."""
    print(f"hermes release script: {detail}", file=sys.stderr)

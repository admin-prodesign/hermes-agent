"""Refuse a nemo release that would serve the desktop webapp unbuilt.

The gateway mounts ``apps/desktop/dist-webapp`` from the release it is running
(``hermes_cli.webapp.webapp_dist_dir``). ``webapp.enabled`` turns that listener
on. Without ``index.html`` the listener answers that the Webapp is not built.
``build.sh`` compiles the bundle; this check stops publish and cutover when a
profile has the webapp on and the file is not there.
"""

from __future__ import annotations

from pathlib import Path

from gateway.webapp_listener import webapp_settings
from hermes_constants import PROFILE_ID_RE

# ``webapp_dist_dir`` plus the file the listener requires before it will serve.
WEBAPP_BUNDLE_INDEX = Path("apps") / "desktop" / "dist-webapp" / "index.html"


def webapp_bundle_problem(release: Path, home: Path) -> str | None:
    """Why *release* must not go live for *home*, or None.

    None when no profile has the webapp on, and when ``index.html`` is a file.
    A profile whose config keeps the webapp off (missing, false, or invalid)
    does not require the bundle: the gateway would not serve it either.
    """
    enabled = _enabled_profiles(home)
    if not enabled:
        return None
    index = release / WEBAPP_BUNDLE_INDEX
    if index.is_file():
        return None
    return f"webapp.enabled is set ({', '.join(enabled)}) but {index} is missing"


def _enabled_profiles(home: Path) -> list[str]:
    names: list[str] = []
    if webapp_settings(home).enabled:
        names.append("default")
    root = home / "profiles"
    if not root.is_dir():
        return names
    for entry in sorted(root.iterdir()):
        if entry.name == "default" or not entry.is_dir():
            continue
        if PROFILE_ID_RE.fullmatch(entry.name) is None:
            continue
        if webapp_settings(entry).enabled:
            names.append(entry.name)
    return names

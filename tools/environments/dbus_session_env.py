"""Derive the current Linux user's session D-Bus address for cookie decryption and scoped spawns."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


def _user_bus_socket_path() -> Path:
    return Path(f"/run/user/{os.getuid()}/bus")


def _user_bus_socket_ready(bus_path: Path | None = None) -> bool:
    if sys.platform != "linux":
        return False
    path = bus_path if bus_path is not None else _user_bus_socket_path()
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISSOCK(metadata.st_mode) and metadata.st_uid == os.getuid()  # windows-footgun: ok — linux gate above


def current_user_dbus_session_bus_address() -> str | None:
    """``unix:path=/run/user/<uid>/bus`` when that socket exists and is owned by this process."""
    if not _user_bus_socket_ready():
        return None
    return f"unix:path={_user_bus_socket_path()}"


def ensure_user_dbus_session_in_environ() -> None:
    """If the session bus address is unset, attach this user's ``/run/user/<uid>/bus`` socket."""
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return
    address = current_user_dbus_session_bus_address()
    if address is None:
        return
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = address
    if not os.environ.get("XDG_RUNTIME_DIR"):
        os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"


def mcp_safe_dbus_session_bus_address() -> str | None:
    """Bus address safe to pass into MCP stdio children: only the canonical user socket path."""
    expected = f"unix:path=/run/user/{os.getuid()}/bus"
    current = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    if current is not None and current != expected:
        return None
    if not _user_bus_socket_ready():
        return None
    return expected
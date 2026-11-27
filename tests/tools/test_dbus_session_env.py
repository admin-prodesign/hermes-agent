"""Contracts for deriving the current user's session D-Bus address."""
from __future__ import annotations

import os
import socket

import pytest

from tools.environments import dbus_session_env as dbus_env


def _bind_user_bus(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    sock = socket.socket(socket.AF_UNIX)
    sock.bind(str(path))
    return sock


@pytest.mark.platforms("linux")
def test_ensure_user_dbus_fills_missing_bus_from_socket(tmp_path, monkeypatch):
    bus_path = tmp_path / "bus"
    sock = _bind_user_bus(bus_path)
    try:
        monkeypatch.setattr(dbus_env, "_user_bus_socket_path", lambda: bus_path)
        monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        dbus_env.ensure_user_dbus_session_in_environ()
        assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={bus_path}"
        assert os.environ["XDG_RUNTIME_DIR"] == f"/run/user/{os.getuid()}"
    finally:
        sock.close()
        bus_path.unlink(missing_ok=True)


@pytest.mark.platforms("linux")
def test_ensure_user_dbus_leaves_foreign_bus_untouched(tmp_path, monkeypatch):
    bus_path = tmp_path / "bus"
    sock = _bind_user_bus(bus_path)
    foreign = "unix:path=/tmp/other-bus"
    try:
        monkeypatch.setattr(dbus_env, "_user_bus_socket_path", lambda: bus_path)
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", foreign)
        dbus_env.ensure_user_dbus_session_in_environ()
        assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == foreign
    finally:
        sock.close()
        bus_path.unlink(missing_ok=True)


def test_mcp_safe_dbus_rejects_foreign_address(monkeypatch):
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/untrusted-bus")
    monkeypatch.setattr(dbus_env, "_user_bus_socket_ready", lambda bus_path=None: True)
    assert dbus_env.mcp_safe_dbus_session_bus_address() is None


@pytest.mark.platforms("linux")
def test_mcp_safe_dbus_accepts_canonical_address_when_socket_ready(monkeypatch):
    uid = os.getuid()
    expected = f"unix:path=/run/user/{uid}/bus"
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", expected)
    monkeypatch.setattr(dbus_env, "_user_bus_socket_ready", lambda bus_path=None: True)
    assert dbus_env.mcp_safe_dbus_session_bus_address() == expected
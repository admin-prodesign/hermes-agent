"""Replace fixed restart sleeps with systemd and HTTP health polling."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

Clock = Callable[[], float]
Sleep = Callable[[float], None]
UnitCheck = Callable[[str, bool], bool]


@dataclass(frozen=True)
class HealthCheck:
    name: str
    ok: bool
    detail: str


def body_healthy(status: int, payload: bytes) -> bool:
    """Gateway ``{"status": "ok"}`` and dashboard ``{"ok": true}`` both pass."""
    if status != 200:
        return False
    text = payload.decode("utf-8", "replace").strip()
    if text.lower() == "ok":
        return True
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    if data.get("ok") is True:
        return True
    return str(data.get("status", "")).lower() == "ok"


def gateway_socket_healthy(profile_home: Path, timeout: float) -> HealthCheck:
    label = f"gateway.sock:{profile_home}"
    try:
        from gateway.control_socket import identify_gateway
    except ImportError as exc:
        return HealthCheck(label, False, str(exc))
    try:
        payload = identify_gateway(profile_home, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 — health probe must not abort cutover polling
        return HealthCheck(label, False, str(exc))
    ok = isinstance(payload, dict) and payload.get("protocol") is not None
    detail = "identify ok" if ok else "no gateway identify response"
    return HealthCheck(label, ok, detail)


def http_healthy(url: str, timeout: float) -> HealthCheck:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = response.read(8192)
            status = getattr(response, "status", 200)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return HealthCheck(url, False, str(exc))
    ok = body_healthy(int(status), payload)
    return HealthCheck(url, ok, f"HTTP {status}")


def evaluate(
    units: list[tuple[str, bool]], urls: list[str], *,
    check_unit: UnitCheck, check_url: Callable[[str], HealthCheck],
    socket_homes: list[tuple[str, Path]] | None = None,
    socket_timeout: float = 5.0,
) -> list[HealthCheck]:
    checks: list[HealthCheck] = []
    for name, user in units:
        active = check_unit(name, user)
        checks.append(HealthCheck(name, active, "active" if active else "inactive"))
    for url in urls:
        checks.append(check_url(url))
    for label, home in socket_homes or []:
        check = gateway_socket_healthy(home, socket_timeout)
        checks.append(HealthCheck(f"{label}:{check.name}", check.ok, check.detail))
    return checks


def poll_until_healthy(
    units: list[tuple[str, bool]], urls: list[str], *,
    timeout_s: float, interval_s: float,
    check_unit: UnitCheck, check_url: Callable[[str], HealthCheck],
    clock_fn: Clock, sleep_fn: Sleep,
    socket_homes: list[tuple[str, Path]] | None = None,
    socket_timeout: float = 5.0,
) -> tuple[bool, list[HealthCheck]]:
    started = clock_fn()
    latest: list[HealthCheck] = []
    while True:
        latest = evaluate(
            units, urls, check_unit=check_unit, check_url=check_url,
            socket_homes=socket_homes, socket_timeout=socket_timeout,
        )
        if latest and all(item.ok for item in latest):
            return True, latest
        if not latest:
            return True, latest
        if clock_fn() - started >= timeout_s:
            return False, latest
        sleep_fn(interval_s)

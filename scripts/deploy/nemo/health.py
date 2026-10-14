"""Replace fixed restart sleeps with systemd and HTTP health polling."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
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
) -> list[HealthCheck]:
    checks: list[HealthCheck] = []
    for name, user in units:
        active = check_unit(name, user)
        checks.append(HealthCheck(name, active, "active" if active else "inactive"))
    for url in urls:
        checks.append(check_url(url))
    return checks


def poll_until_healthy(
    units: list[tuple[str, bool]], urls: list[str], *,
    timeout_s: float, interval_s: float,
    check_unit: UnitCheck, check_url: Callable[[str], HealthCheck],
    clock_fn: Clock, sleep_fn: Sleep,
) -> tuple[bool, list[HealthCheck]]:
    started = clock_fn()
    latest: list[HealthCheck] = []
    while True:
        latest = evaluate(units, urls, check_unit=check_unit, check_url=check_url)
        if latest and all(item.ok for item in latest):
            return True, latest
        if not latest:
            return True, latest
        if clock_fn() - started >= timeout_s:
            return False, latest
        sleep_fn(interval_s)

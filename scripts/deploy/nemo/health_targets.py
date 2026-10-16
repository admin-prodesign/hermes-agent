"""Resolve cutover health checks for a Hermes home (HTTP URLs, gateway sockets, units).

Defaults match nemo: PD Neo gateway and dashboard HTTP endpoints, plus a control-socket
check for profiles that expose no ``/health`` route (PD One LINE).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.deploy.nemo.layout import (
    DEFAULT_DASHBOARD_HEALTH,
    DEFAULT_GATEWAY_HEALTH,
    DEFAULT_PROFILES,
    profile_home,
    resolve_hermes_home,
)

_ENV_GATEWAY = "NEMO_DEPLOY_GATEWAY_HEALTH"
_ENV_DASHBOARD = "NEMO_DEPLOY_DASHBOARD_HEALTH"
_ENV_SOCKET_PROFILES = "NEMO_DEPLOY_SOCKET_PROFILES"
_ENV_EXTRA_UNITS = "NEMO_DEPLOY_HEALTH_UNITS"
_UNIT_RE = re.compile(r"^(?P<path>[^@]+)(?P<user>@user)?$")


@dataclass(frozen=True)
class HealthPlan:
    gateway_url: str
    dashboard_url: str
    socket_profiles: tuple[str, ...]
    extra_units: tuple[tuple[str, bool], ...]


def _load_deploy_health_yaml(home: Path) -> dict[str, Any]:
    path = home / "config.yaml"
    if not path.is_file():
        return {}
    try:
        from utils import fast_safe_load

        data = fast_safe_load(path.read_text(encoding="utf-8-sig"))
    except (ImportError, OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    deploy = data.get("deploy")
    if not isinstance(deploy, dict):
        return {}
    health = deploy.get("health")
    return health if isinstance(health, dict) else {}


def _parse_units(raw: str) -> tuple[tuple[str, bool], ...]:
    units: list[tuple[str, bool]] = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        match = _UNIT_RE.fullmatch(text)
        if not match:
            continue
        units.append((match.group("path"), bool(match.group("user"))))
    return tuple(units)


def _socket_profiles_from_yaml(health: dict[str, Any]) -> tuple[str, ...] | None:
    raw = health.get("socket_profiles")
    if raw is None:
        return None
    if isinstance(raw, str):
        names = [part.strip() for part in raw.split(",") if part.strip()]
        return tuple(names)
    if isinstance(raw, list):
        return tuple(str(item) for item in raw if str(item).strip())
    return None


def resolve_health_plan(home: Path | None) -> HealthPlan:
    resolved = home.expanduser().resolve() if home is not None else resolve_hermes_home(None)
    yaml_health = _load_deploy_health_yaml(resolved)

    gateway = (
        os.environ.get(_ENV_GATEWAY)
        or str(yaml_health.get("gateway_url") or "")
        or DEFAULT_GATEWAY_HEALTH
    )
    dashboard = (
        os.environ.get(_ENV_DASHBOARD)
        or str(yaml_health.get("dashboard_url") or "")
        or DEFAULT_DASHBOARD_HEALTH
    )

    socket_profiles = _socket_profiles_from_yaml(yaml_health)
    if socket_profiles is None:
        env_profiles = os.environ.get(_ENV_SOCKET_PROFILES)
        if env_profiles is not None:
            socket_profiles = tuple(name for name in env_profiles.split(",") if name.strip())
        else:
            socket_profiles = ("pdone", "default")

    extra_units: list[tuple[str, bool]] = []
    yaml_units = yaml_health.get("units")
    if isinstance(yaml_units, list):
        for item in yaml_units:
            if not isinstance(item, dict):
                continue
            path = item.get("path") or item.get("unit")
            if not path:
                continue
            extra_units.append((str(path), bool(item.get("user"))))
    env_units = os.environ.get(_ENV_EXTRA_UNITS, "").strip()
    if env_units:
        extra_units.extend(_parse_units(env_units))

    return HealthPlan(
        gateway_url=gateway,
        dashboard_url=dashboard,
        socket_profiles=socket_profiles,
        extra_units=tuple(extra_units),
    )


def socket_profile_homes(home: Path, profiles: tuple[str, ...]) -> list[tuple[str, Path]]:
    resolved = resolve_hermes_home(home)
    out: list[tuple[str, Path]] = [("neo", resolved)]
    seen = {resolved}
    for name in profiles:
        if name in {"", "default"}:
            path = resolved
        else:
            path = profile_home(resolved, name)
        if path in seen:
            continue
        seen.add(path)
        out.append((name, path))
    return out


def default_socket_profiles_for_cutover(explicit: tuple[str, ...], home: Path) -> tuple[str, ...]:
    if explicit:
        return explicit
    plan = resolve_health_plan(home)
    if plan.socket_profiles:
        return plan.socket_profiles
    return tuple(DEFAULT_PROFILES[:1])

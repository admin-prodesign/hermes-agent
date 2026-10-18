"""Disk, memory, swap, and thermal pressure on the nemo host."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Callable

from scripts.deploy.nemo.watchdogs.common import Finding, hermes_home, run_check, run_cmd

NAME = "host"
DISK_WARN = 85.0
DISK_CRIT = 90.0
MEM_MIN_AVAILABLE = 10.0
SWAP_WARN = 75.0
THERMAL_WARN = 80.0
THERMAL_CRIT = 90.0
_SENSOR_TEMP = re.compile(r"^(\S+)_input:\s*([0-9.]+)\s*$")


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def disk_findings(usage: shutil._ntuple_diskusage | tuple[int, int, int]) -> list[Finding]:
    total, used, _free = usage[0], usage[1], usage[2]
    if total <= 0:
        return []
    percent = 100.0 * used / total
    if percent <= DISK_WARN:
        return []
    severity = "crit" if percent > DISK_CRIT else "warn"
    return [
        Finding(
            "host:disk",
            severity,
            "disk usage high",
            {"used_percent": round(percent, 1), "threshold": DISK_CRIT if severity == "crit" else DISK_WARN},
        )
    ]


def parse_meminfo(text: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        parts = rest.split()
        if not parts:
            continue
        try:
            values[key] = int(parts[0])
        except ValueError:
            continue
    return values


def memory_findings(info: dict[str, int]) -> list[Finding]:
    total = info.get("MemTotal") or 0
    available = info.get("MemAvailable")
    if total <= 0 or available is None:
        return []
    percent = 100.0 * available / total
    if percent >= MEM_MIN_AVAILABLE:
        return []
    return [
        Finding(
            "host:memory",
            "crit",
            "MemAvailable below 10 percent",
            {"available_percent": round(percent, 1), "threshold": MEM_MIN_AVAILABLE},
        )
    ]


def swap_findings(info: dict[str, int]) -> list[Finding]:
    total = info.get("SwapTotal") or 0
    free = info.get("SwapFree")
    if total <= 0 or free is None:
        return []
    used_percent = 100.0 * (total - free) / total
    if used_percent <= SWAP_WARN:
        return []
    return [
        Finding(
            "host:swap",
            "warn",
            "swap usage high",
            {"used_percent": round(used_percent, 1), "threshold": SWAP_WARN},
        )
    ]


def parse_sensors(text: str) -> list[tuple[str, float]]:
    temps: list[tuple[str, float]] = []
    for line in text.splitlines():
        match = _SENSOR_TEMP.match(line.strip())
        if match and "temp" in match.group(1):
            temps.append((match.group(1), float(match.group(2))))
    return temps


def read_thermals(runner=None) -> list[tuple[str, float]]:
    root = Path("/sys/class/thermal")
    temps: list[tuple[str, float]] = []
    if root.is_dir():
        for zone in sorted(root.glob("thermal_zone*")):
            raw = zone / "temp"
            try:
                millideg = int(raw.read_text(encoding="utf-8-sig").strip())
            except (OSError, ValueError):
                continue
            temps.append((zone.name, millideg / 1000.0))
        if temps:
            return temps
    proc = (runner or run_cmd)(["sensors", "-u"], timeout=10)
    return parse_sensors(getattr(proc, "stdout", "") or "")


def thermal_findings(temps: list[tuple[str, float]]) -> list[Finding]:
    warn = _float_env("NEMO_WATCH_THERMAL_WARN_C", THERMAL_WARN)
    crit = _float_env("NEMO_WATCH_THERMAL_CRIT_C", THERMAL_CRIT)
    findings: list[Finding] = []
    for name, celsius in temps:
        if celsius <= warn:
            continue
        severity = "crit" if celsius > crit else "warn"
        findings.append(
            Finding(
                f"host:thermal:{name}",
                severity,
                "thermal threshold exceeded",
                {"zone": name, "celsius": round(celsius, 1), "threshold": crit if severity == "crit" else warn},
            )
        )
    return findings


def read_meminfo(path: Path | None = None) -> dict[str, int]:
    target = path or Path("/proc/meminfo")
    try:
        return parse_meminfo(target.read_text(encoding="utf-8-sig"))
    except OSError:
        return {}


def collect(
    *,
    home: Path | None = None,
    disk: tuple[int, int, int] | None = None,
    meminfo: dict[str, int] | None = None,
    thermals: list[tuple[str, float]] | None = None,
    sensors_runner: Callable | None = None,
) -> list[Finding]:
    root = home or hermes_home()
    usage = disk if disk is not None else tuple(shutil.disk_usage(root))
    info = meminfo if meminfo is not None else read_meminfo()
    temps = thermals if thermals is not None else read_thermals(sensors_runner)
    return [
        *disk_findings(usage),
        *memory_findings(info),
        *swap_findings(info),
        *thermal_findings(temps),
    ]


def main() -> int:
    return run_check(NAME, collect)


if __name__ == "__main__":
    raise SystemExit(main())

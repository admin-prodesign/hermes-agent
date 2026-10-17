"""HTTP health and gateway control-socket identify (every 2 minutes)."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from scripts.deploy.nemo.watchdogs.common import Finding, hermes_home, run_check

NAME = "gateway"
DEFAULT_GATEWAY_HEALTH = "http://127.0.0.1:8644/health"
DEFAULT_DASHBOARD_HEALTH = "http://127.0.0.1:8765/api/health"
Identify = Callable[[Path], dict[str, Any] | None]
HttpGet = Callable[[str], tuple[int | None, str | None]]


def _safe_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def http_status(url: str, timeout: float = 8.0) -> tuple[int | None, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return int(getattr(resp, "status", 200)), None
    except urllib.error.HTTPError as exc:
        return int(exc.code), "http_error"
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, "unreachable"


def raw_identify(home: Path, timeout: float = 2.0) -> dict[str, Any] | None:
    """One JSON line in, one out — same wire contract as gateway.control_socket."""
    path = home / "gateway.sock"
    if not path.exists():
        pointer = home / "gateway.sock.path"
        try:
            target = pointer.read_text(encoding="utf-8").strip() if pointer.is_file() else ""
        except OSError:
            target = ""
        path = Path(target) if target else path
    if not path.exists():
        return None
    request = json.dumps({"verb": "identify", "id": 1, "protocol": 1}).encode() + b"\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(path))
            sock.sendall(request)
            raw = sock.recv(65536)
    except OSError:
        return None
    try:
        response = json.loads(raw.partition(b"\n")[0].decode("utf-8") or "null")
    except ValueError:
        return None
    result = response.get("result") if isinstance(response, dict) and response.get("ok") else None
    return result if isinstance(result, dict) else None


def identify_home(home: Path, timeout: float = 2.0) -> dict[str, Any] | None:
    try:
        from gateway.control_socket import identify_gateway
    except ImportError:
        return raw_identify(home, timeout)
    return identify_gateway(home, timeout=timeout)


def probe_http(url: str, getter: HttpGet | None = None) -> Finding | None:
    status, error = (getter or http_status)(url)
    if status == 200:
        return None
    return Finding(
        f"http:{_safe_url(url)}",
        "crit",
        "health endpoint not 200",
        {"url": _safe_url(url), "status": status or 0, "error": error or "down"},
    )


def probe_socket(label: str, home: Path, identify: Identify | None = None) -> Finding | None:
    payload = (identify or identify_home)(home)
    if isinstance(payload, dict) and payload.get("protocol") is not None:
        return None
    return Finding(
        f"socket:{label}",
        "crit",
        "gateway control socket identify failed",
        {"profile": label},
    )


def socket_targets(home: Path) -> list[tuple[str, Path]]:
    raw = os.environ.get("NEMO_WATCH_SOCKET_PROFILES", "default,pdone")
    names = [part.strip() for part in raw.split(",") if part.strip()]
    out: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for name in names:
        path = home if name in {"", "default"} else home / "profiles" / name
        if path in seen:
            continue
        seen.add(path)
        out.append((name or "default", path))
    return out


def collect(
    *,
    home: Path | None = None,
    getter: HttpGet | None = None,
    identify: Identify | None = None,
) -> list[Finding]:
    root = home or hermes_home()
    urls = [
        os.environ.get("NEMO_WATCH_GATEWAY_HEALTH", DEFAULT_GATEWAY_HEALTH),
        os.environ.get("NEMO_WATCH_DASHBOARD_HEALTH", DEFAULT_DASHBOARD_HEALTH),
    ]
    findings: list[Finding] = []
    for url in urls:
        item = probe_http(url, getter)
        if item is not None:
            findings.append(item)
    for label, path in socket_targets(root):
        item = probe_socket(label, path, identify)
        if item is not None:
            findings.append(item)
    return findings


def main() -> int:
    return run_check(NAME, collect)


if __name__ == "__main__":
    raise SystemExit(main())

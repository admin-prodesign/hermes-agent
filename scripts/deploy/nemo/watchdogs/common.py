"""Shared helpers for nemo no-agent watchdogs.

A healthy tick prints nothing. Findings POST JSON to WEBHOOK_URL with
WEBHOOK_SENDER_KEY as a header. Edge-triggered: one alert per new or changed
fingerprint, one recovery notice on clear. Secrets and message bodies stay out
of the payload. stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

SCHEMA = "nemo.watchdog.alert.v1"
DEFAULT_HOST_LABEL = "nemo"
DEFAULT_SENDER_HEADER = "X-Webhook-Key"
WEBHOOK_URL_KEY = "WEBHOOK_URL"
WEBHOOK_KEY_NAME = "WEBHOOK_SENDER_KEY"
WEBHOOK_HEADER_NAME = "WEBHOOK_SENDER_HEADER"
MAX_BODY = 4000
_SECRET_RES = (
    re.compile(
        r"(?i)(token|api[_-]?key|authorization|password|passwd|secret|cookie)"
        r"(\s*[:=]\s*)([^\s,;\"']+)"
    ),
    re.compile(r"(?i)\b(bearer|bot)\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"[a-z]+://[^\s/:@]+:[^\s/@]+@"),
    re.compile(r"\b(sk|xai|ghp|gho|github_pat|xox[abpr]|crsr)[-_][A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)REPLACE_WITH_[A-Z0-9_]+"),
)


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env).expanduser().resolve()
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except ImportError:
        return (Path.home() / ".hermes").resolve()


def state_dir() -> Path:
    raw = os.environ.get("NEMO_WATCH_STATE_DIR")
    if raw:
        return Path(raw).expanduser()
    return hermes_home() / "watchdogs" / "state"


def webhook_env_path() -> Path:
    raw = os.environ.get("NEMO_WATCH_WEBHOOK_ENV")
    if raw:
        return Path(raw).expanduser()
    return hermes_home() / "watchdogs" / "webhook.env"


def host_label() -> str:
    return os.environ.get("NEMO_WATCH_HOST_LABEL", DEFAULT_HOST_LABEL)


def dry_run() -> bool:
    return "--dry-run" in sys.argv or os.environ.get("NEMO_WATCH_DRY_RUN") == "1"


def now() -> float:
    return time.time()


def iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or now(), tz=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def resolve_under_home(raw: str, home: Path | None = None) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return (home or hermes_home()) / path


def redact(text: str, limit: int = 300) -> str:
    value = str(text or "")
    for rx in _SECRET_RES:
        value = rx.sub(
            lambda m: (
                m.group(1)
                + (m.group(2) if m.lastindex and m.lastindex >= 2 else " ")
                + "<redacted>"
            )
            if m.lastindex
            else "<redacted>",
            value,
        )
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit] + ("…" if len(value) > limit else "")


def sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(k): sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value[:10]]
    return value


def fingerprint(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Finding:
    key: str
    severity: str
    title: str
    details: dict[str, Any] = field(default_factory=dict)

    def fp(self) -> str:
        payload = json.dumps(
            {"key": self.key, "severity": self.severity, "details": self.details},
            sort_keys=True,
            default=str,
        )
        return fingerprint(payload)


@dataclass(frozen=True)
class Event:
    key: str
    state: str
    severity: str
    title: str
    items: list[dict[str, Any]]
    fingerprint: str


class IncidentStore:
    """Per-check JSON state. Dedupe by fingerprint; recover when a key clears."""

    def __init__(self, name: str, directory: Path | None = None):
        root = directory or state_dir()
        root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(root, 0o700)
        except OSError:
            pass
        self.path = root / f"{name}.json"
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("incidents", {})

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self.data, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(tmp, self.path)

    def sync(self, findings: list[Finding]) -> list[Event]:
        events: list[Event] = []
        present = {item.key for item in findings}
        for item in findings:
            event = self._observe(item)
            if event is not None:
                events.append(event)
        for key in list(self.data["incidents"]):
            if key not in present:
                event = self._clear(key)
                if event is not None:
                    events.append(event)
        return events

    def _observe(self, item: Finding) -> Event | None:
        mark = item.fp()
        stamp = now()
        inc = self.data["incidents"].get(item.key)
        if inc is None or not inc.get("active"):
            self.data["incidents"][item.key] = {
                "active": True,
                "fingerprint": mark,
                "first": stamp,
                "last_alert": stamp,
                "last_seen": stamp,
                "severity": item.severity,
                "title": item.title,
            }
            return Event(
                item.key, "firing", item.severity, item.title, [item.details], mark
            )
        inc["last_seen"] = stamp
        if inc.get("fingerprint") == mark:
            return None
        inc.update(
            fingerprint=mark,
            last_alert=stamp,
            severity=item.severity,
            title=item.title,
            active=True,
        )
        return Event(item.key, "firing", item.severity, item.title, [item.details], mark)

    def _clear(self, key: str) -> Event | None:
        inc = self.data["incidents"].get(key)
        if not inc or not inc.get("active"):
            return None
        inc["active"] = False
        inc["resolved"] = now()
        title = f"{inc.get('title') or key} cleared"
        return Event(
            key,
            "resolved",
            "info",
            title,
            [{"key": key, "cleared": True}],
            str(inc.get("fingerprint") or ""),
        )


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw = stripped.split("=", 1)
        value = raw.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def webhook_cfg(path: Path | None = None) -> tuple[str, dict[str, str]]:
    env_path = path or webhook_env_path()
    try:
        stat = env_path.stat()
    except OSError as exc:
        raise RuntimeError(f"webhook env missing: {env_path.name}") from exc
    if stat.st_mode & 0o077:
        raise RuntimeError(f"{env_path.name} must be mode 600")
    values = load_env_file(env_path)
    url = values.get(WEBHOOK_URL_KEY, "")
    key = values.get(WEBHOOK_KEY_NAME, "")
    header = values.get(WEBHOOK_HEADER_NAME, DEFAULT_SENDER_HEADER) or DEFAULT_SENDER_HEADER
    headers = {header: key} if key else {}
    return url, headers


class WebhookPermanentError(RuntimeError):
    pass


def _alert_body(
    watchdog: str, severity: str, title: str, items: list[dict[str, Any]],
    *, state: str, key: str,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "host": host_label(),
        "watchdog": watchdog,
        "severity": severity,
        "state": state,
        "key": key,
        "title": redact(title, 160),
        "items": [sanitize(item) for item in items[:10]],
        "truncated_items": max(0, len(items) - 10),
        "sent_at": iso(),
    }


def post_alert(
    watchdog: str,
    severity: str,
    title: str,
    items: list[dict[str, Any]],
    *,
    state: str = "firing",
    key: str = "",
    opener: Callable[..., Any] | None = None,
) -> int | None:
    body = _alert_body(
        watchdog, severity, title, items, state=state, key=key or fingerprint(watchdog, title),
    )
    raw = json.dumps(body, ensure_ascii=False)
    while len(raw.encode()) > MAX_BODY and body["items"]:
        body["items"].pop()
        body["truncated_items"] += 1
        raw = json.dumps(body, ensure_ascii=False)
    if dry_run():
        sys.stderr.write("[dry-run] " + raw + "\n")
        return 0
    url, auth = webhook_cfg()
    if not url or "REPLACE_WITH" in url or url.rstrip("/") == "https://example.invalid/webhook":
        raise RuntimeError("webhook URL missing or still a placeholder")
    if not auth or any("REPLACE_WITH" in value for value in auth.values()):
        raise RuntimeError("webhook sender key missing or still a placeholder")
    headers = {"Content-Type": "application/json", "User-Agent": "nemo-watchdog/1", **auth}
    request = urllib.request.Request(url, data=raw.encode(), headers=headers, method="POST")
    urlopen = opener or urllib.request.urlopen
    last = "unknown"
    for attempt in range(3):
        try:
            with urlopen(request, timeout=15) as resp:
                status = int(getattr(resp, "status", 200))
                if 200 <= status < 300:
                    return status
                last = f"HTTP {status}"
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code in (400, 401, 403, 404, 410, 422):
                raise WebhookPermanentError(f"webhook delivery failed: {last}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = type(exc).__name__
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"webhook delivery failed: {last}")


Poster = Callable[..., Any]


def emit_events(
    name: str,
    findings: list[Finding],
    *,
    store: IncidentStore | None = None,
    poster: Poster | None = None,
) -> list[Event]:
    held = store or IncidentStore(name)
    events = held.sync(findings)
    held.save()
    send = poster or post_alert
    for event in events:
        send(
            name,
            event.severity,
            event.title,
            event.items,
            state=event.state,
            key=event.fingerprint or fingerprint(name, event.key, event.state),
        )
    return events


def run_cmd(
    argv: list[str],
    *,
    timeout: float = 15,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(argv, 1, "", type(exc).__name__)


def run_check(name: str, collect: Callable[[], list[Finding]]) -> int:
    try:
        emit_events(name, collect())
    except WebhookPermanentError:
        return 1
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        code = post_alert(
            "install-test",
            "info",
            "nemo watchdog webhook test",
            [{"note": "ignore; install check"}],
            key=fingerprint("install-test", iso()),
        )
        print("dry-run only" if dry_run() else f"test alert accepted: HTTP {code}")

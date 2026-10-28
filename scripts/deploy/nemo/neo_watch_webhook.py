"""Shared Neo Watch webhook URL resolution, auth, and supervisor-style alert payloads."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

LOG = logging.getLogger(__name__)

SCHEMA_SUPERVISOR = "neo-watch.alert.v1"
DEFAULT_NEO_WEBHOOK_URL = (
    "https://api2.cursor.sh/automations/webhook/5ced6052-fdb8-52d4-a44e-4a2ced14a6cf"
)
CORRELATION_PREFIX = "pdone-surface:"

_URL_ENV_KEYS = (
    "NEO_WATCH_WEBHOOK_URL",
    "BRIEFING_REPAIR_WEBHOOK_URL",
)
_BEARER_ENV_KEYS = (
    "NEO_WATCH_WEBHOOK_KEY",
    "BRIEFING_REPAIR_WEBHOOK_BEARER",
    "BRIEFING_REPAIR_WEBHOOK_TOKEN",
)
_HMAC_ENV_KEYS = (
    "BRIEFING_REPAIR_WEBHOOK_HMAC_SECRET",
    "NEO_WATCH_WEBHOOK_HMAC_SECRET",
)

_logged_missing_url = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now(dt: datetime | None = None) -> str:
    return (dt or _utc_now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def correlation_key(fingerprint: str) -> str:
    fp = fingerprint.strip()
    if fp.startswith(CORRELATION_PREFIX):
        return fp
    return f"{CORRELATION_PREFIX}{fp}"


def resolve_webhook_url() -> str | None:
    for key in _URL_ENV_KEYS:
        if key not in os.environ:
            continue
        value = os.environ.get(key, "").strip()
        return value or None
    return DEFAULT_NEO_WEBHOOK_URL


def resolve_bearer_token() -> tuple[str, str, str]:
    """Return (header_name, prefix, token)."""
    header = os.environ.get("NEO_WATCH_WEBHOOK_KEY_HEADER", "Authorization").strip() or "Authorization"
    prefix = os.environ.get("NEO_WATCH_WEBHOOK_KEY_PREFIX", "Bearer ")
    for key in _BEARER_ENV_KEYS:
        token = os.environ.get(key, "").strip()
        if token:
            return header, prefix, token
    return header, prefix, ""


def resolve_hmac_secret() -> str:
    for key in _HMAC_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def webhook_configured() -> bool:
    return resolve_webhook_url() is not None


def log_missing_webhook_once() -> None:
    global _logged_missing_url
    if _logged_missing_url:
        return
    if not any(os.environ.get(k, "").strip() for k in _URL_ENV_KEYS):
        LOG.info(
            "Neo webhook URL not set in %s; using built-in default automation endpoint",
            ", ".join(_URL_ENV_KEYS),
        )
    _logged_missing_url = True


def _cafile() -> str:
    paths = ssl.get_default_verify_paths()
    if paths.cafile:
        return paths.cafile
    if paths.capath:
        return paths.capath
    return "/etc/ssl/certs/ca-certificates.crt"


def build_auth_headers(body_bytes: bytes) -> dict[str, str]:
    header_name, prefix, token = resolve_bearer_token()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers[header_name] = f"{prefix}{token}" if prefix else token
    secret = resolve_hmac_secret()
    if secret:
        digest = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        headers["X-Hermes-Signature"] = f"sha256={digest}"
    return headers


def build_supervisor_alert_payload(
    *,
    fingerprint: str,
    findings: list[dict[str, Any]],
    severity: str,
    host: str,
    profile: str,
    first_seen: str | None,
    last_seen: str | None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_SUPERVISOR,
        "host": host,
        "profile": profile,
        "severity": severity,
        "fingerprint": fingerprint,
        "findings": findings,
        "first_seen": first_seen or iso_now(),
        "last_seen": last_seen or iso_now(),
        "correlation_key": correlation_key(fingerprint),
        "sent_at": iso_now(),
    }


def post_json_webhook(payload: dict[str, Any], *, dry_run: bool = False, url: str | None = None) -> bool:
    if dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return True
    target = (url or resolve_webhook_url() or "").strip()
    if not target:
        log_missing_webhook_once()
        LOG.warning("Neo webhook URL unavailable; skipping POST")
        return False
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    headers = build_auth_headers(body)
    request = urllib.request.Request(target, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30, context=ssl.create_default_context(cafile=_cafile())):
            return True
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        LOG.error("Neo webhook POST failed: %s", exc)
        return False


def fingerprint_for_findings(findings: list[dict[str, Any]], *, alertable_fn) -> str:
    parts: list[str] = []
    for raw in findings:
        if not isinstance(raw, dict) or not alertable_fn(raw):
            continue
        fid = str(raw.get("id") or "").strip()
        subject = str(raw.get("subject") or raw.get("title") or "").strip()
        parts.append(fid or subject)
    parts.sort()
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:32]
    return digest or "empty"


def max_severity(findings: list[dict[str, Any]], *, alertable_fn) -> str:
    order = {"critical": 3, "error": 2, "warning": 1, "info": 0}
    best = "warning"
    best_rank = -1
    for raw in findings:
        if not isinstance(raw, dict) or not alertable_fn(raw):
            continue
        sev = str(raw.get("severity") or "warning").strip().lower() or "warning"
        rank = order.get(sev, 0)
        if rank > best_rank:
            best_rank = rank
            best = sev
    return best

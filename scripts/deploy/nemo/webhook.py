"""Signed deploy requests: what CI sends and what the nemo listener accepts.

The signature is HMAC-SHA256 over ``<timestamp>.<body>``. A request outside the
timestamp window, with a different repository or ref, or with anything but a full
40-hex SHA is refused before it reaches the queue.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import subprocess
from dataclasses import dataclass
from typing import Callable

SIGNATURE_HEADER = "X-Hermes-Signature"
TIMESTAMP_HEADER = "X-Hermes-Timestamp"
SIGNATURE_PREFIX = "sha256="
DEFAULT_MAX_SKEW_S = 300.0
MAX_BODY_BYTES = 4096
FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")


class Rejected(Exception):
    """The request is not a deploy. ``status`` is the HTTP code the listener answers."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class DeployRequest:
    sha: str
    ref: str
    repository: str
    run_id: str


def signature(secret: bytes, timestamp: str, body: bytes) -> str:
    digest = hmac.new(secret, timestamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
    return SIGNATURE_PREFIX + digest


def signed_headers(secret: bytes, body: bytes, now: float) -> dict[str, str]:
    timestamp = str(int(now))
    return {
        "Content-Type": "application/json",
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_HEADER: signature(secret, timestamp, body),
    }


def request_body(sha: str, ref: str, repository: str, run_id: str) -> bytes:
    payload = {"sha": sha, "ref": ref, "repository": repository, "run_id": run_id}
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def verify_signature(
    secret: bytes, timestamp: str | None, sig: str | None, body: bytes, now: float,
    max_skew_s: float = DEFAULT_MAX_SKEW_S,
) -> None:
    if not secret:
        raise Rejected(503, "listener has no secret")
    if not timestamp or not sig:
        raise Rejected(401, "missing signature headers")
    try:
        sent = float(timestamp)
    except ValueError as exc:
        raise Rejected(401, "bad timestamp") from exc
    if abs(now - sent) > max_skew_s:
        raise Rejected(401, "timestamp outside the allowed window")
    if not hmac.compare_digest(signature(secret, timestamp, body), sig):
        raise Rejected(401, "bad signature")


def parse_request(body: bytes, *, repository: str, ref: str) -> DeployRequest:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Rejected(400, "body is not JSON") from exc
    if not isinstance(data, dict):
        raise Rejected(400, "body is not a JSON object")
    sha = str(data.get("sha") or "").lower()
    if not FULL_SHA_RE.fullmatch(sha):
        raise Rejected(400, "sha must be a full 40-hex commit")
    if data.get("repository") != repository:
        raise Rejected(403, "repository is not the deployed repository")
    if data.get("ref") != ref:
        raise Rejected(403, f"ref is not {ref}")
    return DeployRequest(sha, ref, repository, str(data.get("run_id") or ""))


WhoisRun = Callable[[list[str]], subprocess.CompletedProcess]


def _whois(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, timeout=10, stdin=subprocess.DEVNULL, check=False)


def peer_tags(ip: str, *, run: WhoisRun = _whois) -> list[str] | None:
    """Tailscale tags on the node at ``ip``, or ``None`` when tailscale cannot answer."""
    try:
        completed = run(["tailscale", "whois", "--json", ip])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        data = json.loads(completed.stdout or b"{}")
    except json.JSONDecodeError:
        return None
    node = data.get("Node") if isinstance(data, dict) else None
    tags = node.get("Tags") if isinstance(node, dict) else None
    return [str(tag) for tag in tags] if isinstance(tags, list) else []


def require_peer_tag(ip: str, tag: str, *, run: WhoisRun = _whois) -> None:
    """Loopback peers are refused: behind ``tailscale serve`` the identity is not visible."""
    if ip.startswith("127.") or ip == "::1":
        raise Rejected(403, "tailscale identity is not visible on a loopback peer")
    tags = peer_tags(ip, run=run)
    if tags is None:
        raise Rejected(403, "tailscale whois did not answer")
    if tag not in tags:
        raise Rejected(403, f"peer is not {tag}")

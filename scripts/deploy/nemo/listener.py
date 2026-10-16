"""HTTP listener that turns a signed CI notification into a queued deploy.

It verifies and queues; it never builds, restarts, or reads profile state. The
worker (``autodeploy.py``) runs from a separate systemd unit. Bind it to loopback
behind ``tailscale serve`` (HTTPS), or to the tailnet address with
``--require-tailscale-tag`` so the peer's Tailscale identity is checked too.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.deploy.nemo.layout import resolve_hermes_home
from scripts.deploy.nemo.spool import enqueue, queue_dir, state_dir
from scripts.deploy.nemo.webhook import (
    DEFAULT_MAX_SKEW_S, MAX_BODY_BYTES, SIGNATURE_HEADER, TIMESTAMP_HEADER,
    Rejected, parse_request, require_peer_tag, verify_signature,
)

logger = logging.getLogger("nemo.listener")

DEFAULT_PORT = 8765
DEFAULT_REF = "refs/heads/main"
DEPLOY_PATH = "/deploy"


@dataclass
class ListenerConfig:
    secret: bytes
    queue: Path
    repository: str
    ref: str = DEFAULT_REF
    require_tag: str | None = None
    max_skew_s: float = DEFAULT_MAX_SKEW_S


class _SeenSignatures:
    """A replayed signature inside the timestamp window is answered without queueing."""

    def __init__(self, limit: int = 256) -> None:
        self._items: OrderedDict[str, None] = OrderedDict()
        self._limit = limit
        self._lock = threading.Lock()

    def add(self, sig: str) -> bool:
        with self._lock:
            if sig in self._items:
                return False
            self._items[sig] = None
            while len(self._items) > self._limit:
                self._items.popitem(last=False)
            return True


def read_secret(path: Path) -> bytes:
    return path.read_text(encoding="utf-8-sig").strip().encode("utf-8")


def handle_deploy(config: ListenerConfig, seen: _SeenSignatures, headers, body: bytes, peer: str, now: float) -> tuple[int, dict]:
    verify_signature(
        config.secret, headers.get(TIMESTAMP_HEADER), headers.get(SIGNATURE_HEADER), body, now,
        config.max_skew_s,
    )
    request = parse_request(body, repository=config.repository, ref=config.ref)
    if config.require_tag:
        require_peer_tag(peer, config.require_tag)
    if not seen.add(headers.get(SIGNATURE_HEADER)):
        return 200, {"duplicate": request.sha}
    enqueue(config.queue, request, peer=peer, now=now)
    logger.info("queued %s (run %s) from %s", request.sha, request.run_id or "-", peer)
    return 202, {"queued": request.sha}


def make_handler(config: ListenerConfig):
    seen = _SeenSignatures()

    class Handler(BaseHTTPRequestHandler):
        server_version = "hermes-deploy"
        sys_version = ""

        def _answer(self, status: int, payload: dict) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/healthz":
                self._answer(200, {"ok": True})
            else:
                self._answer(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path != DEPLOY_PATH:
                self._answer(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY_BYTES:
                self._answer(413, {"error": "body too large"})
                return
            body = self.rfile.read(length)
            peer = self.client_address[0]
            try:
                status, payload = handle_deploy(config, seen, self.headers, body, peer, time.time())
            except Rejected as exc:
                logger.warning("rejected %s from %s: %s", self.path, peer, exc.reason)
                status, payload = exc.status, {"error": exc.reason}
            self._answer(status, payload)

        def log_message(self, fmt: str, *args) -> None:
            logger.debug("%s " + fmt, self.client_address[0], *args)

    return Handler


def serve(config: ListenerConfig, bind: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((bind, port), make_handler(config))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nemo-deploy-listener")
    parser.add_argument("--hermes-home", default=None)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--secret-file", type=Path, default=None)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--ref", default=DEFAULT_REF)
    parser.add_argument("--require-tailscale-tag", default=None)
    parser.add_argument("--max-skew", type=float, default=DEFAULT_MAX_SKEW_S)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    secret_file = args.secret_file or state_dir(home) / "webhook-secret"
    secret = read_secret(secret_file)
    if len(secret) < 32:
        print(f"{secret_file}: secret must be at least 32 characters", file=sys.stderr)
        return 2
    config = ListenerConfig(
        secret=secret, queue=queue_dir(home), repository=args.repository, ref=args.ref,
        require_tag=args.require_tailscale_tag, max_skew_s=args.max_skew,
    )
    server = serve(config, args.bind, args.port)
    logger.info("listening on %s:%d for %s %s", args.bind, args.port, args.repository, args.ref)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

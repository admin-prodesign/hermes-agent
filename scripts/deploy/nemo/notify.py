"""Tell the nemo listener that a commit landed on main. Run by ``.github/workflows/nemo-deploy.yml``.

The secret and URL come from the environment (GitHub secrets), never argv, so they
do not show up in the process list or the workflow log.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request

from scripts.deploy.nemo.webhook import request_body, signed_headers

ATTEMPTS = 4


def post(url: str, secret: bytes, body: bytes, *, timeout: float = 20.0) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, method="POST")
    for key, value in signed_headers(secret, body, time.time()).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read(4096).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read(4096).decode("utf-8", "replace")


def notify(url: str, secret: bytes, body: bytes, *, sleep=time.sleep) -> int:
    """Retry network errors and 5xx. A 4xx is a configuration problem and fails at once."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            status, text = post(url, secret, body)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"attempt {attempt}: {exc}", file=sys.stderr)
        else:
            print(f"attempt {attempt}: HTTP {status} {text}")
            if 200 <= status < 300:
                return 0
            if status < 500:
                return 1
        if attempt < ATTEMPTS:
            sleep(2 ** attempt)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nemo-deploy-notify")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args(argv)
    url = os.environ.get("NEMO_DEPLOY_URL", "")
    secret = os.environ.get("NEMO_DEPLOY_HMAC_SECRET", "").strip().encode("utf-8")
    if not url or not secret:
        print("NEMO_DEPLOY_URL and NEMO_DEPLOY_HMAC_SECRET must be set", file=sys.stderr)
        return 2
    body = request_body(args.sha.lower(), args.ref, args.repository, args.run_id)
    return notify(url, secret, body)


if __name__ == "__main__":
    raise SystemExit(main())

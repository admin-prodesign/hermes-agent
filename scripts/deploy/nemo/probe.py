"""Whether ``git fetch <sha>`` against the bare mirror answers.

Exit 0 when the fetch finishes, 75 when it is still running at the timeout,
and 1 when the mirror is missing or git reports an error. This does not
create a release.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.deploy.nemo.layout import DEFAULT_PROBE_TIMEOUT_S, valid_sha
from scripts.deploy.nemo.source import probe_fetch


def run_probe(mirror: Path, sha: str, timeout: float, remote: str) -> int:
    if not valid_sha(sha):
        print("error: sha must be 7-40 hex characters", file=sys.stderr)
        return 1
    result = probe_fetch(mirror, sha, timeout, remote=remote)
    print(f"{result.status}: {result.detail}")
    return result.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="probe.py",
        description="Probe whether git fetch of one SHA hangs on the nemo bare mirror.",
    )
    parser.add_argument("--mirror", required=True, type=Path)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--timeout", type=float, default=DEFAULT_PROBE_TIMEOUT_S)
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args(argv)
    return run_probe(args.mirror, args.sha, args.timeout, args.remote)


if __name__ == "__main__":
    raise SystemExit(main())

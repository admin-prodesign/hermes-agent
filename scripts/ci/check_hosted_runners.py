#!/usr/bin/env python3
"""Fail if workflow files reintroduce a runner this fork does not have.

Upstream rebases copy in Blacksmith labels (``blacksmith-*``) and paid
larger-runner labels. Jobs that request them sit queued, because this
organization has neither. Hosted defaults live in the workflow ``runs-on``
expressions (``vars.RUNNER_*``); this check is the ratchet that keeps a
rebase from putting the old labels back.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / ".github"

# Substrings, case-insensitive. ``blacksmith`` also covers useblacksmith/*.
BANNED = (
    "blacksmith",
    "windows-latest-32-core",
    "windows-latest-32-arm-core",
)

SCAN_SUFFIXES = {".yml", ".yaml", ".md"}


def main() -> int:
    hits: list[str] = []
    for path in sorted(SCAN.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        for number, line in enumerate(text.splitlines(), 1):
            lowered = line.lower()
            if any(needle in lowered for needle in BANNED):
                hits.append(f"{rel}:{number}: {line.strip()}")
    if hits:
        print("Non-hosted runner labels found under .github:", file=sys.stderr)
        print("\n".join(hits), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

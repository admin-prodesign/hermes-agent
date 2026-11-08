"""Are the requirements a release declares for its extras installed in this interpreter?

Read from the installed ``hermes-agent`` metadata, so the list is whatever
``pyproject.toml`` declares for the extra at that SHA (self-references such as
``hermes-agent[messaging]`` are followed). Run it with the release's own
interpreter: ``build.sh`` does after the install, and the adapter gate does
again before cutover.
"""

from __future__ import annotations

import argparse
import sys
from importlib import metadata

from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

DIST = "hermes-agent"


def _mentions_extra(marker: Marker | None) -> bool:
    return marker is not None and "extra" in str(marker)


def declared(extras: list[str], *, dist: str = DIST) -> list[Requirement]:
    """Base requirements plus those of ``extras`` (transitively), for this platform."""
    own = canonicalize_name(dist)
    reqs = [Requirement(text) for text in metadata.requires(dist) or []]
    chosen: dict[str, Requirement] = {}
    for req in reqs:
        if not _mentions_extra(req.marker) and (req.marker is None or req.marker.evaluate({"extra": ""})):
            chosen.setdefault(str(req), req)
    pending = [canonicalize_name(name) for name in extras]
    seen: set[str] = set()
    while pending:
        extra = pending.pop()
        if extra in seen:
            continue
        seen.add(extra)
        for req in reqs:
            if not _mentions_extra(req.marker) or not req.marker.evaluate({"extra": extra}):
                continue
            if canonicalize_name(req.name) == own:
                pending.extend(canonicalize_name(name) for name in req.extras)
            else:
                chosen.setdefault(str(req), req)
    return list(chosen.values())


def missing(requirements: list[Requirement]) -> list[str]:
    problems: list[str] = []
    for req in requirements:
        try:
            version = metadata.version(req.name)
        except metadata.PackageNotFoundError:
            problems.append(f"{req.name} is not installed (declared {req})")
            continue
        if req.specifier and not req.specifier.contains(version, prereleases=True):
            problems.append(f"{req.name} {version} does not satisfy {req}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nemo-extras")
    parser.add_argument("--extra", action="append", default=[], help="repeatable or comma-separated")
    args = parser.parse_args(argv)
    extras = [name for item in args.extra for name in item.split(",") if name.strip()]
    try:
        problems = missing(declared(extras))
    except metadata.PackageNotFoundError:
        print(f"{DIST} is not installed in {sys.executable}", file=sys.stderr)
        return 1
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

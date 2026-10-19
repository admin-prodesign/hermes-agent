"""Atomic release links: ``current``, ``previous``, runtime links, and the ``.running`` marker.

``current`` targets the build name. Each change records the prior state of its path so
rollback puts back exactly what was there, including "absent".
"""

from __future__ import annotations

import os
from pathlib import Path

from scripts.deploy.nemo.units import STABLE_NAMES

RUNNING_MARKER = ".running"
RUNTIME_LINK = Path("runtime") / "current"


def current_target(releases: Path) -> str | None:
    current = releases / "current"
    if current.is_symlink():
        return os.readlink(current)
    return None


def _replace_symlink(link: Path, target: str) -> None:
    tmp = link.with_name(f".{link.name}-{os.getpid()}")
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(target, tmp)
    os.replace(tmp, link)


def swap_current(releases: Path, build: str) -> str | None:
    """Point ``current`` at ``build``. Returns the previous relative target.

    ``os.replace`` replaces an existing symlink in one step on Linux.
    """
    releases.mkdir(parents=True, exist_ok=True)
    if not (releases / build).is_dir():
        raise FileNotFoundError(f"release is missing: {releases / build}")
    previous = current_target(releases)
    _replace_symlink(releases / "current", build)
    return previous


def snapshot(path: Path) -> dict:
    if path.is_symlink():
        return {"path": str(path), "kind": "symlink", "value": os.readlink(path)}
    if path.is_file():
        return {"path": str(path), "kind": "file", "value": path.read_text(encoding="utf-8-sig")}
    return {"path": str(path), "kind": "absent", "value": ""}


def restore(record: dict) -> None:
    path = Path(record["path"])
    kind = record["kind"]
    if kind == "symlink":
        _replace_symlink(path, str(record["value"]))
    elif kind == "file":
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(str(record["value"]), encoding="utf-8")
        os.replace(tmp, path)
    elif path.is_symlink() or path.is_file():
        path.unlink()


def retarget(link: Path, releases: Path, release: Path) -> str | None:
    """New target for ``link`` when it points into a build under ``releases``; else ``None``.

    The sub-path inside the build and the link's absolute/relative style are kept.
    """
    raw = os.readlink(link)
    absolute = Path(os.path.normpath(raw if os.path.isabs(raw) else os.path.join(link.parent, raw)))
    for root in {releases.absolute(), releases.resolve()}:
        try:
            parts = absolute.relative_to(root).parts
        except ValueError:
            continue
        if not parts or parts[0] in STABLE_NAMES or parts[0].startswith("."):
            return None
        new = release.joinpath(*parts[1:])
        return str(new) if os.path.isabs(raw) else os.path.relpath(new, link.parent)
    return None


def point_links(
    releases: Path, build: str, *, running: bool, runtime_links: list[Path] | None = None,
) -> list[dict]:
    """Point ``previous`` at the old ``current``, runtime links and ``.running`` at ``build``,
    then ``current``. Returns prior states, ``current`` last. A failure restores what changed.
    """
    previous = current_target(releases)
    release = (releases / build).resolve()
    if not release.is_dir():
        raise FileNotFoundError(f"release is missing: {releases / build}")
    links = runtime_links if runtime_links is not None else [releases / RUNTIME_LINK]
    planned: list[tuple[Path, str, str]] = []
    if previous:
        planned.append((releases / "previous", "symlink", previous))
    for link in links:
        target = retarget(link, releases, release) if link.is_symlink() else None
        if target is not None:
            planned.append((link, "symlink", target))
    if running:
        planned.append((releases / RUNNING_MARKER, "file", build + "\n"))
    planned.append((releases / "current", "symlink", build))
    done: list[dict] = []
    try:
        for path, kind, value in planned:
            prior = snapshot(path)
            restore({"path": str(path), "kind": kind, "value": value})
            done.append(prior)
    except OSError:
        for prior in reversed(done):
            restore(prior)
        raise
    return done

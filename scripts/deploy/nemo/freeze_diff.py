"""Compare ``uv pip freeze`` output. A missing nemo pin fails the build."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement

from pm.pip_check import override_requirements
from scripts.deploy.nemo.layout import NEMO_PACKAGES

_SPEC_SEPS = ("===", "==", "~=", "!=", "<=", ">=", "[", "<", ">")


def parse_freeze(text: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-e"):
            continue
        if "==" not in line:
            continue
        name, version = line.split("==", 1)
        pins[_normalize(name)] = version.strip()
    return pins


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def _requirement_name(line: str) -> str:
    req = line.split(";", 1)[0].strip()
    for sep in _SPEC_SEPS:
        if sep in req:
            req = req.split(sep, 1)[0]
            break
    return _normalize(req)


def override_text(lock: Path) -> str:
    """``uv.lock`` [manifest] overrides as a ``uv pip install --overrides`` file.

    ``uv pip install`` re-resolves and ignores ``[tool.uv] override-dependencies``.
    PM already feeds the lock's overrides back through this seam.
    """
    lines = override_requirements(lock)
    return "\n".join(lines) + ("\n" if lines else "")


def override_names(text: str) -> set[str]:
    """Normalized package names from a ``uv pip --overrides`` file."""
    names: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name = _requirement_name(line)
        if name:
            names.add(name)
    return names


def _is_exact_pin(req: Requirement) -> bool:
    specs = list(req.specifier)
    return len(specs) == 1 and specs[0].operator in {"==", "==="}


def _extra_lines(extras_map: dict[str, object], extra: str) -> list[str]:
    wanted = _normalize(extra)
    for key, lines in extras_map.items():
        if _normalize(str(key)) == wanted:
            return [str(item) for item in (lines or [])]
    return []


def exact_pin_names(pyproject_text: str, extra: str | None = None) -> set[str]:
    """Exact ``==`` pins in ``[project]`` dependencies and the install extra.

    Self-references such as ``hermes-agent[mcp]`` are followed. Range pins
    (``>=`` / ``<``) stay in ``-c`` so unrelated packages remain held steady.
    """
    data = tomllib.loads(pyproject_text)
    project = data.get("project") or {}
    own = _normalize(str(project.get("name") or ""))
    extras_map = project.get("optional-dependencies") or {}
    names: set[str] = set()
    pending = [_normalize(extra)] if extra else []
    seen: set[str] = set()

    def absorb(lines: list[str]) -> None:
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            req = Requirement(line)
            name = _normalize(req.name)
            if own and name == own and req.extras:
                pending.extend(_normalize(item) for item in req.extras)
                continue
            if _is_exact_pin(req):
                names.add(name)

    absorb([str(item) for item in (project.get("dependencies") or [])])
    while pending:
        current = pending.pop()
        if not current or current in seen:
            continue
        seen.add(current)
        absorb(_extra_lines(extras_map, current))
    return names


def lock_package_versions(lock_text: str) -> dict[str, set[str]]:
    """Normalized name → versions recorded in ``uv.lock`` ``[[package]]`` tables."""
    data = tomllib.loads(lock_text)
    versions: dict[str, set[str]] = {}
    for package in data.get("package") or []:
        name = package.get("name")
        version = package.get("version")
        if name and version:
            versions.setdefault(_normalize(str(name)), set()).add(str(version))
    return versions


def lock_diff_names(freeze_text: str, lock_text: str) -> set[str]:
    """Freeze pins whose version is not one of the versions in this SHA's lock.

    A name only in the previous freeze is left in ``-c``: this pass does not
    invent a resolution for a new transitive that the lock never named.
    """
    locked = lock_package_versions(lock_text)
    drop: set[str] = set()
    for name, version in parse_freeze(freeze_text).items():
        versions = locked.get(name)
        if versions and version not in versions:
            drop.add(name)
    return drop


def constraint_drops(
    freeze_text: str,
    *,
    overrides_text: str | None = None,
    pyproject_text: str | None = None,
    extra: str | None = None,
    lock_text: str | None = None,
) -> set[str]:
    """Names the previous freeze must not pass as ``uv pip install -c``."""
    drop: set[str] = set()
    if overrides_text:
        drop |= override_names(overrides_text)
    if pyproject_text is not None:
        drop |= exact_pin_names(pyproject_text, extra=extra)
    if lock_text is not None:
        drop |= lock_diff_names(freeze_text, lock_text)
    return drop


def constraint_text(text: str, drop: set[str] | None = None) -> str:
    """Drop editable installs. ``uv pip install -c`` cannot use ``-e`` lines.

    ``drop`` removes packages this SHA re-pins: lock overrides, exact
    pyproject pins, and freeze lines whose version differs in ``uv.lock``.
    An old freeze can still name ``pillow==12.3.0`` or ``certifi==2026.5.20``
    after the new tree moved on; ``-c`` would make ``.[extra]`` unsatisfiable.
    """
    kept = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-e"):
            continue
        if drop and _requirement_name(line) in drop:
            continue
        kept.append(line)
    return "\n".join(kept) + ("\n" if kept else "")


def compare(old_text: str, new_text: str) -> tuple[str, list[str]]:
    """Return a unified-style report and the nemo packages that disappeared."""
    old, new = parse_freeze(old_text), parse_freeze(new_text)
    lines: list[str] = []
    for name in sorted(set(old) | set(new)):
        if name not in old:
            lines.append(f"+ {name}=={new[name]}")
        elif name not in new:
            lines.append(f"- {name}=={old[name]}")
        elif old[name] != new[name]:
            lines.append(f"~ {name}=={old[name]} -> {name}=={new[name]}")
    missing = [name for name in NEMO_PACKAGES if name in old and name not in new]
    if not lines:
        lines.append("(no pin changes)")
    return "\n".join(lines) + "\n", missing

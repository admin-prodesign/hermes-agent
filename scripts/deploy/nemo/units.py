"""Systemd units and drop-ins that run a release: find, render, validate, back up, restore.

A unit is rendered against the release it should run, not patched with the old
``current`` path: the live units may name a release ``current`` never pointed at
(a hand deploy, a rollback). Every ``<releases>/<build>`` reference moves to the
target release, whichever build it names; ``releases/current`` and the other
stable links stay. A release built by ``build.sh`` has no ``.hermes/bin`` wrapper,
so a reference to it moves to ``.venv/bin``. ``HERMES_RUNTIME_SHA`` is set to the
target SHA. Drop-ins (``<unit>.service.d/*.conf``) override ``ExecStart``,
``PATH``, ``VIRTUAL_ENV`` and ``PYTHONPATH``, so they are rendered the same way.
The original text of every file is kept in the build audit for rollback.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

STABLE_NAMES = frozenset({"current", "previous", "runtime"})
SHA_ENV = "HERMES_RUNTIME_SHA"
WRAPPER_ALIASES = ((".hermes/bin", ".venv/bin"),)
RESTART = "restart"
TRY_RESTART = "try-restart"
_EXEC_PREFIX = "@-:+!|"
_NAME = r"[A-Za-z0-9._-]+"
_TOKEN_END = r"(?=$|[/\s:;,\"'])"


@dataclass(frozen=True)
class UnitChange:
    path: str
    backup: str
    user: bool
    unit: str = ""
    restart: str = RESTART


@dataclass(frozen=True)
class UnitFile:
    path: Path
    unit: str
    user: bool


@dataclass(frozen=True)
class Target:
    """The release a unit should run. ``roots`` are the spellings of the releases root."""

    roots: tuple[str, ...]
    release: Path
    sha: str | None = None


@dataclass
class UnitPlan:
    file: UnitFile
    original: str
    rendered: str
    restart: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def is_user_unit(path: Path) -> bool:
    parts = path.parts
    return "user" in parts and "systemd" in parts


def unit_files(directories: list[Path]) -> list[UnitFile]:
    """Every ``*.service`` and ``*.service.d/*.conf`` under the directories, base unit first."""
    found: list[UnitFile] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.service")):
            if path.is_file():
                found.append(UnitFile(path, path.name, is_user_unit(path)))
        for path in sorted(directory.glob("*.service.d/*.conf")):
            if path.is_file():
                found.append(UnitFile(path, path.parent.name.removesuffix(".d"), is_user_unit(path)))
    return found


def root_spellings(releases: Path) -> tuple[str, ...]:
    """The releases root as configured, resolved, and as ``%h/...`` for user units."""
    spellings = {str(releases.absolute()), str(releases.resolve())}
    home = str(Path.home())
    spellings |= {"%h" + text[len(home):] for text in spellings if text.startswith(home + "/")}
    return tuple(sorted(spellings, key=len, reverse=True))


def target_for(releases: Path, build: str, sha: str | None = None) -> Target:
    return Target(roots=root_spellings(releases), release=(releases / build).resolve(), sha=sha or None)


def referenced_builds(text: str, roots: tuple[str, ...]) -> set[str]:
    names: set[str] = set()
    for root in roots:
        for match in re.finditer(re.escape(root) + r"/(" + _NAME + r")" + _TOKEN_END, text):
            name = match.group(1)
            if name not in STABLE_NAMES and not name.startswith("."):
                names.add(name)
    return names


def _move_release_refs(text: str, target: Target) -> str:
    release = str(target.release)

    def swap(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in STABLE_NAMES or name.startswith("."):
            return match.group(0)
        return release

    for root in target.roots:
        text = re.sub(re.escape(root) + r"/(" + _NAME + r")" + _TOKEN_END, swap, text)
    return text


def _alias_wrappers(text: str, release: Path) -> str:
    for missing, replacement in WRAPPER_ALIASES:
        if (release / missing).exists() or not (release / replacement).exists():
            continue
        pattern = re.escape(f"{release}/{missing}") + _TOKEN_END
        text = re.sub(pattern, f"{release}/{replacement}", text)
    return text


def _set_sha(text: str, sha: str | None) -> str:
    if not sha:
        return text

    def swap(match: re.Match[str]) -> str:
        return match.group(1) + sha[:len(match.group(2))]

    pattern = r"(?<![A-Za-z0-9_])(" + SHA_ENV + r"=)([0-9a-fA-F]{7,40})(?![0-9a-fA-F])"
    return re.sub(pattern, swap, text)


def render(text: str, target: Target, *, with_sha: bool = True) -> str:
    rendered = _alias_wrappers(_move_release_refs(text, target), target.release)
    return _set_sha(rendered, target.sha) if with_sha else rendered


def _directives(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";", "[")) or "=" not in line:
            continue
        key, _, value = line.partition("=")
        pairs.append((key.strip(), value.strip()))
    return pairs


def _split(value: str) -> list[str]:
    try:
        return shlex.split(value)
    except ValueError:
        return value.split()


def _expand(token: str) -> str:
    return str(Path.home()) + token[2:] if token.startswith("%h/") else token


def environment(text: str) -> dict[str, str]:
    """``Environment=`` assignments in file order; a later assignment wins."""
    env: dict[str, str] = {}
    for key, value in _directives(text):
        if key != "Environment":
            continue
        for item in _split(value):
            name, sep, val = item.partition("=")
            if sep:
                env[name] = val
    return env


def environment_files(text: str) -> list[tuple[Path, bool]]:
    """``EnvironmentFile=`` paths and whether a missing file is allowed (``-`` prefix)."""
    found: list[tuple[Path, bool]] = []
    for key, value in _directives(text):
        if key == "EnvironmentFile" and value:
            optional = value.startswith("-")
            found.append((Path(_expand(value.lstrip("-"))), optional))
    return found


def _under(token: str, release: Path) -> bool:
    return _expand(token).startswith(str(release) + "/") or _expand(token) == str(release)


def _exec_problems(value: str, release: Path) -> list[str]:
    tokens = _split(value.lstrip(_EXEC_PREFIX))
    errors: list[str] = []
    for index, token in enumerate(tokens):
        if not _under(token, release):
            continue
        path = Path(_expand(token))
        if not path.exists():
            errors.append(f"{token} does not exist")
        elif index == 0 and not os.access(path, os.X_OK):
            errors.append(f"{token} is not executable")
    return errors


def _env_problems(env: dict[str, str], release: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    venv = env.get("VIRTUAL_ENV")
    if venv and _under(venv, release) and not Path(_expand(venv)).is_dir():
        errors.append(f"VIRTUAL_ENV={venv} does not exist")
    for entry in (env.get("PYTHONPATH") or "").split(":"):
        if entry and _under(entry, release) and not Path(_expand(entry)).exists():
            errors.append(f"PYTHONPATH entry {entry} does not exist")
    for entry in (env.get("PATH") or "").split(":"):
        if entry and _under(entry, release) and not Path(_expand(entry)).is_dir():
            warnings.append(f"PATH entry {entry} does not exist")
    return errors, warnings


def problems(text: str, release: Path) -> tuple[list[str], list[str]]:
    """``(errors, warnings)`` for paths under ``release`` that the unit would run or load."""
    errors: list[str] = []
    for key, value in _directives(text):
        if key.startswith("Exec") and value:
            errors.extend(_exec_problems(value, release))
        elif key == "WorkingDirectory" and value and _under(value.lstrip("-~"), release):
            if not Path(_expand(value.lstrip("-~"))).is_dir():
                errors.append(f"WorkingDirectory={value} does not exist")
    env_errors, warnings = _env_problems(environment(text), release)
    return errors + env_errors, warnings


def plan_units(files: list[UnitFile], target: Target) -> list[UnitPlan]:
    """Files whose render differs from disk. SHA-only changes ``try-restart`` their unit."""
    plans: list[UnitPlan] = []
    for item in files:
        original = item.path.read_text(encoding="utf-8-sig")
        rendered = render(original, target)
        if rendered == original:
            continue
        moved = render(original, target, with_sha=False) != original
        plan = UnitPlan(item, original, rendered, RESTART if moved else TRY_RESTART)
        plan.errors, plan.warnings = problems(rendered, target.release)
        plans.append(plan)
    return plans


def _backup_name(path: Path) -> str:
    return f"{path.parent.name}--{path.name}.bak"


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.nemo-tmp")
    tmp.write_text(text, encoding="utf-8")
    if path.exists():
        os.chmod(tmp, path.stat().st_mode & 0o7777)
    os.replace(tmp, path)


def write_plans(plans: list[UnitPlan], backup_dir: Path) -> list[UnitChange]:
    """Back up, then write each rendered file. A failure restores what was already written."""
    changes: list[UnitChange] = []
    backup_dir.mkdir(parents=True, exist_ok=True)
    try:
        for plan in plans:
            backup = backup_dir / _backup_name(plan.file.path)
            backup.write_text(plan.original, encoding="utf-8")
            _write_atomic(plan.file.path, plan.rendered)
            changes.append(UnitChange(str(plan.file.path), str(backup), plan.file.user,
                                      plan.file.unit, plan.restart))
    except OSError:
        restore_units([change.__dict__ for change in changes])
        raise
    return changes


def restore_units(changes: list[dict]) -> list[str]:
    restored: list[str] = []
    for item in changes:
        path, backup = Path(item["path"]), Path(item["backup"])
        if not backup.is_file():
            continue
        _write_atomic(path, backup.read_text(encoding="utf-8-sig"))
        restored.append(str(path))
    return restored

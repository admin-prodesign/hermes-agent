"""Rewrite systemd units that embed the previous release path.

The current host has 15 such units. The count is not pinned: every ``*.service``
under the configured directories that contains the old absolute path is rewritten,
and the original text is kept in the build audit for rollback.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UnitChange:
    path: str
    backup: str
    user: bool


def is_user_unit(path: Path) -> bool:
    parts = path.parts
    return "user" in parts and "systemd" in parts


def units_embedding(directories: list[Path], old: str) -> list[Path]:
    found: list[Path] = []
    if not old or not old.startswith("/"):
        return found
    for directory in directories:
        if not directory.is_dir():
            continue
        found.extend(path for path in sorted(directory.glob("*.service")) if old in path.read_text(encoding="utf-8-sig"))
    return found


def rewrite_units(paths: list[Path], old: str, new: str, backup_dir: Path) -> list[UnitChange]:
    changes: list[UnitChange] = []
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        original = path.read_text(encoding="utf-8-sig")
        if old not in original:
            continue
        backup = backup_dir / (path.name + ".bak")
        backup.write_text(original, encoding="utf-8")
        path.write_text(original.replace(old, new), encoding="utf-8")
        changes.append(UnitChange(str(path), str(backup), is_user_unit(path)))
    return changes


def restore_units(changes: list[dict]) -> list[str]:
    restored: list[str] = []
    for item in changes:
        path, backup = Path(item["path"]), Path(item["backup"])
        if not backup.is_file():
            continue
        original = backup.read_text(encoding="utf-8-sig")
        path.write_text(original, encoding="utf-8")
        restored.append(str(path))
    return restored

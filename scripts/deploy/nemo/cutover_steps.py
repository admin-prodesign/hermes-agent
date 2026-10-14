"""Backup, symlink swap, unit rewrite, and config rewrite. Restart stays in cutover.sh."""

from __future__ import annotations

from pathlib import Path

from scripts.deploy.nemo.config_paths import rewrite_file
from scripts.deploy.nemo.release_swap import current_target, swap_current
from scripts.deploy.nemo.units import rewrite_units, units_embedding


def config_candidates(home: Path) -> list[Path]:
    found: list[Path] = []
    main = home / "config.yaml"
    if main.is_file():
        found.append(main)
    profiles = home / "profiles"
    if profiles.is_dir():
        found.extend(sorted(path for path in profiles.glob("*/config.yaml") if path.is_file()))
    return found


def default_unit_dirs() -> list[Path]:
    return [Path("/etc/systemd/system"), Path.home() / ".config" / "systemd" / "user"]


def apply_cutover(
    *, releases: Path, build: str, unit_dirs: list[Path], configs: list[Path], audit: Path,
) -> dict:
    """Swap ``current``, then rewrite units and configs that embed the old release path.

    Originals land in the audit directory before they are changed.
    """
    previous = current_target(releases)
    if not previous:
        raise RuntimeError(f"no releases/current symlink under {releases}")
    old_path = str((releases / previous).resolve())
    new_path = str((releases / build).resolve())
    if old_path == new_path:
        raise RuntimeError("current already points at the new build")
    swapped_from = swap_current(releases, build)
    unit_changes = rewrite_units(
        units_embedding(unit_dirs, old_path), old_path, new_path, audit / "units",
    )
    config_changes = []
    for path in configs:
        backup = audit / "configs" / f"{path.parent.name}-{path.name}"
        count = rewrite_file(path, old_path, new_path, backup)
        if count:
            config_changes.append({"path": str(path), "backup": str(backup), "replacements": count})
    return {
        "previous": swapped_from,
        "build": build,
        "releases": str(releases),
        "old_path": old_path,
        "new_path": new_path,
        "units": [change.__dict__ for change in unit_changes],
        "configs": config_changes,
    }

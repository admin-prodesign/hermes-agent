"""Restore the previous release symlink, unit files, and configs from an audit manifest."""

from __future__ import annotations

from pathlib import Path

from scripts.deploy.nemo.release_swap import swap_current
from scripts.deploy.nemo.units import restore_units


def apply_rollback(manifest: dict) -> dict:
    restored_units = restore_units(list(manifest.get("units") or []))
    restored_configs: list[str] = []
    for item in manifest.get("configs") or []:
        backup, path = Path(item["backup"]), Path(item["path"])
        if not backup.is_file():
            continue
        path.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
        restored_configs.append(str(path))
    previous = manifest.get("previous")
    releases = Path(manifest["releases"])
    if previous:
        swap_current(releases, str(previous))
    return {"units": restored_units, "configs": restored_configs, "current": previous}

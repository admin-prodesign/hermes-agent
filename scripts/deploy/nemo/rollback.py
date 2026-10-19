"""Restore the previous release links, unit files, and configs from an audit manifest."""

from __future__ import annotations

from pathlib import Path

from scripts.deploy.nemo.release_swap import restore, swap_current
from scripts.deploy.nemo.units import restore_units


def apply_rollback(manifest: dict) -> dict:
    restored_units = restore_units(list(manifest.get("units") or []))
    restored_configs: list[str] = []
    for item in manifest.get("configs") or []:
        backup, path = Path(item["backup"]), Path(item["path"])
        if not backup.is_file():
            continue
        restored = backup.read_text(encoding="utf-8-sig")
        path.write_text(restored, encoding="utf-8")
        restored_configs.append(str(path))
    previous = manifest.get("previous")
    links = list(manifest.get("links") or [])
    if links:
        for record in reversed(links):
            restore(record)
    elif previous:
        swap_current(Path(manifest["releases"]), str(previous))
    return {"units": restored_units, "configs": restored_configs, "current": previous,
            "links": [record["path"] for record in links]}

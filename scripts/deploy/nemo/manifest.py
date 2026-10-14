"""Per-build audit manifest under ``upgrade-audits/<build>/``."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = read_manifest(path)
    current.update(payload)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)

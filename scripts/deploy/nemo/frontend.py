"""Record that dashboard npm dependencies were installed at build time."""

from __future__ import annotations

from pathlib import Path

from hermes_cli.source_build import FRONTEND_PREINSTALL_MARKER


def mark_preinstalled(release: Path) -> Path:
    path = release / FRONTEND_PREINSTALL_MARKER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("preinstalled\n", encoding="utf-8")
    return path

"""Render units, rewrite configs, then move the release links. Restart stays in the rollout."""

from __future__ import annotations

from pathlib import Path

from scripts.deploy.nemo.config_paths import rewrite_file
from scripts.deploy.nemo.release_swap import current_target, point_links, restore
from scripts.deploy.nemo.units import UnitPlan, plan_units, restore_units, target_for, unit_files, write_plans


class UnitProblems(RuntimeError):
    """A rendered unit would run a path the new release does not have. Nothing was changed."""


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


def checked_plans(releases: Path, build: str, unit_dirs: list[Path], sha: str | None) -> list[UnitPlan]:
    plans = plan_units(unit_files(unit_dirs), target_for(releases, build, sha))
    errors = [f"{plan.file.path}: {error}" for plan in plans for error in plan.errors]
    if errors:
        raise UnitProblems("rendered units would not start:\n  " + "\n  ".join(errors))
    return plans


def _rewrite_configs(configs: list[Path], old_path: str, new_path: str, audit: Path) -> list[dict]:
    changes: list[dict] = []
    for path in configs:
        backup = audit / "configs" / f"{path.parent.name}-{path.name}"
        count = rewrite_file(path, old_path, new_path, backup)
        if count:
            changes.append({"path": str(path), "backup": str(backup), "replacements": count})
    return changes


def _undo(units: list[dict], configs: list[dict]) -> None:
    restore_units(units)
    for item in configs:
        restore({"path": item["path"], "kind": "file",
                 "value": Path(item["backup"]).read_text(encoding="utf-8-sig")})


def apply_cutover(
    *, releases: Path, build: str, unit_dirs: list[Path], configs: list[Path], audit: Path,
    sha: str | None = None, running: bool = False, runtime_links: list[Path] | None = None,
) -> dict:
    """Render every unit and drop-in against ``build``, rewrite configs, then move the links.

    Every rendered unit is checked before anything is written. Originals land in the audit
    directory first, and a failure part way restores what was already changed.
    """
    previous = current_target(releases)
    if not previous:
        raise RuntimeError(f"no releases/current symlink under {releases}")
    old_path = str((releases / previous).resolve())
    new_path = str((releases / build).resolve())
    if old_path == new_path:
        raise RuntimeError("current already points at the new build")
    if not (releases / build).is_dir():
        raise FileNotFoundError(f"release is missing: {releases / build}")
    plans = checked_plans(releases, build, unit_dirs, sha)
    unit_changes = [change.__dict__ for change in write_plans(plans, audit / "units")]
    config_changes: list[dict] = []
    try:
        config_changes = _rewrite_configs(configs, old_path, new_path, audit)
        links = point_links(releases, build, running=running, runtime_links=runtime_links)
    except Exception:
        _undo(unit_changes, config_changes)
        raise
    return {
        "previous": previous,
        "build": build,
        "releases": str(releases),
        "old_path": old_path,
        "new_path": new_path,
        "units": unit_changes,
        "configs": config_changes,
        "links": links,
        "warnings": [f"{plan.file.path}: {item}" for plan in plans for item in plan.warnings],
    }

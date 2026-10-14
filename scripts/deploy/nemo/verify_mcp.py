"""Check MCP server scripts inside a release import on the release interpreter.

This is the bounded replacement for the host ``verify_mcp.py``. It compiles each
configured stdio server that points into the release and imports the nemo extra
(``requests``, ``yaml``). It does not start a live tool call.
"""

from __future__ import annotations

from pathlib import Path

from scripts.deploy.nemo.layout import DEFAULT_PROFILES, profile_home


def _servers(config: dict) -> list[Path]:
    raw = config.get("mcp_servers")
    if not isinstance(raw, dict):
        return []
    scripts: list[Path] = []
    for spec in raw.values():
        if not isinstance(spec, dict):
            continue
        for arg in spec.get("args") or []:
            if isinstance(arg, str) and arg.endswith(".py"):
                scripts.append(Path(arg).expanduser())
    return scripts


def scripts_in_release(home: Path, release: Path, profiles: tuple[str, ...] = DEFAULT_PROFILES) -> list[Path]:
    from hermes_yaml import safe_load

    release_root = release.resolve()
    found: list[Path] = []
    configs = [home / "config.yaml"]
    configs.extend(profile_home(home, name) / "config.yaml" for name in profiles)
    for path in configs:
        if not path.is_file():
            continue
        data = safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            continue
        for script in _servers(data):
            if not script.is_file():
                continue
            resolved = script.resolve()
            if resolved == release_root or release_root in resolved.parents:
                found.append(resolved)
    return found


def compile_plan(python: str, scripts: list[Path]) -> list[tuple[str, ...]]:
    commands = [(python, "-c", "import requests, yaml")]
    commands.extend((python, "-m", "py_compile", str(script)) for script in scripts)
    return commands

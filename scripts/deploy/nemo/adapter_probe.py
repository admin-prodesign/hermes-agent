"""Dry start of one profile's gateway adapters, run by the NEW release's interpreter.

``adapter_gate`` spawns this once per profile with the environment the rendered
gateway unit would give the process (``HERMES_HOME``, ``PATH``, ``VIRTUAL_ENV``,
``PYTHONPATH`` ...) and the release as the working directory. It imports
``gateway.run`` (which loads the profile ``.env`` like a real start), discovers
plugins, loads the gateway config, and for each enabled platform runs the same
steps ``GatewayRunner._instantiate_adapter`` does short of ``connect()``: the
adapter's passive dependency probe (``check_fn``), its config validation, and
construction. Nothing connects, binds, or installs. The result is JSON in
``--out``; stdout is left to whatever the gateway import prints.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

_DETAIL_LIMIT = 400


def _short(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    return text[:_DETAIL_LIMIT]


def _check_registered(entry: Any, config: Any) -> str | None:
    if not entry.check_fn():
        hint = f" ({entry.install_hint})" if entry.install_hint else ""
        return f"dependency check failed{hint}"
    if entry.validate_config is not None and not entry.validate_config(config):
        return "config validation failed"
    entry.adapter_factory(config)
    return None


def _check_builtin(platform: Any, config: Any) -> str | None:
    from gateway.run import _BUILTIN_ADAPTERS, _builtin_adapter_import

    spec = _BUILTIN_ADAPTERS.get(platform)
    if spec is None:
        return "no adapter is registered for this platform"
    module, adapter_name, requirement, warning = spec
    adapter_cls, requirements_ok = _builtin_adapter_import(module, adapter_name, requirement)
    if not (requirements_ok() if callable(requirements_ok) else requirements_ok):
        return warning
    adapter_cls(config)
    return None


def check_platform(platform: Any, config: Any) -> str | None:
    """``None`` when the adapter would be created, else why not."""
    from gateway.platform_registry import platform_registry

    try:
        if platform_registry.is_registered(platform.value):
            entry = platform_registry.get(platform.value)
            if entry is None:
                return "registered, but the plugin failed to load"
            return _check_registered(entry, config)
        return _check_builtin(platform, config)
    except Exception as exc:  # health: allow BLE001 -- any adapter failure is the gate's answer, not a crash
        return _short(exc)


def probe() -> dict:
    report: dict = {"home": os.environ.get("HERMES_HOME", ""), "python": sys.executable,
                    "platforms": [], "failures": []}
    try:
        import gateway.run  # loads the profile .env exactly as a start does
        from gateway.config import Platform, load_gateway_config
        from hermes_cli.plugins import discover_plugins

        discover_plugins()
        config = load_gateway_config()
    except Exception as exc:  # health: allow BLE001 -- the traceback is reported in the JSON
        report["failures"].append({"platform": "*", "detail": _short(exc),
                                   "trace": traceback.format_exc(limit=5)[-2000:]})
        return report
    for platform, platform_config in config.platforms.items():
        if not platform_config.enabled or platform == Platform.LOCAL:
            continue
        problem = check_platform(platform, platform_config)
        if problem:
            report["failures"].append({"platform": platform.value, "detail": problem})
        else:
            report["platforms"].append(platform.value)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nemo-adapter-probe")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--extra", action="append", default=[])
    args = parser.parse_args(argv)
    import importlib.metadata

    from scripts.deploy.nemo.extras import DIST, declared, missing

    extras = [name for item in args.extra for name in item.split(",") if name.strip()]
    report = probe()
    try:
        report["missing"] = missing(declared(extras)) if extras else []
    except importlib.metadata.PackageNotFoundError:
        report["missing"] = [f"{DIST} is not installed in {sys.executable}"]
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1 if report["failures"] or report["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

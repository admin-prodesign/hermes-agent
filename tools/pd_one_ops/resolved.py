"""Config values a parent already resolved, read from the environment.

A helper started under ``pd_one.external.winrm_python`` (or any other external
interpreter) imports only this module for those values. This file does not
import the YAML or config loader: that interpreter does not have ruamel.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


class MissingResolvedValue(RuntimeError):
    """The parent did not pass a config value this helper needs."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"PD One helper was started without {name}. The parent must resolve "
            "pd_one config and pass it in the environment."
        )


def _raw(name: str) -> str:
    return os.environ.get(name, "").strip()


def require_path(name: str) -> Path:
    raw = _raw(name)
    if not raw:
        raise MissingResolvedValue(name)
    return Path(raw)


def profile_root() -> Path:
    return require_path("PD_ONE_PROFILE_ROOT")


def ledger_tools() -> Path:
    return require_path("PD_ONE_LEDGER_TOOLS")


def acl_tool() -> Path:
    return require_path("PD_ONE_ACL_TOOL")


def owner_mm_username() -> str:
    return os.environ.get("PD_ONE_OWNER_MM_USERNAME", "").strip()


def external_interpreter() -> bool:
    return _raw("PD_ONE_EXTERNAL_INTERPRETER") not in {"", "0"}


def load_named_module(path: Path, module_name: str, *, site: Path | None = None):
    """Load ``path`` as ``module_name``. ``site`` is an optional site-packages directory."""
    if site is not None and site.is_dir():
        text = str(site)
        if text not in sys.path:
            sys.path.append(text)
    parent = str(path.parent)
    if parent not in sys.path:
        sys.path.append(parent)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"PD One could not load {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_sqlsrv():
    """The ``sqlsrv_readonly`` module from ``PD_ONE_SQLSRV_READONLY``."""
    site_raw = _raw("PD_ONE_WINRM_SITE_PACKAGES")
    return load_named_module(
        require_path("PD_ONE_SQLSRV_READONLY"),
        "sqlsrv_readonly",
        site=Path(site_raw) if site_raw else None,
    )

"""Child-process launch for PD One tools.

A release is published read-only and its files need not carry an exec bit, so a
Python helper always runs as ``<interpreter> <script>``, never as the script
itself. An unset ``pd_one.external.<key>`` stops the launch with that key named,
instead of handing ``<unset pd_one.external.<key>>`` to the OS as a file name.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from tools.pd_one_ops.site_config import UNSET_MARK, MissingExternalConfig, external_path

RELEASE_ROOT = Path(__file__).resolve().parent.parent.parent


def unset_keys(argv: Iterable[Any]) -> list[str]:
    keys = []
    for item in argv:
        text = os.fspath(item) if isinstance(item, os.PathLike) else str(item)
        if text.startswith(UNSET_MARK):
            keys.append(text[len(UNSET_MARK):].rstrip(">"))
    return keys


def checked_argv(argv: Iterable[Any]) -> list[str]:
    """``argv`` as strings; raises :class:`MissingExternalConfig` for an unset external path."""
    items = [os.fspath(item) if isinstance(item, os.PathLike) else str(item) for item in argv]
    missing = unset_keys(items)
    if missing:
        raise MissingExternalConfig(missing[0])
    return items


def python_argv(script: Any, *args: Any, interpreter_key: Optional[str] = None) -> list[str]:
    """``[interpreter, script, *args]``; the interpreter is ``pd_one.external.<interpreter_key>``
    when named (it must be set), else the interpreter running this process."""
    interpreter = external_path(interpreter_key).require() if interpreter_key else Path(sys.executable)
    script_path = Path(os.fspath(script))
    if not script_path.is_file():
        raise FileNotFoundError(f"PD One helper script is missing: {script_path}")
    return checked_argv([interpreter, script_path, *args])


def child_env(base: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Environment for a PD One child: the served Hermes home, and the release on ``PYTHONPATH``."""
    from hermes_constants import get_hermes_home

    env = dict(os.environ if base is None else base)
    env["HERMES_HOME"] = str(get_hermes_home())
    paths = [str(RELEASE_ROOT)] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(paths))
    return env


def external_child_env(base: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """``child_env`` plus the config values an external interpreter must not look up itself.

    ``pd_one.external.winrm_python`` is a separate venv and does not have ruamel, so a
    helper it runs cannot import the YAML loader. The parent resolves the values here
    and the child reads them from the environment.
    """
    from tools.pd_one_ops.site_config import external_path, profile_root, site_text

    env = child_env(base)
    root = profile_root()
    env["PD_ONE_PROFILE_ROOT"] = str(root)
    env["PD_ONE_LEDGER_TOOLS"] = str(root / "legacy-openclaw/workspace/tools")
    env["PD_ONE_ACL_TOOL"] = str(root / "tools/pd_one_sqlsrv_windows_acl_read.py")
    env["PD_ONE_OWNER_MM_USERNAME"] = site_text("PDONE_OWNER_MM_USERNAME").strip()
    for key, var in (
        ("sqlsrv_readonly", "PD_ONE_SQLSRV_READONLY"),
        ("winrm_site_packages", "PD_ONE_WINRM_SITE_PACKAGES"),
    ):
        found = external_path(key).path()
        if found is not None:
            env[var] = str(found)
        else:
            env.pop(var, None)
    env["PD_ONE_EXTERNAL_INTERPRETER"] = "1"
    return env

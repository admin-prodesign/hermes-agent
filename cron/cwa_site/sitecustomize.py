"""Loaded by ``site`` when the cron runner puts this directory on ``PYTHONPATH``.

The runner does that only for a profile script that fetches ``cwa.gov.tw``
(or whose name says typhoon). The file is loaded by path so ``cron/__init__``
does not boot the scheduler inside the script.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

if os.environ.get("_HERMES_CRON_CWA_TLS") == "1":
    module_path = Path(__file__).resolve().parents[1] / "cwa_tls.py"
    spec = importlib.util.spec_from_file_location("_hermes_cwa_tls", module_path)
    if spec is not None and spec.loader is not None:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.install_cwa_tls()

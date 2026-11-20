"""Refresh the profile copies of failure-autofix entry points on cutover.

Cron and webhooks can only execute files inside ``$HERMES_HOME/scripts``.
Those copies are not on the ``releases/current`` symlink, so a deploy that
only swaps the release leaves the October/November scripts in place. The
copies below are the ones the failure-autofix page path actually runs.

The queue workers stay on the profile. The release tree does not contain
their host-only imports (``model_policy``, the admission gate). The live
worker calls ``failure_autofix_first_pass.py``, which this sync refreshes,
and that gate execs the release notification router.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# (path relative to the release root, filename under <home>/scripts)
COPY_SOURCES: tuple[tuple[str, str], ...] = (
    ("scripts/failure_autofix_first_pass.py", "failure_autofix_first_pass.py"),
    ("scripts/failure_autofix_page.py", "failure_autofix_page.py"),
    ("scripts/pd_one_notification_router.py", "pd_one_notification_router.py"),
    ("scripts/hermes_release_paths.py", "hermes_release_paths.py"),
    ("scripts/deploy/nemo/neo_watch_webhook.py", "neo_watch_webhook.py"),
)


def _log(detail: str) -> None:
    print(f"hermes release script: {detail}", file=sys.stderr)


def _atomic_write(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.tmp")
    try:
        tmp.write_bytes(data)
        os.chmod(tmp, 0o755)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)


def sync_profile_scripts(release: Path, home: Path) -> list[dict]:
    """Copy release entry points into ``<home>/scripts``.

    A missing release file is logged and the profile copy is left as it is,
    so a partial release does not delete the script cron is already running.
    """
    results: list[dict] = []
    dest_dir = home / "scripts"
    for relative, name in COPY_SOURCES:
        src = release / relative
        dest = dest_dir / name
        if not src.is_file():
            _log(f"{relative} missing from {release}; leaving {dest}")
            results.append({"script": name, "ok": False, "detail": "missing"})
            continue
        try:
            _atomic_write(dest, src.read_bytes())
        except OSError as exc:
            _log(f"could not copy {src} to {dest}: {exc}")
            results.append({"script": name, "ok": False, "detail": str(exc)})
            continue
        results.append({"script": name, "ok": True, "dest": str(dest)})
    return results

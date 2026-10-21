"""Install the pull-deploy systemd units on nemo. ``install_autodeploy.sh`` wraps this.

Every unit runs code from ``releases/current``, so a merged change to the poller,
worker, or drift check goes live with the release that carries it. All of them are
oneshots that start fresh each time, so nothing needs a restart after a deploy.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scripts.deploy.nemo.layout import DEFAULT_PROFILES, releases_dir, resolve_hermes_home
from scripts.deploy.nemo.spool import queue_dir

POLL = "hermes-deploy-poll.service"
POLL_TIMER = "hermes-deploy-poll.timer"
WORKER = "hermes-deploy.service"
WORKER_PATH = "hermes-deploy.path"
DRIFT = "hermes-deploy-drift.service"
DRIFT_TIMER = "hermes-deploy-drift.timer"
RUNTIME_DRIFT = "hermes-runtime-drift-check.service"
RUNTIME_DRIFT_TIMER = "hermes-runtime-drift-check.timer"
ALERT_WATCH = "hermes-pdone-alert-watch.service"
ALERT_WATCH_TIMER = "hermes-pdone-alert-watch.timer"
ENABLED = (WORKER_PATH, POLL_TIMER, DRIFT_TIMER, RUNTIME_DRIFT_TIMER, ALERT_WATCH_TIMER)
ALL_UNITS = (
    POLL,
    POLL_TIMER,
    WORKER,
    WORKER_PATH,
    DRIFT,
    DRIFT_TIMER,
    RUNTIME_DRIFT,
    RUNTIME_DRIFT_TIMER,
    ALERT_WATCH,
    ALERT_WATCH_TIMER,
)
LEGACY_UNITS = ("hermes-deploy-listener.service",)
_SAFE_ARG = re.compile(r"[A-Za-z0-9_@%+=:,./-]+")


def service_path_env() -> str:
    """``PATH`` for systemd units: caller env plus common user-local tool dirs."""
    parts: list[str] = []
    seen: set[str] = set()
    home = Path.home()
    for candidate in (
        os.environ.get("PATH", ""),
        f"{home}/.local/bin",
        f"{home}/.cargo/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
    ):
        for item in candidate.split(":"):
            if not item or item in seen:
                continue
            seen.add(item)
            parts.append(item)
    return ":".join(parts)


@dataclass
class UnitOptions:
    home: Path
    releases: Path
    mirror: Path
    scope: str = "user"
    remote: str = "origin"
    alert_script: Path | None = None
    profiles: tuple[str, ...] = DEFAULT_PROFILES
    run_as: str | None = None
    worker_user: str | None = None
    poll_every: str = "60s"
    poll_jitter: str = "20s"
    drift_every: str = "1h"
    alert_watch_every: str = "5min"
    canary: bool = False
    path_env: str = field(default_factory=service_path_env)

    @property
    def current(self) -> Path:
        return self.releases / "current"

    @property
    def python(self) -> Path:
        return self.current / ".venv" / "bin" / "python"


def unit_dir(scope: str) -> Path:
    if scope == "system":
        return Path("/etc/systemd/system")
    return Path.home() / ".config" / "systemd" / "user"


def quote(arg: str) -> str:
    """systemd ExecStart quoting; ``%`` is a specifier, so it is doubled."""
    text = arg.replace("%", "%%")
    if _SAFE_ARG.fullmatch(text):
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _exec(argv: list[str]) -> str:
    return " ".join(quote(str(item)) for item in argv)


def _location_args(opts: UnitOptions) -> list[str]:
    argv = ["--hermes-home", str(opts.home), "--releases", str(opts.releases), "--mirror", str(opts.mirror)]
    if opts.remote != "origin":
        argv += ["--remote", opts.remote]
    return argv


def _common_args(opts: UnitOptions) -> list[str]:
    argv = _location_args(opts)
    for name in opts.profiles:
        argv += ["--profile", name]
    if opts.alert_script:
        argv += ["--alert-script", str(opts.alert_script)]
    return argv


def _service(description: str, opts: UnitOptions, argv: list[str], *, user: str | None, extra: str = "") -> str:
    lines = [
        "[Unit]", f"Description={description}", "After=network-online.target", "Wants=network-online.target", "",
        "[Service]", f"WorkingDirectory={opts.current}", f'Environment="PATH={opts.path_env}"',
        f"Environment=HERMES_HOME={opts.home}", "Environment=GIT_TERMINAL_PROMPT=0", f"ExecStart={_exec(argv)}",
    ]
    if user and opts.scope == "system":
        lines.append(f"User={user}")
    if extra:
        lines.append(extra.rstrip("\n"))
    return "\n".join(lines) + "\n"


def _wanted_by(scope: str) -> str:
    return "multi-user.target" if scope == "system" else "default.target"


def render(opts: UnitOptions) -> dict[str, str]:
    python = str(opts.python)
    poll = [python, "-m", "scripts.deploy.nemo.poll", *_location_args(opts)]
    worker = [python, "-m", "scripts.deploy.nemo.autodeploy", "run", *_common_args(opts),
              *(["--canary"] if opts.canary else [])]
    drift = [python, "-m", "scripts.deploy.nemo.autodeploy", "drift", *_common_args(opts)]
    runtime_drift = [python, "-m", "scripts.deploy.nemo.runtime_drift", *_location_args(opts)]
    alert_watch = [python, "-m", "scripts.deploy.nemo.pdone_alert_watchdog", "--hermes-home", str(opts.home)]
    install = f"\n[Install]\nWantedBy={_wanted_by(opts.scope)}\n"
    return {
        POLL: _service(
            "Hermes deploy poll (queue main when it differs from the live SHA)", opts, poll, user=opts.run_as,
            extra="Type=oneshot\nTimeoutStartSec=5min\n",
        ),
        POLL_TIMER: (
            "[Unit]\nDescription=Poll GitHub main for a Hermes deploy about once a minute\n\n"
            f"[Timer]\nOnBootSec=2min\nOnUnitInactiveSec={opts.poll_every}\n"
            f"RandomizedDelaySec={opts.poll_jitter}\nAccuracySec=1s\nUnit={POLL}\n\n"
            "[Install]\nWantedBy=timers.target\n"
        ),
        WORKER: _service(
            "Hermes deploy worker (build, wait for idle profiles, cut over)", opts, worker,
            user=opts.worker_user or opts.run_as, extra="Type=oneshot\nTimeoutStartSec=infinity\n",
        ),
        WORKER_PATH: (
            "[Unit]\nDescription=Start the Hermes deploy worker when a SHA is queued\n\n"
            f"[Path]\nDirectoryNotEmpty={queue_dir(opts.home)}\nMakeDirectory=yes\nDirectoryMode=0700\n"
            f"Unit={WORKER}\n{install}"
        ),
        DRIFT: _service(
            "Hermes release drift check", opts, drift, user=opts.run_as,
            extra="Type=oneshot\nTimeoutStartSec=15min\n",
        ),
        DRIFT_TIMER: (
            "[Unit]\nDescription=Hourly Hermes release drift check\n\n"
            f"[Timer]\nOnBootSec=10min\nOnUnitActiveSec={opts.drift_every}\nUnit={DRIFT}\n\n"
            "[Install]\nWantedBy=timers.target\n"
        ),
        RUNTIME_DRIFT: _service(
            "Hermes runtime drift check (live gateways vs origin main)",
            opts, runtime_drift, user=opts.run_as,
            extra="Type=oneshot\nTimeoutStartSec=30min\nSuccessExitStatus=1\nNice=10\n",
        ),
        RUNTIME_DRIFT_TIMER: (
            "[Unit]\nDescription=Daily 07:50 Asia/Taipei Hermes runtime drift check\n\n"
            "[Timer]\nOnCalendar=*-*-* 07:50:00 Asia/Taipei\nPersistent=true\n"
            "RandomizedDelaySec=60\nUnit="
            f"{RUNTIME_DRIFT}\n\n[Install]\nWantedBy=timers.target\n"
        ),
        ALERT_WATCH: _service(
            "PD One neo-watch alert watchdog", opts, alert_watch, user=opts.run_as,
            extra="Type=oneshot\nTimeoutStartSec=5min\n",
        ),
        ALERT_WATCH_TIMER: (
            "[Unit]\nDescription=PD One neo-watch alert watchdog (every 5 minutes)\n\n"
            f"[Timer]\nOnBootSec=3min\nOnUnitActiveSec={opts.alert_watch_every}\nUnit={ALERT_WATCH}\n\n"
            "[Install]\nWantedBy=timers.target\n"
        ),
    }


def write_units(directory: Path, units: dict[str, str]) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    for name, text in units.items():
        path = directory / name
        if path.is_file() and path.read_text(encoding="utf-8-sig") == text:
            continue
        path.write_text(text, encoding="utf-8")
        changed.append(name)
    return changed


def legacy_present(directory: Path) -> list[str]:
    return [name for name in LEGACY_UNITS if (directory / name).exists()]


def _systemctl(scope: str, *args: str) -> int:
    argv = ["systemctl", *(["--user"] if scope == "user" else []), *args]
    return subprocess.run(argv, timeout=60, stdin=subprocess.DEVNULL, check=False).returncode


def _unit_lifecycle(scope: str, unit: str) -> tuple[bool | None, bool | None]:
    """Return ``(enabled, active)``; ``None`` when the unit is not installed."""
    enabled_code = _systemctl(scope, "is-enabled", unit)
    if enabled_code == 0:
        enabled = True
    elif enabled_code == 1:
        enabled = False
    else:
        return None, None
    active = _systemctl(scope, "is-active", unit) == 0
    return enabled, active


def _capture_unit_states(scope: str, units: tuple[str, ...]) -> dict[str, tuple[bool | None, bool | None]]:
    return {name: _unit_lifecycle(scope, name) for name in units}


def _restore_unit_states(scope: str, states: dict[str, tuple[bool | None, bool | None]]) -> None:
    for unit, (enabled, active) in states.items():
        if enabled is None:
            continue
        if enabled:
            _systemctl(scope, "enable", unit)
        else:
            _systemctl(scope, "disable", unit)
        if active:
            _systemctl(scope, "start", unit)
        elif enabled:
            _systemctl(scope, "stop", unit)


def _remove_legacy(scope: str, directory: Path) -> None:
    """The push listener from the first version of this tool; its module is gone."""
    stale = legacy_present(directory)
    if not stale:
        return
    _systemctl(scope, "disable", "--now", *stale)
    for name in stale:
        (directory / name).unlink(missing_ok=True)
    print("removed " + ", ".join(stale))


def _options(args: argparse.Namespace) -> UnitOptions:
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    run_as = args.run_as or (os.environ.get("SUDO_USER") or getpass.getuser() if args.scope == "system" else None)
    return UnitOptions(
        home=home, releases=releases_dir(home, Path(args.releases) if args.releases else None),
        mirror=Path(args.mirror).expanduser().resolve(), scope=args.scope, remote=args.remote,
        alert_script=Path(args.alert_script).resolve() if args.alert_script else None,
        profiles=tuple(args.profiles or ()) or DEFAULT_PROFILES, run_as=run_as,
        worker_user=args.worker_user, poll_every=args.poll_every, canary=args.canary,
    )


def cmd_install(args: argparse.Namespace) -> int:
    opts = _options(args)
    units = render(opts)
    directory = unit_dir(opts.scope)
    if args.dry_run:
        for name, text in units.items():
            print(f"# {directory / name}\n{text}")
        for name in legacy_present(directory):
            print(f"# would disable and remove {directory / name}")
        return 0
    if not opts.python.exists():
        print(f"{opts.python} is missing; deploy a release with cutover.sh first", file=sys.stderr)
        return 1
    prior = _capture_unit_states(opts.scope, ENABLED)
    _remove_legacy(opts.scope, directory)
    changed = write_units(directory, units)
    print("unchanged" if not changed else "wrote " + ", ".join(changed))
    if _systemctl(opts.scope, "daemon-reload") != 0:
        return 1
    if args.enable:
        rc = _systemctl(opts.scope, "enable", "--now", *ENABLED)
    else:
        _restore_unit_states(opts.scope, prior)
        rc = 0
    if prior.get(ALERT_WATCH_TIMER, (None, None))[0] is None:
        if _systemctl(opts.scope, "enable", "--now", ALERT_WATCH_TIMER) != 0:
            return 1
    return rc


def cmd_uninstall(args: argparse.Namespace) -> int:
    directory = unit_dir(args.scope)
    _systemctl(args.scope, "disable", "--now", *ENABLED, *legacy_present(directory))
    for name in (*ALL_UNITS, *LEGACY_UNITS):
        (directory / name).unlink(missing_ok=True)
    return _systemctl(args.scope, "daemon-reload")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install_autodeploy.sh")
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install", help="write and enable the pull-deploy units")
    install.add_argument("--hermes-home", default=None)
    install.add_argument("--releases", default=None)
    install.add_argument("--mirror", required=True)
    install.add_argument("--remote", default="origin")
    install.add_argument("--scope", choices=("user", "system"), default="user")
    install.add_argument("--poll-every", default="60s")
    install.add_argument("--alert-script", default=None)
    install.add_argument("--profile", action="append", dest="profiles", default=None)
    install.add_argument("--run-as", default=None, help="system scope: user for the poll and drift check")
    install.add_argument("--worker-user", default=None, help="system scope: user for the deploy worker")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--canary", action="store_true",
                         help="worker restarts and verifies PD Neo (top-level profile) before pdone")
    install.add_argument(
        "--enable", action="store_true",
        help="enable and start poll/path/drift units (default: preserve existing enable/active state)",
    )
    install.set_defaults(func=cmd_install, enable=False)
    uninstall = sub.add_parser("uninstall", help="disable and remove the pull-deploy units")
    uninstall.add_argument("--scope", choices=("user", "system"), default="user")
    uninstall.set_defaults(func=cmd_uninstall)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

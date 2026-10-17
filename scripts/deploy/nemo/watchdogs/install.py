"""Install the nemo watchdog systemd --user units from releases/current."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scripts.deploy.nemo.autodeploy_units import quote, service_path_env, unit_dir
from scripts.deploy.nemo.layout import releases_dir, resolve_hermes_home

FAILURES = "hermes-watchdog-failures"
GATEWAY = "hermes-watchdog-gateway"
AUTODEPLOY = "hermes-watchdog-autodeploy"
HOST = "hermes-watchdog-host"
BACKUP = "hermes-watchdog-backup"
CHECKS = (
    (FAILURES, "failures", "5min", "2min"),
    (GATEWAY, "gateway", "2min", "1min"),
    (AUTODEPLOY, "autodeploy", "5min", "2min"),
    (HOST, "host", "5min", "2min"),
    (BACKUP, "backup", "1h", "10min"),
)
SERVICES = tuple(f"{name}.service" for name, _module, _every, _boot in CHECKS)
TIMERS = tuple(f"{name}.timer" for name, _module, _every, _boot in CHECKS)
ALL_UNITS = SERVICES + TIMERS
ENABLED = TIMERS


@dataclass
class Options:
    home: Path
    releases: Path
    scope: str = "user"
    path_env: str = field(default_factory=service_path_env)

    @property
    def current(self) -> Path:
        return self.releases / "current"

    @property
    def python(self) -> Path:
        return self.current / ".venv" / "bin" / "python"


def _exec(argv: list[str]) -> str:
    return " ".join(quote(str(item)) for item in argv)


def render_service(opts: Options, _name: str, module: str) -> str:
    python = str(opts.python)
    webhook = opts.home / "watchdogs" / "webhook.env"
    state = opts.home / "watchdogs" / "state"
    argv = [python, "-m", f"scripts.deploy.nemo.watchdogs.{module}"]
    lines = [
        "[Unit]",
        f"Description=Hermes nemo watchdog ({module})",
        "After=network-online.target",
        "Wants=network-online.target",
        "",
        "[Service]",
        "Type=oneshot",
        f"WorkingDirectory={opts.current}",
        f'Environment="PATH={opts.path_env}"',
        f"Environment=HERMES_HOME={opts.home}",
        f"Environment=NEMO_WATCH_WEBHOOK_ENV={webhook}",
        f"Environment=NEMO_WATCH_STATE_DIR={state}",
        f"ExecStart={_exec(argv)}",
        "TimeoutStartSec=60",
        "",
    ]
    return "\n".join(lines)


def render_timer(name: str, module: str, every: str, boot: str) -> str:
    return (
        f"[Unit]\nDescription=Run the Hermes nemo {module} watchdog\n\n"
        f"[Timer]\nOnBootSec={boot}\nOnUnitActiveSec={every}\n"
        f"AccuracySec=15s\nUnit={name}.service\n\n"
        "[Install]\nWantedBy=timers.target\n"
    )


def render(opts: Options) -> dict[str, str]:
    units: dict[str, str] = {}
    for name, module, every, boot in CHECKS:
        units[f"{name}.service"] = render_service(opts, name, module)
        units[f"{name}.timer"] = render_timer(name, module, every, boot)
    return units


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


def _systemctl(scope: str, *args: str) -> int:
    argv = ["systemctl", *(["--user"] if scope == "user" else []), *args]
    return subprocess.run(argv, timeout=60, stdin=subprocess.DEVNULL, check=False).returncode


def _unit_lifecycle(scope: str, unit: str) -> tuple[bool | None, bool | None]:
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


def _options(args: argparse.Namespace) -> Options:
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    return Options(
        home=home,
        releases=releases_dir(home, Path(args.releases) if args.releases else None),
        scope=args.scope,
    )


def cmd_install(args: argparse.Namespace) -> int:
    opts = _options(args)
    units = render(opts)
    directory = unit_dir(opts.scope)
    if args.dry_run:
        for name, text in units.items():
            print(f"# {directory / name}\n{text}")
        return 0
    if not opts.python.exists():
        print(f"{opts.python} is missing; deploy a release with cutover.sh first", file=sys.stderr)
        return 1
    prior = _capture_unit_states(opts.scope, ENABLED)
    changed = write_units(directory, units)
    print("unchanged" if not changed else "wrote " + ", ".join(changed))
    if _systemctl(opts.scope, "daemon-reload") != 0:
        return 1
    if args.enable:
        return _systemctl(opts.scope, "enable", "--now", *ENABLED)
    _restore_unit_states(opts.scope, prior)
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    directory = unit_dir(args.scope)
    _systemctl(args.scope, "disable", "--now", *ENABLED)
    for name in ALL_UNITS:
        (directory / name).unlink(missing_ok=True)
    return _systemctl(args.scope, "daemon-reload")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install_watchdogs.sh")
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install", help="write the watchdog units")
    install.add_argument("--hermes-home", default=None)
    install.add_argument("--releases", default=None)
    install.add_argument("--scope", choices=("user", "system"), default="user")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument(
        "--enable",
        action="store_true",
        help="enable and start timers (default: preserve existing enable/active state)",
    )
    install.set_defaults(func=cmd_install, enable=False)
    uninstall = sub.add_parser("uninstall", help="disable and remove the watchdog units")
    uninstall.add_argument("--scope", choices=("user", "system"), default="user")
    uninstall.set_defaults(func=cmd_uninstall)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

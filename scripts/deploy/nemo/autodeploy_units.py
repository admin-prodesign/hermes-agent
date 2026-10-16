"""Install the push-deploy systemd units on nemo. ``install_autodeploy.sh`` wraps this.

Every unit runs code from ``releases/current``, so a merged change to the listener,
worker, or drift check goes live with the release that carries it. The listener is
restarted by the worker after each deploy; the oneshot units start fresh each time.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import secrets
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scripts.deploy.nemo.layout import DEFAULT_PROFILES, releases_dir, resolve_hermes_home
from scripts.deploy.nemo.listener import DEFAULT_PORT, DEFAULT_REF
from scripts.deploy.nemo.spool import queue_dir, state_dir

LISTENER = "hermes-deploy-listener.service"
WORKER = "hermes-deploy.service"
WORKER_PATH = "hermes-deploy.path"
DRIFT = "hermes-deploy-drift.service"
DRIFT_TIMER = "hermes-deploy-drift.timer"
ENABLED = (LISTENER, WORKER_PATH, DRIFT_TIMER)
ALL_UNITS = (LISTENER, WORKER, WORKER_PATH, DRIFT, DRIFT_TIMER)
DEFAULT_REPOSITORY = "admin-prodesign/hermes-agent"
_SAFE_ARG = re.compile(r"[A-Za-z0-9_@%+=:,./-]+")


@dataclass
class UnitOptions:
    home: Path
    releases: Path
    mirror: Path
    scope: str = "user"
    repository: str = DEFAULT_REPOSITORY
    ref: str = DEFAULT_REF
    bind: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    require_tag: str | None = None
    secret_file: Path | None = None
    alert_script: Path | None = None
    profiles: tuple[str, ...] = DEFAULT_PROFILES
    run_as: str | None = None
    worker_user: str | None = None
    drift_every: str = "1h"
    path_env: str = field(default_factory=lambda: os.environ.get("PATH", "/usr/bin:/bin"))

    @property
    def current(self) -> Path:
        return self.releases / "current"

    @property
    def python(self) -> Path:
        return self.current / ".venv" / "bin" / "python"

    @property
    def secret(self) -> Path:
        return self.secret_file or state_dir(self.home) / "webhook-secret"


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


def _common_args(opts: UnitOptions) -> list[str]:
    argv = ["--hermes-home", str(opts.home), "--releases", str(opts.releases), "--mirror", str(opts.mirror)]
    for name in opts.profiles:
        argv += ["--profile", name]
    if opts.alert_script:
        argv += ["--alert-script", str(opts.alert_script)]
    return argv


def _service(description: str, opts: UnitOptions, argv: list[str], *, user: str | None, extra: str = "") -> str:
    lines = [
        "[Unit]", f"Description={description}", "After=network-online.target", "Wants=network-online.target", "",
        "[Service]", f"WorkingDirectory={opts.current}", f'Environment="PATH={opts.path_env}"',
        f"Environment=HERMES_HOME={opts.home}", f"ExecStart={_exec(argv)}",
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
    listen = [python, "-m", "scripts.deploy.nemo.listener", "--hermes-home", str(opts.home),
              "--bind", opts.bind, "--port", str(opts.port), "--secret-file", str(opts.secret),
              "--repository", opts.repository, "--ref", opts.ref]
    if opts.require_tag:
        listen += ["--require-tailscale-tag", opts.require_tag]
    worker = [python, "-m", "scripts.deploy.nemo.autodeploy", "run", *_common_args(opts), "--scope", opts.scope]
    drift = [python, "-m", "scripts.deploy.nemo.autodeploy", "drift", *_common_args(opts)]
    install = f"\n[Install]\nWantedBy={_wanted_by(opts.scope)}\n"
    return {
        LISTENER: _service(
            "Hermes push-deploy listener (verifies and queues merged SHAs)", opts, listen, user=opts.run_as,
            extra="Restart=on-failure\nRestartSec=5\nNoNewPrivileges=yes\nPrivateTmp=yes\n" + install,
        ),
        WORKER: _service(
            "Hermes push-deploy worker (build, wait for idle profiles, cut over)", opts, worker,
            user=opts.worker_user or opts.run_as, extra="Type=oneshot\nTimeoutStartSec=infinity\n",
        ),
        WORKER_PATH: (
            "[Unit]\nDescription=Start the Hermes deploy worker when a request is queued\n\n"
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
    }


def ensure_secret(path: Path) -> bool:
    """Create a random secret once. Returns True when it was created. The value is never printed."""
    if path.is_file():
        return False
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(secrets.token_urlsafe(48) + "\n")
    return True


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


def _options(args: argparse.Namespace) -> UnitOptions:
    home = resolve_hermes_home(Path(args.hermes_home) if args.hermes_home else None)
    run_as = args.run_as or (os.environ.get("SUDO_USER") or getpass.getuser() if args.scope == "system" else None)
    return UnitOptions(
        home=home, releases=releases_dir(home, Path(args.releases) if args.releases else None),
        mirror=Path(args.mirror).expanduser().resolve(), scope=args.scope, repository=args.repository,
        bind=args.bind, port=args.port, require_tag=args.require_tailscale_tag,
        secret_file=Path(args.secret_file) if args.secret_file else None,
        alert_script=Path(args.alert_script).resolve() if args.alert_script else None,
        profiles=tuple(args.profiles or ()) or DEFAULT_PROFILES, run_as=run_as,
        worker_user=args.worker_user,
    )


def cmd_install(args: argparse.Namespace) -> int:
    opts = _options(args)
    units = render(opts)
    if args.dry_run:
        for name, text in units.items():
            print(f"# {unit_dir(opts.scope) / name}\n{text}")
        return 0
    if not opts.python.exists():
        print(f"{opts.python} is missing; deploy a release with cutover.sh first", file=sys.stderr)
        return 1
    if ensure_secret(opts.secret):
        print(f"created {opts.secret} (0600); copy it into the NEMO_DEPLOY_HMAC_SECRET repo secret")
    changed = write_units(unit_dir(opts.scope), units)
    print("unchanged" if not changed else "wrote " + ", ".join(changed))
    if _systemctl(opts.scope, "daemon-reload") != 0:
        return 1
    return _systemctl(opts.scope, "enable", "--now", *ENABLED)


def cmd_uninstall(args: argparse.Namespace) -> int:
    directory = unit_dir(args.scope)
    _systemctl(args.scope, "disable", "--now", *ENABLED)
    for name in ALL_UNITS:
        (directory / name).unlink(missing_ok=True)
    return _systemctl(args.scope, "daemon-reload")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install_autodeploy.sh")
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install", help="write and enable the push-deploy units")
    install.add_argument("--hermes-home", default=None)
    install.add_argument("--releases", default=None)
    install.add_argument("--mirror", required=True)
    install.add_argument("--scope", choices=("user", "system"), default="user")
    install.add_argument("--repository", default=DEFAULT_REPOSITORY)
    install.add_argument("--bind", default="127.0.0.1")
    install.add_argument("--port", type=int, default=DEFAULT_PORT)
    install.add_argument("--require-tailscale-tag", default=None)
    install.add_argument("--secret-file", default=None)
    install.add_argument("--alert-script", default=None)
    install.add_argument("--profile", action="append", dest="profiles", default=None)
    install.add_argument("--run-as", default=None, help="system scope: user for the listener and drift check")
    install.add_argument("--worker-user", default=None, help="system scope: user for the deploy worker")
    install.add_argument("--dry-run", action="store_true")
    install.set_defaults(func=cmd_install)
    uninstall = sub.add_parser("uninstall", help="disable and remove the push-deploy units")
    uninstall.add_argument("--scope", choices=("user", "system"), default="user")
    uninstall.set_defaults(func=cmd_uninstall)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

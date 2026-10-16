"""Process, network, and write guards for the PD One self-test.

Inside :class:`Guard` no child process runs: ``subprocess.Popen`` records the argv,
checks it, and answers as a finished process. Sockets refuse to connect, ``time.sleep``
returns at once, and a write outside the scratch sandbox is refused (a write into the
release tree is also recorded as a failure, because production publishes it read-only).
"""
from __future__ import annotations

import builtins
import io
import os
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from tools.pd_one_ops.launch import unset_keys

PLANNED_STDOUT = '{"status": "selftest-planned"}'
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
_NO_SUCH_PID = 2**31 - 1


@dataclass
class Launch:
    argv: list[str]
    problems: list[str] = field(default_factory=list)


def _argv_text(argv: Any) -> list[str]:
    return [os.fspath(item) if isinstance(item, os.PathLike) else str(item) for item in argv]


def is_interpreter(path: str) -> bool:
    return Path(path).name.lower().startswith("python") or os.path.realpath(path) == os.path.realpath(sys.executable)


def launch_problems(argv: Any) -> list[str]:
    """Why ``argv`` would fail from a read-only release with no exec bits, or ``[]``."""
    if isinstance(argv, (str, bytes)):
        return ["launched through a shell string"]
    items = _argv_text(argv)
    problems = [f"pd_one.external.{key} is not set" for key in unset_keys(items)]
    if not items or problems:
        return problems
    first = items[0]
    if first.endswith(".py"):
        problems.append(f"executes {first} directly; run it as <interpreter> {Path(first).name}")
    elif os.sep in first and Path(first).is_file() and not os.access(first, os.X_OK):
        problems.append(f"{first} is not executable")
    for item in items[1:]:
        if item.endswith(".py") and os.sep in item and Path(item).is_file() and not os.access(item, os.R_OK):
            problems.append(f"{item} is not readable")
    return problems


class WriteRefused(PermissionError):
    """A self-test write outside the sandbox. No errno, so it never reads as EACCES."""


class Guard:
    def __init__(self, sandbox: Path, release: Path) -> None:
        self.sandbox = sandbox.resolve()
        self.release = release.resolve()
        self.launches: list[Launch] = []
        self.scripts: dict[tuple[str, str], tuple[dict[str, str], Optional[str]]] = {}
        self._popen = subprocess.Popen
        self._restore: list[tuple[Any, str, Any]] = []

    # -- recording -------------------------------------------------------------------------
    def record(self, argv: Any, env: Optional[dict[str, str]], cwd: Any) -> None:
        launch = Launch(_argv_text(argv) if not isinstance(argv, (str, bytes)) else [str(argv)], launch_problems(argv))
        self.launches.append(launch)
        items = launch.argv
        if len(items) < 2 or not is_interpreter(items[0]) or not items[1].endswith(".py"):
            return
        script = Path(items[1]).resolve()
        if script.is_file() and self.release in script.parents:
            self.scripts.setdefault((items[0], str(script)), (dict(env or os.environ), str(cwd) if cwd else None))

    def _check_write(self, target: Any) -> None:
        path = Path(os.path.abspath(os.fspath(target)))
        if path == Path(os.devnull) or self.sandbox in path.parents or path == self.sandbox:
            return
        if self.release in path.parents:
            self.launches.append(Launch([], [f"writes into the release tree: {path}"]))
        raise WriteRefused(f"selftest refused a write outside its sandbox: {path}")

    # -- real process for the script probes ------------------------------------------------
    def real_run(self, argv: list[str], *, env: dict[str, str], cwd: Optional[str], timeout: float,
                 **_: Any) -> subprocess.CompletedProcess:
        with self._popen(argv, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
            try:
                out, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                raise
        return subprocess.CompletedProcess(argv, proc.returncode, out, err)

    # -- patching --------------------------------------------------------------------------
    def _patch(self, owner: Any, name: str, value: Any) -> None:
        self._restore.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    def _planned_popen(self) -> type:
        guard = self

        class PlannedPopen:
            def __init__(self, args: Any, *positional: Any, **kw: Any) -> None:
                guard.record(args, kw.get("env"), kw.get("cwd"))
                self.args = args
                self.returncode = 0
                self.pid = _NO_SUCH_PID
                self.stdin = self.stdout = self.stderr = None
                text = kw.get("text") or kw.get("universal_newlines") or kw.get("encoding") or kw.get("errors")
                self._out = PLANNED_STDOUT if text else PLANNED_STDOUT.encode()
                self._err = "" if text else b""

            def communicate(self, input: Any = None, timeout: Any = None) -> tuple[Any, Any]:
                return self._out, self._err

            def wait(self, timeout: Any = None) -> int:
                return 0

            def poll(self) -> int:
                return 0

            def kill(self) -> None:
                return None

            terminate = kill

            def send_signal(self, sig: int) -> None:
                return None

            def __enter__(self) -> PlannedPopen:
                return self

            def __exit__(self, *exc: object) -> bool:
                return False

        return PlannedPopen

    def _guarded_open(self, original: Callable[..., Any]) -> Callable[..., Any]:
        def guarded(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            if isinstance(file, (str, bytes, os.PathLike)) and any(flag in mode for flag in "wax+"):
                self._check_write(file)
            return original(file, mode, *args, **kwargs)
        return guarded

    def _guarded_path_op(self, original: Callable[..., Any], arity: int = 1, *, existing_ok: bool = False) -> Callable[..., Any]:
        def guarded(*args: Any, **kwargs: Any) -> Any:
            if kwargs.get("dir_fd") is None and kwargs.get("src_dir_fd") is None:
                for target in args[:arity]:
                    if not (existing_ok and os.path.exists(target)):
                        self._check_write(target)
            return original(*args, **kwargs)
        return guarded

    def _guarded_os_open(self, original: Callable[..., Any]) -> Callable[..., Any]:
        def guarded(path: Any, flags: int, *args: Any, **kwargs: Any) -> Any:
            if flags & _WRITE_FLAGS and kwargs.get("dir_fd") is None:
                self._check_write(path)
            return original(path, flags, *args, **kwargs)
        return guarded

    def _guarded_sqlite(self, original: Callable[..., Any]) -> Callable[..., Any]:
        def guarded(database: Any, *args: Any, **kwargs: Any) -> Any:
            text = os.fspath(database) if isinstance(database, os.PathLike) else str(database)
            inside = text == ":memory:" or text.startswith("file:") or self.sandbox in Path(os.path.abspath(text)).parents
            if inside:
                return original(database, *args, **kwargs)
            kwargs.pop("uri", None)
            return original(f"file:{os.path.abspath(text)}?mode=ro", *args, uri=True, **kwargs)
        return guarded

    def __enter__(self) -> Guard:
        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise ConnectionRefusedError("selftest: network disabled")

        self._patch(subprocess, "Popen", self._planned_popen())
        for name in ("connect", "connect_ex"):
            self._patch(socket.socket, name, refuse)
        self._patch(socket, "create_connection", refuse)
        self._patch(socket, "getaddrinfo", refuse)
        self._patch(time, "sleep", lambda seconds: None)
        opener = self._guarded_open(builtins.open)
        self._patch(builtins, "open", opener)
        self._patch(io, "open", opener)
        self._patch(os, "open", self._guarded_os_open(os.open))
        # mkdir of an existing directory changes nothing (ensure-dir helpers call it on every load).
        self._patch(os, "mkdir", self._guarded_path_op(os.mkdir, existing_ok=True))
        for name, arity in (("remove", 1), ("unlink", 1), ("rmdir", 1), ("replace", 2), ("rename", 2)):
            self._patch(os, name, self._guarded_path_op(getattr(os, name), arity))
        self._patch(sqlite3, "connect", self._guarded_sqlite(sqlite3.connect))
        return self

    def __exit__(self, *exc: object) -> None:
        while self._restore:
            owner, name, value = self._restore.pop()
            setattr(owner, name, value)

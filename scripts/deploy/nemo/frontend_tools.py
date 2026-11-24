"""Pinned Node and pnpm for the nemo frontend build.

``scripts/build/node-deps.mjs`` refuses any pnpm other than the one
``pm/lock.json`` pins, and the workspace ``engineStrict`` rule refuses Node
below 26. The autodeploy host's ``~/.local/bin/pnpm`` (a newer corepack shim)
and its Node 22 therefore cannot install the dashboard.

This downloads those two pins into ``<hermes-home>/tools/.build-pins``, checks
the lock's SHA-256, and returns a PATH prefix for that build step. A directory
whose stamp matches the pin is reused. An entry ``facts.json`` already records
for the same version, target and hashes is used in place, so a host that
already installed the pin does not download it again.

Nothing here writes ``facts.json``, replaces ``~/.local/bin/pnpm``, or selects
a Python. Gateway units keep the interpreter and PATH they already have. The
cache directory is dotted because ``hermes pm gc`` deletes every other
unreferenced directory in the tool store.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from pm.filesystem import lock_fd, unlock_fd
from pm.lock import Lockfile
from pm.registry import get_package
from pm.store import current_target, merge_tree

_SHA = re.compile(r"[a-f0-9]{64}")
_ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".zip")
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
_CHUNK = 256 * 1024


class FrontendToolError(RuntimeError):
    """The pin could not be read, downloaded, or executed."""


@dataclass(frozen=True)
class Artifact:
    url: str
    sha256: str
    filename: str


@dataclass(frozen=True)
class ToolPin:
    name: str
    version: str
    target: str
    artifacts: tuple[Artifact, ...]


@dataclass(frozen=True)
class PinSet:
    target: str
    node: ToolPin
    pnpm: ToolPin


def cache_dir(home: Path) -> Path:
    """Versioned tool cache under the Hermes tool store, ignored by ``pm gc``."""
    return home / "tools" / ".build-pins"


def resolve_pins(source: Path) -> PinSet:
    """The Node and pnpm pins in ``source/pm/lock.json`` for this machine."""
    lock_path = source / "pm" / "lock.json"
    if not lock_path.is_file():
        _fail(f"no pm/lock.json under {source}")
    lock = Lockfile(lock_path)
    target = current_target()
    return PinSet(
        target=target,
        node=_pin(lock, "node", target),
        pnpm=_pin(lock, "pnpm", target),
    )


def dry_run_report(source: Path, home: Path) -> str:
    """Describe the pin. Does not create the cache or open a connection."""
    pins = resolve_pins(source)
    lines = [
        f"target: {pins.target}",
        f"cache: {cache_dir(home)}",
        f"node: {pins.node.version}",
        *_artifact_lines("node", pins.node),
        f"pnpm: {pins.pnpm.version}",
        *_artifact_lines("pnpm", pins.pnpm),
    ]
    return "\n".join(lines)


def provision_path(source: Path, home: Path) -> str:
    """Download or reuse the pins and return ``pnpm_dir:node_bin_dir``.

    pnpm's directory comes first so it wins over ``~/.local/bin/pnpm``. Node's
    ``bin`` comes next so the pinned Node wins over a Node 22 later on PATH.
    Node's own directory has no ``pnpm``, so this order does not hide Node.
    """
    pins = resolve_pins(source)
    cache = cache_dir(home)
    with _locked(cache):
        node_bin, node_how = _ensure(cache, home, pins.node)
        pnpm_bin, pnpm_how = _ensure(cache, home, pins.pnpm)
    print(
        f"pinned frontend tool: node {pins.node.version} ({node_how}) {node_bin}; "
        f"pnpm {pins.pnpm.version} ({pnpm_how}) {pnpm_bin}",
        file=sys.stderr,
    )
    dirs: list[str] = []
    for binary in (pnpm_bin, node_bin):
        folder = str(binary.parent)
        if folder not in dirs:
            dirs.append(folder)
    return os.pathsep.join(dirs)


def _fail(message: str) -> None:
    raise FrontendToolError(f"pinned frontend tool: {message}")


def _artifact_lines(name: str, pin: ToolPin) -> list[str]:
    return [f"{name}_artifact: {item.sha256} {item.url}" for item in pin.artifacts]


def _check_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.username or parsed.password:
        _fail(f"refusing a URL with credentials ({parsed.scheme}://{parsed.hostname})")
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https" and host:
        return
    if parsed.scheme == "http" and host in _LOOPBACK:
        return
    _fail(f"refusing URL {url}")


def _filename(url: str) -> str:
    name = urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name)
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        _fail(f"archive name missing in {url}")
    if not name.endswith(_ARCHIVE_SUFFIXES):
        _fail(f"unsupported archive {name}")
    return name


def _pin(lock: Lockfile, name: str, target: str) -> ToolPin:
    version = lock.version(name)
    if (
        not isinstance(version, str)
        or not version
        or any(char in version for char in "/\\")
    ):
        _fail(f"pm/lock.json pins no {name} version for {target}")
    found = lock.artifacts(name, target)
    if not found:
        _fail(f"pm/lock.json has no {name} artifact for {target}")
    artifacts: list[Artifact] = []
    for item in found:
        url = item.get("url") if isinstance(item, dict) else None
        sha = item.get("sha256") if isinstance(item, dict) else None
        if (
            not isinstance(url, str)
            or not isinstance(sha, str)
            or _SHA.fullmatch(sha) is None
        ):
            _fail(f"{name} artifact for {target} has no url and sha256")
        _check_url(url)
        artifacts.append(Artifact(url=url, sha256=sha, filename=_filename(url)))
    return ToolPin(
        name=name, version=version, target=target, artifacts=tuple(artifacts),
    )


@contextmanager
def _locked(cache: Path):
    cache.mkdir(parents=True, exist_ok=True)
    fd = os.open(cache / ".install.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if not lock_fd(fd, wait=True):
            _fail("could not lock the tool cache")
        yield
    finally:
        unlock_fd(fd)
        os.close(fd)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, dest: Path, sha256: str) -> None:
    _check_url(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".partial")
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": "hermes-nemo-deploy"})
    try:
        with (
            urllib.request.urlopen(request, timeout=300) as response,
            partial.open("wb") as out,
        ):
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
                out.write(chunk)
        got = digest.hexdigest()
        if got != sha256:
            _fail(f"checksum mismatch for {url}: expected {sha256}, got {got}")
        os.replace(partial, dest)
    except FrontendToolError:
        partial.unlink(missing_ok=True)
        raise
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        partial.unlink(missing_ok=True)
        _fail(f"download failed for {url}: {exc}")


def _archive(cache: Path, artifact: Artifact) -> Path:
    dest = cache / "fetch" / artifact.sha256 / artifact.filename
    if dest.is_file() and _sha256_file(dest) == artifact.sha256:
        return dest
    dest.unlink(missing_ok=True)
    _download(artifact.url, dest, artifact.sha256)
    return dest


def _same_version(reported: str, expected: str) -> bool:
    return reported.strip().lstrip("v") == expected.lstrip("v")


def _probe(binary: Path) -> str:
    try:
        proc = subprocess.run(
            [os.fspath(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _fail(f"could not exec {binary}: {exc}")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        _fail(f"{binary} --version exited {proc.returncode}: {detail}")
    return proc.stdout.strip()


def _manifest_version(entry: Path) -> str:
    path = entry / "package.json"
    try:
        version = json.loads(path.read_text(encoding="utf-8-sig")).get("version")
    except (OSError, ValueError) as exc:
        _fail(f"pnpm entry has no readable package.json ({path}): {exc}")
    if not isinstance(version, str) or not version:
        _fail(f"pnpm package.json has no version ({path})")
    return version


def _inspect(package, entry: Path, pin: ToolPin) -> Path:
    binary = package.binary(entry, pin.target)
    if binary is None or not binary.is_file():
        _fail(f"{pin.name} binary missing under {entry}")
    if not os.access(binary, os.X_OK):
        _fail(f"{pin.name} binary is not executable: {binary}")
    if pin.name == "pnpm":
        manifest = _manifest_version(entry)
        if manifest != pin.version:
            _fail(f"pnpm package.json version {manifest} != pin {pin.version}")
    reported = _probe(binary)
    if not _same_version(reported, pin.version):
        _fail(f"{pin.name} --version reported {reported}, pin is {pin.version}")
    return binary


def _try_reuse(package, entry: Path | None, pin: ToolPin) -> Path | None:
    if entry is None or not entry.is_dir():
        return None
    try:
        return _inspect(package, entry, pin)
    except FrontendToolError:
        return None


def _read_fact(home: Path, name: str) -> dict | None:
    """Read one tool fact. A missing or unreadable file is 'not installed'."""
    path = home / "tools" / "facts.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    packages = data.get("packages") if isinstance(data, dict) else None
    fact = packages.get(name) if isinstance(packages, dict) else None
    return fact if isinstance(fact, dict) else None


def _runtime_entry(home: Path, pin: ToolPin, entry_name: str) -> Path | None:
    """The PM store entry, when it already is this pin. Read-only."""
    fact = _read_fact(home, pin.name)
    if fact is None:
        return None
    if fact.get("version") != pin.version or fact.get("target") != pin.target:
        return None
    if fact.get("entry") != entry_name:
        return None
    artifacts = fact.get("artifacts")
    expected = [item.sha256 for item in pin.artifacts]
    if not isinstance(artifacts, list) or list(artifacts) != expected:
        return None
    tools = (home / "tools").resolve()
    entry = (tools / entry_name).resolve()
    if not entry.is_dir() or not entry.is_relative_to(tools):
        return None
    return entry


def _stamp_path(cache: Path, entry_name: str) -> Path:
    return cache / f"{entry_name}.pin"


def _stamp_matches(path: Path, pin: ToolPin) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    return (
        isinstance(data, dict)
        and data.get("version") == pin.version
        and data.get("target") == pin.target
        and data.get("sha256") == [item.sha256 for item in pin.artifacts]
    )


def _write_stamp(path: Path, pin: ToolPin) -> None:
    payload = {
        "version": pin.version,
        "target": pin.target,
        "sha256": [item.sha256 for item in pin.artifacts],
    }
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _extract(package, archives: list[Path], pin: ToolPin, dest: Path) -> None:
    """Unpack the lock's archives the way PM does, into ``dest`` only."""
    staging = dest.with_name(f".staging-{pin.name}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        tree = staging / "tree"
        for index, archive in enumerate(archives):
            destination = tree if index == 0 else staging / f"extra-{index}"
            package.unpack(archive, destination, pin.target)
            if index:
                merge_tree(destination, tree)
        package.stage(None, tree, pin.version, pin.target)
        if dest.exists():
            shutil.rmtree(dest)
        tree.rename(dest)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _ensure(cache: Path, home: Path, pin: ToolPin) -> tuple[Path, str]:
    package = get_package(pin.name)
    entry_name = package.store_entry(pin.version, pin.target)
    cached = cache / entry_name
    if _stamp_matches(_stamp_path(cache, entry_name), pin):
        binary = _try_reuse(package, cached, pin)
        if binary is not None:
            return binary, "cached"
    runtime = _runtime_entry(home, pin, entry_name)
    binary = _try_reuse(package, runtime, pin)
    if binary is not None:
        return binary, "store"
    archives = [_archive(cache, artifact) for artifact in pin.artifacts]
    if cached.exists():
        shutil.rmtree(cached)
    _extract(package, archives, pin, cached)
    extracted = package.binary(cached, pin.target)
    if extracted is not None and extracted.is_file():
        extracted.chmod(extracted.stat().st_mode | 0o755)
    try:
        binary = _inspect(package, cached, pin)
    except FrontendToolError:
        shutil.rmtree(cached, ignore_errors=True)
        raise
    _write_stamp(_stamp_path(cache, entry_name), pin)
    return binary, "downloaded"

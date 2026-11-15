"""The nemo frontend build resolves Node and pnpm from the tree's pm/lock.json.

The archives are served on loopback. Nothing here contacts a registry or writes
the real Hermes home.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from pm.registry import get_package
from pm.store import current_target
from scripts.deploy.nemo.frontend_tools import FrontendToolError, dry_run_report, provision_path

ROOT = Path(__file__).resolve().parents[3]
VERSION = "9.9.9"


def _pack(files: dict[str, tuple[bytes, int]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, (data, mode) in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _script(text: str) -> bytes:
    return f"#!/bin/sh\nprintf '%s\\n' '{text}'\n".encode()


class _Server:
    def __init__(self, files: dict[str, bytes]) -> None:
        hits: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                name = self.path.rsplit("/", 1)[-1]
                body = files.get(name)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                hits.append(name)
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args) -> None:
                return

        self.hits = hits
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def _artifacts(target: str, server: _Server, blobs: dict[str, bytes]) -> dict:
    def one(name: str) -> dict[str, str]:
        return {"url": f"{server.url}/{name}", "sha256": _sha(blobs[name])}

    node = one("node.tgz")
    return {
        "schema": 1,
        "packages": {
            "node": {"version": VERSION, "artifacts": {target: node}},
            "pnpm": {
                "version": VERSION,
                "artifacts": {target: [one("pnpm-exe.tgz"), one("pnpm.tgz")]},
            },
        },
    }


def _tree(tmp_path: Path, server: _Server, blobs: dict[str, bytes]) -> tuple[Path, Path]:
    source = tmp_path / "source"
    (source / "pm").mkdir(parents=True)
    lock = _artifacts(current_target(), server, blobs)
    (source / "pm" / "lock.json").write_text(json.dumps(lock), encoding="utf-8")
    return source, tmp_path / "hermes"


def _blobs() -> dict[str, bytes]:
    exe_manifest = json.dumps({"version": VERSION, "marker": "exe"}).encode()
    launcher_manifest = json.dumps({"version": VERSION, "marker": "launcher"}).encode()
    return {
        "node.tgz": _pack({
            "node-v9/bin/node": (_script(f"v{VERSION}"), 0o644),
        }),
        "pnpm-exe.tgz": _pack({
            "package/pnpm": (_script(VERSION), 0o644),
            "package/package.json": (exe_manifest, 0o644),
        }),
        "pnpm.tgz": _pack({
            "package/package.json": (launcher_manifest, 0o644),
            "package/dist/keep.txt": (b"node-gyp\n", 0o644),
        }),
    }


def _cli(home: Path, source: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HERMES_HOME": str(home)}
    return subprocess.run(
        [
            sys.executable, "-m", "scripts.deploy.nemo.cli", "frontend-tools",
            "--source", str(source), "--hermes-home", str(home), *extra,
        ],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, check=False,
    )


@pytest.mark.platforms("linux", "macos")
def test_provision_puts_the_pin_ahead_of_a_newer_pnpm_and_reuses_it(tmp_path: Path) -> None:
    blobs = _blobs()
    server = _Server(blobs)
    source, home = _tree(tmp_path, server, blobs)
    decoy = tmp_path / "local" / "bin" / "pnpm"
    decoy.parent.mkdir(parents=True)
    decoy.write_bytes(_script("12.21.0"))
    decoy.chmod(0o755)
    before = decoy.read_bytes()
    try:
        first = _cli(home, source)
    finally:
        server.stop()
    assert first.returncode == 0, first.stderr
    prefix = first.stdout.strip()
    assert "\n" not in prefix
    assert "(downloaded)" in first.stderr
    pnpm_dir, node_dir = prefix.split(os.pathsep)
    assert json.loads((Path(pnpm_dir) / "package.json").read_text())["marker"] == "exe"
    assert (Path(pnpm_dir) / "dist" / "keep.txt").read_text() == "node-gyp\n"
    path = os.pathsep.join((prefix, str(decoy.parent)))
    found_pnpm = shutil.which("pnpm", path=path)
    found_node = shutil.which("node", path=path)
    assert found_pnpm == str(Path(pnpm_dir) / "pnpm")
    assert found_node == str(Path(node_dir) / "node")
    assert subprocess.check_output([found_pnpm, "--version"], text=True).strip() == VERSION
    assert subprocess.check_output([found_node, "--version"], text=True).strip() == f"v{VERSION}"
    assert decoy.read_bytes() == before
    assert not (home / "tools" / "facts.json").exists()

    second = _cli(home, source)
    assert second.returncode == 0, second.stderr
    assert second.stdout.strip() == prefix
    assert "(cached)" in second.stderr
    assert server.hits.count("node.tgz") == 1


@pytest.mark.platforms("linux", "macos")
def test_checksum_mismatch_publishes_nothing(tmp_path: Path) -> None:
    blobs = _blobs()
    server = _Server(blobs)
    source, home = _tree(tmp_path, server, blobs)
    lock_path = source / "pm" / "lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    target = current_target()
    lock["packages"]["node"]["artifacts"][target]["sha256"] = "0" * 64
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    try:
        done = _cli(home, source)
    finally:
        server.stop()
    assert done.returncode != 0
    assert "checksum mismatch" in done.stderr
    cache = home / "tools" / ".build-pins"
    assert list(cache.glob("node-*")) == []
    assert not (home / "tools" / "facts.json").exists()


@pytest.mark.platforms("linux", "macos")
def test_cleartext_off_loopback_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "pm").mkdir(parents=True)
    target = current_target()
    artifact = {
        "url": "http://example.com/node.tgz",
        "sha256": "a" * 64,
    }
    lock = {
        "schema": 1,
        "packages": {
            "node": {"version": VERSION, "artifacts": {target: artifact}},
            "pnpm": {"version": VERSION, "artifacts": {target: [artifact, artifact]}},
        },
    }
    (source / "pm" / "lock.json").write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(FrontendToolError, match="refusing URL"):
        dry_run_report(source, tmp_path / "hermes")


@pytest.mark.platforms("linux", "macos")
def test_matching_store_entry_is_reused_without_download(tmp_path: Path) -> None:
    blobs = _blobs()
    server = _Server({name: b"unused" for name in blobs})
    source, home = _tree(tmp_path, server, blobs)
    # The lock still names the real blob hashes; the server would 404 if hit.
    lock = json.loads((source / "pm" / "lock.json").read_text(encoding="utf-8"))
    target = current_target()
    node_sha = lock["packages"]["node"]["artifacts"][target]["sha256"]
    pnpm_shas = [item["sha256"] for item in lock["packages"]["pnpm"]["artifacts"][target]]
    tools = home / "tools"
    node_name = get_package("node").store_entry(VERSION, target)
    pnpm_name = get_package("pnpm").store_entry(VERSION, target)
    node_bin = tools / node_name / "bin" / "node"
    node_bin.parent.mkdir(parents=True)
    node_bin.write_bytes(_script(f"v{VERSION}"))
    node_bin.chmod(0o755)
    pnpm_bin = tools / pnpm_name / "pnpm"
    pnpm_bin.parent.mkdir(parents=True)
    pnpm_bin.write_bytes(_script(VERSION))
    pnpm_bin.chmod(0o755)
    (pnpm_bin.parent / "package.json").write_text(
        json.dumps({"version": VERSION, "marker": "store"}), encoding="utf-8",
    )
    facts = {
        "schema": 1,
        "packages": {
            "node": {
                "entry": node_name, "version": VERSION, "target": target,
                "artifacts": [node_sha],
            },
            "pnpm": {
                "entry": pnpm_name, "version": VERSION, "target": target,
                "artifacts": pnpm_shas,
            },
        },
    }
    facts_path = tools / "facts.json"
    facts_path.write_text(json.dumps(facts), encoding="utf-8")
    original = facts_path.read_bytes()
    try:
        done = _cli(home, source)
    finally:
        server.stop()
    assert done.returncode == 0, done.stderr
    assert "(store)" in done.stderr
    assert server.hits == []
    assert facts_path.read_bytes() == original
    pnpm_dir = done.stdout.strip().split(os.pathsep)[0]
    assert Path(pnpm_dir) == pnpm_bin.parent.resolve()


@pytest.mark.platforms("linux", "macos")
def test_store_entry_with_a_different_hash_is_not_reused(tmp_path: Path) -> None:
    blobs = _blobs()
    server = _Server(blobs)
    source, home = _tree(tmp_path, server, blobs)
    target = current_target()
    tools = home / "tools"
    node_name = get_package("node").store_entry(VERSION, target)
    node_bin = tools / node_name / "bin" / "node"
    node_bin.parent.mkdir(parents=True)
    node_bin.write_bytes(_script("v0.0.1"))
    node_bin.chmod(0o755)
    facts = {
        "schema": 1,
        "packages": {
            "node": {
                "entry": node_name, "version": VERSION, "target": target,
                "artifacts": ["f" * 64],
            },
        },
    }
    (tools / "facts.json").write_text(json.dumps(facts), encoding="utf-8")
    try:
        done = _cli(home, source)
    finally:
        server.stop()
    assert done.returncode == 0, done.stderr
    assert "node.tgz" in server.hits
    prefix = done.stdout.strip().split(os.pathsep)
    assert Path(prefix[1]).name == "bin"
    assert "v0.0.1" not in subprocess.check_output(
        [str(Path(prefix[1]) / "node"), "--version"], text=True,
    )


@pytest.mark.platforms("linux", "macos")
def test_real_lock_dry_run_does_not_download(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    done = _cli(home, ROOT, "--dry-run")
    assert done.returncode == 0, done.stderr
    assert "node:" in done.stdout
    assert "pnpm:" in done.stdout
    assert "https://" in done.stdout
    assert not (home / "tools" / ".build-pins").exists()

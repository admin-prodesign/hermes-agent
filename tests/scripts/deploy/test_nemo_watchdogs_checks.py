"""Each nemo watchdog check against fixtures. No live host, journal, or webhook."""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.deploy.nemo.watchdogs import autodeploy, backup, failures, gateway, host


@pytest.fixture
def watch_home(tmp_path: Path, monkeypatch) -> Path:
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return home


def _proc(code: int = 0, stdout: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=code, stdout=stdout, stderr="")


def test_failed_units_and_cron_streak(watch_home: Path) -> None:
    jobs = {
        "jobs": [
            {"id": "abc123", "enabled": True, "failure_streak": 2, "last_error": "token=secret-value"},
            {"id": "okjob", "enabled": True, "failure_streak": 0},
            {"id": "paused", "enabled": False, "failure_streak": 9},
        ]
    }
    (watch_home / "cron").mkdir()
    (watch_home / "cron" / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    profile = watch_home / "profiles" / "pdone" / "cron"
    profile.mkdir(parents=True)
    profile.joinpath("jobs.json").write_text(
        json.dumps({"jobs": [{"id": "sat1", "enabled": True, "failure_streak": 1}]}),
        encoding="utf-8",
    )

    def runner(argv, **_kwargs):
        if "--user" in argv:
            return _proc(0, "hermes-watchdog-host.service loaded failed failed\n")
        return _proc(0, "ssh.service loaded failed failed\n")

    items = failures.collect(home=watch_home, runner=runner, journal=[], logs=[])
    keys = {item.key for item in items}
    assert "unit:system:ssh.service" in keys
    assert "unit:user:hermes-watchdog-host.service" in keys
    assert "cron:default:abc123" in keys
    assert "cron:pdone:sat1" in keys
    assert "cron:default:okjob" not in keys
    assert "cron:default:paused" not in keys
    cron = next(item for item in items if item.key == "cron:default:abc123")
    assert "secret-value" not in json.dumps(cron.details)


def test_pdone_escalation_and_bitwarden_503_count_only(watch_home: Path) -> None:
    repairer = watch_home / "profiles" / "pdone" / "state"
    repairer.mkdir(parents=True)
    repairer.joinpath("repairer-escalation.json").write_text(
        json.dumps({"status": "escalated", "message": "do not leak this body"}),
        encoding="utf-8",
    )
    journal = [
        "bws secret list: HTTP 503 Service Unavailable",
        "unrelated 503 from nginx",
        "bitwarden vault ok",
    ]
    items = failures.collect(home=watch_home, runner=lambda *_a, **_k: _proc(), journal=journal, logs=[])
    keys = {item.key for item in items}
    assert "pdone:repairer" in keys
    assert "bws503:journal" in keys
    bws = next(item for item in items if item.key == "bws503:journal")
    assert bws.details == {"source": "journal", "count": 1}
    assert "Service Unavailable" not in json.dumps(bws.details)


def test_gateway_http_200_and_identify_ok(watch_home: Path) -> None:
    items = gateway.collect(
        home=watch_home,
        getter=lambda _url: (200, None),
        identify=lambda _home: {"protocol": 1, "pid": 1},
    )
    assert items == []


def test_gateway_http_and_socket_failures(watch_home: Path) -> None:
    items = gateway.collect(
        home=watch_home,
        getter=lambda url: (503 if "8644" in url else None, "http_error" if "8644" in url else "unreachable"),
        identify=lambda _home: None,
    )
    keys = {item.key for item in items}
    assert any(key.startswith("http:") and "8644" in key for key in keys)
    assert any(key.startswith("http:") and "8765" in key for key in keys)
    assert "socket:default" in keys
    assert "socket:pdone" in keys
    assert all("token" not in json.dumps(item.details) for item in items)


@pytest.mark.platforms("linux", "macos")
def test_raw_identify_speaks_control_socket_protocol(tmp_path: Path) -> None:
    sock_path = tmp_path / "gateway.sock"
    ready = threading.Event()

    def serve() -> None:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock_path))
        server.listen(1)
        ready.set()
        conn, _addr = server.accept()
        raw = conn.recv(4096)
        request = json.loads(raw.partition(b"\n")[0].decode())
        assert request["verb"] == "identify"
        conn.sendall(b'{"ok": true, "result": {"protocol": 1, "pid": 9}}\n')
        conn.close()
        server.close()

    thread = threading.Thread(target=serve)
    thread.start()
    assert ready.wait(2)
    payload = gateway.raw_identify(tmp_path, timeout=2.0)
    thread.join(2)
    assert payload == {"protocol": 1, "pid": 9}


def test_autodeploy_refused_status_units_and_drift(watch_home: Path) -> None:
    deploy = watch_home / "deploy"
    deploy.mkdir()
    deploy.joinpath("refused.jsonl").write_text('{"sha": "a" * 0}\n{"sha": "deadbeef"}\n', encoding="utf-8")
    deploy.joinpath("status.json").write_text(json.dumps({"result": "failed", "detail": "nope"}), encoding="utf-8")

    def lifecycle(unit: str):
        if unit.endswith(".timer"):
            return False, False
        return True, True

    items = autodeploy.collect(home=watch_home, lifecycle=lifecycle, failed=lambda _unit: True)
    keys = {item.key for item in items}
    assert "deploy-unit:hermes-deploy-poll.timer" in keys
    assert "deploy:refused" in keys
    assert "deploy:status" in keys
    assert "deploy:drift" in keys
    status = next(item for item in items if item.key == "deploy:status")
    assert status.details == {"result": "failed"}


def test_autodeploy_quiet_when_units_live_and_status_ok(watch_home: Path) -> None:
    deploy = watch_home / "deploy"
    deploy.mkdir()
    deploy.joinpath("status.json").write_text(json.dumps({"result": "deployed"}), encoding="utf-8")
    items = autodeploy.collect(
        home=watch_home,
        lifecycle=lambda _unit: (True, True),
        failed=lambda _unit: False,
    )
    assert items == []


def test_host_thresholds(watch_home: Path) -> None:
    total = 1000
    warn = host.collect(
        home=watch_home,
        disk=(total, 860, 140),
        meminfo={"MemTotal": 1000, "MemAvailable": 200, "SwapTotal": 100, "SwapFree": 50},
        thermals=[("thermal_zone0", 70.0)],
    )
    assert warn == []
    bad = host.collect(
        home=watch_home,
        disk=(total, 920, 80),
        meminfo={"MemTotal": 1000, "MemAvailable": 50, "SwapTotal": 100, "SwapFree": 10},
        thermals=[("thermal_zone0", 91.0)],
    )
    keys = {item.key for item in bad}
    assert keys == {"host:disk", "host:memory", "host:swap", "host:thermal:thermal_zone0"}
    disk = next(item for item in bad if item.key == "host:disk")
    assert disk.severity == "crit"


def test_backup_missing_fresh_and_stale(watch_home: Path) -> None:
    assert backup.collect(home=watch_home, clock=lambda: 1000)[0].key == "backup:missing"
    marker = watch_home / "backups"
    marker.mkdir()
    path = marker / "last-successful-push"
    path.write_text("2026-10-16T08:00:00Z\n", encoding="utf-8")
    stamp = backup.parse_timestamp("2026-10-16T08:00:00Z")
    assert stamp is not None
    assert backup.collect(home=watch_home, clock=lambda: stamp + 3600) == []
    stale = backup.collect(home=watch_home, clock=lambda: stamp + 27 * 3600)
    assert stale[0].key == "backup:stale"
    assert stale[0].details["source"] == "marker"


def test_backup_git_log(watch_home: Path, monkeypatch) -> None:
    repo = watch_home / "backup-repo"
    repo.mkdir()
    monkeypatch.setenv("NEMO_WATCH_BACKUP_REPO", str(repo))

    def runner(argv, **_kwargs):
        assert argv[:3] == ["git", "-C", str(repo)]
        return _proc(0, "100\n")

    assert backup.collect(home=watch_home, clock=lambda: 200, runner=runner) == []
    stale = backup.collect(home=watch_home, clock=lambda: 100 + 30 * 3600, runner=runner)
    assert stale[0].key == "backup:stale"


class _Health(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *_args) -> None:
        return


def test_http_status_accepts_200() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Health)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/health"
        status, error = gateway.http_status(url, timeout=2)
        assert (status, error) == (200, None)
    finally:
        server.shutdown()
        server.server_close()

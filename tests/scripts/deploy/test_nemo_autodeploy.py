"""Push deploy on nemo: signed requests, the idle gate, rollback, the no-restart path, and drift.

Shell steps run the real ``cutover.sh`` against a temp release tree; git steps use a
real bare origin and ``--mirror`` clone. Nothing here touches systemd or the real
Hermes home.
"""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from scripts.deploy.nemo import autodeploy
from scripts.deploy.nemo.autodeploy import Config, Hooks, check_drift, on_main, run_once
from scripts.deploy.nemo.autodeploy_units import UnitOptions, ensure_secret, render
from scripts.deploy.nemo.changes import NOOP, RESTART, SKILLS, classify
from scripts.deploy.nemo.listener import ListenerConfig, serve
from scripts.deploy.nemo.manifest import write_manifest
from scripts.deploy.nemo.notify import notify
from scripts.deploy.nemo.retention import keep_set, prune, running_build, set_running
from scripts.deploy.nemo.spool import enqueue, queue_dir, take_latest
from scripts.deploy.nemo.webhook import DeployRequest, Rejected, request_body, require_peer_tag, signed_headers

ROOT = Path(__file__).resolve().parents[3]
NEMO = ROOT / "scripts" / "deploy" / "nemo"
REPO = "admin-prodesign/hermes-agent"
MAIN = "refs/heads/main"
SECRET = b"s" * 48
SHA_A = "a" * 40


# ---------------------------------------------------------------- helpers


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    done = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=30, check=True)
    return done.stdout.strip()


def _commit(work: Path, files: dict[str, str], message: str) -> str:
    for rel, text in files.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", message)
    return _git(work, "rev-parse", "HEAD")


@pytest.fixture
def origin(tmp_path: Path):
    """A work tree pushing to a bare origin, and nemo's ``--mirror`` clone of it."""
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(bare), str(work))
    _git(work, "checkout", "-q", "-b", "main")
    base = _commit(work, {"pyproject.toml": "[project]\nname = 'x'\n", "agent/core.py": "X = 1\n",
                          "skills/demo/SKILL.md": "v1\n"}, "base")
    _git(work, "push", "-q", "origin", "main")
    mirror = tmp_path / "mirror.git"
    _git(tmp_path, "clone", "-q", "--mirror", str(bare), str(mirror))
    return work, mirror, base


def _release(releases: Path, build: str) -> Path:
    release = releases / build
    (release / ".venv" / "bin").mkdir(parents=True)
    (release / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    os.symlink(sys.executable, release / ".venv" / "bin" / "python")
    return release


def _live_home(tmp_path: Path, old_sha: str, build: str = "old") -> tuple[Path, Path]:
    home = tmp_path / "hermes"
    releases = home / "releases"
    _release(releases, build)
    os.symlink(build, releases / "current")
    write_manifest(home / "upgrade-audits" / build / "manifest.json",
                   {"build": build, "sha": old_sha, "releases": str(releases)})
    return home, releases


def _write_db(path: Path, message_at: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE messages (timestamp REAL)")
    conn.execute("INSERT INTO messages (timestamp) VALUES (?)", (message_at,))
    conn.commit()
    conn.close()


def _cutover(home: Path, build: str, *extra: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "NEMO_PYTHON": sys.executable}
    argv = ["bash", str(NEMO / "cutover.sh"), "--hermes-home", str(home), "--build", build,
            "--sha", "b" * 40, "--unit-dir", str(home / "units"), "--skip-preflight", "--skip-postcheck",
            *extra]
    return subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120, check=False)


class _Health(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b'{"status": "ok"}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


@pytest.fixture
def running_server():
    servers: list[ThreadingHTTPServer] = []

    def start(server: ThreadingHTTPServer) -> str:
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def _post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, dict]:
    request = Request(url, data=body, method="POST", headers=headers)
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ---------------------------------------------------------------- auth


def test_listener_queues_only_signed_main_requests(tmp_path: Path, running_server) -> None:
    queue = tmp_path / "queue"
    base = running_server(serve(ListenerConfig(SECRET, queue, REPO), "127.0.0.1", 0))
    url = base + "/deploy"
    good = request_body(SHA_A, MAIN, REPO, "1")

    assert _post(url, good, {})[0] == 401
    assert _post(url, good, signed_headers(b"x" * 48, good, time.time()))[0] == 401
    assert _post(url, good, signed_headers(SECRET, good, time.time() - 3600))[0] == 401
    tampered = signed_headers(SECRET, good, time.time())
    assert _post(url, request_body("b" * 40, MAIN, REPO, "1"), tampered)[0] == 401
    branch = request_body(SHA_A, "refs/heads/feature", REPO, "1")
    assert _post(url, branch, signed_headers(SECRET, branch, time.time()))[0] == 403
    fork = request_body(SHA_A, MAIN, "someone/fork", "1")
    assert _post(url, fork, signed_headers(SECRET, fork, time.time()))[0] == 403
    short = request_body("abc1234", MAIN, REPO, "1")
    assert _post(url, short, signed_headers(SECRET, short, time.time()))[0] == 400
    assert not list(queue.glob("*.json"))

    headers = signed_headers(SECRET, good, time.time())
    assert _post(url, good, headers) == (202, {"queued": SHA_A})
    assert _post(url, good, headers) == (200, {"duplicate": SHA_A})
    assert len(list(queue.glob("*.json"))) == 1


def test_ci_notify_reaches_the_listener(tmp_path: Path, running_server) -> None:
    queue = tmp_path / "queue"
    base = running_server(serve(ListenerConfig(SECRET, queue, REPO), "127.0.0.1", 0))
    body = request_body(SHA_A, MAIN, REPO, "42")
    assert notify(base + "/deploy", SECRET, body, sleep=lambda _s: None) == 0
    item, _ = take_latest(queue)
    assert item is not None and item.sha == SHA_A and item.run_id == "42"
    assert notify(base + "/deploy", b"w" * 48, body, sleep=lambda _s: None) == 1


def test_tailscale_tag_is_required_from_a_tagged_peer() -> None:
    def whois(tags):
        payload = json.dumps({"Node": {"Tags": tags}}).encode()
        return lambda argv: subprocess.CompletedProcess(argv, 0, payload, b"")

    require_peer_tag("100.64.0.5", "tag:ci", run=whois(["tag:ci"]))
    with pytest.raises(Rejected, match="not tag:ci"):
        require_peer_tag("100.64.0.5", "tag:ci", run=whois(["tag:laptop"]))
    with pytest.raises(Rejected, match="loopback"):
        require_peer_tag("127.0.0.1", "tag:ci", run=whois(["tag:ci"]))


def test_worker_refuses_a_sha_that_is_not_on_main(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    _git(work, "checkout", "-q", "-b", "feature")
    side = _commit(work, {"agent/core.py": "X = 2\n"}, "side")
    _git(work, "push", "-q", "origin", "feature")
    _git(mirror, "fetch", "-q", "origin", "+refs/heads/feature:refs/heads/feature")
    cfg = Config(home=tmp_path / "hermes", mirror=mirror, releases=tmp_path / "hermes" / "releases")
    assert on_main(cfg, base, autodeploy.run_cmd) is None
    assert "not on main" in (on_main(cfg, side, autodeploy.run_cmd) or "")


# ---------------------------------------------------------------- idle gate and rollback


@pytest.mark.platforms("linux", "macos")
def test_cutover_does_not_touch_a_busy_profile(tmp_path: Path) -> None:
    home, releases = _live_home(tmp_path, SHA_A)
    _release(releases, "new")
    _write_db(home / "profiles" / "pdone" / "state.db", time.time())
    proc = _cutover(home, "new", "--profile", "pdone", "--quiet", "90", "--poll", "0.1",
                    "--gate-timeout", "0.3")
    assert proc.returncode == 75, proc.stderr
    assert os.readlink(releases / "current") == "old"
    assert not (home / "upgrade-audits" / "new" / "manifest.json").exists()


@pytest.mark.platforms("linux", "macos")
def test_cutover_rolls_back_when_health_fails(tmp_path: Path) -> None:
    home, releases = _live_home(tmp_path, SHA_A)
    _release(releases, "new")
    dead = "http://127.0.0.1:9/health"
    proc = _cutover(home, "new", "--skip-gate", "--skip-restart", "--gateway-health", dead,
                    "--dashboard-health", dead, "--health-timeout", "1", "--health-interval", "0.2")
    assert proc.returncode == 1
    assert "rolling back" in proc.stderr
    assert os.readlink(releases / "current") == "old"


@pytest.mark.platforms("linux", "macos")
def test_cutover_stays_on_the_new_release_when_healthy(tmp_path: Path, running_server) -> None:
    home, releases = _live_home(tmp_path, SHA_A)
    _release(releases, "new")
    ok = running_server(ThreadingHTTPServer(("127.0.0.1", 0), _Health)) + "/health"
    proc = _cutover(home, "new", "--skip-gate", "--skip-restart", "--gateway-health", ok,
                    "--dashboard-health", ok, "--health-timeout", "10")
    assert proc.returncode == 0, proc.stderr
    assert os.readlink(releases / "current") == "new"


def _queue(home: Path, sha: str) -> None:
    enqueue(queue_dir(home), DeployRequest(sha, MAIN, REPO, "1"), peer="127.0.0.1")


class _Recorder:
    """Fake build.sh; cutover.sh is either the real script or a canned exit code."""

    def __init__(self, releases: Path, home: Path, cutover_code: int | None = None) -> None:
        self.releases, self.home, self.cutover_code = releases, home, cutover_code
        self.calls: list[list[str]] = []
        self.systemctl: list[list[str]] = []
        self.synced: list[Path] = []

    def script(self, argv: list[str]) -> int:
        self.calls.append(argv)
        if argv[1].endswith("build.sh"):
            build = argv[argv.index("--build") + 1]
            _release(self.releases, build)
            write_manifest(self.home / "upgrade-audits" / build / "manifest.json",
                           {"build": build, "sha": argv[argv.index("--sha") + 1]})
            return 0
        if self.cutover_code is not None:
            return self.cutover_code
        env = {**os.environ, "NEMO_PYTHON": sys.executable}
        argv = [*argv, "--unit-dir", str(self.home / "units")]
        return subprocess.run(argv, env=env, timeout=120, check=False).returncode

    def sync(self, release: Path, _home: Path, profiles: tuple[str, ...]) -> list[dict]:
        self.synced.append(release)
        return [{"profile": name, "ok": True, "detail": {}} for name in profiles]

    def hooks(self) -> Hooks:
        return Hooks(script=self.script, sync=self.sync, disk_free=lambda _p: 100.0,
                     systemctl=lambda argv: self.systemctl.append(argv) or 0)


@pytest.mark.platforms("linux", "macos")
def test_worker_requeues_while_profiles_are_busy(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    new = _commit(work, {"agent/core.py": "X = 2\n"}, "code")
    _git(work, "push", "-q", "origin", "main")
    home, releases = _live_home(tmp_path, base)
    _queue(home, new)
    fake = _Recorder(releases, home, cutover_code=autodeploy.GATE_BUSY)
    outcome = run_once(Config(home=home, mirror=mirror, releases=releases), fake.hooks())
    assert outcome.result == "waiting" and outcome.mode == RESTART
    assert os.readlink(releases / "current") == "old"
    item, _ = take_latest(queue_dir(home))
    assert item is not None and item.sha == new and item.attempts == 1
    assert (releases / new[:12]).is_dir()
    assert fake.systemctl == []


@pytest.mark.platforms("linux", "macos")
def test_worker_prunes_a_rolled_back_build_and_keeps_the_live_one(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    new = _commit(work, {"agent/core.py": "X = 3\n"}, "code")
    _git(work, "push", "-q", "origin", "main")
    home, releases = _live_home(tmp_path, base)
    _queue(home, new)
    outcome = run_once(Config(home=home, mirror=mirror, releases=releases),
                       _Recorder(releases, home, cutover_code=1).hooks())
    assert outcome.result == "failed" and "still on old" in outcome.detail
    assert os.readlink(releases / "current") == "old"
    assert running_build(releases) == "old"
    assert not (releases / new[:12]).exists()
    status = json.loads((home / "deploy" / "status.json").read_text(encoding="utf-8"))
    assert status["result"] == "failed"


# ---------------------------------------------------------------- no-restart path


def test_classify_only_skips_restart_for_docs_and_skills() -> None:
    assert classify(["website/docs/x.md", "tests/a.py", "README.md", "agent/AGENTS.md"]) == NOOP
    assert classify(["skills/demo/SKILL.md", "website/x.md"]) == SKILLS
    assert classify(["skills/demo/SKILL.md", "agent/prompt_builder.py"]) == RESTART
    assert classify(["SOUL.md"]) == RESTART
    assert classify(None) == RESTART
    assert classify([]) == NOOP


@pytest.mark.platforms("linux", "macos")
def test_skills_only_merge_swaps_without_restarting(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    new = _commit(work, {"skills/demo/SKILL.md": "v2\n"}, "skill")
    _git(work, "push", "-q", "origin", "main")
    home, releases = _live_home(tmp_path, base)
    _queue(home, new)
    fake = _Recorder(releases, home)
    outcome = run_once(Config(home=home, mirror=mirror, releases=releases), fake.hooks())
    assert outcome.result == "deployed" and outcome.mode == SKILLS, outcome
    assert os.readlink(releases / "current") == new[:12]
    assert running_build(releases) == "old"
    assert fake.synced == [releases / new[:12]]
    assert fake.systemctl == [["--user", "try-restart", autodeploy.LISTENER_UNIT]]
    cutover = next(argv for argv in fake.calls if argv[1].endswith("cutover.sh"))
    assert "--skip-restart" in cutover and "--skip-gate" in cutover


@pytest.mark.platforms("linux", "macos")
def test_worker_ignores_a_request_older_than_the_live_sha(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    newer = _commit(work, {"agent/core.py": "X = 4\n"}, "code")
    _git(work, "push", "-q", "origin", "main")
    home, releases = _live_home(tmp_path, newer)
    _queue(home, base)
    fake = _Recorder(releases, home)
    outcome = run_once(Config(home=home, mirror=mirror, releases=releases), fake.hooks())
    assert outcome.result == "rejected" and "older" in outcome.detail
    assert fake.calls == []


# ---------------------------------------------------------------- retention


def test_prune_keeps_current_its_rollback_target_and_the_running_build(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    releases = home / "releases"
    for name in ("r1", "r2", "r3", "r4"):
        _release(releases, name)
        (releases / name).chmod(stat.S_IRUSR | stat.S_IXUSR)
    os.symlink("r4", releases / "current")
    write_manifest(home / "upgrade-audits" / "r4" / "manifest.json", {"previous": "r3"})
    set_running(releases, "r2")
    stale = releases / ".staging-r5.abc"
    stale.mkdir()
    os.utime(stale, (0, 0))
    fresh = releases / ".staging-r6.abc"
    fresh.mkdir()

    removed = prune(releases, keep_set(home, releases, with_previous=True))
    assert removed == [".staging-r5.abc", "r1"]
    assert sorted(p.name for p in releases.iterdir() if not p.name.startswith(".")) == ["current", "r2", "r3", "r4"]
    assert fresh.is_dir()
    assert prune(releases, keep_set(home, releases, with_previous=False)) == ["r3"]
    assert prune(tmp_path / "empty", set()) == []


# ---------------------------------------------------------------- drift


def test_drift_reports_edits_deletions_strays_and_old_units(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    home, releases = _live_home(tmp_path, base)
    live = releases / "old"
    for rel in ("agent/core.py", "skills/demo/SKILL.md"):
        (live / rel).parent.mkdir(parents=True, exist_ok=True)
        (live / rel).write_bytes((work / rel).read_bytes())
    (live / "pyproject.toml").write_bytes((work / "pyproject.toml").read_bytes())
    (live / ".venv" / "lib").mkdir()
    (live / ".venv" / "lib" / "site.py").write_text("ok\n", encoding="utf-8")
    cfg = Config(home=home, mirror=mirror, releases=releases)
    units = tmp_path / "units"
    units.mkdir()

    assert check_drift(cfg, unit_dirs=[units], max_lag_s=0).clean

    (live / "agent" / "core.py").write_text("X = 'hand edit'\n", encoding="utf-8")
    (live / "skills" / "demo" / "SKILL.md").unlink()
    (live / "agent" / "patch.py").write_text("print(1)\n", encoding="utf-8")
    (units / "hermes-gateway.service").write_text(
        f"ExecStart={releases.resolve()}/gone/.venv/bin/python\n", encoding="utf-8")
    report = check_drift(cfg, unit_dirs=[units], max_lag_s=0)
    assert report.modified == ["agent/core.py"]
    assert report.missing == ["skills/demo/SKILL.md"]
    assert report.extra == ["agent/patch.py"]
    assert report.units and "gone" in report.units[0]
    assert "hand edit" not in report.summary()


def test_drift_flags_main_moving_ahead_of_the_live_sha(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    _commit(work, {"agent/core.py": "X = 5\n"}, "ahead")
    _git(work, "push", "-q", "origin", "main")
    home, releases = _live_home(tmp_path, base)
    cfg = Config(home=home, mirror=mirror, releases=releases)
    later = time.time() + 7200
    report = check_drift(cfg, unit_dirs=[], max_lag_s=3600, now=later)
    assert report.behind and base[:12] in report.behind
    assert check_drift(cfg, unit_dirs=[], max_lag_s=3600 * 4, now=later).behind is None


# ---------------------------------------------------------------- install


def test_units_run_from_current_and_never_embed_the_secret(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    secret = home / "deploy" / "webhook-secret"
    assert ensure_secret(secret) is True
    assert ensure_secret(secret) is False
    assert stat.S_IMODE(secret.stat().st_mode) == 0o600
    value = secret.read_text(encoding="utf-8").strip()
    assert len(value) >= 32

    opts = UnitOptions(home=home, releases=home / "releases", mirror=tmp_path / "mirror.git",
                       require_tag="tag:ci", path_env="/usr/bin")
    units = render(opts)
    assert all(value not in text for text in units.values())
    current = str(home / "releases" / "current")
    listener = units["hermes-deploy-listener.service"]
    assert f"{current}/.venv/bin/python -m scripts.deploy.nemo.listener" in listener
    assert "--require-tailscale-tag tag:ci" in listener
    assert f"--mirror {tmp_path / 'mirror.git'}" in units["hermes-deploy.service"]
    assert f"DirectoryNotEmpty={home / 'deploy' / 'queue'}" in units["hermes-deploy.path"]
    assert "User=" not in "".join(units.values())


@pytest.mark.platforms("linux", "macos")
def test_new_shell_entry_points_parse() -> None:
    for name in ("install_autodeploy.sh", "cutover.sh"):
        subprocess.run(["bash", "-n", str(NEMO / name)], check=True, timeout=20)

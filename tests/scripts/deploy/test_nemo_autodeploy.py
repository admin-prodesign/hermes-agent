"""Pull deploy on nemo: the main poller, the idle gate, rollback, the no-restart path, and drift.

Shell steps run the real ``cutover.sh`` against a temp release tree; git steps use a
real bare origin and ``--mirror`` clone, so the poller's ``git ls-remote`` is real too.
Nothing here touches systemd, the network, or the real Hermes home.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from scripts.deploy.nemo import autodeploy, poll
from scripts.deploy.nemo.autodeploy import (
    Config, Hooks, _script_env, build_name, check_drift, fetch_main, on_main, run_once, run_script,
    script_failure_detail,
)
from scripts.deploy.nemo.autodeploy_units import UnitOptions, render
from scripts.deploy.nemo.changes import NOOP, RESTART, SKILLS, classify
from scripts.deploy.nemo.manifest import live_sha, main_matches_live, sha_from_release_name, write_manifest
from scripts.deploy.nemo.preflight import deploy_preflight
from scripts.deploy.nemo.poll import PollResult, poll_once
from scripts.deploy.nemo.retention import audit_rollback_targets, keep_set, prune, running_build, set_running
from scripts.deploy.nemo import autodeploy_units
from scripts.deploy.nemo.spool import enqueue, queue_dir, queued_shas, refuse, refused_shas

ROOT = Path(__file__).resolve().parents[3]
NEMO = ROOT / "scripts" / "deploy" / "nemo"
MAIN = "refs/heads/main"
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


@pytest.fixture(autouse=True)
def _uv_available_for_deploy(monkeypatch) -> None:
    real_which = shutil.which

    def _which(cmd: str, path: str | None = None) -> str | None:
        if cmd == "uv":
            return "/bin/uv"
        return real_which(cmd, path=path)

    monkeypatch.setattr("scripts.deploy.nemo.preflight.shutil.which", _which)


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
    env = {**os.environ, "NEMO_PYTHON": sys.executable, "NEMO_DEPLOY_SOCKET_PROFILES": ""}
    argv = ["bash", str(NEMO / "cutover.sh"), "--hermes-home", str(home), "--build", build,
            "--sha", "b" * 40, "--unit-dir", str(home / "units"), "--skip-preflight", "--skip-selftest",
            "--skip-postcheck", "--skip-adapter-gate", *extra]
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


# ---------------------------------------------------------------- poll


def _poll(home: Path, releases: Path, mirror: Path, **kwargs) -> PollResult:
    return poll_once(Config(home=home, mirror=mirror, releases=releases), **kwargs)


def _push(work: Path, files: dict[str, str]) -> str:
    sha = _commit(work, files, "change")
    _git(work, "push", "-q", "origin", "main")
    return sha


@pytest.mark.platforms("linux", "macos")
def test_poll_queues_a_new_main_once_and_goes_quiet_after_the_deploy(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    home, releases = _live_home(tmp_path, base)
    queue = queue_dir(home)
    assert _poll(home, releases, mirror).action == "live"
    assert not queued_shas(queue)

    new = _push(work, {"skills/demo/SKILL.md": "v2\n"})
    result = _poll(home, releases, mirror)
    assert (result.action, result.main, result.live) == ("queued", new, base)
    assert _poll(home, releases, mirror).action == "pending"
    assert len(list(queue.glob("*.json"))) == 1

    outcome = run_once(Config(home=home, mirror=mirror, releases=releases), _Recorder(releases, home).hooks())
    assert outcome.result == "deployed" and outcome.sha == new, outcome
    assert _poll(home, releases, mirror).action == "live"
    assert not queued_shas(queue)
    recorded = json.loads((home / "deploy" / "poll.json").read_text(encoding="utf-8"))
    assert recorded["action"] == "live" and recorded["live"] == new


@pytest.mark.platforms("linux", "macos")
def test_poll_does_not_run_beside_a_deploy_that_holds_the_lock(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    _push(work, {"agent/core.py": "X = 2\n"})
    home, releases = _live_home(tmp_path, base)
    calls: list[list[str]] = []

    def git(argv: list[str], timeout: float) -> subprocess.CompletedProcess:
        calls.append(argv)
        return autodeploy.run_cmd(argv, timeout)

    with autodeploy.deploy_lock(autodeploy.lock_path(home)) as held:
        assert held
        assert _poll(home, releases, mirror, git=git).action == "busy"
    assert calls == [] and not queued_shas(queue_dir(home))
    assert _poll(home, releases, mirror, git=git).action == "queued"


@pytest.mark.platforms("linux", "macos")
def test_poll_skips_a_refused_sha_until_retry(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    new = _push(work, {"agent/core.py": "X = 2\n"})
    home, releases = _live_home(tmp_path, base)
    refuse(home, new, "failed", "cutover exited 1; still on old")
    assert _poll(home, releases, mirror).action == "refused"
    assert not queued_shas(queue_dir(home))

    assert autodeploy.main(["retry", "--hermes-home", str(home), new]) == 0
    assert new not in refused_shas(home)
    assert _poll(home, releases, mirror).action == "queued"


@pytest.mark.platforms("linux", "macos")
def test_a_failed_or_hung_ls_remote_never_queues(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    _push(work, {"agent/core.py": "X = 2\n"})
    home, releases = _live_home(tmp_path, base)
    _git(mirror, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    result = _poll(home, releases, mirror)
    assert result.action == "error" and result.exit_code == 1 and result.live == base

    def hang(argv: list[str], timeout: float) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(argv, timeout)

    assert "timed out" in _poll(home, releases, mirror, git=hang).detail
    assert poll.main(["--hermes-home", str(home), "--mirror", str(mirror)]) == 1
    assert not queued_shas(queue_dir(home))


@pytest.mark.platforms("linux", "macos")
def test_worker_defers_without_refusing_when_main_cannot_be_fetched(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    new = _push(work, {"agent/core.py": "X = 2\n"})
    home, releases = _live_home(tmp_path, base)
    _queue(home, new)
    _git(mirror, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    fake = _Recorder(releases, home)
    outcome = run_once(Config(home=home, mirror=mirror, releases=releases), fake.hooks())
    assert outcome.result == "deferred" and not outcome.alert
    assert fake.calls == [] and new not in refused_shas(home)


def test_worker_refuses_a_sha_that_is_not_on_main(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    _git(work, "checkout", "-q", "-b", "feature")
    side = _commit(work, {"agent/core.py": "X = 2\n"}, "side")
    _git(work, "push", "-q", "origin", "feature")
    _git(mirror, "fetch", "-q", "origin", "+refs/heads/feature:refs/heads/feature")
    cfg = Config(home=tmp_path / "hermes", mirror=mirror, releases=tmp_path / "hermes" / "releases")
    assert fetch_main(cfg, autodeploy.run_cmd) is None
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
    enqueue(queue_dir(home), sha, ref=MAIN)


class _Recorder:
    """Fake build.sh; cutover.sh is either the real script or a canned exit code."""

    def __init__(self, releases: Path, home: Path, cutover_code: int | None = None) -> None:
        self.releases, self.home, self.cutover_code = releases, home, cutover_code
        self.calls: list[list[str]] = []
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
        # The fake releases carry no tools/ package for the PD One selftest.
        argv = [*argv, "--unit-dir", str(self.home / "units"), "--skip-selftest"]
        return subprocess.run(argv, env=env, timeout=120, check=False).returncode

    def sync(self, release: Path, _home: Path, profiles: tuple[str, ...]) -> list[dict]:
        self.synced.append(release)
        return [{"profile": name, "ok": True, "detail": {}} for name in profiles]

    def hooks(self) -> Hooks:
        return Hooks(script=self.script, sync=self.sync, disk_free=lambda _p: 100.0)


@pytest.mark.platforms("linux", "macos")
def test_busy_profiles_leave_the_sha_for_the_next_poll(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    new = _commit(work, {"agent/core.py": "X = 2\n"}, "code")
    _git(work, "push", "-q", "origin", "main")
    home, releases = _live_home(tmp_path, base)
    _queue(home, new)
    fake = _Recorder(releases, home, cutover_code=autodeploy.GATE_BUSY)
    outcome = run_once(Config(home=home, mirror=mirror, releases=releases), fake.hooks())
    assert outcome.result == "waiting" and outcome.mode == RESTART
    assert os.readlink(releases / "current") == "old"
    assert (releases / build_name(new)).is_dir()
    assert new not in refused_shas(home)
    assert _poll(home, releases, mirror).action == "queued"


@pytest.mark.platforms("linux", "macos")
def test_worker_keeps_failed_build_dir_and_does_not_prune_on_cutover_failure(tmp_path: Path, origin) -> None:
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
    assert (releases / build_name(new)).exists()
    status = json.loads((home / "deploy" / "status.json").read_text(encoding="utf-8"))
    assert status["result"] == "failed"
    assert new in refused_shas(home)
    assert _poll(home, releases, mirror).action == "refused"


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
    assert os.readlink(releases / "current") == build_name(new)
    assert running_build(releases) == "old"
    assert fake.synced == [releases / build_name(new)]
    cutover = next(argv for argv in fake.calls if argv[1].endswith("cutover.sh"))
    assert "--skip-restart" in cutover and "--skip-gate" in cutover


@pytest.mark.platforms("linux", "macos")
def test_worker_rejects_using_full_sha_when_live_is_a_short_prefix(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    home = tmp_path / "hermes"
    releases = home / "releases"
    build = "hermes-agent-" + base[:10] + "-live"
    _release(releases, build)
    os.symlink(build, releases / "current")
    _queue(home, base)
    fake = _Recorder(releases, home)
    outcome = run_once(Config(home=home, mirror=mirror, releases=releases), fake.hooks())
    assert outcome.result == "live", outcome


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


def test_audit_rollback_targets_keep_only_the_two_most_recent(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    audits = home / "upgrade-audits"
    entries = (
        ("b-old", "r1", 1.0),
        ("b-mid", "r2", 2.0),
        ("b-new", "r3", 3.0),
        ("b-newest", "r4", 4.0),
    )
    for build, previous, mtime in entries:
        path = audits / build
        path.mkdir(parents=True)
        manifest = path / "manifest.json"
        write_manifest(manifest, {"previous": previous})
        os.utime(manifest, (mtime, mtime))
    assert audit_rollback_targets(home) == {"r4", "r3"}


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

    os.symlink("r1", releases / "previous")
    removed = prune(releases, keep_set(home, releases, with_previous=True))
    assert removed == [".staging-r5.abc"]
    assert sorted(p.name for p in releases.iterdir() if not p.name.startswith(".")) == [
        "current", "previous", "r1", "r2", "r3", "r4",
    ]
    assert fresh.is_dir()
    assert prune(releases, keep_set(home, releases, with_previous=False)) == []
    assert prune(tmp_path / "empty", set()) == []
    assert prune(releases, keep_set(home, releases, with_previous=False), allow=False) == []


# ---------------------------------------------------------------- drift

_GITATTRS_EOL = "*.py text eol=lf\n*.ps1 text eol=crlf\n"
_DEPLOY_PS1 = "Write-Host 'deployed'\n"


def _live_release_matching_sha(work: Path, mirror: Path, live: Path, sha: str) -> None:
    from scripts.deploy.nemo.drift import GIT_SUBMODULE_MODE, tree_blobs

    for rel, (mode, _obj) in tree_blobs(mirror, sha).items():
        if mode == GIT_SUBMODULE_MODE:
            continue
        dest = live / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(subprocess.check_output(["git", "-C", str(work), "show", f"{sha}:{rel}"]))


@pytest.fixture
def ps1_drift_origin(origin):
    """Origin with ``.gitattributes`` eol rules and a tracked ``.ps1`` at HEAD."""
    work, mirror, _base = origin
    sha = _commit(work, {".gitattributes": _GITATTRS_EOL, "tools/deploy.ps1": _DEPLOY_PS1}, "ps1")
    _git(work, "push", "-q", "origin", "main")
    _git(mirror, "fetch", "-q", "origin", "main")
    return work, mirror, sha


@pytest.fixture
def ps1_drift_cfg(tmp_path: Path, ps1_drift_origin):
    work, mirror, sha = ps1_drift_origin
    home, releases = _live_home(tmp_path, sha)
    live = releases / "old"
    _live_release_matching_sha(work, mirror, live, sha)
    return Config(home=home, mirror=mirror, releases=releases), live


@pytest.mark.platforms("linux", "macos")
def test_drift_ps1_crlf_only_line_endings_are_clean(ps1_drift_cfg) -> None:
    cfg, live = ps1_drift_cfg
    ps1 = live / "tools/deploy.ps1"
    ps1.write_bytes(ps1.read_bytes().replace(b"\n", b"\r\n"))
    assert check_drift(cfg, unit_dirs=[], max_lag_s=0).clean


@pytest.mark.platforms("linux", "macos")
def test_drift_ps1_content_edit_is_drift(ps1_drift_cfg) -> None:
    cfg, live = ps1_drift_cfg
    ps1 = live / "tools/deploy.ps1"
    ps1.write_bytes(ps1.read_bytes().replace(b"\n", b"\r\n") + b"# patched\r\n")
    report = check_drift(cfg, unit_dirs=[], max_lag_s=0)
    assert report.modified == ["tools/deploy.ps1"]


@pytest.mark.platforms("linux", "macos")
def test_drift_lf_tracked_py_edit_is_drift(ps1_drift_cfg) -> None:
    cfg, live = ps1_drift_cfg
    (live / "agent/core.py").write_text("X = 'tampered'\n", encoding="utf-8")
    report = check_drift(cfg, unit_dirs=[], max_lag_s=0)
    assert report.modified == ["agent/core.py"]


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


def test_drift_accepts_release_dir_sha_when_manifest_is_missing(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    home = tmp_path / "hermes"
    releases = home / "releases"
    build = "hermes-agent-" + base[:10] + "-live"
    _release(releases, build)
    os.symlink(build, releases / "current")
    live = releases / build
    for rel in ("agent/core.py", "skills/demo/SKILL.md"):
        (live / rel).parent.mkdir(parents=True, exist_ok=True)
        (live / rel).write_bytes((work / rel).read_bytes())
    (live / "pyproject.toml").write_bytes((work / "pyproject.toml").read_bytes())
    cfg = Config(home=home, mirror=mirror, releases=releases)
    report = check_drift(cfg, unit_dirs=[], max_lag_s=0)
    assert report.error is None
    assert report.clean


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


def test_live_sha_infers_hermes_agent_release_names_and_matches_main_prefix() -> None:
    name = "hermes-agent-deadbeef01-extra"
    assert sha_from_release_name(name) == "deadbeef01"
    assert main_matches_live("deadbeef01" + "a" * 30, "deadbeef01")


def test_poll_treats_inferred_live_sha_as_current(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    home = tmp_path / "hermes"
    releases = home / "releases"
    build = "hermes-agent-" + base[:10] + "-manual"
    _release(releases, build)
    os.symlink(build, releases / "current")
    assert live_sha(home, build) == base[:10].lower()
    assert _poll(home, releases, mirror).action == "live"


def test_run_script_retains_child_output_for_failure_detail() -> None:
    code = run_script(["bash", "-c", "printf '%s\\n' 'EACCES: permission denied'; exit 1"], timeout=10)
    assert code == 1
    detail = script_failure_detail("build.sh failed")
    assert "permission denied" in detail.lower()
    assert detail.startswith("build.sh failed")


@pytest.mark.platforms("linux", "macos")
def test_worker_does_not_refuse_sha_when_build_hits_eacces(tmp_path: Path, origin) -> None:
    work, mirror, base = origin
    new = _commit(work, {"agent/core.py": "X = 10\n"}, "code")
    _git(work, "push", "-q", "origin", "main")
    home, releases = _live_home(tmp_path, base)
    _queue(home, new)
    recorder = _Recorder(releases, home)
    real_script = recorder.script

    def script(argv: list[str]) -> int:
        if argv[1].endswith("build.sh"):
            autodeploy._last_script_log = (
                "Error: EACCES: permission denied, unlink 'node_modules/.hermes-node-deps'"
            )
            return 1
        return real_script(argv)

    hooks = recorder.hooks()
    hooks = Hooks(script=script, sync=hooks.sync, disk_free=hooks.disk_free)
    outcome = run_once(Config(home=home, mirror=mirror, releases=releases), hooks)
    assert outcome.result == "failed"
    assert "permission denied" in outcome.detail.lower() or "eacces" in outcome.detail.lower()
    assert new not in refused_shas(home)


def test_worker_fails_fast_when_uv_is_missing(tmp_path: Path, origin, monkeypatch) -> None:
    work, mirror, base = origin
    new = _push(work, {"agent/core.py": "X = 9\n"})
    home, releases = _live_home(tmp_path, base)
    _queue(home, new)
    monkeypatch.setattr("scripts.deploy.nemo.preflight.shutil.which", lambda *_a, **_k: None)
    assert deploy_preflight() is not None
    outcome = run_once(Config(home=home, mirror=mirror, releases=releases), _Recorder(releases, home).hooks())
    assert outcome.result == "failed" and "uv" in outcome.detail.lower()
    assert new not in refused_shas(home)


def test_script_env_puts_uv_local_bin_on_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".local" / "bin").mkdir(parents=True)
    assert f"{tmp_path}/.local/bin" in _script_env()["PATH"].split(":")


def test_install_preserves_disabled_units_without_enable_flag(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_systemctl(scope: str, *args: str) -> int:
        calls.append((scope, *args))
        if len(args) >= 2 and args[0] == "is-enabled":
            return 1
        if len(args) >= 2 and args[0] == "is-active":
            return 3
        return 0

    monkeypatch.setattr(autodeploy_units, "_systemctl", fake_systemctl)
    autodeploy_units._restore_unit_states(
        "user",
        {autodeploy_units.POLL_TIMER: (False, False)},
    )
    assert ("user", "disable", autodeploy_units.POLL_TIMER) in calls
    assert not any(call[1] == "enable" and call[2] == "--now" for call in calls)


def test_units_run_from_current_and_poll_the_mirror_on_a_jittered_timer(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    mirror = tmp_path / "mirror.git"
    units = render(UnitOptions(home=home, releases=home / "releases", mirror=mirror))
    assert ".local/bin" in units["hermes-deploy-poll.service"]
    current = str(home / "releases" / "current")
    poller = units["hermes-deploy-poll.service"]
    assert f"{current}/.venv/bin/python -m scripts.deploy.nemo.poll" in poller
    assert f"--mirror {mirror}" in poller and "GIT_TERMINAL_PROMPT=0" in poller
    timer = units["hermes-deploy-poll.timer"]
    assert "OnUnitInactiveSec=60s" in timer and "RandomizedDelaySec=" in timer
    assert f"DirectoryNotEmpty={home / 'deploy' / 'queue'}" in units["hermes-deploy.path"]
    assert "User=" not in "".join(units.values())
    assert not any("listener" in name or "tailscale" in text for name, text in units.items())


def test_dry_run_lists_a_leftover_listener_and_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    from scripts.deploy.nemo import autodeploy_units

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    units_dir = autodeploy_units.unit_dir("user")
    units_dir.mkdir(parents=True)
    (units_dir / "hermes-deploy-listener.service").write_text("[Service]\n", encoding="utf-8")
    home = tmp_path / "hermes"
    code = autodeploy_units.main(["install", "--hermes-home", str(home), "--mirror", str(tmp_path / "m.git"),
                                  "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0
    assert "hermes-deploy-poll.timer" in out and "would disable and remove" in out
    assert sorted(p.name for p in units_dir.iterdir()) == ["hermes-deploy-listener.service"]


@pytest.mark.platforms("linux", "macos")
def test_new_shell_entry_points_parse() -> None:
    for name in ("install_autodeploy.sh", "cutover.sh"):
        subprocess.run(["bash", "-n", str(NEMO / name)], check=True, timeout=20)

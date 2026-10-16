"""Behaviour of the nemo deploy helpers.

Shell entry points are checked with bash -n, and with shellcheck when it is
installed. Nothing here writes to the real Hermes home.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from scripts.deploy.nemo.config_paths import rewrite_yaml_text, swap_prefix
from scripts.deploy.nemo.cutover_steps import apply_cutover
from scripts.deploy.nemo.freeze_diff import compare, constraint_text
from scripts.deploy.nemo.gate import inspect_db, poll_until_quiet
from scripts.deploy.nemo.health import HealthCheck, body_healthy, gateway_socket_healthy, poll_until_healthy
from scripts.deploy.nemo.health import evaluate
from scripts.deploy.nemo.health_targets import resolve_health_plan, socket_profile_homes
from scripts.deploy.nemo.layout import DEFAULT_DASHBOARD_HEALTH, DEFAULT_GATEWAY_HEALTH
from scripts.deploy.nemo.manifest import record_build_manifest
from scripts.deploy.nemo.layout import FRONTEND_MARKER_RELATIVE, pin_uv_cache
from scripts.deploy.nemo.postcheck import (
    HR_SYNC, REAPER, TYPHOON, Invocation, POLICIES, command_list, guard, plan_policy,
    resolve_script, run_postcheck, script_accepts_dry_run,
)
from scripts.deploy.nemo.preflight import changed_files, is_environment_failure, plan_for
from scripts.deploy.nemo.release_swap import swap_current
from scripts.deploy.nemo.rollback import apply_rollback
from scripts.deploy.nemo.source import SourceMissing, acquire_source, extract_tarball, probe_fetch
from scripts.deploy.nemo.units import rewrite_units, units_embedding
from scripts.deploy.nemo.verify_mcp import compile_plan, scripts_in_release
from scripts.deploy.nemo.verify_ws import static_problems

ROOT = Path(__file__).resolve().parents[3]
NEMO = ROOT / "scripts" / "deploy" / "nemo"
SHELLS = (NEMO / "common.sh", NEMO / "build.sh", NEMO / "cutover.sh", NEMO / "rollback.sh")
SHA = "abc1234"


def _tar(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _write_tar(path: Path, members: dict[str, bytes]) -> None:
    path.write_bytes(_tar(members))


def _completed(argv: list[str], code: int = 0, stdout: bytes = b"", stderr: bytes = b""):
    return subprocess.CompletedProcess(argv, code, stdout, stderr)


def test_missing_source_leaves_staging_empty(tmp_path: Path) -> None:
    dest = tmp_path / "stage"
    dest.mkdir()
    with pytest.raises(SourceMissing):
        acquire_source(
            sha=SHA, dest=dest, mirror=None, tarball=tmp_path / "missing.tar", timeout=1,
        )
    assert list(dest.iterdir()) == []


def test_fetch_timeout_falls_back_to_the_tarball(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    tarball = tmp_path / "src.tar"
    _write_tar(tarball, {"pkg/pyproject.toml": b"[project]\nname = 'x'\n"})

    def run(argv, timeout):
        if "fetch" in argv:
            raise subprocess.TimeoutExpired(argv, timeout)
        return _completed(argv, code=1, stderr=b"missing")

    dest = tmp_path / "stage"
    result = acquire_source(
        sha=SHA, dest=dest, mirror=mirror, tarball=tarball, timeout=1, run=run,
    )
    assert result.method == "tarball"
    assert (dest / "pyproject.toml").is_file()


def test_fetch_timeout_uses_a_commit_already_in_the_mirror(tmp_path: Path) -> None:
    payload = _tar({"pyproject.toml": b"[project]\nname = 'x'\n"})

    def run(argv, timeout):
        if "fetch" in argv:
            raise subprocess.TimeoutExpired(argv, timeout)
        if "archive" in argv:
            return _completed(argv, stdout=payload)
        raise AssertionError(argv)

    mirror = tmp_path / "mirror"
    mirror.mkdir()
    dest = tmp_path / "stage"
    result = acquire_source(
        sha=SHA, dest=dest, mirror=mirror, tarball=None, timeout=1, run=run,
    )
    assert result.method == "mirror-local"
    assert (dest / "pyproject.toml").read_text(encoding="utf-8").startswith("[project]")


def test_unsafe_tar_member_is_rejected(tmp_path: Path) -> None:
    tarball = tmp_path / "bad.tar"
    _write_tar(tarball, {"../evil": b"nope"})
    dest = tmp_path / "stage"
    dest.mkdir()
    with pytest.raises(SourceMissing):
        extract_tarball(tarball, dest)
    assert not (tmp_path / "evil").exists()
    assert list(dest.iterdir()) == []


def test_probe_reports_a_hang_without_writing_a_release(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror"
    mirror.mkdir()

    def run(argv, timeout):
        raise subprocess.TimeoutExpired(argv, timeout)

    result = probe_fetch(mirror, SHA, 1, run=run)
    assert result.status == "hang"
    assert result.exit_code == 75
    assert not (tmp_path / "releases").exists()
    assert not (tmp_path / "upgrade-audits").exists()


def test_probe_missing_mirror_is_an_error(tmp_path: Path) -> None:
    result = probe_fetch(tmp_path / "missing", SHA, 1)
    assert result.exit_code == 1


def test_nemo_default_health_urls_match_pd_neo_and_dashboard() -> None:
    assert DEFAULT_GATEWAY_HEALTH == "http://127.0.0.1:8644/health"
    assert DEFAULT_DASHBOARD_HEALTH == "http://127.0.0.1:8765/api/health"


def test_default_health_plan_checks_pdone_and_hermes_home_sockets(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    (home / "profiles" / "pdone").mkdir(parents=True)
    plan = resolve_health_plan(home)
    assert plan.socket_profiles == ("pdone", "default")
    sockets = socket_profile_homes(home, plan.socket_profiles)
    checked: list[Path] = []

    def fake_socket(profile_home: Path, timeout: float) -> HealthCheck:
        checked.append(profile_home.resolve())
        return HealthCheck(str(profile_home), True, "ok")

    monkeypatch.setattr("scripts.deploy.nemo.health.gateway_socket_healthy", fake_socket)
    evaluate(
        [], [], check_unit=lambda _n, _u: True, check_url=lambda url: HealthCheck(url, True, ""),
        socket_homes=sockets,
    )
    assert home.resolve() in checked
    assert (home / "profiles" / "pdone").resolve() in checked


def test_health_plan_reads_config_yaml_and_env(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    (home / "config.yaml").write_text(
        "deploy:\n  health:\n"
        '    gateway_url: "http://127.0.0.1:1/gw"\n'
        '    dashboard_url: "http://127.0.0.1:2/dash"\n'
        "    socket_profiles: [pdneo]\n",
        encoding="utf-8",
    )
    plan = resolve_health_plan(home)
    assert plan.gateway_url.endswith("/gw")
    assert plan.dashboard_url.endswith("/dash")
    assert plan.socket_profiles == ("pdneo",)
    monkeypatch.setenv("NEMO_DEPLOY_GATEWAY_HEALTH", "http://127.0.0.1:9/env")
    assert resolve_health_plan(home).gateway_url.endswith("/env")


def test_record_build_manifest_writes_sha_time_and_release_name(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    record_build_manifest(path, sha="a" * 40, release_name="hermes-agent-aaaaaaaaaa-x")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["sha"] == "a" * 40
    assert data["release_name"] == "hermes-agent-aaaaaaaaaa-x"
    assert "T" in data["build_time"] and data["build_time"].endswith("Z")


@pytest.mark.platforms("linux", "macos")
def test_build_sh_finds_uv_under_home_local_bin(tmp_path: Path, monkeypatch) -> None:
    uv = tmp_path / ".local" / "bin" / "uv"
    uv.parent.mkdir(parents=True)
    uv.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    uv.chmod(0o755)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    script = NEMO / "common.sh"
    done = subprocess.run(
        ["bash", "-c", f'source "{script}" && command -v uv'],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert done.returncode == 0
    assert str(uv) in done.stdout.strip()


def test_gateway_socket_healthy_reports_missing_socket(tmp_path: Path) -> None:
    check = gateway_socket_healthy(tmp_path / "profiles" / "pdone", timeout=0.5)
    assert check.ok is False


def test_body_healthy_accepts_gateway_and_dashboard_payloads() -> None:
    assert body_healthy(200, b"ok")
    assert body_healthy(200, b'{"status": "ok"}')
    assert body_healthy(200, b'{"ok": true}')
    assert body_healthy(500, b'{"status": "ok"}') is False
    assert body_healthy(200, b'{"ok": false}') is False


def test_health_poll_waits_until_the_unit_is_active() -> None:
    state = {"t": 0.0, "checks": 0}

    def check_unit(_name: str, _user: bool) -> bool:
        state["checks"] += 1
        return state["checks"] >= 2

    def sleep(seconds: float) -> None:
        state["t"] += seconds

    ok, checks = poll_until_healthy(
        [("hermes.service", False)], [], timeout_s=30, interval_s=2,
        check_unit=check_unit, check_url=lambda url: HealthCheck(url, False, ""),
        clock_fn=lambda: state["t"], sleep_fn=sleep,
    )
    assert ok is True
    assert checks[0].ok is True
    assert state["t"] == 2


def test_health_poll_times_out() -> None:
    state = {"t": 0.0}

    def sleep(seconds: float) -> None:
        state["t"] += seconds

    ok, checks = poll_until_healthy(
        [("hermes.service", False)], ["http://127.0.0.1/health"],
        timeout_s=5, interval_s=2,
        check_unit=lambda _name, _user: False,
        check_url=lambda url: HealthCheck(url, False, "down"),
        clock_fn=lambda: state["t"], sleep_fn=sleep,
    )
    assert ok is False
    assert state["t"] >= 5
    assert all(item.ok is False for item in checks)


def _write_db(path: Path, *, message_at: float | None, leases=(), goals=(), locks=()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE messages (timestamp REAL)")
    if message_at is not None:
        conn.execute("INSERT INTO messages (timestamp) VALUES (?)", (message_at,))
    conn.execute("CREATE TABLE session_turn_leases (expires_at REAL)")
    for expiry in leases:
        conn.execute("INSERT INTO session_turn_leases (expires_at) VALUES (?)", (expiry,))
    conn.execute("CREATE TABLE compression_locks (expires_at REAL)")
    for expiry in locks:
        conn.execute("INSERT INTO compression_locks (expires_at) VALUES (?)", (expiry,))
    conn.execute("CREATE TABLE state_meta (key TEXT, value TEXT)")
    for key, value in goals:
        conn.execute("INSERT INTO state_meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def test_gate_passes_when_the_profile_is_quiet(tmp_path: Path) -> None:
    now = 1_000_000.0
    db = tmp_path / "state.db"
    _write_db(db, message_at=now - 120, goals=[("goal:abc", json.dumps({"status": "done"}))])
    snap = inspect_db("pdone", db, now)
    assert snap.quiet(now, 90) is True
    assert snap.leases == 0
    assert snap.live_goals == 0


def test_gate_blocks_on_a_lease_a_fresh_message_or_a_live_goal(tmp_path: Path) -> None:
    now = 1_000_000.0
    fresh = tmp_path / "fresh.db"
    _write_db(fresh, message_at=now - 10)
    assert inspect_db("pdone", fresh, now).quiet(now, 90) is False

    leased = tmp_path / "leased.db"
    _write_db(leased, message_at=now - 120, leases=[None])
    assert inspect_db("pdone", leased, now).leases == 1

    locked = tmp_path / "locked.db"
    _write_db(locked, message_at=now - 120, locks=[now + 30])
    assert inspect_db("pdone", locked, now).leases == 1

    live = tmp_path / "live.db"
    _write_db(live, message_at=now - 120, goals=[("goal:abc", json.dumps({"status": "active"}))])
    assert inspect_db("pdone", live, now).live_goals == 1

    broken = tmp_path / "broken.db"
    _write_db(broken, message_at=now - 120, goals=[("goal:abc", "not-json")])
    assert inspect_db("pdone", broken, now).live_goals == 1
    assert inspect_db("pdone", tmp_path / "missing.db", now).quiet(now, 90) is False


def test_gate_counts_every_row_when_expiry_is_absent(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE messages (timestamp REAL)")
    conn.execute("CREATE TABLE session_turn_leases (id INTEGER)")
    conn.execute("INSERT INTO session_turn_leases (id) VALUES (1)")
    conn.execute("CREATE TABLE state_meta (key TEXT, value TEXT)")
    conn.commit()
    conn.close()
    assert inspect_db("pdone", db, 10).leases == 1


def test_gate_poll_waits_for_the_quiet_window(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    db = home / "profiles" / "pdone" / "state.db"
    state = {"now": 1_000.0, "mono": 0.0}
    _write_db(db, message_at=1_000.0)

    def now() -> float:
        return state["now"]

    def mono() -> float:
        return state["mono"]

    def sleep(seconds: float) -> None:
        state["now"] += seconds
        state["mono"] += seconds

    ok, snaps = poll_until_quiet(
        home, ("pdone",), quiet_s=90, poll_s=30, timeout_s=600,
        now_fn=now, sleep_fn=sleep, clock_fn=mono,
    )
    assert ok is True
    assert snaps[0].profile == "pdone"
    assert state["now"] - 1_000.0 >= 90


def test_plan_follows_the_diff_and_fails_open() -> None:
    mcp = plan_for(["tools/mcp/server.py"], full=False)
    assert mcp.verifies == ("verify_mcp",)
    assert mcp.tests == ()

    web = plan_for(["hermes_cli/main_tui_launch.py"], full=False)
    assert web.verifies == ("verify_ws",)
    assert "tests/hermes_cli/test_frontend_preinstall.py" in web.tests

    quiet = plan_for(["agent/turn_loop.py"], full=False)
    assert quiet.verifies == ()
    assert quiet.tests == ()

    full = plan_for(["README.md"], full=True)
    assert full.reason == "full"
    assert full.verifies == ("verify_mcp", "verify_ws")

    opened = plan_for(None, full=False)
    assert opened.reason == "diff unavailable"
    assert opened.verifies == full.verifies


def test_changed_files_timeout_is_an_unreadable_diff(tmp_path: Path) -> None:
    def run(argv, timeout):
        raise subprocess.TimeoutExpired(argv, timeout)

    assert changed_files(tmp_path, "a" * 7, "b" * 7, run=run) is None


def test_freeze_diff_fails_when_a_nemo_pin_disappears() -> None:
    old = "requests==2.33.0\npyyaml==6.0.3\n-e /opt/hermes\n"
    new = "requests==2.33.0\n"
    report, missing = compare(old, new)
    assert missing == ["pyyaml"]
    assert "- pyyaml==6.0.3" in report
    assert "-e" not in constraint_text(old)


def test_swap_prefix_does_not_eat_a_longer_path() -> None:
    assert swap_prefix("/old/rel", "/old/rel", "/new/rel") == "/new/rel"
    assert swap_prefix("/old/rel/bin", "/old/rel", "/new/rel") == "/new/rel/bin"
    assert swap_prefix("/old/rel2", "/old/rel", "/new/rel") == "/old/rel2"


def test_config_rewrite_keeps_comments() -> None:
    text = "# keep me\nmodel: x  # inline\nroot: /old/rel\nnested:\n  bin: /old/rel/bin/python\nother: /elsewhere\n"
    updated, count = rewrite_yaml_text(text, "/old/rel", "/new/rel")
    assert count == 2
    assert "# keep me" in updated
    assert "# inline" in updated
    assert "/new/rel/bin/python" in updated
    assert "/old/rel" not in updated.replace("/old/rel2", "")
    assert "/elsewhere" in updated


def test_cutover_rewrites_units_and_rollback_restores_them(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    releases = home / "releases"
    old = releases / "old"
    new = releases / "new"
    old.mkdir(parents=True)
    new.mkdir()
    os.symlink("old", releases / "current")
    unit_dir = tmp_path / "units"
    unit_dir.mkdir()
    unit = unit_dir / "hermes.service"
    old_path = str(old.resolve())
    new_path = str(new.resolve())
    unit.write_text(f"ExecStart={old_path}/.venv/bin/python\n", encoding="utf-8")
    config = home / "config.yaml"
    config.write_text(f"# keep\nroot: {old_path}\n", encoding="utf-8")
    audit = home / "upgrade-audits" / "new"
    result = apply_cutover(
        releases=releases, build="new", unit_dirs=[unit_dir], configs=[config], audit=audit,
    )
    assert os.readlink(releases / "current") == "new"
    assert new_path in unit.read_text(encoding="utf-8")
    assert "# keep" in config.read_text(encoding="utf-8")
    assert new_path in config.read_text(encoding="utf-8")
    restored = apply_rollback({
        "units": result["units"],
        "configs": result["configs"],
        "previous": result["previous"],
        "releases": result["releases"],
    })
    assert os.readlink(releases / "current") == "old"
    assert old_path in unit.read_text(encoding="utf-8")
    assert old_path in config.read_text(encoding="utf-8")
    assert unit in [Path(path) for path in restored["units"]] or str(unit) in restored["units"]


def test_swap_refuses_a_missing_release(tmp_path: Path) -> None:
    releases = tmp_path / "releases"
    releases.mkdir()
    with pytest.raises(FileNotFoundError):
        swap_current(releases, "missing")


def test_unit_rewrite_round_trip(tmp_path: Path) -> None:
    unit_dir = tmp_path / "systemd"
    unit_dir.mkdir()
    unit = unit_dir / "gateway.service"
    unit.write_text("WorkingDirectory=/opt/old\n", encoding="utf-8")
    found = units_embedding([unit_dir], "/opt/old")
    changes = rewrite_units(found, "/opt/old", "/opt/new", tmp_path / "audit")
    assert "/opt/new" in unit.read_text(encoding="utf-8")
    assert changes[0].backup
    assert Path(changes[0].backup).read_text(encoding="utf-8") == "WorkingDirectory=/opt/old\n"


def test_pin_uv_cache_exports_the_given_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("UV_CACHE_DIR", raising=False)
    path = pin_uv_cache(tmp_path / "uv-cache")
    assert path == (tmp_path / "uv-cache").resolve()
    assert os.environ["UV_CACHE_DIR"] == str(path)
    assert path.is_dir()


def test_dry_run_flag_must_be_an_argparse_declaration() -> None:
    assert script_accepts_dry_run("import argparse\np.add_argument('--dry-run')\n") is True
    assert script_accepts_dry_run("help = '--dry-run is mentioned'\n") is False


def test_hr_sync_and_reaper_are_not_executed_live(tmp_path: Path) -> None:
    script = tmp_path / "hr.py"
    script.write_text("import requests\nrequests.post('https://appsheet.example')\n", encoding="utf-8")
    hr = next(policy for policy in POLICIES if policy.job_id == HR_SYNC)
    planned = plan_policy(hr, script, script.read_text(encoding="utf-8"), sys.executable)
    assert planned.action == "compile"
    commands = command_list(planned, hr, sys.executable)
    assert any("py_compile" in argv for argv in commands)
    assert all(argv[-1:] != [str(script)] for argv in commands)
    with pytest.raises(RuntimeError, match="AppSheet"):
        guard(Invocation(HR_SYNC, "hr-sync", "exec", (sys.executable, str(script)), "forged"))

    reaper = next(policy for policy in POLICIES if policy.job_id == REAPER)
    bare = plan_policy(reaper, script, "print('reap')\n", sys.executable)
    assert bare.action == "compile"
    with pytest.raises(RuntimeError, match="reaper"):
        guard(Invocation(REAPER, "reaper", "exec", (sys.executable, str(script)), "forged"))

    dry = "import argparse\nap = argparse.ArgumentParser()\nap.add_argument('--dry-run')\n"
    safe = plan_policy(hr, script, dry, sys.executable)
    assert safe.argv[-1] == "--dry-run"
    command_list(safe, hr, sys.executable)


def test_postcheck_runs_typhoon_with_the_cron_tls_mount(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    profile = home / "profiles" / "pdone"
    scripts = profile / "scripts"
    scripts.mkdir(parents=True)
    jobs = {
        TYPHOON: ("typhoon_check.py", "url = 'https://www.cwa.gov.tw/'\n"),
        "870dd7349151": ("digest.py", "import yaml\n"),
        REAPER: ("reaper.py", "print('reap')\n"),
        HR_SYNC: ("hr_sync.py", "import requests\n"),
    }
    payload = []
    for job_id, (name, source) in jobs.items():
        (scripts / name).write_text(source, encoding="utf-8")
        payload.append({"id": job_id, "script": name})
    cron = profile / "cron" / "jobs.json"
    cron.parent.mkdir()
    cron.write_text(json.dumps({"jobs": payload}), encoding="utf-8")
    seen: list[tuple[list[str], dict[str, str]]] = []

    def run(argv, env):
        seen.append((list(argv), dict(env)))
        return 0

    results = run_postcheck(home, ("pdone",), sys.executable, run=run)
    assert all(item["ok"] for item in results)
    hr = next(item for item in results if item["job_id"] == HR_SYNC)
    assert hr["action"] == "compile"
    assert any("py_compile" in argv for argv in hr["argv"])
    typhoon = [item for item in seen if any("typhoon_check.py" in part for part in item[0])]
    assert typhoon
    assert typhoon[0][1]["_HERMES_CRON_CWA_TLS"] == "1"
    assert "cwa_site" in typhoon[0][1]["PYTHONPATH"]
    assert resolve_script(profile, "../outside.py") is None


def test_mcp_scripts_outside_the_release_are_ignored(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    release = home / "releases" / "new"
    inside = release / "tools" / "srv.py"
    inside.parent.mkdir(parents=True)
    inside.write_text("print(1)\n", encoding="utf-8")
    outside = tmp_path / "other.py"
    outside.write_text("print(1)\n", encoding="utf-8")
    config = {
        "mcp_servers": {"demo": {"args": [str(inside), str(outside)]}},
    }
    (home / "config.yaml").write_text(json.dumps(config), encoding="utf-8")
    found = scripts_in_release(home, release, profiles=())
    assert found == [inside.resolve()]
    assert compile_plan(sys.executable, found)[0][2] == "import requests, yaml"


def test_static_ws_problems_name_a_missing_preinstall(tmp_path: Path) -> None:
    problems = static_problems(tmp_path)
    assert "missing node_modules" in problems
    assert "missing frontend preinstall marker" in problems
    (tmp_path / "hermes_cli" / "web_dist").mkdir(parents=True)
    (tmp_path / "hermes_cli" / "web_dist" / "index.html").write_text("ok", encoding="utf-8")
    (tmp_path / "ui-tui" / "dist").mkdir(parents=True)
    (tmp_path / "ui-tui" / "dist" / "entry.js").write_text("ok", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    marker = tmp_path / FRONTEND_MARKER_RELATIVE
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("preinstalled\n", encoding="utf-8")
    assert static_problems(tmp_path) == []


def _bash() -> str:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required")
    return bash


_UV_BIN_DIR: str | None = None
_UV_BIN_DIR_RESOLVED = False


def _resolve_uv_bin_dir() -> str | None:
    global _UV_BIN_DIR, _UV_BIN_DIR_RESOLVED
    if _UV_BIN_DIR_RESOLVED:
        return _UV_BIN_DIR
    pm_home = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
    if "hermes-pytest" in pm_home or "/pytest" in pm_home:
        pm_home = str(Path.home() / ".hermes")
    done = subprocess.run(
        [sys.executable, "-c",
         "from pm.install import uv_launcher\n"
         "p = uv_launcher('uv')\n"
         "print(p.parent if p else '')"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
        env={**os.environ, "HERMES_HOME": pm_home},
    )
    parent = (done.stdout or "").strip()
    _UV_BIN_DIR = parent or None
    _UV_BIN_DIR_RESOLVED = True
    return _UV_BIN_DIR


def _deploy_script_path() -> str:
    entries = [str(Path.home() / ".local" / "bin")]
    uv_dir = _resolve_uv_bin_dir()
    if uv_dir:
        entries.append(uv_dir)
    return ":".join(entries)


def _run_build(tmp_path: Path, *extra: str, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "hermes"
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env["PATH"] = f"{_deploy_script_path()}:{env.get('PATH', '')}"
    env.setdefault("NEMO_PYTHON", sys.executable)
    env["TMPDIR"] = str(tmp_path / "tmp")
    (tmp_path / "tmp").mkdir(exist_ok=True)
    command = [
        _bash(), str(NEMO / "build.sh"),
        "--hermes-home", str(home),
        "--sha", SHA,
        "--build", "build-a",
        "--uv-cache", str(tmp_path / "uv"),
        *extra,
    ]
    return subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=timeout)


def _chmod_read_only(path: Path) -> None:
    for root, dirs, files in os.walk(path):
        root_path = Path(root)
        for name in files:
            os.chmod(root_path / name, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        for name in dirs:
            os.chmod(
                root_path / name,
                stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,
            )
    os.chmod(path, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


def test_is_environment_failure_recognizes_build_host_errors() -> None:
    assert is_environment_failure("uv is required on PATH")
    assert is_environment_failure("build.sh failed\nError: EACCES, unlink 'node_modules/.hermes-node-deps'")
    assert is_environment_failure("build.sh failed\nnode is required to preinstall dashboard dependencies")
    assert not is_environment_failure("build.sh failed\nimport hermes_cli failed")


@pytest.mark.platforms("linux", "macos")
def test_shell_scripts_parse() -> None:
    bash = _bash()
    for path in SHELLS:
        subprocess.run([bash, "-n", str(path)], check=True, timeout=20)


@pytest.mark.platforms("linux", "macos")
def test_shellcheck_when_installed() -> None:
    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        pytest.skip("shellcheck is not installed")
    subprocess.run(
        [shellcheck, "-S", "warning", "-x", "--source-path=SCRIPTDIR",
         *[str(path) for path in SHELLS]],
        check=True, timeout=60,
    )


@pytest.mark.platforms("linux", "macos")
def test_build_missing_tarball_does_not_leave_an_empty_release(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    release = home / "releases" / "build-a"
    release.mkdir(parents=True)
    proc = _run_build(tmp_path, "--tarball", str(tmp_path / "missing.tar"))
    assert proc.returncode != 0
    assert not release.exists()
    assert "source missing" in proc.stderr


@pytest.mark.platforms("linux", "macos")
def test_build_refuses_a_non_empty_release(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    release = home / "releases" / "build-a"
    release.mkdir(parents=True)
    (release / "keep.txt").write_text("safe", encoding="utf-8")
    proc = _run_build(tmp_path, "--tarball", str(tmp_path / "missing.tar"))
    assert proc.returncode != 0
    assert (release / "keep.txt").read_text(encoding="utf-8") == "safe"


@pytest.mark.platforms("linux", "macos")
def test_build_stop_after_source_extracts_without_publishing(tmp_path: Path) -> None:
    tarball = tmp_path / "src.tar"
    _write_tar(tarball, {"pkg/pyproject.toml": b"[project]\nname = 'x'\n"})
    staging = tmp_path / "staging"
    proc = _run_build(
        tmp_path, "--tarball", str(tarball), "--staging", str(staging), "--stop-after", "source",
    )
    assert proc.returncode == 0, proc.stderr
    assert "source tarball" in proc.stdout
    assert (staging / "pyproject.toml").is_file()
    assert not (tmp_path / "hermes" / "releases" / "build-a").exists()


@pytest.mark.platforms("linux", "macos")
def test_build_rejects_an_unsafe_tarball(tmp_path: Path) -> None:
    tarball = tmp_path / "bad.tar"
    _write_tar(tarball, {"../evil": b"nope"})
    proc = _run_build(tmp_path, "--tarball", str(tarball), "--stop-after", "source")
    assert proc.returncode != 0
    assert not (tmp_path / "hermes" / "releases" / "build-a").exists()
    assert list(tmp_path.rglob("evil")) == []


@pytest.mark.platforms("linux", "macos")
def test_build_reuses_read_only_node_modules_from_previous_release(tmp_path: Path) -> None:
    if shutil.which("node") is None:
        pytest.skip("node is required on PATH")
    if _resolve_uv_bin_dir() is None:
        pytest.skip("uv is required (PM install store not available in this runner)")
    tarball = tmp_path / "src.tar"
    subprocess.run(
        ["git", "archive", "--format=tar", "-o", str(tarball), "HEAD"],
        cwd=ROOT, check=True, timeout=180,
    )
    home = tmp_path / "hermes"
    releases = home / "releases"
    previous = releases / "old"
    previous.mkdir(parents=True)
    shutil.copy2(ROOT / "package-lock.json", previous / "package-lock.json")
    nm = previous / "node_modules"
    nm.mkdir()
    (nm / ".hermes-node-deps").write_text("stale-receipt\n", encoding="utf-8")
    os.symlink("old", releases / "current")
    _chmod_read_only(previous)

    proc = _run_build(
        tmp_path,
        "--tarball", str(tarball),
        "--stop-after", "frontend",
        timeout=900,
    )
    combined = proc.stdout + proc.stderr
    assert "node-deps" in combined
    assert "EACCES" not in combined
    assert "permission denied" not in combined.lower() or "hermes-node-deps" not in combined.lower()
    if proc.returncode != 0:
        if any(marker in combined.lower() for marker in ("web.mjs", "tui.mjs", "vite", "rolldown")):
            pytest.skip("frontend compile is not available in this runner")
        assert proc.returncode == 0, combined


def test_probe_cli_missing_mirror_exits_nonzero(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.deploy.nemo.probe",
         "--mirror", str(tmp_path / "missing"), "--sha", SHA, "--timeout", "1"],
        cwd=ROOT, capture_output=True, text=True, timeout=20,
    )
    assert proc.returncode == 1
    assert "error" in proc.stdout

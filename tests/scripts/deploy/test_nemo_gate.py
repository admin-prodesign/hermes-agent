"""Quiet-window gate: profile resolution, missing DBs, and stale 0-turn goals.

Nothing here writes to the real Hermes home. Paths are temp placeholders.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from argparse import Namespace
from pathlib import Path

import pytest

from scripts.deploy.nemo.cli import cmd_gate
from scripts.deploy.nemo.gate import MissingProfileDatabase, inspect_db, poll_until_quiet, profile_db
from scripts.deploy.nemo.layout import DEFAULT_PROFILES, DEFAULT_STALE_GOAL_S, profile_home

DAY = 24 * 3600.0
NOW = 1_000_000.0


def _write_db(path: Path, *, message_at: float | None = NOW - 120, goals=()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE messages (timestamp REAL)")
    if message_at is not None:
        conn.execute("INSERT INTO messages (timestamp) VALUES (?)", (message_at,))
    conn.execute("CREATE TABLE session_turn_leases (expires_at REAL)")
    conn.execute("CREATE TABLE compression_locks (expires_at REAL)")
    conn.execute("CREATE TABLE state_meta (key TEXT, value TEXT)")
    for key, value in goals:
        conn.execute("INSERT INTO state_meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def _goal(*, status="active", turns_used=0, created_at=NOW - 30 * DAY, last_turn_at=0.0) -> str:
    return json.dumps({
        "status": status,
        "turns_used": turns_used,
        "created_at": created_at,
        "last_turn_at": last_turn_at,
    })


def test_profile_home_default_and_empty_are_top_level(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    assert profile_home(home, "default") == home
    assert profile_home(home, "") == home
    assert profile_db(home, "default") == home / "state.db"


def test_profile_home_pdneo_alias_is_top_level(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    assert profile_home(home, "pdneo") == home
    assert profile_db(home, "pdneo") == home / "state.db"
    assert profile_db(home, "pdneo") != home / "profiles" / "pdneo" / "state.db"


def test_profile_home_named_profile_stays_under_profiles(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    assert profile_home(home, "pdone") == home / "profiles" / "pdone"
    assert profile_db(home, "pdone") == home / "profiles" / "pdone" / "state.db"


def test_default_profiles_resolve_pd_neo_to_the_top_level_home(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    assert DEFAULT_PROFILES[0] == "pdone"
    assert "default" in DEFAULT_PROFILES
    neo = DEFAULT_PROFILES[1]
    assert profile_home(home, neo) == home


def test_gate_reads_top_level_db_for_default_and_pdneo_alias(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    _write_db(home / "state.db")
    _write_db(home / "profiles" / "pdone" / "state.db")
    for name in ("default", "pdneo"):
        ok, snaps = poll_until_quiet(
            home, ("pdone", name), quiet_s=90, poll_s=1, timeout_s=1,
            now_fn=lambda: NOW, sleep_fn=lambda _s: None, clock_fn=lambda: 0.0,
        )
        assert ok is True
        assert snaps[1].profile == name
        assert snaps[1].db == home / "state.db"
        assert snaps[1].missing is False


def test_missing_db_fails_fast_with_a_clear_message(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    slept: list[float] = []
    with pytest.raises(MissingProfileDatabase) as raised:
        poll_until_quiet(
            home, ("pdone",), quiet_s=90, poll_s=30, timeout_s=600,
            now_fn=lambda: NOW, sleep_fn=slept.append, clock_fn=lambda: 0.0,
        )
    assert slept == []
    message = str(raised.value)
    db = home / "profiles" / "pdone" / "state.db"
    assert "does not exist" in message
    assert "pdone" in message
    assert str(db) in message


def test_cmd_gate_missing_db_is_a_loud_failure(tmp_path: Path, capsys) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    code = cmd_gate(Namespace(
        hermes_home=str(home), profiles=["pdone"], quiet=90.0, poll=1.0,
        timeout=600.0, stale_goal_s=DEFAULT_STALE_GOAL_S,
    ))
    assert code == 1
    err = capsys.readouterr().err
    assert "does not exist" in err
    assert "pdone" in err
    assert "state.db" in err


def test_stale_zero_turn_active_goal_is_ignored(tmp_path: Path, caplog) -> None:
    db = tmp_path / "state.db"
    _write_db(db, goals=[("goal:stale-zero", _goal(created_at=NOW - 30 * DAY))])
    caplog.set_level(logging.INFO, logger="scripts.deploy.nemo.gate")
    snap = inspect_db("pdone", db, NOW)
    assert snap.live_goals == 0
    assert snap.quiet(NOW, 90) is True
    assert "goal:stale-zero" in caplog.text


def test_recent_zero_turn_active_goal_still_blocks(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _write_db(db, goals=[("goal:recent-zero", _goal(created_at=NOW - DAY))])
    snap = inspect_db("pdone", db, NOW)
    assert snap.live_goals == 1
    assert snap.quiet(NOW, 90) is False


def test_turned_active_goal_still_blocks_even_when_old(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _write_db(db, goals=[("goal:turned", _goal(turns_used=1, created_at=NOW - 30 * DAY))])
    snap = inspect_db("pdone", db, NOW)
    assert snap.live_goals == 1
    assert snap.quiet(NOW, 90) is False


def test_stale_zero_turn_with_recent_last_turn_still_blocks(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _write_db(db, goals=[("goal:updated", _goal(
        created_at=NOW - 30 * DAY, last_turn_at=NOW - DAY,
    ))])
    snap = inspect_db("pdone", db, NOW)
    assert snap.live_goals == 1


def test_stale_goal_threshold_is_configurable(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    created = NOW - 3 * DAY
    _write_db(db, goals=[("goal:three-days", _goal(created_at=created))])
    assert inspect_db("pdone", db, NOW).live_goals == 1
    assert inspect_db("pdone", db, NOW, stale_goal_s=2 * DAY).live_goals == 0
    assert inspect_db("pdone", db, NOW, stale_goal_s=DEFAULT_STALE_GOAL_S).live_goals == 1


def test_poll_treats_stale_zero_turn_goals_as_quiet(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    _write_db(
        home / "profiles" / "pdone" / "state.db",
        goals=[("goal:stale-zero", _goal(created_at=NOW - 30 * DAY))],
    )
    ok, snaps = poll_until_quiet(
        home, ("pdone",), quiet_s=90, poll_s=1, timeout_s=1,
        now_fn=lambda: NOW, sleep_fn=lambda _s: None, clock_fn=lambda: 0.0,
    )
    assert ok is True
    assert snaps[0].live_goals == 0

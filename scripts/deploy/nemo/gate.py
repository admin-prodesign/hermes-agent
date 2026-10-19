"""Quiet-window gate. pdone, then the top-level default profile (PD Neo).

A profile is quiet when it has no leases, newest message >= 90s, and no live
goal. An active goal whose last activity is older than ``stale_goal_s`` is
ignored, unless its session holds a live lease. Last activity is
``last_turn_at`` (written with every ``turns_used`` increment) or
``updated_at``; ``created_at`` stands in only for a goal that never took a
turn. A goal with turns but no last-activity stamp still blocks. The gate
does not write goal state. A missing ``state.db`` for a configured profile is
a configuration error and fails immediately.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from scripts.deploy.nemo.layout import (
    DEFAULT_POLL_S,
    DEFAULT_PROFILES,
    DEFAULT_QUIET_S,
    DEFAULT_STALE_GOAL_S,
    profile_home,
)

LEASE_TABLES = {"session_turn_leases": "conversation_id", "compression_locks": "session_id"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProfileSnapshot:
    profile: str
    db: Path
    missing: bool
    leases: int
    newest_message_at: float | None
    live_goals: int

    def quiet(self, now: float, quiet_s: float) -> bool:
        if self.missing or self.leases > 0 or self.live_goals > 0:
            return False
        if self.newest_message_at is None:
            return True
        return (now - self.newest_message_at) >= quiet_s


class MissingProfileDatabase(RuntimeError):
    """A configured profile's state.db is absent. Do not wait it out."""

    def __init__(self, snapshots: list[ProfileSnapshot]):
        self.snapshots = tuple(snapshots)
        details = ", ".join(f"{item.profile} ({item.db})" for item in snapshots)
        super().__init__(f"gate: configured profile state database does not exist: {details}")


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {str(row[0]) for row in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _live_lease_keys(conn: sqlite3.Connection, tables: set[str], now: float) -> list[str | None]:
    """One entry per live lease row: its session key, or None when the table has no key column."""
    keys: list[str | None] = []
    for table, key_column in LEASE_TABLES.items():
        if table not in tables:
            continue
        columns = _columns(conn, table)
        sql = f"SELECT {key_column if key_column in columns else 'NULL'} FROM {table}"
        if "expires_at" in columns:
            rows = conn.execute(sql + " WHERE expires_at IS NULL OR expires_at > ?", (now,))
        else:
            rows = conn.execute(sql)
        keys.extend(None if row[0] is None else str(row[0]) for row in rows)
    return keys


def _newest_message(conn: sqlite3.Connection, tables: set[str]) -> float | None:
    if "messages" not in tables or "timestamp" not in _columns(conn, "messages"):
        return None
    row = conn.execute("SELECT MAX(timestamp) FROM messages").fetchone()
    if row is None or row[0] is None:
        return None
    return float(row[0])


def _as_float(raw: object) -> float | None:
    if raw in (None, ""):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _as_int(raw: object, default: int = 0) -> int | None:
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _goal_last_activity(data: dict) -> float | None:
    """Newest known activity stamp, or None when unknown.

    ``created_at`` alone only describes a goal that never took a turn; a goal with
    turns needs ``last_turn_at`` or ``updated_at``, otherwise its activity is unknown.
    """
    stamps = {key: _as_float(data.get(key)) for key in ("last_turn_at", "updated_at", "created_at")}
    if _as_int(data.get("turns_used"), 0) != 0 and stamps["last_turn_at"] is None and stamps["updated_at"] is None:
        return None
    known = [stamp for stamp in stamps.values() if stamp is not None]
    return max(known) if known else None


def _idle_age(data: dict, now: float, stale_s: float) -> float | None:
    """Seconds since last activity when that is at least ``stale_s``; None when the goal may be busy."""
    activity = _goal_last_activity(data)
    if activity is None or (now - activity) < stale_s:
        return None
    return now - activity


def _live_goals(
    conn: sqlite3.Connection, tables: set[str], now: float, stale_s: float, *,
    profile: str, leased: set[str],
) -> int:
    if "state_meta" not in tables:
        return 0
    rows = conn.execute("SELECT key, value FROM state_meta WHERE key LIKE 'goal:%'")
    live = 0
    for key, raw in rows:
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            live += 1  # unreadable goal state blocks cutover
            continue
        if not isinstance(data, dict) or data.get("status") != "active":
            continue
        if str(key).removeprefix("goal:") in leased:
            live += 1
            continue
        age = _idle_age(data, now, stale_s)
        if age is None:
            live += 1
            continue
        logger.info(
            "gate: ignoring idle goal %s on profile %s (last activity %.0fs / %.1fd ago)",
            key, profile, age, age / 86400,
        )
    return live


def inspect_db(
    profile: str, db_path: Path, now: float, *, stale_goal_s: float = DEFAULT_STALE_GOAL_S,
) -> ProfileSnapshot:
    """Read-only snapshot. A missing database is not quiet."""
    if not db_path.is_file():
        return ProfileSnapshot(profile, db_path, True, 0, None, 0)
    uri = f"file:{db_path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        conn.execute("PRAGMA query_only = ON")
        tables = _table_names(conn)
        leases = _live_lease_keys(conn, tables, now)
        return ProfileSnapshot(
            profile, db_path, False,
            len(leases),
            _newest_message(conn, tables),
            _live_goals(
                conn, tables, now, stale_goal_s, profile=profile,
                leased={key for key in leases if key},
            ),
        )
    finally:
        conn.close()


def profile_db(home: Path, name: str) -> Path:
    return profile_home(home, name) / "state.db"


def all_quiet(snapshots: list[ProfileSnapshot], now: float, quiet_s: float) -> bool:
    return bool(snapshots) and all(item.quiet(now, quiet_s) for item in snapshots)


def poll_until_quiet(
    home: Path, profiles: tuple[str, ...] = DEFAULT_PROFILES, *,
    quiet_s: float = DEFAULT_QUIET_S, poll_s: float = DEFAULT_POLL_S, timeout_s: float = 600.0,
    stale_goal_s: float = DEFAULT_STALE_GOAL_S,
    now_fn=time.time, sleep_fn=time.sleep, clock_fn=time.monotonic,
) -> tuple[bool, list[ProfileSnapshot]]:
    """Poll every ``poll_s`` until every profile is quiet or ``timeout_s`` elapses.

    A missing ``state.db`` for a configured profile raises ``MissingProfileDatabase``
    on the first inspect instead of waiting out the timeout.
    """
    started = clock_fn()
    latest: list[ProfileSnapshot] = []
    while True:
        now = float(now_fn())
        latest = [
            inspect_db(name, profile_db(home, name), now, stale_goal_s=stale_goal_s)
            for name in profiles
        ]
        missing = [item for item in latest if item.missing]
        if missing:
            raise MissingProfileDatabase(missing)
        if all_quiet(latest, now, quiet_s):
            return True, latest
        if clock_fn() - started >= timeout_s:
            return False, latest
        sleep_fn(poll_s)

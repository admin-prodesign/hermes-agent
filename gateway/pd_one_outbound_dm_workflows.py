"""PD One outbound DM workflow registry and conservative routing helpers.

This module intentionally keeps routing deterministic and conservative: open
workflow targets are candidates, not automatic context.  Full workflow context is
only returned when an inbound DM is linked by tracker code or platform thread
metadata.  Ambiguous or merely probable matches produce a disambiguation decision
instead of injecting task details into an unrelated DM.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

TRACKER_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,12}(?:-[A-Z0-9]{1,24}){1,8}\b")
OPEN_TARGET_STATUSES = {
    "awaiting_reply",
    "initial_dm_sent",
    "coaching_in_progress",
    "awaiting_user_revision",
    "ready_for_final_confirmation",
}
ROUTABLE_TARGET_STATUSES = OPEN_TARGET_STATUSES | {"partial_response"}
CLOSED_TARGET_STATUSES = {
    "closed",
    "submitted_to_sheet",
    "expired_no_response",
    "needs_human_review",
    "superseded_by_next_cycle",
    "cancelled",
}
WORKFLOW_TARGET_SELECT = """
    SELECT
        w.workflow_id AS workflow_id,
        w.workflow_type AS workflow_type,
        w.title AS title,
        w.owner_user_id AS owner_user_id,
        w.status AS workflow_status,
        w.recurrence_group AS recurrence_group,
        w.recurrence_key AS recurrence_key,
        w.supersedes_workflow_id AS supersedes_workflow_id,
        w.instructions_json AS instructions_json,
        w.writeback_json AS writeback_json,
        w.no_response_policy_json AS no_response_policy_json,
        w.created_at AS workflow_created_at,
        w.updated_at AS workflow_updated_at,
        wt.target_user_id AS target_user_id,
        wt.platform AS platform,
        wt.status AS status,
        wt.phase AS phase,
        wt.tracker_code AS tracker_code,
        wt.last_outreach_message_id AS last_outreach_message_id,
        wt.last_outreach_at AS last_outreach_at,
        wt.reply_window_until AS reply_window_until,
        wt.last_inbound_at AS last_inbound_at,
        wt.sheet_row_key AS sheet_row_key,
        wt.raw_answer AS raw_answer,
        wt.final_answer AS final_answer,
        wt.pd_one_notes AS pd_one_notes,
        wt.closed_at AS closed_at,
        wt.updated_at AS target_updated_at
    FROM workflow_targets wt
    JOIN workflows w ON w.workflow_id = wt.workflow_id
"""
SAFE_INSTRUCTION_KEYS = {
    "question",
    "questions",
    "homework_questions",
    "rubric",
    "coaching_rubric",
    "completion_rule",
    "expected_answer_format",
    "privacy_notes",
    "user_visible_context",
}
SAFE_WRITEBACK_KEYS = {"type", "worksheet", "columns", "status_column", "row_key_column"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_after(deadline: str | None, now: str | None) -> bool:
    deadline_dt = parse_utc(deadline)
    now_dt = parse_utc(now) or datetime.now(timezone.utc)
    return bool(deadline_dt and now_dt > deadline_dt)


@dataclass(frozen=True)
class RouteDecision:
    action: str
    workflow_id: Optional[str] = None
    target_user_id: Optional[str] = None
    tracker_code: Optional[str] = None
    routing_evidence: Optional[str] = None
    candidates: tuple[dict[str, Any], ...] = ()
    reason: str = ""


class WorkflowRegistry:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser()

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS workflows (
                    workflow_id TEXT PRIMARY KEY,
                    workflow_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    recurrence_group TEXT NOT NULL DEFAULT '',
                    recurrence_key TEXT NOT NULL DEFAULT '',
                    supersedes_workflow_id TEXT NOT NULL DEFAULT '',
                    instructions_json TEXT NOT NULL DEFAULT '{}',
                    writeback_json TEXT NOT NULL DEFAULT '{}',
                    no_response_policy_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_targets (
                    workflow_id TEXT NOT NULL,
                    target_user_id TEXT NOT NULL,
                    platform TEXT NOT NULL DEFAULT 'mattermost',
                    status TEXT NOT NULL DEFAULT 'awaiting_reply',
                    phase TEXT NOT NULL DEFAULT 'awaiting_initial_reply',
                    tracker_code TEXT NOT NULL,
                    last_outreach_message_id TEXT NOT NULL DEFAULT '',
                    last_outreach_at TEXT NOT NULL DEFAULT '',
                    reply_window_until TEXT NOT NULL DEFAULT '',
                    last_inbound_at TEXT NOT NULL DEFAULT '',
                    sheet_row_key TEXT NOT NULL DEFAULT '',
                    raw_answer TEXT NOT NULL DEFAULT '',
                    final_answer TEXT NOT NULL DEFAULT '',
                    pd_one_notes TEXT NOT NULL DEFAULT '',
                    closed_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (workflow_id, target_user_id),
                    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
                );
                CREATE INDEX IF NOT EXISTS idx_workflow_targets_tracker ON workflow_targets(tracker_code);
                CREATE INDEX IF NOT EXISTS idx_workflow_targets_user_status ON workflow_targets(target_user_id, status);
                CREATE INDEX IF NOT EXISTS idx_workflow_targets_outreach ON workflow_targets(last_outreach_message_id);
                CREATE TABLE IF NOT EXISTS workflow_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL DEFAULT '',
                    target_user_id TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )

    def create_workflow(
        self,
        *,
        workflow_id: str,
        workflow_type: str,
        title: str,
        owner_user_id: str,
        status: str = "open",
        recurrence_group: str = "",
        recurrence_key: str = "",
        supersedes_workflow_id: str = "",
        instructions: dict[str, Any] | None = None,
        writeback: dict[str, Any] | None = None,
        no_response_policy: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> None:
        self.ensure_schema()
        ts = now or utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO workflows (
                    workflow_id, workflow_type, title, owner_user_id, status,
                    recurrence_group, recurrence_key, supersedes_workflow_id,
                    instructions_json, writeback_json, no_response_policy_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id) DO UPDATE SET
                    workflow_type=excluded.workflow_type,
                    title=excluded.title,
                    owner_user_id=excluded.owner_user_id,
                    status=excluded.status,
                    recurrence_group=excluded.recurrence_group,
                    recurrence_key=excluded.recurrence_key,
                    supersedes_workflow_id=excluded.supersedes_workflow_id,
                    instructions_json=excluded.instructions_json,
                    writeback_json=excluded.writeback_json,
                    no_response_policy_json=excluded.no_response_policy_json,
                    updated_at=excluded.updated_at
                """,
                (
                    workflow_id,
                    workflow_type,
                    title,
                    owner_user_id,
                    status,
                    recurrence_group,
                    recurrence_key,
                    supersedes_workflow_id,
                    json.dumps(instructions or {}, ensure_ascii=False, sort_keys=True),
                    json.dumps(writeback or {}, ensure_ascii=False, sort_keys=True),
                    json.dumps(no_response_policy or {}, ensure_ascii=False, sort_keys=True),
                    ts,
                    ts,
                ),
            )
            self.log_event(conn, workflow_id, "", "workflow_upserted", {"status": status}, ts)

    def add_target(
        self,
        *,
        workflow_id: str,
        target_user_id: str,
        tracker_code: str,
        platform: str = "mattermost",
        status: str = "awaiting_reply",
        phase: str = "awaiting_initial_reply",
        last_outreach_message_id: str = "",
        last_outreach_at: str = "",
        reply_window_until: str = "",
        sheet_row_key: str = "",
        now: str | None = None,
    ) -> None:
        self.ensure_schema()
        ts = now or utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO workflow_targets (
                    workflow_id, target_user_id, platform, status, phase, tracker_code,
                    last_outreach_message_id, last_outreach_at, reply_window_until,
                    sheet_row_key, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id, target_user_id) DO UPDATE SET
                    platform=excluded.platform,
                    status=excluded.status,
                    phase=excluded.phase,
                    tracker_code=excluded.tracker_code,
                    last_outreach_message_id=excluded.last_outreach_message_id,
                    last_outreach_at=excluded.last_outreach_at,
                    reply_window_until=excluded.reply_window_until,
                    sheet_row_key=excluded.sheet_row_key,
                    updated_at=excluded.updated_at
                """,
                (
                    workflow_id,
                    target_user_id,
                    platform,
                    status,
                    phase,
                    tracker_code,
                    last_outreach_message_id,
                    last_outreach_at,
                    reply_window_until,
                    sheet_row_key,
                    ts,
                ),
            )
            self.log_event(conn, workflow_id, target_user_id, "target_upserted", {"status": status, "tracker_code": tracker_code}, ts)

    def log_event(self, conn: sqlite3.Connection, workflow_id: str, target_user_id: str, event_type: str, metadata: dict[str, Any] | None = None, ts: str | None = None) -> None:
        conn.execute(
            "INSERT INTO workflow_events (workflow_id, target_user_id, event_type, timestamp, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (workflow_id, target_user_id, event_type, ts or utc_now(), json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)),
        )

    def close_prior_recurring_targets(
        self,
        *,
        workflow_type: str,
        recurrence_group: str,
        new_workflow_id: str,
        target_user_ids: Iterable[str],
        now: str | None = None,
    ) -> int:
        self.ensure_schema()
        target_ids = [t for t in target_user_ids if t]
        if not target_ids:
            return 0
        placeholders = ",".join("?" for _ in target_ids)
        ts = now or utc_now()
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT wt.workflow_id, wt.target_user_id
                FROM workflow_targets wt
                JOIN workflows w ON w.workflow_id = wt.workflow_id
                WHERE w.workflow_type = ?
                  AND w.recurrence_group = ?
                  AND wt.target_user_id IN ({placeholders})
                  AND wt.status IN ({','.join('?' for _ in OPEN_TARGET_STATUSES)})
                  AND wt.workflow_id <> ?
                """,
                [workflow_type, recurrence_group, *target_ids, *sorted(OPEN_TARGET_STATUSES), new_workflow_id],
            ).fetchall()
            for row in rows:
                conn.execute(
                    "UPDATE workflow_targets SET status='superseded_by_next_cycle', phase='superseded', closed_at=?, updated_at=? WHERE workflow_id=? AND target_user_id=?",
                    (ts, ts, row["workflow_id"], row["target_user_id"]),
                )
                self.log_event(conn, row["workflow_id"], row["target_user_id"], "target_superseded_by_next_cycle", {"new_workflow_id": new_workflow_id}, ts)
            return len(rows)

    def lookup_by_tracker(self, tracker_code: str, sender_id: str) -> Optional[dict[str, Any]]:
        if not tracker_code or not sender_id:
            return None
        self.ensure_schema()
        with self.connect() as conn:
            row = conn.execute(
                WORKFLOW_TARGET_SELECT + " WHERE wt.tracker_code = ? AND wt.target_user_id = ?",
                (tracker_code, sender_id),
            ).fetchone()
        return row_to_dict(row)

    def lookup_by_outreach_message(self, message_id: str, sender_id: str) -> Optional[dict[str, Any]]:
        if not message_id or not sender_id:
            return None
        self.ensure_schema()
        with self.connect() as conn:
            row = conn.execute(
                WORKFLOW_TARGET_SELECT + " WHERE wt.last_outreach_message_id = ? AND wt.target_user_id = ?",
                (message_id, sender_id),
            ).fetchone()
        return row_to_dict(row)

    def open_candidates(self, sender_id: str) -> list[dict[str, Any]]:
        if not sender_id:
            return []
        self.ensure_schema()
        with self.connect() as conn:
            rows = conn.execute(
                WORKFLOW_TARGET_SELECT + f"""
                WHERE wt.target_user_id = ?
                  AND wt.status IN ({','.join('?' for _ in OPEN_TARGET_STATUSES)})
                  AND w.status NOT IN ('closed', 'cancelled')
                ORDER BY wt.last_outreach_at DESC, w.created_at DESC
                """,
                [sender_id, *sorted(OPEN_TARGET_STATUSES)],
            ).fetchall()
        return [row_to_dict(row) for row in rows]

    def selected_workflow(self, workflow_id: str, target_user_id: str) -> Optional[dict[str, Any]]:
        if not workflow_id or not target_user_id:
            return None
        self.ensure_schema()
        with self.connect() as conn:
            row = conn.execute(
                WORKFLOW_TARGET_SELECT + " WHERE wt.workflow_id = ? AND wt.target_user_id = ?",
                (workflow_id, target_user_id),
            ).fetchone()
        return row_to_dict(row)

    def status_summary(self) -> dict[str, Any]:
        self.ensure_schema()
        with self.connect() as conn:
            workflows = conn.execute("SELECT status, COUNT(*) AS n FROM workflows GROUP BY status").fetchall()
            targets = conn.execute("SELECT status, COUNT(*) AS n FROM workflow_targets GROUP BY status").fetchall()
        return {
            "ok": True,
            "dbPath": str(self.db_path),
            "workflows": {r["status"]: r["n"] for r in workflows},
            "targets": {r["status"]: r["n"] for r in targets},
        }


def row_to_dict(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _json_obj(text: Any) -> dict[str, Any]:
    try:
        data = json.loads(text or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _is_routable(record: dict[str, Any] | None, *, now: str | None, exact_link: bool) -> bool:
    if not record:
        return False
    status = str(record.get("status") or "")
    if status in CLOSED_TARGET_STATUSES or status not in ROUTABLE_TARGET_STATUSES:
        return False
    if exact_link:
        return True
    if is_after(record.get("reply_window_until"), now):
        return False
    return True


def _extract_trackers(message_text: str) -> list[str]:
    seen: set[str] = set()
    trackers: list[str] = []
    for match in TRACKER_RE.finditer(str(message_text or "")):
        value = match.group(0).upper()
        if value not in seen:
            seen.add(value)
            trackers.append(value)
    return trackers


def _message_probably_workflow_related(message_text: str, candidates: list[dict[str, Any]]) -> bool:
    text = str(message_text or "").lower()
    if not text:
        return False
    generic = ["homework", "answer", "update", "status", "blocker", "next step", "進度", "作業", "答案", "回覆"]
    if any(word in text for word in generic):
        return True
    for candidate in candidates:
        title_words = [w.lower() for w in re.findall(r"[A-Za-z0-9]{4,}", str(candidate.get("title") or ""))]
        if any(word in text for word in title_words[:6]):
            return True
    return False


def _candidate_public_view(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow_id": record.get("workflow_id"),
        "title": record.get("title"),
        "tracker_code": record.get("tracker_code"),
        "phase": record.get("phase"),
        "reply_window_until": record.get("reply_window_until"),
    }


def route_inbound_message(
    registry: WorkflowRegistry,
    *,
    sender_id: str,
    message_text: str,
    root_message_id: str = "",
    now: str | None = None,
) -> RouteDecision:
    """Route a DM without leaking open workflow context into unrelated turns."""
    trackers = _extract_trackers(message_text)
    for tracker in trackers:
        record = registry.lookup_by_tracker(tracker, sender_id)
        if _is_routable(record, now=now, exact_link=True):
            return RouteDecision("inject_workflow", record["workflow_id"], sender_id, record.get("tracker_code"), "tracker_code_match")
    if trackers:
        # A visible tracker that does not belong to a routable target for this sender
        # must not be reinterpreted as another open workflow.
        return RouteDecision("normal_dm", reason="tracker_present_but_no_routable_target")

    if root_message_id:
        record = registry.lookup_by_outreach_message(root_message_id, sender_id)
        if _is_routable(record, now=now, exact_link=True):
            return RouteDecision("inject_workflow", record["workflow_id"], sender_id, record.get("tracker_code"), "thread_linkage")

    candidates = [c for c in registry.open_candidates(sender_id) if _is_routable(c, now=now, exact_link=False)]
    if not candidates:
        return RouteDecision("normal_dm", reason="no_routable_candidate")

    if not _message_probably_workflow_related(message_text, candidates):
        return RouteDecision("normal_dm", reason="unrelated_to_open_workflows")

    public_candidates = tuple(_candidate_public_view(c) for c in candidates)
    if len(candidates) == 1:
        c = candidates[0]
        return RouteDecision("ask_confirmation", candidates=public_candidates, reason="probable_single_candidate_requires_confirmation")
    return RouteDecision("ask_user_to_choose", candidates=public_candidates, reason="multiple_candidate_workflows")


def _safe_projection(record: dict[str, Any]) -> dict[str, Any]:
    instructions = _json_obj(record.get("instructions_json"))
    writeback = _json_obj(record.get("writeback_json"))
    return {
        "schema": "pd-one.outbound-dm-workflow-context.v1",
        "workflow_id": record.get("workflow_id"),
        "workflow_type": record.get("workflow_type"),
        "title": record.get("title"),
        "tracker_code": record.get("tracker_code"),
        "target_user_id": record.get("target_user_id"),
        "status": record.get("status"),
        "phase": record.get("phase"),
        "instructions": {k: instructions[k] for k in SAFE_INSTRUCTION_KEYS if k in instructions},
        "writeback": {k: writeback[k] for k in SAFE_WRITEBACK_KEYS if k in writeback},
        "privacy": [
            "Do not reveal other trainees/users or admin-only setup details.",
            "Do not treat unrelated DMs as belonging to this workflow.",
            "Capture raw, coached, and final answers separately when available.",
        ],
    }


def build_injected_context(registry: WorkflowRegistry, decision: RouteDecision) -> str:
    if decision.action != "inject_workflow" or not decision.workflow_id or not decision.target_user_id:
        return ""
    record = registry.selected_workflow(decision.workflow_id, decision.target_user_id)
    if not record:
        return ""
    projection = _safe_projection(record)
    payload = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (
        "[PD One outbound DM workflow]\n"
        "Active outbound DM workflow selected by deterministic router. "
        "Inject this workflow only for the current turn; do not generalize it to unrelated DMs. "
        "If the user's latest message is actually unrelated, answer the unrelated request and note that the workflow can continue when they use the tracker/reply thread.\n"
        f"Routing evidence: {decision.routing_evidence}\n"
        f"Workflow JSON: {payload}"
    )


def build_disambiguation_context(decision: RouteDecision) -> str:
    if decision.action not in {"ask_confirmation", "ask_user_to_choose"}:
        return ""
    payload = json.dumps({"action": decision.action, "reason": decision.reason, "candidates": list(decision.candidates)}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (
        "[PD One outbound DM workflow routing]\n"
        "There are open outbound workflow candidates, but no exact tracker/thread link was found. "
        "Do not inject full workflow context. Ask a short confirmation/choice question only if the user appears to be replying to a workflow; otherwise answer normally.\n"
        f"Candidate JSON: {payload}"
    )


def format_outreach_message(*, tracker_code: str, title: str, body: str) -> str:
    return (
        f"[PD One Follow-up: {tracker_code}]\n"
        f"{title}\n\n"
        f"{body.strip()}\n\n"
        f"Reply to this message, or include {tracker_code} in your reply, so I know your answer belongs to this follow-up."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage PD One outbound DM workflow registry")
    parser.add_argument("--db", type=Path, default=Path.home() / ".hermes" / "profiles" / "pdone" / "state" / "outbound_dm_workflows.sqlite")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    sub.add_parser("status")
    fmt = sub.add_parser("format-outreach")
    fmt.add_argument("--tracker", required=True)
    fmt.add_argument("--title", required=True)
    fmt.add_argument("--body", required=True)
    args = parser.parse_args()
    reg = WorkflowRegistry(args.db)
    if args.cmd == "init-db":
        reg.ensure_schema()
        print(json.dumps({"ok": True, "dbPath": str(reg.db_path)}, ensure_ascii=False, indent=2))
    elif args.cmd == "status":
        print(json.dumps(reg.status_summary(), ensure_ascii=False, indent=2, sort_keys=True))
    elif args.cmd == "format-outreach":
        print(format_outreach_message(tracker_code=args.tracker, title=args.title, body=args.body))


if __name__ == "__main__":
    main()

"""Guards the IT meeting progress-summary job against the 2026-11-10 token blowup.

That wake inlined it-meeting-briefing (the 12:00 pack) and appsheet-record-ops
(13,506 bytes) and then re-sent raw rows. Live token totals cannot be proven
here. These checks lock the inlined skill budget and the job contract.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "profiles" / "pdone" / "skills"
SCRIPTS = REPO / "profiles" / "pdone" / "scripts"
CONTRACT_PATH = REPO / "profiles" / "pdone" / "cron" / "job-9606f49ec7ec.contract.json"
TAIPEI = ZoneInfo("Asia/Taipei")
LIVE_APPSHEET_SKILL_BYTES = 13_506
PACK_MARKERS = (
    "infographic",
    "firm-template.pptx",
    "pd_one_pptx",
    "company-template",
    "load_firm_presentation",
)
sys.path.insert(0, str(SCRIPTS))

import it_meeting_progress_summary_gather as gather
import it_meeting_progress_summary_packet as packet


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _summary_skill() -> str:
    return (SKILLS / "it-meeting-progress-summary" / "SKILL.md").read_text(
        encoding="utf-8"
    )


def _briefing_skill() -> str:
    return (SKILLS / "it-meeting-briefing" / "SKILL.md").read_text(encoding="utf-8")


def test_summary_job_does_not_attach_the_write_skill_or_the_pack() -> None:
    contract = _contract()
    attached = contract["set"]["skills"]
    assert attached == ["it-meeting-progress-summary"]
    assert contract["set"]["skill"] == "it-meeting-progress-summary"
    blob = json.dumps(contract["set"])
    assert "appsheet-record-ops" not in blob
    assert "it-meeting-briefing" not in attached
    assert contract["set"]["model"] == "grok-4.7"
    assert "provider" not in contract["set"]
    assert contract["set"]["script"] == "it_meeting_progress_summary_gather.py"
    assert contract["set"]["enabled_toolsets"] == ["file", "no_mcp"]
    unchanged = contract["leave_unchanged"]
    assert unchanged["schedule_expr"] == "10 4 * * 2"
    assert unchanged["deliver"] == "local"
    assert unchanged["failure_deliver"] == "mattermost:5gmqtwqf7bde3cyihas79xi8ie"
    assert unchanged["monitor_script"] == "it_meeting_progress_summary_gate.py"
    assert unchanged["enabled"] is True
    assert unchanged["provider"] is None


def test_inlined_summary_skill_is_far_smaller_than_the_bad_wake() -> None:
    skill_bytes = (SKILLS / "it-meeting-progress-summary" / "SKILL.md").stat().st_size
    prompt_bytes = len(_contract()["set"]["prompt"].encode("utf-8"))
    assert skill_bytes <= 6000
    assert skill_bytes < LIVE_APPSHEET_SKILL_BYTES
    assert skill_bytes + prompt_bytes < LIVE_APPSHEET_SKILL_BYTES
    for marker in PACK_MARKERS:
        assert marker not in _summary_skill()
    assert "appsheet-record-ops" not in _summary_skill()


def test_noon_pack_skill_stays_complete() -> None:
    briefing = _briefing_skill()
    assert "firm-template.pptx" in briefing
    assert "infographic" in briefing
    assert "pd_one_pptx_from_template" in briefing
    assert (SKILLS / "it-meeting-briefing" / "SKILL.md").stat().st_size <= 8192


def test_gather_script_matches_the_contract_and_does_not_page_history() -> None:
    script = SCRIPTS / _contract()["set"]["script"]
    assert script.is_file()
    argv = gather.member_search_argv(
        "jp47xmyu8prytmqrhimaw9hy7e", "Outlook", "2026-10-27"
    )
    assert argv[argv.index("--max-fallback-posts") + 1] == "0"
    assert argv[argv.index("--max-results") + 1] == "6"
    assert gather.doc_header_argv(packet.IT_MANUAL_DOC_ID)[2] == packet.IT_MANUAL_DOC_ID


class _Boom:
    def find(self, table: str, selector: str) -> list:
        raise AssertionError(f"not_due must not probe {table}")

    def post_audit(self, channel_id: str, lookback_days: int) -> dict:
        raise AssertionError("not_due must not audit")

    def member_search(self, channel_id: str, query: str, since: str) -> dict:
        raise AssertionError("not_due must not search")

    def doc_header(self, doc_id: str) -> dict:
        raise AssertionError("not_due must not inspect docs")


def test_third_tuesday_is_not_due_and_does_not_gather() -> None:
    now = datetime(2026, 11, 17, 12, 10, tzinfo=TAIPEI)
    assert packet.render_run(now, _Boom()) == "not_due"


def test_due_window_walks_back_to_the_prior_meeting_tuesday() -> None:
    now = datetime(2026, 11, 10, 12, 10, tzinfo=TAIPEI)
    window = packet.meeting_window(now)
    assert window is not None
    assert window.meeting_date == "2026-11-10"
    assert window.start == datetime(2026, 10, 27, 13, 30, tzinfo=TAIPEI)
    later = datetime(2026, 11, 24, 12, 10, tzinfo=TAIPEI)
    later_window = packet.meeting_window(later)
    assert later_window is not None
    assert later_window.start == datetime(2026, 11, 10, 13, 30, tzinfo=TAIPEI)


class _FakeSources:
    def __init__(self) -> None:
        self.tables: list[str] = []

    def find(self, table: str, selector: str) -> list:
        self.tables.append(table)
        if "Case_Updates" in selector and "Created On" in selector:
            raise RuntimeError("Created On is not a Case_Updates column")
        if table == "Case_Updates":
            return [
                {
                    "CaseUpdateID": "C-U-1",
                    "Timestamp": "2026-11-03 10:12:00",
                    "CaseID": "C-parent",
                    "Case Type": "Other",
                    "Update Summary": "closed the ticket",
                    "New Status": "Completed",
                    "Update Description": "x" * 5000,
                    "Mattermost Link": "https://mm.example/secret",
                },
                {
                    "CaseUpdateID": "C-U-2",
                    "Timestamp": "2026-11-04 10:12:00",
                    "CaseID": "C-other",
                    "Case Type": "Facilities",
                    "Update Summary": "not IT",
                },
            ]
        if "C-parent" in selector:
            return [
                {
                    "CaseID": "C-parent",
                    "Type": "IT Ticket",
                    "Status": "Completed",
                    "Title": "Parent",
                }
            ]
        if "Created On" in selector:
            return [
                {
                    "CaseID": "C-new",
                    "Type": "IT Ticket",
                    "Created On": "2026-11-02 10:00:00",
                    "Title": "Mail host aa:bb:cc:dd:ee:ff",
                    "Status": "Not Started",
                    "Description": "reset the account at 10.1.2.3 token=abc",
                    "sql-srv Link": "secret",
                }
            ]
        return [
            {
                "CaseID": "C-open",
                "Type": "IT Ticket",
                "Title": "Older open",
                "Status": "In Progress",
                "Description": "payroll row",
            }
        ]

    def post_audit(self, channel_id: str, lookback_days: int) -> dict:
        return {
            "status": "ok",
            "active_in_window": 3,
            "posts_in_window": 4,
            "window": {"lookback_days": lookback_days},
            "bot": {"username": "should-not-leak"},
        }

    def member_search(self, channel_id: str, query: str, since: str) -> dict:
        return {
            "status": "ok",
            "hitCapReached": False,
            "results": [
                {
                    "createAt": 1,
                    "originalPostId": "thread-1",
                    "userId": "person-private",
                    "excerpt": "Outlook sync at 10.0.0.8 mac 00-11-22-33-44-55",
                }
            ],
        }

    def doc_header(self, doc_id: str) -> dict:
        return {
            "status": "ok",
            "documentTitle": "IT manual",
            "docId": doc_id,
            "headers": [{"type": "DEFAULT", "text": "Header 2026-09-29\nline"}],
            "recentChangelogEntries": [
                {"date": "2026-09-29", "text": "no write in window"}
            ],
        }


def test_due_packet_projects_rows_and_stays_small() -> None:
    now = datetime(2026, 11, 10, 12, 23, tzinfo=TAIPEI)
    sources = _FakeSources()
    text = packet.render_run(now, sources)
    assert "wakeAgent" not in text
    body = json.loads(text)
    assert body["gate"] == "due:2026-11-10"
    assert body["meeting_date"] == "2026-11-10"
    titles = json.dumps(body["new_tickets"])
    assert "Description" not in titles
    assert "aa:bb:cc:dd:ee:ff" not in text
    assert "10.1.2.3" not in text
    assert "10.0.0.8" not in text
    assert "00-11-22-33-44-55" not in text
    assert "person-private" not in text
    assert "should-not-leak" not in text
    assert "payroll row" not in text
    assert body["new_tickets"]["returned"] == 1
    update_ids = [
        row["CaseUpdateID"]
        for row in body["case_updates"]["timestamp_it_ticket"]["rows"]
    ]
    assert update_ids == ["C-U-1"]
    assert (
        body["case_updates"]["timestamp_it_ticket"]["parent_status"]["C-parent"]
        == "Completed"
    )
    assert body["case_updates"]["created_on"]["error"]
    assert body["channels"][0]["audit"]["counts_are_lookback_not_topics"] is True
    assert body["documents"][0]["doc_id"] == packet.IT_MANUAL_DOC_ID
    assert len(text.encode("utf-8")) < LIVE_APPSHEET_SKILL_BYTES


def test_oversized_packet_stays_valid_and_under_the_cap() -> None:
    fat = {
        "schema": packet.PACKET_SCHEMA,
        "gate": "due:2026-11-10",
        "open_it_tickets": {
            "returned": 40,
            "truncated": False,
            "rows": [
                {"CaseID": f"C-{i}", "Title": "詞" * 400, "Status": "In Progress"}
                for i in range(40)
            ],
        },
        "channels": [
            {
                "name": "IT",
                "search": {"hits": [{"excerpt": "x" * 500} for _ in range(6)]},
            }
        ],
        "documents": [{"headers": [{"text": "h" * 2000}], "changelog": ["c" * 2000]}],
        "errors": [],
    }
    text = packet.render_packet(fat)
    assert len(text) <= packet.MAX_PACKET_CHARS
    json.loads(text)


@pytest.mark.parametrize(
    "day",
    [
        datetime(2026, 11, 3, 12, 0, tzinfo=TAIPEI),
        datetime(2026, 11, 11, 12, 0, tzinfo=TAIPEI),
        datetime(2026, 11, 17, 12, 0, tzinfo=TAIPEI),
    ],
)
def test_gate_matches_the_live_second_and_fourth_tuesday_rule(day: datetime) -> None:
    assert packet.meeting_date(day) is None


def test_gate_marks_the_second_and_fourth_tuesdays() -> None:
    assert (
        packet.meeting_date(datetime(2026, 11, 10, 12, 10, tzinfo=TAIPEI))
        == "2026-11-10"
    )
    assert (
        packet.meeting_date(datetime(2026, 11, 24, 12, 10, tzinfo=TAIPEI))
        == "2026-11-24"
    )

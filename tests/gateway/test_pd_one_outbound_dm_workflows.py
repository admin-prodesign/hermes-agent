import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from gateway.pd_one_outbound_dm_workflows import (
    WorkflowRegistry,
    build_injected_context,
    format_outreach_message,
    route_inbound_message,
)


def utc(hours=0):
    return (datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc) + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def make_registry(tmp_path: Path) -> WorkflowRegistry:
    db = tmp_path / "workflows.sqlite"
    reg = WorkflowRegistry(db)
    reg.ensure_schema()
    return reg


def test_tracker_match_routes_only_for_target_sender(tmp_path):
    reg = make_registry(tmp_path)
    reg.create_workflow(
        workflow_id="wf-homework",
        workflow_type="training_homework",
        title="Training Homework — SOP Module 1",
        owner_user_id="admin",
        instructions={"question": "What are the first three SOP documentation steps?"},
    )
    reg.add_target(
        workflow_id="wf-homework",
        target_user_id="alice",
        tracker_code="HW-2026-0611-003",
        status="awaiting_reply",
        phase="awaiting_initial_reply",
        last_outreach_message_id="post-1",
        reply_window_until=utc(48),
    )

    decision = route_inbound_message(
        reg,
        sender_id="alice",
        message_text="Here is my answer for HW-2026-0611-003: first observe, then document, then review.",
        root_message_id="",
        now=utc(1),
    )

    assert decision.action == "inject_workflow"
    assert decision.workflow_id == "wf-homework"
    assert decision.routing_evidence == "tracker_code_match"

    wrong_sender = route_inbound_message(
        reg,
        sender_id="bob",
        message_text="HW-2026-0611-003 my answer is...",
        root_message_id="",
        now=utc(1),
    )
    assert wrong_sender.action == "normal_dm"
    assert wrong_sender.workflow_id is None


def test_open_workflow_is_not_injected_for_unrelated_dm(tmp_path):
    reg = make_registry(tmp_path)
    reg.create_workflow(
        workflow_id="wf-homework",
        workflow_type="training_homework",
        title="Training Homework — SOP Module 1",
        owner_user_id="admin",
        instructions={"question": "What are the first three SOP documentation steps?"},
    )
    reg.add_target(
        workflow_id="wf-homework",
        target_user_id="alice",
        tracker_code="HW-2026-0611-003",
        status="awaiting_reply",
        phase="awaiting_initial_reply",
        last_outreach_message_id="post-1",
        reply_window_until=utc(48),
    )

    decision = route_inbound_message(
        reg,
        sender_id="alice",
        message_text="Can you help me reset my Google password?",
        root_message_id="",
        now=utc(1),
    )

    assert decision.action == "normal_dm"
    assert decision.workflow_id is None


def test_thread_linkage_routes_without_tracker(tmp_path):
    reg = make_registry(tmp_path)
    reg.create_workflow(
        workflow_id="wf-project",
        workflow_type="project_update",
        title="Weekly Project Tracker — Week 24",
        owner_user_id="admin",
        instructions={"question": "Send project status, blocker, next step, finish date."},
    )
    reg.add_target(
        workflow_id="wf-project",
        target_user_id="alice",
        tracker_code="PROJ-2026-W24-ALICE",
        status="awaiting_reply",
        phase="awaiting_initial_reply",
        last_outreach_message_id="post-project-24",
        reply_window_until=utc(48),
    )

    decision = route_inbound_message(
        reg,
        sender_id="alice",
        message_text="Status is green, no blocker, next step is QA.",
        root_message_id="post-project-24",
        now=utc(1),
    )

    assert decision.action == "inject_workflow"
    assert decision.workflow_id == "wf-project"
    assert decision.routing_evidence == "thread_linkage"


def test_expired_open_workflow_is_not_auto_injected_without_exact_link(tmp_path):
    reg = make_registry(tmp_path)
    reg.create_workflow(
        workflow_id="wf-homework",
        workflow_type="training_homework",
        title="Training Homework — SOP Module 1",
        owner_user_id="admin",
        instructions={"question": "Homework question"},
    )
    reg.add_target(
        workflow_id="wf-homework",
        target_user_id="alice",
        tracker_code="HW-OLD",
        status="awaiting_reply",
        phase="awaiting_initial_reply",
        last_outreach_message_id="post-old",
        reply_window_until=utc(-1),
    )

    decision = route_inbound_message(
        reg,
        sender_id="alice",
        message_text="Here is my homework answer.",
        root_message_id="",
        now=utc(1),
    )

    assert decision.action == "normal_dm"


def test_recurring_new_cycle_supersedes_prior_open_targets(tmp_path):
    reg = make_registry(tmp_path)
    reg.create_workflow(
        workflow_id="proj-w23",
        workflow_type="project_update",
        title="Weekly Project Tracker — Week 23",
        owner_user_id="admin",
        recurrence_group="project_tracker_weekly",
        recurrence_key="2026-W23",
        instructions={},
    )
    reg.add_target(
        workflow_id="proj-w23",
        target_user_id="alice",
        tracker_code="PROJ-2026-W23-ALICE",
        status="awaiting_reply",
        phase="awaiting_initial_reply",
        reply_window_until=utc(24),
    )

    reg.close_prior_recurring_targets(
        workflow_type="project_update",
        recurrence_group="project_tracker_weekly",
        new_workflow_id="proj-w24",
        target_user_ids=["alice"],
        now=utc(1),
    )
    reg.create_workflow(
        workflow_id="proj-w24",
        workflow_type="project_update",
        title="Weekly Project Tracker — Week 24",
        owner_user_id="admin",
        recurrence_group="project_tracker_weekly",
        recurrence_key="2026-W24",
        instructions={},
    )
    reg.add_target(
        workflow_id="proj-w24",
        target_user_id="alice",
        tracker_code="PROJ-2026-W24-ALICE",
        status="awaiting_reply",
        phase="awaiting_initial_reply",
        reply_window_until=utc(48),
    )

    old_decision = route_inbound_message(
        reg,
        sender_id="alice",
        message_text="PROJ-2026-W23-ALICE old answer",
        root_message_id="",
        now=utc(2),
    )
    assert old_decision.action == "normal_dm"

    new_decision = route_inbound_message(
        reg,
        sender_id="alice",
        message_text="PROJ-2026-W24-ALICE new answer",
        root_message_id="",
        now=utc(2),
    )
    assert new_decision.action == "inject_workflow"
    assert new_decision.workflow_id == "proj-w24"


def test_ambiguous_related_message_asks_disambiguation_without_full_injection(tmp_path):
    reg = make_registry(tmp_path)
    for workflow_id, title, tracker in [
        ("wf-a", "Training Homework — SOP Module 1", "HW-A"),
        ("wf-b", "Training Homework — Safety Module 2", "HW-B"),
    ]:
        reg.create_workflow(
            workflow_id=workflow_id,
            workflow_type="training_homework",
            title=title,
            owner_user_id="admin",
            instructions={"question": "Homework question"},
        )
        reg.add_target(
            workflow_id=workflow_id,
            target_user_id="alice",
            tracker_code=tracker,
            status="awaiting_reply",
            phase="awaiting_initial_reply",
            reply_window_until=utc(48),
        )

    decision = route_inbound_message(
        reg,
        sender_id="alice",
        message_text="Here is my homework answer.",
        root_message_id="",
        now=utc(1),
    )

    assert decision.action == "ask_user_to_choose"
    assert decision.workflow_id is None
    assert {c["tracker_code"] for c in decision.candidates} == {"HW-A", "HW-B"}


def test_build_context_omits_admin_setup_and_includes_routing_evidence(tmp_path):
    reg = make_registry(tmp_path)
    reg.create_workflow(
        workflow_id="wf-homework",
        workflow_type="training_homework",
        title="Training Homework — SOP Module 1",
        owner_user_id="admin",
        instructions={
            "question": "What are the first three SOP documentation steps?",
            "admin_secret_note": "manager-only setup detail",
            "rubric": ["specific", "evidence-backed"],
        },
        writeback={"type": "google_sheet", "spreadsheet_id": "sheet-1"},
    )
    reg.add_target(
        workflow_id="wf-homework",
        target_user_id="alice",
        tracker_code="HW-2026-0611-003",
        status="awaiting_reply",
        phase="coaching_in_progress",
    )
    decision = route_inbound_message(
        reg,
        sender_id="alice",
        message_text="HW-2026-0611-003 answer",
        root_message_id="",
        now=utc(1),
    )

    context = build_injected_context(reg, decision)

    assert "Active outbound DM workflow selected by deterministic router" in context
    assert "tracker_code_match" in context
    assert "HW-2026-0611-003" in context
    assert "manager-only setup detail" not in context
    assert "spreadsheet_id" not in context


def test_format_outreach_message_contains_tracker_title_and_reply_instruction():
    text = format_outreach_message(
        tracker_code="HW-2026-0611-003",
        title="Training Homework — SOP Module 1",
        body="Question: What are the first three steps?",
    )

    assert text.startswith("[PD One Follow-up: HW-2026-0611-003]")
    assert "Training Homework — SOP Module 1" in text
    assert "Reply to this message, or include HW-2026-0611-003" in text

"""Portal-only approval notify must not tell the employee it posted to Admin.

Regression for Ivy's PDAPP-20261104-61CDF611: admin_approval_notify returned
route=portal / post_id=portal-only / mattermost_posted=false (Andy 2026-09-08
portal-only rule), but cmd_admin_approval_request claimed the ticket was sent
to the PD One Admin channel.
"""
from __future__ import annotations

import argparse
import types
from pathlib import Path

import pytest

from tools.pd_one_ops import pd_one_safe_ops_part1 as part1

TICKET = "PDAPP-20261104-61CDF611"
ORIGIN_INLINE = (
    f"I asked @Owner for inline approval in this thread as {TICKET}. "
    "The approved action is cryptographically bound to this request."
)
ADMIN_CHANNEL = (
    f"This request came from a DM Owner cannot access, so I sent approval ticket "
    f"{TICKET} to the PD One Admin channel."
)
PORTAL_QUEUE = (
    f"I created approval ticket {TICKET} and it is now in the PD One Portal "
    "approval queue, awaiting Andy approval. It was not posted to any Mattermost "
    "channel, and I will not take privileged action until it is approved."
)
NOTIFY_FAILED = (
    f"I created approval ticket {TICKET}, but the admin notification failed and "
    "needs retry by admin. I will not take privileged action until it is approved."
)


@pytest.mark.parametrize(
    ("notify_result", "expected"),
    [
        ({"ok": True, "route": "origin_inline", "post_id": "abc123"}, ORIGIN_INLINE),
        (
            {
                "ok": True,
                "route": "origin_inline",
                "post_id": "portal-only",
                "mattermost_posted": False,
            },
            ORIGIN_INLINE,
        ),
        (
            {
                "ok": True,
                "route": "admin_channel",
                "post_id": "mmpost00000000000000000001",
                "mattermost_posted": True,
            },
            ADMIN_CHANNEL,
        ),
        ({"ok": False, "route": "portal", "post_id": "portal-only"}, NOTIFY_FAILED),
        ({"ok": True, "route": "portal", "post_id": "portal-only", "mattermost_posted": False}, PORTAL_QUEUE),
        ({"ok": True, "route": "portal"}, PORTAL_QUEUE),
        ({"ok": True, "route": "admin_channel", "post_id": None}, PORTAL_QUEUE),
        ({"ok": True, "route": "admin_channel", "post_id": ""}, PORTAL_QUEUE),
        ({"ok": True, "route": "admin_channel", "post_id": "portal-only"}, PORTAL_QUEUE),
        (
            {
                "ok": True,
                "route": "admin_channel",
                "post_id": "mmpost00000000000000000001",
                "mattermost_posted": False,
            },
            PORTAL_QUEUE,
        ),
    ],
    ids=[
        "origin_inline",
        "origin_inline_wins_over_portal_markers",
        "real_admin_channel",
        "notification_failed",
        "ivy_portal_only_receipt",
        "route_portal",
        "missing_post_id",
        "empty_post_id",
        "post_id_portal_only",
        "mattermost_posted_false",
    ],
)
def test_employee_message_for_approval_notify(notify_result, expected):
    message = part1.employee_message_for_approval_notify(TICKET, notify_result)
    assert message == expected
    assert ("PD One Admin channel" in message) == (expected == ADMIN_CHANNEL)


def _request_args() -> argparse.Namespace:
    return argparse.Namespace(
        requester_user_id="a" * 26,
        requester_label="Ivy",
        origin_channel_id="b" * 26,
        origin_channel_name="dm-ivy",
        origin_root_id="c" * 26,
        origin_post_id="d" * 26,
        admin_channel_id="e" * 26,
        request_type="generic_handoff_v1",
        requested_action="Need a privileged action",
        requested_scope=None,
        risk_summary=None,
        acceptance_criteria=None,
        required_capabilities=None,
        allowed_document_ids=None,
        allowed_write_targets=None,
        unresolved_assumptions=None,
        request_original=None,
        request_english=None,
        idempotency_key="ivy-portal-only",
        allow_deployment=False,
        dry_run=False,
    )


def test_cmd_admin_approval_request_portal_only_does_not_claim_admin_channel(monkeypatch):
    captured: dict = {}

    class Ledger:
        def create_draft(self, context, idempotency_key=None):
            return {"ticket_id": TICKET, "status": "needs_employee_confirmation"}

        def validate_readiness(self, ticket_id, fields, validator=None):
            return {"ticket_id": TICKET, "status": "needs_employee_confirmation", "implementation_plan": {}}

        def confirm_draft(self, ticket_id, employee_confirmation_post_id=None):
            return {"ticket_id": TICKET}

    class Notify:
        def notify_ticket(self, ledger, ticket_id, admin_channel_id=None, dry_run=False):
            return {
                "ok": True,
                "route": "portal",
                "post_id": "portal-only",
                "mattermost_posted": False,
                "channel_id": None,
            }

    monkeypatch.setattr(part1, "employee_live_drive_writer_skips_admin_ticket", lambda **kwargs: None)
    monkeypatch.setattr(part1, "verified_admin_request_source", lambda *args, **kwargs: {"eligible": False})
    monkeypatch.setattr(
        part1,
        "load_admin_approval_modules",
        lambda: (types.SimpleNamespace(ApprovalLedger=lambda path: Ledger()), Notify()),
    )
    monkeypatch.setattr(part1, "APPROVAL_LEDGER", lambda: Path("/tmp/unused-approval-ledger.json"))
    monkeypatch.setattr(part1, "emit", captured.update)

    part1.cmd_admin_approval_request(_request_args())

    assert captured["status"] == "sent"
    assert captured["ticket_id"] == TICKET
    assert captured["approval_route"] == "portal"
    assert captured["admin_post_id"] == "portal-only"
    assert captured["employee_message"] == PORTAL_QUEUE
    assert "PD One Admin channel" not in captured["employee_message"]

"""PD One's Mattermost bot was renamed from ``pd_one_bot`` to ``pdone``; its user id did not change.

Mentions and approval commands must accept both handles, identity checks key on the bot
user id, and the labels the review log writes use the new name.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

PD_ONE_OPS = Path(__file__).resolve().parents[3] / "tools" / "pd_one_ops"
TICKET = "PDAPP-20261019-ABCDEFGH"
BOT_ID = "bot0000000000000000000000a"


@pytest.fixture
def review_log(monkeypatch):
    monkeypatch.syspath_prepend(str(PD_ONE_OPS))
    from tools.pd_one_ops import mattermost_review_log, mattermost_review_log_part0

    return mattermost_review_log, mattermost_review_log_part0


@pytest.fixture
def listener(monkeypatch):
    monkeypatch.syspath_prepend(str(PD_ONE_OPS))
    if "admin_approval_tickets" not in sys.modules:
        stub = types.ModuleType("admin_approval_tickets")
        stub.ApprovalLedger, stub.DEFAULT_LEDGER_PATH, stub.InvalidTransition = object, "", Exception
        monkeypatch.setitem(sys.modules, "admin_approval_tickets", stub)
    from tools.pd_one_ops import pd_one_admin_approval_listener

    return pd_one_admin_approval_listener


@pytest.mark.parametrize("handle", ["@pdone", "@pd_one_bot", "@PDONE", ""])
def test_explicit_approve_accepts_both_bot_handles(listener, handle):
    parsed = listener.parse_decision(f"approve {TICKET} {handle} with: run it".replace("  ", " "))
    assert parsed == {"decision": "approved", "ticket_id": TICKET, "instructions": "run it"}


@pytest.mark.parametrize("handle", ["@pdone", "@pd_one_bot"])
def test_explicit_reject_accepts_both_bot_handles(listener, handle):
    parsed = listener.parse_decision(f"reject {TICKET} {handle}: not now")
    assert parsed == {"decision": "rejected", "ticket_id": TICKET, "instructions": "not now"}


@pytest.mark.parametrize("handle", ["@someone_else", "@pdonebot"])
def test_explicit_decision_rejects_other_handles(listener, handle):
    assert listener.parse_decision(f"approve {TICKET} {handle}") is None


@pytest.mark.parametrize(
    "post",
    [
        {"message": "hello @pdone"},
        {"message": "@pd_one_bot can you check"},
        {"message": "@PD_ONE_BOT can you check"},
        {"message": f"@{BOT_ID} ping"},
        {"message": "no handle here", "props": {"mentions": [BOT_ID]}},
    ],
)
def test_post_mentions_bot_accepts_new_legacy_and_id(review_log, post):
    facade, _ = review_log
    assert facade.post_mentions_bot(post, {"id": BOT_ID, "username": "pdone"})


@pytest.mark.parametrize("message", ["hello @pdonebot", "email pdone@example.com", "@someone_else hi"])
def test_post_mentions_bot_rejects_lookalikes(review_log, message):
    facade, _ = review_log
    assert not facade.post_mentions_bot({"message": message}, {"id": BOT_ID, "username": "pdone"})


def test_post_mentions_bot_matches_by_id_when_username_missing(review_log):
    facade, _ = review_log
    post = {"message": "hi", "props": {"mentions": [BOT_ID]}}
    assert facade.post_mentions_bot(post, {"id": BOT_ID})


@pytest.mark.parametrize("handle", ["@pdone", "@pd_one_bot"])
def test_quoted_request_to_either_handle_is_not_a_progress_update(review_log, handle):
    facade, _ = review_log
    record = {"request_summary": f'已完成 "{handle} 幫我整理"'}
    assert facade.is_likely_project_list_progress_update(record) is False


def test_dm_review_row_label_uses_new_bot_name(review_log, monkeypatch):
    facade, part0 = review_log
    appended: list[list[str]] = []
    monkeypatch.setattr(part0, "resolve_user", lambda user_id: {"mattermost_username": "alice"})
    monkeypatch.setattr(part0, "append_row", lambda row: appended.append(row) or {"ok": True})
    args = facade.build_parser().parse_args([
        "append", "--user-id", "user000000000000000000000a", "--channel-id", "chan0", "--dm",
        "--category", "dm_question", "--request-summary", "hi", "--assistant-response-type", "answer",
        "--reason", "test", "--timestamp-utc", "2026-10-19T00:00:00Z",
    ])
    args.func(args)
    assert appended[0][4] == "DM: alice <> pdone"

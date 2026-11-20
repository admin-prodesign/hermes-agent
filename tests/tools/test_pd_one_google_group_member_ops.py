"""Behaviour contracts for Google group member add/remove with PDAPP or Andy post auth."""
from __future__ import annotations

import pytest

from tools.pd_one_ops import pd_one_google_group_member_ops as ops
from tools.pd_one_ops import pd_one_safe_ops_mcp_part0 as mcp

ANDY_USER_ID = "5nak6m7nmf8kudbrwbtccazbgc"
ORIGIN_POST_ID = "zyxwvutsrqponmlkjihgfedcba"
GROUP = "it-team@prodesign-group.com"
MEMBER = "employee@prodesign-group.com"
ADMIN_CHANNEL = "5gmqtwqf7bde3cyihas79xi8ie"
NOW_MS = 1_700_000_000_000


@pytest.fixture(autouse=True)
def _stub_fixed_account(monkeypatch):
    monkeypatch.setattr(ops, "fixed_account", lambda: "admin@prodesign-group.com")


class _FakeDirectoryClient:
    def __init__(self, *, role: str | None = None) -> None:
        self._role = role
        self.closed = False

    def get_role(self, group: str, member: str) -> str | None:
        return self._role

    def add_member(self, group_email: str, member_email: str, member_role: str = "MEMBER") -> None:
        self._role = member_role

    def delete_member(self, group: str, member: str) -> None:
        self._role = None

    def close(self) -> None:
        self.closed = True


def _andy_post(message: str, *, post_id: str = ORIGIN_POST_ID) -> dict:
    return {
        "id": post_id,
        "user_id": ANDY_USER_ID,
        "channel_id": ADMIN_CHANNEL,
        "delete_at": 0,
        "create_at": NOW_MS - 60_000,
        "message": message,
    }


def test_mm_post_prefix_skips_pdapp_ticket_format_before_post_auth(monkeypatch):
    monkeypatch.setattr(ops, "andy_user_id", lambda: ANDY_USER_ID)
    monkeypatch.setattr(
        ops,
        "authorize_ticket",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("authorize_ticket must not run")),
    )
    client = _FakeDirectoryClient(role="MEMBER")
    payload = ops.apply_member_change(
        action="remove-member",
        group=GROUP,
        member=MEMBER,
        role="MEMBER",
        dry_run=False,
        ticket_id=f"mm-post:{ORIGIN_POST_ID}",
        confirm_live_write=ops.LIVE_CONFIRMATION,
        client=client,
        post_fetcher=lambda pid: _andy_post(f"Remove {MEMBER} from {GROUP}", post_id=pid),
        now_ms=NOW_MS,
    )
    assert payload["mm_post_id"] == ORIGIN_POST_ID
    assert payload["ticket_id"] is None
    assert payload["authorization"]["authorization"] == "andy_mattermost_post"


def test_apply_live_with_mm_post_id_authorizes_andy_post(monkeypatch):
    monkeypatch.setattr(ops, "andy_user_id", lambda: ANDY_USER_ID)
    client = _FakeDirectoryClient(role="MEMBER")
    payload = ops.apply_member_change(
        action="remove-member",
        group=GROUP,
        member=MEMBER,
        role="MEMBER",
        dry_run=False,
        mm_post_id=ORIGIN_POST_ID,
        confirm_live_write=ops.LIVE_CONFIRMATION,
        client=client,
        post_fetcher=lambda pid: _andy_post(f"please remove {MEMBER} from google group {GROUP}", post_id=pid),
        now_ms=NOW_MS,
    )
    assert payload["authorization"]["authorization"] == "andy_mattermost_post"
    assert payload["mm_post_id"] == ORIGIN_POST_ID
    assert payload["changed"] is True
    assert client._role is None


def test_mcp_wrapper_passes_mm_post_id_without_ticket_id(monkeypatch):
    calls: list[list[str]] = []

    def fake_run_json(cmd, **kwargs):
        calls.append([str(part) for part in cmd])
        return "{}"

    monkeypatch.setattr(mcp, "run_json", fake_run_json)
    mcp.pd_one_google_group_change_apply(
        GROUP,
        "remove-member",
        MEMBER,
        mm_post_id=ORIGIN_POST_ID,
        confirm_live_write=ops.LIVE_CONFIRMATION,
    )
    argv = calls[0]
    assert "--mm-post-id" in argv
    assert ORIGIN_POST_ID in argv
    assert "--ticket-id" not in argv


def test_mcp_wrapper_maps_mm_post_ticket_alias(monkeypatch):
    calls: list[list[str]] = []

    def fake_run_json(cmd, **kwargs):
        calls.append([str(part) for part in cmd])
        return "{}"

    monkeypatch.setattr(mcp, "run_json", fake_run_json)
    mcp.pd_one_google_group_change_apply(
        GROUP,
        "remove-member",
        MEMBER,
        ticket_id=f"mm-post:{ORIGIN_POST_ID}",
        confirm_live_write=ops.LIVE_CONFIRMATION,
    )
    argv = calls[0]
    idx = argv.index("--mm-post-id")
    assert argv[idx + 1] == ORIGIN_POST_ID
    assert "--ticket-id" not in argv


def test_authorize_andy_mm_post_rejects_stale_post(monkeypatch):
    monkeypatch.setattr(ops, "andy_user_id", lambda: ANDY_USER_ID)
    with pytest.raises(SystemExit):
        ops.authorize_andy_mm_post(
            mm_post_id=ORIGIN_POST_ID,
            action="remove-member",
            group=GROUP,
            member=MEMBER,
            role="MEMBER",
            post_fetcher=lambda _pid: _andy_post(
                f"remove {MEMBER} from {GROUP}",
                post_id=ORIGIN_POST_ID,
            ),
            now_ms=NOW_MS + ops.POST_MAX_AGE_MS + 1,
        )
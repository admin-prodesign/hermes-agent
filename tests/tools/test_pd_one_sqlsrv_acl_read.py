"""``pd_one_sqlsrv_windows_acl_read`` authorizes on the requester's live NTFS rights and fails closed.

Its ``main()`` shipped as a stub that could not run (``build_parser`` was defined after the
``__main__`` guard and nothing set ``args.func``), so the tool never started as a script.
These pin the restored contract: red-line paths and unknown requesters are refused before any
helper call, read access needs an Allow ACE with read rights and no matching Deny, a helper
error is a refusal, and listings never return red-line entries. Nothing is written.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from tools.pd_one_ops import pd_one_sqlsrv_windows_acl_read as acl

REQUESTER = "requester-id-placeholder"
ADMIN = "admin-id-placeholder"
SHARE = r"\\file-server\share\plans"


class FakeHelper:
    def __init__(self, authorize: dict[str, Any], listing: dict[str, Any] | None = None) -> None:
        self.authorize = authorize
        self.listing = listing or {"ok": True, "items": []}
        self.payloads: list[str] = []

    def unc_path(self, path: str) -> str:
        return path

    def load_env(self) -> dict[str, str]:
        return {}

    def make_session(self, values: dict[str, str]) -> tuple[str, str, str, str]:
        return ("session", "helper-host", "helper-user", "helper-secret")

    def remote_payload(self, command: str, target: str, max_items: int, max_bytes: int, host: str) -> str:
        return f"{command}:{target}"

    def run_via_task(self, session: Any, user: str, password: str, payload: str, timeout: int) -> dict[str, Any]:
        self.payloads.append(payload)
        return self.listing if payload.startswith(("list:", "stat:", "read:")) else self.authorize


@pytest.fixture(autouse=True)
def profile(tmp_path, monkeypatch):
    policies = tmp_path / "policies"
    policies.mkdir()
    users = {
        REQUESTER: {"status": "active", "mattermostEmail": "person@example.com", "roles": ["staff"]},
        ADMIN: {"status": "active", "mattermostEmail": "admin@example.com", "roles": ["admin"]},
        "inactive-id": {"status": "disabled", "mattermostEmail": "gone@example.com"},
    }
    (policies / "mattermost-users.json").write_text(json.dumps({"users": users}), encoding="utf-8")
    monkeypatch.setenv("HERMES_PROFILE_HOME", str(tmp_path))
    return tmp_path


def _use(monkeypatch, helper: FakeHelper) -> FakeHelper:
    monkeypatch.setattr(acl, "sqlsrv", helper)
    return helper


def _run(capsys, *argv: str) -> tuple[int, dict[str, Any]]:
    try:
        code = acl.main(list(argv))
    except SystemExit as exc:
        code = int(exc.code or 0)
    return code, json.loads(capsys.readouterr().out)


def _ace(kind: str, rights: str) -> dict[str, Any]:
    return {"identity": "DOMAIN\\person", "type": kind, "rights": rights, "inherited": True}


def test_allow_read_ace_authorizes(monkeypatch, capsys):
    _use(monkeypatch, FakeHelper({"ok": True, "authorized": True, "sam": "person", "errors": [], "matched_aces": [_ace("Allow", "ReadAndExecute, Synchronize")]}))
    code, payload = _run(capsys, "--requester-user-id", REQUESTER, "--path", SHARE)
    assert code == 0
    assert payload["authorized"] is True and payload["admin_bypass"] is False
    assert payload["windows_sam"] == "person" and payload["matched_ace_count"] == 1


@pytest.mark.parametrize("raw", [
    {"authorized": True, "errors": [], "matched_aces": [_ace("Allow", "Read"), _ace("Deny", "Read")]},
    {"authorized": True, "errors": ["AD mail lookup hit_count=0"], "matched_aces": [_ace("Allow", "Read")]},
    {"authorized": True, "errors": [], "matched_aces": [_ace("Allow", "Synchronize")]},
    {"authorized": False, "errors": [], "matched_aces": [_ace("Allow", "Read")]},
])
def test_any_doubt_is_a_refusal(monkeypatch, capsys, raw):
    _use(monkeypatch, FakeHelper(raw))
    _code, payload = _run(capsys, "--requester-user-id", REQUESTER, "--path", SHARE)
    assert payload["authorized"] is False and payload["error"]


@pytest.mark.parametrize("requester,path", [
    (REQUESTER, r"\\file-server\share\payroll\2026.xlsx"),
    (ADMIN, r"\\file-server\share\薪資\2026.xlsx"),
    ("unknown-id", SHARE),
    ("inactive-id", SHARE),
])
def test_refused_before_any_helper_call(monkeypatch, capsys, requester, path):
    helper = _use(monkeypatch, FakeHelper({"authorized": True, "errors": [], "matched_aces": [_ace("Allow", "Read")]}))
    code, payload = _run(capsys, "--requester-user-id", requester, "--path", path)
    assert code != 0 and payload["authorized"] is False
    assert helper.payloads == []


def test_unauthorized_read_never_reaches_the_file_helper(monkeypatch, capsys):
    helper = _use(monkeypatch, FakeHelper({"authorized": False, "errors": [], "matched_aces": []}))
    code, payload = _run(capsys, "--requester-user-id", REQUESTER, "--path", SHARE, "--action", "read")
    assert code != 0 and payload["authorized"] is False
    assert not any(p.startswith("read:") for p in helper.payloads)


def test_listing_withholds_red_line_entries(monkeypatch, capsys):
    listing = {"ok": True, "items": [{"full_name": SHARE + r"\plan.docx"}, {"full_name": SHARE + r"\bonus-2026.xlsx"}]}
    _use(monkeypatch, FakeHelper({"authorized": True, "errors": [], "matched_aces": [_ace("Allow", "Modify")]}, listing))
    code, payload = _run(capsys, "--requester-user-id", REQUESTER, "--path", SHARE, "--action", "list")
    assert code == 0
    assert [item["full_name"] for item in payload["items"]] == [SHARE + r"\plan.docx"]
    assert payload["red_line_items_withheld"] == 1 and payload["safety"]["writes_implemented"] is False


def test_admin_bypass_is_reported(monkeypatch, capsys):
    helper = _use(monkeypatch, FakeHelper({"authorized": False, "errors": [], "matched_aces": []}))
    code, payload = _run(capsys, "--requester-user-id", ADMIN, "--path", SHARE)
    assert code == 0 and payload["authorized"] is True and payload["admin_bypass"] is True
    assert helper.payloads == []


def test_unset_owner_username_never_makes_an_unnamed_user_an_admin(monkeypatch, capsys):
    """``PDONE_OWNER_MM_USERNAME`` unset is ``""``; a record without a username must not match it."""
    monkeypatch.delenv("PDONE_OWNER_MM_USERNAME", raising=False)
    helper = _use(monkeypatch, FakeHelper({"authorized": False, "errors": [], "matched_aces": []}))
    _code, payload = _run(capsys, "--requester-user-id", REQUESTER, "--path", SHARE)
    assert payload["authorized"] is False and payload["admin_bypass"] is False
    assert helper.payloads

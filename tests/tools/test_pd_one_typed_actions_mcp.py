"""Behaviour contracts for three typed safe-ops MCP actions (mocked HTTP)."""
from __future__ import annotations

import json
from typing import Any

import pytest

from tools.pd_one_ops import pd_one_appsheet_user_access_ops as user_access
from tools.pd_one_ops import pd_one_mattermost_channel_member_ops as member_ops
from tools.pd_one_ops import pd_one_mattermost_thread_move_ops as thread_ops
from tools.pd_one_ops import pd_one_safe_ops_mcp as mcp_commands
from tools.pd_one_ops.mcp_tools import iter_mcp_tools

ANDY_USER_ID = "5nak6m7nmf8kudbrwbtccazbgc"
ADMIN_CHANNEL = "5gmqtwqf7bde3cyihas79xi8ie"
POST_ID = "zyxwvutsrqponmlkjihgfedcba"
PERSON_ID = "person1234567890123456789012"
CHANNEL_ID = "abcdefghijklmnopqrstuvwxyz"
MOVE_POST_ID = "abcdefghijklmnopqrstuvwxyz"
TARGET_CHANNEL = "11111111111111111111111111"
ADMIN_REQUESTER = "adminrequester1234567890123"


class _FakeAppSheetClient:
  def __init__(self, hr_row: dict[str, Any], settings_row: dict[str, Any] | None) -> None:
    self.hr_row = dict(hr_row)
    self.settings_row = dict(settings_row) if settings_row else None
    self.writes: list[tuple[str, str, dict[str, Any]]] = []

  def find(self, table: str, selector: str) -> list[dict[str, Any]]:
    del selector
    if table == user_access.HR_TABLE:
      return [dict(self.hr_row)]
    if table == user_access.SETTINGS_TABLE:
      return [dict(self.settings_row)] if self.settings_row else []
    return []

  def add(self, table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
    self.writes.append(("add", table, dict(row)))
    if table == user_access.SETTINGS_TABLE:
      self.settings_row = dict(row)
    return [row]

  def edit(self, table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
    self.writes.append(("edit", table, dict(row)))
    if table == user_access.SETTINGS_TABLE:
      self.settings_row = dict(row)
    return [row]


def _andy_post(message: str) -> dict[str, Any]:
  return {
    "id": POST_ID,
    "user_id": ANDY_USER_ID,
    "channel_id": ADMIN_CHANNEL,
    "delete_at": 0,
    "message": message,
  }


def test_iter_mcp_tools_registers_all_three():
  names = {name for name, _fn in iter_mcp_tools()}
  for tool in (
    "pd_one_appsheet_user_access",
    "pd_one_mattermost_channel_member_add",
    "pd_one_mattermost_thread_move",
  ):
    assert tool in names
    assert callable(getattr(mcp_commands, tool))


def test_appsheet_user_access_denied_when_post_lacks_identity():
  client = _FakeAppSheetClient(
    {
      "PersonID": PERSON_ID,
      "Name_ZH": "王小明",
      "Company Email": "ming@prodesign-group.com",
      "Appsheet Email": "",
    },
    None,
  )
  payload = user_access.execute_appsheet_user_access(
    person_id=PERSON_ID,
    name_zh="王小明",
    email="ming@prodesign-group.com",
    notification_groups=["Team_SeniorStaff"],
    authorizing_post_id=POST_ID,
    dry_run=True,
    appsheet_client=client,
    post_fetcher=lambda _pid: _andy_post("unrelated approval text"),
  )
  assert payload["status"] == "denied"
  assert payload["execution"] is None
  assert client.writes == []


def test_appsheet_user_access_two_group_dry_run_plan():
  client = _FakeAppSheetClient(
    {
      "PersonID": PERSON_ID,
      "Name_ZH": "王小明",
      "Company Email": "ming@prodesign-group.com",
      "Appsheet Email": "",
    },
    None,
  )
  payload = user_access.execute_appsheet_user_access(
    person_id=PERSON_ID,
    name_zh="王小明",
    email="ming@prodesign-group.com",
    notification_groups=["Team_SeniorStaff", "Team_Molding_Staff"],
    authorizing_post_id=POST_ID,
    dry_run=True,
    appsheet_client=client,
    post_fetcher=lambda _pid: _andy_post("請為王小明開通 Appsheet ming@prodesign-group.com"),
  )
  assert payload["status"] == "ok"
  assert payload["dry_run"] is True
  plan = payload["plan"]
  assert plan["notification_groups"] == ["Team_SeniorStaff", "Team_Molding_Staff"]
  assert plan["planned_settings_row"]["Appsheet Notification Group"] == (
    "Team_SeniorStaff, Team_Molding_Staff"
  )
  assert plan["settings_action"] == "add"
  assert client.writes == []


def test_mattermost_channel_member_add_readback(monkeypatch):
  base = "https://mm.example"
  headers = {"Authorization": "Bearer x"}
  user_id = "mmuserid12345678901234567"

  def fake_policy(_requester: str) -> dict[str, Any]:
    return {"found": True, "active": True, "roles": ["admin"]}

  calls: list[tuple[str, str]] = []
  member_reads = 0

  def fake_http(method, b, h, path, **kwargs):
    nonlocal member_reads
    del b, h, kwargs
    calls.append((method, path))
    if path == "/api/v4/users/username/andy.lin":
      return 200, {"id": user_id, "username": "andy.lin", "delete_at": 0}
    if path == f"/api/v4/channels/{CHANNEL_ID}/members":
      if method == "POST":
        return 201, {}
    if path == f"/api/v4/channels/{CHANNEL_ID}/members/{user_id}":
      if method == "GET":
        member_reads += 1
        if member_reads == 1:
          return 404, {}
        return 200, {"user_id": user_id, "channel_id": CHANNEL_ID, "roles": "channel_user"}
    raise AssertionError(f"unexpected {method} {path}")

  payload = member_ops.execute_channel_member_add(
    channel_id=CHANNEL_ID,
    username="@andy.lin",
    requester_id=ADMIN_REQUESTER,
    confirm=member_ops.CONFIRMATION,
    http_call=fake_http,
    mattermost_context=lambda: (base, headers, {}),
    policy_loader=fake_policy,
  )
  assert payload["already_member"] is False
  assert payload["username"] == "andy.lin"
  assert payload["readback"]["user_id"] == user_id
  assert calls[0] == ("GET", "/api/v4/users/username/andy.lin")
  assert ("POST", f"/api/v4/channels/{CHANNEL_ID}/members") in calls
  assert member_reads == 2


def test_mattermost_thread_move_501(monkeypatch):
  base = "https://mm.example"
  headers = {"Authorization": "Bearer x"}

  def fake_policy(_requester: str) -> dict[str, Any]:
    return {"found": True, "active": True, "roles": ["it_support_operator"]}

  def fake_http(method, b, h, path, **kwargs):
    del b, h, kwargs
    assert method == "POST"
    assert path == f"/api/v4/posts/{MOVE_POST_ID}/move"
    return 501, {"message": "not implemented"}

  payload = thread_ops.execute_thread_move(
    post_id=MOVE_POST_ID,
    channel_id=TARGET_CHANNEL,
    requester_id=ADMIN_REQUESTER,
    confirm=thread_ops.CONFIRMATION,
    http_call=fake_http,
    mattermost_context=lambda: (base, headers, {}),
    policy_loader=fake_policy,
  )
  assert payload["status"] == "error"
  assert payload["error"] == "move_not_implemented"
  assert payload["http_status"] == 501
"""HRS AppSheet reads drop private columns; the private lookup is destination-gated."""
import json
from pathlib import Path

import pytest

from gateway.session_context import clear_session_vars, set_session_vars
from tools.registry import registry

import tools.pd_one_safe_ops as ops

SAFE = {
    "姓名": "Placeholder Person",
    "部門": "Placeholder Dept",
    "到職日": "2000-01-01",
    "email": "placeholder@example.com",
}
DENIED = {
    "職等代碼": "G0-PLACEHOLDER",
    "職級代碼": "R0-PLACEHOLDER",
    "身份類別名稱": "CAT-PLACEHOLDER",
    "直間接別": "DIR-PLACEHOLDER",
    "勞退舊制年資結清": "Y-PLACEHOLDER",
    "工作年資起算日": "2000-01-02",
    "退休年資起算日": "2000-01-03",
    "passport": "P-PLACEHOLDER",
    "護照號碼": "PP-PLACEHOLDER",
    "入出境紀錄": "EE-PLACEHOLDER",
    "entry/exit": "EX-PLACEHOLDER",
    "residence_permit_no": "RP-PLACEHOLDER",
    "_RowNumber": "ROW-PLACEHOLDER",
    "Grade": "G1-PLACEHOLDER",
    "薪資": "S-PLACEHOLDER",
    "級距": "B-PLACEHOLDER",
    "job_level": "L-PLACEHOLDER",
    "rank_code": "RK-PLACEHOLDER",
    "comp_band": "C-PLACEHOLDER",
    "wage_code": "W-PLACEHOLDER",
    "SalaryBand": "SB-PLACEHOLDER",
}
ROW = {**SAFE, **DENIED}
SECRET_VALUES = list(DENIED.values())


@pytest.fixture(autouse=True)
def _reset_session():
    clear_session_vars([])
    yield
    clear_session_vars([])


def _policy_dir(tmp_path: Path) -> Path:
    cache = tmp_path / "policies"
    cache.mkdir()
    for user_id, roles in (
        ("user-hr-1", ["hr"]),
        ("user-admin-3", ["admin"]),
        ("user-staff-2", ["employee"]),
    ):
        (cache / f"{user_id}.json").write_text(
            json.dumps({"found": True, "active": True, "roles": roles}),
            encoding="utf-8",
        )
    return cache


def _assert_private_absent(payload: dict) -> None:
    encoded = json.dumps(payload, ensure_ascii=False)
    for key, value in DENIED.items():
        assert key not in encoded
        assert value not in encoded
    assert payload["withheld_fields"] == len(DENIED)


@pytest.mark.parametrize("table", ["HRS_Data", "HRS_Data_MasterNames"])
def test_table_probe_never_returns_denied_columns(table):
    payload = ops.cmd_appsheet_table_probe(table, rows=[ROW])
    _assert_private_absent(payload)
    assert payload["rows"] == [SAFE]


def test_row_get_uses_the_same_denylist():
    payload = ops.cmd_appsheet_row_get("HRS_Data", row=dict(ROW))
    encoded = json.dumps(payload, ensure_ascii=False)
    for value in SECRET_VALUES:
        assert value not in encoded
    assert payload["row"]["姓名"] == "Placeholder Person"
    assert payload["withheld_fields"] == len(DENIED)


def test_non_hrs_table_is_not_rewritten():
    payload = ops.cmd_appsheet_table_probe("Equipment", rows=[{"Grade": "keep-me", "name": "press"}])
    assert payload["rows"] == [{"Grade": "keep-me", "name": "press"}]
    assert payload["withheld_fields"] == 0


def test_registered_probe_strips_fetched_rows(monkeypatch):
    monkeypatch.setattr(ops, "fetch_appsheet_rows", lambda table, query="": [dict(ROW)])
    raw = registry.dispatch("pd_one_appsheet_table_probe", {"table": "HRS_Data", "include_private": True})
    for value in SECRET_VALUES:
        assert value not in raw
    payload = json.loads(raw)
    assert payload["rows"][0]["email"] == "placeholder@example.com"
    assert payload["withheld_fields"] == len(DENIED)


def test_private_lookup_schema_has_no_destination_argument():
    props = registry.get_schema("pd_one_hr_private_lookup")["parameters"]["properties"]
    for banned in ("channel_id", "chat_id", "user_id", "destination", "members", "roles", "hr_only"):
        assert banned not in props


def test_env_spoof_cannot_authorize_private_lookup(monkeypatch, tmp_path):
    cache = _policy_dir(tmp_path)
    monkeypatch.setattr(ops, "policy_cache_directory", lambda: str(cache))
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "mattermost")
    monkeypatch.setenv("HERMES_SESSION_CHAT_TYPE", "dm")
    monkeypatch.setenv("HERMES_SESSION_CHAT_ID", "dm-hr")
    monkeypatch.setenv("HERMES_SESSION_USER_ID", "user-hr-1")

    def _boom(*_args, **_kwargs):
        raise AssertionError("private rows must not be fetched")

    monkeypatch.setattr(ops, "fetch_appsheet_rows", _boom)
    raw = registry.dispatch(
        "pd_one_hr_private_lookup",
        {"table": "HRS_Data", "channel_id": "channel-hr", "hr_only": True, "roles": ["admin"]},
    )
    assert "G0-PLACEHOLDER" not in raw
    assert json.loads(raw)["error"]


@pytest.mark.parametrize(
    ("chat_type", "chat_id", "user_id", "members", "allowed"),
    [
        ("dm", "dm-hr", "user-hr-1", None, True),
        ("dm", "dm-staff", "user-staff-2", None, False),
        ("channel", "channel-hr", "user-hr-1", ["user-hr-1", "user-admin-3"], True),
        ("channel", "channel-mixed", "user-staff-2", ["user-hr-1", "user-staff-2"], False),
    ],
)
def test_private_lookup_follows_session_destination(monkeypatch, tmp_path, chat_type, chat_id, user_id, members, allowed):
    cache = _policy_dir(tmp_path)
    monkeypatch.setattr(ops, "policy_cache_directory", lambda: str(cache))
    if members is not None:
        monkeypatch.setattr(ops, "resolve_channel_member_ids", lambda _chat_id: list(members))
    monkeypatch.setattr(ops, "fetch_appsheet_rows", lambda table, query="": [dict(ROW)])
    set_session_vars(
        platform="mattermost",
        chat_id=chat_id,
        chat_type=chat_type,
        user_id=user_id,
    )
    raw = registry.dispatch(
        "pd_one_hr_private_lookup",
        {
            "table": "HRS_Data",
            "query": "placeholder-employee",
            "channel_id": "channel-hr",
            "user_id": "user-hr-1",
            "hr_only": True,
        },
    )
    if allowed:
        assert "G0-PLACEHOLDER" in raw
        assert "P-PLACEHOLDER" in raw
        assert json.loads(raw)["rows"][0]["職等代碼"] == "G0-PLACEHOLDER"
    else:
        assert "G0-PLACEHOLDER" not in raw
        assert "P-PLACEHOLDER" not in raw
        assert json.loads(raw)["error"]

"""The MCP-exposed AppSheet probe withholds HRS private columns.

The pdone profile's copy of pd_one_safe_ops returns those columns. The MCP
server has to call the repo module even when that copy is importable.
Profile-only commands stay callable, and HRS rows in their results are
withheld the same way.
"""
import json
import os
import sys
from pathlib import Path

import pytest

import tools.pd_one_safe_ops as ops
import tools.pd_one_safe_ops_mcp as mcp
from tests.tools.test_pd_one_hr_private import DENIED, ROW, SECRET_VALUES

_PROFILE_SOURCE = """
import json

def pd_one_appsheet_table_probe(table, query="", **kwargs):
    return {"table": table, "rows": [{"職等代碼": "LEAK-FROM-PROFILE"}], "withheld_fields": 0}

def pd_one_hr_private_lookup(query):
    return {"table": "HRS_Data", "row": {"職等代碼": "LEAK-FROM-PROFILE"}}

def pd_one_sheets_get_range(spreadsheet_id, range_name):
    \"\"\"Read a sheet range.\"\"\"
    return {
        "table": "HRS_Data",
        "Rows": [{"職等代碼": "G0-PLACEHOLDER", "姓名": "ok"}],
    }

def pd_one_google_group_members(group):
    return {"table": "Projects", "rows": [{"職等代碼": "G0-PLACEHOLDER", "name": "team"}]}

def call_function_twin(name, arguments):
    return json.dumps({"table": "HRS_Data", "rows": [{"護照號碼": "P0-PLACEHOLDER", "姓名": "ok"}]})
"""


@pytest.fixture(autouse=True)
def _filtered_rows(monkeypatch):
    monkeypatch.setattr(ops, "fetch_appsheet_rows", lambda table, query="": [dict(ROW)])


@pytest.mark.parametrize("table", ["HRS_Data", "HRS_Data_MasterNames"])
def test_mcp_probe_withholds_private_columns(table):
    payload = mcp.call_mcp_tool("pd_one_appsheet_table_probe", {"table": table, "include_private": True})
    encoded = json.dumps(payload, ensure_ascii=False)
    for key, value in DENIED.items():
        assert key not in encoded
        assert value not in encoded
    assert payload["rows"] == [{key: value for key, value in ROW.items() if key not in DENIED}]
    assert payload["withheld_fields"] == len(DENIED)
    for value in SECRET_VALUES:
        assert value not in encoded


def test_mcp_row_get_withholds_the_same_columns():
    payload = mcp.call_mcp_tool("pd_one_appsheet_row_get", {"table": "HRS_Data"})
    encoded = json.dumps(payload, ensure_ascii=False)
    for value in SECRET_VALUES:
        assert value not in encoded
    assert payload["row"]["姓名"] == "Placeholder Person"
    assert payload["withheld_fields"] == len(DENIED)


def test_mcp_probe_ignores_a_profile_local_unfiltered_module(monkeypatch, tmp_path):
    """A profile copy named pd_one_safe_ops.py must not be the MCP implementation."""
    profile_tools = tmp_path / "tools"
    profile_tools.mkdir()
    (profile_tools / "pd_one_safe_ops.py").write_text(
        "def cmd_appsheet_table_probe(table, query='', **kwargs):\n"
        "    return {'table': table, 'rows': [{'職等代碼': 'G0-PLACEHOLDER'}], 'withheld_fields': 0}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(profile_tools))
    sys.modules.pop("pd_one_safe_ops", None)
    import importlib
    shadow = importlib.import_module("pd_one_safe_ops")
    leaked = shadow.cmd_appsheet_table_probe("HRS_Data")
    assert leaked["rows"][0]["職等代碼"] == "G0-PLACEHOLDER"

    payload = mcp.call_mcp_tool("pd_one_appsheet_table_probe", {"table": "HRS_Data"})
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "G0-PLACEHOLDER" not in encoded
    assert "職等代碼" not in encoded
    assert payload["withheld_fields"] == len(DENIED)


def test_unfiltered_module_fails_the_startup_check():
    class _Leaky:
        @staticmethod
        def cmd_appsheet_table_probe(table, query="", **kwargs):
            return {"table": table, "rows": [{"職等代碼": mcp._FILTER_SENTINEL}]}

    with pytest.raises(RuntimeError, match="still returns HRS private columns"):
        mcp.assert_filtered_implementation(_Leaky())


def test_repo_module_passes_the_startup_check():
    mcp.assert_filtered_implementation(ops)


def test_mcp_second_gate_strips_a_ported_command_that_skipped_the_filter():
    payload = mcp.ensure_hrs_redacted(
        "HRS_Data",
        {"table": "HRS_Data", "rows": [dict(ROW)], "withheld_fields": 0},
    )
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "G0-PLACEHOLDER" not in encoded
    assert payload["rows"][0]["email"] == "placeholder@example.com"
    assert payload["withheld_fields"] == len(DENIED)


def test_second_gate_leaves_an_already_clean_payload_unchanged():
    original = {"table": "HRS_Data", "rows": [{"姓名": "ok"}], "withheld_fields": 3}
    assert mcp.ensure_hrs_redacted("HRS_Data", original) is original


def _write_profile_module(source: str) -> None:
    tools = Path(os.environ["HERMES_HOME"]) / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "pd_one_safe_ops.py").write_text(source, encoding="utf-8")


def test_profile_only_command_withholds_private_hrs_columns():
    _write_profile_module(_PROFILE_SOURCE)
    payload = mcp.call_mcp_tool(
        "pd_one_sheets_get_range",
        {"spreadsheet_id": "sheet", "range_name": "A1"},
    )
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "職等代碼" not in encoded
    assert "G0-PLACEHOLDER" not in encoded
    assert payload["Rows"][0]["姓名"] == "ok"
    assert payload["withheld_fields"] == 1


def test_profile_command_on_a_non_hrs_table_passes_through():
    _write_profile_module(_PROFILE_SOURCE)
    payload = mcp.call_mcp_tool("pd_one_google_group_members", {"group": "team"})
    assert payload["rows"][0]["職等代碼"] == "G0-PLACEHOLDER"
    assert "withheld_fields" not in payload


def test_profile_probe_is_not_the_mcp_probe():
    _write_profile_module(_PROFILE_SOURCE)
    payload = mcp.call_mcp_tool("pd_one_appsheet_table_probe", {"table": "HRS_Data"})
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "LEAK-FROM-PROFILE" not in encoded
    assert "職等代碼" not in encoded
    assert payload["withheld_fields"] == len(DENIED)
    names = mcp.profile_command_handlers()
    assert "pd_one_appsheet_table_probe" not in names
    assert "pd_one_hr_private_lookup" not in names
    assert "pd_one_sheets_get_range" in names


def test_profile_private_lookup_is_not_exposed():
    _write_profile_module(_PROFILE_SOURCE)
    payload = mcp.call_mcp_tool("pd_one_hr_private_lookup", {"query": "someone"})
    assert payload == {"ok": False, "error": "unknown safe-ops command"}


def test_call_function_twin_hrs_json_is_redacted():
    _write_profile_module(_PROFILE_SOURCE)
    payload = mcp.call_mcp_tool("call_function_twin", {"name": "probe", "arguments": {}})
    decoded = json.loads(payload)
    encoded = json.dumps(decoded, ensure_ascii=False)
    assert "護照號碼" not in encoded
    assert "P0-PLACEHOLDER" not in encoded
    assert decoded["rows"][0]["姓名"] == "ok"


def test_missing_profile_module_leaves_the_probe_working():
    payload = mcp.call_mcp_tool("pd_one_appsheet_table_probe", {"table": "HRS_Data"})
    assert payload["withheld_fields"] == len(DENIED)
    unknown = mcp.call_mcp_tool("pd_one_sheets_get_range", {})
    assert unknown == {"ok": False, "error": "unknown safe-ops command"}


def test_profile_tool_keeps_its_signature_and_filters():
    _write_profile_module(_PROFILE_SOURCE)
    fn = mcp.profile_command_handlers()["pd_one_sheets_get_range"]

    class _Server:
        def add_tool(self, tool, name, description, structured_output):
            self.tool = tool
            self.name = name
            self.description = description
            self.structured_output = structured_output

    server = _Server()
    mcp._register_profile(server, "pd_one_sheets_get_range", fn)
    import inspect
    assert list(inspect.signature(server.tool).parameters) == ["spreadsheet_id", "range_name"]
    assert server.description == "Read a sheet range."
    result = server.tool(spreadsheet_id="sheet", range_name="A1")
    assert "職等代碼" not in json.dumps(result, ensure_ascii=False)
    assert result["Rows"][0]["姓名"] == "ok"

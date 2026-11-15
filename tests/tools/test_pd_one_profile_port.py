"""Release safe-ops: CLI/MCP names, pd_one config, and HR-employee filtering."""
import json
import os
from pathlib import Path

import pytest

import tools.pd_one_safe_ops as ops
import tools.pd_one_safe_ops_mcp as mcp
from tools.pd_one_hr_fields import column_is_private
from tools.pd_one_ops._catalog import CLI_SUBCOMMANDS, MCP_TOOLS
from tools.pd_one_ops.hr_guard import guard_hr_payload
from tools.pd_one_ops.site_config import external_path, profile_tools_enabled, site_text


def _write_config(text: str) -> None:
    home = Path(os.environ["HERMES_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(text, encoding="utf-8")


def test_cli_subcommands_match_the_catalog():
    import argparse

    from tools.pd_one_ops.cli import build_parser

    parser = build_parser()
    action = next(
        item for item in parser._actions if isinstance(item, argparse._SubParsersAction)
    )
    assert set(action.choices) == set(CLI_SUBCOMMANDS)
    assert len(CLI_SUBCOMMANDS) == len(set(CLI_SUBCOMMANDS))


def test_mcp_tool_names_match_the_catalog():
    handlers = ops.mcp_read_handlers()
    missing = [name for name in MCP_TOOLS if name not in handlers]
    assert missing == []
    assert all(callable(handlers[name]) for name in MCP_TOOLS)
    assert "pd_one_appsheet_row_get" in handlers
    assert handlers["pd_one_appsheet_table_probe"] is ops.merged_appsheet_table_probe
    assert "pd_one_hr_private_lookup" not in handlers
    assert len(MCP_TOOLS) == len(set(MCP_TOOLS))


def test_text_metrics_cli_runs(capsys):
    from tools.pd_one_ops.cli import main

    assert main(["text-metrics", "--text", "hi"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["characters_including_punctuation"] == 2
    assert payload["safety"]["text_returned"] is False


def test_pd_one_config_loads_at_call_time(monkeypatch):
    _write_config(
        "\n".join([
            "pd_one:",
            "  load_profile_tools: false",
            "  owner_display_name: Owner",
            "  channels:",
            "    admin_alert: channel-placeholder",
            "  emails:",
            "    admin: placeholder@example.com",
            "  external:",
            "    sqlsrv_readonly: /tmp/pd-one-missing-sqlsrv.py",
        ]) + "\n"
    )
    monkeypatch.delenv("PDONE_ADMIN_ALERT_CHANNEL_ID", raising=False)
    monkeypatch.setenv("PDONE_OWNER_NAME_EN", "Placeholder Owner")
    assert site_text("PDONE_ADMIN_ALERT_CHANNEL_ID") == "channel-placeholder"
    assert site_text("PDONE_EMAIL_ADMIN") == "placeholder@example.com"
    assert site_text("PDONE_OWNER_NAME_EN") == "Placeholder Owner"
    assert profile_tools_enabled() is False
    assert external_path("sqlsrv_readonly").exists() is False
    with pytest.raises(FileNotFoundError, match=r"pd_one\.external\.sqlsrv_readonly"):
        external_path("sqlsrv_readonly").require()


def test_hr_employee_rows_drop_private_columns():
    payload = {
        "table": "HR_Employees",
        "capability": "pd_one_appsheet_hr_employee_patch",
        "rows": [{
            "職等代碼": "G0-PLACEHOLDER",
            "護照號碼": "P0-PLACEHOLDER",
            "Name_ZH": "ok",
        }],
    }
    cleaned = guard_hr_payload(payload, tool_name="pd_one_appsheet_hr_employee_patch")
    encoded = json.dumps(cleaned, ensure_ascii=False)
    assert "職等代碼" not in encoded
    assert "護照號碼" not in encoded
    assert "G0-PLACEHOLDER" not in encoded
    assert cleaned["rows"][0]["Name_ZH"] == "ok"
    assert column_is_private("職等代碼")
    assert column_is_private("護照號碼")


def test_hr_twin_rows_drop_private_columns():
    payload = {"rows": [{"護照號碼": "P0-PLACEHOLDER", "姓名": "ok"}]}
    cleaned = guard_hr_payload(
        payload, tool_name="call_function_twin", arguments={"twin": "hr"},
    )
    encoded = json.dumps(cleaned, ensure_ascii=False)
    assert "護照號碼" not in encoded
    assert cleaned["rows"][0]["姓名"] == "ok"


def test_hr_policy_prose_is_left_intact():
    text = "The policy mentions 護照號碼 as a column name in prose."
    assert guard_hr_payload(text, tool_name="pd_one_hr_policy_lookup") is text


def test_mcp_hr_employee_patch_drops_private_columns(monkeypatch):
    def _rows(person_id, updates, dry_run=True, env="deployed", expected_name_zh=None,
              expected_company_email=None, confirm_live_write=None):
        del person_id, updates, dry_run, env
        del expected_name_zh, expected_company_email, confirm_live_write
        return json.dumps({
            "capability": "pd_one_appsheet_hr_employee_patch",
            "table": "HR_Employees",
            "rows": [{
                "職等代碼": "G0-PLACEHOLDER",
                "護照號碼": "P0-PLACEHOLDER",
                "Name_ZH": "ok",
            }],
        }, ensure_ascii=False)

    monkeypatch.setattr(
        "tools.pd_one_ops.pd_one_safe_ops_mcp.pd_one_appsheet_hr_employee_patch",
        _rows,
    )
    payload = mcp.call_mcp_tool(
        "pd_one_appsheet_hr_employee_patch",
        {"person_id": "person-placeholder", "updates": {}},
    )
    if isinstance(payload, str):
        encoded = payload
    else:
        encoded = json.dumps(payload, ensure_ascii=False)
    assert "職等代碼" not in encoded
    assert "護照號碼" not in encoded
    assert "ok" in encoded

"""Zero-tool PD One reviewer path.

Regression for the interaction-review v2 shadow job: ``cli.main`` with
``toolsets=bot_room`` still exposed MCP ``list_prompts`` / ``list_resources``,
the model spent its only turn on those tools, CLI exited 1 via SystemExit, and
``invoke_reviewer`` hid stdout behind a Bitwarden banner.
"""
from __future__ import annotations

from io import StringIO

import pytest

from scripts.pd_one_interaction_review_v2 import (
    combined_reviewer_tail,
    invoke_reviewer,
    review_once,
    strip_reviewer_noise,
)
from scripts.pd_one_review_model_runner import (
    REVIEWER_TOOLSETS,
    invoke_cli_main,
    parse_reviewer_json_array,
    print_reviewer_status,
    result_tool_turns,
    run_reviewer,
)


def _json_array_turn(_prompt: str) -> dict:
    return {
        "final_response": '[{"review_log_id": "r1", "status": "ok"}]',
        "turn_exit_reason": "completed",
        "tool_turns": 0,
        "failed": False,
        "exit_code": 0,
    }


def test_reviewer_toolsets_are_bot_room_without_mcp() -> None:
    assert "bot_room" in REVIEWER_TOOLSETS.split(",")
    assert "no_mcp" in REVIEWER_TOOLSETS.split(",")


def test_bot_room_selection_excludes_mcp_utility_tools() -> None:
    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import _select_tool_names

    enabled = _get_platform_tools(
        {
            "platform_toolsets": {"cli": ["bot_room"]},
            "mcp_servers": {"survey_passcodes": {"url": "https://example.invalid/mcp"}},
        },
        "cli",
    )
    names = _select_tool_names(list(enabled), None, quiet_mode=True)
    assert "survey_passcodes" not in enabled
    assert "mcp-survey_passcodes" not in enabled
    assert not any(str(name).startswith("mcp__survey_passcodes__") for name in names)


def test_invoke_cli_main_catches_system_exit() -> None:
    from hermes_cli.mcp_startup import set_mcp_server_filter

    seen = {}

    def fake_cli_main(**kwargs):
        seen.update(kwargs)
        raise SystemExit(1)

    try:
        result = invoke_cli_main("review these rows", cli_main=fake_cli_main)
    finally:
        set_mcp_server_filter(None)
    assert result["exit_code"] == 1
    assert seen["toolsets"] == REVIEWER_TOOLSETS
    assert seen["max_turns"] == 1
    assert seen["oneshot"] is True


def test_print_reviewer_status_includes_end_reason_and_response_len() -> None:
    buf = StringIO()
    print_reviewer_status(
        {
            "turn_exit_reason": "max_iterations_reached(1/1)",
            "final_response": "x" * 12,
            "tool_turns": 1,
        },
        stream=buf,
    )
    line = buf.getvalue()
    assert "end_reason=max_iterations_reached(1/1)" in line
    assert "response_len=12" in line
    assert "tool_turns=1" in line


def test_strip_reviewer_noise_drops_bitwarden_banner() -> None:
    raw = (
        "  Bitwarden Secrets Manager: applied 4 secrets\n"
        "session_id: local-8e731534cef9d09603088b2ee6cad3ca\n"
        "end_reason=max_iterations_reached(1/1) response_len=1373 tool_turns=1\n"
    )
    cleaned = strip_reviewer_noise(raw)
    assert "Bitwarden" not in cleaned
    assert "session_id" not in cleaned
    assert "end_reason=max_iterations_reached(1/1)" in cleaned


def test_invoke_reviewer_logs_stdout_tail_with_stderr() -> None:
    """The live bug used ``stderr or stdout``, so a Bitwarden banner hid the model reply."""
    stderr = "  Bitwarden Secrets Manager: applied 4 secrets\nsession_id: local-abc\n"
    stdout = '[{"status":"ok"}]'
    tail = combined_reviewer_tail(stdout, stderr)
    assert "Bitwarden" not in tail
    assert "session_id" not in tail
    assert '[{"status":"ok"}]' in tail

    def failing_turn(_prompt: str) -> dict:
        return {
            "final_response": '[{"status":"ok"}]',
            "turn_exit_reason": "max_iterations_reached(1/1)",
            "tool_turns": 1,
            "failed": True,
            "exit_code": 1,
        }

    with pytest.raises(RuntimeError, match="reviewer failed rc=1:") as caught:
        invoke_reviewer("prompt", run_turn=failing_turn)
    message = str(caught.value)
    assert "Bitwarden" not in message
    assert '[{"status":"ok"}]' in message


def test_bot_room_reviewer_path_finishes_without_tools_and_returns_json_array() -> None:
    rows = review_once("You are PD Neo acting as an isolated quality auditor", run_turn=_json_array_turn)
    assert rows == [{"review_log_id": "r1", "status": "ok"}]
    result = run_reviewer("prompt", run_turn=_json_array_turn)
    assert result_tool_turns(result) == 0
    assert parse_reviewer_json_array(result["final_response"]) == rows

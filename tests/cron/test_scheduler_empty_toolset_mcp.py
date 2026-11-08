"""Empty native toolsets must not grow into every enabled MCP server.

``bot_room`` is a verified text-only toolset (zero tools). Callers pick it
intending no tools; default MCP merge used to inject ``list_prompts`` /
``list_resources``. An explicit empty per-job list is the same zero-tool
allowlist (#82010).
"""
from __future__ import annotations

from cron.scheduler import _merge_mcp_into_per_job_toolsets


CFG = {
    "mcp_servers": {
        "finnhub": {"enabled": True},
        "playwright": {"enabled": True},
        "disabled_one": {"enabled": False},
        "string_enabled": {"enabled": "true"},
        "not_a_dict": "ignored",
    }
}


def _enabled_names() -> set[str]:
    return {"finnhub", "playwright", "string_enabled"}


def test_empty_bot_room_toolset_does_not_inject_mcp_servers() -> None:
    result = _merge_mcp_into_per_job_toolsets(["bot_room"], CFG)
    assert result == ["bot_room"]
    assert not (set(result) & _enabled_names())


def test_explicit_empty_list_does_not_inject_mcp_servers() -> None:
    result = _merge_mcp_into_per_job_toolsets([], CFG)
    assert result == []

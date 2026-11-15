"""The dedicated worker-scheduling MCP server exposes one tool.

mcp 2.0.0 (the dev pin) builds the real server. The tool forwards to the
release dispatcher and turns a dispatch exception into a JSON error. Importing
the module does not touch a profiles path.
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import tools.pd_one_worker_scheduling_mcp as scheduling


_INSTRUCTIONS = (
    "Dedicated long-timeout PD One monthly worker scheduling tools. "
    "Use this server instead of pdone_safe_ops for scheduling playbook actions."
)
_ACTIONS = (
    "audit_rest_requests",
    "correct_raw_request_dates",
    "source_setup",
    "setup_scheduling_rules",
    "sync_source_rollover",
    "preflight",
    "solve_preview",
    "poll_solve_preview",
    "write_generated_schedule_from_report",
    "closeout_processed_requests",
    "review_im_scheduling",
)


def _text(result) -> str:
    blocks = [block.text for block in result.content if getattr(block, "type", None) == "text"]
    assert len(blocks) == 1
    return blocks[0]


def _property(schema: dict, name: str) -> dict:
    prop = schema["properties"][name]
    return {key: value for key, value in prop.items() if key != "title"}


def test_build_server_succeeds(require_mcp_2_sdk):
    server = scheduling.build_server()
    assert server.name == "pdone_worker_scheduling"
    assert server.instructions == _INSTRUCTIONS


def test_list_tools_is_worker_scheduling_only(require_mcp_2_sdk):
    server = scheduling.build_server()
    tools = asyncio.run(server.list_tools())
    assert [tool.name for tool in tools] == ["worker_scheduling"]
    tool = tools[0]
    schema = tool.input_schema
    assert schema["type"] == "object"
    assert schema["required"] == ["action"]
    assert set(schema["properties"]) == {
        "action",
        "payload",
        "dry_run",
        "timeout_seconds",
        "output_dir",
        "confirm_live_write",
    }
    for name in schema["properties"]:
        assert name.isidentifier()
        assert not name.startswith("_")
    assert _property(schema, "action") == {"type": "string"}
    assert _property(schema, "payload") == {
        "anyOf": [
            {"additionalProperties": True, "type": "object"},
            {"type": "null"},
        ],
        "default": None,
    }
    assert _property(schema, "dry_run") == {"default": True, "type": "boolean"}
    assert _property(schema, "timeout_seconds") == {"default": 420, "type": "integer"}
    assert _property(schema, "output_dir") == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
    }
    assert _property(schema, "confirm_live_write") == {
        "anyOf": [{"type": "string"}, {"type": "boolean"}, {"type": "null"}],
        "default": None,
    }
    for action in _ACTIONS:
        assert action in tool.description
    assert "following_month_required_rest_days_count" in tool.description
    assert "confirm_live_write='RUN LIVE WORKER SCHEDULING SOURCE WRITE'" in tool.description
    assert "confirm_live_write=true" in tool.description


def test_tool_call_forwards_arguments(require_mcp_2_sdk, monkeypatch):
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return json.dumps({"status": "ok", "action": kwargs["action"]})

    monkeypatch.setattr(
        "tools.pd_one_ops.pd_one_safe_ops_mcp.worker_scheduling",
        fake,
    )
    server = scheduling.build_server()
    arguments = {
        "action": "solve_preview",
        "payload": {"following_month_required_rest_days_count": 4},
        "dry_run": False,
        "timeout_seconds": 90,
        "output_dir": "/path/to/output",
        "confirm_live_write": True,
    }
    result = asyncio.run(server.call_tool("worker_scheduling", arguments))
    assert result.is_error is False
    assert json.loads(_text(result)) == {"status": "ok", "action": "solve_preview"}
    assert seen == arguments

    seen.clear()
    result = asyncio.run(server.call_tool("worker_scheduling", {"action": "preflight"}))
    assert json.loads(_text(result))["action"] == "preflight"
    assert seen == {
        "action": "preflight",
        "payload": None,
        "dry_run": True,
        "timeout_seconds": 420,
        "output_dir": None,
        "confirm_live_write": None,
    }


def test_dispatch_exception_returns_error_json(require_mcp_2_sdk, monkeypatch):
    def fake(**kwargs):
        raise RuntimeError("backend down")

    monkeypatch.setattr(
        "tools.pd_one_ops.pd_one_safe_ops_mcp.worker_scheduling",
        fake,
    )
    server = scheduling.build_server()
    result = asyncio.run(server.call_tool("worker_scheduling", {"action": "preflight"}))
    assert result.is_error is False
    assert json.loads(_text(result)) == {
        "status": "error",
        "error": "worker_scheduling_dispatch_failed",
        "detail": "backend down",
        "safety": {
            "shell_used": False,
            "server": "pdone_worker_scheduling",
        },
    }


def test_import_touches_no_profiles_path():
    """A fresh interpreter import must not stat or list a profiles directory."""
    root = Path(__file__).resolve().parents[2]
    script = r"""
import json
import sys
from pathlib import Path

hits = []

def consider(value):
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeError:
            return
    if not isinstance(value, str) or not value:
        return
    if "profiles" in Path(value).parts:
        hits.append(value)

def hook(event, args):
    for arg in args:
        if isinstance(arg, (str, bytes)):
            consider(arg)

sys.addaudithook(hook)
import tools.pd_one_worker_scheduling_mcp
for entry in sys.path:
    consider(entry)
for module in list(sys.modules.values()):
    consider(getattr(module, "__file__", None))
print(json.dumps({"hits": hits}))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["hits"] == []

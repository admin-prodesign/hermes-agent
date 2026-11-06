"""Regression: cron's script cwd is not the repository package root.

Land at tests/scripts/test_pd_one_queue_router_cron_import.py.
The outer launch matches the scheduled managed-Python -c bootstrap repo script form.
Only the production command-building functions are copied into the fixture shim;
queue, locks and delivery are replaced. Real router children run --help, never
send/flush, and inherit no PYTHONPATH.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys


def test_router_children_import_from_scheduled_script_cwd(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    source = (repo / "scripts/pd_one_failure_alert_queue_worker.py").read_text()
    runner_tree = ast.parse((repo / "cron/scheduler_script.py").read_text())
    bootstrap = next(ast.literal_eval(node.value) for node in runner_tree.body
                     if isinstance(node, ast.Assign) and any(
                         isinstance(target, ast.Name) and target.id == "_POSIX_SCRIPT_BOOTSTRAP"
                         for target in node.targets
                     ))
    names = {"_router_base_cmd", "deliver_route_notification", "main"}
    functions = [node for node in ast.parse(source).body
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in functions} == names
    functions_source = ast.unparse(ast.Module(body=functions, type_ignores=[]))

    router_tree = ast.parse((repo / "scripts/pd_one_notification_router.py").read_text())
    router_main = next(node for node in router_tree.body
                       if isinstance(node, ast.FunctionDef) and node.name == "main")
    parser_nodes = []
    for node in router_main.body:
        parser_nodes.append(node)
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "args" for target in node.targets
        ):
            break
    parser_source = ast.unparse(ast.Module(body=parser_nodes, type_ignores=[]))

    home = tmp_path / "hermes"
    scripts = home / "scripts"
    scripts.mkdir(parents=True)
    shim = scripts / "release73__pd_one_failure_alert_queue_worker.py"
    # Reproduce the release shim's in-process sys.path bootstrap. This MUST NOT
    # leak into children; cwd must make the child's `-m scripts...` import work.
    prefix = r'''from __future__ import annotations
import argparse
import logging
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any
HERMES_AGENT = Path(os.environ["HERMES_AGENT_DIR"])
sys.path[:0] = [str(HERMES_AGENT / "scripts"), str(HERMES_AGENT)]
NOTIFICATION_ROUTER_PYTHON = sys.executable
NOTIFICATION_STATE_DIR = Path(os.environ["HERMES_HOME"]) / "unused"
SUPERVISOR_DELIVERY_TIMEOUT_SECONDS = 30
ESCALATION_ROUTE = "pd_one_failure_escalations"
RECEIPT_ROUTE = "pd_one_admin_receipts"
MAX_ALERTS_PER_RUN = 1
'''
    prefix += "\nPARSER_SOURCE = " + repr(parser_source) + "\n"
    suffix = r'''
real_run = subprocess.run
calls = []
def import_only(cmd, **kwargs):
    assert cmd[:3] == [sys.executable, "-m", "scripts.pd_one_notification_router"]
    assert "PYTHONPATH" not in os.environ
    # Preserve command prefix and cwd from the real production call site.
    # Replace the action with --help before spawning, so no outbox can flush.
    result = real_run([*cmd[:3], "--help"], cwd=kwargs.get("cwd"),
                      env=os.environ, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert kwargs.get("cwd") == str(HERMES_AGENT)
    assert "--config" in result.stdout
    parser_env = {
        "logging": logging, "argparse": argparse, "Path": Path,
        "DEFAULT_CONFIG": Path("/unused"), "DEFAULT_STATE_DIR": Path("/unused"),
        "SEVERITY_ORDER": {"info": 0, "error": 2}, "__doc__": "parser-only check",
    }
    saved_argv = sys.argv
    try:
        sys.argv = [cmd[2], *cmd[3:]]
        exec(PARSER_SOURCE, parser_env)
    finally:
        sys.argv = saved_argv
    calls.append(parser_env["args"].command)
    return SimpleNamespace(returncode=0, stdout="{}", stderr="")
subprocess = SimpleNamespace(run=import_only)
acquire_lock = lambda: 123
release_lock = lambda fd: None
notification_route_has_pending = lambda route: True
drain_queue = lambda: []
_redact_text = lambda text: text
_clean_triage_text = lambda text: text
default_subject = lambda outcome, alert: "import regression"
notification_route_for_outcome = lambda outcome: ESCALATION_ROUTE
_alert_ref = lambda alert: "test-event"
_notification_correlation_key = lambda alert: "test-correlation"
assert main() == 0
deliver_route_notification({"outcome": "fixed", "summary": "test"}, {})
assert calls == ["flush", "flush", "send"], calls
print("scheduled-script-router-import-ok")
'''
    shim.write_text(prefix + "\n" + functions_source + "\n" + suffix)
    env = {
        "HOME": str(tmp_path), "HERMES_HOME": str(home),
        "HERMES_AGENT_DIR": str(repo),
        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.defpath,
        "PYTHONDONTWRITEBYTECODE": "1", "HERMES_DISABLE_LAZY_INSTALLS": "1",
    }
    # No `python -m worker` from the repository cwd, and no PYTHONPATH crutch.
    result = subprocess.run([sys.executable, "-c", bootstrap, str(repo), str(shim)],
                            cwd=scripts, env=env,
                            text=True, capture_output=True, timeout=120, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "scheduled-script-router-import-ok" in result.stdout

#!/usr/bin/env python3
"""One-turn, zero-tool reviewer used by PD One interaction review.

``bot_room`` is an empty text-only toolset. Callers historically passed it to
``cli.main`` intending no tools, but default MCP merge still injected
``list_prompts`` / ``list_resources``. This runner pins ``bot_room,no_mcp``,
filters MCP discovery, catches ``SystemExit``, and prints the turn end reason
plus response length on stderr.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable

REVIEWER_TOOLSETS = "bot_room,no_mcp"
REVIEWER_MAX_TURNS = 1


def reviewer_toolset_list() -> list[str]:
    return [name.strip() for name in REVIEWER_TOOLSETS.split(",") if name.strip()]


def result_end_reason(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    reason = result.get("turn_exit_reason") or result.get("failure_reason") or ""
    return str(reason)


def result_response_text(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("final_response") or result.get("response") or "")
    return "" if result is None else str(result)


def result_tool_turns(result: Any) -> int:
    if not isinstance(result, dict):
        return 0
    raw = result.get("tool_turns")
    if raw is None:
        raw = result.get("api_calls")
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def parse_reviewer_json_array(text: str) -> list[Any]:
    """Return the reviewed JSON array from model stdout, or raise ValueError."""
    blob = (text or "").strip()
    if not blob:
        raise ValueError("reviewer returned empty output")
    decoder = json.JSONDecoder()
    for index, char in enumerate(blob):
        if char != "[":
            continue
        try:
            parsed, _end = decoder.raw_decode(blob[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            return parsed
    raise ValueError("reviewer output is not a JSON array")


def print_reviewer_status(result: Any, *, stream=None) -> None:
    stream = sys.stderr if stream is None else stream
    text = result_response_text(result)
    print(
        f"end_reason={result_end_reason(result) or 'unknown'} "
        f"response_len={len(text)} tool_turns={result_tool_turns(result)}",
        file=stream,
    )


def _patch_run_conversation(capture: dict[str, Any]) -> Callable[[], None]:
    from run_agent import AIAgent

    original = AIAgent.run_conversation

    def wrapped(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        capture["result"] = result
        return result

    AIAgent.run_conversation = wrapped  # type: ignore[method-assign]

    def restore() -> None:
        AIAgent.run_conversation = original  # type: ignore[method-assign]

    return restore


def invoke_cli_main(
    prompt: str,
    *,
    cli_main: Callable[..., Any] | None = None,
    toolsets: str = REVIEWER_TOOLSETS,
    max_turns: int = REVIEWER_MAX_TURNS,
) -> Any:
    """Call ``cli.main`` the way the live reviewer does; capture SystemExit + the turn result."""
    from hermes_cli.mcp_startup import set_mcp_server_filter

    set_mcp_server_filter(toolsets)
    capture: dict[str, Any] = {}

    def restore() -> None:
        return None

    restore_fn = restore
    if cli_main is None:
        from cli import main as cli_main
        restore_fn = _patch_run_conversation(capture)
    try:
        try:
            cli_main(
                query=prompt,
                oneshot=True,
                quiet=True,
                toolsets=toolsets,
                max_turns=max_turns,
                ignore_rules=True,
            )
            code = 0
        except SystemExit as exc:
            if exc.code is None:
                code = 0
            elif isinstance(exc.code, int):
                code = exc.code
            else:
                code = 1
        result = capture.get("result")
        if not isinstance(result, dict):
            result = {}
        result = dict(result)
        result.setdefault("exit_code", code)
        return result
    finally:
        restore_fn()


def run_reviewer(
    prompt: str,
    *,
    cli_main: Callable[..., Any] | None = None,
    run_turn: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Run one reviewer turn and return the agent result dict."""
    if run_turn is not None:
        result = run_turn(prompt)
        if not isinstance(result, dict):
            result = {"final_response": result_response_text(result)}
        return result
    return invoke_cli_main(prompt, cli_main=cli_main)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PD One zero-tool interaction reviewer")
    parser.add_argument("prompt", nargs="?", help="Reviewer prompt; omit to read stdin")
    parser.add_argument("--prompt-file", help="Read the reviewer prompt from this path")
    args = parser.parse_args(argv)
    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8-sig") as handle:
            prompt = handle.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        prompt = sys.stdin.read()
    if not prompt.strip():
        print("end_reason=empty_prompt response_len=0 tool_turns=0", file=sys.stderr)
        return 2
    # HERMES_IGNORE_RULES matches the live --ignore-rules reviewer path.
    os.environ.setdefault("HERMES_IGNORE_RULES", "1")
    try:
        result = run_reviewer(prompt)
    except SystemExit as exc:
        code = 0 if exc.code is None else (exc.code if isinstance(exc.code, int) else 1)
        print_reviewer_status({"turn_exit_reason": f"SystemExit({code})"})
        return code
    except Exception as exc:  # health: allow BLE001 -- CLI boundary: any reviewer failure is rc=1 + status
        print_reviewer_status({"turn_exit_reason": type(exc).__name__, "final_response": str(exc)})
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    text = result_response_text(result)
    if text:
        print(text)
    print_reviewer_status(result)
    code = result.get("exit_code")
    if isinstance(code, int):
        return code
    reason = result_end_reason(result)
    if result.get("failed") or (reason.startswith("max_iterations_reached") and result_tool_turns(result)):
        return 1
    try:
        parse_reviewer_json_array(text)
    except ValueError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

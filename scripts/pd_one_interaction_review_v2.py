#!/usr/bin/env python3
"""PD One interaction review v2 — reviewer invocation helpers.

The live cron scanner lives under ``~/.hermes/scripts/``. This module is the
repo copy of ``invoke_reviewer``: it runs the zero-tool model runner, logs the
stdout tail together with stderr, and strips Bitwarden secret-source banners
that previously hid the real failure.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from io import StringIO
from pathlib import Path

try:
    from scripts.pd_one_review_model_runner import (
        parse_reviewer_json_array,
        print_reviewer_status,
        result_response_text,
        result_tool_turns,
        run_reviewer,
    )
except ImportError:  # script next to the runner (``~/.hermes/scripts`` copy)
    from pd_one_review_model_runner import (
        parse_reviewer_json_array,
        print_reviewer_status,
        result_response_text,
        result_tool_turns,
        run_reviewer,
    )

_BITWARDEN_LINE = re.compile(r"bitwarden", re.IGNORECASE)
_SESSION_ID_LINE = re.compile(r"^\s*session_id:\s+\S+\s*$")
_TAIL_CHARS = 2000
_REVIEWER_RUNNER = Path(__file__).resolve().parent / "pd_one_review_model_runner.py"


def strip_reviewer_noise(text: str) -> str:
    """Drop Bitwarden secret-source banners and CLI session_id lines."""
    kept = []
    for line in (text or "").splitlines():
        if _BITWARDEN_LINE.search(line) or _SESSION_ID_LINE.match(line):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def combined_reviewer_tail(stdout: str, stderr: str, *, limit: int = _TAIL_CHARS) -> str:
    """Always include stdout (the model reply) with cleaned stderr, not ``stderr or stdout``."""
    chunks = []
    cleaned_err = strip_reviewer_noise(stderr)
    if cleaned_err:
        chunks.append(cleaned_err)
    out = (stdout or "").strip()
    if out:
        chunks.append(out[-limit:] if len(out) > limit else out)
    return "\n".join(chunks)[-limit:]


def _status_line(result: dict) -> str:
    buf = StringIO()
    print_reviewer_status(result, stream=buf)
    return buf.getvalue()


def invoke_reviewer(
    prompt: str,
    *,
    timeout: int = 180,
    python: str | None = None,
    env: dict[str, str] | None = None,
    run_turn=None,
) -> str:
    """Run the zero-tool reviewer. ``run_turn`` is the in-process test seam."""
    if run_turn is not None:
        result = run_reviewer(prompt, run_turn=run_turn)
        text = result_response_text(result)
        code = result.get("exit_code")
        if result.get("failed") or code not in (None, 0):
            raise RuntimeError(
                f"reviewer failed rc={code if code is not None else 1}: "
                f"{combined_reviewer_tail(text, _status_line(result))}"
            )
        return text

    proc = subprocess.run(
        [python or sys.executable, str(_REVIEWER_RUNNER)],
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env or os.environ.copy(),
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    stderr = strip_reviewer_noise(proc.stderr or "")
    stdout = proc.stdout or ""
    if stderr:
        print(stderr, file=sys.stderr)
    if proc.returncode != 0:
        raise RuntimeError(
            f"reviewer failed rc={proc.returncode}: {combined_reviewer_tail(stdout, proc.stderr or '')}"
        )
    return stdout


def review_once(prompt: str, *, run_turn=None) -> list:
    """One reviewer call that must finish with ``tool_turns=0`` and a JSON array."""
    if run_turn is not None:
        result = run_reviewer(prompt, run_turn=run_turn)
        if result_tool_turns(result) != 0:
            raise RuntimeError(f"reviewer used tools: tool_turns={result_tool_turns(result)}")
        raw = result_response_text(result)
    else:
        raw = invoke_reviewer(prompt)
    return parse_reviewer_json_array(raw)


def main(argv: list[str] | None = None) -> int:
    prompt = " ".join(argv) if argv else sys.stdin.read()
    if not prompt.strip():
        print("reviewer prompt is empty", file=sys.stderr)
        return 2
    try:
        rows = review_once(prompt)
    except Exception as exc:  # health: allow BLE001 -- CLI boundary: reviewer failure is rc=1
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(rows, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))

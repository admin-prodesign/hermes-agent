"""Deploy-gate self-test for the PD One safe-ops tools.

Every MCP tool in the catalog is called once in a harmless mode, from the release
this module is imported from (the published release is read-only):

* placeholder arguments, ``dry_run=True`` and ``live=False``, never a confirmation phrase;
* child processes are planned, not run: each argv is checked (a ``.py`` must be run by
  an interpreter, every ``pd_one.external.*`` it names must be set, scripts readable);
* outbound network is refused, and writes outside a scratch copy of the profile config
  are refused;
* each release helper script a tool would launch is then started for real with
  ``--help``, by the planned interpreter with the planned environment, so an import that
  breaks under a read-only release fails here and not in production.

Run before cutover::

    <release>/.venv/bin/python -m tools.pd_one_ops.selftest --hermes-home <home> --profile pdone

Exit 0 when every tool passes, 1 otherwise. ``--readonly-copy`` first copies the release
``tools/`` package to a temp tree with every file 0444 and runs the test from there.
"""
from __future__ import annotations

import argparse
import contextlib
import inspect
import io
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from tools.pd_one_ops.selftest_guard import Guard, WriteRefused

RELEASE_ROOT = Path(__file__).resolve().parent.parent.parent
_TOOL_TIMEOUT_SECONDS = 60
_PROBE_TIMEOUT_SECONDS = 60
_RERUN_TIMEOUT_SECONDS = 1800

# Text that means the bug class this gate exists for, wherever it surfaces.
_FAILURE_SIGNATURES = (
    ("[Errno 13]", "permission denied (a file launched without its exec bit?)"),
    ("<unset pd_one.external.", "an unset pd_one.external key reached a launch"),
    ("missing_external_config", "a required pd_one.external key is unset or missing"),
    ("PD One external dependency", "a required pd_one.external key is unset or missing"),
    ("[Errno 30]", "write into the read-only release"),
    ("Read-only file system", "write into the read-only release"),
    ("No module named", "an import failed"),
)


@dataclass
class ToolResult:
    name: str
    status: str = "pass"
    outcome: str = ""
    launches: int = 0
    problems: list[str] = field(default_factory=list)
    detail: str = ""


def _placeholder(param: inspect.Parameter) -> Any:
    text = str(param.annotation)
    if "list" in text:
        return [1.0] if "float" in text else ["selftest"]
    if "dict" in text:
        return {}
    if "bool" in text:
        return False
    if "int" in text:
        return 1
    if "float" in text:
        return 1.0
    return "selftest"


def placeholder_arguments(fn: Any) -> dict[str, Any]:
    """Required parameters filled with placeholders; ``dry_run`` on and ``live`` off."""
    arguments: dict[str, Any] = {}
    for name, param in inspect.signature(fn).parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        if name == "dry_run":
            arguments[name] = True
        elif name == "live":
            arguments[name] = False
        elif param.default is inspect.Parameter.empty:
            arguments[name] = _placeholder(param)
    return arguments


def failure_reasons(text: str) -> list[str]:
    return list(dict.fromkeys(reason for marker, reason in _FAILURE_SIGNATURES if marker in text))


def named_external_keys(text: str) -> set[str]:
    chunks = text.split("pd_one.external.")[1:]
    return {chunk.split()[0].strip(">'\",.:;)") for chunk in chunks if chunk.split()}


def _only_allowed_keys(text: str, allow_missing: frozenset[str]) -> bool:
    """True when ``text`` is about pd_one.external keys the operator declared absent on this host."""
    keys = named_external_keys(text)
    return bool(keys) and keys <= allow_missing


class _Timeout(Exception):
    pass


# A per-tool deadline where the host has one (POSIX); elsewhere a hung tool hangs the run.
_HAS_ALARM = hasattr(signal, "SIGALRM")


def _on_alarm(signum: int, frame: Any) -> None:
    raise _Timeout()


def _invoke(fn: Any, result: ToolResult) -> str:
    """Call ``fn`` with placeholders; returns the text to scan (result, error, or printed output)."""
    printed = io.StringIO()
    if _HAS_ALARM:
        signal.signal(signal.SIGALRM, _on_alarm)  # windows-footgun: ok — gated on _HAS_ALARM
        signal.alarm(_TOOL_TIMEOUT_SECONDS)
    try:
        with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
            payload = fn(**placeholder_arguments(fn))
        result.outcome = "completed"
        return payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)
    except _Timeout:
        result.outcome, result.status = "timeout", "warn"
        result.detail = f"did not finish within {_TOOL_TIMEOUT_SECONDS}s"
        return printed.getvalue()
    except SystemExit:
        result.outcome = "exited"
        return printed.getvalue()
    except Exception as exc:  # health: allow BLE001 -- every tool failure is reported in the result, none stops the run
        result.outcome = "raised"
        text = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, (ImportError, OSError)) and not isinstance(exc, (ConnectionError, TimeoutError, WriteRefused)):
            result.problems.append(text[:300])
        return text + "\n" + printed.getvalue()
    finally:
        if _HAS_ALARM:
            signal.alarm(0)


def _call_tool(name: str, fn: Any, guard: Guard, allow_missing: frozenset[str]) -> ToolResult:
    result = ToolResult(name)
    guard.launches.clear()
    text = _invoke(fn, result)
    result.launches = len(guard.launches)
    for launch in guard.launches:
        result.problems.extend(launch.problems)
    if not _only_allowed_keys(text, allow_missing):
        result.problems.extend(failure_reasons(text))
    result.problems = [p for p in dict.fromkeys(result.problems) if not _only_allowed_keys(p, allow_missing)]
    if result.problems:
        result.status = "fail"
        result.detail = result.detail or text[:300]
    return result


def _probe_scripts(guard: Guard) -> list[ToolResult]:
    """Start every release helper a tool would launch, with ``--help``."""
    results = []
    for (interpreter, script), (env, cwd) in sorted(guard.scripts.items()):
        result = ToolResult(f"start {Path(script).name} ({Path(interpreter).name})", outcome="started")
        try:
            proc = guard.real_run([interpreter, script, "--help"], env=env, cwd=cwd,
                                  capture_output=True, text=True, timeout=_PROBE_TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired) as exc:
            result.status, result.detail = "fail", f"{type(exc).__name__}: {exc}"
            results.append(result)
            continue
        if proc.returncode != 0:
            result.status = "fail"
            result.detail = (proc.stderr or proc.stdout or "")[-600:]
        results.append(result)
    return results


def _server_result() -> ToolResult:
    result = ToolResult("build_server", outcome="registered")
    try:
        from tools.pd_one_safe_ops_mcp import build_server

        build_server()
    except Exception as exc:  # health: allow BLE001 -- the server's startup failure is the reported result
        result.status, result.detail = "fail", f"{type(exc).__name__}: {exc}"[:600]
    return result


def profile_home(home: Path, profile: str) -> Path:
    return home if home.parent.name == "profiles" else home / "profiles" / profile


def _scoped_environ(home: Path, profile: str, scratch: Path) -> None:
    """The environment the gateway now hands the safe-ops server: HERMES_HOME on the profile."""
    for key in ("HERMES_PROFILE_HOME", "PD_ONE_PROFILE_HOME", "HERMES_PROFILE", "HERMES_PROFILE_NAME"):
        os.environ.pop(key, None)
    os.environ["HERMES_HOME"] = str(profile_home(home, profile))
    os.environ["TMPDIR"] = str(scratch)
    tempfile.tempdir = str(scratch)


def run_selftest(home: Path, profile: str, *, tools: Optional[list[str]] = None,
                 allow_missing: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Reads come from the real profile; every write outside a scratch directory is refused."""
    scratch = Path(tempfile.mkdtemp(prefix="pd-one-selftest-"))
    _scoped_environ(home, profile, scratch)
    from tools.pd_one_ops.mcp_tools import iter_mcp_tools
    from tools.pd_one_ops.site_config import config_sources

    # The first config load initialises the Hermes home; do it before writes are refused.
    config_sources()
    results = [_server_result()]
    logging.disable(logging.CRITICAL)
    try:
        with Guard(scratch, RELEASE_ROOT) as guard:
            for name, fn in iter_mcp_tools():
                if tools and name not in tools:
                    continue
                results.append(_call_tool(name, fn, guard, allow_missing))
            results.extend(_probe_scripts(guard))
    finally:
        logging.disable(logging.NOTSET)
        shutil.rmtree(scratch, ignore_errors=True)
    failed = [result for result in results if result.status == "fail"]
    return {
        "ok": not failed,
        "release": str(RELEASE_ROOT),
        "profile": profile,
        "counts": {status: sum(1 for r in results if r.status == status) for status in ("pass", "warn", "fail")},
        "results": [result.__dict__ for result in results],
    }


def readonly_copy(source: Path) -> Path:
    """Copy ``source/tools`` to a temp release with every file 0444 and every directory 0555."""
    target = Path(tempfile.mkdtemp(prefix="pd-one-readonly-release-"))
    shutil.copytree(source / "tools", target / "tools",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for path in sorted(target.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    return target


def _rerun_from_copy(argv: list[str]) -> int:
    copy = readonly_copy(RELEASE_ROOT)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(copy), str(RELEASE_ROOT), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    rest = [arg for arg in argv if arg != "--readonly-copy"]
    try:
        return subprocess.run([sys.executable, "-m", "tools.pd_one_ops.selftest", *rest],
                              cwd=str(copy), env=env, check=False, timeout=_RERUN_TIMEOUT_SECONDS).returncode
    finally:
        for path in [copy, *copy.rglob("*")]:
            path.chmod(0o755 if path.is_dir() else 0o644)
        shutil.rmtree(copy, ignore_errors=True)


def _print_summary(report: dict[str, Any]) -> None:
    for result in report["results"]:
        if result["status"] == "pass":
            continue
        reasons = "; ".join(result["problems"]) or result["detail"]
        print(f"{result['status'].upper():4} {result['name']}: {reasons}")
    counts = report["counts"]
    verdict = "PASS" if report["ok"] else "FAIL"
    print(f"{verdict} pd-one safe-ops selftest: {counts['pass']} pass, {counts['warn']} warn, "
          f"{counts['fail']} fail (release {report['release']}, profile {report['profile']})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.pd_one_ops.selftest", description=__doc__.split("\n\n")[0])
    parser.add_argument("--hermes-home", type=Path, default=None,
                        help="Hermes install root or profile home. Defaults to HERMES_HOME.")
    parser.add_argument("--profile", default="pdone", help="Profile folder under profiles/. Default: pdone.")
    parser.add_argument("--tool", action="append", default=None, help="Only this MCP tool (repeatable).")
    parser.add_argument("--allow-missing", action="append", default=[],
                        help="pd_one.external key that is intentionally absent on this host (repeatable).")
    parser.add_argument("--readonly-copy", action="store_true",
                        help="Copy the release tools/ to a 0444 temp tree and run from there.")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(raw)
    if args.readonly_copy:
        return _rerun_from_copy(raw)
    from hermes_constants import get_hermes_home

    home = (args.hermes_home or get_hermes_home()).expanduser()
    if not profile_home(home, args.profile).is_dir():
        print(f"no PD One profile at {profile_home(home, args.profile)}; pass --hermes-home/--profile", file=sys.stderr)
        return 2
    report = run_selftest(home, args.profile, tools=args.tool, allow_missing=frozenset(args.allow_missing))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_summary(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

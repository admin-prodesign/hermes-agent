"""stdio MCP server for PD One safe ops.

Every ``pd_one_*`` command and ``call_function_twin`` is registered from the
release module beside this file. HRS and HR-employee row payloads go through
the private-column denylist before the result is returned. Private HR lookup
stays on the in-process tool, which can see the bound Mattermost session; an
MCP child cannot.

The profile ``tools/`` directory is not imported unless
``pd_one.load_profile_tools`` is true. That flag is off by default. Names the
release already owns are never taken from the profile file.

Deploy, after the nemo release is rebuilt from main (the ``nemo`` extra
supplies honcho-ai and PyYAML):

1. Point the pdone profile ``mcp_servers.pdone_safe_ops`` command at
   ``tools/pd_one_safe_ops_mcp.py`` in the release checkout, using the
   release interpreter. Do not copy this file into the profile ``tools/``
   directory: a script's ``sys.path[0]`` is its own directory, and a copy
   beside an old module would import that module.
2. Set the ``pd_one`` config values (channels, owner, drive ids, emails,
   external paths). See ``website/docs/user-guide/pd-one-safe-ops.md``.
3. Retire ``profiles/pdone/tools/pd_one_safe_ops.py`` and
   ``profiles/pdone/tools/pd_one_safe_ops_mcp.py``.
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Callable

_MODULE_NAME = "tools.pd_one_safe_ops"
_FILTER_SENTINEL = "SENTINEL-PRIVATE-COLUMN"
_ROW_LIST_KEYS = ("rows", "Rows", "data")

# Read commands the profile MCP must keep. Handlers live in the filtered
# repo module; this map is only the MCP names and the argument shape
# (table, query). Profile-only reads are added in ``mcp_read_handlers``.
_READ_TOOLS = (
    "pd_one_appsheet_table_probe",
    "pd_one_appsheet_row_get",
)

# The profile module's copies of these names are the unfiltered probe. Never
# dispatch them. Private lookup stays on the in-process tool, which can see
# the bound session; an MCP child cannot.
_REPO_OWNED = frozenset({
    *_READ_TOOLS,
    "pd_one_hr_private_lookup",
    "cmd_appsheet_table_probe",
    "cmd_appsheet_row_get",
})

_PROFILE_MODULE = "pd_one_safe_ops_profile"
_PROFILE_CACHE: dict[str, dict[str, Callable[..., Any]]] = {}


def _repo_safe_ops_path() -> Path:
    return Path(__file__).resolve().with_name("pd_one_safe_ops.py")


def load_filtered_safe_ops() -> Any:
    """Import the filtered implementation that sits beside this file.

    ``sys.path[0]`` for a script is the script directory. Running a copy of
    this file from ``profiles/pdone/tools/`` would otherwise bind the
    unfiltered sibling. Loading by path, and checking the file identity of
    an already-imported module, keeps the release copy.
    """
    path = _repo_safe_ops_path()
    loaded = sys.modules.get(_MODULE_NAME)
    loaded_file = getattr(loaded, "__file__", None)
    if loaded is not None and loaded_file and Path(loaded_file).resolve() == path:
        return loaded
    root = str(path.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"filtered safe ops missing at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def assert_filtered_implementation(ops: Any | None = None) -> None:
    """Fail closed when the loaded probe still returns a private column."""
    module = ops if ops is not None else load_filtered_safe_ops()
    payload = module.cmd_appsheet_table_probe(
        "HRS_Data",
        rows=[{"職等代碼": _FILTER_SENTINEL, "姓名": "ok"}],
    )
    encoded = json.dumps(payload, ensure_ascii=False)
    if _FILTER_SENTINEL in encoded or "職等代碼" in encoded:
        raise RuntimeError(
            "safe-ops MCP refused to start: the loaded pd_one_safe_ops module "
            "still returns HRS private columns. Point the pdone profile at the "
            "release tools/pd_one_safe_ops_mcp.py and retire the profile copy "
            "profiles/pdone/tools/pd_one_safe_ops.py."
        )


def _read_handlers(ops: Any) -> dict[str, Callable[..., Any]]:
    handlers = dict(ops.mcp_read_handlers())
    missing = [name for name in _READ_TOOLS if name not in handlers]
    if missing:
        raise RuntimeError(f"filtered safe ops is missing MCP reads: {', '.join(missing)}")
    return handlers


def _profile_module_path() -> Path | None:
    """Profile library under the active Hermes home, when it is not the release file."""
    from hermes_constants import get_hermes_home

    path = (get_hermes_home() / "tools" / "pd_one_safe_ops.py").resolve()
    if not path.is_file() or path == _repo_safe_ops_path():
        return None
    return path


def _profile_exports(module: Any, owned: frozenset[str] | None = None) -> dict[str, Callable[..., Any]]:
    blocked = _REPO_OWNED if owned is None else owned
    found: dict[str, Callable[..., Any]] = {}
    for name, obj in vars(module).items():
        if name.startswith("_") or name in blocked or not inspect.isfunction(obj):
            continue
        if name.startswith("pd_one_") or name == "call_function_twin":
            found[name] = obj
    return found


def _load_profile_module(path: Path) -> Any:
    """Load the profile library without replacing ``tools.pd_one_safe_ops``.

    The profile tools directory is appended, not inserted at the front, so a
    sibling import cannot shadow the release package. A broken profile file
    raises: a missing command is visible, and the probe is not silently
    swapped back to the unfiltered copy.
    """
    tools_dir = str(path.parent)
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    digest = hashlib.sha256(str(path).encode()).hexdigest()[:16]
    mod_name = f"{_PROFILE_MODULE}_{digest}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"profile safe ops missing at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def profile_command_handlers() -> dict[str, Callable[..., Any]]:
    """Profile ``pd_one_*`` commands. Empty unless ``pd_one.load_profile_tools`` is true.

    Release-owned names are excluded, so a profile file cannot replace the
    filtered probe or any command that now ships in the repo.
    """
    from tools.pd_one_ops.site_config import profile_tools_enabled

    if not profile_tools_enabled():
        return {}
    path = _profile_module_path()
    if path is None:
        return {}
    key = str(path)
    cached = _PROFILE_CACHE.get(key)
    if cached is not None:
        return cached
    handlers = _profile_exports(_load_profile_module(path), _release_owned_names())
    _PROFILE_CACHE[key] = handlers
    return handlers


def _release_owned_names() -> frozenset[str]:
    from tools.pd_one_safe_ops import mcp_read_handlers

    return frozenset(_REPO_OWNED) | frozenset(mcp_read_handlers())


def ensure_hrs_redacted(
    table: str,
    payload: Any,
    *,
    tool_name: str = "",
    arguments: dict | None = None,
) -> Any:
    """Second gate for MCP results. An already-filtered payload is unchanged.

    HRS tables and HR-employee row payloads lose private columns. JSON text is
    parsed and written back only when a cell was removed. A clean object is
    returned as the same object.
    """
    from tools.pd_one_ops.hr_guard import guard_hr_payload

    guarded = guard_hr_payload(
        payload, table=table, tool_name=tool_name, arguments=arguments,
    )
    if guarded is not payload:
        return guarded
    if isinstance(payload, str):
        return _redact_json_text(table, payload)
    if isinstance(payload, list):
        return _redact_row_list(str(table or ""), payload)
    if not isinstance(payload, dict):
        return payload
    return _redact_mapping(table, payload)


def _redact_json_text(table: str, payload: str) -> Any:
    stripped = payload.lstrip()
    if not stripped or stripped[0] not in "{[":
        return payload
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    cleaned = ensure_hrs_redacted(table, decoded)
    if cleaned is decoded:
        return payload
    return json.dumps(cleaned, ensure_ascii=False)


def _redact_row_list(table: str, rows: list) -> Any:
    from tools.pd_one_hr_fields import PRIVATE_HRS_TABLES, redact_private_hr_columns

    if table not in PRIVATE_HRS_TABLES:
        return rows
    redacted = redact_private_hr_columns(table, rows)
    if not redacted["withheld_fields"]:
        return rows
    return redacted["rows"]


def _redact_mapping(table: str, payload: dict) -> Any:
    from tools.pd_one_hr_fields import PRIVATE_HRS_TABLES, redact_private_hr_columns

    table_name = str(table or payload.get("table") or "")
    if table_name not in PRIVATE_HRS_TABLES:
        return payload
    list_key = next((key for key in _ROW_LIST_KEYS if isinstance(payload.get(key), list)), None)
    row = payload.get("row") if isinstance(payload.get("row"), dict) else None
    if list_key is None and row is None:
        return payload
    cleaned = dict(payload)
    withheld = 0
    if list_key is not None:
        redacted = redact_private_hr_columns(table_name, payload[list_key])
        withheld = _apply_row_list(cleaned, list_key, redacted, withheld)
    if row is not None:
        redacted_one = redact_private_hr_columns(table_name, [row])
        withheld = _apply_single_row(cleaned, redacted_one, withheld)
    if not withheld:
        return payload
    cleaned["table"] = table_name
    cleaned["withheld_fields"] = withheld
    return cleaned


def _apply_row_list(cleaned: dict, list_key: str, redacted: dict, withheld: int) -> int:
    if not redacted["withheld_fields"]:
        return withheld
    cleaned[list_key] = redacted["rows"]
    return max(withheld, int(redacted["withheld_fields"]))


def _apply_single_row(cleaned: dict, redacted: dict, withheld: int) -> int:
    if not redacted["withheld_fields"]:
        return withheld
    cleaned["row"] = redacted["rows"][0] if redacted["rows"] else {}
    return max(withheld, int(redacted["withheld_fields"]))


def _table_name(args: dict, payload: Any) -> str:
    named = args.get("table")
    if named:
        return str(named)
    if isinstance(payload, dict) and payload.get("table"):
        return str(payload["table"])
    if isinstance(payload, str):
        return _table_name({}, _decode_object(payload))
    return ""


def _decode_object(payload: str) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _invoke_profile(fn: Callable[..., Any], args: dict[str, Any]) -> Any:
    signature = inspect.signature(fn)
    accepts_any = any(
        param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
    )
    if accepts_any:
        return fn(**args)
    accepted = {key: value for key, value in args.items() if key in signature.parameters}
    return fn(**accepted)


def call_mcp_tool(name: str, arguments: dict | None = None) -> Any:
    """Run one MCP-exposed safe-ops command.

    Release handlers win. A profile command is used only when
    ``pd_one.load_profile_tools`` is true and the name is not in the release.
    Unknown names do not fetch rows. The result goes through the HR denylist.
    """
    ops = load_filtered_safe_ops()
    handlers = _read_handlers(ops)
    args = arguments if isinstance(arguments, dict) else {}
    fn = handlers.get(name)
    if fn is None:
        fn = profile_command_handlers().get(name)
    if fn is None:
        return {"ok": False, "error": "unknown safe-ops command"}
    payload = _invoke_profile(fn, args)
    return ensure_hrs_redacted(
        _table_name(args, payload), payload, tool_name=name, arguments=args,
    )


def _descriptions() -> dict[str, str]:
    return {
        "pd_one_appsheet_table_probe": (
            "Read an AppSheet table for PD One. HRS_Data and HRS_Data_MasterNames "
            "omit private columns and return a withheld_fields count."
        ),
        "pd_one_appsheet_row_get": (
            "Read one AppSheet row for PD One. HRS private columns are omitted."
        ),
    }


def build_server() -> Any:
    """Expose every release command, then profile commands when the flag is on."""
    from mcp.server.mcpserver import MCPServer

    ops = load_filtered_safe_ops()
    assert_filtered_implementation(ops)
    server = MCPServer("pdone_safe_ops")
    descriptions = _descriptions()
    _register_release_tools(server, _read_handlers(ops), descriptions)
    for name, fn in profile_command_handlers().items():
        _register_profile(server, name, fn)
    return server


def _register_release_tools(
    server: Any,
    handlers: dict[str, Callable[..., Any]],
    descriptions: dict[str, str],
) -> None:
    row_get = "pd_one_appsheet_row_get"
    _register_read(server, row_get, descriptions.get(row_get, row_get))
    for name, fn in handlers.items():
        if name == row_get:
            continue
        _register_profile(server, name, fn)


def _register_read(server: Any, name: str, description: str) -> None:
    # The tool name is closed over. mcp 2.0 rejects a parameter whose name
    # starts with "_" (InvalidSignature), so it cannot be a default argument.
    def tool(table: str, query: str = "") -> dict[str, Any]:
        result = call_mcp_tool(name, {"table": table, "query": query})
        if not isinstance(result, dict):
            return {"ok": False, "error": "safe-ops command returned no object"}
        return result

    tool.__name__ = name
    tool.__doc__ = description
    server.add_tool(tool, name=name, description=description, structured_output=True)


def _public_signature(fn: Callable[..., Any]) -> inspect.Signature:
    """Input schema for a wrapped tool.

    Varargs, keyword-only extras, and private names stay off the schema.
    mcp 2.0 rejects a parameter whose name starts with "_". Annotations are
    evaluated here because assigning ``__signature__`` skips the SDK's
    ``eval_str`` pass. The return annotation is ``dict[str, Any]`` because
    that is the value the wrapper hands back for structured output.
    """
    original = inspect.signature(fn, eval_str=True)
    visible = [
        param for param in original.parameters.values()
        if param.kind not in {
            inspect.Parameter.VAR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.KEYWORD_ONLY,
        }
        and not param.name.startswith("_")
    ]
    return original.replace(parameters=visible, return_annotation=dict[str, Any])


def _as_tool_object(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    parsed = _json_object(result)
    if isinstance(parsed, dict):
        return parsed
    return {"ok": True, "result": result}


def _json_object(result: Any) -> Any:
    if not isinstance(result, str):
        return None
    stripped = result.lstrip()
    if not stripped or stripped[0] not in "{[":
        return None
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return None


def _register_profile(server: Any, name: str, fn: Callable[..., Any]) -> None:
    description = inspect.getdoc(fn) or name

    def tool(**kwargs: Any) -> dict[str, Any]:
        return _as_tool_object(call_mcp_tool(name, kwargs))

    tool.__name__ = name
    tool.__doc__ = description
    # The SDK builds the tool schema from this signature, not from **kwargs.
    tool.__signature__ = _public_signature(fn)  # type: ignore[attr-defined]
    server.add_tool(tool, name=name, description=description, structured_output=True)


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()

"""MCP tool callables that ship in the release.

Names and order match the profile server the skills already call. The
functions live in ``tools.pd_one_ops.pd_one_safe_ops_mcp``, not in the stdio
server module.
"""
from __future__ import annotations

from typing import Any, Callable, Iterator


def iter_mcp_tools() -> Iterator[tuple[str, Callable[..., Any]]]:
    from tools.pd_one_ops._catalog import MCP_TOOLS
    from tools.pd_one_ops import pd_one_safe_ops_mcp as commands

    for name in MCP_TOOLS:
        yield name, getattr(commands, name)

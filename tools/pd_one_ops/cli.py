"""CLI entry for the packaged PD One safe-ops commands.

``tools/pd_one_safe_ops.py`` stays the path skills and the MCP server execute.
This module is the implementation that file delegates to.
"""
from __future__ import annotations


def build_parser():
    from tools.pd_one_ops.pd_one_safe_ops import build_parser as impl

    return impl()


def main(argv=None) -> int:
    from tools.pd_one_ops.pd_one_safe_ops import main as impl

    return int(impl(argv))

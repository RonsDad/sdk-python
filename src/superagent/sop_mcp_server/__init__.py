"""Standalone MCP server exposing SOPs as prompts over stdio.

Each ``*.sop.md`` file under :mod:`superagent.sop_mcp_server.sops` is
registered as an MCP prompt; the prompt name is the filename slug (without
the ``.sop.md`` suffix) and the prompt body is the file's full text.

Launch with ``python -m superagent.sop_mcp_server`` — the process speaks
MCP stdio and is intended to be consumed by :class:`strands.tools.mcp.MCPClient`
(``strands/tools/mcp/mcp_client.py``).
"""

from .server import build_server, iter_sops

__all__ = ["build_server", "iter_sops"]

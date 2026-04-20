"""Runtime wiring for the superagent.

The ``bootstrap`` module exposes :func:`build_agent`, which combines:

  - ``strands.experimental.agent_config.config_to_agent`` to load the
    declarative 13-tool roster from ``superagent/agent_config.json``.
  - ``strands.session.FileSessionManager`` for on-disk persistence.
  - ``strands.agent.conversation_manager.SummarizingConversationManager``
    for context overflow handling.
  - Hook providers from :mod:`superagent.plugins`.
  - An ``MCPClient`` (``strands.tools.mcp.MCPClient``) connected to the
    local SOP MCP server (``superagent.sop_mcp_server``) for prompt
    lookups.

The bootstrap layer never introduces new tool logic; it only composes
SDK-provided primitives around the config-driven agent.
"""

from .bootstrap import build_agent, build_sop_mcp_client

__all__ = ["build_agent", "build_sop_mcp_client"]

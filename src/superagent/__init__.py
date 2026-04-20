"""Superagent — a config-driven Strands meta-tooling agent.

This package assembles an ``Agent`` from :mod:`strands.experimental.agent_config`
(``config_to_agent``) with a flat tool directory under
:mod:`superagent.tools`, a stdio SOP MCP server under
:mod:`superagent.sop_mcp_server`, resilience hooks under
:mod:`superagent.plugins`, and runtime wiring under
:mod:`superagent.runtime`.
"""

__all__: list[str] = []

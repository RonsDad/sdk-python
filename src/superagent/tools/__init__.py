"""Flat tool directory for the superagent.

Every module in this package exposes one or more functions decorated with
``@strands.tool`` (``strands.tools.decorator.tool``). The 13 tools listed in
``superagent/agent_config.json`` are preloaded into the agent's registry by
``config_to_agent``; all remaining modules here are loadable on demand via the
``load_tool`` tool.
"""

__all__: list[str] = []

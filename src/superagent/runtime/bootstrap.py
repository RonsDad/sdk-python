"""Compose the superagent from SDK primitives only.

``build_agent`` is the single entry point. It:

  1. Loads the declarative config via
     ``strands.experimental.agent_config.config_to_agent``.
  2. Attaches a ``FileSessionManager`` for durable state.
  3. Installs ``SummarizingConversationManager`` for context overflow.
  4. Registers hook providers from :mod:`superagent.plugins`.
  5. Optionally attaches an ``MCPClient`` connected to the local SOP
     MCP server (``python -m superagent.sop_mcp_server``) so the agent
     can resolve SOP prompts.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from strands.agent.conversation_manager import SummarizingConversationManager
from strands.experimental.agent_config import config_to_agent
from strands.session import FileSessionManager
from strands.tools.mcp import MCPClient

from ..model_providers import build_model
from ..plugins import build_default_hooks

logger = logging.getLogger(__name__)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "agent_config.json"
DEFAULT_MODEL_CONFIG_PATH = PACKAGE_ROOT / "configs" / "model.anthropic.json"
DEFAULT_SESSION_DIR = os.environ.get(
    "SUPERAGENT_SESSION_DIR",
    str(Path.home() / ".superagent" / "sessions"),
)


def build_sop_mcp_client() -> MCPClient:
    """Return an ``MCPClient`` that launches the local SOP MCP server over stdio."""
    from mcp import StdioServerParameters  # type: ignore
    from mcp.client.stdio import stdio_client  # type: ignore

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "superagent.sop_mcp_server"],
    )
    return MCPClient(lambda: stdio_client(params))


def build_agent(
    *,
    config_path: str | os.PathLike[str] = DEFAULT_CONFIG_PATH,
    model_config_path: str | os.PathLike[str] | None = DEFAULT_MODEL_CONFIG_PATH,
    session_id: str | None = None,
    session_dir: str = DEFAULT_SESSION_DIR,
    attach_sop_mcp: bool = True,
    extra_hooks: list[Any] | None = None,
) -> Any:
    """Construct the superagent.

    Args:
        config_path: Path to the **Type 1** ``agent_config.json`` — name,
            system prompt, and tool roster. Validated by the SDK's strict
            ``AGENT_CONFIG_SCHEMA``; contains no provider wiring.
        model_config_path: Path to the **Type 2** ``model.<provider>.json``
            file consumed by :mod:`superagent.model_providers`. Produces a
            ``strands.models.Model`` instance that is passed as ``model=``
            into ``config_to_agent``. If None, the agent falls back to the
            SDK-default Bedrock model.
        session_id: Session identifier for ``FileSessionManager``. If None,
            falls back to ``SUPERAGENT_SESSION_ID`` env var or "default".
        session_dir: Directory for on-disk session storage.
        attach_sop_mcp: If True, open a connection to the local SOP MCP
            server and register its prompts/tools on the agent.
        extra_hooks: Optional hook providers appended after the default
            ``build_default_hooks()`` stack.

    Returns:
        A fully configured ``strands.Agent`` ready for ``agent(...)`` calls.
    """
    sid = session_id or os.environ.get("SUPERAGENT_SESSION_ID", "default")

    session_manager = FileSessionManager(session_id=sid, storage_dir=session_dir)
    conversation_manager = SummarizingConversationManager()
    hooks = list(build_default_hooks())
    if extra_hooks:
        hooks.extend(extra_hooks)

    agent_kwargs: dict[str, Any] = {
        "session_manager": session_manager,
        "conversation_manager": conversation_manager,
        "hooks": hooks,
    }
    if model_config_path is not None:
        agent_kwargs["model"] = build_model(str(model_config_path))

    agent = config_to_agent(str(config_path), **agent_kwargs)

    if attach_sop_mcp:
        try:
            sop_client = build_sop_mcp_client()
            sop_client.start()
            for sop_tool in sop_client.list_tools_sync():
                agent.tool_registry.register_tool(sop_tool)
            logger.info("attached SOP MCP client with %d tools", len(agent.tool_registry.registry))
        except Exception as exc:  # noqa: BLE001 - bootstrap must degrade gracefully
            logger.warning("could not attach SOP MCP client: %s", exc)

    return agent


__all__ = ["DEFAULT_CONFIG_PATH", "DEFAULT_SESSION_DIR", "build_agent", "build_sop_mcp_client"]

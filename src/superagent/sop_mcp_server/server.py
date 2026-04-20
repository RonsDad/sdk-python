"""FastMCP stdio server that serves SOPs as MCP prompts.

Design choices:
  - One prompt per ``<slug>.sop.md`` file, discovered by glob at startup.
  - Prompt description is the first paragraph under the ``## Purpose``
    heading (falls back to the H1 if the file lacks a Purpose section).
  - Prompt body is the full file contents returned as a single user
    message — MCP clients decide whether to inject it as a system prompt
    or a tool-visible document.
  - Uses ``mcp.server.fastmcp.FastMCP`` (the reference Python MCP server),
    which is a sibling of the client at ``strands/tools/mcp/mcp_client.py``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

SOP_DIR = Path(__file__).parent / "sops"
SOP_SUFFIX = ".sop.md"


def iter_sops(sop_dir: Path = SOP_DIR) -> Iterator[tuple[str, Path]]:
    """Yield ``(slug, path)`` pairs for every ``*.sop.md`` file."""
    for path in sorted(sop_dir.glob(f"*{SOP_SUFFIX}")):
        slug = path.name[: -len(SOP_SUFFIX)]
        yield slug, path


def _extract_description(body: str) -> str:
    """Return the paragraph under ``## Purpose`` or the H1 as a fallback."""
    purpose = re.search(r"^##\s+Purpose\s*\n+(.+?)(?:\n\s*\n|\Z)", body, re.MULTILINE | re.DOTALL)
    if purpose:
        return " ".join(purpose.group(1).split())
    h1 = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    return h1.group(1).strip() if h1 else "Strands SOP."


def build_server(sop_dir: Path = SOP_DIR) -> "object":
    """Construct a FastMCP server with one prompt per SOP file.

    Lazily imports ``mcp`` so the package stays importable without the
    optional dependency installed.
    """
    from mcp.server.fastmcp import FastMCP  # type: ignore

    server = FastMCP("superagent-sops")

    for slug, path in iter_sops(sop_dir):
        body = path.read_text(encoding="utf-8")
        description = _extract_description(body)

        def _make_handler(captured_body: str):
            def _handler() -> str:
                return captured_body

            return _handler

        server.prompt(name=slug, description=description)(_make_handler(body))
        logger.debug("registered SOP prompt %s from %s", slug, path)

    return server


__all__ = ["SOP_DIR", "SOP_SUFFIX", "build_server", "iter_sops"]

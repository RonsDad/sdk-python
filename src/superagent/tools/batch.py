"""Batch tool for parallel tool invocation.

Modernized from the legacy TOOL_SPEC module-based pattern (strands_tools.batch) to
the current @tool decorator (strands.tools.decorator.tool). Logic is preserved
verbatim; only the signature and entry shape changed.

Example:
    from strands import Agent
    from superagent.tools import batch, http_request, use_aws

    agent = Agent(tools=[batch, http_request, use_aws])
    agent.tool.batch(invocations=[
        {"name": "http_request", "arguments": {"method": "GET", "url": "https://example.com"}},
    ])
"""

import traceback
from typing import Any

from strands import ToolContext, tool

try:
    from strands_tools.utils import console_util  # type: ignore
except Exception:  # pragma: no cover - console is optional
    console_util = None


@tool(context=True)
def batch(invocations: list[dict[str, Any]], tool_context: ToolContext) -> dict[str, Any]:
    """Invoke multiple other tools in parallel (by name) from a single message.

    Args:
        invocations: List of {"name": <tool_name>, "arguments": <dict>} entries.
        tool_context: Injected by the framework (carries toolUseId and invocation_state).

    Returns:
        ToolResult with per-invocation status and a summary.
    """
    console = console_util.create() if console_util else None
    tool_use_id = tool_context["tool_use"]["toolUseId"]
    agent = tool_context["invocation_state"].get("agent")
    results: list[dict[str, Any]] = []

    try:
        if agent is None or not hasattr(agent, "tool") or agent.tool is None:
            raise AttributeError("Agent does not have a valid 'tool' attribute.")

        for invocation in invocations:
            tool_name = invocation.get("name")
            arguments = invocation.get("arguments", {})
            tool_fn = getattr(agent.tool, tool_name, None)

            if callable(tool_fn):
                try:
                    result = tool_fn(**arguments)
                    results.append({"name": tool_name, "status": "success", "result": result})
                except Exception as e:
                    if console:
                        console.print(f"Error executing tool '{tool_name}': {e}")
                    results.append({
                        "name": tool_name,
                        "status": "error",
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    })
            else:
                msg = f"Tool '{tool_name}' not found in agent"
                if console:
                    console.print(msg)
                results.append({"name": tool_name, "status": "error", "error": msg})

        summary_lines = [f"Batch execution completed with {len(results)} tool(s):"]
        for r in results:
            mark = "✓" if r["status"] == "success" else "✗"
            detail = "Success" if r["status"] == "success" else f"Error - {r.get('error')}"
            summary_lines.append(f"{mark} {r['name']}: {detail}")

        return {
            "toolUseId": tool_use_id,
            "status": "success",
            "content": [
                {"text": "\n".join(summary_lines)},
                {
                    "json": {
                        "batch_summary": {
                            "total_tools": len(results),
                            "successful": sum(1 for r in results if r["status"] == "success"),
                            "failed": sum(1 for r in results if r["status"] == "error"),
                        },
                        "results": results,
                    }
                },
            ],
        }

    except Exception as e:
        error_msg = f"Error in batch tool: {e}\n{traceback.format_exc()}"
        if console:
            console.print(f"Error in batch tool: {e}")
        return {
            "toolUseId": tool_use_id,
            "status": "error",
            "content": [{"text": error_msg}],
        }

"""Custom Perplexity Agent API provider.

The Perplexity Agent API (``POST https://api.perplexity.ai/v1/agent``)
is a distinct endpoint from Perplexity's chat-completions endpoint. It
orchestrates the full agentic loop server-side (retrieval via
``web_search``/``fetch_url``, multi-model fallback, tool execution) and
streams events using a schema closely related to the OpenAI Responses
API (``response.output_text.delta`` events).

Because the Agent API has a distinct URL and schema, we implement it as
a first-class :class:`strands.models.Model` subclass rather than
bending ``OpenAIModel``. The implementation stays within the SDK
contract — it just overrides the four abstract methods and yields
``StreamEvent`` dicts.

Refs (external):
  - https://docs.perplexity.ai/docs/agent-api/quickstart
  - https://www.perplexity.ai/hub/blog/agent-api-a-managed-runtime-for-agentic-workflows
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any, TypeVar

from pydantic import BaseModel
from typing_extensions import override

from strands.models.model import Model
from strands.types.content import Messages, SystemContentBlock
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolChoice, ToolSpec

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_BASE_URL = "https://api.perplexity.ai"
AGENT_PATH = "/v1/agent"


def _messages_to_input(messages: Messages) -> list[dict[str, Any]]:
    """Convert Strands ``Messages`` into the Agent API ``input`` array.

    The Agent API accepts a list of role/content entries similar to the
    Chat Completions schema. We flatten each block's text, which covers
    the common case; binary/image content is rejected upstream by the
    superagent's resilience layer.
    """
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        text_parts: list[str] = []
        for block in msg.get("content", []) or []:
            if "text" in block and block["text"]:
                text_parts.append(block["text"])
        out.append({"role": role, "content": "\n".join(text_parts)})
    return out


def _system_to_instructions(
    system_prompt: str | None,
    system_prompt_content: list[SystemContentBlock] | None,
) -> str | None:
    """Collapse the Strands system-prompt surface into Perplexity's ``instructions``."""
    if system_prompt_content:
        parts: list[str] = []
        for block in system_prompt_content:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        if parts:
            return "\n\n".join(parts)
    return system_prompt


class PerplexityAgentModel(Model):
    """Perplexity Agent API model provider.

    Configuration shape::

        PerplexityAgentModel(
            api_key="pplx-...",
            base_url="https://api.perplexity.ai",
            model_id="sonar-pro",
            params={"max_output_tokens": 4096, "temperature": 0.2},
            tools=[{"type": "web_search", ...}, {"type": "fetch_url"}],
        )
    """

    def __init__(
        self,
        *,
        api_key: str | None,
        model_id: str,
        base_url: str = DEFAULT_BASE_URL,
        params: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        http_timeout: float = 600.0,
    ) -> None:
        """Initialize the provider.

        Args:
            api_key: Perplexity API key. Required.
            model_id: Agent model identifier (e.g. ``sonar-pro``).
            base_url: Base URL for the Perplexity API (defaults to public endpoint).
            params: Optional generation parameters (``max_output_tokens``,
                ``temperature``, ``top_p``, ``top_k``, ``stream``, ...).
            tools: Optional list of native Agent API tools (``web_search``,
                ``fetch_url``). These are merged with any Strands tool specs
                passed at stream time.
            http_timeout: httpx timeout in seconds for the streaming request.
        """
        if not api_key:
            raise ValueError(
                "PerplexityAgentModel requires api_key (or PERPLEXITY_API_KEY env var)"
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http_timeout = http_timeout
        self.config: dict[str, Any] = {
            "model_id": model_id,
            "params": params or {},
            "tools": tools or [],
        }
        logger.debug("PerplexityAgentModel initialized model_id=%s base_url=%s", model_id, base_url)

    @override
    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    @override
    def get_config(self) -> dict[str, Any]:
        return self.config

    def _build_request_body(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None,
        system_prompt: str | None,
        system_prompt_content: list[SystemContentBlock] | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.config["model_id"],
            "input": _messages_to_input(messages),
            "stream": True,
        }
        instructions = _system_to_instructions(system_prompt, system_prompt_content)
        if instructions:
            body["instructions"] = instructions
        tools: list[dict[str, Any]] = list(self.config.get("tools") or [])
        for spec in tool_specs or []:
            tools.append({
                "type": "function",
                "name": spec["name"],
                "description": spec.get("description"),
                "parameters": spec.get("inputSchema", {}).get("json", {}),
            })
        if tools:
            body["tools"] = tools
        body.update(self.config.get("params") or {})
        return body

    @override
    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: ToolChoice | None = None,
        system_prompt_content: list[SystemContentBlock] | None = None,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        """Stream a conversation from the Agent API.

        Implements the Strands ``StreamEvent`` protocol by translating
        the Agent API's SSE frames into
        ``messageStart`` → ``contentBlockDelta`` → ``contentBlockStop`` →
        ``messageStop`` events.
        """
        import httpx  # lazy; httpx is already a transitive dep via mcp

        body = self._build_request_body(messages, tool_specs, system_prompt, system_prompt_content)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        url = f"{self._base_url}{AGENT_PATH}"

        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {}}}

        stop_reason = "end_turn"
        usage: dict[str, int] = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            async with client.stream("POST", url, headers=headers, json=body) as response:
                response.raise_for_status()
                async for raw_line in response.aiter_lines():
                    if not raw_line or not raw_line.startswith("data:"):
                        continue
                    payload = raw_line.removeprefix("data:").strip()
                    if payload in ("", "[DONE]"):
                        continue
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        logger.warning("perplexity: non-JSON SSE frame: %r", payload[:80])
                        continue

                    etype = event.get("type")
                    if etype == "response.output_text.delta":
                        delta_text = event.get("delta", "")
                        if delta_text:
                            yield {
                                "contentBlockDelta": {
                                    "contentBlockIndex": 0,
                                    "delta": {"text": delta_text},
                                }
                            }
                    elif etype == "response.completed":
                        response_usage = event.get("response", {}).get("usage") or {}
                        usage = {
                            "inputTokens": response_usage.get("input_tokens", 0),
                            "outputTokens": response_usage.get("output_tokens", 0),
                            "totalTokens": response_usage.get("total_tokens", 0),
                        }
                        stop_reason = event.get("response", {}).get("stop_reason", "end_turn")
                    elif etype == "response.error":
                        err_msg = event.get("error", {}).get("message", "perplexity agent error")
                        raise RuntimeError(f"perplexity: {err_msg}")

        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": stop_reason}}
        yield {"metadata": {"usage": usage, "metrics": {"latencyMs": 0}}}

    @override
    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        """Request a JSON-schema-constrained response.

        The Agent API supports structured outputs via ``response_format``
        with JSON schema. We set that and collect the streamed text, then
        parse it into the pydantic model.
        """
        schema = output_model.model_json_schema()
        prior_params = dict(self.config.get("params") or {})
        self.config["params"] = {
            **prior_params,
            "response_format": {"type": "json_schema", "json_schema": {"schema": schema, "name": output_model.__name__}},
        }
        try:
            text_parts: list[str] = []
            async for event in self.stream(prompt, system_prompt=system_prompt):
                delta = event.get("contentBlockDelta", {}).get("delta", {})
                if "text" in delta:
                    text_parts.append(delta["text"])
            raw = "".join(text_parts)
            parsed = output_model.model_validate_json(raw)
            yield {"output": parsed}
        finally:
            self.config["params"] = prior_params


__all__ = ["PerplexityAgentModel", "DEFAULT_BASE_URL", "AGENT_PATH"]

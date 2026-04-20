"""HookProvider implementations for the superagent.

These providers are wired into ``Agent(hooks=[...])`` by
``superagent.runtime.bootstrap.build_agent``. Each class subscribes to a
distinct lifecycle event from :mod:`strands.hooks` and performs a single
cross-cutting concern:

  - :class:`LoggingHooks`         — request-level log breadcrumbs.
  - :class:`ToolTracingHooks`     — per-tool latency + outcome trace.
  - :class:`SessionCaptureHooks`  — message-level audit log to stderr.

None of these hooks mutate agent behavior; they only observe. Any hook
that mutates behavior (redaction, cancellation, retry) should live in a
separate module so intent is clear from the import path alone.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from strands.hooks import (
    AfterInvocationEvent,
    AfterToolCallEvent,
    AgentInitializedEvent,
    BeforeInvocationEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
    MessageAddedEvent,
)

logger = logging.getLogger(__name__)


class LoggingHooks(HookProvider):
    """Emit structured breadcrumbs around every agent invocation."""

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(AgentInitializedEvent, self._on_init)
        registry.add_callback(BeforeInvocationEvent, self._on_start)
        registry.add_callback(AfterInvocationEvent, self._on_end)

    def _on_init(self, event: AgentInitializedEvent) -> None:
        logger.info("agent.initialized name=%s", getattr(event.agent, "name", None))

    def _on_start(self, event: BeforeInvocationEvent) -> None:
        logger.info("agent.invocation.start name=%s", getattr(event.agent, "name", None))

    def _on_end(self, event: AfterInvocationEvent) -> None:
        logger.info(
            "agent.invocation.end name=%s has_result=%s",
            getattr(event.agent, "name", None),
            event.result is not None,
        )


class ToolTracingHooks(HookProvider):
    """Measure per-tool call latency and log outcome."""

    def __init__(self) -> None:
        self._starts: dict[str, float] = {}

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._on_before)
        registry.add_callback(AfterToolCallEvent, self._on_after)

    def _on_before(self, event: BeforeToolCallEvent) -> None:
        tool_use_id = event.tool_use.get("toolUseId", "")
        self._starts[tool_use_id] = time.monotonic()
        logger.info(
            "tool.call.start name=%s id=%s",
            event.tool_use.get("name"),
            tool_use_id,
        )

    def _on_after(self, event: AfterToolCallEvent) -> None:
        tool_use_id = event.tool_use.get("toolUseId", "")
        started = self._starts.pop(tool_use_id, None)
        elapsed_ms = int((time.monotonic() - started) * 1000) if started else -1
        status = event.result.get("status") if isinstance(event.result, dict) else "exception"
        logger.info(
            "tool.call.end name=%s id=%s status=%s elapsed_ms=%d",
            event.tool_use.get("name"),
            tool_use_id,
            status,
            elapsed_ms,
        )


class SessionCaptureHooks(HookProvider):
    """Log every message added to the conversation."""

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(MessageAddedEvent, self._on_message)

    def _on_message(self, event: MessageAddedEvent) -> None:
        role = event.message.get("role") if isinstance(event.message, dict) else "?"
        content = event.message.get("content") if isinstance(event.message, dict) else None
        n_blocks = len(content) if isinstance(content, list) else 0
        logger.info("message.added role=%s blocks=%d", role, n_blocks)


def build_default_hooks() -> list[HookProvider]:
    """Return the canonical hook stack used by ``runtime.bootstrap``."""
    return [LoggingHooks(), ToolTracingHooks(), SessionCaptureHooks()]


__all__ = [
    "LoggingHooks",
    "SessionCaptureHooks",
    "ToolTracingHooks",
    "build_default_hooks",
]

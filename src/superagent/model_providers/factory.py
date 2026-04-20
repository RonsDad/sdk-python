"""Dispatch table that turns a model-config JSON into a ``Model`` instance.

The factory is intentionally thin: each provider entry resolves to an SDK
``strands.models.*`` constructor with the right base_url / client args
injected. This keeps the superagent 100% SDK-compliant — the only
non-SDK piece is the custom Perplexity provider, which is a proper
``strands.models.Model`` subclass.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from strands.models import (
    AnthropicModel,
    BedrockModel,
    GeminiModel,
    LiteLLMModel,
    MistralModel,
    Model,
    OpenAIModel,
)

logger = logging.getLogger(__name__)

# OpenAI-compatible endpoints. Each entry is the provider's chat-completions
# base URL; the corresponding env var holds the API key.
_OPENAI_COMPATIBLE_BASES: dict[str, tuple[str, str]] = {
    # provider key     -> (base_url,                                            api_key_env)
    "xai":       ("https://api.x.ai/v1",                               "XAI_API_KEY"),
    "zai":       ("https://api.z.ai/api/paas/v4",                      "ZAI_API_KEY"),
    "moonshot":  ("https://api.moonshot.ai/v1",                        "MOONSHOT_API_KEY"),
    "deepseek":  ("https://api.deepseek.com/v1",                       "DEEPSEEK_API_KEY"),
    "alibaba":   ("https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "nim":       ("https://integrate.api.nvidia.com/v1",               "NVIDIA_API_KEY"),
    "vercel":    ("https://ai-gateway.vercel.sh/v1",                   "VERCEL_AI_GATEWAY_API_KEY"),
}


def _openai_compatible_builder(base_url: str, api_key_env: str) -> Callable[[dict[str, Any]], Model]:
    """Return a builder that constructs an ``OpenAIModel`` with the given base URL."""

    def _build(cfg: dict[str, Any]) -> Model:
        client_args: dict[str, Any] = {"base_url": base_url}
        if cfg.get("api_key"):
            client_args["api_key"] = cfg["api_key"]
        elif os.environ.get(api_key_env):
            client_args["api_key"] = os.environ[api_key_env]
        # caller-supplied client_args override
        client_args.update(cfg.get("client_args") or {})
        model_config = {"model_id": cfg["model_id"]}
        if cfg.get("params") is not None:
            model_config["params"] = cfg["params"]
        return OpenAIModel(client_args=client_args, **model_config)

    return _build


def _build_openai(cfg: dict[str, Any]) -> Model:
    client_args = dict(cfg.get("client_args") or {})
    if cfg.get("api_key"):
        client_args.setdefault("api_key", cfg["api_key"])
    model_config = {"model_id": cfg["model_id"]}
    if cfg.get("params") is not None:
        model_config["params"] = cfg["params"]
    return OpenAIModel(client_args=client_args, **model_config)


def _build_openai_responses(cfg: dict[str, Any]) -> Model:
    # Lazy import to avoid requiring openai>=2.0 unless the user selects this provider.
    from strands.models.openai_responses import OpenAIResponsesModel  # type: ignore

    client_args = dict(cfg.get("client_args") or {})
    if cfg.get("api_key"):
        client_args.setdefault("api_key", cfg["api_key"])
    model_config = {"model_id": cfg["model_id"]}
    if cfg.get("params") is not None:
        model_config["params"] = cfg["params"]
    return OpenAIResponsesModel(client_args=client_args, **model_config)


def _build_anthropic(cfg: dict[str, Any]) -> Model:
    client_args = dict(cfg.get("client_args") or {})
    if cfg.get("api_key"):
        client_args.setdefault("api_key", cfg["api_key"])
    kwargs: dict[str, Any] = {
        "model_id": cfg["model_id"],
        "max_tokens": cfg.get("max_tokens", 4096),
    }
    if cfg.get("params") is not None:
        kwargs["params"] = cfg["params"]
    return AnthropicModel(client_args=client_args, **kwargs)


def _build_gemini(cfg: dict[str, Any]) -> Model:
    client_args = dict(cfg.get("client_args") or {})
    if cfg.get("api_key"):
        client_args.setdefault("api_key", cfg["api_key"])
    kwargs: dict[str, Any] = {"model_id": cfg["model_id"]}
    if cfg.get("params") is not None:
        kwargs["params"] = cfg["params"]
    return GeminiModel(client_args=client_args, **kwargs)


def _build_mistral(cfg: dict[str, Any]) -> Model:
    kwargs: dict[str, Any] = {"model_id": cfg["model_id"]}
    for k in ("max_tokens", "temperature", "top_p", "stream"):
        if k in cfg:
            kwargs[k] = cfg[k]
    api_key = cfg.get("api_key") or os.environ.get("MISTRAL_API_KEY")
    client_args = dict(cfg.get("client_args") or {})
    return MistralModel(api_key=api_key, client_args=client_args, **kwargs)


def _build_litellm(cfg: dict[str, Any]) -> Model:
    kwargs: dict[str, Any] = {"model_id": cfg["model_id"]}
    if cfg.get("params") is not None:
        kwargs["params"] = cfg["params"]
    client_args = dict(cfg.get("client_args") or {})
    return LiteLLMModel(client_args=client_args, **kwargs)


def _build_bedrock(cfg: dict[str, Any]) -> Model:
    model_kwargs: dict[str, Any] = {}
    for k in (
        "model_id",
        "max_tokens",
        "cache_prompt",
        "cache_tools",
        "stop_sequences",
        "temperature",
        "top_p",
        "additional_request_fields",
        "additional_response_field_paths",
        "service_tier",
        "include_tool_result_status",
    ):
        if k in cfg:
            model_kwargs[k] = cfg[k]
    region_name = cfg.get("region_name")
    return BedrockModel(region_name=region_name, **model_kwargs)


def _build_perplexity(cfg: dict[str, Any]) -> Model:
    from .perplexity import PerplexityAgentModel  # lazy

    return PerplexityAgentModel(
        api_key=cfg.get("api_key") or os.environ.get("PERPLEXITY_API_KEY"),
        base_url=cfg.get("base_url", "https://api.perplexity.ai"),
        model_id=cfg["model_id"],
        params=cfg.get("params"),
        tools=cfg.get("native_tools"),
    )


PROVIDERS: dict[str, Callable[[dict[str, Any]], Model]] = {
    "anthropic": _build_anthropic,
    "bedrock": _build_bedrock,
    "gemini": _build_gemini,
    "litellm": _build_litellm,
    "mistral": _build_mistral,
    "openai": _build_openai,
    "openai_responses": _build_openai_responses,
    "perplexity": _build_perplexity,
}
for _name, (_url, _env) in _OPENAI_COMPATIBLE_BASES.items():
    PROVIDERS[_name] = _openai_compatible_builder(_url, _env)


def load_model_config(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Read a model-config JSON file from disk."""
    cfg_path = Path(os.fspath(path))
    if not cfg_path.is_file():
        raise FileNotFoundError(f"model config not found: {cfg_path}")
    with open(cfg_path, encoding="utf-8") as fh:
        return json.load(fh)


def build_model(config: dict[str, Any] | str | os.PathLike[str]) -> Model:
    """Construct a ``strands.models.Model`` from a declarative config.

    Args:
        config: Either a path to a model-config JSON file, or a parsed dict.
            Must contain a ``provider`` key listed in :data:`PROVIDERS` and a
            ``model_id`` key (except for providers that don't require one).

    Returns:
        A ready-to-use ``Model`` instance.
    """
    cfg = config if isinstance(config, dict) else load_model_config(config)
    provider = cfg.get("provider")
    if not provider:
        raise ValueError("model config must include a 'provider' field")
    if provider not in PROVIDERS:
        raise ValueError(
            f"unknown provider {provider!r}; valid: {sorted(PROVIDERS)}"
        )
    logger.debug("building model provider=%s model_id=%s", provider, cfg.get("model_id"))
    return PROVIDERS[provider](cfg)


__all__ = ["PROVIDERS", "build_model", "load_model_config"]

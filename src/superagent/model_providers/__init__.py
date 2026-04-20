"""Model provider factories for the superagent.

This package implements **Type 2** configuration: the model provider + model
ID + provider-specific kwargs (reasoning level, native server-side tools,
temperature, max_tokens, ...). It is kept strictly separate from
**Type 1** (agent name / system prompt / tool roster) because the
declarative ``AGENT_CONFIG_SCHEMA`` at
``strands/experimental/agent_config.py:22`` is ``additionalProperties: False``
— the agent config must stay model-only, so all provider wiring lives here.

The factory in :func:`build_model` reads a second JSON file and returns a
fully-constructed ``strands.models.Model`` instance ready to be passed as
``model=<instance>`` into ``config_to_agent``.

Supported providers:

  - ``bedrock``       -> ``strands.models.BedrockModel`` (AWS)
  - ``anthropic``     -> ``strands.models.AnthropicModel``
  - ``openai``        -> ``strands.models.OpenAIModel``
  - ``openai_responses`` -> ``strands.models.OpenAIResponsesModel``
  - ``gemini``        -> ``strands.models.GeminiModel`` (AI Studio)
  - ``mistral``       -> ``strands.models.MistralModel``
  - ``litellm``       -> ``strands.models.LiteLLMModel``
  - ``xai``           -> ``OpenAIModel`` @ ``https://api.x.ai/v1``
  - ``zai``           -> ``OpenAIModel`` @ ``https://api.z.ai/api/paas/v4``
  - ``moonshot``      -> ``OpenAIModel`` @ ``https://api.moonshot.ai/v1``
  - ``deepseek``      -> ``OpenAIModel`` @ ``https://api.deepseek.com/v1``
  - ``alibaba``       -> ``OpenAIModel`` @ DashScope compatible-mode
  - ``nim``           -> ``OpenAIModel`` @ ``https://integrate.api.nvidia.com/v1``
  - ``vercel``        -> ``OpenAIModel`` @ ``https://ai-gateway.vercel.sh/v1``
  - ``perplexity``    -> :class:`~superagent.model_providers.perplexity.PerplexityAgentModel`
"""

from .factory import PROVIDERS, build_model, load_model_config

__all__ = ["PROVIDERS", "build_model", "load_model_config"]
